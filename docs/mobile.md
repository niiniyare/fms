# FMS Attendant Mobile App — SRS & Design Guide

**Module:** FMS Mobile (Attendant PDQ/POS Terminal)  
**Version:** 1.0 Draft  
**Date:** 2026-09-01  
**Scope:** Attendant-facing only (supervisor/manager screens excluded)  
**Integration:** Odoo 18 FMS + PTS-2/3 + MPesa Daraja API + PDQ card terminal  

---

## 1. Purpose & Scope

This document defines requirements, user flows, and screen layouts for the **attendant mobile terminal** — a handheld PDQ/POS device used at the pump island. The attendant never touches Odoo desktop. Every action flows through this terminal.

### 1.1 Core Problem Solved

Manual transaction recording at the pump is error-prone and slow:
- Attendant guesses which customer owns a vehicle
- Payment method logged on paper, entered later
- MPesa payments matched by memory
- Cash shortfalls discovered at shift close — too late to fix

### 1.2 Out of Scope (This Document)

- Supervisor approval flows
- Shift open/close (supervisor device)
- Tank dip entry (supervisor device)
- GL / accounting screens
- Admin / configuration

---

## 2. Actors & Preconditions

| Actor | Role |
|---|---|
| Attendant | Operates pump, collects payment, uses this terminal |
| Odoo FMS | Source of truth: vehicles, customers, accounts, products |
| PTS-2/3 | Pump controller: authorizes flow, reports volume/amount |
| MPesa Daraja | Payment gateway: STK push, transaction query |
| PDQ Terminal | Card payment hardware (may be same device or paired) |

**Preconditions for attendant session:**
- Supervisor has opened the shift in Odoo FMS
- Attendant has clocked in and received terminal PIN
- Terminal is connected (WiFi/4G) and synced with active shift ID

---

## 3. Master User Flow

```
Attendant Login
      │
      ▼
[HOME SCREEN] — Pump island overview
      │
      ▼
Customer arrives at pump
      │
      ├── Has vehicle? ──YES──► [SCAN VEHICLE PLATE]
      │                               │
      │                         Plate recognized?
      │                          │           │
      │                         YES          NO
      │                          │           │
      │                   [CUSTOMER CARD]  [WALK-IN]
      │                          │           │
      └──────── NO ──────────────┘           │
                (walk-in, no vehicle)         │
                          │                  │
                          ▼                  ▼
                   [SELECT PRODUCT & AMOUNT / FILL]
                          │
                          ▼
                   [AUTHORIZE PUMP] ──► PTS starts flow
                          │
                          ▼
                   [FUELING IN PROGRESS]
                          │
                    Flow stops (nozzle)
                          │
                          ▼
                   [PAYMENT COLLECTION]
                    ┌─────┼──────┐
                  CASH  MPESA  CARD
                    │     │      │
                    ▼     ▼      ▼
              [CASH   [MPESA  [PDQ
               ENTRY]  FLOW]   FLOW]
                    │     │      │
                    └─────┼──────┘
                          │
                          ▼
                   [RECEIPT / CONFIRM]
                          │
                          ▼
                   [HOME SCREEN]
```

---

## 4. Detailed Flow Specifications

### 4.1 Flow A — Vehicle Scan → Customer Fetch

**Trigger:** Customer arrives, has a known vehicle (fleet/account customer)

**Steps:**
1. Attendant taps [Scan Plate] or [Type Plate]
2. Camera opens — OCR reads plate number
3. Terminal sends plate to Odoo FMS: `GET /api/fms/vehicle/{plate}`
4. Odoo returns:
   - Customer name
   - Account type: `CASH | CREDIT | PREPAID`
   - Credit limit & available credit (if CREDIT)
   - Prepaid balance (if PREPAID)
   - Allowed products (some fleets restrict product type)
   - Preferred pump (optional)
   - Vehicle make/model (for visual confirm)
5. Terminal shows **Customer Card** — attendant confirms visually

**Match failure paths:**

| Scenario | System Action |
|---|---|
| Plate not in Odoo | Offer: "Register new vehicle" or "Continue as walk-in" |
| Customer credit exceeded | Show limit + block auth (unless supervisor override) |
| Product not allowed | Show restriction, prompt product change |
| Account inactive/blocked | Show block reason, deny auth |

---

### 4.2 Flow B — Walk-In (No Vehicle / Unknown)

**Trigger:** Customer has no registered vehicle, or attendant skips scan

1. Attendant taps [Walk-In] on home screen
2. Selects product and amount/fill-up
3. Payment method selected **before** fueling if MPesa/Card
4. If Cash: authorize pump, fuel, collect after

---

### 4.3 Flow C — Pump Authorization

**Trigger:** Customer profile confirmed (or walk-in selected)

1. Attendant selects:
   - Product (Petrol / Diesel / Premium / etc.)
   - Amount (KES) **OR** Volume (litres) **OR** Fill Up
2. Terminal sends authorize command to PTS:
   - Pump number
   - Max amount / volume
   - Shift ID + attendant ID
   - Customer reference (if any)
3. PTS responds: `AUTHORIZED` or `ERROR`
4. Terminal shows [FUELING IN PROGRESS] screen
5. PTS streams live litres/KES to terminal during flow
6. Nozzle replaced → PTS sends `COMPLETE` event with final volume + amount

---

### 4.4 Flow D — Payment: Cash

**Trigger:** Customer paying cash (most common walk-in scenario)

**Sub-flow:**
1. After PTS `COMPLETE`, terminal shows final amount
2. Attendant taps [Cash]
3. Enters amount tendered
4. Terminal computes change
5. Attendant collects cash, confirms [Cash Received]
6. Transaction posts to shift: `cash_received += amount`
7. Receipt option shown

**Rules:**
- Cash transaction posts immediately to attendant running balance
- No pre-authorization needed — fuel first, collect after
- If customer underpays: terminal flags shortfall, attendant must resolve before next transaction on that nozzle

---

### 4.5 Flow E — Payment: MPesa

**Two sub-paths:**

#### E1 — STK Push (Prompt Customer)

1. After auth (or after fueling completes), attendant taps [MPesa]
2. Enters customer phone number (or fetches from customer profile)
3. Terminal triggers Daraja STK push for exact amount
4. Customer sees prompt on phone, enters M-PIN
5. Daraja callback: `SUCCESS` with `MpesaReceiptNumber`
6. Terminal shows confirmation, posts to shift
7. Receipt printed/SMS

#### E2 — Match from Recent MPesa Transactions

**Trigger:** Customer already paid via Paybill/Till before reaching pump (common scenario — customer pays at kiosk first)

1. After fueling completes, terminal shows final amount
2. Attendant taps [MPesa → Match Recent]
3. Terminal queries Daraja: `GET /transactions?amount={pump_amount}&window=15min`
4. Returns list of recent MPesa receipts matching that amount
5. Attendant selects correct receipt (shows sender name + time)
6. Terminal verifies receipt not already used (duplicate check in Odoo)
7. Posts to shift with receipt number

**Matching logic (server-side in Odoo):**
```
Match criteria:
  - Amount == pump_tx_amount ± 0 (exact)
  - Timestamp within 30 minutes of pump transaction start
  - Receipt not already linked to another shift transaction
  - Paybill/Till number matches station's registered number

If multiple matches: show list, attendant selects
If no match: fall back to STK push or manual receipt entry
```

**Manual fallback:**
- Attendant types MPesa receipt number manually
- System validates format (10-character alphanumeric)
- Odoo queries Daraja to verify receipt exists + amount matches
- If mismatch: show error, block post

---

### 4.6 Flow F — Payment: Card (PDQ)

1. After fueling completes, attendant taps [Card]
2. Terminal sends amount to paired PDQ hardware
3. Customer taps/inserts card
4. PDQ returns: `APPROVED` + authorization code + card last 4 digits
5. Terminal posts to shift: `card_received += amount`
6. Receipt printed from PDQ + terminal SMS option

**Partial card payment:**
- Customer pays partial by card, remainder by cash/MPesa
- Terminal supports split-tender: allocate amounts per method
- Both post to shift separately

---

## 5. Screen Designs

### SCREEN 01 — Attendant Login

```
┌─────────────────────────────────────┐
│  ⛽ FMS ATTENDANT                   │
│                                     │
│  Shift: MORNING  │  Station: MAIN   │
│  Date: 01-Sep-2026                  │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  Employee ID                │    │
│  │  [____________________]     │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  PIN                        │    │
│  │  [● ● ● ● ____]             │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │      [ SIGN IN ]            │    │
│  └─────────────────────────────┘    │
│                                     │
│  Pump assigned: P1, P2              │
└─────────────────────────────────────┘
```

**Behavior:**
- Employee ID auto-filled if terminal is dedicated to one attendant
- PIN is 4–6 digits
- On success: fetches active shift ID, syncs pump assignments
- If shift not open: "No active shift. Contact supervisor."

---

### SCREEN 02 — Home / Pump Overview

```
┌─────────────────────────────────────┐
│  Ali Hassan          MORNING SHIFT  │
│  Balance: KES 0  │  Txns: 0        │
│─────────────────────────────────────│
│                                     │
│  MY PUMPS                           │
│                                     │
│  ┌──────────────┐ ┌──────────────┐  │
│  │   PUMP 1     │ │   PUMP 2     │  │
│  │              │ │              │  │
│  │  ● IDLE      │ │  ● IDLE      │  │
│  │              │ │              │  │
│  │  [START TX]  │ │  [START TX]  │  │
│  └──────────────┘ └──────────────┘  │
│                                     │
│─────────────────────────────────────│
│  [MY BALANCE]  [HISTORY]  [HELP]    │
└─────────────────────────────────────┘
```

**Pump status colors:**
- Grey = IDLE (ready)
- Green = FUELING (live transaction)
- Yellow = AWAITING PAYMENT
- Red = ERROR / BLOCKED

---

### SCREEN 03 — Start Transaction (Pump Selected)

```
┌─────────────────────────────────────┐
│  ← PUMP 1                           │
│─────────────────────────────────────│
│                                     │
│  CUSTOMER                           │
│  ┌─────────────────────────────┐    │
│  │  📷 [SCAN PLATE]            │    │
│  │  ⌨️  [TYPE PLATE]           │    │
│  │  👤 [WALK-IN (NO VEHICLE)]  │    │
│  └─────────────────────────────┘    │
│                                     │
└─────────────────────────────────────┘
```

---

### SCREEN 04 — Plate Scan

```
┌─────────────────────────────────────┐
│  ← BACK             PUMP 1          │
│─────────────────────────────────────│
│                                     │
│  ┌─────────────────────────────┐    │
│  │                             │    │
│  │   [ CAMERA VIEWFINDER ]     │    │
│  │                             │    │
│  │   Align plate within frame  │    │
│  │                             │    │
│  │   ┌─────────────────────┐   │    │
│  │   │   KBZ 123A          │   │    │  ← detected
│  │   └─────────────────────┘   │    │
│  │                             │    │
│  └─────────────────────────────┘    │
│                                     │
│  [ CONFIRM: KBZ 123A ]              │
│  [ TYPE MANUALLY ]                  │
│                                     │
└─────────────────────────────────────┘
```

---

### SCREEN 05 — Customer Card (Vehicle Matched)

```
┌─────────────────────────────────────┐
│  ← BACK             PUMP 1          │
│─────────────────────────────────────│
│                                     │
│  ✅ VEHICLE FOUND                   │
│                                     │
│  Plate:    KBZ 123A                 │
│  Vehicle:  Toyota Hilux (White)     │
│                                     │
│  Customer: ACME Transport Ltd       │
│  Account:  CREDIT                   │
│  Limit:    KES 500,000              │
│  Used:     KES 312,450              │
│  Available:KES 187,550  ✅          │
│                                     │
│  Allowed products:                  │
│  ● Diesel  ● Petrol                 │
│                                     │
│─────────────────────────────────────│
│  [ CONFIRM — START TRANSACTION ]    │
│  [ NOT THIS CUSTOMER ]              │
└─────────────────────────────────────┘
```

**Credit warning state (if near limit):**
```
│  Available:KES 12,000  ⚠️ LOW       │
│  [ CONFIRM ]  [ CONTACT SUPERVISOR ]│
```

**Blocked state:**
```
│  ❌ ACCOUNT BLOCKED                 │
│  Reason: Overdue balance            │
│  [ WALK-IN CASH ONLY ]              │
│  [ CANCEL ]                         │
```

---

### SCREEN 06 — Product & Amount Selection

```
┌─────────────────────────────────────┐
│  ← BACK   ACME Transport / KBZ 123A │
│─────────────────────────────────────│
│                                     │
│  PRODUCT                            │
│  ┌──────────┐ ┌──────────┐          │
│  │ ● DIESEL │ │  PETROL  │          │
│  │ KES 182  │ │ KES 191  │          │
│  │  /litre  │ │  /litre  │          │
│  └──────────┘ └──────────┘          │
│                                     │
│  AMOUNT                             │
│  ┌──────────┐ ┌──────────┐ ┌──────┐ │
│  │  BY KES  │ │ BY LITRES│ │ FILL │ │
│  └──────────┘ └──────────┘ └──────┘ │
│                                     │
│  KES [ 5,000        ]               │
│                                     │
│  ≈ 27.47 litres @ KES 182           │
│                                     │
│─────────────────────────────────────│
│  PAYMENT (pre-select for MPesa/Card)│
│  ○ Cash (collect after)             │
│  ○ MPesa (prompt now)               │
│  ○ Card (prompt after)              │
│─────────────────────────────────────│
│  [ AUTHORIZE PUMP ]                 │
└─────────────────────────────────────┘
```

**Notes:**
- "Fill" = no cap, pump runs until nozzle replaced
- KES/litres toggle updates estimate live
- Payment pre-select: MPesa triggers STK push at authorization, not after fueling

---

### SCREEN 07 — Fueling in Progress

```
┌─────────────────────────────────────┐
│  PUMP 1 — FUELING                   │
│─────────────────────────────────────│
│                                     │
│  Customer: ACME Transport           │
│  Product:  Diesel                   │
│                                     │
│  ┌─────────────────────────────┐    │
│  │                             │    │
│  │   27.45 L                   │    │  ← live from PTS
│  │                             │    │
│  │   KES 4,995.90              │    │  ← live
│  │                             │    │
│  │   ████████████░░  91%       │    │  ← vs. requested
│  │                             │    │
│  └─────────────────────────────┘    │
│                                     │
│  ⏱  Elapsed: 00:01:23              │
│                                     │
│  [ STOP PUMP (EMERGENCY) ]          │
│                                     │
└─────────────────────────────────────┘
```

**Auto-advances** when PTS sends `COMPLETE` event.  
Emergency stop sends `HALT` command to PTS immediately.

---

### SCREEN 08 — Fueling Complete / Payment Selection

```
┌─────────────────────────────────────┐
│  ✅ FUELING COMPLETE — PUMP 1       │
│─────────────────────────────────────│
│                                     │
│  Product:  Diesel                   │
│  Volume:   27.47 L                  │
│  Amount:   KES 5,000.00             │
│  PTS Ref:  TXN-20260901-00847       │
│                                     │
│─────────────────────────────────────│
│  HOW IS CUSTOMER PAYING?            │
│                                     │
│  ┌────────┐  ┌────────┐  ┌────────┐ │
│  │        │  │        │  │        │ │
│  │  CASH  │  │ MPESA  │  │  CARD  │ │
│  │        │  │        │  │        │ │
│  └────────┘  └────────┘  └────────┘ │
│                                     │
│  [ SPLIT PAYMENT ]                  │
│                                     │
│  [ CREDIT ACCOUNT (ACME) ]          │
│                                     │
└─────────────────────────────────────┘
```

---

### SCREEN 09 — Cash Payment

```
┌─────────────────────────────────────┐
│  ← BACK              CASH PAYMENT   │
│─────────────────────────────────────│
│                                     │
│  Amount Due:   KES 5,000.00         │
│                                     │
│  Cash Received:                     │
│  ┌─────────────────────────────┐    │
│  │  KES  [ 5,000       ]       │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌──────┐ ┌──────┐ ┌──────┐        │
│  │ 5000 │ │ 1000 │ │  500 │        │  ← quick amounts
│  └──────┘ └──────┘ └──────┘        │
│                                     │
│  Change:       KES 0.00             │
│                                     │
│─────────────────────────────────────│
│  [ CONFIRM CASH RECEIVED ]          │
└─────────────────────────────────────┘
```

**Change state:**
```
│  Cash Received: KES 6,000           │
│  Change:        KES 1,000.00  💵    │
│  [ CONFIRM — GIVE CHANGE ]          │
```

**Underpayment state:**
```
│  Cash Received: KES 4,000           │
│  Shortfall:     KES 1,000.00  ⚠️    │
│  [ COLLECT REMAINING ]              │
│  [ POST SHORTFALL TO ACCOUNT ]      │  ← credit customers only
```

---

### SCREEN 10 — MPesa Payment

```
┌─────────────────────────────────────┐
│  ← BACK             MPESA PAYMENT   │
│─────────────────────────────────────│
│                                     │
│  Amount Due:   KES 5,000.00         │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  📱 PROMPT CUSTOMER (STK)   │    │
│  └─────────────────────────────┘    │
│                                     │
│  Phone: [ +254 7__ ___ ___ ]        │
│         (from profile or type)      │
│                                     │
│  [ SEND PROMPT ]                    │
│                                     │
│─────────────────────────────────────│
│         — OR —                      │
│─────────────────────────────────────│
│                                     │
│  ┌─────────────────────────────┐    │
│  │  🔍 MATCH RECENT PAYMENT    │    │
│  │  (customer already paid)    │    │
│  └─────────────────────────────┘    │
│                                     │
│  [ ENTER RECEIPT MANUALLY ]         │
│                                     │
└─────────────────────────────────────┘
```

---

### SCREEN 11 — MPesa STK Push Waiting

```
┌─────────────────────────────────────┐
│  MPESA — AWAITING CONFIRMATION      │
│─────────────────────────────────────│
│                                     │
│  Prompt sent to:                    │
│  +254 712 345 678                   │
│                                     │
│  ┌─────────────────────────────┐    │
│  │                             │    │
│  │   ⏳  Waiting...            │    │
│  │                             │    │
│  │   KES 5,000.00              │    │
│  │   Paybill: 247247           │    │
│  │   Acct: PUMP1               │    │
│  │                             │    │
│  └─────────────────────────────┘    │
│                                     │
│  Expires in: 02:47                  │
│                                     │
│  [ RESEND PROMPT ]                  │
│  [ CUSTOMER PAID — MATCH MANUAL ]   │
│  [ CANCEL MPESA — USE CASH/CARD ]   │
│                                     │
└─────────────────────────────────────┘
```

**On success (Daraja callback received):**

```
┌─────────────────────────────────────┐
│  ✅ MPESA CONFIRMED                 │
│─────────────────────────────────────│
│                                     │
│  Receipt:   QAB12345XY              │
│  Amount:    KES 5,000.00            │
│  From:      JOHN KAMAU              │
│  Time:      09:14:32                │
│                                     │
│  [ DONE ]                           │
│                                     │
└─────────────────────────────────────┘
```

---

### SCREEN 12 — MPesa Match Recent Transactions

```
┌─────────────────────────────────────┐
│  ← BACK        MATCH MPESA RECEIPT  │
│─────────────────────────────────────│
│                                     │
│  Showing payments of KES 5,000      │
│  in last 30 minutes                 │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ ✓  QAB12345XY               │    │
│  │    JOHN KAMAU               │    │
│  │    KES 5,000  │  09:12:45   │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │    QCD98765AB               │    │
│  │    MARY WANJIKU             │    │
│  │    KES 5,000  │  09:08:11   │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ ⚠️  PQR11122ZZ  USED        │    │  ← already matched
│  │    JAMES ODHIAMBO           │    │
│  │    KES 5,000  │  09:04:59   │    │
│  └─────────────────────────────┘    │
│                                     │
│  [ TYPE RECEIPT NUMBER ]            │
│  [ REFRESH ]                        │
│                                     │
└─────────────────────────────────────┘
```

**Select a receipt → confirmation screen → posts to shift.**

---

### SCREEN 13 — Manual Receipt Entry

```
┌─────────────────────────────────────┐
│  ← BACK      ENTER MPESA RECEIPT    │
│─────────────────────────────────────│
│                                     │
│  Receipt Number:                    │
│  ┌─────────────────────────────┐    │
│  │  [ QAB12345XY        ]      │    │
│  └─────────────────────────────┘    │
│                                     │
│  [ VERIFY RECEIPT ]                 │
│                                     │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─    │
│                                     │
│  Verifying...                       │
│                                     │
│  ✅ Receipt valid                   │
│     JOHN KAMAU                      │
│     KES 5,000.00                    │
│     Paid at: 09:12:45               │
│                                     │
│  [ CONFIRM & POST ]                 │
│                                     │
└─────────────────────────────────────┘
```

**Mismatch state:**
```
│  ❌ Amount mismatch                 │
│     Receipt: KES 4,500              │
│     Pump tx: KES 5,000              │
│  [ TRY DIFFERENT RECEIPT ]          │
│  [ SPLIT: 4500 MPESA + 500 CASH ]   │
```

---

### SCREEN 14 — Card Payment

```
┌─────────────────────────────────────┐
│  CARD PAYMENT                       │
│─────────────────────────────────────│
│                                     │
│  Amount:  KES 5,000.00              │
│                                     │
│  ┌─────────────────────────────┐    │
│  │                             │    │
│  │   💳 TAP / INSERT CARD      │    │
│  │                             │    │
│  │   Processing...  ⏳         │    │
│  │                             │    │
│  └─────────────────────────────┘    │
│                                     │
│  [ CANCEL ]                         │
│                                     │
└─────────────────────────────────────┘
```

**Success:**
```
│  ✅ APPROVED                        │
│     Auth: 029481                    │
│     Card: ****4821                  │
│  [ DONE ]                           │
```

**Declined:**
```
│  ❌ DECLINED                        │
│     Reason: Insufficient funds      │
│  [ TRY DIFFERENT CARD ]             │
│  [ USE CASH / MPESA ]               │
```

---

### SCREEN 15 — Split Payment

```
┌─────────────────────────────────────┐
│  ← BACK            SPLIT PAYMENT   │
│─────────────────────────────────────│
│                                     │
│  Total Due:    KES 5,000.00         │
│  Allocated:    KES 3,500.00         │
│  Remaining:    KES 1,500.00  ⚠️     │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  CASH      KES [ 3,500 ] ✅ │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │  MPESA     KES [ 1,500 ]    │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │  CARD      KES [ 0     ]    │    │
│  └─────────────────────────────┘    │
│                                     │
│  [ PROCESS MPESA PORTION ]          │
│                                     │
└─────────────────────────────────────┘
```

Amounts must sum to total — validation inline.

---

### SCREEN 16 — Credit Account Post

```
┌─────────────────────────────────────┐
│  POST TO CREDIT ACCOUNT             │
│─────────────────────────────────────│
│                                     │
│  Customer: ACME Transport Ltd       │
│  Amount:   KES 5,000.00             │
│                                     │
│  Before:   KES 312,450 used         │
│  After:    KES 317,450 used         │
│  Remaining:KES 182,550              │
│                                     │
│  ✅ Within credit limit             │
│                                     │
│  [ POST TO ACCOUNT ]                │
│  [ COLLECT CASH/MPESA INSTEAD ]     │
│                                     │
└─────────────────────────────────────┘
```

---

### SCREEN 17 — Receipt / Transaction Complete

```
┌─────────────────────────────────────┐
│  ✅ TRANSACTION COMPLETE            │
│─────────────────────────────────────│
│                                     │
│  Txn #:    FMS-20260901-00312       │
│  PTS Ref:  TXN-20260901-00847       │
│                                     │
│  Customer: ACME Transport           │
│  Vehicle:  KBZ 123A                 │
│  Product:  Diesel                   │
│  Volume:   27.47 L                  │
│  Amount:   KES 5,000.00             │
│  Payment:  MPesa QAB12345XY         │
│                                     │
│  Attendant: Ali Hassan              │
│  Time:     09:15:02                 │
│                                     │
│─────────────────────────────────────│
│  [ 🖨️  PRINT RECEIPT ]              │
│  [ 📱 SMS RECEIPT ]                 │
│  [ DONE — NEXT CUSTOMER ]           │
└─────────────────────────────────────┘
```

---

### SCREEN 18 — My Running Balance

```
┌─────────────────────────────────────┐
│  ALI HASSAN — MY BALANCE            │
│  MORNING SHIFT │ 01-Sep-2026        │
│─────────────────────────────────────│
│                                     │
│  Total Sales:    KES 187,500        │
│                                     │
│  Collected:                         │
│    Cash:         KES  82,000        │
│    MPesa:        KES  75,500        │
│    Card:         KES  20,000        │
│    Credit A/R:   KES  10,000        │
│                 ─────────────       │
│  Total Coll:    KES 187,500        │
│                                     │
│  Variance:       KES 0  ✅          │
│                                     │
│─────────────────────────────────────│
│  Transactions: 24                   │
│                                     │
│  [ VIEW TRANSACTION LIST ]          │
│  [ BACK ]                           │
└─────────────────────────────────────┘
```

---

### SCREEN 19 — Transaction History (Attendant)

```
┌─────────────────────────────────────┐
│  ← BACK         MY TRANSACTIONS     │
│─────────────────────────────────────│
│  09:15  KBZ 123A  Diesel  5,000  M  │
│  09:02  Walk-In   Petrol  3,200  C  │
│  08:51  KBJ 445Z  Diesel 12,000  A  │
│  08:33  Walk-In   Diesel  2,000  P  │
│  08:19  KCA 001B  Petrol  8,500  M  │
│  ...                                │
│─────────────────────────────────────│
│  M=MPesa  C=Cash  A=A/R  P=Card     │
│                                     │
│  [ FILTER BY PUMP ]                 │
│  [ FILTER BY PAYMENT ]              │
└─────────────────────────────────────┘
```

Tap any row → full receipt detail.

---

## 6. Non-Functional Requirements

### 6.1 Connectivity

| Scenario | Behavior |
|---|---|
| Full online | All features active, real-time PTS sync |
| Intermittent | Queue transactions locally, sync on reconnect |
| Full offline | Block new transactions, show last-known pump status |

Offline-first is critical — pump islands have poor indoor signal. Local SQLite queue with background sync to Odoo via REST.

### 6.2 Performance

| Operation | Target |
|---|---|
| Plate scan → customer fetch | < 2 seconds |
| Pump authorize command | < 1 second |
| MPesa STK push trigger | < 3 seconds |
| MPesa match query | < 2 seconds |
| Transaction post to Odoo | < 2 seconds |

### 6.3 Security

- PIN expires every shift; attendant re-authenticates per shift
- Session token scoped to: attendant ID + shift ID + assigned pumps
- Attendant cannot view other attendants' balances
- MPesa receipt numbers stored hashed + indexed (duplicate detection)
- Card data: PAN never stored; only last 4 digits + auth code
- All API calls over HTTPS/TLS 1.2+
- Device lock after 3 failed PIN attempts

### 6.4 Hardware

| Component | Spec |
|---|---|
| Terminal | Android 10+ handheld (e.g., Sunmi P2, PAX A920) |
| Scanner | Rear camera + embedded barcode scanner |
| Printer | Bluetooth receipt printer OR built-in (Sunmi) |
| Card reader | Built-in NFC + chip + swipe (Sunmi/PAX) |
| Connectivity | WiFi + 4G SIM failover |

---

## 7. API Endpoints (Odoo FMS — Mobile Consumer)

```
POST   /api/fms/auth/login                  Attendant login
GET    /api/fms/shift/active                Get active shift + pump assignments
GET    /api/fms/vehicle/{plate}             Fetch vehicle + customer profile
POST   /api/fms/transaction/start           Create transaction record
POST   /api/fms/transaction/{id}/authorize  Authorize pump via PTS
POST   /api/fms/transaction/{id}/complete   Record final volume/amount from PTS
POST   /api/fms/transaction/{id}/payment    Post payment (cash/mpesa/card/credit)
GET    /api/fms/mpesa/recent?amount=&min=   Query recent MPesa receipts
POST   /api/fms/mpesa/verify                Verify receipt number vs. Daraja
POST   /api/fms/mpesa/stk-push              Trigger STK push
GET    /api/fms/attendant/{id}/balance      Running balance for attendant
GET    /api/fms/attendant/{id}/transactions Attendant transaction history
```

---

## 8. PTS-2/3 Integration Points

| Event | Direction | Action |
|---|---|---|
| `AUTHORIZE` | App → PTS | Enable pump flow up to max amount/volume |
| `HALT` | App → PTS | Emergency stop |
| `FLOW_UPDATE` | PTS → App | Live litres/KES (stream, every 500ms) |
| `COMPLETE` | PTS → App | Final volume + amount, PTS transaction ref |
| `ERROR` | PTS → App | Pump fault — show error, alert supervisor |
| `DELIVERY_START` | PTS → FMS | Tank delivery beginning (PTS-3 with ATG) |
| `DIP_READING` | PTS → FMS | Automatic tank level (PTS-3 with ATG) |

PTS-2: meter-only (no tank gauge)  
PTS-3: meter + ATG (automatic tank gauge) — enables auto dip entry

---

## 9. Data Model (Mobile-Relevant Fields)

```python
# Posted to fms.shift.attendant.cash on each transaction:
{
    "shift_id": int,
    "attendant_id": int,
    "pump_id": int,
    "product_id": int,
    "volume": float,           # litres from PTS
    "amount": float,           # KES
    "pts_transaction_ref": str, # PTS-2/3 reference
    "pts_source": str,         # "PTS2" | "PTS3" | "MANUAL"
    "vehicle_plate": str,      # nullable (walk-in = null)
    "customer_id": int,        # nullable
    "payment_method": str,     # "CASH" | "MPESA" | "CARD" | "CREDIT"
    "mpesa_receipt": str,      # nullable
    "card_auth_code": str,     # nullable
    "card_last4": str,         # nullable
    "transaction_time": datetime,
}
```

---

## 10. Edge Cases & Business Rules

| Scenario | Rule |
|---|---|
| Customer drives off without paying | Attendant flags "DRIVE-OFF", supervisor notified, amount posted to loss account |
| MPesa receipt for wrong amount | Block post; offer split or request correct receipt |
| Pump overfills beyond requested amount | Post actual PTS amount, not requested amount; variance flagged |
| Two attendants claim same MPesa receipt | Second claim blocked (duplicate detection); supervisor resolves |
| Card declined mid-split | Roll back card portion; re-select payment for remainder |
| PTS connection drops during fueling | Cache transaction locally; reconcile on reconnect; alert supervisor |
| Customer requests product switch after auth | Cancel auth, re-authorize new product, new PTS transaction |
| Plate OCR misread | Manual override always available; no forced OCR lock |
| Same vehicle scanned twice in one shift | Warning: "Last transaction 12 min ago — KES 5,000 Diesel. Continue?" |

---

## 11. Implementation Notes

### 11.1 Framework Recommendation

**React Native + Expo** with:
- `expo-camera` for plate OCR (via Google ML Kit or Tesseract)
- `react-native-bluetooth-printer` for receipt printing
- `WatermelonDB` for local SQLite queue (offline-first)
- `react-native-pax` or generic serial/TCP for PDQ integration

**OR** Odoo PWA (if Odoo 18 mobile client covers the UX above) — test first before building native.

### 11.2 MPesa Daraja v2

- STK Push: `POST /mpesa/stkpush/v1/processrequest`
- Transaction status: `POST /mpesa/transactionstatus/v1/query`
- Use Daraja C2B confirmation URL to receive real-time receipts into Odoo — this is the feed that powers SCREEN 12 (match recent).

### 11.3 PTS Protocol

- Wayne Fusion / Gilbarco Passport: use IFSF protocol over TCP
- Generic serial pumps: RS-232/485 adapter to WiFi bridge
- Confirm vendor before finalizing authorize/halt command format

---

## 12. Future Screens (Post-MVP)

- Loyalty points display per transaction
- Carwash / LPG non-fuel sales entry (for residual allocation)
- Attendant handover to relief attendant (mid-shift balance transfer)
- Supervisor call button (one-tap escalation)
- Daily personal performance summary

---

*End of document.*
