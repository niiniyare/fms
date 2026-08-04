#!/bin/bash
set -e

# ═════════════════════════════════════════════════════════════════════
# FMS Complete Project Setup
# ═════════════════════════════════════════════════════════════════════
# 
# Master script that runs all setup steps in order
# Usage: bash setup-all.sh [PROJECT_ROOT]

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PROJECT_ROOT="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}"
cat << "EOF"
╔═════════════════════════════════════════════════════════════════╗
║                                                                 ║
║     FMS (Forecourt Management System) - Complete Setup         ║
║                                                                 ║
║     Odoo 18 Community Edition                                  ║
║     Phase 1: MVP Development                                   ║
║                                                                 ║
╚═════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}\n"

echo -e "${BLUE}Project Root: ${PROJECT_ROOT}${NC}\n"

# ═════════════════════════════════════════════════════════════════════
# Step 1: Project Structure
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 1/3: Project Structure${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

cd "$PROJECT_ROOT"

# Make scripts executable
chmod +x "$SCRIPT_DIR/setup-fms-project.sh" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/setup-git-workflow.sh" 2>/dev/null || true

# Run project setup
bash "$SCRIPT_DIR/setup-fms-project.sh" "$PROJECT_ROOT"

# ═════════════════════════════════════════════════════════════════════
# Step 2: Git Workflow
# ═════════════════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 2/3: Git Workflow${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

bash "$SCRIPT_DIR/setup-git-workflow.sh" "$PROJECT_ROOT"

# ═════════════════════════════════════════════════════════════════════
# Step 3: Create helpful info files
# ═════════════════════════════════════════════════════════════════════

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 3/3: Creating Info Files${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# Create quick reference file
cat > "$PROJECT_ROOT/QUICK_START.md" << 'EOF'
# FMS Quick Start Guide

## Project Setup Complete! ✅

Your FMS project is now ready for development.

### Directory Structure

```
fms/
├── __init__.py                    # Module init
├── __manifest__.py                # Odoo metadata
├── models/                        # Python models
│   ├── __init__.py
│   ├── fms_shift.py               # Main shift model
│   ├── fms_pump.py                # Pump master data
│   ├── fms_logs.py                # Immutable logs
│   ├── fms_shift_entry.py         # Entry forms
│   └── fms_shift_reconciliation.py # Reconciliation
├── views/                         # Form layouts (XML)
│   ├── fms_pump_views.xml
│   ├── fms_shift_views.xml
│   └── ...
├── security/                      # Access control (XML)
│   ├── fms_groups.xml
│   ├── ir_model_access.xml
│   └── ir_rule.xml
├── tests/                         # Unit tests (pytest)
│   ├── test_fms_shift.py
│   ├── test_fms_logs.py
│   └── ...
├── docs/                          # Documentation
│   ├── FMS_Complete_Specification_Technical_Guide.md
│   ├── FMS_DEVELOPMENT_SYSTEM_README.md
│   ├── CLAUDE.md
│   ├── RUNBOOK.md
│   ├── INSTALLATION.md
│   └── fms-development.skill
├── scripts/                       # Utilities & orchestration
│   ├── dev-guide.py               # Task orchestrator
│   └── tasks.yaml                 # Task registry
├── reports/                       # PDF reports
├── static/                        # CSS/JS
├── data/                          # Master data
└── .git/                          # Git repository
```

### What to Do Next

#### 1. Read Documentation (15 minutes)

```bash
# Quick overview
cat docs/FMS_DEVELOPMENT_SYSTEM_README.md

# Project context & architecture
cat docs/CLAUDE.md

# Operational procedures
cat docs/RUNBOOK.md

# Installation guide
cat docs/INSTALLATION.md

# Coding patterns
cat docs/fms-development.skill
```

#### 2. View Current Status

```bash
# Show git status
git status

# View branches
git branch -a

# See file structure
tree -L 2 .
```

#### 3. Start Development

```bash
# Check development task status
python scripts/dev-guide.py status

# Start first task
python scripts/dev-guide.py task FMS-001

# List all tasks
python scripts/dev-guide.py list
```

### Development Workflow

For each of 8 tasks (FMS-001 through FMS-008):

```bash
# 1. View task details & generate prompt
python scripts/dev-guide.py task FMS-001

# 2. Copy the prompt to Claude Code
/claude dev-guide.py [paste prompt]

# 3. Claude generates code (models + tests)

# 4. Run tests locally
pytest tests/test_fms_001.py -v

# 5. Visual testing (follow guide in CLI output)
./odoo-bin -d test_fms
# Install FMS, create sample data, verify forms

# 6. Approve (system auto-commits)
git log --oneline -1

# 7. Start next task
python scripts/dev-guide.py task FMS-002
```

### Git Workflow

```bash
# Create feature branch for a task
git checkout -b fms-001-core-models

# Make changes, commit (hooks add template)
git add .
git commit -m "feat(models): implement core FMS models
...details...
Task: FMS-001"

# Tag task completion
git tag v0.1-core-models

# Merge back to development
git checkout development
git merge --no-ff fms-001-core-models

# View commit graph
git log --oneline --graph --all
```

### Key Commands

```bash
# Development orchestration
python scripts/dev-guide.py status          # Show progress
python scripts/dev-guide.py task FMS-001    # Start task with prompt
python scripts/dev-guide.py list            # List all tasks
python scripts/dev-guide.py info FMS-001    # Task details
python scripts/dev-guide.py report          # Progress report

# Testing
pytest tests/ -v                            # Run all tests
pytest tests/test_fms_001.py -v            # Single task tests
pytest tests/ -v --cov=models/             # With coverage

# Git
git checkout -b fms-001-core-models        # Create branch
git commit -m "..."                         # Commit changes
git tag v0.1-core-models                   # Tag release
git log --graph --all --oneline            # View history
```

### Important Files

- **docs/FMS_Complete_Specification_Technical_Guide.md** — Complete technical spec (reference)
- **docs/FMS_DEVELOPMENT_SYSTEM_README.md** — Development guide
- **scripts/dev-guide.py** — Task orchestrator (main CLI)
- **scripts/tasks.yaml** — All 8 task definitions
- **docs/CLAUDE.md** — Project memory & context
- **docs/fms-development.skill** — Coding patterns

### Timeline

```
Week 1: FMS-001, FMS-002, FMS-003  →  8 hours
Week 2: FMS-004, FMS-005, FMS-006  →  5 hours
Week 3: FMS-007, FMS-008           →  5 hours
Buffer: Fixes & surprises          →  2 hours
───────────────────────────────────────────
TOTAL: Phase 1 MVP                 → ~16 hours
```

### Troubleshooting

**If something doesn't work:**

1. Check **docs/FMS_DEVELOPMENT_SYSTEM_README.md** (Troubleshooting section)
2. Read relevant spec section: **docs/FMS_Complete_Specification_Technical_Guide.md**
3. Review coding patterns: **docs/fms-development.skill**
4. Look at error message carefully
5. Check Odoo logs (F12 console for JS errors)

### Next Immediate Action

```bash
# Read the development guide
cat docs/FMS_DEVELOPMENT_SYSTEM_README.md

# Then start the first task
python scripts/dev-guide.py task FMS-001
```

---

**Setup completed:** $(date)  
**Status:** ✅ Ready for development  
**Next step:** Start FMS-001  

Good luck! 🚀
EOF

echo -e "${GREEN}✓ Created: QUICK_START.md${NC}"

# Create helpful reference file
cat > "$PROJECT_ROOT/SETUP_SUMMARY.md" << 'EOF'
# FMS Project Setup Summary

## ✅ Setup Complete

Your FMS project has been successfully initialized with:

### 1. Directory Structure ✓
- Models directory (Python models)
- Views directory (XML form layouts)
- Security directory (access control)
- Tests directory (pytest tests)
- Docs directory (documentation)
- Scripts directory (utilities)
- Reports directory (PDF templates)
- Static directory (CSS/JS)
- Data directory (master data)

### 2. Odoo Module Files ✓
- `__init__.py` — Module initialization
- `__manifest__.py` — Odoo metadata
- Placeholder models in `models/`
- Placeholder views in `views/`
- Placeholder security in `security/`

### 3. Git Workflow ✓
- Initialized git repository
- Created main branch
- Created development branch
- Set up git hooks (pre-commit, prepare-commit-msg)
- Created .gitignore
- Created .gitattributes

### 4. Documentation ✓
- RUNBOOK.md (operations guide)
- INSTALLATION.md (setup guide)
- CLAUDE.md (project context & memory)
- fms-development.skill (coding patterns)
- FMS_Complete_Specification_Technical_Guide.md (technical spec)
- FMS_DEVELOPMENT_SYSTEM_README.md (development guide)

### 5. Development Tools ✓
- dev-guide.py (task orchestrator)
- tasks.yaml (task registry)
- Sample data templates (per task)
- Testing guides (per task)

---

## Files & Locations

**Development Orchestration:**
- `scripts/dev-guide.py` — Main CLI (use this!)
- `scripts/tasks.yaml` — All 8 tasks defined

**Documentation:**
- `docs/QUICK_START.md` — This file's complement
- `docs/FMS_DEVELOPMENT_SYSTEM_README.md` — Full guide
- `docs/FMS_Complete_Specification_Technical_Guide.md` — Technical spec
- `docs/CLAUDE.md` — Project context
- `docs/fms-development.skill` — Coding patterns
- `docs/RUNBOOK.md` — Operations guide
- `docs/INSTALLATION.md` — Setup instructions

**Code (to be populated):**
- `models/` — Python models (generated per task)
- `views/` — XML form layouts (generated per task)
- `tests/` — Pytest tests (generated per task)
- `security/` — Access control (generated per task)

**Git:**
- `.git/` — Git repository (initialized)
- `.gitignore` — Ignore patterns
- `.gitattributes` — Line ending rules
- `.git/hooks/` — Custom git hooks

---

## Quick Commands

### Development
```bash
python scripts/dev-guide.py status          # View progress
python scripts/dev-guide.py task FMS-001    # Start task + get prompt
python scripts/dev-guide.py list            # List all tasks
```

### Testing
```bash
pytest tests/ -v                            # Run all tests
pytest tests/ -v --cov=models/             # With coverage
```

### Git
```bash
git status                                  # Current status
git branch -a                               # View branches
git log --oneline --graph --all            # View history
git checkout -b fms-001-core-models        # Create feature branch
```

---

## Next Steps

### Immediate (Now)
1. ✅ Read: `docs/FMS_DEVELOPMENT_SYSTEM_README.md` (5 min)
2. ✅ Understand: Directory structure (`tree -L 2`)
3. ✅ Check: `python scripts/dev-guide.py status`

### Within 1 Hour
1. Run: `python scripts/dev-guide.py task FMS-001`
2. Copy prompt to Claude Code
3. Let Claude generate code

### Within 2-3 Hours
1. Run tests: `pytest tests/test_fms_001.py -v`
2. Visual test in Odoo (follow guide)
3. Approve task (system commits)

### Over Next 16 Hours (Total)
1. Complete all 8 tasks (4 hours per week)
2. Each task: generate → test → visual → approve
3. System auto-tracks progress
4. Phase 1 MVP complete

---

## File Inventory

**Total Files Created:** 40+
**Total Directories:** 10+
**Total Code/Docs:** 2500+ lines

**Key Files:**
- Scripts: 5+ (dev-guide.py, setup scripts)
- Documentation: 8+ (guides, specs, skills)
- Models: 5 placeholders (fms_shift, fms_pump, etc.)
- Views: 5 placeholders (XML templates)
- Security: 3 placeholders (access control)
- Tests: Multiple placeholders
- Config: 3 (.gitignore, .gitattributes, __manifest__.py)

---

## Verify Setup

Run these commands to verify everything is set up:

```bash
# Check directory structure
tree -L 2 .

# Check git status
git status

# Check branches exist
git branch -a

# Check Python is available
python --version

# Check odoo module structure
ls -la __init__.py __manifest__.py models/ views/ security/ tests/ docs/

# Check dev-guide.py works
python scripts/dev-guide.py status

# Expected output:
# ✅ All directories present
# ✅ Git initialized (main, development branches)
# ✅ Python 3.9+ available
# ✅ All module files present
# ✅ dev-guide.py shows 0/8 tasks completed
```

---

## Support

If you get stuck:

1. **Quick answers:** `docs/FMS_DEVELOPMENT_SYSTEM_README.md` (Troubleshooting)
2. **Detailed docs:** `docs/FMS_Complete_Specification_Technical_Guide.md`
3. **Patterns:** `docs/fms-development.skill`
4. **Context:** `docs/CLAUDE.md`

---

## Success Criteria (End of Setup)

✅ Directory structure created  
✅ Git repository initialized  
✅ All placeholder files created  
✅ Documentation in place  
✅ dev-guide.py working  
✅ Ready to start FMS-001  

---

**Setup Status:** ✅ COMPLETE  
**Date:** $(date)  
**Next Action:** `python scripts/dev-guide.py task FMS-001`  

🚀 Ready to build FMS!
EOF

echo -e "${GREEN}✓ Created: SETUP_SUMMARY.md${NC}"

# ═════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════

echo ""
echo -e "${BLUE}═════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}╔═════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                             ║${NC}"
echo -e "${CYAN}║  ${GREEN}✓ FMS PROJECT SETUP COMPLETE!${CYAN}                           ║${NC}"
echo -e "${CYAN}║                                                             ║${NC}"
echo -e "${CYAN}╚═════════════════════════════════════════════════════════════╝${NC}"
echo -e "${BLUE}═════════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}What's Been Set Up:${NC}\n"

echo "✅ Project Structure"
echo "   - models/, views/, security/, tests/, docs/, scripts/"
echo "   - All necessary directories created"
echo ""

echo "✅ Odoo Module Files"
echo "   - __init__.py (module initialization)"
echo "   - __manifest__.py (metadata with dependencies)"
echo "   - Placeholder files (models, views, security)"
echo ""

echo "✅ Git Workflow"
echo "   - Repository initialized"
echo "   - main & development branches created"
echo "   - Pre-commit hooks installed"
echo "   - .gitignore & .gitattributes configured"
echo ""

echo "✅ Documentation"
echo "   - Development guide"
echo "   - Operational runbook"
echo "   - Installation guide"
echo "   - Complete technical specification"
echo "   - Coding patterns & best practices"
echo ""

echo "✅ Development System"
echo "   - dev-guide.py (task orchestrator)"
echo "   - tasks.yaml (8 tasks with full metadata)"
echo "   - Per-task testing guides"
echo "   - Sample data templates"
echo ""

echo -e "${YELLOW}Quick Start:${NC}\n"

echo "1. Read the quick start guide:"
echo "   cat QUICK_START.md"
echo ""

echo "2. Check status:"
echo "   python scripts/dev-guide.py status"
echo ""

echo "3. Start first task:"
echo "   python scripts/dev-guide.py task FMS-001"
echo ""

echo "4. See full guide:"
echo "   cat docs/FMS_DEVELOPMENT_SYSTEM_README.md"
echo ""

echo -e "${YELLOW}Current Status:${NC}\n"

cd "$PROJECT_ROOT"
echo -n "Git branches: "
git branch -q && echo "" || echo "initialized"

echo -n "Directory structure: "
[ -d "models" ] && echo "✓" || echo "✗"

echo -n "dev-guide.py: "
[ -f "scripts/dev-guide.py" ] && echo "✓" || echo "✗"

echo -n "Documentation: "
[ -d "docs" ] && echo "✓" || echo "✗"

echo ""
echo -e "${GREEN}You're all set! 🚀${NC}"
echo -e "${GREEN}Next step: python scripts/dev-guide.py task FMS-001${NC}\n"
