# Feature: Shift-Linked Financial Documents

**Module:** `fms`
**Status:** Specification — Release 1
**Related:** Report Catalogue §12.3 (D11), §1.3 (validation), §1.6 (analytic plans)

---

## 1. What this is

Every financial document raised on the forecourt — a cash sale, a customer payment, an expense, a credit invoice — needs to answer three questions: **which shift, which attendant, which sales point**. Today none of them can.

This feature adds that link, and it does so **once, as a shared extension**, rather than four times as four features.

The consequence is larger than it sounds. Once documents carry a shift, the shift stops storing its own totals and starts computing them by reading its documents. That is the difference between a shift record that is a **lens** over the ledger and one that is a **second ledger** — and the second kind is what this whole architecture exists to avoid.

### Release plan

| Release | Document type | Odoo object | Status |
|---|---|---|---|
| **1** | Sales Receipt — non-invoice sales | `account.move`, `out_receipt` | **This spec** |
| **1** | Customer Payment — collections against AR | `account.payment`, inbound | **This spec** |
| 2 | Expense — forecourt spending | `hr.expense` → `account.move` | Section 8.1 |
| 2 | Customer Invoice — credit sales | `account.move`, `out_invoice` | Section 8.2 |
| Later | Deliveries, staff debt, cylinder deposits | Various | Section 8.3 |

Releases 2 and later reuse the extension defined here. They add fields specific to their document type; they do not add a second way of linking to a shift.

---

## 2. The rule that governs all of it

> **Every document stays a native Odoo document. The `fms` module adds fields to it and never replaces it.**

No `fms.sales.receipt`. No `fms.customer.payment`. No custom document model of any kind.

Four reasons, in order of how much they would cost to get wrong:

**eTIMS.** Kenyan fiscal integration hangs off `account.move`. A sales document that isn't one silently skips the fiscal path — the sale happens, the customer gets paper, and nothing reaches KRA. This is the reason to be careful with the phrase "outside the standard invoicing workflow": outside the *UI* workflow is fine, outside `account.move` is a compliance failure that surfaces at audit.

**The ledger.** Native documents post revenue, COGS, tax and AR without anyone writing a journal entry. A custom model means hand-written entries, which means a parallel ledger, which means two versions of every number.

**Everything downstream is free.** Aging, statements, reconciliation, credit control, multi-currency, refunds, audit trail — all of it already works against `account.move`.

**Upgrades.** Three fields on a native model survive a version jump. A parallel document model is a port every year.

---

## 3. The shared extension

An abstract mixin, applied to every document type in the release plan.

### 3.1 Fields

| Field | Type | On | Required | Purpose |
|---|---|---|---|---|
| `shift_id` | M2O `fms.shift` | All | Yes | The period anchor. Everything else depends on this |
| `attendant_id` | M2O `hr.employee` | All | Yes | Who transacted. Feeds R25, R27, R28 |
| `analytic_distribution` | Native | All | Defaulted | Sales point, per §1.6. Set from the nozzle or counter, not typed |

**Sales documents only** (`out_receipt`, `out_invoice`):

| Field | Type | Required | Purpose |
|---|---|---|---|
| `vehicle_id` | M2O `fms.vehicle` | No | Feeds R13. Optional because walk-in cash has no vehicle |
| `nozzle_id` | M2O `fms.nozzle` | Fuel lines | Ties a document to a meter — the join that makes R10's three-way reconciliation possible |

> **Where `nozzle_id` lives is a design choice worth making explicitly.** On the header it is simpler and correct for a fuel-only receipt. On the line it is correct for a mixed sale — fuel plus a bottle of oil plus a car wash. **Recommendation: line level, with a header convenience field that sets all fuel lines.** A mixed receipt is common at a forecourt, and retrofitting line-level attribution after the data exists is expensive.

### 3.2 Constraints

These make the shift link trustworthy rather than decorative.

| Rule | Behaviour |
|---|---|
| Document date must fall inside the shift window | `ValidationError` |
| Shift must be **open** when the document is created | `ValidationError` |
| A posted shift's documents are **locked** | No create, edit or delete against a closed shift. Corrections are reversals |
| Company on document must match company on shift | `ValidationError` |
| Fuel line requires a nozzle | `ValidationError` |
| Attendant must be rostered to that shift | Warning, not blocking — cover happens |

**The locking rule is what makes shift close mean something.** Without it, a document raised after close changes a reconciliation that was already signed, and the audit trail becomes fiction.

---

## 4. Sales Receipt

`account.move`, `move_type = 'out_receipt'`. Native Odoo — enable under Invoicing → Configuration → Customer Invoices → *Sale Receipt*, then work from Invoicing → Customers → Receipts.

### 4.1 What it replaces

Cash sales are currently **derived**: `cash = metered litres − credit`. A plug, not a measurement.

That is why 25 January 2026 recorded diesel cash sales of **−663.93 litres and −KES 113,134**. Keyed credit exceeded metered sales, and the cash column silently absorbed the difference. Any error in credit entry lands in cash by construction, and nothing in the system can detect it — the report foots perfectly and is wrong.

**A receipt makes cash measured.** The residual stops being a definition and becomes a genuine disagreement between three independent records.

### 4.2 Partner handling

Walk-in cash has no customer, and a blank partner breaks AR reporting. **Use a dedicated "Walk-in — Cash" partner** rather than leaving it empty, and exclude it from R12 and statements by category.

### 4.3 Granularity — decision D11a

| Answer | Built as | Gains | Costs |
|---|---|---|---|
| Per transaction | A receipt per fill, raised at the pump | R28 detects an individual fraudulent fill; R13 gets real per-vehicle history; R25 gets true transaction counts | Highest keying load, at the busiest moment, by the least-trained user. Needs a device at the island |
| Per nozzle per shift | One aggregate receipt, keyed at close | Almost no extra work; R10's reconciliation still works in full | R28 drops to shift-level resolution; R13 unusable for per-vehicle consumption |

Both fix the plug. **Settle this before building the form, because it changes who the user is** — an attendant at a pump or a cashier at a desk — and that changes the entire UI.

---

## 5. Customer Payment

`account.payment`, inbound. **A payment is not a sale**, and conflating the two is the most expensive mistake available in this feature.

When a credit customer settles their account, the sale was already recognised when the fuel went into the truck. Booking the collection as a sales receipt recognises the revenue twice, and you then spend a month explaining why fuel sales exceed metered litres.

Your legacy system already separates them — the cashier sheet carries **Sales** and **Recpts** as distinct columns, and its formula treats them distinctly. That design has years of use behind it. Keep it.

| Field | Notes |
|---|---|
| `shift_id` | **Required.** Expected cash cannot be computed unless collections attach to the shift that took them |
| `attendant_id` | Who received the money |
| Journal | Decides whether it reaches the drawer. M-Pesa and card collections do not increase cash in hand; native journals handle this without special-casing |

> **`shift_id` on payments fixes a live defect.** On 26 January 2026 one cashier showed expected cash of −11,000 against actual +11,000 — a collection keyed with the wrong sign — producing a phantom KES 22,000 station surplus that the report presented as real. Attaching collections to a shift is what makes the "expected cash can never be negative" rule (Catalogue §1.3) enforceable rather than aspirational.

**Printing.** A payment slip is a print layout on `account.payment`, not a document type. OCA's `account_voucher_print` and `account_receipt_send` do this, but both surfaced at v12 and v15 and are lightly maintained — **verify an 18.0 branch before depending on either**, and be willing to write the QWeb template yourself. It is an afternoon's work.

---

## 6. How the shift close changes

The reconciliation formula does not change. **Every term in it stops being keyed and starts being a sum of documents.**

```
Total Credits = Invoices + POS + VISA
Expected Cash = Sales − Total Credits + Receipts − Payments
```

| Term | Before | After |
|---|---|---|
| Sales | Derived from meters | Σ sale documents for the shift |
| Invoices | Keyed | Σ `out_invoice` for the shift |
| POS / VISA | Keyed | Σ receipts by payment journal |
| Receipts | Keyed | Σ inbound `account.payment` for the shift |
| Payments | Keyed | Σ outbound payments and expenses for the shift |
| Cash sales | **The plug** | Σ receipts on a cash journal — measured |

### 6.1 The three-way reconciliation

```
Metered litres        from meter entries
Documented litres     Σ fuel lines on receipts + invoices for the shift
Cash counted          blind count on the cash declaration

Volume residual = Metered − Documented        ← R10, now a real comparison
Cash variance   = Counted − Expected Cash     ← R4 / R11
```

Two independent measurements disagreeing is information. A plug agreeing with itself is not.

### 6.2 New validation this makes possible

**Documented fuel litres must not exceed metered litres beyond tolerance.** You cannot sell fuel that never came out of a pump. Impossible to check while cash is a plug; trivial once it isn't.

---

## 7. Reports unlocked

| Report | Effect |
|---|---|
| **R10** | Gains its diagnostic half — net-to-zero test, diagnosed cause, document to correct. Currently a list only |
| **R13** | Becomes possible at all, given per-transaction granularity and a vehicle |
| **R12** | Fuel volume per customer, and the vehicle filter, move from Phase 2 to buildable |
| **R25** | True transaction counts and average ticket per attendant, not just litres |
| **R28** | Per-fill anomaly detection, at per-transaction granularity |
| **F10** | Business-line P&L resolves cleanly once every document carries a sales point |

---

## 8. Future releases

Each of these reuses section 3's extension. None of them introduces a new document model.

### 8.1 Expenses — Release 2

Forecourt spending recorded through `hr.expense`, posting to `account.move`. Adds `shift_id` and the analytic distribution from the mixin.

- Replaces the `expense_amount` field currently on attendant cash, which becomes a **computed total** of linked expenses. A bare amount cannot carry an approval, an attachment, a VAT treatment or an account — so an expense recorded that way is invisible to F14 and gets re-keyed by the accountant.
- Feeds the **Payments** term in the expected-cash formula directly.
- Menu placement: Operations → Expenses, as a link into the Expense module (Catalogue §12.2).

### 8.2 Customer Invoices — Release 2

`out_invoice` already exists and already posts correctly. This release adds only:

- The section 3 extension — shift, attendant, analytic.
- `vehicle_id`, for R13.
- The **credit limit block** (Catalogue §9, build order 4). Note the exposure calculation: posted AR alone understates it. Exposure must include unposted credit sales in open shifts and delivered-but-uninvoiced orders, or a customer who exceeded their limit this morning still passes.

### 8.3 Later

Delivery receipts, staff debt, LPG cylinder deposits, tyre and service jobs. Each is a document type that already exists in Odoo, needing the same three fields.

---

## 9. Open decisions

| # | Question | Blocks | Recommendation |
|---|---|---|---|
| **D11** | Native Sale Receipts or POS orders? | This entire feature, and D2 | Native receipts. Keeps sales on `account.move` — eTIMS, tax, GL and AR all work with no extra wiring |
| **D11a** | Per transaction or per nozzle per shift? | Form design, R13, R28 | Count cash fills per nozzle in a peak hour before deciding. A per-transaction design attendants cannot sustain degrades into fabricated receipts, which is worse than the aggregate — you lose the resolution *and* trust the data |
| **D11b** | `nozzle_id` on header or line? | Data model | Line, with a header convenience setter. Mixed sales are common; retrofitting is expensive |
| **D2** | Cash model — cash journal per cashier, or `pos.session`? | R11, F13 | Follows from D11. With receipts, a cash journal per cashier plus a thin blind-count record |

---

## 10. Explicitly not in scope

- **A custom document model of any kind.** See section 2.
- **Changing the reconciliation formula.** It is correct; only its inputs change.
- **The blind-count fix.** An active defect fixed independently and ahead of this work (Catalogue build order 6b).
- **eTIMS transmission itself.** A separate integration. This feature ensures the documents exist in the right shape to be transmitted; it does not transmit them.