.PHONY: help \
	setup seed upgrade run stop shell drop reset build \
	test test-unit test-coverage test-watch test-specific test-task \
	status task list info report \
	git-status git-branch git-log git-commit git-merge git-tag \
	docs docs-quick docs-setup docs-system docs-dev docs-spec \
	docs-patterns docs-runbook docs-install docs-commands \
	docs-setup-guide docs-operations docs-finance \
	format lint syntax clean check full-check \
	install install-dev project-info version tree structure \
	start-task finish-task dev-cycle \
	s t o h \
	odoo odoo-dev odoo-shell odoo-install odoo-update odoo-test \
	odoo-e2e-create odoo-e2e-seed odoo-e2e-update odoo-e2e odoo-e2e-drop

# ── Colors ────────────────────────────────────────────────────────────────────
BLUE   := \033[0;34m
GREEN  := \033[0;32m
YELLOW := \033[1;33m
RED    := \033[0;31m
NC     := \033[0m

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_NAME := FMS (Forecourt Management System)
PYTHON       := python3
PYTEST       := pytest

# Main working database (fms_e2e) — used for all daily commands
DB_NAME      := fms_e2e
ODOO_PORT    := 8070

# Test-only database — recreated fresh for every 'make test' run
TEST_DB      := test_fms

ODOO_VENV   := /home/niini/odoo-venv/bin/python
ODOO_BIN    := /home/niini/odoo18/odoo-bin
ODOO_ADDONS := /home/niini/odoo18/addons,/home/niini/fms/..,/home/niini/oca/account-financial-reporting,/home/niini/oca/account-financial-tools,/home/niini/oca/account-reconcile,/home/niini/oca/credit-control,/home/niini/oca/web,/home/niini/oca/server-ux,/home/niini/oca/reporting-engine,/home/niini/oca/server-tools,/home/niini/oca/mis-builder,/home/niini/oca/hr-expense

.DEFAULT_GOAL := help

# ═════════════════════════════════════════════════════════════════════════════
# HELP
# ═════════════════════════════════════════════════════════════════════════════

help: ## Show this help
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║  $(GREEN)$(PROJECT_NAME)$(BLUE)                     ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(YELLOW)DAILY COMMANDS (db: $(DB_NAME), port $(ODOO_PORT)):$(NC)"
	@echo "  make setup             Create DB + install FMS modules (first time)"
	@echo "  make seed              Seed Kenya CoA + products + demo data"
	@echo "  make upgrade           Update modules after code changes"
	@echo "  make run               Upgrade modules then start server → http://localhost:$(ODOO_PORT)"
	@echo "  make shell             Open Odoo Python shell"
	@echo "  make stop              Kill server"
	@echo "  make drop              Drop the database (with confirmation)"
	@echo "  make reset             Drop + setup + seed from scratch"
	@echo ""
	@echo "$(YELLOW)TESTING (db: $(TEST_DB)):$(NC)"
	@echo "  make test              Run FMS test suite (recreates $(TEST_DB))"
	@echo "  make test-coverage     Tests + HTML coverage report"
	@echo "  make test-task TASK=FMS-001"
	@echo ""
	@echo "$(YELLOW)TASK MANAGEMENT:$(NC)"
	@echo "  make status            Show task progress"
	@echo "  make task TASK=FMS-001 Start a development task"
	@echo "  make list              List all tasks"
	@echo ""
	@echo "$(YELLOW)DOCS:$(NC)"
	@echo "  make docs              List all documentation"
	@echo "  make docs-setup-guide  Pre-first-shift system setup"
	@echo "  make docs-operations   Operations training"
	@echo "  make docs-finance      Finance training"
	@echo ""
	@echo "$(YELLOW)SHORTCUTS:$(NC)"
	@echo "  s=status  t=test  o=run  h=help"
	@echo ""
	@echo "$(YELLOW)ALL TARGETS:$(NC)"
	@grep -E '^[a-z][a-z0-9-]+:.*?## ' Makefile | awk 'BEGIN {FS = ":.*?## "} {printf "  $(GREEN)%-25s$(NC) %s\n", $$1, $$2}' | sort

# ═════════════════════════════════════════════════════════════════════════════
# DAILY COMMANDS  (all target fms_e2e on port 8070)
# ═════════════════════════════════════════════════════════════════════════════

setup: ## Create fms_e2e DB and install FMS modules (first time)
	@echo "$(BLUE)Creating $(DB_NAME)...$(NC)"
	$(ODOO_VENV) $(ODOO_BIN) -d $(DB_NAME) \
		-i fms,fms_accounting \
		--addons-path=$(ODOO_ADDONS) \
		--stop-after-init --without-demo=all \
		--load-language=en_US
	@echo "$(GREEN)✓ $(DB_NAME) created. Next: make seed$(NC)"

seed: ## Seed fms_e2e with Kenya CoA + products + demo data
	@echo "$(BLUE)Seeding $(DB_NAME)...$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) shell -d $(DB_NAME) \
		--addons-path=$(ODOO_ADDONS) --no-http \
		< scripts/seed_e2e.py
	@echo "$(GREEN)✓ Seed complete$(NC)"

upgrade: ## Update fms + fms_accounting modules after code changes
	@echo "$(BLUE)Updating modules in $(DB_NAME)...$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) -d $(DB_NAME) -u fms,fms_accounting \
		--addons-path=$(ODOO_ADDONS) --stop-after-init --no-http
	@echo "$(GREEN)✓ Updated$(NC)"

run: ## Upgrade modules then start server → http://localhost:$(ODOO_PORT)
	@fuser -k $(ODOO_PORT)/tcp 2>/dev/null || true
	@echo "$(BLUE)Upgrading modules...$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) -d $(DB_NAME) -u fms,fms_accounting \
		--addons-path=$(ODOO_ADDONS) --stop-after-init --no-http
	@echo "$(YELLOW)Starting server → http://localhost:$(ODOO_PORT)$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) -d $(DB_NAME) -p $(ODOO_PORT) \
		--addons-path=$(ODOO_ADDONS) --dev=all

stop: ## Kill Odoo server
	@fuser -k $(ODOO_PORT)/tcp 2>/dev/null || true
	@fuser -k 8069/tcp 2>/dev/null || true
	@echo "$(GREEN)✓ Stopped$(NC)"

shell: ## Open Odoo interactive Python shell
	@echo "$(BLUE)Opening shell (db: $(DB_NAME))...$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) shell -d $(DB_NAME) \
		--addons-path=$(ODOO_ADDONS)

drop: ## Drop fms_e2e database (WARNING: deletes all data!)
	@echo "$(RED)WARNING: This will delete $(DB_NAME)$(NC)"
	@read -p "Type 'yes' to confirm: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		dropdb $(DB_NAME); \
		echo "$(GREEN)✓ $(DB_NAME) dropped$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled$(NC)"; \
	fi

reset: ## Drop + setup + seed fms_e2e from scratch
	@echo "$(RED)WARNING: Deletes and recreates $(DB_NAME)$(NC)"
	@read -p "Type 'yes' to confirm: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		dropdb --if-exists $(DB_NAME); \
		$(MAKE) setup && $(MAKE) seed; \
		echo "$(GREEN)✓ Reset complete. Run: make run$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled$(NC)"; \
	fi

build: ## Full build: drop + setup + seed (same as reset but no confirmation)
	@echo "$(BLUE)Full build of $(DB_NAME)...$(NC)"
	@dropdb --if-exists $(DB_NAME) || true
	@$(MAKE) setup
	@$(MAKE) seed
	@echo "$(GREEN)✓ Build complete. Run: make run$(NC)"

# ═════════════════════════════════════════════════════════════════════════════
# TESTING  (uses separate test_fms DB, recreated each run)
# ═════════════════════════════════════════════════════════════════════════════

test: ## Run FMS test suite (drops + recreates test_fms)
	@echo "$(BLUE)Running FMS tests (db: $(TEST_DB))...$(NC)"
	@dropdb --if-exists $(TEST_DB)
	@$(ODOO_VENV) $(ODOO_BIN) -d $(TEST_DB) \
		--addons-path=$(ODOO_ADDONS) \
		--test-enable --stop-after-init -i fms,fms_accounting --without-demo=all -p 8072 \
		--test-tags fms,fms_accounting
	@echo "$(GREEN)✓ Tests complete$(NC)"

test-unit: ## Run unit tests only (no integration tests)
	@$(PYTEST) tests/ -v -m "not integration"

test-coverage: ## Run tests with HTML coverage report
	@$(PYTEST) tests/ -v --cov=models/ --cov-report=html --cov-report=term
	@echo "$(GREEN)✓ Coverage: htmlcov/index.html$(NC)"

test-watch: ## Run tests in watch mode (requires pytest-watch)
	@ptw tests/ -v

test-specific: ## Run one test file (usage: make test-specific TEST=test_fms_shift.py)
	@if [ -z "$(TEST)" ]; then \
		echo "$(RED)Usage: make test-specific TEST=test_fms_shift.py$(NC)"; \
	else \
		$(PYTEST) tests/$(TEST) -v; \
	fi

test-task: ## Run tests for one task (usage: make test-task TASK=FMS-001)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Usage: make test-task TASK=FMS-001$(NC)"; \
	else \
		$(PYTEST) tests/ -v -k "$(shell echo $(TASK) | tr 'A-Z' 'a-z')" || true; \
	fi

# ═════════════════════════════════════════════════════════════════════════════
# TASK MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════

status: ## Show development progress
	@$(PYTHON) scripts/dev-guide.py status

task: ## Start a task (usage: make task TASK=FMS-001)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Usage: make task TASK=FMS-001$(NC)"; \
		$(PYTHON) scripts/dev-guide.py list; \
	else \
		$(PYTHON) scripts/dev-guide.py task $(TASK); \
	fi

list: ## List all development tasks
	@$(PYTHON) scripts/dev-guide.py list

info: ## Show task details (usage: make info TASK=FMS-001)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Usage: make info TASK=FMS-001$(NC)"; \
	else \
		$(PYTHON) scripts/dev-guide.py info $(TASK); \
	fi

report: ## Generate progress report
	@$(PYTHON) scripts/dev-guide.py report
	@echo "$(GREEN)✓ Report: REPORT.md$(NC)"

# ═════════════════════════════════════════════════════════════════════════════
# GIT
# ═════════════════════════════════════════════════════════════════════════════

git-status: ## Show git status
	@git status

git-branch: ## Create feature branch (usage: make git-branch TASK=FMS-001)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Usage: make git-branch TASK=FMS-001$(NC)"; \
	else \
		BRANCH="fms-$$(echo $(TASK) | tr '[:upper:]' '[:lower:]' | sed 's/-/_/g')"; \
		git checkout -b $$BRANCH; \
		echo "$(GREEN)✓ Branch: $$BRANCH$(NC)"; \
	fi

git-log: ## View recent commit history
	@git log --oneline --graph --all | head -20

git-commit: ## Interactive commit (stages all changes)
	@git add .
	@git commit

git-merge: ## Merge branch to main (usage: make git-merge BRANCH=fms-001)
	@if [ -z "$(BRANCH)" ]; then \
		echo "$(RED)Usage: make git-merge BRANCH=fms-001-core-models$(NC)"; \
	else \
		git checkout main; \
		git merge --no-ff $(BRANCH); \
		echo "$(GREEN)✓ Merged $(BRANCH) to main$(NC)"; \
	fi

git-tag: ## Tag task completion (usage: make git-tag TASK=FMS-001)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Usage: make git-tag TASK=FMS-001$(NC)"; \
	else \
		TAG="v0.$$(echo $(TASK) | sed 's/.*-//')-complete"; \
		git tag $$TAG; \
		echo "$(GREEN)✓ Tagged: $$TAG$(NC)"; \
	fi

# ═════════════════════════════════════════════════════════════════════════════
# DOCUMENTATION
# ═════════════════════════════════════════════════════════════════════════════

docs: ## List available documentation
	@echo "$(BLUE)FMS Documentation$(NC)"
	@echo ""
	@echo "$(YELLOW)Training guides:$(NC)"
	@echo "  make docs-setup-guide    Pre-first-shift system setup"
	@echo "  make docs-operations     Operations training (supervisors/attendants)"
	@echo "  make docs-finance        Finance training (accountants)"
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@echo "  make docs-spec           Technical specification"
	@echo "  make docs-dev            Development guide"
	@echo "  make docs-patterns       Coding patterns"
	@echo ""
	@echo "$(YELLOW)Operations:$(NC)"
	@echo "  make docs-runbook        Operations runbook"
	@echo "  make docs-install        Installation guide"

docs-setup-guide: ## View pre-first-shift system setup guide
	@less docs/training/00-system-setup-before-first-shift.md

docs-operations: ## View operations training guide (supervisors/attendants)
	@less docs/training/01-fms-operations-training.md

docs-finance: ## View finance training guide (accountants)
	@less docs/training/02-fms-finance-training.md

docs-quick: ## View quick start guide
	@less +G QUICK_START.md 2>/dev/null || cat QUICK_START.md

docs-setup: ## View setup summary
	@less +G SETUP_SUMMARY.md 2>/dev/null || cat SETUP_SUMMARY.md

docs-system: ## View system overview
	@less +G docs/SYSTEM_OVERVIEW.md 2>/dev/null || cat docs/SYSTEM_OVERVIEW.md

docs-dev: ## View development guide
	@less +G docs/FMS_DEVELOPMENT_SYSTEM_README.md 2>/dev/null || cat docs/FMS_DEVELOPMENT_SYSTEM_README.md

docs-spec: ## View technical specification
	@less +G docs/FMS_Complete_Specification_Technical_Guide.md 2>/dev/null || cat docs/FMS_Complete_Specification_Technical_Guide.md

docs-patterns: ## View coding patterns
	@less +G docs/fms-development.skill 2>/dev/null || cat docs/fms-development.skill

docs-runbook: ## View operations runbook
	@less docs/runbook/README.md 2>/dev/null || cat docs/runbook/README.md

docs-install: ## View installation guide
	@less +G docs/INSTALLATION.md 2>/dev/null || cat docs/INSTALLATION.md

docs-commands: ## View commands reference (make help)
	@$(MAKE) help

# ═════════════════════════════════════════════════════════════════════════════
# CODE QUALITY
# ═════════════════════════════════════════════════════════════════════════════

format: ## Auto-format Python with black
	@black models/ tests/ scripts/ 2>/dev/null || echo "$(YELLOW)Install: pip install black$(NC)"
	@echo "$(GREEN)✓ Formatted$(NC)"

lint: ## Check code style with flake8
	@flake8 models/ tests/ scripts/ 2>/dev/null || echo "$(YELLOW)Install: pip install flake8$(NC)"

syntax: ## Check Python syntax
	@$(PYTHON) -m py_compile models/*.py tests/*.py 2>/dev/null \
		&& echo "$(GREEN)✓ Syntax OK$(NC)" || echo "$(RED)✗ Syntax errors$(NC)"

check: ## Run syntax + tests + coverage
	@$(MAKE) syntax
	@$(MAKE) test-coverage

full-check: ## All checks before commit (syntax + test + coverage)
	@$(MAKE) syntax
	@$(MAKE) test
	@$(MAKE) test-coverage
	@echo "$(GREEN)✓ Ready to commit$(NC)"

# ═════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

install: ## Install Python test dependencies (pytest)
	@pip install pytest pytest-cov 2>/dev/null || pip3 install pytest pytest-cov
	@echo "$(GREEN)✓ Installed$(NC)"

install-dev: ## Install all dev dependencies (pytest + black + flake8)
	@pip install pytest pytest-cov black flake8 2>/dev/null || pip3 install pytest pytest-cov black flake8
	@echo "$(GREEN)✓ Installed$(NC)"

clean: ## Remove __pycache__, .pyc, coverage artifacts
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name ".coverage" -delete
	@rm -rf htmlcov/ .pytest_cache/ .tox/
	@echo "$(GREEN)✓ Cleaned$(NC)"

tree: ## Show project tree (2 levels)
	@tree -L 2 -a --gitignore 2>/dev/null || find . -maxdepth 2 -not -path '*/.*' | sort | sed 's|[^/]*/|  |g'

structure: ## List all project files
	@find . -type f -not -path './.git/*' -not -path '*/__pycache__/*' -not -name '*.pyc' | sort | head -60

project-info: ## Show environment info
	@echo "$(YELLOW)Project:$(NC) $(PROJECT_NAME)"
	@echo "$(YELLOW)DB:$(NC)      $(DB_NAME)  Port: $(ODOO_PORT)"
	@echo "$(YELLOW)Test DB:$(NC) $(TEST_DB)"
	@echo "$(YELLOW)Odoo:$(NC)    $(ODOO_BIN)"

version: ## Show version info
	@echo "$(YELLOW)Python:$(NC) $$($(PYTHON) --version)"
	@echo "$(YELLOW)Pytest:$(NC) $$($(PYTEST) --version 2>/dev/null || echo 'not installed')"
	@git --version 2>/dev/null || echo "git: not found"

# ═════════════════════════════════════════════════════════════════════════════
# COMBINED WORKFLOWS
# ═════════════════════════════════════════════════════════════════════════════

start-task: ## Start task workflow: branch + show prompt (usage: make start-task TASK=FMS-001)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Usage: make start-task TASK=FMS-001$(NC)"; \
	else \
		$(MAKE) git-branch TASK=$(TASK); \
		$(MAKE) task TASK=$(TASK); \
	fi

finish-task: ## Complete task: tag + merge (usage: make finish-task BRANCH=fms-001 TAG=FMS-001)
	@if [ -z "$(BRANCH)" ] || [ -z "$(TAG)" ]; then \
		echo "$(RED)Usage: make finish-task BRANCH=fms-001-core-models TAG=FMS-001$(NC)"; \
	else \
		$(MAKE) git-tag TASK=$(TAG); \
		$(MAKE) git-merge BRANCH=$(BRANCH); \
		$(MAKE) status; \
	fi

dev-cycle: ## status + test + report
	@$(MAKE) status
	@$(MAKE) test
	@$(MAKE) report

# ═════════════════════════════════════════════════════════════════════════════
# SHORTCUTS
# ═════════════════════════════════════════════════════════════════════════════

s: ## Alias: status
	@$(MAKE) status

t: ## Alias: test
	@$(MAKE) test

o: ## Alias: run
	@$(MAKE) run

h: ## Alias: help
	@$(MAKE) help

# ═════════════════════════════════════════════════════════════════════════════
# BACKWARD COMPAT — old names still work
# ═════════════════════════════════════════════════════════════════════════════

odoo:            run
odoo-dev:        run
odoo-shell:      shell
odoo-install:    setup
odoo-update:     upgrade
odoo-test:       test
odoo-e2e-create: setup
odoo-e2e-seed:   seed
odoo-e2e-update: upgrade
odoo-e2e:        run
odoo-e2e-drop:   drop

# ─────────────────────────────────────────────────────────────────────────────
# END
# ─────────────────────────────────────────────────────────────────────────────
