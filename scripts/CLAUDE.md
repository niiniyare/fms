# FMS (Forecourt Management System) Development Memory

**Project:** Forecourt Management System for Odoo 18  
**Status:** In Development  
**Started:** 2026-08-04 15:56  
**Team:** Solo Developer + Claude Code

## Context Summary

FMS is a lightweight, operational fuel station management module for Odoo 18. It solves shift-based fuel reconciliation: reconciling what pump meters say was sold against what actually arrived at the tank, and where the money went.

**Reference:** Complete specification in `FMS_Complete_Specification_Technical_Guide.md`

---

## Development System

This project uses a **sequential task-based development system** with:
- Python CLI orchestrator (`dev-guide.py`)
- YAML task registry (`tasks.yaml`)
- Automated testing & git integration
- Progress persistence
- Claude Skills integration

### Key Commands

```bash
# Show current status
$ python dev-guide.py status

# Start next task
$ python dev-guide.py task FMS-001

# List all tasks
$ python dev-guide.py list

# Show detailed task info
$ python dev-guide.py info FMS-001

# Rollback last task
$ python dev-guide.py rollback

# Generate progress report
$ python dev-guide.py report
```

---

## Architecture Decisions

### Why Odoo 18 Community Edition?

1. **Setup Time:** 5 weeks vs. 12+ weeks for ERPNext
2. **Learning Curve:** Gentle (industry standard) vs. Steep (Frappe)
3. **Accounting:** Full IFRS/GAAP support
4. **Stock Ledger:** Single source of truth (not parallel bookkeeping)
5. **POS Integration:** Modern, native, real-time
6. **Community:** 700k+ developers vs. smaller ERPNext community

### Custom vs. Odoo Core

**Use Odoo Core:**
- `pos.order` (POS sales capture)
- `account.move` (GL posting)
- `stock.move` / `stock.quant` (inventory)
- `hr.employee` (employee tracking)

**Custom (FMS Module):**
- `fms.shift` (shift orchestration)
- `fms.meter_log` / `fms.dip_log` (fuel-specific logs)
- Residual allocation algorithm
- Hard gates & validation logic

**Why?** No fuel-specific shift module in Odoo core. Everything else leverages existing.

---

## Core Algorithm: Residual Allocation

**Problem:** Attendants lump non-fuel sales into fuel categories (carwash in Diesel)  
**Solution:** Automatic detection & reallocation

**Example:**
```
Meter says:     Diesel 1000L  (at 222.80 = 222,800 KES)
Attendant reports: Diesel MPesa 250,000 KES

Discrepancy: 250k - 222.8k = 27,200 KES extra
→ System allocates: "This 27,200 KES is actually carwash, not Diesel"
→ Journal entry: DR Diesel COGS | CR Carwash COGS (27,200)
→ Result: Inventory & GL accurate

Reference:** Spec Section 7.1
```

---

## Key Constraints (Hard Gates)

**These CANNOT be overridden:**

1. **FC Cash = 0 (exactly)**
   - Every KES must be accounted for
   - If +/- variance, supervisor posts correction entry
   - Only then shift closes

2. **All Attendants Clear**
   - Each person's (Sales + Receipts) = (Cash + AR + Card + Expenses)
   - No "close shift anyway" button
   - Supervisor must find discrepancy

3. **Stock Variance < Meniscus**
   - Default: ±0.5% per tank
   - Example: If tank closed 10,000L, variance max ±50L
   - If exceeded, supervisor investigates or posts adjustment

---

## Data Model Overview

### Core Models

- `fms.shift` — Main shift orchestration (state machine, validation, posting)
- `fms.pump` — Fuel pump definitions (pump1, pump2, etc.)
- `fms.pump.nozzle` — Nozzles per pump (e.g., Pump1-A/B, Pump2-A)
- `fms.meter_log` — Immutable meter reading audit trail
- `fms.dip_log` — Immutable dip reading audit trail

### Child Models (Entry Forms)

- `fms.shift.meter.entry` — Meter entry (one2many on shift)
- `fms.shift.dip.entry` — Dip entry (one2many on shift)
- `fms.shift.attendant.cash` — Per-attendant cash reconciliation
- `fms.shift.product.sales` — Computed product sales summary
- `fms.shift.residual.allocation` — Auto-calculated allocations

### Extensions

- `stock.location` extended with `fms_is_fuel_tank`, `fms_fuel_product_id`
- `product.product` extended with `fms_is_fuel`, `fms_cogs_account_id`, `fms_revenue_account_id`
- `hr.employee` extended with `fms_is_attendant`, `fms_pumps_assigned`

---

## Task Ordering & Dependencies

```
FMS-001 (Models)
  ├→ FMS-002 (Entry forms)
  ├→ FMS-003 (Residuals)
  └→ FMS-004 (Security)
      └→ FMS-005 (GL Posting)
          ├→ FMS-006 (Lifecycle)
          └→ FMS-007 (UI/Forms)
              └→ FMS-008 (Testing & Go-Live)
```

**Critical path:** 001 → 002 → 003 → 005 → 007 → 008 (est. 14 hours)

---

## Testing Strategy

### Unit Tests
- Model creation, constraints, computed fields
- Run: `pytest tests/ -v`
- Expected: 40+ tests, all passing

### Integration Tests
- Shift workflow end-to-end
- Run: `pytest tests/test_shift_workflow.py -v`
- Expected: 6+ tests, all passing

### Visual Tests (Per-Task)
- Each task includes "where to test" instructions
- Sample data auto-generated or provided
- Screenshots required for approval

### Regression Tests
- After every 2–3 tasks
- Run: `pytest tests/ --cov=models/ -v`
- Expected: 85%+ coverage, all passing

---

## Git Workflow

### Branch Strategy

```bash
# Create branch per task
git checkout -b fms-001-core-models

# Commit per sub-task
git commit -m "feat(models): implement fms.shift
  
Ref: Spec Section 8.1
Task: FMS-001-A
Tests: 4/4 passing"

# After all sub-tasks complete & approved
git tag v0.1-core-models
git checkout main
git merge fms-001-core-models
```

### Commit Message Format

```
[type](scope): [brief description]

[Longer explanation]

Ref: Spec [Section X.Y]
Task: [FMS-NNN-X]
Tests: [N/N passing]
Time: [1h 30m]
```

---

## Progress Tracking

**Live Progress File:** `PROGRESS.md` (auto-updated)

**Summary:**
- Total Tasks: 8
- Completed: 0
- In Progress: 0
- Remaining: 8
- Elapsed: 0h
- Estimated: ~16h

---

## Resources

- **Spec:** `FMS_Complete_Specification_Technical_Guide.md` (14 sections, 5000+ lines)
- **UI Mockups:** `new_ui_page-0001.jpg` (original Shell Maanzoni design reference)
- **Roadmap:** `Odoo18_Forecourt_Implementation_Roadmap.md`

---


### FMS-001: IN_PROGRESS
- Updated: 2026-08-04 15:56
- Notes: Started at 15:56


### FMS-001: IN_PROGRESS
- Updated: 2026-08-04 16:03
- Notes: Started at 16:03

## Next Steps

1. Start FMS-001: Core Models
2. Follow testing instructions (sample data provided)
3. Visual test before approval
4. Commit & proceed to FMS-002

---

**Last Updated:** 2026-08-04 15:56  
**Status:** Ready to begin development
