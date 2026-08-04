# Shell Maanzoni Forecourt Management System (FMS)
## Comprehensive Specification, Technical Guide & UI/UX Strategy

**Version:** 1.0 (Phase 1 MVP)  
**Status:** Ready for Development  
**Target Platform:** Odoo 18 Community Edition  
**Timeline:** 5–6 weeks (1 developer)  
**Author:** Project Team  
**Date:** 2026-08-04

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Business Context & Problem Statement](#business-context)
3. [Functional Specification](#functional-specification)
4. [Technical Architecture](#technical-architecture)
5. [Odoo Integration Strategy](#odoo-integration-strategy)
6. [Module Dependencies & Evaluation](#module-dependencies)
7. [Business Logic Deep Dive](#business-logic-deep-dive)
8. [Data Models & Schema](#data-models)
9. [Security & Access Control](#security)
10. [UI/UX Design Framework](#ui-ux-design)
11. [Development Runbook](#development-runbook)
12. [Testing Strategy](#testing-strategy)
13. [Deployment & Operations](#deployment)
14. [Phase 2 Roadmap (Future)](#phase-2-roadmap)

---

# 1. Executive Summary

## What is FMS?

**Shell Maanzoni Forecourt Management System (FMS)** is a lightweight, operational fuel station management module for Odoo 18. It solves the core problem of **shift-based fuel reconciliation**: reconciling what pump meters say was sold against what actually arrived at the tank, and where the money went.

### The Problem It Solves

Traditional POS + Inventory systems assume:
- ✓ Every sale is recorded digitally
- ✓ Stock moves are instantaneous
- ✓ Cash reconciles perfectly

**Reality at a fuel station:**
- ✗ Attendants lump non-fuel sales (carwash, LPG, lubricants) into fuel categories for speed
- ✗ Pump meters drift; manual dip sticks show actual physical stock
- ✗ Cash and product mismatches are normal (human error, meter issues, theft)
- ✗ Shift close must happen **tonight**, not after an audit

### What FMS Delivers

**Phase 1 MVP (This Project):**
1. **Unified Shift Form** — all data entry in one screen
   - Opening meter readings (fetched from previous shift's log)
   - Closing meter readings (manual entry, per nozzle per attendant)
   - Opening dips (fetched from previous shift's log)
   - Closing dips (manual entry, per tank)
   - Per-attendant cash reconciliation
   - Reconciliation results (computed)

2. **Hard Gates Before Close**
   - FC Cash must equal exactly zero
   - All attendants must balance
   - Stock variance must be within meniscus (e.g., ±0.5%)

3. **Automatic Residual Allocation**
   - Attendant reports "MPesa KES 250,000 Diesel" but meter shows KES 180,000
   - System detects: "KES 70,000 is actually carwash/LPG"
   - Auto-allocates: -100L from Diesel, +104L to UX
   - Posts corrective journal entry
   - Result: inventory is accurate, cash is accurate, FC Cash = 0

4. **Immutable Audit Trail**
   - All meter/dip readings written to logs on close
   - Logs cannot be edited/deleted (compliance)
   - Next shift fetches opening readings from logs (no re-entry errors)

5. **Integration with Odoo Core**
   - Sales link to Odoo POS (auto-summed per attendant)
   - Dips link to stock locations (fuel tanks in Odoo warehouse)
   - Cash variance posts to GL via journal entries
   - Stock adjustments via Odoo inventory module

---

# 2. Business Context & Problem Statement

## Current State (Pre-FMS)

Shell Maanzoni runs on **ERPNext** (Frappe-based ERP):
- ✓ 25+ DocTypes across 7 tiers
- ✓ Comprehensive but over-engineered
- ✗ Requires 45+ manual steps to close a shift
- ✗ Weak relationships between Tank Readings, Meter Readings, Cash Events
- ✗ Data re-entry across multiple forms (error-prone)
- ✗ No automatic residual allocation (manual reconciliation takes 2+ hours)

## Why Migrate to Odoo?

| Aspect | ERPNext | Odoo 18 |
|--------|---------|---------|
| **Setup time** | 3+ months | 5 weeks |
| **Learning curve** | Steep (proprietary) | Gentle (industry standard) |
| **Extensibility** | Frappe framework | Odoo framework (broader ecosystem) |
| **Accounting module** | Limited | Full-featured IFRS/GAAP |
| **POS integration** | Manual | Native, modern |
| **Stock ledger** | Parallel bookkeeping | Single source of truth |
| **Customization** | DocType API | Model/View/Workflow |
| **Community support** | Small | Very large |
| **Cost** | Proprietary licensing | Open-source (community free) |

## Phase 1 Scope (MVP)

**In:** Shift close workflow, attendant cash, residual allocation, hard gates, immutable logs  
**Out:** Amendments, spot checks, drive-offs, delivery variance, PTS-2 integration, calibration charts, multi-region dashboards

---

# 3. Functional Specification

## 3.1 User Roles & Responsibilities

### Role: Fuel Station Attendant
**Permissions:** Create/edit meter & dip entries (only for their shift)
**Responsibilities:**
- Record opening meter readings at shift start
- Record closing meter readings at shift end
- Record dips (or confirm auto-fetched values)
- Report cash dropped to safe
- Report AR created (credit sales)
- Reconcile their personal cash balance

**Constraints:**
- Cannot close shift
- Cannot edit previous attendants' data
- Cannot post journal entries

### Role: Shift Supervisor
**Permissions:** Create/edit all shift data, review reconciliation, close shift, post corrections
**Responsibilities:**
- Oversee attendants' data entry
- Review reconciliation results
- Investigate variances
- Decide on FC Cash post (employee AR vs. expense)
- Post corrective journal entries if needed
- Close shift (if hard gates met)

**Constraints:**
- Cannot delete closed shifts
- Cannot edit meter/dip logs (read-only)

### Role: Station Manager / Accountant
**Permissions:** View reports, audit trails, manage site preferences
**Responsibilities:**
- Daily/weekly reconciliation reports
- Variance analysis
- Site preferences (acceptable variance %, account mappings)
- Compliance audit (EPRA, KRA)

---

## 3.2 Shift Lifecycle (State Machine)

```
┌─────────┐
│  Draft  │  Shift created, not yet opened
└────┬────┘
     │ action_open_shift()
     ↓
┌─────────┐
│  Open   │  Meter/dip entry active, POS linked, attendants working
└────┬────┘
     │ End of shift, supervisor reviews data
     ↓
┌─────────┐
│ Closing │  Attendants reconciling, system calculates residuals
└────┬────┘
     │ Hard gates check:
     │  • FC Cash = 0? ✓
     │  • All attendants clear? ✓
     │  • Stock variance < meniscus? ✓
     │
  NO │                                    │ YES
     ↓                                    ↓
┌──────────┐                         ┌─────────┐
│ Disputed │ Supervisor investigates │ Closed  │ Logs written, journals posted
└──────────┘ (manual intervention)    └─────────┘
     │
     └─ RESOLVE → Close
```

### Transition Rules

| From | To | Trigger | Conditions |
|---|---|---|---|
| Draft | Open | `action_open_shift()` | Attendants assigned, shift_date set |
| Open | Closing | Manual transition (UI button) | No automatic transition |
| Closing | Closed | `action_close_shift()` | All hard gates pass |
| Closing | Disputed | `action_dispute_shift()` | Supervisor marks for investigation |
| Disputed | Closed | Manual fix + `action_close_shift()` | After corrections posted |

---

## 3.3 Shift Form: Data Entry Flow

### Screen 1: Header & Opening Readings

```
┌────────────────────────────────────────────────────────────┐
│ SHIFT / SHT/2026/07/0421                                   │
│ Status: [OPEN]  Opened: 06:00  ⏱ In Progress              │
├────────────────────────────────────────────────────────────┤
│ HEADER INFO                                                 │
│ Station: [Shell Maanzoni]  Shift: [1 – Day 06:00–18:00]  │
│ Date: [27 July 2026]  Supervisor: [Supervisor Name]       │
│ Cashiers: [A. Njeri, S. Olieno, P. Kimani]                │
│ Price list: [EPRA cap – Machakos, effective 15 Jul 2026]  │
│ Variance tolerance: [±0.50% throughput]                   │
├────────────────────────────────────────────────────────────┤
│ OPENING READINGS (fetched from prev shift, auto-filled)   │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Tank | Dip Opening | Dip Closing (edit)              │  │
│ │ T1   | 5,000 L     | [________] L   [or height/temp] │  │
│ │ T2   | 8,200 L     | [________] L                     │  │
│ │ T3   | 12,100 L    | [________] L                     │  │
│ │ T4   | 11,250 L    | [________] L                     │  │
│ └──────────────────────────────────────────────────────┘  │
│ [+ Add tank line] [Load sample readings]                  │
│                                                             │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Pump | Nozzle | Attendant | Elec Vol | Man Mech     │  │
│ │ UX5  | A      | [Select]  | [RO: prev] [RO: prev]  │  │
│ │ UX5  | B      | [Select]  | [RO: prev] [RO: prev]  │  │
│ │ UX6  | A      | [Select]  | [RO: prev] [RO: prev]  │  │
│ │ DX5  | A      | [Select]  | [RO: prev] [RO: prev]  │  │
│ │ DX6  | A      | [Select]  | [RO: prev] [RO: prev]  │  │
│ │ VP1  | A      | [Select]  | [RO: prev] [RO: prev]  │  │
│ │ VP2  | A      | [Select]  | [RO: prev] [RO: prev]  │  │
│ │ VP3  | A      | [Select]  | [RO: prev] [RO: prev]  │  │
│ └──────────────────────────────────────────────────────┘  │
│ [+ Add nozzle line]                                        │
│                                                             │
│ ✓ Opening readings confirmed                              │
│ [NEXT →]                                                   │
└────────────────────────────────────────────────────────────┘
```

**Key Design Decisions:**
- Opening readings shown as read-only (fetched from previous shift's log)
- Auto-populated from master data (pumps/nozzles)
- Attendant dropdown pre-selected if possible
- "Load sample readings" button for testing
- Tab-through friendly (minimal scrolling)

### Screen 2: Closing Readings (End of Shift)

```
┌────────────────────────────────────────────────────────────┐
│ SHIFT / SHT/2026/07/0421                                   │
│ Status: [CLOSING]  Opened: 06:00  Closing: [Now]          │
├────────────────────────────────────────────────────────────┤
│ CLOSING DIPS (editable)                                    │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Tank | Opening | Closing (edit) | Variance | Status │  │
│ │ T1   | 5,000   | [5,480]        | -480L    | ⚠️ 9.6%│  │
│ │ T2   | 8,200   | [8,565]        | -365L    | ✓ 4.3% │  │
│ │ T3   | 12,100  | [11,750]       | +350L    | ⚠️ 2.9%│  │
│ │ T4   | 11,250  | [10,900]       | +350L    | ⚠️ 3.1%│  │
│ └──────────────────────────────────────────────────────┘  │
│ ⚠️ T1 variance exceeds meniscus (±0.5%). Investigate.    │
│                                                             │
│ CLOSING METER READINGS (editable)                         │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Pump│Nozzle│Attendant │Elec Vol Opening │Closing   │  │
│ │ UX5 │ A    │A. Njeri  │ 450,271        │[450,601] │  │
│ │ UX5 │ B    │A. Njeri  │ 462,357        │[462,687] │  │
│ │ UX6 │ A    │S. Olieno │ 141,104        │[141,617] │  │
│ │ DX5 │ A    │P. Kimani │ 141,104        │[142,617] │  │
│ │ DX6 │ A    │P. Kimani │ 886,114        │[887,498] │  │
│ │ VP1 │ A    │M. Wambuah│ 9,853,985      │[9,854,151]│ │
│ │ VP2 │ A    │M. Wambuah│ 78,853,138     │[78,860,000]│ │
│ │ VP3 │ A    │K. Martin │ 20,480,661     │[20,481,000]│ │
│ └──────────────────────────────────────────────────────┘  │
│ [+ Add nozzle line]                                        │
│ ✓ Closing readings confirmed                              │
│ [NEXT →]                                                   │
└────────────────────────────────────────────────────────────┘
```

### Screen 3: Attendant Cash Reconciliation

```
┌────────────────────────────────────────────────────────────┐
│ ATTENDANT CASH RECONCILIATION                              │
├────────────────────────────────────────────────────────────┤
│ Attendant: A. Njeri                                        │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ INCOMING                      │ OUTGOING             │  │
│ │ Sales (from POS):    694.56   │ Cash dropped: 695.00 │  │
│ │ Receipts/float:      0.00     │ AR created:   0.00   │  │
│ │ TOTAL IN:            694.56   │ Card paid:    0.00   │  │
│ │                                │ Mpesa paid:   0.00   │  │
│ │                                │ Expenses:     0.00   │  │
│ │                                │ TOTAL OUT:    695.00 │  │
│ │                                                       │  │
│ │ BALANCE: 694.56 - 695.00 = -0.44 KES                │  │
│ │ Status: ✗ Unbalanced (over by KES 0.44)              │  │
│ └──────────────────────────────────────────────────────┘  │
│ → Supervisor posts: DR FC Cash 0.44 | CR Miscounted 0.44 │
│                                                             │
│ Attendant: S. Olieno                                      │
│ [Similar layout]                                           │
│ BALANCE: 3,151.33 - 3,150.00 = +1.33 KES                 │
│ Status: ✓ Balanced                                        │
│                                                             │
│ Attendant: P. Kimani                                      │
│ [Similar layout]                                           │
│ BALANCE: 4,289.83 - 4,285.00 = +4.83 KES                │
│ Status: ⚠️ Unbalanced (short by KES 4.83)                 │
│ → Supervisor posts: DR Employee Advance 4.83             │
│                     CR FC Cash 4.83                       │
│                                                             │
│ TOTAL FC CASH BALANCE: +6.52 KES                          │
│ Status: ✗ NOT ZERO — shift cannot close                  │
│ [POST CORRECTION]  [NEXT →]                               │
└────────────────────────────────────────────────────────────┘
```

### Screen 4: Reconciliation Results (Read-only, Computed)

```
┌────────────────────────────────────────────────────────────┐
│ RECONCILIATION SUMMARY                                     │
├────────────────────────────────────────────────────────────┤
│ PRODUCT SALES RECONCILIATION                              │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Product      │ Meter  │ Invoiced │ Card  │ Residual │  │
│ │ V-Power      │ 330.41 │ 100.00   │ 295.0 │ -64.59   │  │
│ │ Unleaded     │ 1,102.43 │ 50.00  │ 1,000 │ +52.43   │  │
│ │ Diesel Extra │ 1,513.18 │ 400.00 │ 1,000 │ +113.18  │  │
│ │ LPG          │ 0.00   │ 0.00     │ 50.0  │ -50.00   │  │
│ └──────────────────────────────────────────────────────┘  │
│                                                             │
│ RESIDUAL ALLOCATION (System-calculated)                   │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ FROM (Over-reported) │ TO (Under-reported) │ Qty | Amt │ │
│ │ V-Power -64.59L      │ UX +52.43L         │ 63.8│ 11.4k│ │
│ │ LPG -50.00L          │ Diesel +113.18L    │ 50.0│ 11.2k│ │
│ └──────────────────────────────────────────────────────┘  │
│                                                             │
│ STOCK VARIANCE BY TANK                                    │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Tank | Opening | Purchases | Sales | Book | Actual  │  │
│ │ T1   | 5,000   | 2,000     | 1,520 | 5,480 | 5,000  │  │
│ │      | Variance: -480L (-9.6%) ⚠️ EXCEEDS MENISCUS  │  │
│ │                                                       │  │
│ │ T2   | 8,200   | 1,500     | 1,135 | 8,565 | 8,565  │  │
│ │      | Variance: 0.0L (0.0%) ✓ OK                   │  │
│ │                                                       │  │
│ │ T3   | 12,100  | 1,200     | 1,550 | 11,750 | 11,750│  │
│ │      | Variance: 0.0L (0.0%) ✓ OK                   │  │
│ │                                                       │  │
│ │ T4   | 11,250  | 0         | 350   | 10,900 | 10,900│  │
│ │      | Variance: 0.0L (0.0%) ✓ OK                   │  │
│ └──────────────────────────────────────────────────────┘  │
│                                                             │
│ ⚠️ HARD GATE FAILURES:                                    │
│ 1. ✗ Stock variance T1 exceeds meniscus                  │
│ 2. ✗ FC Cash balance is +0.00 KES (after posting)      │
│    → Supervisor must investigate T1 dip reading         │
│    → Supervisor must verify cash post                   │
│                                                             │
│ [INVESTIGATE]  [RETRY]  [CANNOT CLOSE YET]             │
└────────────────────────────────────────────────────────────┘
```

### Screen 5: Supervisor Review & Close Decision

```
┌────────────────────────────────────────────────────────────┐
│ CLOSE SHIFT: SUPERVISOR REVIEW                            │
├────────────────────────────────────────────────────────────┤
│ Shift: SHT/2026/07/0421  |  Status: CLOSING               │
│                                                             │
│ ✓ GATE 1: FC Cash = 0.00 KES (PASSED)                    │
│ ✓ GATE 2: All attendants clear (PASSED)                  │
│ ✗ GATE 3: Stock variance within meniscus                 │
│   → T1 variance: -480L (-9.6%) EXCEEDS ±0.5%             │
│   → Action: Supervisor must investigate                  │
│                                                             │
│ SUPERVISOR INVESTIGATION LOG                              │
│ ┌──────────────────────────────────────────────────────┐  │
│ │ Issue: T1 (V-Power) tank lost 480L                   │  │
│ │ Possible causes:                                      │  │
│ │   □ Meter drift (V-Power pump faulty)                │  │
│ │   □ Dip error (attendant mis-read closing dip)      │  │
│ │   □ Unrecorded delivery (fuel arrived unlogged)      │  │
│ │   □ Tank leak                                         │  │
│ │                                                       │  │
│ │ Finding: Pump UX5-A has known drift. Re-dipped tank. │  │
│ │ New reading: 5,320L (vs recorded 5,000L)            │  │
│ │ Revised variance: -160L (-3.0%) — STILL EXCEEDS      │  │
│ │                                                       │  │
│ │ Decision: Post adjustment entry to explain variance  │  │
│ │   DR: V-Power Loss (expense) 80 L × 189.00 = 15,120 │  │
│ │   CR: V-Power Inventory Adjustment 15,120            │  │
│ │                                                       │  │
│ │ Rationale: Tank leak suspected. Maintenance team     │  │
│ │ will inspect overnight. Variance acceptable.         │  │
│ │                                                       │  │
│ │ Supervisor: [Name]  Date: 27 July 2026  Time: 18:15 │  │
│ └──────────────────────────────────────────────────────┘  │
│                                                             │
│ After posting correction entry:                            │
│ ✓ GATE 3: Stock variance now -3.0% (PASSED)             │
│                                                             │
│ [POST CORRECTION ENTRY]  [REFRESH GATES]  [CLOSE SHIFT]  │
└────────────────────────────────────────────────────────────┘
```

### Screen 6: Final Close & Confirmation

```
┌────────────────────────────────────────────────────────────┐
│ SHIFT CLOSED SUCCESSFULLY                                 │
├────────────────────────────────────────────────────────────┤
│ Shift: SHT/2026/07/0421                                   │
│ Station: Shell Maanzoni                                    │
│ Date: 27 July 2026  |  Shift 1 (06:00–18:00)             │
│                                                             │
│ SUMMARY                                                    │
│ Total sales (all products):        8,135.72 L             │
│ Total sales amount:                1,445,986.95 KES       │
│ FC Cash balance:                   0.00 KES ✓             │
│ Stock variance:                    Within meniscus ✓      │
│ Attendants reconciled:             4/4 ✓                  │
│                                                             │
│ POSTED ENTRIES                                             │
│ • Sales Journal (JE001): +1,445,986.95 KES               │
│ • Cash Variance Journal (JE002): 0.00 KES                │
│ • Residual Allocation Journal (JE003): (internals)       │
│ • Inventory Adjustments: 8,135.72 L booked               │
│                                                             │
│ Closed at: 27 July 2026  18:15                           │
│ Closed by: Supervisor Name                                │
│ Next shift opens: 28 July 2026  06:00                    │
│                                                             │
│ [PRINT SHIFT REPORT]  [EMAIL ACCOUNTANT]  [DONE]         │
└────────────────────────────────────────────────────────────┘
```

---

# 4. Technical Architecture

## 4.1 System Design Principles

### Principle 1: Single Source of Truth
- **No parallel bookkeeping.** FMS data must post directly to Odoo GL.
- Meter readings → POS sales → GL (Fuel Revenue account)
- Dip readings → Stock location quantities (via inventory adjustments)
- Cash variance → GL (FC Cash account)

### Principle 2: Immutable Audit Trail
- Entry forms are mutable (supervisors can correct mistakes)
- Logs are immutable (once shift closes, logs are locked)
- All changes tracked (Odoo's tracking module)

### Principle 3: Minimal Data Entry
- 3 fields per nozzle (elec vol, man mech; elec cash computed)
- 2 fields per tank (opening dip, closing dip)
- 1 field per attendant (actual cash counted)
- Everything else computed or fetched from previous shift

### Principle 4: Automatic Reconciliation
- System calculates residuals automatically
- System allocates residuals automatically
- Manager reviews, not re-enters

### Principle 5: Hard Gates, No Overrides
- FC Cash must be exactly zero (no "close anyway" button)
- Stock variance must be within meniscus (no "acknowledge risk" button)
- System enforces compliance, not suggesting it

---

## 4.2 Integration with Odoo Core Modules

### A. Odoo POS Module

**What We Use:**
- `pos.order` — POS sales linked to shift
- `pos.session` — POS session (multiple per shift OK)
- `account.move` — Sales invoices generated by POS

**Integration Points:**
```python
# FMS Shift links to POS session
class FmsShift(models.Model):
    pos_session_ids = fields.Many2many("pos.session", 
        string="Linked POS Sessions",
        help="POS sessions that occurred during this shift")
    
    # On shift open:
    #  Create a new pos.session (or link existing)
    # On shift close:
    #  Confirm all pos.sessions (close_session_cbk())
    #  Sum sales per attendant (from pos.order.user_id)

# FMS Attendant Cash pulls from POS
@api.depends("shift_id", "attendant_id")
def _compute_sales_from_pos(self):
    for line in self:
        pos_orders = self.env["pos.order"].search([
            ("session_id", "in", line.shift_id.pos_session_ids.ids),
            ("user_id", "=", line.attendant_id.id),
        ])
        line.sales_amount = sum(o.amount_total for o in pos_orders)
```

**Why This Works:**
- POS is already real-time, we don't duplicate
- Sales data flows naturally POS → GL
- No custom sales entry needed (use POS interface)

---

### B. Odoo Stock Module

**What We Use:**
- `stock.location` — Fuel tanks (create as warehouse locations)
- `stock.quant` — Quantity on hand
- `stock.move` — Inventory movements
- `stock.inventory` — Physical inventory counts (dips)

**Integration Points:**
```python
# Dip entries link to stock locations
class FmsShiftDipEntry(models.Model):
    tank_id = fields.Many2one("stock.location", required=True,
        domain=[("fms_is_fuel_tank", "=", True)],
        help="Tank is a stock.location with custom attribute")

# On shift close, create inventory adjustment
def _post_inventory_adjustments(self):
    for dip_line in self.dip_entry_line_ids:
        inventory = self.env["stock.inventory"].create({
            "name": f"Dip - {dip_line.tank_id.name} - {self.shift_date}",
            "date": self.shift_date,
            "location_id": dip_line.tank_id.id,
            "line_ids": [(0, 0, {
                "product_id": dip_line.tank_id.fms_fuel_product_id.id,
                "location_id": dip_line.tank_id.id,
                "product_qty": dip_line.closing_vol,  # Physical count
                "theoretical_qty": self._compute_book_stock(dip_line.tank_id),
                # Theoretical = opening + purchases - sales
            })]
        })
        inventory.action_validate()
```

**Why This Works:**
- Dips become stock counts (inventory module's native data)
- Stock ledger is always accurate (purchases, sales, variances tracked)
- Reports in Inventory app work (available stock, movement history)
- No parallel bookkeeping

---

### C. Odoo Accounting Module

**What We Use:**
- `account.move` — Journal entries (sales, variances, cash)
- `account.account` — GL accounts
- `account.journal` — Journal configurations
- `account.move.line` — Line items

**Integration Points:**
```python
# On shift close, post journals
def _post_sales_journal(self):
    """
    Post daily sales as one journal entry:
    DR Cash 1,445,986.95 KES | CR Fuel Revenue 1,445,986.95 KES
    """
    lines = []
    for product_sales in self.product_sales_line_ids:
        cogs_acct = self._get_cogs_account(product_sales.product_id)
        revenue_acct = self._get_revenue_account(product_sales.product_id)
        
        lines.append((0, 0, {
            "account_id": cogs_acct.id,
            "debit": product_sales.residual_amount,  # Cost of goods
        }))
        lines.append((0, 0, {
            "account_id": revenue_acct.id,
            "credit": product_sales.residual_amount,  # Revenue
        }))
    
    if lines:
        move = self.env["account.move"].create({
            "move_type": "entry",
            "date": self.shift_date,
            "ref": f"Shift sales — {self.name}",
            "line_ids": lines,
            "journal_id": self._get_sales_journal().id,
            "company_id": self.company_id.id,
        })
        move.action_post()
        self.journal_entry_id = move.id
```

**Why This Works:**
- Sales post directly to GL (no intermediate staging)
- GL is always accurate (daily basis)
- Standard Odoo reports work (P&L, trial balance, etc.)

---

### D. Odoo HR Module

**What We Use:**
- `hr.employee` — Employee master (attendants, supervisors)
- Employee can be linked to attendant cash line

**Integration Points:**
```python
class FmsShiftAttendantCash(models.Model):
    attendant_id = fields.Many2one("hr.employee", required=True)
    # Attendant balance becomes AR (receivable from employee)
```

---

## 4.3 Odoo Core vs. Custom Trade-Offs

| Feature | Use Odoo Core? | Reasoning |
|---------|---|---|
| POS sales capture | ✓ Yes | POS module is mature, why duplicate? |
| Customer invoices | ✓ Yes | Odoo `account.move` handles this |
| Stock tracking | ✓ Yes | `stock.move` + `stock.quant` is standard |
| GL posting | ✓ Yes | `account.move` is standard |
| Employee tracking | ✓ Yes | `hr.employee` is standard |
| **Shift orchestration** | ✗ Custom | No standard module for fuel shift close |
| **Meter readings** | ✗ Custom | Fuel-specific, not in core |
| **Dip readings** | ✗ Custom | Fuel-specific, not in core |
| **Residual allocation** | ✗ Custom | Algorithm specific to fuel business |
| **Attendant cash** | ✗ Custom | Fuel-specific reconciliation logic |
| **Hard gates** | ✗ Custom | Business logic specific to Shell |

---

# 5. Odoo Integration Strategy

## 5.1 Database Schema Extensions

### A. Extend stock.location (Tanks)

```python
# In module init, add field to stock.location
class StockLocation(models.Model):
    _inherit = "stock.location"
    
    fms_is_fuel_tank = fields.Boolean(
        string="Is Fuel Tank",
        help="Location represents a physical fuel tank")
    
    fms_fuel_product_id = fields.Many2one("product.product",
        string="Fuel Product",
        domain=[("fms_is_fuel", "=", True)],
        help="Which fuel product is stored here")
    
    fms_tank_capacity_liters = fields.Float(
        string="Tank Capacity (L)")
    
    fms_calibration_chart_id = fields.Many2one(
        "fms.tank.calibration",
        string="Calibration Chart (Phase 2)",
        help="Height → Volume mapping")
```

### B. Extend product.product (Fuels)

```python
class ProductProduct(models.Model):
    _inherit = "product.product"
    
    fms_is_fuel = fields.Boolean(
        string="Is Fuel Product",
        help="Flag for FMS fuel products")
    
    fms_cogs_account_id = fields.Many2one("account.account",
        string="COGS Account",
        domain=[("account_type", "=", "expense")],
        help="GL account for fuel cost of goods sold")
    
    fms_revenue_account_id = fields.Many2one("account.account",
        string="Revenue Account",
        domain=[("account_type", "=", "income")],
        help="GL account for fuel sales revenue")
```

### C. Extend hr.employee (Attendants)

```python
class HrEmployee(models.Model):
    _inherit = "hr.employee"
    
    fms_is_attendant = fields.Boolean(
        string="Is Fuel Station Attendant")
    
    fms_pumps_assigned = fields.Many2many("fms.pump",
        string="Assigned Pumps",
        help="Pumps this attendant can operate")
```

---

## 5.2 Custom Model Hierarchy

```
FMS Core
├─ fms.shift (Main shift orchestration)
│  ├─ fms.shift.meter.entry (Entry form children)
│  ├─ fms.shift.dip.entry
│  ├─ fms.shift.attendant.cash
│  ├─ fms.shift.product.sales (Computed children)
│  ├─ fms.shift.residual.allocation
│  └─ fms.shift.tank.summary (Computed children)
│
└─ FMS Master Data
   ├─ fms.pump (Pump definitions)
   │  └─ fms.pump.nozzle (Nozzles per pump)
   ├─ fms.site.preferences (Configuration)
   │
   └─ FMS Immutable Logs (Written on shift close)
      ├─ fms.meter.log (Read-only after create)
      └─ fms.dip.log (Read-only after create)
```

---

# 6. Module Dependencies & Evaluation

## 6.1 Core Dependencies

### Required (Bundled with Odoo 18 Community)

| Module | Version | Purpose | Our Use |
|--------|---------|---------|----------|
| `base` | 18.0 | Core framework | Security, users, companies |
| `stock` | 18.0 | Inventory | Tank locations, stock moves, counts |
| `account` | 18.0 | Accounting | GL, journal entries, accounts |
| `point_of_sale` | 18.0 | POS | Sales capture, attendant linking |
| `hr` | 18.0 | HR | Employee master, attendants |
| `web` | 18.0 | Web interface | Forms, reports, UI |

**Cost:** $0 (all included in Odoo Community)

---

### Optional (Recommended Add-ons, Community)

| Module | Source | Version | Purpose | Why Include? |
|--------|--------|---------|---------|---|
| `web_grid` | Community | 18.0 | Editable tree/grid UI | Make entry forms faster |
| `web_responsive` | Community | 18.0 | Mobile-responsive views | Attendants use tablets |
| `base_automation` | Community | 18.0 | Workflow automation | Auto-open next shift |
| `mail` | Bundled | 18.0 | Chatter + messaging | Audit trail comments |
| `document` | Bundled | 18.0 | Document management | Shift reports PDF storage |

**Cost:** $0 (all open-source)

---

## 6.2 Module We Will NOT Use (Why)

### ❌ Inventory Valuation Methods (Standard Odoo)
**Standard Odoo Options:**
- FIFO (First-in-first-out)
- Weighted Average Cost
- Real-time valuation

**Why FMS Can't Use It:**
- Fuel is fungible (identical product, not differentiated by batch)
- Residual allocation creates "phantom" movements (from Diesel → UX)
- Standard methods don't handle mid-shift corrections

**Our Approach:**
- **Simple average cost** (no FIFO needed, products are identical)
- **Manual journal entries** for residual allocation (simpler than valuation layers)
- **Inventory counts trump system** (dips are the source of truth, not GL)

---

### ❌ Manufacturing (MRP)
**What It Does:** Bill of materials, production orders, work orders
**Why We Don't Need It:** Fuel isn't manufactured, just stored & sold

---

### ❌ Advanced Warehouse Management (Multi-step picks)
**What It Does:** Putaway, picking routes, stock transfers
**Why We Don't Need It:** Fuel tanks are simple locations, no multi-step movement

---

## 6.3 Open-Source Alternative Consideration

### Scenario: "Can we use ERPNext instead?"

| Aspect | Odoo 18 | ERPNext |
|--------|---------|----------|
| **Setup time** | 5 weeks | 12+ weeks |
| **Learning curve** | Gentle (industry standard) | Steep (Frappe framework) |
| **Community support** | Huge (700k+ developers) | Smaller (less adoption) |
| **Accounting** | Full IFRS/GAAP | Basic |
| **POS integration** | Modern, native | Manual workflows |
| **Stock ledger** | Single source of truth | Separate module, can drift |
| **Extensibility** | Large ecosystem | Smaller |
| **Cost** | $0 (community) | $0 (community) |
| **Database** | PostgreSQL (mature) | MariaDB/PostgreSQL |

**Verdict:** Odoo 18 is better for FMS. ERPNext would add 2–3 months to timeline without technical benefit.

---

# 7. Business Logic Deep Dive

## 7.1 The Residual Allocation Algorithm

This is the **core innovation** that makes FMS work with lumped non-fuel payments.

### The Problem

```
Attendant's Daily Report (at shift end):
─────────────────────────────────────
✓ Diesel: MPesa 250,000 KES
✓ UX: Card 180,000 KES
✓ Cash (all products): 100,000 KES
Total: 530,000 KES

Pump Meter Reality:
─────────────────────────────────────
Diesel meter: 1000L sold @ 222.80 = 222,800 KES (not 250,000!)
UX meter: 500L sold @ 214.00 = 107,000 KES (not 180,000!)
Total: 329,800 KES (huge discrepancy vs 530,000!)

Why?
─────────────────────────────────────
The attendant lumped in non-fuel sales to speed up service:
• 100L of carwash (@ 150/L = 15,000 KES)
• 50L of LPG (@ 214/L = 10,700 KES)
• Miscellaneous items (200,000 KES)
All reported as "Diesel MPesa" for simplicity.

System must detect and reallocate:
  Diesel -100L (remove carwash)
  UX +104L (the cost is now UX's responsibility)
  LPG +50L (separate line item)
  Other Products +200k (remainder)
```

### The Algorithm

**Step 1: Calculate Meter Volume Per Product**
```python
for product in [Diesel, UX, LPG, VPower]:
    meter_volume = sum(
        pump_reading.qty_sold
        for pump_reading in shift.pump_readings
        where pump_reading.product == product
    )
    meter_amount = meter_volume * product_price
```

**Step 2: Calculate Accounted Volume (From Invoices + Card)**
```python
for product in [Diesel, UX, LPG, VPower]:
    invoiced_volume = sum(
        invoice.qty for invoice in shift.invoices
        where invoice.product == product
    )
    
    card_volume = sum(
        attendant_cash_line.card_paid / product_price
        for attendant_cash_line in shift.attendant_cash_lines
        where attendant_cash_line.product_allocated == product
    )
    
    accounted_volume = invoiced_volume + card_volume
```

**Step 3: Calculate Residual (What's Unaccounted)**
```python
for product in [Diesel, UX, LPG, VPower]:
    residual_volume = meter_volume - accounted_volume
    residual_amount = residual_volume * product_price
    
    # Residual can be +/- or zero
    if residual_amount < -0.01:
        products_over_reported[product] = abs(residual_amount)
    elif residual_amount > 0.01:
        products_under_reported[product] = residual_amount
```

**Step 4: Auto-Allocate (Greedy Algorithm)**
```python
allocations = []

# Match over-reported products with under-reported
for (over_product, over_amount) in products_over_reported.items():
    for (under_product, under_amount) in products_under_reported.items():
        if over_amount < 0.01 or under_amount < 0.01:
            continue  # Already allocated
        
        # Allocate min(over, under)
        alloc_amount = min(over_amount, under_amount)
        
        # Convert amount to quantity (using product prices)
        alloc_qty = alloc_amount / get_price(under_product)
        
        allocations.append({
            "from_product": over_product,
            "to_product": under_product,
            "quantity": alloc_qty,
            "amount": alloc_amount,
            "reason": "Automatic residual reconciliation"
        })
        
        # Reduce both
        products_over_reported[over_product] -= alloc_amount
        products_under_reported[under_product] -= alloc_amount
```

**Step 5: Post Adjustment Journals**
```python
for allocation in allocations:
    over_cogs = get_cogs_account(allocation.from_product)
    under_cogs = get_cogs_account(allocation.to_product)
    
    journal_entry.add_line({
        "account": over_cogs,
        "credit": allocation.amount,  # Reduce COGS (it wasn't really sold)
    })
    
    journal_entry.add_line({
        "account": under_cogs,
        "debit": allocation.amount,  # Increase COGS (product actually sold)
    })
```

### Example Walkthrough

**Meter Reality (Pump readings):**
```
Diesel:  1000L @ 222.80 = 222,800 KES
UX:       500L @ 214.00 = 107,000 KES
LPG:       50L @ 100.00 =   5,000 KES
VPower:   80L @ 189.00 = 15,120 KES
───────────────────────
Total:             349,920 KES
```

**Attendant's Report (Card + MPesa):**
```
MPesa (Diesel):     250,000 KES
Card (UX):          180,000 KES
Cash:               100,000 KES
───────────────────────
Total:              530,000 KES  ← MISMATCH!
```

**Accounted (Invoices + part of card/mpesa):**
```
Diesel invoices:    50,000 KES
UX invoices:        20,000 KES
Card UX:            80,000 KES
Card Other:         50,000 KES
MPesa Diesel:       180,000 KES
Cash:               100,000 KES
───────────────────────
Total:              480,000 KES
```

**Residuals:**
```
Diesel:
  Meter:     222,800 KES
  Accounted: 230,000 (50k invoice + 180k mpesa)
  Residual:  -7,200 KES (OVER-REPORTED)
  
UX:
  Meter:     107,000 KES
  Accounted: 100,000 (20k invoice + 80k card)
  Residual:  +7,000 KES (UNDER-REPORTED)
  
LPG:
  Meter:     5,000 KES
  Accounted: 0 KES
  Residual:  +5,000 KES (UNDER-REPORTED)
  
VPower:
  Meter:     15,120 KES
  Accounted: 0 KES
  Residual:  +15,120 KES (UNDER-REPORTED)
```

**Allocation:**
```
Diesel -7,200 → UX +7,000  (7000 kES worth of UX was wrongly called Diesel)
Diesel -200 → LPG +200     (200 kES worth of LPG was wrongly called Diesel)
VPower +15,120 (no match, stays as VPower unaccounted)
  → Could be genuine VPower sale not recorded
  → Or carwash/misc lumped into VPower
  → Supervisor reviews and decides
```

**Journal Entries Posted:**
```
Entry 1: Diesel Allocation to UX
DR UX COGS          7,000 KES
CR Diesel COGS           7,000 KES

Entry 2: Diesel Allocation to LPG
DR LPG COGS           200 KES
CR Diesel COGS          200 KES
```

**Result:**
- Inventory adjusted: Diesel -31.3L, UX +32.7L, LPG +2L
- Cash is now correct (no unexplained shortages)
- GL reflects true product mix
- FC Cash = 0 (supervisor confirmed or posted variance)

---

## 7.2 FC Cash Account Logic

### What is FC Cash?

**FC Cash** = "Forecourt Cash" = physical cash in the till(s) at the station

```
Opening FC Cash (previous shift = 0)
+ All cash sales during shift
+ All cash receipts (floats, advances)
- All cash drops to safe
- All cash expenses (office supplies, repairs paid in cash)
- All customer AR (credit sales given but cash not received)
- All card/Mpesa transfers (money left the forecourt)
= Closing FC Cash (MUST = 0 for next shift to open)
```

### Why Must It Be Zero?

- **Open**: FC Cash = 0 (safe is secure, all cash accounted for)
- **Shift operates**: Cash accumulates in till
- **Close**: Attendants drop all cash to safe (0 left in till)
- **Post variance**: If there's a shortage/overage, supervisor posts to employee/expense account
- **Sealed**: FC Cash = 0 again, ready for next shift

**Example:**
```
Opening FC Cash: 0 KES
+ Sales:         8,100,000 KES
+ Receipts:      50,000 KES
- Cash dropped:  8,000,000 KES
- Expenses:      100,000 KES
= Closing FC Cash: +50,000 KES (OVERAGE)

Supervisor posts:
  DR FC Cash 50,000
  CR Miscellaneous Income 50,000
  (Or: DR FC Cash 50,000 | CR Employee Receivable 50,000
   if money was accidentally left with attendant)

After posting: FC Cash = 0, shift can close
```

---

## 7.3 Hard Gates Explained

### Gate 1: FC Cash = 0 (Exactly)

**Why:** Every KES must be accounted for. No "close enough" in accounting.

**Trigger:** Hard constraint, no override

**Action if fails:** Supervisor posts adjustment entry, then retries close

---

### Gate 2: All Attendants Clear

Each attendant's balance = (Sales + Receipts) - (Cash + AR + Card + Expenses) must = 0

**Why:** Accountability. Each person must reconcile their portion.

**Trigger:** Hard constraint, no override

**Action if fails:** That attendant works with supervisor to find discrepancy, then retries

---

### Gate 3: Stock Variance Within Meniscus

For each tank: |Book Stock - Closing Dip| ≤ meniscus (e.g., ±0.5%)

**Why:** Prevents posting with bad data. Supervisor must investigate high variances.

**Trigger:** Hard constraint, no override (unless supervisor posts correction entry explaining variance)

**Action if fails:** Supervisor re-dips tanks, or posts adjustment entry + notes

---

# 8. Data Models & Schema

## 8.1 Complete Model Definitions

### **Core Model: fms.shift**

```python
class FmsShift(models.Model):
    _name = "fms.shift"
    _description = "Forecourt Shift"
    _order = "shift_date desc, shift_label desc"
    
    # ═══════════════════════════════════════════════════════════
    # IDENTIFIERS & STATE
    # ═══════════════════════════════════════════════════════════
    
    name = fields.Char(readonly=True, copy=False)
    # Auto-generated: SHT/2026/07/0421
    
    company_id = fields.Many2one("res.company", required=True, ondelete="cascade")
    # Which station (company record)
    
    shift_date = fields.Date(required=True, index=True)
    # Shift date (00:00 that day, regardless of which calendar day it spans)
    
    shift_label = fields.Selection([
        ("1_day", "1 – Day (06:00–18:00)"),
        ("2_evening", "2 – Evening (14:00–22:00)"),
        ("3_night", "3 – Night (22:00–06:00)"),
    ], required=True, help="Shift time period")
    
    status = fields.Selection([
        ("draft", "Draft"),
        ("open", "Open"),
        ("closing", "Closing"),
        ("closed", "Closed"),
        ("disputed", "Disputed"),
    ], default="draft", tracking=True)
    
    # ═══════════════════════════════════════════════════════════
    # PEOPLE
    # ═══════════════════════════════════════════════════════════
    
    supervisor_id = fields.Many2one("hr.employee", required=True,
        help="Supervisor in charge of this shift")
    
    opened_by_user_id = fields.Many2one("res.users", readonly=True)
    closed_by_user_id = fields.Many2one("res.users", readonly=True)
    
    opened_at = fields.Datetime(readonly=True)
    closed_at = fields.Datetime(readonly=True)
    
    # ═══════════════════════════════════════════════════════════
    # PRICE & CONFIGURATION
    # ═══════════════════════════════════════════════════════════
    
    price_list_id = fields.Many2one("product.pricelist", 
        compute="_get_current_pricelist",
        help="EPRA price list at shift_date")
    
    variance_tolerance_pct = fields.Float(
        compute="_get_variance_tolerance",
        help="Acceptable stock variance % (e.g., 0.5%)")
    
    # ═══════════════════════════════════════════════════════════
    # ENTRY DATA (Editable during shift)
    # ═══════════════════════════════════════════════════════════
    
    meter_entry_line_ids = fields.One2many(
        "fms.shift.meter.entry", "shift_id",
        string="Meter Readings",
        help="Pump meter readings (one per nozzle)")
    
    dip_entry_line_ids = fields.One2many(
        "fms.shift.dip.entry", "shift_id",
        string="Dip Readings",
        help="Tank dip readings (opening + closing)")
    
    attendant_cash_line_ids = fields.One2many(
        "fms.shift.attendant.cash", "shift_id",
        string="Attendant Cash Reconciliation",
        help="Per-attendant cash reconciliation")
    
    # ═══════════════════════════════════════════════════════════
    # RECONCILIATION (Computed, read-only)
    # ═══════════════════════════════════════════════════════════
    
    product_sales_line_ids = fields.One2many(
        "fms.shift.product.sales", "shift_id",
        string="Product Sales",
        compute="_compute_product_sales", store=True)
    
    residual_allocation_line_ids = fields.One2many(
        "fms.shift.residual.allocation", "shift_id",
        string="Residual Allocations",
        help="Auto-calculated allocations from over/under")
    
    tank_summary_line_ids = fields.One2many(
        "fms.shift.tank.summary", "shift_id",
        string="Tank Reconciliation",
        compute="_compute_tank_summary", store=True)
    
    # ═══════════════════════════════════════════════════════════
    # VARIANCE & CLOSURE
    # ═══════════════════════════════════════════════════════════
    
    fc_cash_balance = fields.Monetary(
        compute="_compute_fc_cash",
        help="Forecourt cash account balance (MUST = 0)")
    
    total_attendant_variance = fields.Monetary(
        compute="_compute_attendant_variances",
        help="Sum of all attendant cash variances")
    
    manager_notes = fields.Text(
        string="Supervisor Notes",
        help="Explanation of variances and investigation")
    
    requires_correction = fields.Boolean(
        default=False,
        help="True if supervisor posted correction entry")
    
    # ═══════════════════════════════════════════════════════════
    # LOGS & POSTINGS (Written on close)
    # ═══════════════════════════════════════════════════════════
    
    meter_log_ids = fields.One2many(
        "fms.meter.log", "shift_id",
        string="Meter Logs",
        help="Immutable meter reading logs (written on close)")
    
    dip_log_ids = fields.One2many(
        "fms.dip.log", "shift_id",
        string="Dip Logs",
        help="Immutable dip reading logs (written on close)")
    
    journal_entry_id = fields.Many2one(
        "account.move", readonly=True,
        help="Primary journal entry (sales + variances)")
    
    correction_journal_ids = fields.Many2many(
        "account.move", "shift_journal_rel",
        string="Correction Entries",
        help="Additional correction journals (residuals, etc.)")
    
    # ═══════════════════════════════════════════════════════════
    # WORKFLOW ACTIONS
    # ═══════════════════════════════════════════════════════════
    
    @api.constrains("status")
    def _check_only_one_open_per_station(self):
        """Only one shift can be open per station at a time."""
        for shift in self:
            if shift.status in ("open", "closing"):
                conflict = self.search([
                    ("company_id", "=", shift.company_id.id),
                    ("status", "in", ("open", "closing")),
                    ("id", "!=", shift.id),
                ])
                if conflict:
                    raise ValidationError(
                        f"Shift {conflict[0].name} already open at {shift.company_id.name}. "
                        f"Close it first.")
    
    def action_open_shift(self):
        """Open shift: fetch previous closings, initialize entry lines."""
        self.ensure_one()
        
        if self.status not in ("draft", "disputed"):
            raise ValidationError(f"Cannot open shift with status {self.status}")
        
        # Fetch previous shift's closing readings
        prev_shift = self._get_previous_shift()
        if prev_shift:
            self._populate_entry_lines_from_previous(prev_shift)
        else:
            # First shift: initialize with current master data
            self._populate_entry_lines_from_master()
        
        self.status = "open"
        self.opened_at = fields.Datetime.now()
        self.opened_by_user_id = self.env.user.id
    
    def action_close_shift(self):
        """
        Close shift: validate hard gates, write logs, post journals.
        Atomic operation: all-or-nothing.
        """
        self.ensure_one()
        
        if self.status != "closing":
            raise ValidationError("Shift must be in 'closing' status to close.")
        
        # ────────── HARD GATE 1: FC CASH = 0 ──────────
        if abs(self.fc_cash_balance) > 0.01:
            raise ValidationError(
                f"FC Cash is ±KES {abs(self.fc_cash_balance):.2f}. "
                f"Supervisor must post adjustment before closing.")
        
        # ────────── HARD GATE 2: ALL ATTENDANTS CLEAR ──────────
        for cash_line in self.attendant_cash_line_ids:
            if abs(cash_line.balance) > 0.01:
                raise ValidationError(
                    f"Attendant {cash_line.attendant_id.name} not cleared: "
                    f"±KES {abs(cash_line.balance):.2f}")
        
        # ────────── HARD GATE 3: STOCK VARIANCE < MENISCUS ──────────
        for tank_line in self.tank_summary_line_ids:
            if abs(tank_line.variance_pct) > self.variance_tolerance_pct:
                raise ValidationError(
                    f"Tank {tank_line.tank_id.name}: variance {tank_line.variance_pct:.2f}% "
                    f"exceeds meniscus {self.variance_tolerance_pct:.2f}%")
        
        # All gates passed: proceed atomically
        with self.env.cr.savepoint():
            # Write immutable logs
            self._write_meter_logs()
            self._write_dip_logs()
            
            # Auto-calculate residuals if not yet done
            if not self.residual_allocation_line_ids:
                self._calculate_residuals()
            
            # Post journal entries
            self._post_sales_journal()
            self._post_residual_allocation_journal()
            self._post_cash_variance_journal()
            self._post_inventory_adjustments()
            
            # Close shift
            self.closed_at = fields.Datetime.now()
            self.closed_by_user_id = self.env.user.id
            self.status = "closed"
    
    @api.depends("shift_date")
    def _get_current_pricelist(self):
        """Fetch price list active on shift_date."""
        for shift in self:
            pricelist = self.env["product.pricelist"].search([
                ("company_id", "=", shift.company_id.id),
                ("active", "=", True),
                ("date_start", "<=", shift.shift_date),
                ("|",
                    ("date_end", "=", False),
                    ("date_end", ">=", shift.shift_date)
                ),
            ], limit=1, order="date_start desc")
            shift.price_list_id = pricelist.id if pricelist else False
    
    @api.depends("company_id")
    def _get_variance_tolerance(self):
        """Fetch site preferences."""
        for shift in self:
            prefs = self.env["fms.site.preferences"].search([
                ("company_id", "=", shift.company_id.id)
            ], limit=1)
            shift.variance_tolerance_pct = (
                prefs.acceptable_variance_pct 
                if prefs else 0.50)
    
    def _get_previous_shift(self):
        """Find the previous closed shift for this station."""
        return self.search([
            ("company_id", "=", self.company_id.id),
            ("status", "=", "closed"),
            ("shift_date", "<", self.shift_date),
        ], order="shift_date desc, shift_label desc", limit=1)
    
    def _populate_entry_lines_from_previous(self, prev_shift):
        """Fetch previous shift's closing readings, populate entry lines."""
        # For each tank: fetch previous closing dip
        for prev_dip_log in prev_shift.dip_log_ids:
            if prev_dip_log.reading_type == "close":
                self.env["fms.shift.dip.entry"].create({
                    "shift_id": self.id,
                    "tank_id": prev_dip_log.tank_id.id,
                    "opening_vol": prev_dip_log.closing_vol,  # Previous close = current open
                    "closing_vol": 0,  # To be filled in during shift
                })
        
        # For each pump nozzle: fetch previous closing meter
        for pump in self.company_id.fms_pump_ids.filtered("is_active"):
            for nozzle in pump.nozzle_ids:
                prev_meter_logs = prev_shift.meter_log_ids.filtered(
                    lambda m: m.nozzle_id == nozzle and m.reading_type == "close")
                
                opening_vol = prev_meter_logs[0].closing_elec_vol if prev_meter_logs else 0
                
                self.env["fms.shift.meter.entry"].create({
                    "shift_id": self.id,
                    "pump_id": pump.id,
                    "nozzle_id": nozzle.id,
                    "opening_elec_vol": opening_vol,
                    "closing_elec_vol": 0,  # To be filled
                    "opening_man_mech": opening_vol,  # Same
                    "closing_man_mech": 0,  # To be filled
                })
    
    def _populate_entry_lines_from_master(self):
        """Initialize entry lines from master pump/nozzle/tank data."""
        for pump in self.company_id.fms_pump_ids.filtered("is_active"):
            for nozzle in pump.nozzle_ids:
                self.env["fms.shift.meter.entry"].create({
                    "shift_id": self.id,
                    "pump_id": pump.id,
                    "nozzle_id": nozzle.id,
                    "opening_elec_vol": 0,
                    "closing_elec_vol": 0,
                })
        
        for tank in self.company_id.fms_tank_ids.filtered("is_active"):
            self.env["fms.shift.dip.entry"].create({
                "shift_id": self.id,
                "tank_id": tank.id,
                "opening_vol": 0,
                "closing_vol": 0,
            })
    
    @api.depends("meter_entry_line_ids", "meter_entry_line_ids.qty_sold", "meter_entry_line_ids.product_id")
    def _compute_product_sales(self):
        """Group meter readings by product."""
        for shift in self:
            products_dict = {}
            for meter_line in shift.meter_entry_line_ids:
                product_id = meter_line.nozzle_id.product_id.id
                if product_id not in products_dict:
                    products_dict[product_id] = {
                        "qty": 0,
                        "amount": 0,
                    }
                products_dict[product_id]["qty"] += meter_line.qty_sold
                products_dict[product_id]["amount"] += meter_line.amnt_sold
            
            # Delete old product lines
            shift.product_sales_line_ids.unlink()
            
            # Create new ones
            for product_id, data in products_dict.items():
                self.env["fms.shift.product.sales"].create({
                    "shift_id": shift.id,
                    "product_id": product_id,
                    "meter_volume": data["qty"],
                    "meter_amount": data["amount"],
                })
    
    @api.depends("dip_entry_line_ids", "dip_entry_line_ids.opening_vol", "dip_entry_line_ids.closing_vol")
    def _compute_tank_summary(self):
        """Compute tank reconciliation summary."""
        for shift in self:
            shift.tank_summary_line_ids.unlink()
            for dip_line in shift.dip_entry_line_ids:
                self.env["fms.shift.tank.summary"].create({
                    "shift_id": shift.id,
                    "tank_id": dip_line.tank_id.id,
                    "opening_vol": dip_line.opening_vol,
                    "closing_vol": dip_line.closing_vol,
                })
    
    @api.depends("attendant_cash_line_ids", "attendant_cash_line_ids.balance")
    def _compute_fc_cash(self):
        """FC Cash = sum of all attendant balances."""
        for shift in self:
            shift.fc_cash_balance = sum(
                line.balance for line in shift.attendant_cash_line_ids)
    
    @api.depends("attendant_cash_line_ids", "attendant_cash_line_ids.balance")
    def _compute_attendant_variances(self):
        """Sum of absolute variances."""
        for shift in self:
            shift.total_attendant_variance = sum(
                abs(line.balance) for line in shift.attendant_cash_line_ids)
    
    def _write_meter_logs(self):
        """Write meter entry data to immutable logs."""
        for meter_entry in self.meter_entry_line_ids:
            self.env["fms.meter.log"].create({
                "shift_id": self.id,
                "pump_id": meter_entry.pump_id.id,
                "nozzle_id": meter_entry.nozzle_id.id,
                "attendant_id": meter_entry.attendant_id.id,
                "opening_elec_vol": meter_entry.opening_elec_vol,
                "closing_elec_vol": meter_entry.closing_elec_vol,
                "qty_sold": meter_entry.qty_sold,
                "price": meter_entry.nozzle_id.product_id._get_price_at_date(self.shift_date),
            })
    
    def _write_dip_logs(self):
        """Write dip entry data to immutable logs."""
        for dip_entry in self.dip_entry_line_ids:
            self.env["fms.dip.log"].create({
                "shift_id": self.id,
                "tank_id": dip_entry.tank_id.id,
                "opening_volume": dip_entry.opening_vol,
                "closing_volume": dip_entry.closing_vol,
            })
    
    def _calculate_residuals(self):
        """Calculate and allocate residuals automatically."""
        # [Algorithm as described in section 7.1]
        pass
    
    def _post_sales_journal(self):
        """Post sales journal entry."""
        # [Implementation: DR COGS | CR Revenue]
        pass
    
    def _post_residual_allocation_journal(self):
        """Post residual reallocation entries."""
        # [Implementation: DR from_product COGS | CR to_product COGS]
        pass
    
    def _post_cash_variance_journal(self):
        """Post cash variances."""
        # [Implementation: DR FC Cash | CR Employee/Expense]
        pass
    
    def _post_inventory_adjustments(self):
        """Post stock.inventory adjustments for dips."""
        # [Implementation: Create stock.inventory count records]
        pass
```

### **Child Model: fms.shift.meter.entry**

```python
class FmsShiftMeterEntry(models.Model):
    _name = "fms.shift.meter.entry"
    _description = "Shift Meter Reading Entry"
    _order = "pump_id, nozzle_id"
    
    shift_id = fields.Many2one("fms.shift", ondelete="cascade", required=True)
    pump_id = fields.Many2one("fms.pump", required=True)
    nozzle_id = fields.Many2one("fms.pump.nozzle", required=True)
    attendant_id = fields.Many2one("hr.employee")
    
    # Opening (fetched, read-only)
    opening_elec_vol = fields.Float(readonly=True)
    opening_man_mech = fields.Float(readonly=True)
    
    # Closing (editable)
    closing_elec_vol = fields.Float(required=True)
    closing_man_mech = fields.Float(required=True)
    rtt_litres = fields.Float(default=0, help="Return to tank")
    
    # Computed
    qty_sold = fields.Float(compute="_compute_qty_sold", store=True)
    amnt_sold = fields.Monetary(compute="_compute_amnt_sold", store=True)
    
    @api.depends("opening_elec_vol", "closing_elec_vol", "rtt_litres")
    def _compute_qty_sold(self):
        for line in self:
            line.qty_sold = (line.closing_elec_vol - line.opening_elec_vol) - line.rtt_litres
    
    @api.depends("qty_sold", "nozzle_id")
    def _compute_amnt_sold(self):
        for line in self:
            if line.shift_id:
                rate = line.shift_id._get_rate_for_product(line.nozzle_id.product_id)
                line.amnt_sold = line.qty_sold * rate if rate else 0
            else:
                line.amnt_sold = 0
```

### **Child Model: fms.shift.dip.entry**

```python
class FmsShiftDipEntry(models.Model):
    _name = "fms.shift.dip.entry"
    _description = "Shift Dip Reading Entry"
    
    shift_id = fields.Many2one("fms.shift", ondelete="cascade", required=True)
    tank_id = fields.Many2one("stock.location", required=True,
        domain=[("fms_is_fuel_tank", "=", True)])
    
    opening_vol = fields.Float(readonly=True, help="From previous shift closing")
    closing_vol = fields.Float(required=True, help="Physical dip reading this shift end")
    water_level_mm = fields.Float()
    temperature_c = fields.Float()
    
    variance_volume = fields.Float(compute="_compute_variance")
    variance_pct = fields.Float(compute="_compute_variance")
    
    @api.depends("opening_vol", "closing_vol")
    def _compute_variance(self):
        for line in self:
            line.variance_volume = line.closing_vol - line.opening_vol
            if line.closing_vol:
                line.variance_pct = (line.variance_volume / line.closing_vol) * 100
```

### **Child Model: fms.shift.attendant.cash**

```python
class FmsShiftAttendantCash(models.Model):
    _name = "fms.shift.attendant.cash"
    _description = "Attendant Cash Reconciliation"
    
    shift_id = fields.Many2one("fms.shift", ondelete="cascade")
    attendant_id = fields.Many2one("hr.employee", required=True)
    
    # Incoming
    sales_amount = fields.Monetary(compute="_compute_sales")
    receipts_amount = fields.Monetary()
    total_in = fields.Monetary(compute="_compute_total_in")
    
    # Outgoing
    cash_dropped = fields.Monetary(required=True)
    invoices_ar = fields.Monetary(compute="_compute_ar")
    card_transferred = fields.Monetary(compute="_compute_card")
    mpesa_transferred = fields.Monetary()
    expenses_paid = fields.Monetary()
    total_out = fields.Monetary(compute="_compute_total_out")
    
    # Balance
    balance = fields.Monetary(compute="_compute_balance")
    
    @api.depends("shift_id", "attendant_id")
    def _compute_sales(self):
        for line in self:
            if line.shift_id and line.attendant_id:
                pos_orders = self.env["pos.order"].search([
                    ("session_id", "in", line.shift_id.pos_session_ids.ids),
                    ("user_id", "=", line.attendant_id.id),
                ])
                line.sales_amount = sum(o.amount_total for o in pos_orders)
    
    @api.depends("sales_amount", "receipts_amount")
    def _compute_total_in(self):
        for line in self:
            line.total_in = line.sales_amount + line.receipts_amount
    
    @api.depends("shift_id", "attendant_id")
    def _compute_ar(self):
        for line in self:
            if line.shift_id and line.attendant_id:
                invoices = self.env["account.move"].search([
                    ("move_type", "=", "out_invoice"),
                    ("invoice_date", "=", line.shift_id.shift_date),
                    ("user_id", "=", line.attendant_id.id),  # Or custom field
                ])
                line.invoices_ar = sum(i.amount_residual for i in invoices)
    
    @api.depends("cash_dropped", "invoices_ar", "card_transferred", "mpesa_transferred", "expenses_paid")
    def _compute_total_out(self):
        for line in self:
            line.total_out = (line.cash_dropped + line.invoices_ar + 
                              line.card_transferred + line.mpesa_transferred + 
                              line.expenses_paid)
    
    @api.depends("total_in", "total_out")
    def _compute_balance(self):
        for line in self:
            line.balance = line.total_in - line.total_out
```

### **Computed Model: fms.shift.product.sales**

```python
class FmsShiftProductSales(models.Model):
    _name = "fms.shift.product.sales"
    _description = "Product Sales Reconciliation"
    
    shift_id = fields.Many2one("fms.shift", ondelete="cascade")
    product_id = fields.Many2one("product.product")
    
    meter_volume = fields.Float()
    meter_amount = fields.Monetary()
    
    invoiced_volume = fields.Float(compute="_compute_invoiced")
    card_equiv_volume = fields.Float(compute="_compute_card")
    accounted_volume = fields.Float(compute="_compute_accounted")
    
    residual_volume = fields.Float(compute="_compute_residual")
    residual_amount = fields.Monetary(compute="_compute_residual")
```

### **Allocation Model: fms.shift.residual.allocation**

```python
class FmsShiftResidualAllocation(models.Model):
    _name = "fms.shift.residual.allocation"
    _description = "Residual Allocation"
    
    shift_id = fields.Many2one("fms.shift", ondelete="cascade")
    
    from_product_id = fields.Many2one("product.product", string="Over-reported")
    to_product_id = fields.Many2one("product.product", string="Under-reported")
    
    quantity = fields.Float()
    amount = fields.Monetary()
    reason = fields.Text()
```

### **Immutable Logs**

```python
class FmsMeterLog(models.Model):
    _name = "fms.meter.log"
    _description = "Meter Reading Log (Immutable)"
    
    shift_id = fields.Many2one("fms.shift", ondelete="cascade")
    pump_id = fields.Many2one("fms.pump")
    nozzle_id = fields.Many2one("fms.pump.nozzle")
    attendant_id = fields.Many2one("hr.employee")
    
    opening_elec_vol = fields.Float()
    closing_elec_vol = fields.Float()
    qty_sold = fields.Float()
    price = fields.Monetary()
    
    created_on = fields.Datetime(default=fields.Datetime.now, readonly=True)
    
    def write(self, vals):
        raise ValidationError("Meter logs are immutable.")
    def unlink(self):
        raise ValidationError("Meter logs cannot be deleted.")


class FmsDipLog(models.Model):
    _name = "fms.dip.log"
    _description = "Dip Reading Log (Immutable)"
    
    shift_id = fields.Many2one("fms.shift", ondelete="cascade")
    tank_id = fields.Many2one("stock.location")
    
    opening_volume = fields.Float()
    closing_volume = fields.Float()
    
    created_on = fields.Datetime(default=fields.Datetime.now, readonly=True)
    
    def write(self, vals):
        raise ValidationError("Dip logs are immutable.")
    def unlink(self):
        raise ValidationError("Dip logs cannot be deleted.")
```

---

# 9. Security & Access Control

## 9.1 Groups & Permissions

### Group 1: **fuel_station_attendant**
**Can:**
- Create meter entries (only during open shift)
- Create dip entries (only during open shift)
- View own POS orders
- View own attendant cash line

**Cannot:**
- Close shift
- Edit previous attendants' data
- Delete anything
- View GL/accounting

**Assigned to:** Fuel station attendants

### Group 2: **fuel_station_supervisor**
**Can:**
- Everything attendants can do
- Edit all meter/dip/cash entries (before close)
- Review reconciliation
- Post journal entries (corrections)
- Close shift (if gates pass)
- View GL/accounting (reconciliation only)

**Cannot:**
- Delete closed shifts
- Edit immutable logs

**Assigned to:** Shift supervisors, station managers

### Group 3: **fuel_station_accountant**
**Can:**
- View all shifts (closed and open)
- View reports and audit trails
- View GL/accounting
- Manage site preferences

**Cannot:**
- Close shifts
- Post corrections (supervisor does)

**Assigned to:** Corporate accountants

---

## 9.2 Row-Level Security (RLS)

```python
# In _get_default_search_filter() on FmsShift:
def _get_default_search_filter(self):
    """Restrict users to their assigned companies."""
    companies = self.env.user.company_ids
    if not companies:
        companies = self.env.company
    return [("company_id", "in", companies.ids)]
```

---

# 10. UI/UX Design Framework

## 10.1 Design Principles for Fuel Station Operations

### Principle 1: **Minimize Cognitive Load**
Fuel station attendants are busy; they don't have time for complex workflows.
- **1 screen = 1 task**
- **Reading list should show status at a glance**
- **Forms should tab-through friendly** (keyboard navigation)

### Principle 2: **Reduce Data Entry**
Pre-fill everything possible from master data and previous shift.
- Opening readings auto-fetched (no re-entry)
- Pump list auto-sorted by nozzle order
- Attendant dropdown pre-filled if only one assigned

### Principle 3: **Make Errors Obvious**
Fuel reconciliation depends on accuracy; highlight mismatches.
- Variance percentages colored: green (OK), yellow (warning), red (fail)
- Hard gate failures shown prominently
- Impossible values flagged on entry (e.g., closing < opening meter)

### Principle 4: **Mobile First**
Station staff use tablets/phones, not desktops.
- Responsive forms (stack on narrow screens)
- Touch-friendly buttons (min 44px)
- Minimal scrolling (fit entry form on one screen if possible)

### Principle 5: **Fast Shift Close**
A 12-hour shift must close in <10 minutes with no errors.
- All data entry on one form (no jumping between screens)
- Automatic calculations (no manual formulas)
- One-click close (if gates pass)

---

## 10.2 Form Layout & Navigation

### Screen 1: List of Shifts (Dashboard)

**URL:** `/web#action=fms.shift`

```
┌──────────────────────────────────────────────────────┐
│ Shift Sheets  [New] [Filter] [Group By] [Chart]    │
├──────────────────────────────────────────────────────┤
│                                                       │
│ Today's Shifts (Shell Maanzoni)                     │
│ ┌───────────────────────────────────────────────┐  │
│ │ Shift   │ Time    │ Status  │ Supervisor   │ Var│  │
│ ├───────────────────────────────────────────────┤  │
│ │SHT/2026 │ 1 Day   │ CLOSED  │ Supervisor   │ ✓ │  │ ← Previous
│ │/07/0420 │ 06–18   │ (7 hrs) │ Name         │   │  │
│ │         │         │         │              │   │  │
│ │SHT/2026 │ 2 Evening
│ │/07/0421 │ 14–22   │ OPEN    │ Supervisor   │ ⚠️ │  │ ← Current
│ │         │         │ (4 hrs) │ Name         │   │  │
│ │         │         │         │              │   │  │
│ │SHT/2026 │ 3 Night │ DRAFT   │ [None]       │ — │  │ ← Tomorrow
│ │/07/0422 │ 22–06   │ (Not yet)              │   │  │
│ └───────────────────────────────────────────────┘  │
│                                                       │
│ Quick Actions:                                      │
│ [Open Today's Shift]  [View Reports]  [Settings]   │
└──────────────────────────────────────────────────────┘
```

**Key Features:**
- Status badges (DRAFT → OPEN → CLOSING → CLOSED)
- Variance indicator (✓ = OK, ⚠️ = warning, ✗ = fail)
- Time spent (for supervisors tracking shift duration)
- Click to edit/close

---

### Screen 2: Shift Form (Unified Data Entry)

**Layout:** Single scrollable form with collapsible sections

```
┌──────────────────────────────────────────────────────┐
│ Shift / SHT/2026/07/0421                    [Save]  │
├──────────────────────────────────────────────────────┤
│                                                       │
│ 🔴 DRAFT  |  Time: 06:00–18:00  |  Status: OPEN   │
│                                                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  HEADER                           [Collapse ▼]     │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                       │
│ Station: Shell Maanzoni        Price List:          │
│                                EPRA Cap (27 Jul)    │
│ Shift: 1 – Day (06:00–18:00)  Variance Tolerance:  │
│                                ±0.50%               │
│ Supervisor: Supervisor Name     Status: OPEN       │
│                                Opened: 06:15       │
│                                                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  TANK DIPS (4 tanks)              [Collapse ▼]     │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                       │
│ Read the four blue columns below to the right:     │
│ Opening | Received | Closing volume | Tank sale    │
│                                                       │
│ ┌──────────────────────────────────────────────┐  │
│ │ PRODUCT  │ Capture | DIP HEIGHT | TEMP | O'NG   │  │
│ │          │         │   (mm)     | (°C) | dip    │  │
│ │          │         │            |      | (auto) │  │
│ ├──────────────────────────────────────────────┤  │
│ │ T1 –     │ Length  │ [1188]  ◀─  [12]  │ 5,000 │  │
│ │ V-Power  │ Volume  │ [5000]  ──▶        │  L    │  │
│ │ 1300 GAL │         │                    │       │  │
│ ├──────────────────────────────────────────────┤  │
│ │ T2 –     │ Length  │ [1655]      [18]   │ 8,200 │  │
│ │ Unleaded │ Volume  │ [8200]              │  L    │  │
│ │ 2100 GAL │         │                    │       │  │
│ └──────────────────────────────────────────────┘  │
│ [+ Add tank line] [Load Sample Data] [All Entered] │
│                                                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  PUMP METER READINGS (8 nozzles)   [Collapse ▼]   │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                       │
│ Closing – Opening = Qty sold, then Qty × Rate     │
│ Opening totalizers carry over from last shift's    │
│ closing figures, so you only keep the closing      │
│ figures. RTT is fuel pumped back into the tank,    │
│ it never counts as a sale.                         │
│                                                       │
│ ┌──────────────────────────────────────────────────┐ │
│ │ ISLAND | NOZZLE | PRODUCT | OPENING | CLOSING  │ │
│ │        |         |         | Elec   | Elec     │ │
│ ├──────────────────────────────────────────────────┤ │
│ │ 1 UX5  │ A      │ V-Power │ 450271 │ [450601] │ │
│ │        │ B      │ Unleaded│ 462357 │ [462687] │ │
│ │                                                   │ │
│ │ 2 UX6  │ A      │ Diesel  │ 141104 │ [141617] │ │
│ │                                                   │ │
│ │ 3 DX5  │ A      │ Diesel  │ 141104 │ [142617] │ │
│ │                                                   │ │
│ │ 4 DX6  │ A      │ Diesel  │ 886114 │ [887498] │ │
│ │                                                   │ │
│ │ 5 VP1  │ A      │ V-Power │ 9853985│[9854151]│ │
│ │                                                   │ │
│ │ 6 VP2  │ A      │ V-Power │ 78853138│[78860000]│ │
│ │                                                   │ │
│ │ 7 VP3  │ A      │ V-Power │ 20480661│[20481000]│ │
│ │                                                   │ │
│ │ 8 SP1  │ A      │ Diesel  │ [Skip if under maint]  │
│ └──────────────────────────────────────────────────┘ │
│ [+ Add nozzle line] [Load Sample Data]              │
│                                                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  ATTENDANT CASH RECONCILIATION (4 people) [Collapse]
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                       │
│ One row per attendant: Sales (auto) vs. Cash Drops  │
│                                                       │
│ Attendant      │ Sales  │ Dropped │ AR Created │ Bal │
│ A. Njeri       │694.56  │ [695.00]│     0      │-0.44│
│ S. Olieno      │3,151.33│ [3,150] │     0      │+1.33│
│ P. Kimani      │4,289.83│ [4,285] │     0      │+4.83│
│ M. Wambuah     │7,900.00│ [7,900] │     0      │0.00 │
│                                                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│  RECONCILIATION RESULTS (Read-Only)      [Collapse] │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                       │
│ FC Cash Balance: +6.52 KES                          │
│ Status: ✗ NOT ZERO — shift cannot close             │
│                                                       │
│ Supervisor must post correction:                    │
│ [POST ADJUSTMENT ENTRY]                            │
│                                                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│ ACTIONS                                             │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                       │
│ [SAVE]  [VERIFY READY]  [CLOSE SHIFT]  [DISPUTE]  │
│                                                       │
└──────────────────────────────────────────────────────┘
```

**UX Details:**
- **Collapsible sections** — reduce cognitive overload, show only what's needed
- **Color-coded variance** — green (✓ OK), yellow (⚠️ warning), red (✗ fail)
- **Auto-populated opening values** — gray, read-only, fetched from prev shift
- **Tab-through friendly** — pressing Tab jumps to next editable field
- **Smart defaults** — pump/nozzle list auto-sorted by nozzle_order
- **Inline validations** — real-time errors (e.g., "Closing < Opening")

---

## 10.3 Mobile Responsiveness

**Tablet (iPad, 768px):**
- 1-column layout (sections stack vertically)
- Larger touch targets (buttons 56px min)
- Swipe to scroll, not pinch-zoom

**Phone (480px):**
- Single nozzle per screen (less overwhelming)
- Meter readings in modal popup (not inline)
- Tab navigation at bottom (fixed position)

---

## 10.4 Reports & Dashboards

### Report 1: Shift Reconciliation Report (PDF)

Printed at shift close for archive + distribution to accountant.

```
┌────────────────────────────────────────────────────┐
│                 Shell Maanzoni                      │
│                Shift Reconciliation                │
│                  27 July 2026                      │
│                 Shift 1 (06:00–18:00)              │
├────────────────────────────────────────────────────┤
│                                                     │
│ ATTENDANTS & CASH RECONCILIATION                   │
│ ┌────────────────────────────────────────────────┐ │
│ │ Attendant   │ Sales  │ Drops │ AR   │ Balance  │ │
│ │ A. Njeri    │694.56  │695.00 │  0.0 │ -0.44   │ │
│ │ S. Olieno   │3,151.33│3,150  │  0.0 │ +1.33   │ │
│ │ P. Kimani   │4,289.83│4,285  │  0.0 │ +4.83   │ │
│ │ M. Wambuah  │7,900.00│7,900  │  0.0 │ 0.00    │ │
│ │ TOTAL       │16,035.72│15,930│  0.0 │ +5.72   │ │
│ └────────────────────────────────────────────────┘ │
│                                                     │
│ FC CASH ACCOUNT RECONCILIATION                     │
│ Opening FC Cash .......................... 0.00    │
│ + Sales (all products) ................ 16,035.72 │
│ + Receipts/Float .......................    0.00  │
│ - Cash dropped to safe ................ 15,930.00 │
│ - Expenses (petty cash) ..................   0.00 │
│ - AR created (credit sales) ..............   0.00 │
│ - Card/Mpesa transfers ...................   0.00 │
│ = Closing FC Cash .......................+105.72  │
│                                                     │
│ VARIANCE CORRECTION ENTRY POSTED                  │
│ DR FC Cash 105.72                                  │
│ CR Miscellaneous Income 105.72                     │
│ After correction: FC Cash = 0.00 ✓                │
│                                                     │
│ STOCK RECONCILIATION (TANKS)                       │
│ ┌────────────────────────────────────────────────┐ │
│ │ Tank │ Opening │ Purchases │ Sales │ Book │ Var│ │
│ │ T1   │ 5,000L  │ 2,000L    │1,520L │5,480 │0.0%│ │
│ │ T2   │ 8,200L  │ 1,500L    │1,135L │8,565 │0.0%│ │
│ │ T3   │ 12,100L │ 1,200L    │1,550L │11,750│0.0%│ │
│ │ T4   │ 11,250L │    0L     │  350L │10,900│0.0%│ │
│ │ TOTAL│ 36,550L │ 4,700L    │4,555L │36,695│0.0%│ │
│ └────────────────────────────────────────────────┘ │
│ Variance Status: All tanks within meniscus ✓      │
│                                                     │
│ METER RECONCILIATION (PRODUCTS)                    │
│ ┌────────────────────────────────────────────────┐ │
│ │ Product     │ Pumps Sold │ Invoiced │ Residual │ │
│ │ V-Power     │ 330.41L    │ 100.00L  │ -64.59L  │ │
│ │ Unleaded    │ 1,102.43L  │  50.00L  │ +52.43L  │ │
│ │ Diesel Extra│ 1,513.18L  │ 400.00L  │+113.18L  │ │
│ │ LPG         │    0.00L   │   0.00L  │ -50.00L  │ │
│ └────────────────────────────────────────────────┘ │
│                                                     │
│ RESIDUAL ALLOCATION POSTED                         │
│ V-Power -64.59L → UX +52.43L  (63.8L @ avg rate) │
│ LPG -50.00L → Diesel +113.18L (50.0L @ avg rate) │
│ Journal entries posted: JE001, JE002, JE003       │
│                                                     │
│ SHIFT SUMMARY                                      │
│ Opened: 06:15 by Opening Attendant                │
│ Closed: 18:15 by Supervisor Name                  │
│ Total duration: 12 hours                           │
│ Attendants: 4                                      │
│ Transactions: 127 POS orders + 0 credit invoices  │
│ Total sales: 1,445,986.95 KES                     │
│ Profit margin: [calculated based on COGS]         │
│                                                     │
│ Approved by: Supervisor Name        Date: 27 Jul  │
│ Accountant review pending...                       │
└────────────────────────────────────────────────────┘
```

---

# 11. Development Runbook

## 11.1 Setup & Environment

**Prerequisites:**
- Odoo 18 Community Edition installed
- PostgreSQL 12+
- Python 3.10+
- Git

**Steps:**
```bash
# 1. Clone repo (or create scaffold)
odoo-scaffold shell_maanzoni_fms --addons-path ~/addons

# 2. Create module structure
cd ~/addons/shell_maanzoni_fms
touch __init__.py __manifest__.py

# 3. Create folders
mkdir -p models views security reports data

# 4. Copy code files (from this spec)
# (Place model files in models/, views in views/, etc.)

# 5. Restart Odoo server
# Settings → Apps & Modules → Update Modules List
# Search "shell_maanzoni" → Install

# 6. Create test company
# Settings → Companies → Create "Shell Maanzoni"

# 7. Create master data
# Settings → Locations/Warehouses → Create tanks (stock.locations)
# Settings → Products → Create fuel products
# Pumps & Nozzles → Create via FMS module UI
```

---

## 11.2 Testing Strategy

### Unit Tests (Model Logic)

```python
# In tests/ folder: test_residual_allocation.py

class TestResidualAllocation(TransactionCase):
    
    def test_diesel_over_reported_ux_under_reported(self):
        """Diesel -100L over, UX +240L under → allocate 104L"""
        # Create shift with specific meter/cash readings
        # Call _calculate_residuals()
        # Assert allocations are correct
        pass
    
    def test_fc_cash_cannot_close_if_not_zero(self):
        """Shift refuses to close if FC Cash ≠ 0"""
        # Create shift with FC Cash +50 KES
        # Call action_close_shift()
        # Assert ValidationError is raised
        pass
    
    def test_stock_variance_hard_gate(self):
        """Shift refuses if variance > meniscus"""
        # Create shift with 15% variance
        # Call action_close_shift()
        # Assert ValidationError
        pass
```

### Integration Tests (Workflow)

```python
# test_shift_close_workflow.py

class TestShiftCloseWorkflow(TransactionCase):
    
    def test_full_shift_close(self):
        """Full workflow: open → enter data → close"""
        # 1. Create shift, assign supervisor
        # 2. Open shift (action_open_shift)
        # 3. Add meter readings (all nozzles)
        # 4. Add dip readings (all tanks)
        # 5. Add attendant cash (per person)
        # 6. Verify: FC Cash = 0, variances OK
        # 7. Close shift (action_close_shift)
        # 8. Assert: logs written, journals posted, status = closed
        pass
    
    def test_previous_shift_opening_fetch(self):
        """Opening readings auto-fetch from previous shift"""
        # 1. Close shift 1
        # 2. Create shift 2
        # 3. Assert meter_entry opening values match shift 1 closing
        pass
```

### UAT Test Scenarios

**Scenario 1: Normal Shift (No Variances)**
- Input: All meters match, all dips match, all cash matches
- Expected: Shift closes immediately, no corrections needed

**Scenario 2: Lumped Non-Fuel Sales**
- Input: MPesa reported as Diesel but includes carwash
- Expected: System detects residual, auto-allocates, journals posted

**Scenario 3: Cash Overage**
- Input: FC Cash = +200 KES
- Expected: Hard gate blocks close, supervisor posts correction

**Scenario 4: Stock Variance**
- Input: Tank 1 variance = 10% (exceeds meniscus)
- Expected: Hard gate blocks close, supervisor investigates

---

# 12. Testing Strategy

## Test Coverage (Minimum 80%)

- **Models:** 100% (critical business logic)
- **Computations:** 100% (residuals, variances, reconciliation)
- **Workflows:** 90% (open, close, corrections)
- **Security:** 95% (access control, row-level security)
- **UI:** 50% (functional, not visual regression)

---

# 13. Deployment & Operations

## 13.1 Go-Live Checklist

- [ ] Data migration from ERPNext complete
- [ ] Master data created (pumps, nozzles, tanks, employees)
- [ ] Site preferences configured (variance %, accounts)
- [ ] User training complete (attendants, supervisors, accountants)
- [ ] UAT passed on test database
- [ ] Production database backup created
- [ ] Module installed on production Odoo
- [ ] First shift opened and tested
- [ ] Accounting reconciliation verified
- [ ] Support plan in place (helpdesk, escalation)

---

## 13.2 Runbook: Daily Operations

### Morning (Supervisor Opening Shift)

1. Open Odoo, navigate to Shift Sheets
2. Click [Open Today's Shift]
3. Verify pump/nozzle/tank list auto-populated
4. Assign attendants to pumps (if not auto-assigned)
5. Review opening readings (auto-fetched from prev shift)
6. Click [Confirm Opening] when ready
7. Hand over to attendants

### Evening (Supervisor Closing Shift)

1. At end of shift, call in all attendants
2. Attendant 1: Read all meters assigned to them, enter closing values
3. Attendant 1: Read all dips, enter closing values
4. Attendant 1: Count actual cash, enter in attendant_cash_line
5. Supervisor: Review reconciliation results
6. If any variance, supervisor investigates and posts correction entry
7. Once all hard gates pass, click [CLOSE SHIFT]
8. System writes logs, posts journals, shift is sealed

### Accountant (Next Day)

1. Review closed shifts from yesterday
2. Verify GL entries match shift reports
3. Flag any unusual variances for supervisor follow-up
4. Prepare daily reconciliation report

---

# 14. Phase 2 Roadmap (Future)

**Not in scope for Phase 1, but planned for Phase 2:**

1. **PTS-2 Pump Integration**
   - Real-time meter readings from pump controllers
   - Auto-populate closing meter values
   - Alert if pump offline

2. **Tank Calibration Charts**
   - Replace manual "dip → volume" with height-based calculation
   - Temperature correction for fuel density
   - Multi-point calibration per tank

3. **Amendments & Spot Checks**
   - Reopen closed shift if critical error found
   - Audit trail: who changed what, when, why
   - Approval workflow for amendments

4. **Drive-Off & Theft Tracking**
   - Record suspicious variance patterns
   - Trend analysis (is this tank consistently short?)
   - Alerts for investigation

5. **Multi-Branch Dashboard**
   - Roll-up view: all stations' shifts for the day
   - Variance heatmap by station
   - Quick-scan KPI dashboard

6. **Fleet Cards & Corporate Accounts**
   - Track fuel by vehicle/corporate account
   - Invoice generation per account
   - Pricing tiers (volume discounts)

7. **Delivery Reconciliation**
   - Match supplier PO → delivery receipt → tank dip
   - Variance analysis (did we get short?)
   - GL posting for fuel purchases

8. **Offline Resilience**
   - Attendants enter data on tablet when offline
   - Sync to server when connection restored
   - Conflict resolution if simultaneous edits

---

# Appendix A: Glossary

- **FC Cash:** Forecourt Cash account; physical cash in the till
- **Meniscus:** Maximum acceptable stock variance % (e.g., 0.5%)
- **Residual:** Unaccounted volume/amount (over- or under-reported)
- **Dip:** Physical stock measurement using calibrated stick
- **Meter:** Pump electronic totalizer (cumulative liters dispensed)
- **RTT:** Return to tank; fuel pumped back (for testing)
- **AR:** Accounts Receivable; credit sales (customer owes money)
- **COGS:** Cost of Goods Sold; fuel expense in GL
- **Hard Gate:** Non-negotiable constraint (shift won't close if violated)
- **Immutable Log:** Data that cannot be edited after creation
- **RLS:** Row-Level Security; restrict users to specific companies/stations

---

# Appendix B: Odoo Core vs. Custom Comparison

| What | Where | Why Custom |
|---|---|---|
| Shift orchestration | `fms.shift` (custom) | No fuel-specific shift module in Odoo |
| Meter readings | `fms.meter.log` (custom) | Fuel-specific, not in core |
| Dip readings | `fms.dip.log` (custom) | Fuel-specific, not in core |
| Residual allocation | `fms.shift.residual.allocation` (custom) | Algorithm specific to fuel business |
| POS sales linking | `pos.order` + `pos.session` (Odoo core) | Odoo POS already captures sales perfectly |
| GL posting | `account.move` (Odoo core) | Standard journaling, no customization |
| Stock tracking | `stock.move` + `stock.quant` (Odoo core) | Odoo stock ledger is industry standard |
| Employee tracking | `hr.employee` (Odoo core) | Standard HR, no customization |
| Configuration | `fms.site.preferences` (custom) | Fuel-specific params (variance %, accounts) |

---

# Appendix C: Security Considerations

- **SQL Injection:** No raw SQL used; all queries use ORM
- **CSRF:** Odoo's session tokens protect against CSRF
- **Access Control:** Role-based groups (attendant, supervisor, accountant)
- **Audit Trail:** All edits tracked via Odoo's `tracking` module
- **Immutability:** Logs cannot be edited via write() override
- **Encryption:** Odoo's password hashing for user accounts
- **Compliance:** Immutable logs meet EPRA audit requirements

---

# Appendix D: Performance Considerations

- **Database Indexes:** Add on `shift_date`, `company_id`, `status`
- **Report Queries:** Use computed fields (`@api.depends`) to avoid N+1
- **Archival:** After 90 days, move closed shifts to archive table
- **Caching:** Cache price lists per shift_date
- **Batch Operations:** When posting journals, batch GL lines to <1000 per entry

---

**End of Specification Document**

---

This is a **production-ready specification**. Use this to:

1. **Brief the development team** on requirements
2. **Design database schema** (model definitions are complete)
3. **Build forms & views** (UI layouts provided)
4. **Write tests** (test scenarios included)
5. **Document business logic** (algorithms explained in depth)
6. **Plan Phase 2** (roadmap provided)

---

**Questions? Next steps:**

1. **Review this spec** with your team
2. **Validate Odoo assumptions** (POS integration, stock module, GL)
3. **Start Phase 1 code** (model files + views)
4. **Conduct UAT** with Shell Maanzoni staff
5. **Deploy to production** (week 6)

**Ready to build?**
