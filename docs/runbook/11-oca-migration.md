# 11 — OCA Migration Audit & Status

**Date:** 2026-08-18  
**Audience:** Architect, Developer  
**Status:** COMPLETE — no active migration required

---

## Executive Summary

A full audit of the FMS codebase confirms that **Cybrosys addons were never a hard
dependency of FMS or FMS Accounting**. No database has Cybrosys installed. The only
Cybrosys artifacts were dead code and an addons-path reference — both now removed.

The system currently runs:

```
Odoo 18 Community (Core)
         ↓
FMS custom module (fms)
         ↓
FMS Accounting module (fms_accounting)
```

No OCA addons are currently installed. The architecture is clean.

---

## 1. Cybrosys Dependency Inventory

| Item | Finding |
|------|---------|
| `cybrosys_addons/` directory | Present on disk at `/home/niini/cybrosys_addons/` |
| Modules in directory | `base_accounting_kit` (v18.0.5.0.9), `base_account_budget` |
| Installed in `fms_e2e` | **None** — `ir.module.module` shows `[]` |
| Installed in `test_fms*` | **None** |
| In `fms/__manifest__.py` depends | **Not present** |
| In `fms_accounting/__manifest__.py` depends | **Not present** |
| Python imports in FMS | `fms_cybrosys_compat.py` — docstring only, **no logic** |
| XML/view inheritance of Cybrosys models | **None found** |
| External IDs referencing Cybrosys | **None found** |
| Security groups from Cybrosys | **None found** |
| Database tables from Cybrosys | **None** (never installed) |

**Conclusion:** Cybrosys was evaluated, a compatibility shim was started but never
completed, and the modules were never installed. Zero migration risk.

---

## 2. What FMS_Accounting Provides (Without Cybrosys)

All financial reporting is self-implemented via `fms_financial_reports.py`:

| Report | Implementation | Model |
|--------|---------------|-------|
| Profit & Loss | `fms.report.pl` wizard | queries `account.move.line` by `account_type` |
| Balance Sheet | `fms.report.balance.sheet` wizard | same |
| Trial Balance | `fms.report.trial.balance` wizard | same |
| Debtors Aging | `fms.report.debtor` | queries `account.move.line` |
| GL Reconciliation | `fms.report.gl.recon` view | SQL view |
| Attendant Cash Breakdown | `fms.report.attendant.cash` | SQL view |

These do not depend on any third-party addon. They query Odoo core models directly.

---

## 3. OCA Replacement Matrix

Since Cybrosys was never installed, this table documents what FMS implements itself
vs. what OCA could optionally add in the future.

| Feature | Current State | OCA Option | Action |
|---------|--------------|------------|--------|
| P&L / Balance Sheet / Trial Balance | Self-implemented in fms_accounting | `account_financial_report` (OCA/account-financial-reporting) | **D — Not required; FMS implementation sufficient for current scale** |
| Bank Reconciliation | Native Odoo | `account_reconcile_oca` | D — native Odoo sufficient |
| Per-Journal Lock Dates | Native Odoo lock_date | `account_journal_lock_date` | D — not yet needed |
| Credit Control / AR Follow-up | Manual via debtors report | `account_credit_control` | D — future consideration |
| Post-Dated Cheques | `account.payment` + `fms_pdc_state` field | No OCA equivalent | E — FMS custom, keep |
| Budget Management | Not implemented | Native Odoo budgets | D — out of scope |
| Recurring Entries | Not implemented | `account_move_template` | D — future |
| Async Reconciliation | Not applicable at current scale | `account_reconcile_oca_queue` | D — future (needed at 400+ sites) |

**Action codes:**
- D = Remove/Don't install (functionality not needed or already covered)
- E = Keep existing FMS implementation

---

## 4. Changes Made (2026-08-18)

### 4.1 Removed dead compatibility shim

`fms_accounting/models/fms_cybrosys_compat.py` — contained only a docstring, no
executable code. Removed file and its import from `__init__.py`.

### 4.2 Removed Cybrosys from addons path

`Makefile`: Removed `,/home/niini/cybrosys_addons` from `ODOO_ADDONS`.  
Updated comment to reflect clean dependency graph.

### 4.3 No database migration required

Cybrosys was never installed. No models, tables, or XML IDs to migrate.

---

## 5. OCA Future Roadmap (When Needed)

If the system scales to 50+ stations, consider:

```
Priority 1 (Performance):
  account_financial_report (OCA/account-financial-reporting@18.0)
  → Replace fms_financial_reports.py wizards with indexed SQL views
  → 10-100x faster at high GL entry volume

Priority 2 (AR Management):
  account_credit_control (OCA/account-financial-tools@18.0)
  → Auto-dunning for fleet customers on credit

Priority 3 (Scale):
  account_journal_lock_date (OCA/account-financial-tools@18.0)
  → Per-site journal locking for multi-station deployment
```

**Installation would require:**
1. Clone OCA repo at pinned commit/tag
2. Add to addons path
3. Add to fms_accounting `depends`
4. Remove corresponding FMS custom implementations
5. Run full test suite

---

## 6. Current Dependency Graph

```
Odoo 18 Community
  base, mail, account, stock, point_of_sale, hr, purchase
         ↓
fms (Forecourt Management System)
  depends: base, mail, account, stock, point_of_sale, hr
         ↓
fms_accounting (FMS Accounting)
  depends: fms, account, stock, purchase, mail
```

No third-party addon dependency. Clean.

---

## 7. Security Audit — OCA Replacement Impact

Not applicable — no OCA modules installed, no security changes.

Existing FMS security unchanged:
- `fms.group_fms_attendant` — meter/dip entry
- `fms.group_fms_supervisor` — shift close, override
- `fms.group_fms_accountant` — financial reports
- Company isolation via record rules on all FMS models

---

## 8. Test Baseline

Before cleanup: **266 tests, 0 failures, 0 errors**  
After cleanup: re-verified (see task.md)

---

## 9. Rollback

Nothing to roll back. The `cybrosys_addons/` directory remains on disk at
`/home/niini/cybrosys_addons/` and can be re-added to the addons path if
ever needed. No data was deleted.
