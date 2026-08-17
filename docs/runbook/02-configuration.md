# 02 — Configuration

Audience: Manager / Accountant
Do this once before opening the first shift.

---

## 1. Site Preferences

**Forecourt → Configuration → Site Preferences**

| Field | Value to set | Why |
|---|---|---|
| Company | Your company | Scopes all FMS data |
| FMS Journal | Cash journal or create a dedicated "FMS Shifts" journal | Where shift GL entries post |
| Cash Clearing Account | e.g. 191600 FMS Cash Clearing | Debit side of every shift sales entry |
| Variance Meniscus (%) | 0.5 (default) | Max dip variance before Gate 5 blocks close |
| Auto-sync Attendant Cash Lines | Enabled (recommended) | Auto-creates attendant rows on Start Closing |

Click **Save**.

---

## 2. Chart of Accounts — Fuel Products

For each fuel product, set two GL accounts. Go to:
**Inventory → Products → [Fuel Product] → FMS tab**

| Field | Example account |
|---|---|
| Fuel Revenue Account | 400000 Sales of Fuel Income |
| Fuel COGS Account | 591000 Cost of Sales — Fuel |

Products without these set are skipped during GL posting (a warning is logged).

---

## 3. Pumps and Nozzles

**Forecourt → Configuration → Pumps**

For each physical pump:
1. Click **New**.
2. Set **Name** (e.g. Pump 1), **Location** (forecourt stock location), **Active**.
3. Under **Nozzles** tab, add a row per nozzle:
   - **Product** — fuel product dispensed
   - **Nozzle Label** — e.g. "1A", "1B"
   - **Current Elec Cash (KES)** — current pump meter totalizer (KES). Read from the physical pump.
   - **Current Elec Volume (L)** — current pump volume totalizer (litres).
   - **Current Manual Meter (L)** — current mechanical odometer (litres).
4. Click **Save**.

These "current" values become the opening readings for the first shift.

---

## 4. Fuel Tank Locations

**Inventory → Configuration → Locations → New** (or edit existing)

For each underground tank:
- Enable **Is Fuel Tank**.
- Set **Fuel Product** to the product stored in that tank.

These locations appear in the Tank Dips tab when a shift is opened.

---

## 5. Attendants

**Forecourt → Configuration → Employees** (or HR → Employees)

For each forecourt attendant:
- Enable **Is FMS Attendant**.
- Optionally assign **Default Pumps** (used to auto-populate attendant cash rows).
- Assign the **Attendant** Odoo user account and add them to `fms.group_fms_attendant` security group.

---

## 6. Price Periods

**Forecourt → Configuration → Price Periods**

Create a price period whenever the pump price changes:
- **Product** — fuel product
- **Start Date** — effective date of new price
- **Price per Litre (KES)** — pump selling price

The system uses price periods to validate pump cash meter vs. volume meter consistency.

---

## 7. FMS Journal (create if needed)

**Accounting → Configuration → Journals → New**

| Field | Value |
|---|---|
| Name | FMS Shifts |
| Type | Miscellaneous |
| Short Code | FMS |
| Default Account | 191600 FMS Cash Clearing |

Set this journal in Site Preferences.
