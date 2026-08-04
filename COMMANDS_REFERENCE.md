# FMS Commands Reference & Cheat Sheet

Quick reference for all commonly used FMS development commands.

---

## Development Orchestration

### Show Status
```bash
python scripts/dev-guide.py status
```
**Output:** Shows progress (completed/in-progress/todo tasks)

### Start a Task
```bash
python scripts/dev-guide.py task FMS-001
```
**Output:** Task description, subtasks, prompt, testing guide

### List All Tasks
```bash
python scripts/dev-guide.py list
```
**Output:** All 8 tasks with titles

### Get Task Details
```bash
python scripts/dev-guide.py info FMS-001
```
**Output:** Detailed task information (dependencies, artifacts, time)

### Generate Progress Report
```bash
python scripts/dev-guide.py report
```
**Output:** Saves to REPORT.md (summary of all tasks)

---

## Setup & Initialization

### Complete Project Setup (Recommended)
```bash
bash setup-all.sh
```
**Does:** Runs all setup steps (structure + git + docs)

### Project Structure Only
```bash
bash setup-fms-project.sh
```
**Does:** Creates directories, files, placeholders

### Git Workflow Only
```bash
bash setup-git-workflow.sh
```
**Does:** Initializes git, branches, hooks

---

## Git Operations

### Show Current Status
```bash
git status
```

### View All Branches
```bash
git branch -a
```

### Create Feature Branch
```bash
git checkout -b fms-001-core-models
```
**Pattern:** `fms-[task-number]-[description]`

### Stage Changes
```bash
git add .
```

### Commit Changes
```bash
git commit -m "feat(models): implement core FMS models

- fms.shift model
- fms.pump and fms.pump.nozzle
- fms.meter_log and fms.dip_log

Ref: Spec Section 8.1
Task: FMS-001
Tests: 12/12 passing
Time: 2h 34m"
```

### Tag Release
```bash
git tag v0.1-core-models
```

### Merge to Development
```bash
git checkout development
git merge --no-ff fms-001-core-models
```

### View Commit History
```bash
git log --oneline --graph --all
```

### Show Changes for a Task
```bash
git log --oneline --grep='FMS-001'
```

### Undo Last Commit (Keep Changes)
```bash
git reset --soft HEAD~1
```

### Undo Last Commit (Discard Changes)
```bash
git reset --hard HEAD~1
```

---

## Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Tests for a Specific Task
```bash
pytest tests/test_fms_shift.py -v
```

### Run Tests with Coverage
```bash
pytest tests/ -v --cov=models/
```

### Run Tests with Coverage Report
```bash
pytest tests/ -v --cov=models/ --cov-report=html
```
**Output:** HTML report in `htmlcov/index.html`

### Run Specific Test
```bash
pytest tests/test_fms_shift.py::TestFMSShift::test_create_shift -v
```

### Run Tests Matching Pattern
```bash
pytest tests/ -k "residual" -v
```

### Run Tests with Detailed Output
```bash
pytest tests/ -v -s
```

### Run Quick Tests (skip slow tests)
```bash
pytest tests/ -v -m "not slow"
```

---

## Odoo Operations

### Start Odoo Server
```bash
./odoo-bin -d test_fms
```
**Flags:**
- `-d` — Database name
- `-p` — Port (default 8069)
- `--dev=all` — Development mode
- `--limit-time-cpu=9999` — Increase timeout

### Start Odoo with Debug
```bash
./odoo-bin -d test_fms --dev=all
```

### Shell/Interactive Console
```bash
odoo shell -d test_fms
```

### Create New Database
```bash
createdb test_fms
./odoo-bin -d test_fms -i base,account,stock,point_of_sale,hr
```

### Backup Database
```bash
pg_dump test_fms > test_fms_backup.sql
```

### Restore Database
```bash
psql test_fms < test_fms_backup.sql
```

### Update FMS Module
```bash
./odoo-bin -d test_fms -u fms
```

---

## File Operations

### View Directory Structure
```bash
tree -L 2 .
```

### Find Python Files
```bash
find . -name "*.py" -not -path './.git/*' -not -path '*/__pycache__/*'
```

### Find View Files
```bash
find . -name "*.xml" -path "*/views/*"
```

### Find Test Files
```bash
find . -name "test_*.py"
```

### Count Lines of Code
```bash
find . -name "*.py" -not -path './.git/*' | xargs wc -l
```

### Check File Syntax
```bash
python -m py_compile models/fms_shift.py
```

### Format Python Code (if using black)
```bash
black models/ tests/
```

### Check Code Style (if using flake8)
```bash
flake8 models/ tests/
```

---

## Documentation

### View Quick Start
```bash
cat QUICK_START.md
```

### View Development Guide
```bash
cat docs/FMS_DEVELOPMENT_SYSTEM_README.md
```

### View Complete Specification
```bash
cat docs/FMS_Complete_Specification_Technical_Guide.md
```

### View Runbook (Operations)
```bash
cat docs/RUNBOOK.md
```

### View Installation Guide
```bash
cat docs/INSTALLATION.md
```

### View Coding Patterns
```bash
cat docs/fms-development.skill
```

### View Project Memory/Context
```bash
cat docs/CLAUDE.md
```

### Edit Project Memory
```bash
vim docs/CLAUDE.md
```

---

## Debugging

### View Odoo Logs (Running)
```bash
tail -f ~/.local/share/Odoo/filestore/test_fms/logs/odoo.log
```

### Check Python Syntax Error
```bash
python -m py_compile models/fms_shift.py
```

### Run Python with Debugging
```bash
python -m pdb -c continue models/fms_shift.py
```

### Interactive Python Shell
```bash
python
```
Then:
```python
import sys
sys.path.insert(0, '/path/to/odoo')
import odoo
# ...
```

### View Browser Console (Odoo Web)
Press `F12` in browser

### Enable Odoo Debug Mode
In Odoo web UI: **Settings → Activate Debug Mode**

---

## Development Workflow (Full Example)

```bash
# 1. Check current status
python scripts/dev-guide.py status

# 2. Start FMS-001 task
python scripts/dev-guide.py task FMS-001

# 3. Create feature branch
git checkout -b fms-001-core-models

# 4. View first subtask details
python scripts/dev-guide.py info FMS-001

# 5. Copy prompt to Claude Code
# (Manually copy from CLI output)
/claude dev-guide.py [paste FMS-001 prompt]

# 6. Claude generates code...

# 7. Run unit tests
pytest tests/test_fms_shift.py -v

# 8. Start Odoo for visual testing
./odoo-bin -d test_fms

# 9. Visual test (in Odoo web UI)
# - Install FMS module
# - Create sample data
# - Verify forms load
# - Take screenshot

# 10. If tests pass and visual test OK:
git add .
git commit -m "feat(models): implement core FMS models

- fms.shift model
- fms.pump, fms.pump.nozzle

Ref: Spec Section 8.1
Task: FMS-001
Tests: 12/12 passing
Time: 2h 34m"

# 11. Tag task
git tag v0.1-core-models

# 12. Merge to development
git checkout development
git merge --no-ff fms-001-core-models

# 13. Start next task
python scripts/dev-guide.py task FMS-002
```

---

## Useful Combinations

### Run tests and update coverage
```bash
pytest tests/ -v --cov=models/ && open htmlcov/index.html
```

### Commit with auto-filled task reference (if using git hooks)
```bash
git add . && git commit  # hooks auto-add task template
```

### Quick status check before push
```bash
git status && git log --oneline -3 && pytest tests/ -q
```

### Full test coverage report
```bash
pytest tests/ --cov=models/ --cov-report=html --cov-report=term
```

### Clean up merged branches
```bash
git branch -d fms-001-core-models fms-002-child-models
```

### See what changed in a commit
```bash
git show abc123d
```

### Compare two branches
```bash
git diff main..development
```

---

## Helpful Aliases (Add to ~/.bashrc or ~/.zshrc)

```bash
# FMS development aliases
alias fms-status='python scripts/dev-guide.py status'
alias fms-task='python scripts/dev-guide.py task'
alias fms-list='python scripts/dev-guide.py list'
alias fms-test='pytest tests/ -v'
alias fms-coverage='pytest tests/ -v --cov=models/'
alias fms-tree='tree -L 2 .'
alias fms-odoo='./odoo-bin -d test_fms'

# Git aliases
alias g='git'
alias gs='git status'
alias gb='git branch -a'
alias gl='git log --oneline --graph --all'
alias gd='git diff'
alias gc='git commit'
```

Usage:
```bash
fms-status
fms-task FMS-001
fms-test
fms-coverage
```

---

## Cheat Sheet (TL;DR)

```bash
# Start
python scripts/dev-guide.py task FMS-001

# Develop
git checkout -b fms-001-core-models
# (Make changes)
pytest tests/test_fms_shift.py -v

# Commit
git add .
git commit -m "feat(models): [changes]"

# Done with task
git tag v0.1-core-models
git checkout development
git merge --no-ff fms-001-core-models

# Next
python scripts/dev-guide.py task FMS-002
```

---

## Reference Links

- **Python:** https://docs.python.org/3/
- **Pytest:** https://docs.pytest.org/
- **Git:** https://git-scm.com/docs
- **Odoo 18:** https://www.odoo.com/documentation/18.0/
- **Odoo ORM:** https://www.odoo.com/documentation/18.0/developer/reference/orm.html

---

**Keep this file handy!** 📌

Save this page or print it for quick reference during development.
