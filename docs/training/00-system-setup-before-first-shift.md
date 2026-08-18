# System Setup Guide — Before the First Shift
**Audience:** System administrator, station manager, and accountant working together  
**When to use:** Once only — during initial station setup. Never repeat unless re-installing from scratch.  
**Estimated time:** 3–5 hours depending on number of pumps, products, and accounts  
**Role required:** Odoo Administrator + `fms.group_fms_supervisor` + `account.group_account_manager`

---

## Overview

This guide walks through every configuration step required before opening the very first shift. Steps must be completed in the order listed — later steps depend on earlier ones.

```
SETUP SEQUENCE
─────────────────────────────────────────────────────────────────
Step 1   Company & Currency
Step 2   Chart of Accounts (fuel-specific accounts)
Step 3   FMS Journals
Step 4   Fuel Products (with GL accounts wired)
Step 5   Fuel Tank Locations
Step 6   Pumps and Nozzles (with initial meter readings)
Step 7   Employees and Attendants
Step 8   Price Periods (current pump price per product)
Step 9   Site Preferences (ties everything together)
Step 10  Security Groups and Users
Step 11  Verification Checklist
─────────────────────────────────────────────────────────────────
```

**Checkpoint after each step:** The system will not allow you to open a shift until every step is complete. If you open the first shift and it fails with a "GL Config" error, something in Steps 1–9 was missed.

---

## Step 1 — Company and Currency

### What and Why

Odoo scopes all data to a company. FMS is fully multi-company aware — every shift, every nozzle, every attendant cash line belongs to one company. If you run multiple stations, each is its own company in Odoo.

Currency must be KES (Kenyan Shilling). All pump prices, meter totalisers, and GL entries will be in KES.

### Where

**Settings → Companies → [Your Company Name]**

### What to Set

| Field | Value | Notes |
|---|---|---|
| Company Name | Full legal name (e.g. Anika Global Limited) | Appears on all printed reports |
| Country | Kenya | Activates KES currency |
| Currency | KES — Kenyan Shilling | Set this before creating any accounts |
| Street / City | Station physical address | Appears on shift reports and invoices |
| Phone | Station main line | |
| Email | Station accounting email | |
| VAT / KRA PIN | Company KRA PIN | Required for tax compliance |

Click **Save**.

### Verify

- Top-right of Odoo shows "KES" next to the company name.
- If you see USD or EUR, the currency was not set — fix before proceeding.

---

## Step 2 — Chart of Accounts

### What and Why

The Chart of Accounts (CoA) is the complete list of GL accounts the station will use. Every shift sales entry, every purchase bill, and every payment posts to specific accounts in this chart.

For a fuel station, you need accounts in six categories:
1. **Cash and bank** — where money sits
2. **Receivables** — what customers owe
3. **Clearing** — staging between pump and bank
4. **Revenue** — what was sold (one account per fuel product recommended)
5. **Cost of Sales (COGS)** — what the fuel cost (one per product)
6. **Operating Expenses** — electricity, salaries, repairs

### Where

**Accounting → Configuration → Chart of Accounts**

In Kenya, Odoo installs a generic CoA. You need to either:
- **Use the generic CoA** and map your account codes to the existing accounts, OR
- **Import a custom CoA** via Settings → Technical → Import (CSV format)

The seed script (`scripts/seed_e2e.py`) creates the full Anika Global Limited chart. For a production station, adapt it to your actual account codes.

### Minimum Required Accounts for FMS

These accounts MUST exist before FMS can be configured. Create them if they don't exist in your CoA:

| Account Code | Account Name | Type | Required For |
|---|---|---|---|
| 100000 | Bank Account | `asset_cash` | Banking cash |
| 101000 | Cash in Safe | `asset_cash` | Clearing to safe |
| 102001 | Card Receivable | `asset_current` | Card clearing |
| 102003 | MPesa Account | `asset_cash` | MPesa clearing |
| 110000 | Accounts Receivable | `asset_receivable` | Credit customers |
| 191600 | FMS Cash Clearing | `asset_receivable` | **Required by FMS** — staging account |
| 210000 | Accounts Payable | `liability_payable` | Supplier bills |
| 400000 | Diesel Revenue | `income` | Diesel shift sales |
| 400100 | Unleaded Revenue | `income` | Unleaded shift sales |
| 400200 | V-Power Revenue | `income` | V-Power shift sales |
| 400300 | LPG Revenue | `income` | LPG shift sales |
| 400400 | Other Fuel Revenue | `income` | Kerosene / other |
| 591000 | Diesel COGS | `expense_direct_cost` | Residual allocation |
| 591100 | Unleaded COGS | `expense_direct_cost` | Residual allocation |
| 591200 | Non-Fuel COGS | `expense_direct_cost` | Carwash/LPG residuals |
| 624000 | Bad Debts | `expense` | AR write-offs |
| 700002 | Reconciliation Discrepancies | `expense` | Unresolved shift variances |

### How to Create an Account

**Accounting → Configuration → Chart of Accounts → New**

| Field | What to set |
|---|---|
| Code | Account number (e.g. 191600) |
| Name | Account name (e.g. FMS Cash Clearing) |
| Type | Select from dropdown (see table above) |
| Default Taxes | Leave blank for most accounts |
| Deprecated | Leave unchecked |

Click **Save**.

> **Critical:** The FMS Cash Clearing account (191600) must have Type = `asset_receivable`. This is because Odoo requires reconcilable accounts on the debit side of shift entries. Any other type will cause the shift close GL posting to fail.

### Verify

- Accounting → Configuration → Chart of Accounts → search "191600" — must exist with type `asset_receivable`.
- Search "400000" — must exist with type `income`.
- Search "591000" — must exist with type `expense_direct_cost`.

---

## Step 3 — FMS Journals

### What and Why

A journal in Odoo is a named grouping for GL entries. All FMS shift sales entries must post to a dedicated journal so accountants can filter and review them separately from other transactions.

You need one new journal: **FMS Shifts**.

### Where

**Accounting → Configuration → Journals → New**

### What to Create

**Journal 1: FMS Shifts** (mandatory)

| Field | Value |
|---|---|
| Journal Name | FMS Shifts |
| Type | Miscellaneous |
| Short Code | FCST |
| Default Account | 191600 (FMS Cash Clearing) |
| Currency | KES |

Click **Save**.

> **Why Miscellaneous?** Shift sales entries are not bank statements, not customer invoices, not vendor bills. They are internal posting journals. "Miscellaneous" is the correct Odoo type for this.

**Optional: Separate Cash Journal** (recommended if station has heavy cash volume)

If you want cash collections (safe drops, bank deposits) in a separate journal from shift sales:

| Field | Value |
|---|---|
| Journal Name | Station Cash |
| Type | Cash |
| Short Code | CASH |
| Default Account | 101000 (Cash in Safe) |

### Verify

- Accounting → Configuration → Journals → find "FMS Shifts" with short code FCST.
- Click it — confirm default account is 191600.

---

## Step 4 — Fuel Products

### What and Why

Each grade of fuel (Diesel, Unleaded/Super, V-Power, Kerosene, LPG) must be a product record in Odoo. FMS extends the product with two extra fields:

- **Is Fuel Product** — marks it as a fuel for FMS purposes
- **Fuel Revenue Account** — which income account is credited when this fuel is sold
- **Fuel COGS Account** — which expense account is used when residual allocations move COGS

Without these two accounts on every fuel product, shift close will fail with "GL Config gate failed."

Non-fuel products that attendants sell (Carwash, Engine Oil, LPG) can also be set up, but they only need COGS accounts if they will appear in residual allocations.

### Where

**Inventory → Products → New** (or edit existing)

### What to Create Per Fuel Product

Navigate to: **Inventory → Products → [Product Name]**

**General tab:**

| Field | Value |
|---|---|
| Product Name | Diesel / Super (Unleaded) / V-Power / Kerosene / LPG |
| Product Type | Consumable (not Storable — FMS manages fuel stock via dip readings) |
| Unit of Measure | Litre (L) |
| Sales Price | Current pump selling price per litre (e.g. 222.80 for Diesel) |
| Can be Sold | Yes |
| Can be Purchased | Yes (for vendor bills on fuel deliveries) |

**FMS tab** (appears after FMS module is installed):

| Field | Value | How to find the account |
|---|---|---|
| Is Fuel Product | ✓ Checked | Enables fuel-specific features |
| Fuel Revenue Account | e.g. 400000 Diesel Revenue | Type the account code in the search field |
| Fuel COGS Account | e.g. 591000 Diesel COGS | Type the account code in the search field |

Click **Save**.

### Full Product List for a Typical Kenyan Station

| Product | Revenue Account | COGS Account | Is Fuel |
|---|---|---|---|
| Diesel | 400000 | 591000 | ✓ |
| Super (Unleaded) | 400100 | 591100 | ✓ |
| V-Power | 400200 | 591200 | ✓ |
| Kerosene (IK) | 400400 | 591300 | ✓ |
| LPG (cooking gas) | 400300 | 591400 | ✓ |
| Carwash (Basic) | — | 591200 | ✗ (non-fuel, but used in residual allocation) |
| Engine Oil (1L) | — | 592000 | ✗ |

> **Non-fuel products only need a COGS account if they appear in residual allocations.** If carwash is frequently lumped into fuel by attendants (very common), set its COGS account. If it is always sold separately via POS, you can leave it blank.

### Verify

- Open each fuel product → FMS tab → both Revenue Account and COGS Account are filled.
- `Is Fuel Product` is checked.
- Confirm the revenue account type is `income` — not `asset` or `expense`.

---

## Step 5 — Fuel Tank Locations

### What and Why

Odoo uses "stock locations" to track where physical inventory lives. Each underground fuel tank is a stock location. FMS extends the location with:

- **Is Fuel Tank** — marks it for dip reading collection
- **Fuel Product** — which product is stored in this tank

When a shift opens, FMS auto-creates dip entry rows for every location where `Is Fuel Tank = True` for the current company. If a tank has no location record, it will not appear in dip readings.

### Where

**Inventory → Configuration → Locations**

### Steps

**First:** Create a parent location to group all tanks:

| Field | Value |
|---|---|
| Location Name | Fuel Tanks |
| Location Type | Internal Location |
| Parent Location | Physical Locations / [Your Company] |

**Then:** Create one child location per underground tank:

| Field | Value |
|---|---|
| Location Name | e.g. Diesel Tank 1 |
| Location Type | Internal Location |
| Parent Location | Fuel Tanks (the parent you just created) |
| Is Fuel Tank | ✓ Checked |
| Fuel Product | Diesel (select the product created in Step 4) |

Repeat for every tank.

### Naming Convention

Use a consistent naming convention:
- `[Product] Tank [Number]` — e.g. "Diesel Tank 1", "Diesel Tank 2", "Super Tank", "V-Power Tank"
- If a product has two tanks (dual-tank for Diesel), name them separately — they each get their own dip row.

### Example Setup for a Typical Station

| Tank Name | Product | Capacity (L) |
|---|---|---|
| Diesel Tank 1 | Diesel | 30,000 |
| Diesel Tank 2 | Diesel | 20,000 |
| Super Tank | Super (Unleaded) | 15,000 |
| V-Power Tank | V-Power | 10,000 |
| Kerosene Tank | Kerosene (IK) | 8,000 |

> **Tanks storing the same product:** Each tank is a separate location but same product. The dip tab will show two rows for Diesel — one per tank. Meter readings and tank dips are matched separately, and variances are computed per tank.

### Verify

- Inventory → Configuration → Locations → search your tank names.
- Open each — confirm `Is Fuel Tank = True` and `Fuel Product` is set.
- Count: the number of tank locations must equal the number of dip rows you expect to see when opening a shift.

---

## Step 6 — Pumps and Nozzles

### What and Why

Each physical fuel pump is a `fms.pump` record. Each hose/nozzle on that pump is a `fms.pump.nozzle` record. This is the most critical setup step — **the opening readings for the very first shift come from the nozzle's "Current Meter" values.**

If you enter wrong current meter values here, every shift from the first one onward will have wrong opening readings. There is no automatic way to fix this later without a database correction.

### What to Record Before Entering Data

Before touching the system, physically visit each pump and write down:

```
PUMP METER READING SHEET — [Station Name] — [Date]
─────────────────────────────────────────────────────────────
Pump: [name]   Nozzle: [letter/label]   Product: [fuel]

  Electronic Cash Totalizer (KES):  _________________________
  Electronic Volume Totalizer (L):  _________________________
  Mechanical Odometer (L):          _________________________

  Read by: ___________________  Time: ___________________
  Verified by: _______________  Time: ___________________
─────────────────────────────────────────────────────────────
```

Two people must verify each reading. Transcription errors in the initial meter values are the most common cause of systematic variance across all future shifts.

### Where

**Forecourt → Configuration → Station Setup**

### How to Create a Pump

Click **New**:

| Field | What to set |
|---|---|
| Pump Name | e.g. "Pump 1" or use the pump's physical label (UX5, DX6) |
| Pump Code | Short code for reports (e.g. P1, P2, UX5) |
| Order | Display order on shift form (1, 2, 3...) |
| Active | ✓ Checked |

### How to Add Nozzles (under the Nozzles tab)

For each hose/nozzle on this pump:

| Field | What to set |
|---|---|
| Nozzle Name | e.g. "P1-A", "P1-B" — pump + letter |
| Letter | A, B, C (hose identifier on this pump) |
| Order | 1, 2, 3 |
| Product | The fuel this nozzle dispenses |
| Init Elec Cash (KES) | **Current pump cash totalizer** — read from physical pump right now |
| Init Elec Volume (L) | **Current pump volume totalizer (litres)** — read from physical pump |
| Init Mech Volume (L) | **Current mechanical counter (litres)** — read from physical pump |
| Active | ✓ Checked |

> **"Init" vs "Current":** The system has two sets of fields — `init_*` (the initial values you enter here during setup) and `current_*` (updated automatically after each shift closes). On setup, they are the same. After the first shift closes, `current_*` is updated to the closing values. Never touch `current_*` manually after the first shift.

Click **Save**.

### Example for a Typical Dual-Nozzle Pump

```
Pump: UX5  (Code: UX5)

Nozzle UX5-A:
  Product:              Diesel
  Init Elec Cash:       27,694,880.00  KES
  Init Elec Volume:     124,500.00     L
  Init Mech Volume:     124,498.00     L

Nozzle UX5-B:
  Product:              Super (Unleaded)
  Init Elec Cash:       19,183,500.00  KES
  Init Elec Volume:     88,200.00      L
  Init Mech Volume:     88,198.00      L
```

> **Why the KES totalizer is so high:** Pump meters are cumulative since the pump was installed. A pump installed 3 years ago at a busy station will have hundreds of millions of KES on the cash totalizer. This is normal. The system only uses the difference (closing − opening) to compute shift sales, so the large absolute value does not matter.

### Verify

- Forecourt → Configuration → Station Setup → open each pump.
- Confirm every nozzle has:
  - Product set
  - Init Elec Cash > 0 (should match physical pump)
  - Init Elec Volume > 0
  - Init Mech Volume > 0
  - The Mech Volume should be close to (but not exactly equal to) Elec Volume — small differences (< 3L) are normal calibration tolerances.

---

## Step 7 — Employees and Attendants

### What and Why

FMS needs to know which employees are forecourt attendants. Attendant records control:
- Who appears in the Attendant field on Meter Readings rows
- Who gets an Attendant Cash reconciliation row when a shift closes
- Who cash drops can be recorded against

### Where

**HR → Employees** (or Forecourt → Configuration → Employees if the menu exists)

### What to Set Per Attendant

Open each employee record → **FMS tab**:

| Field | What to set |
|---|---|
| Is FMS Attendant | ✓ Checked |
| Default Pumps | Select which pumps this attendant normally operates (optional but useful for auto-assignment) |

Also confirm:
- **Name** is correctly spelled — it appears on all shift reports and GL entries.
- **Job Title** set to "Forecourt Attendant" for clarity.
- The employee has an Odoo **user account** linked (HR → Employees → [Name] → HR Settings tab → Related User) if they need system login access.

### Create the Supervisor Record

Also create the shift supervisor(s) as employees:

| Field | Value |
|---|---|
| Name | Full name |
| Job Title | Shift Supervisor |
| Is FMS Attendant | ✗ Not checked (supervisors are not attendants) |
| Related User | Link to their Odoo login |

### Minimum Staff Setup

For a 3-shift-per-day station, typical setup:

| Employee | Is Attendant | Pumps Assigned |
|---|---|---|
| [Station Manager] | No | — |
| [Day Supervisor] | No | — |
| [Evening Supervisor] | No | — |
| [Attendant 1] | Yes | Pump 1, Pump 2 |
| [Attendant 2] | Yes | Pump 3, Pump 4 |
| [Attendant 3] | Yes | Pump 5 |
| [Night Attendant] | Yes | All pumps |

### Verify

- HR → Employees → filter by `Is FMS Attendant = True` — count must match number of active forecourt staff.
- Open one attendant record → FMS tab → confirm `Is FMS Attendant = True`.
- Search: when creating a shift meter entry and clicking the Attendant field, can you see all attendant names in the dropdown? If no, the flag was not set.

---

## Step 8 — Price Periods

### What and Why

FMS uses price periods to validate meter readings. When the system checks that the electronic cash totalizer is consistent with the volume totalizer, it needs to know: what was the pump price per litre for this product on this date?

A price period says: "From [date], the pump price for [product] is [price] per litre."

If no price period exists for a product, the Elec vs Cash gate (Gate G2) cannot validate and may either skip the check or fail.

### Where

**Forecourt → Configuration → Price Periods** (or Forecourt → Configuration → Shift Definitions & Prices)

### How to Create a Price Period

**Forecourt → Configuration → Price Periods → New**

| Field | What to set |
|---|---|
| Product | Select the fuel product |
| Effective From | Date from which this price is valid (set to the date before the first shift) |
| Price per Litre (KES) | The current pump selling price |

Create one price period per fuel product, dated to before the first shift date.

### Example

| Product | Effective From | Price/L |
|---|---|---|
| Diesel | 2026-01-01 | 222.80 |
| Super (Unleaded) | 2026-01-01 | 217.50 |
| V-Power | 2026-01-01 | 250.00 |
| Kerosene (IK) | 2026-01-01 | 149.30 |

### When the EPRA Pump Price Changes

Whenever EPRA announces a new pump price:
1. Create a new price period for each affected product with the new price and the effective date.
2. Do NOT edit the old price period — leave it as is for historical accuracy.
3. The system will automatically use the correct price for each shift based on the shift date.

### Verify

- Forecourt → Configuration → Price Periods — at least one period per fuel product exists.
- The effective date of each period is on or before the date you plan to open the first shift.
- The prices match the current physical pump price.

---

## Step 9 — Site Preferences

### What and Why

Site Preferences is the master control panel for FMS. It pulls together everything you configured in Steps 1–8 and tells FMS how to behave. This is the last configuration step before the first shift.

One record exists per company. If you run multiple companies, each has its own Site Preferences.

### Where

**Forecourt → Configuration → Site Preferences**

### What to Set

**Accounting section:**

| Field | What to set | Why |
|---|---|---|
| Forecourt Sales Journal | FMS Shifts (created in Step 3) | All shift sales entries post here |
| Cash Clearing Account | 191600 FMS Cash Clearing (Step 2) | Debit side of every shift sales entry |
| Default Revenue Account | 400000 Diesel Revenue (or any income account) | Pre-fills new fuel products; not used in shift posting directly |
| Default COGS Account | 591000 Diesel COGS | Same — pre-fill default |

**Operations section:**

| Field | What to set | Why |
|---|---|---|
| Variance Meniscus (%) | 0.5 | Maximum tank dip variance allowed — 0.5% is EPRA standard |
| Elec vs Cash Threshold (L) | 5.0 | Max difference between volume and cash meters per nozzle |
| Attendant Assignment Mode | Per Nozzle | Supervisor assigns attendant to each nozzle row manually |
| Auto-sync Attendant Cash Lines | ✓ Enabled | System auto-creates cash rows when Start Closing is clicked |
| Auto-open Next Shift | ✓ Enabled (recommended) | Next shift auto-created and opened on close of current |

**Shift schedule section:**

| Field | What to set | Example |
|---|---|---|
| Shift Duration | 8 hours (3 shifts/day) or 12 hours (2 shifts/day) or 24 hours | 8hr for Day/Evening/Night |
| Shift 1 Label | 1_day | Appears in shift records and reports |
| Shift 2 Label | 2_evening | |
| Shift 3 Label | 3_night | |
| Shift 1 Start Hour | 6 | 06:00 AM |
| Shift 2 Start Hour | 14 | 02:00 PM |
| Shift 3 Start Hour | 22 | 10:00 PM |

**POS Integration section:**

| Field | What to set |
|---|---|
| Require POS Reconciliation | ✓ Enabled if using Odoo POS; ✗ Disabled if using external POS or no POS |

> **Require POS Reconciliation = False** is required if the station does not use Odoo Point of Sale to record fuel transactions. In that mode, the volume and cash reconciliation gates (G3 and G4) are skipped when no POS session is linked. All other gates still run.

Click **Save**.

### Verify

- Forecourt → Configuration → Site Preferences → open the record.
- Forecourt Sales Journal = FMS Shifts.
- Cash Clearing Account = 191600 FMS Cash Clearing.
- Variance Meniscus = 0.5.
- At least Shift Duration, Shift 1 Label, and Shift 1 Start Hour are set.

---

## Step 10 — Security Groups and Users

### What and Why

FMS uses role-based access. Each user must be assigned to the correct group before they can log in and perform their duties.

### Groups

| Group | Technical Name | Who gets it |
|---|---|---|
| FMS Attendant | `fms.group_fms_attendant` | Forecourt attendants (if they need system access) |
| FMS Supervisor | `fms.group_fms_supervisor` | Shift supervisors — can open and close shifts |
| FMS Accountant | `fms.group_fms_accountant` | Finance team — GL entries, credit customers, reports |
| Account User | `account.group_account_user` | Any user who needs to see the Accounting menu |
| Account Manager | `account.group_account_manager` | Accountant with full access including lock dates |

### How to Assign Groups

**Settings → Users & Companies → Users → [Select User]**

Under the **FMS** section, select the appropriate role.

Under the **Accounting** section, select "Accountant" for finance users or "Billing" for supervisors who only need to see invoices.

### Minimum User Setup

| User | FMS Role | Accounting Role |
|---|---|---|
| Station Manager | FMS Supervisor | Account Manager |
| Shift Supervisor(s) | FMS Supervisor | Billing |
| Forecourt Attendants | FMS Attendant | None (unless they view invoices) |
| Finance Officer / Accountant | FMS Accountant | Account Manager |
| System Administrator | All | Account Manager |

### Verify

- Log in as a supervisor user. Navigate to Forecourt → Operations → Shifts → New. Can you create a shift?
- Log in as an attendant user. Can they see Shifts? Can they see the "Open Shift" button? (They should NOT be able to.)
- Log in as accountant. Can they see Accounting → Journal Entries?

---

## Step 11 — Full Verification Checklist Before First Shift

Work through this checklist completely. Only open the first shift when every item is checked.

### Company & CoA
- [ ] Company name, country (Kenya), and currency (KES) are set
- [ ] Account 191600 exists with type `asset_receivable`
- [ ] All revenue accounts (400000–400400) exist with type `income`
- [ ] All COGS accounts (591000–591400) exist with type `expense_direct_cost`

### Journals
- [ ] "FMS Shifts" journal exists with short code FCST and default account 191600
- [ ] Journal type is Miscellaneous

### Products
- [ ] One product record exists per fuel grade
- [ ] Each fuel product: `Is Fuel Product = True`
- [ ] Each fuel product: `Fuel Revenue Account` is set to correct income account
- [ ] Each fuel product: `Fuel COGS Account` is set to correct COGS account
- [ ] Sales price per litre is current EPRA pump price

### Tank Locations
- [ ] One stock location per underground tank
- [ ] Each location: `Is Fuel Tank = True`
- [ ] Each location: `Fuel Product` is set
- [ ] Location names clearly identify the tank (e.g. "Diesel Tank 1")

### Pumps and Nozzles
- [ ] One `fms.pump` record per physical pump
- [ ] Each pump: at least one active nozzle
- [ ] Each nozzle: `Product` is set
- [ ] Each nozzle: `Init Elec Cash` entered from physical pump display (read by 2 people)
- [ ] Each nozzle: `Init Elec Volume` entered from physical pump display
- [ ] Each nozzle: `Init Mech Volume` entered from physical pump display
- [ ] Reading sheet signed by reader and verifier — filed physically

### Employees
- [ ] All active forecourt attendants have `Is FMS Attendant = True`
- [ ] All shift supervisors are set up as employees
- [ ] Each user account linked to the correct employee record

### Price Periods
- [ ] One price period per fuel product with current price and start date before first shift

### Site Preferences
- [ ] Forecourt Sales Journal = FMS Shifts
- [ ] Cash Clearing Account = 191600
- [ ] Variance Meniscus = 0.5%
- [ ] Shift labels and start hours match station's actual shift times
- [ ] Auto-sync Attendant Cash Lines = Enabled
- [ ] Require POS Reconciliation = set correctly for this station's POS setup

### Security
- [ ] Supervisor user(s) can log in and see the Forecourt menu
- [ ] Attendant user(s) have Attendant role
- [ ] Accountant user(s) have Accountant role and accounting access

---

## Step 12 — Opening the Very First Shift (Supervised)

Do this with the station manager and accountant present.

### Before Clicking "Open Shift"

1. Physical meter readings were recorded and verified (Step 6 reading sheet is signed and filed).
2. All tanks were dipped and opening dip volumes recorded (will be needed for Gate 5 verification).
3. At least one supervisor user is logged in.

### Creating the First Shift

**Forecourt → Operations → Shifts → New**

| Field | Value |
|---|---|
| Date | Today's date |
| Shift Label | 1_day (or whichever period this is) |
| Supervisor | The supervisor opening this shift |

Click **Open Shift**.

### Verify the Opening Readings

When the shift opens, the Meter Readings tab shows one row per nozzle with opening values auto-filled from the nozzle's `current_elec_volume`, `current_elec_cash`, and `current_mech_volume` fields (which at first shift equal the `init_*` values you entered in Step 6).

**Cross-check each row:**
- Opening Elec Volume (L) in FMS must match the physical pump display reading from the signed sheet.
- If they don't match: DO NOT proceed. Close/delete this draft shift. Fix the nozzle init values in Station Setup. Open the shift again.

**Verify the Tank Dips tab:**
- One row per tank location you created in Step 5.
- Opening volumes show the init dip values (0.0 if you didn't set them — this is OK for the first shift as there is no previous shift).
- Enter today's actual dip readings in the "Closing Dip (L)" column.

If both match, **the system is correctly configured.** Proceed with the shift as per the Operations Training guide.

### After the First Shift Closes Successfully

Confirm these happened:
1. Shift state = Closed.
2. `Sales GL Entry` field on the shift is populated with a journal entry number (e.g. FCST/2026/00001).
3. Go to Accounting → Journal Entries → find the entry — verify the debit and credits match expected amounts.
4. Open each nozzle in Station Setup — the `current_*` values have advanced to the first shift's closing readings.
5. If Auto-open Next Shift is enabled, the next shift is already in Open state.

**The station is now live.**

---

## Appendix A — Initial Meter Reading Sheet Template

```
INITIAL PUMP METER READING SHEET
Station: _______________________________  Date: _______________

─────────────────────────────────────────────────────────────────────────
Pump   Nozzle   Product         Elec Cash (KES)   Elec Vol (L)   Mech Vol (L)
─────────────────────────────────────────────────────────────────────────
____   ______   ____________    _______________   ____________   ___________
____   ______   ____________    _______________   ____________   ___________
____   ______   ____________    _______________   ____________   ___________
____   ______   ____________    _______________   ____________   ___________
____   ______   ____________    _______________   ____________   ___________
____   ______   ____________    _______________   ____________   ___________
─────────────────────────────────────────────────────────────────────────

INITIAL TANK DIP READINGS
─────────────────────────────────────────────────────────────────────────
Tank Name              Product        Opening Dip (L)   Dip Time
─────────────────────────────────────────────────────────────────────────
____________________   ____________   _______________   _________
____________________   ____________   _______________   _________
____________________   ____________   _______________   _________
____________________   ____________   _______________   _________
____________________   ____________   _______________   _________
─────────────────────────────────────────────────────────────────────────

VERIFIED BY:

Reader 1: ____________________________  Signature: _______________
Reader 2: ____________________________  Signature: _______________
Manager:  ____________________________  Signature: _______________

Date/Time readings were taken: _______________________________________
Filed by: ____________________________________________________________
─────────────────────────────────────────────────────────────────────────
```

---

## Appendix B — Common Setup Errors and Fixes

| Error | When it appears | Fix |
|---|---|---|
| "GL Config gate failed — Diesel has no revenue account" | On first Close Shift attempt | Inventory → Products → Diesel → FMS tab → set Fuel Revenue Account |
| "GL Config gate failed — no FMS journal configured" | On first Close Shift attempt | Forecourt → Configuration → Site Preferences → set Forecourt Sales Journal |
| "No dip entries for this shift" | On Open Shift | No tank locations with `Is Fuel Tank = True` exist for this company |
| "No meter entries for this shift" | On Open Shift | No active nozzles exist — check Pumps configuration |
| Opening readings are all zero | On Open Shift | Nozzle Init values were not entered — return to Station Setup |
| Gate G1 fails immediately | On first Close Shift | Mech Volume was not read from pump — entered wrong column; re-enter |
| Gate G2 fails | On first Close Shift | Price period does not exist or price is wrong — check Forecourt → Configuration → Price Periods |
| "Attendant not found" | When entering meter row | Employee does not have `Is FMS Attendant = True` |
| Dip tab shows wrong number of tanks | On Open Shift | Some tank locations are missing `Is Fuel Tank = True` |
| "Another shift is already open" | On creating a new shift | An incomplete shift exists — find it and close or delete it |

---

## Appendix C — Setup Data Entry Order (Summary)

```
Settings → Companies                     → Set name, country, currency
Accounting → Chart of Accounts           → Create 191600 and all required accounts
Accounting → Journals                    → Create FMS Shifts journal
Inventory → Products                     → Create fuel products with FMS accounts
Inventory → Configuration → Locations   → Create tank locations with Is Fuel Tank
Forecourt → Configuration → Station Setup → Create pumps and nozzles with init values
HR → Employees                           → Set Is FMS Attendant on all attendants
Forecourt → Configuration → Price Periods → Create current price per product
Forecourt → Configuration → Site Preferences → Wire journal, accounts, set options
Settings → Users                         → Assign FMS roles to all users
                                            ↓
                              Open First Shift
```
