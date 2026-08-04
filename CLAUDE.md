# FMS (Forecourt Management System) Development Memory

**Project:** Forecourt Management System for Odoo 18  
**Status:** Development  
**Framework:** Python CLI + Claude Code  
**Started:** 2026-08-04  

---

## 🎯 Project Summary

**FMS** solves the core problem of **shift-based fuel reconciliation** at fuel stations:
- Reconciling what pump meters say was sold vs. actual tank stock
- Tracking where money went (cash, AR, cards, expenses)
- Handling lumped non-fuel sales (carwash lumped into "Diesel")
- Enforcing hard gates (FC Cash must be zero, variances must be acceptable)

**Reference:** Complete 14-section specification in `FMS_Complete_Specification_Technical_Guide.md`

---

## 📋 Core Concepts

### The Residual Allocation Problem

**Scenario:** Attendant reports "MPesa KES 250,000 Diesel" but pump meter shows only KES 180,000 Diesel sold

**Why the gap?** Attendant lumped in non-fuel sales for speed:
- KES 100,000 carwash
- KES 50,000 LPG
- KES 20,000 miscellaneous

**System Solution:**
1. Detect residual: Diesel meter -100L (under-reported)
2. Auto-allocate: Diesel -100L → Carwash +100L @ rate conversion
3. Post journal: DR Diesel COGS | CR Carwash COGS
4. Result: Inventory & GL accurate, no manual intervention needed

**Reference:** Spec Section 7.1

### Hard Gates (Non-Negotiable Constraints)

```
GATE 1: FC Cash = 0 (exactly)
  ├─ Every KES must be accounted for
  ├─ If variance exists, supervisor posts correction
  └─ Only then can shift close

GATE 2: All Attendants Clear
  ├─ Each person's balance = (Sales + Receipts) - (Cash + AR + Card + Expenses)
  ├─ Must = 0 for each person
  └─ Supervisor must resolve discrepancies

GATE 3: Stock Variance < Meniscus
  ├─ Default meniscus: ±0.5% per tank
  ├─ Example: 10,000L tank, variance max ±50L
  └─ If exceeded, supervisor investigates or posts adjustment
```

**Reference:** Spec Section 7.2-7.3

### Data Model Architecture

```
fms.shift (Main orchestration)
  ├─ One2Many: fms.shift.meter.entry (pump readings, editable)
  ├─ One2Many: fms.shift.dip.entry (tank readings, editable)
  ├─ One2Many: fms.shift.attendant.cash (cash reconciliation)
  ├─ One2Many: fms.shift.product.sales (computed, read-only)
  ├─ One2Many: fms.shift.residual.allocation (auto-calculated)
  ├─ One2Many: fms.meter_log (immutable audit trail, written on close)
  └─ One2Many: fms.dip_log (immutable audit trail, written on close)

Extensions to Odoo core:
  └─ stock.location: +fms_is_fuel_tank, +fms_fuel_product_id
  └─ product.product: +fms_is_fuel, +fms_cogs_account_id, +fms_revenue_account_id
  └─ hr.employee: +fms_is_attendant, +fms_pumps_assigned
```

**Reference:** Spec Section 8.1

---

## 🛠️ Development System

### Python CLI Orchestrator

**Command:** `python dev-guide.py`

**Available commands:**
```
status          → Show current progress (tasks done/remaining)
task FMS-NNN    → Start specific task (shows prompt + testing guide)
list            → List all 8 tasks
info FMS-NNN    → Show detailed task info
report          → Generate progress report
```

### Task Registry (8 Tasks, ~16 hours)

| Task | Title | Deps | Est. Time |
|---|---|---|---|
| **FMS-001** | Core Models & Schema | None | 3h |
| **FMS-002** | Child Models & Entry Forms | FMS-001 | 2h 30m |
| **FMS-003** | Residual Allocation Algorithm | FMS-001, 002 | 2h |
| **FMS-004** | Security & Access Control | FMS-001 | 1h 30m |
| **FMS-005** | Journal Entry Posting & GL | FMS-003, 004 | 2h |
| **FMS-006** | Shift Lifecycle & Hard Gates | FMS-002, 003 | 1h 30m |
| **FMS-007** | UI/UX Forms & Reports | FMS-002, 006 | 3h |
| **FMS-008** | Testing & Go-Live | FMS-005, 007 | 2h |

**Critical path:** FMS-001 → 002 → 003 → 005 → 007 → 008

### Workflow (Per Task)

1. **Run:** `python dev-guide.py task FMS-NNN`
   - Shows task details
   - Lists subtasks
   - Shows expected artifacts
   - Generates comprehensive Claude Code prompt
   - Displays testing guide + sample data

2. **Claude Code generates:** Model + test code (subtask-by-subtask)

3. **You run tests locally:** 
   ```bash
   pytest tests/test_fms_nnn.py -v
   ```

4. **You do visual testing:**
   - Follow guide provided by CLI
   - Use sample data
   - Take screenshots
   - Verify no errors

5. **You approve:**
   - System auto-commits with task reference
   - Progress tracking updated
   - CLAUDE.md updated with completion note
   - Next task queued

---

## 🏗️ Architecture Decisions

### Why Odoo 18 Community Edition (Not ERPNext)?

**Setup:** 5 weeks vs. 12+ weeks  
**Learning curve:** Gentle vs. Steep (proprietary Frappe framework)  
**Accounting:** Full IFRS/GAAP vs. Basic  
**Stock ledger:** Single source of truth vs. Parallel bookkeeping risk  
**POS:** Modern, native vs. Manual workflows  
**Community:** 700k+ developers vs. Smaller ecosystem  

**Trade-off:** Give up some ERPNext familiarity, gain industry-standard Odoo skills

### Custom vs. Odoo Core (Dont Reinvent the Wheel)

**Use Odoo Core:**
- `pos.order` → POS sales capture (already real-time)
- `account.move` → GL posting (standard journaling)
- `stock.move` / `stock.quant` → Inventory (industry standard)
- `hr.employee` → Employee tracking

**Custom (FMS module only):**
- `fms.shift` → Shift orchestration (no Odoo module for fuel shifts)
- `fms.meter_log` / `fms.dip_log` → Fuel-specific logs
- Residual allocation algorithm (fuel-specific business logic)
- Hard gates & validation (Shell-specific requirements)

**Rationale:** Leverage Odoo's strength in accounting/inventory; add only fuel-specific layer

### Single Shift Form (Not Multiple Models)

**Old approach (ERPNext):** 25+ DocTypes, weak relationships, manual re-entry

**New approach (Odoo):** One fms.shift with embedded child models
```
fms.shift
  ├─ meter_entry (One2Many): pump readings
  ├─ dip_entry (One2Many): tank dips
  ├─ attendant_cash (One2Many): cash reconciliation
  └─ (all editable in one unified form)
```

**Why:** Minimal data entry, no switching between models, less error-prone

---

## 🧪 Testing Strategy

### Per-Task Testing

Each task has:
- **Unit tests** (40+ total, pytest format)
- **Integration tests** (6+ total)
- **Visual testing guide** (where to test, sample data, screenshots)
- **Expected outcome** (all tests pass, no errors)

### Running Tests Locally

```bash
# Unit tests for a task
pytest tests/test_fms_001.py -v

# Coverage
pytest tests/test_fms_001.py -v --cov=models/fms_shift.py

# All tests
pytest tests/ -v --cov=models/

# Regression (after every 2-3 tasks)
pytest tests/ -v --cov=models/ --tb=short
```

### Visual Testing

After tests pass:
1. Start Odoo: `./odoo-bin -d test_fms`
2. Install FMS module
3. Create sample data (CLI provides it)
4. Verify forms load without errors
5. Check browser console (F12): No JS errors
6. Check Odoo logs: No Python errors
7. Take screenshot of working feature
8. Approve (system commits)

---

## 📊 Progress Tracking

**Files:**
- `PROGRESS.md` — Auto-updated after each task approval
- `CLAUDE.md` — This file (context & memory)
- `tasks.yaml` — Task registry (dependencies, estimates)

**Git workflow:**
```
Feature branch: fms-001-core-models
  └─ Commits per subtask with references
  └─ Tag: v0.1-core-models (after full task)
  └─ Merge to main (after approval)
```

**Commit format:**
```
feat(models): implement fms.shift, fms_pump, fms_logs

Ref: Spec Section 8.1
Task: FMS-001
Tests: 12/12 passing
Time: 2h 34m
```

---

## 🔑 Key Constraints & Rules

### Rule 1: No Parallel Bookkeeping
- All FMS data must post directly to Odoo GL
- No separate "FMS cash" vs. "GL cash"
- Stock ledger is single source of truth

### Rule 2: Immutable Logs
- After shift closes, meter/dip logs are locked
- `write()` and `unlink()` raise ValidationError
- Audit trail is tamper-proof (EPRA compliance)

### Rule 3: Opening Readings Auto-Fetch
- New shift opening values come from previous shift's closing logs
- No re-entry of last shift's closing readings
- Reduces human error

### Rule 4: Residuals Always Allocated
- No "unaccounted for" category
- Every KES assigned to a product
- May be negative (over-reported) or positive (under-reported)

### Rule 5: Hard Gates Are Non-Negotiable
- FC Cash must = 0 exactly
- No "close anyway" or "acknowledge risk" buttons
- Supervisor must fix before shift closes

---

## 🎓 Learning Resources

### Core Documentation
- `FMS_Complete_Specification_Technical_Guide.md` — Complete spec (14 sections)
- `Odoo18_Forecourt_Implementation_Roadmap.md` — Roadmap (Phases 1-2)
- This file (`CLAUDE.md`) — Context & memory

### Odoo 18 Docs
- https://www.odoo.com/documentation/18.0/
- Models: https://www.odoo.com/documentation/18.0/developer/reference/orm.html
- Views: https://www.odoo.com/documentation/18.0/developer/reference/frontend/xml_framework.html
- Testing: https://www.odoo.com/documentation/18.0/developer/reference/backend/testing.html

### Specific Topics
- Stock module: Field `stock.move`, `stock.quant`
- Accounting module: `account.move`, `account.journal`
- POS module: `pos.order`, `pos.session`

---

## 👥 Development Team

- **Developer:** You (solo dev using Claude Code)
- **AI Assistant:** Claude (code generation + prompting)
- **System:** Python CLI orchestrator (task management, testing guides)

---

## 📈 Success Criteria (Phase 1 MVP)

- [ ] All 8 tasks completed
- [ ] All 42 tests passing (80%+ coverage)
- [ ] All 5 UAT scenarios passing
- [ ] Shift close workflow working end-to-end (5 min close time)
- [ ] Hard gates enforced (no overrides)
- [ ] GL accurate (sales journaled, stock adjusted)
- [ ] Mobile responsive
- [ ] Documentation complete (RUNBOOK.md, INSTALLATION.md)
- [ ] Ready for production deployment

---

## 📅 Timeline Estimate

- **Week 1:** FMS-001 through FMS-003 (Core models + residuals) — 8h
- **Week 2:** FMS-004 through FMS-006 (Security + GL + lifecycle) — 5h
- **Week 3:** FMS-007 through FMS-008 (UI + testing + go-live) — 5h
- **Buffer:** 2h for fixes, adjustments

**Total:** ~16 hours development + testing

---

## 🚀 Next Steps

1. Review this file (context & memory)
2. Run: `python dev-guide.py status` (show progress)
3. Run: `python dev-guide.py task FMS-001` (start first task)
4. Follow Claude Code prompt (code generation)
5. Run tests locally
6. Do visual testing (follow guide)
7. Approve (system commits)
8. Proceed to FMS-002

---

## 📝 Notes & Learnings

*(This section will auto-populate as development progresses)*

### Task FMS-001: Core Models
- *(To be filled in after completion)*

### Task FMS-002: Child Models & Forms
- *(To be filled in after completion)*

*(Continue for all tasks...)*

---

**Last Updated:** 2026-08-04 14:00  
**Status:** Ready to begin development  
**Next Action:** Run `python dev-guide.py task FMS-001`
