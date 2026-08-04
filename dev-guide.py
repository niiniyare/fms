#!/usr/bin/env python3
"""
FMS (Forecourt Management System) Development Guide Orchestrator

Manages sequential development tasks with:
- Dependency tracking
- Git integration
- Progress persistence
- Testing automation
- Prompt generation
"""

import os
import sys
import json
import subprocess
import yaml
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import click
from enum import Enum


# ═════════════════════════════════════════════════════════════════════
# Configuration & Setup
# ═════════════════════════════════════════════════════════════════════

FMS_ROOT = Path(__file__).parent
TASKS_FILE = FMS_ROOT / "tasks.yaml"
PROGRESS_FILE = FMS_ROOT / "PROGRESS.md"
CLAUDE_MEMORY = FMS_ROOT / "CLAUDE.md"
SCRIPTS_DIR = FMS_ROOT / "scripts"
PROMPTS_DIR = SCRIPTS_DIR / "prompts"
HOOKS_DIR = SCRIPTS_DIR / "hooks"
TESTS_DIR = FMS_ROOT / "tests"
MODELS_DIR = FMS_ROOT / "models"
VIEWS_DIR = FMS_ROOT / "views"
SECURITY_DIR = FMS_ROOT / "security"


class TaskStatus(Enum):
    """Task lifecycle states"""
    TODO = "⏳"
    IN_PROGRESS = "🔄"
    TESTING = "🧪"
    APPROVED = "✅"
    FAILED = "❌"
    BLOCKED = "🚫"


@dataclass
class TaskMetadata:
    """Metadata for a development task"""
    id: str
    title: str
    description: str
    status: TaskStatus = TaskStatus.TODO
    spec_reference: str = ""
    estimated_time: str = "0h"
    actual_time: str = "0h"
    subtasks: List[str] = None
    dependencies: List[str] = None
    artifacts: Dict[str, List[str]] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    commit_hash: Optional[str] = None
    notes: str = ""
    
    def __post_init__(self):
        if self.subtasks is None:
            self.subtasks = []
        if self.dependencies is None:
            self.dependencies = []
        if self.artifacts is None:
            self.artifacts = {}


# ═════════════════════════════════════════════════════════════════════
# Task Registry
# ═════════════════════════════════════════════════════════════════════

TASKS: Dict[str, TaskMetadata] = {
    "FMS-001": TaskMetadata(
        id="FMS-001",
        title="Core Models & Schema",
        description="Implement base FMS models: fms.shift, fms.meter_log, fms.dip_log, fms.pump, fms.pump_nozzle",
        spec_reference="Spec Section 8.1",
        estimated_time="3h",
        subtasks=[
            "FMS-001-A: fms.shift model (620 lines)",
            "FMS-001-B: fms.meter_log & fms.dip_log (immutable logs)",
            "FMS-001-C: fms.pump & fms.pump_nozzle master data",
            "FMS-001-D: Unit tests (12+ tests)",
        ],
        artifacts={
            "models": [
                "models/__init__.py",
                "models/fms_shift.py",
                "models/fms_pump.py",
                "models/fms_logs.py",
            ],
            "tests": [
                "tests/test_fms_shift.py",
                "tests/test_fms_logs.py",
            ]
        }
    ),
    
    "FMS-002": TaskMetadata(
        id="FMS-002",
        title="Child Models & Entry Forms",
        description="Implement shift entry models: meter.entry, dip.entry, attendant.cash, product.sales",
        spec_reference="Spec Section 8.1",
        estimated_time="2h 30m",
        dependencies=["FMS-001"],
        subtasks=[
            "FMS-002-A: fms.shift.meter.entry & fms.shift.dip.entry",
            "FMS-002-B: fms.shift.attendant.cash reconciliation model",
            "FMS-002-C: fms.shift.product.sales (computed)",
            "FMS-002-D: Basic forms & list views",
            "FMS-002-E: Tests (8+ tests)",
        ],
        artifacts={
            "models": [
                "models/fms_shift_entry.py",
                "models/fms_shift_reconciliation.py",
            ],
            "views": [
                "views/fms_shift_views.xml",
                "views/fms_shift_meter_views.xml",
                "views/fms_shift_dip_views.xml",
            ],
            "tests": [
                "tests/test_fms_shift_entry.py",
            ]
        }
    ),
    
    "FMS-003": TaskMetadata(
        id="FMS-003",
        title="Residual Allocation Algorithm",
        description="Implement automatic residual allocation (over-reported → under-reported product reallocation)",
        spec_reference="Spec Section 7.1",
        estimated_time="2h",
        dependencies=["FMS-001", "FMS-002"],
        subtasks=[
            "FMS-003-A: Product sales reconciliation computation",
            "FMS-003-B: Residual detection & calculation",
            "FMS-003-C: Greedy allocation algorithm",
            "FMS-003-D: Unit tests (6+ tests)",
        ],
        artifacts={
            "models": [
                "models/fms_shift_reconciliation.py (method: _calculate_residuals)",
            ],
            "tests": [
                "tests/test_residual_allocation.py",
            ]
        }
    ),
    
    "FMS-004": TaskMetadata(
        id="FMS-004",
        title="Security & Access Control",
        description="Implement role-based groups, row-level security, immutable log protection",
        spec_reference="Spec Section 9",
        estimated_time="1h 30m",
        dependencies=["FMS-001"],
        subtasks=[
            "FMS-004-A: Define groups (attendant, supervisor, accountant)",
            "FMS-004-B: Model-level access rules (ir.model.access)",
            "FMS-004-C: Row-level security (company scoping)",
            "FMS-004-D: Log immutability enforcement",
            "FMS-004-E: Tests (5+ tests)",
        ],
        artifacts={
            "security": [
                "security/ir_model_access.xml",
                "security/ir_rule.xml",
            ],
            "tests": [
                "tests/test_security.py",
            ]
        }
    ),
    
    "FMS-005": TaskMetadata(
        id="FMS-005",
        title="Journal Entry Posting & GL Integration",
        description="Implement automatic GL posting: sales journals, residual allocation journals, cash variance journals",
        spec_reference="Spec Section 7.2-7.3, Section 8.1",
        estimated_time="2h",
        dependencies=["FMS-003", "FMS-004"],
        subtasks=[
            "FMS-005-A: Sales journal posting (_post_sales_journal)",
            "FMS-005-B: Residual allocation journal (_post_residual_allocation_journal)",
            "FMS-005-C: Cash variance posting (_post_cash_variance_journal)",
            "FMS-005-D: Stock inventory adjustments (_post_inventory_adjustments)",
            "FMS-005-E: Tests (8+ tests)",
        ],
        artifacts={
            "models": [
                "models/fms_shift.py (posting methods)",
            ],
            "tests": [
                "tests/test_journal_posting.py",
            ]
        }
    ),
    
    "FMS-006": TaskMetadata(
        id="FMS-006",
        title="Shift Lifecycle & Hard Gates",
        description="Implement shift state machine, validation gates (FC Cash=0, stock variance, attendant clear)",
        spec_reference="Spec Section 3.2, Section 8.1",
        estimated_time="1h 30m",
        dependencies=["FMS-002", "FMS-003"],
        subtasks=[
            "FMS-006-A: Shift state machine (Draft → Open → Closing → Closed)",
            "FMS-006-B: Hard gate 1: FC Cash must equal zero",
            "FMS-006-C: Hard gate 2: All attendants must clear",
            "FMS-006-D: Hard gate 3: Stock variance within meniscus",
            "FMS-006-E: Tests (6+ tests)",
        ],
        artifacts={
            "models": [
                "models/fms_shift.py (state machine & gates)",
            ],
            "tests": [
                "tests/test_shift_lifecycle.py",
            ]
        }
    ),
    
    "FMS-007": TaskMetadata(
        id="FMS-007",
        title="UI/UX Forms & Reports",
        description="Build complete shift form (unified data entry + reconciliation), shift list dashboard, PDF report",
        spec_reference="Spec Section 3.3, Section 10",
        estimated_time="3h",
        dependencies=["FMS-002", "FMS-006"],
        subtasks=[
            "FMS-007-A: Shift list view dashboard",
            "FMS-007-B: Unified shift form (6-screen workflow in one form)",
            "FMS-007-C: Collapsible sections, responsive layout",
            "FMS-007-D: Reconciliation summary (read-only computed section)",
            "FMS-007-E: Shift reconciliation PDF report",
            "FMS-007-F: Mobile responsiveness",
        ],
        artifacts={
            "views": [
                "views/fms_shift_list_views.xml",
                "views/fms_shift_form_views.xml",
                "reports/fms_shift_reconciliation_report.xml",
                "reports/fms_shift_reconciliation_template.xml",
            ]
        }
    ),
    
    "FMS-008": TaskMetadata(
        id="FMS-008",
        title="Testing, Documentation & Go-Live",
        description="Run full test suite, create runbooks, deploy to test instance, UAT checklist",
        spec_reference="Spec Section 11-13",
        estimated_time="2h",
        dependencies=["FMS-005", "FMS-007"],
        subtasks=[
            "FMS-008-A: Full test suite (regression)",
            "FMS-008-B: Create RUNBOOK.md (daily operations)",
            "FMS-008-C: Create INSTALLATION.md (setup guide)",
            "FMS-008-D: Sample data import script",
            "FMS-008-E: UAT checklist & sign-off",
        ],
        artifacts={
            "docs": [
                "RUNBOOK.md",
                "INSTALLATION.md",
                "UAT_CHECKLIST.md",
            ],
            "scripts": [
                "scripts/import_sample_data.py",
            ]
        }
    ),
}


# ═════════════════════════════════════════════════════════════════════
# Progress & Memory Management
# ═════════════════════════════════════════════════════════════════════

class ProgressTracker:
    """Manages task progress persistence"""
    
    def __init__(self, progress_file: Path = PROGRESS_FILE):
        self.file = progress_file
        self.data = self._load() or {}
    
    def _load(self) -> Optional[Dict[str, Any]]:
        """Load progress from file"""
        if self.file.exists():
            with open(self.file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save(self):
        """Persist progress to file"""
        with open(self.file, 'w') as f:
            json.dump(self.data, f, indent=2, default=str)
    
    def update_task(self, task_id: str, **kwargs):
        """Update task metadata"""
        if task_id not in self.data:
            self.data[task_id] = {}
        self.data[task_id].update(kwargs)
        self._save()
    
    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get task progress"""
        return self.data.get(task_id, {})
    
    def get_status(self) -> Dict[str, int]:
        """Get summary stats"""
        total = len(TASKS)
        completed = sum(1 for t in self.data.values() if t.get('status') == 'APPROVED')
        in_progress = sum(1 for t in self.data.values() if t.get('status') == 'IN_PROGRESS')
        todo = total - completed - in_progress
        
        return {
            'total': total,
            'completed': completed,
            'in_progress': in_progress,
            'todo': todo,
        }


class ClaudeMemory:
    """Manages CLAUDE.md context memory"""
    
    def __init__(self, memory_file: Path = CLAUDE_MEMORY):
        self.file = memory_file
        self._ensure_file()
    
    def _ensure_file(self):
        """Create CLAUDE.md if doesn't exist"""
        if not self.file.exists():
            self.file.write_text(self._template())
    
    def _template(self) -> str:
        return """# FMS (Forecourt Management System) Development Memory

**Project:** Forecourt Management System for Odoo 18  
**Status:** In Development  
**Started:** %(date)s  
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

## Next Steps

1. Start FMS-001: Core Models
2. Follow testing instructions (sample data provided)
3. Visual test before approval
4. Commit & proceed to FMS-002

---

**Last Updated:** %(date)s  
**Status:** Ready to begin development
""" % {'date': datetime.now().strftime('%Y-%m-%d %H:%M')}
    
    def update_task(self, task_id: str, status: str, notes: str = ""):
        """Update memory with task progress"""
        content = self.file.read_text()
        
        # Add entry to memory (append to task log section)
        entry = f"\n### {task_id}: {status}\n- Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        if notes:
            entry += f"- Notes: {notes}\n"
        
        # Find insertion point (after last task log)
        if "## Next Steps" in content:
            content = content.replace("## Next Steps", entry + "\n## Next Steps")
        
        self.file.write_text(content)
    
    def get_context(self) -> str:
        """Get full memory context for Claude"""
        if self.file.exists():
            return self.file.read_text()
        return "No memory context yet."


# ═════════════════════════════════════════════════════════════════════
# Testing Framework
# ═════════════════════════════════════════════════════════════════════

class TestingGuide:
    """Provides testing instructions for each task"""
    
    GUIDES = {
        "FMS-001": {
            "title": "Testing: Core Models",
            "unit_tests": [
                "Test fms.shift model creation",
                "Test fms.meter_log immutability (write raises error)",
                "Test fms.pump and fms.pump_nozzle relationships",
                "Test computed fields (if any)",
            ],
            "sample_data": {
                "pump": [
                    {"name": "UX5", "order": 1},
                    {"name": "UX6", "order": 2},
                    {"name": "DX5", "order": 3},
                ],
                "nozzle": [
                    {"pump": "UX5", "letter": "A", "product": "V-Power"},
                    {"pump": "UX5", "letter": "B", "product": "Unleaded"},
                ],
                "shift": [
                    {"date": "2026-01-15", "label": "1_day", "supervisor": "John Supervisor"},
                ]
            },
            "where_to_test": """
1. Start Odoo: ./odoo-bin -d test_fms
2. Install module: Settings → Apps → Search "FMS" → Install
3. Create sample data:
   - Settings → Pumps → Create: Name=UX5, Order=1
   - Settings → Nozzles → Create: Pump=UX5-A, Product=V-Power
4. Create test shift:
   - Forecourt → Shifts → New
   - Fill: Date=Today, Supervisor=Select
   - Save (should auto-generate name SHT/2026/01/0001)
5. Verify model creation via console:
   $ odoo shell
   >>> self.env['fms.shift'].search([])  # Should return shift
   >>> self.env['fms.pump'].search([])   # Should return pumps
6. Screenshot: Show shift form (proof models loaded)
7. Test immutability:
   - Try to edit a meter_log via admin (should raise error)
   - Verify: "Meter logs are immutable"
""",
            "expected_outcome": """
✅ All models loaded without errors
✅ Sample data created (1 shift, 3 pumps, 2 nozzles)
✅ Shift form displays without errors
✅ Immutability enforced (write raises ValidationError)
✅ Unit tests: 12/12 passing
✅ Coverage: 90%+
""",
        },
        
        "FMS-002": {
            "title": "Testing: Child Models & Forms",
            "unit_tests": [
                "Test fms.shift.meter.entry creation",
                "Test fms.shift.dip.entry creation",
                "Test attendant.cash balance computation",
                "Test form rendering (no errors)",
            ],
            "sample_data": {
                "meter_entry": [
                    {
                        "pump": "UX5",
                        "nozzle": "A",
                        "attendant": "John",
                        "opening_elec_vol": 450000,
                        "closing_elec_vol": 450500,
                    }
                ],
                "dip_entry": [
                    {
                        "tank": "T1-VPower",
                        "opening_vol": 5000,
                        "closing_vol": 4800,
                    }
                ],
                "attendant_cash": [
                    {
                        "attendant": "John",
                        "sales_amount": 5000,
                        "cash_dropped": 5000,
                    }
                ],
            },
            "where_to_test": """
1. Open existing shift: Forecourt → Shifts → SHT/2026/01/0001
2. Add meter readings:
   - Click "Add a line" under "Meter Readings"
   - Select pump UX5, nozzle A, attendant
   - Enter: Opening=450000, Closing=450500
   - Verify: Qty Sold = 500L auto-calculated
3. Add dip readings:
   - Click "Add a line" under "Dip Readings"
   - Select tank T1-VPower
   - Enter: Opening=5000, Closing=4800
   - Verify: Variance shown (negative 200L)
4. Add attendant cash:
   - Click "Add attendant" under "Cash Reconciliation"
   - Select attendant: John
   - Verify: Sales auto-populated from POS (if any)
   - Enter: Cash Dropped=5000
   - Verify: Balance = 0 (expected)
5. Screenshot: Show filled form with all sections
6. Test form validation:
   - Try entering Closing < Opening (should error)
   - Verify error message
""",
            "expected_outcome": """
✅ All entry forms render without errors
✅ Sample data entered (1 meter, 1 dip, 1 attendant)
✅ Computed fields working (qty, amount, balance)
✅ Form validation enforced
✅ No database errors in logs
✅ Unit tests: 8/8 passing
""",
        },
        
        "FMS-003": {
            "title": "Testing: Residual Allocation",
            "unit_tests": [
                "Test residual detection (over-reported product)",
                "Test allocation to under-reported product",
                "Test residual amounts calculation",
                "Test greedy allocation algorithm",
            ],
            "sample_data": {
                "scenario": "Attendant reported Diesel as carwash",
                "meters": {
                    "Diesel": {"volume": 1000, "rate": 222.80, "total": 222800},
                    "Unleaded": {"volume": 500, "rate": 214.00, "total": 107000},
                    "Carwash": {"volume": 0, "rate": 150.00, "total": 0},
                },
                "reported": {
                    "Diesel": {"invoiced": 400, "card": 600},  # Total 1000
                    "Unleaded": {"invoiced": 50, "card": 400},  # Total 450 (under by 50)
                    "Carwash": {"invoiced": 0, "card": 0},     # Zero (but 100L should be here)
                },
            },
            "where_to_test": """
1. Use same shift from FMS-002
2. Add product sales with intentional mismatch:
   - Meter: Diesel 1000L, Unleaded 500L, Carwash 100L
   - Invoices: Diesel 400L, Unleaded 50L, Carwash 0L
   - Card/MPesa: Diesel 600L, Unleaded 400L
   
   Total Meter: 1600L
   Total Reported: Diesel 1000L + Unleaded 450L + Carwash 0L = 1450L
   Residual: 150L unaccounted
   
3. Trigger reconciliation:
   - Click [VERIFY RECONCILIATION] button
   - System should show:
     * Diesel: -100L residual (over-reported)
     * Unleaded: +50L residual (under-reported)
     * Carwash: +100L residual (unaccounted)
   
4. Verify allocation:
   - System auto-calculates: Diesel -100L → Carwash +100L @ rate
   - Shows allocation in UI:
     "Diesel -100L → Carwash +100L  |  Amount: 15,000 KES"
   
5. Screenshot: Show reconciliation results before/after allocation
6. Verify no journals posted yet (only calculated)
""",
            "expected_outcome": """
✅ Residuals correctly detected
✅ Allocation algorithm matches expected output
✅ Allocation amounts calculated correctly
✅ UI shows allocation details
✅ Unit tests: 6/6 passing
✅ No journals posted (pending shift close)
""",
        },
        
        "FMS-004": {
            "title": "Testing: Security & Access Control",
            "unit_tests": [
                "Test group permissions (attendant, supervisor, accountant)",
                "Test row-level security (company scoping)",
                "Test immutability (log write/unlink blocked)",
                "Test field-level permissions",
            ],
            "sample_data": {
                "users": [
                    {"name": "John (Attendant)", "groups": ["fuel_station_attendant"]},
                    {"name": "Supervisor", "groups": ["fuel_station_supervisor"]},
                    {"name": "Accountant", "groups": ["fuel_station_accountant"]},
                ]
            },
            "where_to_test": """
1. Create test users:
   Settings → Users & Companies → Create:
   - User: "John_Attendant"
     Email: john@station.local
     Groups: Fuel Station Attendant
   - User: "Supervisor_A"
     Email: supervisor@station.local
     Groups: Fuel Station Supervisor
   - User: "Accountant_A"
     Email: accountant@station.local
     Groups: Fuel Station Accountant

2. Test Attendant permissions:
   - Login as John_Attendant
   - Forecourt → Shifts → Should see open shift ✓
   - Try to close shift → Should be blocked ✓
   - Try to edit supervisor field → Should be blocked ✓
   
3. Test Supervisor permissions:
   - Login as Supervisor_A
   - Forecourt → Shifts → Should see all shifts ✓
   - Should be able to close shift ✓
   - Should be able to post corrections ✓
   
4. Test Accountant permissions:
   - Login as Accountant_A
   - Should see reports ✓
   - Should NOT see shift entry form ✓
   - Should NOT be able to close shift ✓
   
5. Test row-level security:
   - Create second company: "Another Station"
   - Login as user assigned to first company only
   - Should NOT see shifts from second company ✓
   
6. Test immutability:
   - Close a shift (creates meter_log)
   - Try to edit meter_log record (as admin)
   - Should error: "Meter logs are immutable" ✓
   
7. Screenshot: Show access denied messages when attempting restricted actions
""",
            "expected_outcome": """
✅ Groups created and assigned
✅ Attendant: can enter data, cannot close
✅ Supervisor: can close shift, post corrections
✅ Accountant: read-only access to reports
✅ Row-level security enforced (company-based)
✅ Logs protected from editing
✅ Unit tests: 5/5 passing
""",
        },
        
        "FMS-005": {
            "title": "Testing: Journal Entry Posting",
            "unit_tests": [
                "Test sales journal posting",
                "Test residual allocation journal",
                "Test cash variance journal",
                "Test stock inventory adjustments",
                "Test journal line balancing",
            ],
            "sample_data": {
                "shift_data": {
                    "sales_total": 1445986.95,
                    "residual_allocation": 22280,
                    "fc_cash_variance": 50.50,
                    "stock_adjustments": [
                        {"tank": "T1", "dip_volume": 4800, "book_volume": 4850},
                    ]
                }
            },
            "where_to_test": """
1. Set up GL accounts (if not auto-created):
   Accounting → Accounts → Ensure exists:
   - 4100: Fuel Revenue (Income)
   - 5100: Fuel COGS (Expense)
   - 1010: FC Cash (Asset)
   - 1020: Employee Advance (Asset)
   - 8000: Miscellaneous Expense

2. Prepare shift for close:
   - Open shift from FMS-002
   - Complete all meter/dip/cash entries
   - Verify: FC Cash = 0, variances OK
   
3. Close shift:
   - Click [CLOSE SHIFT]
   - System should:
     * Post sales journal (Debit COGS, Credit Revenue)
     * Post residual allocation (if any)
     * Post cash variance (if any)
     * Create stock inventory adjustments
   
4. Verify journals in Accounting:
   Accounting → Journal Entries → Filter by date
   - JE001: Sales Entry
     Line 1: DR Fuel COGS 1,445,986.95
     Line 2: CR Fuel Revenue 1,445,986.95
     Status: Posted ✓
   
   - JE002: Residual Allocation (if applicable)
     Line 1: DR Diesel COGS 22,280
     Line 2: CR Carwash COGS 22,280
     Status: Posted ✓
   
   - JE003: Cash Variance (if FC Cash ≠ 0 before correction)
     Line 1: DR FC Cash 50.50
     Line 2: CR Miscellaneous Expense 50.50
     Status: Posted ✓

5. Verify stock adjustments:
   Inventory → Physical Inventory Counts
   - Should see count records for each tank
   - Status: Validated ✓

6. Verify GL impact:
   Accounting → GL (Trial Balance)
   - FC Cash: 0.00 (or correct amount)
   - Fuel Revenue: 1,445,986.95 ✓
   - Fuel COGS: 1,445,986.95 ✓

7. Screenshot: Show posted journal entries
""",
            "expected_outcome": """
✅ All journals posted successfully
✅ Journal line items balanced (DR = CR)
✅ Correct GL accounts used
✅ Stock adjustments created
✅ No GL errors in system log
✅ Unit tests: 8/8 passing
✅ Integration tests: 6/6 passing
""",
        },
        
        "FMS-006": {
            "title": "Testing: Shift Lifecycle & Hard Gates",
            "unit_tests": [
                "Test shift open (Draft → Open)",
                "Test shift close (Closing → Closed)",
                "Test FC Cash hard gate enforcement",
                "Test stock variance hard gate enforcement",
                "Test attendant clear hard gate enforcement",
            ],
            "sample_data": {
                "test_cases": [
                    {
                        "name": "Normal Close (No Variances)",
                        "fc_cash": 0.00,
                        "stock_variance": 0.00,
                        "attendants_clear": True,
                        "expected": "CLOSE SUCCESS",
                    },
                    {
                        "name": "FC Cash Not Zero",
                        "fc_cash": 50.00,
                        "stock_variance": 0.00,
                        "attendants_clear": True,
                        "expected": "HARD GATE BLOCKS CLOSE (FC Cash ≠ 0)",
                    },
                    {
                        "name": "Stock Variance Exceeds Meniscus",
                        "fc_cash": 0.00,
                        "stock_variance": 2.0,  # 2% > 0.5% meniscus
                        "attendants_clear": True,
                        "expected": "HARD GATE BLOCKS CLOSE (Variance > meniscus)",
                    },
                    {
                        "name": "Attendant Not Clear",
                        "fc_cash": 0.00,
                        "stock_variance": 0.00,
                        "attendants_clear": False,
                        "expected": "HARD GATE BLOCKS CLOSE (Attendant balance ≠ 0)",
                    },
                ]
            },
            "where_to_test": """
1. Test Case 1: Normal Close
   - Open shift, enter all data
   - Verify: FC Cash = 0, variances OK, attendants clear
   - Click [CLOSE SHIFT]
   - Expected: Shift closes immediately ✓
   - Verify: Status = "Closed", journals posted ✓

2. Test Case 2: FC Cash Not Zero
   - Open shift, enter data
   - Set up scenario: FC Cash = +50 KES
   - Click [CLOSE SHIFT]
   - Expected: Error dialog
     "FC Cash is +50.00 KES. Cannot close shift.
      Supervisor must post adjustment."
   - Supervisor posts: DR FC Cash 50 | CR Expense 50
   - Retry close → Success ✓

3. Test Case 3: Stock Variance Exceeds Meniscus
   - Open shift
   - Enter dip: Opening 10,000L, Closing 9,800L (2% loss > 0.5% meniscus)
   - Click [CLOSE SHIFT]
   - Expected: Error dialog
     "Tank T1: variance 2.00% exceeds meniscus 0.50%. Investigate."
   - Supervisor re-dips (gets 9,950L instead), retries
   - Close succeeds ✓

4. Test Case 4: Attendant Not Clear
   - Open shift, add attendant cash
   - Create scenario: Attendant balance = -5 KES
   - Click [CLOSE SHIFT]
   - Expected: Error dialog
     "Attendant John: balance -5.00 KES not cleared."
   - Attendant investigates, finds error, posts correction
   - Retry close → Success ✓

5. Test shift state machine:
   - New shift: Status = Draft ✓
   - Click Open: Status = Open ✓
   - Enter data
   - Shift becomes: Status = Closing (automatic) ✓
   - Close shift (if gates pass): Status = Closed ✓
   - Try to reopen closed shift: Should be blocked ✓

6. Screenshot: Show each hard gate error message
""",
            "expected_outcome": """
✅ Shift opens without errors
✅ Hard gate 1: FC Cash = 0 enforced
✅ Hard gate 2: Attendants clear enforced
✅ Hard gate 3: Stock variance enforced
✅ State machine working (Draft → Open → Closing → Closed)
✅ Reopening closed shift blocked
✅ Unit tests: 6/6 passing
""",
        },
        
        "FMS-007": {
            "title": "Testing: UI/UX Forms & Reports",
            "unit_tests": [
                "Test form rendering (no JS errors)",
                "Test mobile responsiveness (tablet/phone)",
                "Test PDF report generation",
                "Test dashboard list view",
            ],
            "sample_data": {
                "shifts": [
                    {"date": "2026-01-13", "status": "closed", "supervisor": "Jane"},
                    {"date": "2026-01-14", "status": "closed", "supervisor": "John"},
                    {"date": "2026-01-15", "status": "open", "supervisor": "Mike"},
                ]
            },
            "where_to_test": """
1. Open shift dashboard:
   - Forecourt → Shifts
   - Should see list of shifts with status indicators:
     * ✅ Closed
     * 🔄 Open
     * ⏳ Draft
   - Click on a closed shift to view reconciliation

2. Test shift form (desktop):
   - Open a closed shift
   - Verify sections are collapsible:
     * Header (always visible)
     * Opening Readings (collapsible)
     * Closing Readings (collapsible)
     * Attendant Cash (collapsible)
     * Reconciliation (collapsible, read-only)
   - Scroll through form (should not be > 3 screens)
   - All inputs accessible and readable

3. Test mobile responsiveness:
   - Open browser dev tools (F12)
   - Set to iPad (768px width)
   - Verify:
     * Form stacks vertically ✓
     * Buttons are large enough (56px) ✓
     * No horizontal scrolling ✓
   
   - Set to iPhone (375px width)
   - Verify:
     * Form still readable ✓
     * Meter entries show one pump per row ✓
     * Attendant cash section fits ✓

4. Test form interactions:
   - Open new shift form
   - Verify opening values auto-filled (from previous shift)
   - Tab through meter entry fields (should go in order)
   - Click into one meter closing field → should be focused
   - Press Tab → should move to next field
   - Enter invalid data (closing < opening) → inline error ✓

5. Test PDF report:
   - Close a shift
   - Click [PRINT SHIFT REPORT]
   - PDF should generate with:
     * Shift header (date, supervisor, station)
     * Attendant reconciliation table
     * FC Cash reconciliation
     * Stock reconciliation (tanks)
     * Product reconciliation
     * Residual allocation (if any)
     * Journal entries posted
     * All numbers formatted (1,234.56 format) ✓
   - Save PDF and verify layout (check in Adobe or browser)

6. Screenshots:
   - Desktop: Full shift form
   - Tablet (iPad): Same form
   - Mobile (iPhone): Same form
   - PDF report: First and last pages
""",
            "expected_outcome": """
✅ All forms render without errors
✅ Collapsible sections working
✅ Mobile responsive (no horizontal scroll)
✅ Touch targets large enough (56px+)
✅ PDF report generates correctly
✅ No console errors (F12)
✅ Dashboard shows all shifts with status
✅ All screenshots attached for approval
""",
        },
        
        "FMS-008": {
            "title": "Testing: Full System & Go-Live",
            "unit_tests": [
                "Run full test suite (regression)",
                "Integration test: full shift workflow",
                "UAT test scenarios",
                "Performance test (response times)",
            ],
            "sample_data": {
                "scenario": "Complete real-world shift at a fuel station",
                "details": {
                    "station": "Demo Station",
                    "shift_date": "2026-01-15",
                    "shift_label": "1_day",
                    "attendants": 4,
                    "pumps": 8,
                    "tanks": 4,
                    "expected_sales": 8135.72,
                    "expected_cash": 1445986.95,
                }
            },
            "where_to_test": """
1. Run full test suite:
   $ pytest tests/ -v --cov=models/
   
   Expected output:
   ✅ 42 tests passing
   📊 Coverage: 87%+
   ⏱️ Duration: <5s

2. End-to-end shift workflow:
   - Open shift (06:00)
   - Attendants log in, start POS sales
   - System tracks sales in real-time
   - At shift end (18:00):
     * Attendants enter closing meters (8 nozzles)
     * Attendants enter closing dips (4 tanks)
     * Attendants enter cash drops & AR
     * Supervisor reviews reconciliation
     * System auto-allocates residuals (if any)
     * Supervisor closes shift (gates pass)
     * Journals auto-post to GL
   - Time elapsed: ~5 minutes (typical shift close)

3. UAT Checklist (Test Scenarios):
   
   ✓ Scenario A: No Variances
     - All meters match, all dips match, all cash matches
     - Expected: Shift closes immediately
   
   ✓ Scenario B: Lumped Non-Fuel Sales
     - MPesa reported as Diesel but includes carwash
     - Expected: System detects & allocates residual
     - Journal posts: DR Diesel COGS | CR Carwash COGS
   
   ✓ Scenario C: Cash Overage
     - FC Cash = +200 KES after attendant drops
     - Expected: Hard gate blocks close
     - Supervisor posts: DR FC Cash 200 | CR Employee AR
     - Retry: Shift closes
   
   ✓ Scenario D: Stock Variance
     - Tank variance = 2% (exceeds 0.5% meniscus)
     - Expected: Hard gate blocks close
     - Supervisor investigates, re-dips, retries
     - Shift closes
   
   ✓ Scenario E: Attendant Discrepancy
     - One attendant short 100 KES
     - Expected: Cannot close until resolved
     - Supervisor posts: DR Employee Advance 100
     - All attendants clear, shift closes

4. Performance testing:
   - Open shift form: should load in <2s ✓
   - Submit entry (meter reading): should respond in <1s ✓
   - Calculate reconciliation: should complete in <5s ✓
   - Close shift (post journals): should complete in <10s ✓

5. Browser compatibility:
   - Test in Chrome, Firefox, Safari
   - All forms should render without errors ✓
   - No JavaScript warnings ✓

6. Database integrity:
   - Run: SELECT COUNT(*) FROM fms_meter_log
   - Verify: count matches expected (8 nozzles × shift count)
   - Run: SELECT SUM(amount) FROM account_move WHERE journal = sales
   - Verify: total matches GL balance
   - Check: No orphaned records (meter_entry with no shift_id)

7. Final checklist:
   ✅ Unit tests: 42/42 passing
   ✅ Integration tests: 6/6 passing
   ✅ UAT scenarios: 5/5 passing
   ✅ Performance: all <10s
   ✅ No DB errors
   ✅ No console errors
   ✅ Mobile responsive
   ✅ PDF reports generate
   ✅ GL accurate
   ✅ Stock accurate
   ✅ Documentation complete

8. Sign-off:
   - Supervisor approves shift close workflow
   - Accountant approves GL entries
   - Manager approves for production deployment
""",
            "expected_outcome": """
✅ All 42 tests passing (80%+ coverage)
✅ All 5 UAT scenarios successful
✅ Performance: all actions <10s
✅ No errors in logs
✅ Documentation complete (RUNBOOK.md, INSTALLATION.md)
✅ Ready for production deployment
✅ Sample data import script works
✅ Go-live checklist signed off
""",
        }
    }
    
    @classmethod
    def get_guide(cls, task_id: str) -> Dict[str, Any]:
        """Get testing guide for a task"""
        return cls.GUIDES.get(task_id, {})
    
    @classmethod
    def print_guide(cls, task_id: str):
        """Print full testing guide"""
        guide = cls.get_guide(task_id)
        if not guide:
            click.echo(f"No testing guide for {task_id}")
            return
        
        click.secho(f"\n{'='*70}", fg='cyan')
        click.secho(guide['title'], fg='cyan', bold=True)
        click.secho(f"{'='*70}\n", fg='cyan')
        
        click.secho("Unit Tests:", fg='yellow', bold=True)
        for test in guide.get('unit_tests', []):
            click.echo(f"  • {test}")
        
        click.secho("\nWhere to Test:", fg='yellow', bold=True)
        click.echo(guide.get('where_to_test', 'N/A'))
        
        click.secho("\nExpected Outcome:", fg='green', bold=True)
        click.echo(guide.get('expected_outcome', 'N/A'))


# ═════════════════════════════════════════════════════════════════════
# CLI Commands
# ═════════════════════════════════════════════════════════════════════

@click.group()
def cli():
    """FMS Development Guide — Sequential Task Orchestrator"""
    pass


@cli.command()
def status():
    """Show current development status"""
    tracker = ProgressTracker()
    stats = tracker.get_status()
    
    click.secho("\n" + "="*70, fg='cyan')
    click.secho("FMS Development Status", fg='cyan', bold=True)
    click.secho("="*70 + "\n", fg='cyan')
    
    total = stats['total']
    completed = stats['completed']
    in_progress = stats['in_progress']
    todo = stats['todo']
    
    # Progress bar
    filled = int((completed / total) * 30)
    bar = "█" * filled + "░" * (30 - filled)
    pct = int((completed / total) * 100)
    
    click.echo(f"Overall Progress: {bar} {pct}% ({completed}/{total})")
    click.echo(f"  ✅ Completed:    {completed}")
    click.echo(f"  🔄 In Progress:  {in_progress}")
    click.echo(f"  ⏳ To Do:        {todo}\n")
    
    # Task breakdown
    click.secho("Task Breakdown:", fg='yellow', bold=True)
    for task_id, task in sorted(TASKS.items()):
        progress = tracker.get_task(task_id)
        status_sym = progress.get('status_symbol', TaskStatus.TODO.value)
        title = task.title
        time_est = task.estimated_time
        click.echo(f"  {status_sym} {task_id}: {title:<40} ({time_est})")
    
    click.echo()


@cli.command()
@click.argument('task_id')
def task(task_id: str):
    """Start or resume a specific task"""
    if task_id not in TASKS:
        click.secho(f"❌ Task {task_id} not found", fg='red')
        return
    
    task_meta = TASKS[task_id]
    tracker = ProgressTracker()
    memory = ClaudeMemory()
    
    click.secho(f"\n{'='*70}", fg='cyan')
    click.secho(f"TASK {task_id}: {task_meta.title}", fg='cyan', bold=True)
    click.secho(f"{'='*70}\n", fg='cyan')
    
    # Check dependencies
    if task_meta.dependencies:
        click.secho("Prerequisites:", fg='yellow', bold=True)
        for dep in task_meta.dependencies:
            dep_meta = TASKS.get(dep)
            dep_progress = tracker.get_task(dep)
            status = dep_progress.get('status', 'TODO')
            symbol = "✅" if status == "APPROVED" else "❌"
            click.echo(f"  {symbol} {dep}: {dep_meta.title if dep_meta else 'Unknown'}")
        
        # Check if all deps complete
        all_complete = all(
            tracker.get_task(dep).get('status') == 'APPROVED'
            for dep in task_meta.dependencies
        )
        if not all_complete:
            click.secho("\n⚠️  Not all prerequisites complete. Proceed anyway? (y/n): ", fg='yellow')
            if not click.confirm("", default=False):
                return
    
    # Show task details
    click.secho("\nTask Details:", fg='yellow', bold=True)
    click.echo(f"  Description: {task_meta.description}")
    click.echo(f"  Reference: {task_meta.spec_reference}")
    click.echo(f"  Estimated Time: {task_meta.estimated_time}\n")
    
    click.secho("Subtasks:", fg='yellow', bold=True)
    for i, subtask in enumerate(task_meta.subtasks, 1):
        click.echo(f"  {i}. {subtask}")
    
    # Show expected artifacts
    click.secho("\nExpected Artifacts:", fg='yellow', bold=True)
    for category, files in task_meta.artifacts.items():
        click.echo(f"  {category.capitalize()}:")
        for file in files:
            click.echo(f"    - {file}")
    
    click.secho("\n" + "-"*70, fg='blue')
    click.secho("CLAUDE CODE PROMPT COMING NEXT...", fg='blue', bold=True)
    click.secho("-"*70 + "\n", fg='blue')
    
    # Generate prompt
    prompt = _generate_prompt(task_id)
    click.echo(prompt)
    
    click.secho("\n" + "="*70, fg='green')
    click.secho("NEXT STEPS:", fg='green', bold=True)
    click.secho("="*70, fg='green')
    click.echo("""
1. Copy the prompt above
2. Paste into Claude Code: /claude dev-guide.py <prompt>
3. Claude will generate code for subtasks
4. After each subtask:
   - Claude will show test commands
   - You run tests locally
   - You perform visual testing (see guide below)
5. After all subtasks pass, you approve
6. Script commits and tracks progress

TESTING GUIDE (Where to Test & Sample Data):
""")
    
    # Show testing guide
    TestingGuide.print_guide(task_id)
    
    # Update memory
    memory.update_task(task_id, "IN_PROGRESS", f"Started at {datetime.now().strftime('%H:%M')}")
    
    # Mark as in progress
    tracker.update_task(task_id, status="IN_PROGRESS", started_at=datetime.now().isoformat())


@cli.command()
def list():
    """List all tasks"""
    click.secho("\nFMS Development Tasks:\n", fg='cyan', bold=True)
    
    for task_id in sorted(TASKS.keys()):
        task = TASKS[task_id]
        click.echo(f"{task_id}: {task.title}")
        click.echo(f"  └─ {task.description}")
        if task.dependencies:
            click.echo(f"  └─ Requires: {', '.join(task.dependencies)}")
        click.echo()


@cli.command()
@click.argument('task_id')
def info(task_id: str):
    """Show detailed information about a task"""
    if task_id not in TASKS:
        click.secho(f"❌ Task not found: {task_id}", fg='red')
        return
    
    task = TASKS[task_id]
    click.secho(f"\n{'='*70}", fg='cyan')
    click.secho(f"{task_id}: {task.title}", fg='cyan', bold=True)
    click.secho(f"{'='*70}\n", fg='cyan')
    
    click.secho("Description:", fg='yellow', bold=True)
    click.echo(f"  {task.description}\n")
    
    click.secho("Specification Reference:", fg='yellow', bold=True)
    click.echo(f"  {task.spec_reference}\n")
    
    click.secho("Estimated Time:", fg='yellow', bold=True)
    click.echo(f"  {task.estimated_time}\n")
    
    if task.dependencies:
        click.secho("Dependencies:", fg='yellow', bold=True)
        for dep in task.dependencies:
            click.echo(f"  • {dep}")
        click.echo()
    
    click.secho("Subtasks:", fg='yellow', bold=True)
    for subtask in task.subtasks:
        click.echo(f"  • {subtask}")
    click.echo()
    
    click.secho("Expected Artifacts:", fg='yellow', bold=True)
    for category, files in task.artifacts.items():
        click.echo(f"\n  {category.capitalize()}:")
        for file in files:
            click.echo(f"    - {file}")


@cli.command()
def report():
    """Generate progress report"""
    tracker = ProgressTracker()
    stats = tracker.get_status()
    
    report_lines = [
        "# FMS Development Progress Report",
        f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"\n## Summary",
        f"- **Total Tasks:** {stats['total']}",
        f"- **Completed:** {stats['completed']} ✅",
        f"- **In Progress:** {stats['in_progress']} 🔄",
        f"- **To Do:** {stats['todo']} ⏳",
        f"\n## Task Status",
    ]
    
    for task_id in sorted(TASKS.keys()):
        progress = tracker.get_task(task_id)
        status = progress.get('status', 'TODO')
        report_lines.append(f"\n### {task_id}: {TASKS[task_id].title}")
        report_lines.append(f"- Status: {status}")
        if progress.get('commit_hash'):
            report_lines.append(f"- Commit: {progress['commit_hash']}")
        if progress.get('notes'):
            report_lines.append(f"- Notes: {progress['notes']}")
    
    report_text = "\n".join(report_lines)
    click.echo(report_text)
    
    # Save to file
    report_file = FMS_ROOT / "REPORT.md"
    report_file.write_text(report_text)
    click.secho(f"\n✅ Report saved to {report_file}", fg='green')


# ═════════════════════════════════════════════════════════════════════
# Prompt Generation
# ═════════════════════════════════════════════════════════════════════

def _generate_prompt(task_id: str) -> str:
    """Generate comprehensive Claude Code prompt for a task"""
    task = TASKS[task_id]
    
    prompt = f"""# Task: {task_id} - {task.title}

## Objective
{task.description}

## Reference
Specification: {task.spec_reference}  
See: FMS_Complete_Specification_Technical_Guide.md

## Requirements

### Subtasks (In Order)
"""
    
    for i, subtask in enumerate(task.subtasks, 1):
        prompt += f"\n{i}. {subtask}"
    
    prompt += f"""

### Expected Artifacts

**Models:**
"""
    for file in task.artifacts.get('models', []):
        prompt += f"\n- {file}"
    
    prompt += f"""

**Views (if applicable):**
"""
    for file in task.artifacts.get('views', []):
        prompt += f"\n- {file}"
    
    prompt += f"""

**Tests:**
"""
    for file in task.artifacts.get('tests', []):
        prompt += f"\n- {file}"
    
    prompt += """

## Constraints
1. Follow Spec Section 8 (Data Models) for exact field names & relationships
2. Use Odoo 18 API (fields, models, @api.depends, etc.)
3. Include docstrings in all methods
4. Write unit tests (pytest format)
5. Use Odoo ORM (no raw SQL)
6. Follow PEP 8 style (4-space indent)

## Instructions for Code Generation

1. **Start with model definitions** (if this is a models task)
   - Define model class with _name, _description
   - Add all fields (from spec)
   - Add computed fields with @api.depends
   - Add constraints (@api.constrains)
   - Add methods (create, write, etc.)

2. **Write tests as you go**
   - For each model/method, write 1-3 tests
   - Test happy path + edge cases
   - Use TransactionCase for DB tests

3. **Output format**
   - First: model code in ```python blocks
   - Then: test code in ```python blocks
   - Each file should be complete & runnable

4. **Testing commands** (you'll run these)
   ```bash
   pytest tests/test_{task_id}.py -v
   pytest tests/test_{task_id}.py -v --cov=models/{task_id}
   ```

## What NOT to Do
- Don't import shell_maanzoni_fms (make it generic fms_*)
- Don't hardcode test data (use fixtures)
- Don't assume POS module exists (check dependencies)
- Don't write views (only models & tests for now)
- Don't skip tests

## After Code Generation

1. Show test commands to run
2. I will run tests locally
3. I will do visual testing (see guide below)
4. I will approve or request changes
5. System will auto-commit with reference

---

## Visual Testing Guide

After you generate code, I will:

1. **Run unit tests locally:**
   ```bash
   cd ~/fms
   pytest tests/test_{task_id}.py -v
   ```

2. **Start Odoo & test manually:**
   - Launch: `./odoo-bin -d test_fms`
   - Install: Settings → Apps → Install FMS module
   - Create sample data (see guide below)
   - Verify forms load without errors

3. **Check for errors:**
   - Browser console (F12): No JS errors
   - Odoo logs: No Python errors
   - Database: No constraint violations

4. **Screenshot for approval:**
   - Take screenshot of working form/feature
   - Verify data persists after reload

Only after ALL TESTS PASS + VISUAL TEST PASSED, I approve and system commits.

---

## Done. Ready to generate code?
"""
    
    return prompt


# ═════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    cli()
