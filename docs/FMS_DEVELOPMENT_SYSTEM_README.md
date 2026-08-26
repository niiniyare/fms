# FMS Development System — Python CLI Orchestrator

**Complete development guide for Forecourt Management System (FMS) on Odoo 18**

This system combines:
- **Python CLI** (`dev-guide.py`) — Task orchestration, progress tracking, prompt generation
- **Memory System** (`CLAUDE.md`) — Context persistence across sessions
- **Claude Skills** (`fms-development.skill`) — Coding patterns & best practices
- **Task Registry** (`tasks.yaml`) — 8 sequential tasks with dependencies
- **Testing Guides** — Per-task with sample data & where to test

---

## Quick Start (3 minutes)

### 1. Check Prerequisites
```bash
# Ensure you're in the FMS project root
ls -la
# Should see: dev-guide.py, CLAUDE.md, tasks.yaml, fms-development.skill
```

### 2. Show Current Status
```bash
python dev-guide.py status
```

**Output:**
```
======================================================================
FMS Development Status
======================================================================

Overall Progress: ░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 0% (0/8)
  ✅ Completed:    0
  🔄 In Progress:  0
  ⏳ To Do:        8

Task Breakdown:
  ⏳ FMS-001: Core Models & Schema                  (3h)
  ⏳ FMS-002: Child Models & Entry Forms           (2h 30m)
  ⏳ FMS-003: Residual Allocation Algorithm        (2h)
  ⏳ FMS-004: Security & Access Control            (1h 30m)
  ⏳ FMS-005: Journal Entry Posting & GL Integration (2h)
  ⏳ FMS-006: Shift Lifecycle & Hard Gates         (1h 30m)
  ⏳ FMS-007: UI/UX Forms & Reports                (3h)
  ⏳ FMS-008: Testing, Documentation & Go-Live    (2h)
```

### 3. Start First Task
```bash
python dev-guide.py task FMS-001
```

**Output shows:**
- Task description & reference (Spec Section 8.1)
- All 4 subtasks
- Expected artifacts
- Comprehensive Claude Code prompt (copy this)
- Testing guide with sample data
- Where to test & what to verify

### 4. Copy Prompt to Claude Code
```
/claude dev-guide.py [paste the FMS-001 prompt here]
```

### 5. Claude Generates Code
Claude Code will:
1. Generate `models/fms_shift.py` with full model definition
2. Generate `models/fms_pump.py` with pump/nozzle masters
3. Generate `tests/test_fms_shift.py` with 12+ unit tests
4. Show test commands to run

### 6. Run Tests Locally
```bash
pytest tests/test_fms_shift.py -v
```

Expected: **12/12 passing**

### 7. Visual Testing
Follow the testing guide provided by CLI:
1. Start Odoo: `make run`
2. Open http://localhost:8070
3. Create sample data (provided in guide)
4. Take screenshot of working form
5. Verify no errors in console (F12)

### 8. Approve Task
When all tests pass + visual testing OK:
```bash
# System auto-commits with reference
# (In real implementation: approve button in CLI)

git status  # Should show committed FMS-001 changes
```

### 9. Start Next Task
```bash
python dev-guide.py task FMS-002
```

---

## System Files Overview

### `dev-guide.py` — Main Orchestrator (500+ lines)
**Purpose:** Manage task workflow, generate prompts, track progress

**Commands:**
- `status` — Show progress (completed/in-progress/todo)
- `task [ID]` — Start specific task (shows prompt + testing guide)
- `list` — List all 8 tasks with titles
- `info [ID]` — Show detailed task info
- `report` — Generate progress report (REPORT.md)

**What it does:**
1. ✅ Checks task prerequisites (blocks FMS-002 until FMS-001 done)
2. ✅ Generates comprehensive Claude Code prompt (subtask-by-subtask)
3. ✅ Shows testing guide (sample data + where to test + expected outcome)
4. ✅ Tracks progress in JSON (PROGRESS.md)
5. ✅ Updates memory (CLAUDE.md) with task completion notes

### `CLAUDE.md` — Memory System (2000+ lines)
**Purpose:** Context persistence across development sessions

**Includes:**
- Project summary & problem statement
- Core concepts (residual allocation, hard gates, data model)
- Architecture decisions (why Odoo, why custom FMS module)
- Task ordering & dependencies
- Testing strategy
- Git workflow
- Resources & references
- Progress log (auto-updated per task)

**Usage:**
- Claude reads this at start of session
- System updates it after each task completion
- Acts as institutional knowledge base

### `fms-development.skill` — Claude Skill (600+ lines)
**Purpose:** Reusable coding patterns & best practices

**Contains:**
- Pattern 1: Immutable log models (write/unlink override)
- Pattern 2: Hard gate constraints (FC Cash, stock variance)
- Pattern 3: Computed fields (reconciliation, balance)
- Pattern 4: Residual allocation algorithm (greedy matching)
- Pattern 5: Journal entry posting (GL integration)
- Pattern 6: Opening readings auto-fetch (minimize entry)
- Pattern 7: Unit testing (pytest patterns)
- Pattern 8: Form design (minimal entry UI)
- Best practices summary (10 items)

**Usage:**
- Claude references this when generating code
- Ensures consistency across all models
- Examples ready to copy-paste

### `tasks.yaml` — Task Registry (500+ lines)
**Purpose:** Central registry of all 8 tasks with metadata

**Contains per task:**
- Title, description, reference (spec section)
- Status, estimated time, actual time
- Dependencies (blocks on others)
- Subtasks (4-6 per task)
- Expected artifacts (models, tests, views, docs)
- Testing guide reference
- Git commit message template
- Total lines of code

**Usage:**
- CLI reads this to validate dependencies
- Generates prompts from task definitions
- Tracks progress (status updates)

### Test Guides (Built-in)
**8 comprehensive testing guides** (1 per task), including:
- Unit test list (what to test)
- Sample data (realistic test scenarios)
- Where to test (Odoo steps: Settings → Apps → Create)
- Expected outcome (all tests pass, no errors)
- Screenshots for approval

**Example (FMS-001):**
```
1. Start Odoo: make run  (http://localhost:8070)
2. Install FMS module
3. Create sample data:
   - Pumps: UX5, UX6, DX5
   - Nozzles: Pump1-A, Pump1-B
   - Shift: Date=Today, Supervisor=John
4. Verify forms load without errors
5. Test immutability (try to edit meter_log, should error)
6. Screenshot: Show shift form
7. Tests passing:
   ✅ 12/12 tests passing
   ✅ No JS errors (F12)
   ✅ No DB errors
```

---

## Workflow (Per Task)

```
┌─────────────────────────────────────────────────────────┐
│ Step 1: Show Status                                     │
│ $ python dev-guide.py status                            │
└────────┬────────────────────────────────────────────────┘

         │
         ↓

┌─────────────────────────────────────────────────────────┐
│ Step 2: Start Next Task                                 │
│ $ python dev-guide.py task FMS-001                      │
│                                                          │
│ Output:                                                 │
│ - Task description & spec reference                     │
│ - 4 subtasks (FMS-001-A through FMS-001-D)             │
│ - Comprehensive Claude Code prompt (copy this)          │
│ - Testing guide (where to test, sample data)           │
└────────┬────────────────────────────────────────────────┘

         │
         ↓

┌─────────────────────────────────────────────────────────┐
│ Step 3: Use Claude Code CLI                             │
│ /claude dev-guide.py [paste FMS-001 prompt]            │
│                                                          │
│ Claude generates:                                       │
│ - models/fms_shift.py (620 lines)                      │
│ - models/fms_pump.py (60 lines)                        │
│ - models/fms_logs.py (160 lines)                       │
│ - tests/test_fms_shift.py (150 lines)                  │
│ - Tests: 12 unit tests                                 │
└────────┬────────────────────────────────────────────────┘

         │
         ↓

┌─────────────────────────────────────────────────────────┐
│ Step 4: Run Unit Tests                                  │
│ $ pytest tests/test_fms_shift.py -v                    │
│                                                          │
│ Expected output:                                        │
│ ✅ 12/12 passing                                       │
│ 📊 Coverage: 90%+                                      │
│ ⏱️ Duration: <5s                                       │
└────────┬────────────────────────────────────────────────┘

         │
         ↓

┌─────────────────────────────────────────────────────────┐
│ Step 5: Visual Testing (Follow Guide)                   │
│                                                          │
│ 1. Start Odoo: make run  (http://localhost:8070)                  │
│ 2. Install module: Settings → Apps → FMS               │
│ 3. Create sample data (provided in guide)              │
│ 4. Verify forms load, no errors                        │
│ 5. Take screenshot of working feature                  │
│ 6. Screenshot for approval                             │
│                                                          │
│ Expected: No errors in browser console (F12)          │
│ Expected: No errors in Odoo logs                       │
│ Expected: Forms render correctly                       │
└────────┬────────────────────────────────────────────────┘

         │
         ↓

┌─────────────────────────────────────────────────────────┐
│ Step 6: Approve Task                                    │
│                                                          │
│ ✅ All unit tests passing                              │
│ ✅ Visual test passed (screenshot)                     │
│ ✅ No errors in logs                                   │
│                                                          │
│ System auto-commits:                                   │
│ $ git commit -m "feat(models): implement core FMS..."  │
│   + Reference: Spec Section 8.1                        │
│   + Task: FMS-001                                      │
│   + Tests: 12/12 passing                               │
│   + Time: 2h 34m                                       │
└────────┬────────────────────────────────────────────────┘

         │
         ↓

┌─────────────────────────────────────────────────────────┐
│ Step 7: Progress Updates                                │
│                                                          │
│ PROGRESS.md auto-updated:                              │
│ ✅ FMS-001: APPROVED (commit: abc123d)                 │
│                                                          │
│ CLAUDE.md updated:                                      │
│ ### FMS-001: Core Models                               │
│ - Status: APPROVED                                     │
│ - Time: 2h 34m (14% faster than estimate!)             │
│ - Notes: Models created, tests passing, all good       │
└────────┬────────────────────────────────────────────────┘

         │
         ↓

┌─────────────────────────────────────────────────────────┐
│ Step 8: Start Next Task                                 │
│ $ python dev-guide.py task FMS-002                     │
│                                                          │
│ (Repeats cycle)                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Sample Data (Per Task)

Each task's testing guide includes realistic sample data.

**Example: FMS-001 Sample Data**

```python
# Pumps to create
[
    {"name": "UX5", "order": 1},
    {"name": "UX6", "order": 2},
    {"name": "DX5", "order": 3},
    {"name": "DX6", "order": 4},
    {"name": "VP1", "order": 5},
]

# Nozzles to create
[
    {"pump": "UX5", "letter": "A", "product": "V-Power"},
    {"pump": "UX5", "letter": "B", "product": "Unleaded"},
    {"pump": "UX6", "letter": "A", "product": "Diesel"},
]

# Shift to create
{
    "date": "2026-01-15",
    "shift_label": "1_day",
    "supervisor": "John Supervisor"
}
```

**Example: FMS-003 Sample Data (Residual Test)**

```python
# Simulate lumped non-fuel sales
{
    "meters": {
        "Diesel": {"volume": 1000, "rate": 222.80},  # Meter says 1000L
        "Unleaded": {"volume": 500, "rate": 214.00},
    },
    "reported": {
        "Diesel": {"invoiced": 400, "card": 600},  # Reports 1000L
        "Unleaded": {"invoiced": 50, "card": 400},  # Reports 450L (under by 50)
        "Carwash": {"invoiced": 0, "card": 0},      # Reports 0 (should be 100)
    }
}

# Expected allocation:
# Diesel -100L (over-reported) → Carwash +100L (under-reported)
# Journal: DR Diesel COGS 22,280 | CR Carwash COGS 22,280
```

---

## Git Workflow

### Per Task Commits
```bash
# Branch per task
git checkout -b fms-001-core-models

# Subtask commits (optional, but recommended)
git commit -m "feat(models): implement fms.shift model

- Ref: Spec Section 8.1
- Task: FMS-001-A
- Lines: 620
- Tests: 4/4 passing"

# After all subtasks complete
git tag v0.1-core-models
git checkout main
git merge fms-001-core-models
```

### Commit Message Format
```
[type](scope): [brief title]

[Longer explanation]

Ref: Spec [Section X.Y]
Task: [FMS-NNN]
Tests: [N/N passing]
Lines: [N]
Time: [X hours]
```

---

## Testing Strategy (Overview)

### Unit Tests (Per Task)
- Run: `pytest tests/test_fms_nnn.py -v`
- Expected: 40+ tests total, all passing
- Coverage: 80%+

### Visual Tests (Per Task)
- Follow guide provided by CLI
- Create sample data
- Verify forms load without errors
- Take screenshot
- Approve before commit

### Regression Tests (After Every 2-3 Tasks)
- Run: `pytest tests/ -v --cov=models/`
- Expected: All tests passing, no new breakage
- Takes <10s

### UAT Tests (FMS-008)
- 5 scenarios: normal close, lumped sales, cash overage, stock variance, attendant discrepancy
- Manual testing
- Supervisor sign-off

---

## Project Structure

```
fms/                              (Odoo module root)
├── __init__.py                   (module init)
├── __manifest__.py               (Odoo metadata)
│
├── models/                       (Python models)
│   ├── __init__.py
│   ├── fms_shift.py              (FMS-001, FMS-006, FMS-005)
│   ├── fms_pump.py               (FMS-001)
│   ├── fms_logs.py               (FMS-001)
│   ├── fms_shift_entry.py        (FMS-002)
│   └── fms_shift_reconciliation.py (FMS-002, FMS-003)
│
├── views/                        (XML form layouts)
│   ├── fms_shift_views.xml       (FMS-002, FMS-007)
│   ├── fms_shift_meter_views.xml (FMS-007)
│   ├── fms_shift_dip_views.xml   (FMS-007)
│   └── fms_shift_list_views.xml  (FMS-007)
│
├── security/                     (Access control)
│   ├── fms_groups.xml            (FMS-004)
│   ├── ir_model_access.xml       (FMS-004)
│   └── ir_rule.xml               (FMS-004)
│
├── reports/                      (PDF templates)
│   ├── fms_shift_reconciliation_report.xml (FMS-007)
│   └── fms_shift_reconciliation_template.xml (FMS-007)
│
├── static/                       (CSS/JS)
│   └── src/css/fms_responsive.css (FMS-007)
│
├── tests/                        (Pytest tests)
│   ├── test_fms_shift.py         (FMS-001)
│   ├── test_fms_logs.py          (FMS-001)
│   ├── test_fms_shift_entry.py   (FMS-002)
│   ├── test_residual_allocation.py (FMS-003)
│   ├── test_security.py          (FMS-004)
│   ├── test_journal_posting.py   (FMS-005)
│   ├── test_shift_lifecycle.py   (FMS-006)
│   └── test_integration_full_workflow.py (FMS-008)
│
├── scripts/                      (Utilities)
│   └── import_sample_data.py     (FMS-008)
│
└── docs/                         (Documentation)
    ├── INSTALLATION.md           (FMS-008)
    ├── runbook/                  (operational runbook, 11 sections)
    ├── training/                 (training guides — setup, ops, finance)
    └── UAT_CHECKLIST.md          (FMS-008)
```

---

## Timeline Estimate

| Phase | Tasks | Time | Focus |
|-------|-------|------|-------|
| **Week 1** | FMS-001, 002, 003 | 8h | Core models, entry, residuals |
| **Week 2** | FMS-004, 005, 006 | 5h | Security, GL, lifecycle |
| **Week 3** | FMS-007, 008 | 5h | UI, testing, go-live |
| **Buffer** | Fixes/surprises | 2h | Adjustments |
| **TOTAL** | 8 tasks | **~16h** | Phase 1 MVP |

---

## Key Features of This System

✅ **Sequential:** Tasks ordered by dependency (can't start FMS-002 until FMS-001 done)  
✅ **Testable:** Every task has unit tests + visual testing guide + sample data  
✅ **Trackable:** Progress persisted (PROGRESS.md, CLAUDE.md, git history)  
✅ **Repeatable:** Patterns & skills for consistent code quality  
✅ **Documented:** Comprehensive spec, skills, memory, testing guides  
✅ **Automated:** CLI generates prompts, tracks progress, updates memory  
✅ **Auditable:** Git commits with task refs, spec sections, test counts  
✅ **Scalable:** Easy to add Phase 2 tasks (PTS-2, amendments, etc.)  

---

## Next Steps

### 1. Review This System
- Read this file (you're doing it!)
- Skim CLAUDE.md (context & project memory)
- Quick look at fms-development.skill (coding patterns)
- Read tasks.yaml (task definitions)

### 2. Show Status
```bash
make status
```

### 3. Start FMS-001
```bash
make task TASK=FMS-001
```

### 4. Copy Prompt to Claude Code
```bash
/claude dev-guide.py [paste FMS-001 prompt]
```

### 5. Follow the Testing Guide
Tests run locally, visual test in Odoo, approve, commit, move on.

---

## Troubleshooting

### "Task FMS-002 not available yet"
**Issue:** Trying to start FMS-002 before FMS-001 is approved  
**Solution:** Complete FMS-001 first (dependency check in CLI)

### "Tests passing but visual testing shows blank form"
**Issue:** Models created but views not linked  
**Solution:** Check __manifest__.py includes views (auto-added by Claude)

### "Cannot post journal entry"
**Issue:** GL accounts not configured  
**Solution:** Set up GL accounts in Odoo (Accounting → Chart of Accounts)

### "Shift won't close — 'FC Cash not zero'"
**Feature, not bug!** Hard gate is working.  
**Solution:** Follow guide — supervisor posts adjustment entry

---

## Resources

- **Complete Spec:** `FMS_Complete_Specification_Technical_Guide.md` (14 sections)
- **This System:** `FMS_DEVELOPMENT_SYSTEM_README.md` (you are here)
- **Memory:** `CLAUDE.md` (context & progress)
- **Skills:** `fms-development.skill` (coding patterns)
- **Tasks:** `tasks.yaml` (task registry)
- **Progress:** `PROGRESS.md` (auto-updated per task)
- **CLI:** `dev-guide.py` (orchestrator)

---

**Ready to build? Run: `make task TASK=FMS-001`**
