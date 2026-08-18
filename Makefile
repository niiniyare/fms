.PHONY: help setup setup-all setup-structure setup-git clean status task list info report test test-coverage test-watch git-branch git-commit git-merge odoo odoo-dev odoo-install odoo-update odoo-shell odoo-test odoo-demo odoo-demo-reload odoo-drop docs runbook spec patterns install format lint

# Color output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Project variables
PROJECT_NAME := FMS (Forecourt Management System)
PYTHON := python3
PYTEST := pytest
DB_NAME := test_fms
ODOO_PORT := 8069

# Odoo / venv paths
ODOO_VENV    := /home/niini/odoo-venv/bin/python
ODOO_BIN     := /home/niini/odoo18/odoo-bin
# Addons: odoo core | fms custom | OCA addons
ODOO_ADDONS  := /home/niini/odoo18/addons,/home/niini/fms/..,/home/niini/oca/account-financial-reporting,/home/niini/oca/account-financial-tools,/home/niini/oca/account-reconcile,/home/niini/oca/credit-control,/home/niini/oca/web,/home/niini/oca/server-ux,/home/niini/oca/reporting-engine,/home/niini/oca/server-tools,/home/niini/oca/mis-builder

# Help target (default)
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║  $(GREEN)$(PROJECT_NAME)$(BLUE)  ║$(NC)"
	@echo "$(BLUE)║  Makefile - Common Development Tasks                    ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(YELLOW)SETUP (First Time Only):$(NC)"
	@grep -E '^\s+make (setup|clean)' Makefile | head -5
	@echo ""
	@echo "$(YELLOW)DEVELOPMENT:$(NC)"
	@grep -E '^\s+make (status|task|test|odoo)' Makefile | head -8
	@echo ""
	@echo "$(YELLOW)GIT WORKFLOW:$(NC)"
	@grep -E '^\s+make git-' Makefile | head -4
	@echo ""
	@echo "$(YELLOW)DOCUMENTATION:$(NC)"
	@grep -E '^\s+make (docs|spec|patterns|runbook)' Makefile | head -4
	@echo ""
	@echo "$(YELLOW)ALL TARGETS:$(NC)"
	@grep -E '^[a-z-]+:.*?##' Makefile | awk 'BEGIN {FS = ":.*?## "} {printf "  $(GREEN)%-25s$(NC) %s\n", $$1, $$2}' | sort

# ═════════════════════════════════════════════════════════════════════════════
# SETUP TARGETS
# ═════════════════════════════════════════════════════════════════════════════

setup: setup-all ## Complete project setup (project structure + git)

setup-all: ## Run complete setup (both structure and git)
	@echo "$(BLUE)Running complete FMS setup...$(NC)"
	@bash setup-fms-project.sh
	@bash setup-git-workflow.sh
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo "$(YELLOW)Next: make status$(NC)"

setup-structure: ## Create project directory structure only
	@echo "$(BLUE)Creating FMS project structure...$(NC)"
	@bash setup-fms-project.sh
	@echo "$(GREEN)✓ Structure created!$(NC)"

setup-git: ## Initialize git workflow only
	@echo "$(BLUE)Setting up git workflow...$(NC)"
	@bash setup-git-workflow.sh
	@echo "$(GREEN)✓ Git setup complete!$(NC)"

clean: ## Remove generated files (be careful!)
	@echo "$(RED)Cleaning generated files...$(NC)"
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name ".coverage" -delete
	@rm -rf htmlcov/ .pytest_cache/ .tox/
	@rm -f PROGRESS.md REPORT.md
	@echo "$(GREEN)✓ Cleaned!$(NC)"

# ═════════════════════════════════════════════════════════════════════════════
# DEVELOPMENT ORCHESTRATION TARGETS
# ═════════════════════════════════════════════════════════════════════════════

status: ## Show development status (completed/in-progress/todo tasks)
	@$(PYTHON) scripts/dev-guide.py status

task: ## Start specific task (usage: make task TASK=FMS-001)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Usage: make task TASK=FMS-001$(NC)"; \
		echo "$(YELLOW)Available tasks:$(NC)"; \
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

report: ## Generate development progress report
	@$(PYTHON) scripts/dev-guide.py report
	@echo "$(GREEN)✓ Report generated: REPORT.md$(NC)"

# ═════════════════════════════════════════════════════════════════════════════
# TESTING TARGETS
# ═════════════════════════════════════════════════════════════════════════════

test: ## Run all tests
	@echo "$(BLUE)Running tests...$(NC)"
	@$(PYTEST) tests/ -v
	@echo "$(GREEN)✓ Tests complete$(NC)"

test-unit: ## Run unit tests only (no integration tests)
	@echo "$(BLUE)Running unit tests...$(NC)"
	@$(PYTEST) tests/ -v -m "not integration"

test-coverage: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	@$(PYTEST) tests/ -v --cov=models/ --cov-report=html --cov-report=term
	@echo "$(GREEN)✓ Coverage report: htmlcov/index.html$(NC)"

test-watch: ## Run tests in watch mode (re-run on file changes)
	@echo "$(BLUE)Running tests in watch mode (requires pytest-watch)...$(NC)"
	@ptw tests/ -v

test-specific: ## Run specific test (usage: make test-specific TEST=test_fms_shift.py)
	@if [ -z "$(TEST)" ]; then \
		echo "$(RED)Usage: make test-specific TEST=test_fms_shift.py$(NC)"; \
	else \
		$(PYTEST) tests/$(TEST) -v; \
	fi

test-task: ## Run tests for specific task (usage: make test-task TASK=FMS-001)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Usage: make test-task TASK=FMS-001$(NC)"; \
	else \
		@echo "$(BLUE)Running tests for $(TASK)...$(NC)"; \
		$(PYTEST) tests/ -v -k "$(shell echo $(TASK) | tr 'A-Z' 'a-z')" || true; \
	fi

# ═════════════════════════════════════════════════════════════════════════════
# GIT WORKFLOW TARGETS
# ═════════════════════════════════════════════════════════════════════════════

git-status: ## Show git status
	@git status

git-branch: ## Create feature branch for task (usage: make git-branch TASK=FMS-001)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Usage: make git-branch TASK=FMS-001$(NC)"; \
		echo "$(YELLOW)Example: make git-branch TASK=FMS-001$(NC)"; \
	else \
		BRANCH_NAME="fms-$$(echo $(TASK) | tr '[:upper:]' '[:lower:]' | sed 's/-/_/g')-$$$(echo $(TASK) | sed 's/.*-//')"; \
		git checkout -b $$BRANCH_NAME; \
		echo "$(GREEN)✓ Created branch: $$BRANCH_NAME$(NC)"; \
	fi

git-log: ## View commit history (graph view)
	@git log --oneline --graph --all | head -20

git-commit: ## Make commit with task template
	@echo "$(BLUE)Committing with task template...$(NC)"
	@git add .
	@git commit
	@echo "$(GREEN)✓ Committed$(NC)"

git-merge: ## Merge feature branch to development (usage: make git-merge BRANCH=fms-001)
	@if [ -z "$(BRANCH)" ]; then \
		echo "$(RED)Usage: make git-merge BRANCH=fms-001-core-models$(NC)"; \
	else \
		git checkout development; \
		git merge --no-ff $(BRANCH); \
		echo "$(GREEN)✓ Merged $(BRANCH) to development$(NC)"; \
	fi

git-tag: ## Tag task completion (usage: make git-tag TASK=FMS-001)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Usage: make git-tag TASK=FMS-001$(NC)"; \
	else \
		TAG="v0.$$(echo $(TASK) | sed 's/.*-//')-$$(echo $(TASK) | sed 's/-.*//;s/[a-z]//g' | tr 'A-Z' 'a-z')"; \
		git tag $$TAG; \
		echo "$(GREEN)✓ Tagged: $$TAG$(NC)"; \
	fi

# ═════════════════════════════════════════════════════════════════════════════
# ODOO TARGETS
# ═════════════════════════════════════════════════════════════════════════════

odoo: ## Start Odoo web server (http://localhost:8069)
	@echo "$(BLUE)Starting Odoo (db: $(DB_NAME), port: $(ODOO_PORT))...$(NC)"
	@echo "$(YELLOW)Open: http://localhost:$(ODOO_PORT)$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) -d $(DB_NAME) -p $(ODOO_PORT) \
		--addons-path=$(ODOO_ADDONS) --dev=all

odoo-dev: ## Start Odoo web server on port 8070 (use when 8069 is busy)
	@echo "$(BLUE)Starting Odoo on port 8070 (db: $(DB_NAME))...$(NC)"
	@echo "$(YELLOW)Open: http://localhost:8070$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) -d $(DB_NAME) -p 8070 \
		--addons-path=$(ODOO_ADDONS) --dev=all

odoo-shell: ## Open Odoo interactive Python shell
	@echo "$(BLUE)Opening Odoo shell (db: $(DB_NAME))...$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) shell -d $(DB_NAME) \
		--addons-path=$(ODOO_ADDONS)

odoo-install: ## Install FMS module (first time)
	@echo "$(BLUE)Installing FMS module...$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) -d $(DB_NAME) -i fms \
		--addons-path=$(ODOO_ADDONS) --stop-after-init
	@echo "$(GREEN)✓ FMS installed$(NC)"

odoo-update: ## Update FMS module after code changes
	@echo "$(BLUE)Updating FMS module...$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) -d $(DB_NAME) -u fms \
		--addons-path=$(ODOO_ADDONS) --stop-after-init
	@echo "$(GREEN)✓ FMS updated$(NC)"

odoo-test: ## Run FMS tests (drops and recreates test DB to avoid demo data conflicts)
	@echo "$(BLUE)Running FMS tests (db: $(DB_NAME))...$(NC)"
	@dropdb --if-exists $(DB_NAME)
	@$(ODOO_VENV) $(ODOO_BIN) -d $(DB_NAME) \
		--addons-path=$(ODOO_ADDONS) \
		--test-enable --stop-after-init -i fms,fms_accounting --without-demo=all -p 8070 \
		--test-tags fms,fms_accounting
	@echo "$(GREEN)✓ Tests complete$(NC)"

odoo-demo: ## Start Odoo web server on the demo database (http://localhost:8070)
	@echo "$(BLUE)Starting Odoo with demo data (db: fms_demo, port: 8070)...$(NC)"
	@echo "$(YELLOW)Open: http://localhost:8070  →  Forecourt → Shifts$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) -d fms_demo -p 8070 \
		--addons-path=$(ODOO_ADDONS) --dev=all

odoo-demo-reload: ## Reload demo data into fms_demo (re-runs demo XML)
	@echo "$(BLUE)Reloading demo data into fms_demo...$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) -d fms_demo -u fms \
		--addons-path=$(ODOO_ADDONS) --stop-after-init -p 8070
	@echo "$(GREEN)✓ Demo data reloaded$(NC)"

odoo-e2e-create: ## Create fms_e2e DB with Kenya locale and install FMS modules
	@echo "$(BLUE)Creating fms_e2e database...$(NC)"
	$(ODOO_VENV) $(ODOO_BIN) -d fms_e2e \
		-i fms,fms_accounting \
		--addons-path=$(ODOO_ADDONS) \
		--stop-after-init --without-demo=all \
		--load-language=en_US
	@echo "$(GREEN)✓ fms_e2e created with FMS modules$(NC)"

odoo-e2e-seed: ## Seed fms_e2e with Kenya CoA + all products (run after odoo-e2e-create)
	@echo "$(BLUE)Seeding fms_e2e database...$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) shell -d fms_e2e \
		--addons-path=$(ODOO_ADDONS) --no-http \
		< scripts/seed_e2e.py
	@echo "$(GREEN)✓ Seed complete$(NC)"

odoo-e2e-update: ## Update fms + fms_accounting in fms_e2e after code changes
	@echo "$(BLUE)Updating fms_e2e...$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) -d fms_e2e -u fms,fms_accounting \
		--addons-path=$(ODOO_ADDONS) --stop-after-init --no-http
	@echo "$(GREEN)✓ fms_e2e updated$(NC)"

odoo-e2e: ## Start Odoo with the fms_e2e database (http://localhost:8070)
	@fuser -k 8070/tcp 2>/dev/null || true
	@echo "$(BLUE)Starting Odoo with fms_e2e on port 8070...$(NC)"
	@echo "$(YELLOW)Open: http://localhost:8070$(NC)"
	@$(ODOO_VENV) $(ODOO_BIN) -d fms_e2e -p 8070 \
		--addons-path=$(ODOO_ADDONS) --dev=all

odoo-e2e-drop: ## Drop fms_e2e database (WARNING: deletes all data!)
	@echo "$(RED)WARNING: This will delete fms_e2e$(NC)"
	@read -p "Type 'yes' to confirm: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		dropdb fms_e2e; \
		echo "$(GREEN)✓ fms_e2e dropped$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled$(NC)"; \
	fi

odoo-drop: ## Drop test database (WARNING: deletes all data!)
	@echo "$(RED)WARNING: This will delete all data in $(DB_NAME)$(NC)"
	@read -p "Type 'yes' to confirm: " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		dropdb $(DB_NAME); \
		echo "$(GREEN)✓ Database dropped$(NC)"; \
	else \
		echo "$(YELLOW)Cancelled$(NC)"; \
	fi

# ═════════════════════════════════════════════════════════════════════════════
# DOCUMENTATION TARGETS
# ═════════════════════════════════════════════════════════════════════════════

docs: ## Show list of available documentation
	@echo "$(BLUE)FMS Documentation$(NC)"
	@echo ""
	@echo "$(YELLOW)Getting Started:$(NC)"
	@echo "  make docs-quick          - Quick start guide"
	@echo "  make docs-setup          - Setup guide"
	@echo "  make docs-system         - System overview"
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@echo "  make docs-dev            - Development guide"
	@echo "  make docs-spec           - Technical specification"
	@echo "  make docs-patterns       - Coding patterns"
	@echo ""
	@echo "$(YELLOW)Operations:$(NC)"
	@echo "  make docs-runbook        - Operations runbook"
	@echo "  make docs-install        - Installation guide"
	@echo ""

docs-quick: ## View quick start guide
	@less +G QUICK_START.md 2>/dev/null || cat QUICK_START.md

docs-setup: ## View setup guide
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
	@less +G docs/RUNBOOK.md 2>/dev/null || cat docs/RUNBOOK.md

docs-install: ## View installation guide
	@less +G docs/INSTALLATION.md 2>/dev/null || cat docs/INSTALLATION.md

docs-commands: ## View commands reference (cheat sheet)
	@less +G COMMANDS_REFERENCE.md 2>/dev/null || cat COMMANDS_REFERENCE.md

# ═════════════════════════════════════════════════════════════════════════════
# CODE QUALITY TARGETS
# ═════════════════════════════════════════════════════════════════════════════

format: ## Format Python code (requires black)
	@echo "$(BLUE)Formatting Python code...$(NC)"
	@black models/ tests/ scripts/ 2>/dev/null || echo "$(YELLOW)black not installed (pip install black)$(NC)"
	@echo "$(GREEN)✓ Formatted$(NC)"

lint: ## Check code style (requires flake8)
	@echo "$(BLUE)Checking code style...$(NC)"
	@flake8 models/ tests/ scripts/ 2>/dev/null || echo "$(YELLOW)flake8 not installed (pip install flake8)$(NC)"

syntax: ## Check Python syntax
	@echo "$(BLUE)Checking Python syntax...$(NC)"
	@$(PYTHON) -m py_compile models/*.py tests/*.py 2>/dev/null && echo "$(GREEN)✓ Syntax OK$(NC)" || echo "$(RED)✗ Syntax errors$(NC)"

# ═════════════════════════════════════════════════════════════════════════════
# UTILITY TARGETS
# ═════════════════════════════════════════════════════════════════════════════

tree: ## Show project structure
	@tree -L 2 -a --gitignore 2>/dev/null || find . -maxdepth 2 -not -path '*/.*' | sort | sed 's|[^/]*/|  |g'

structure: ## Show detailed project structure
	@find . -type f -not -path './.git/*' -not -path '*/__pycache__/*' -not -path '*.pyc' | sort | head -50

install: ## Install Python dependencies
	@echo "$(BLUE)Installing dependencies...$(NC)"
	@pip install pytest pytest-cov 2>/dev/null || pip3 install pytest pytest-cov
	@echo "$(GREEN)✓ Installed$(NC)"

install-dev: ## Install development dependencies
	@echo "$(BLUE)Installing dev dependencies...$(NC)"
	@pip install pytest pytest-cov black flake8 2>/dev/null || pip3 install pytest pytest-cov black flake8
	@echo "$(GREEN)✓ Installed$(NC)"

check: ## Run all checks (syntax, tests, coverage)
	@echo "$(BLUE)Running all checks...$(NC)"
	@make syntax
	@make test-coverage
	@echo "$(GREEN)✓ All checks passed$(NC)"

project-info: ## Show project environment information
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║  Project Information                                      ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(YELLOW)Project:$(NC) $(PROJECT_NAME)"
	@echo "$(YELLOW)Python:$(NC)  $(PYTHON)"
	@echo "$(YELLOW)Odoo DB:$(NC)  $(DB_NAME)"
	@echo "$(YELLOW)Port:$(NC)    $(ODOO_PORT)"
	@echo ""
	@echo "$(YELLOW)Directories:$(NC)"
	@ls -d */ 2>/dev/null | head -10
	@echo ""
	@echo "$(YELLOW)Key Files:$(NC)"
	@ls -1 *.py *.yaml *.md 2>/dev/null | head -10
	@echo ""

version: ## Show version information
	@echo "$(BLUE)FMS Version Information$(NC)"
	@echo ""
	@echo "$(YELLOW)Python:$(NC) $$($(PYTHON) --version)"
	@echo "$(YELLOW)Pytest:$(NC) $$($(PYTEST) --version 2>/dev/null || echo 'not installed')"
	@echo ""
	@git --version 2>/dev/null || echo "git: not found"

# ═════════════════════════════════════════════════════════════════════════════
# COMBINED WORKFLOWS
# ═════════════════════════════════════════════════════════════════════════════

start-task: ## Complete workflow for a new task (usage: make start-task TASK=FMS-001)
	@if [ -z "$(TASK)" ]; then \
		echo "$(RED)Usage: make start-task TASK=FMS-001$(NC)"; \
	else \
		echo "$(BLUE)Starting task $(TASK)...$(NC)"; \
		make git-branch TASK=$(TASK); \
		make task TASK=$(TASK); \
		echo "$(GREEN)✓ Task $(TASK) started$(NC)"; \
		echo "$(YELLOW)Next: Run 'make test' after generating code$(NC)"; \
	fi

finish-task: ## Complete workflow after task is done (usage: make finish-task BRANCH=fms-001-core-models TAG=FMS-001)
	@if [ -z "$(BRANCH)" ] || [ -z "$(TAG)" ]; then \
		echo "$(RED)Usage: make finish-task BRANCH=fms-001-core-models TAG=FMS-001$(NC)"; \
	else \
		echo "$(BLUE)Finishing task $(TAG)...$(NC)"; \
		make git-tag TASK=$(TAG); \
		make git-merge BRANCH=$(BRANCH); \
		make status; \
		echo "$(GREEN)✓ Task $(TAG) complete$(NC)"; \
	fi

full-check: ## Run complete checks before commit
	@echo "$(BLUE)Running full checks...$(NC)"
	@make syntax
	@make test
	@make test-coverage
	@echo "$(GREEN)✓ All checks passed - ready to commit$(NC)"

dev-cycle: ## Complete development cycle (setup → test → commit → next)
	@echo "$(BLUE)Running development cycle...$(NC)"
	@make status
	@make test
	@make report
	@echo "$(GREEN)✓ Development cycle complete$(NC)"

# ═════════════════════════════════════════════════════════════════════════════
# QUICK ACTIONS
# ═════════════════════════════════════════════════════════════════════════════

s: ## Alias for 'status'
	@make status

t: ## Alias for 'test'
	@make test

o: ## Alias for 'odoo'
	@make odoo

h: ## Alias for 'help'
	@make help

# ═════════════════════════════════════════════════════════════════════════════
# INFORMATION
# ═════════════════════════════════════════════════════════════════════════════

.PHONY: info
info-all: ## Show comprehensive information
	@clear
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║  FMS Makefile - Comprehensive Guide                       ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(YELLOW)QUICK COMMANDS:$(NC)"
	@echo "  make help               Show all commands"
	@echo "  make status             Show development status"
	@echo "  make task TASK=FMS-001  Start development task"
	@echo "  make test               Run all tests"
	@echo "  make odoo               Start Odoo server"
	@echo ""
	@echo "$(YELLOW)SETUP:$(NC)"
	@echo "  make setup              Complete setup (recommended)"
	@echo "  make setup-structure    Create directories only"
	@echo "  make setup-git          Initialize git only"
	@echo ""
	@echo "$(YELLOW)DEVELOPMENT:$(NC)"
	@echo "  make status             View progress"
	@echo "  make task TASK=FMS-001  Start specific task"
	@echo "  make list               List all tasks"
	@echo "  make info TASK=FMS-001  Show task details"
	@echo "  make report             Generate progress report"
	@echo ""
	@echo "$(YELLOW)TESTING:$(NC)"
	@echo "  make test               Run all tests"
	@echo "  make test-coverage      Tests with coverage report"
	@echo "  make test-task TASK=FMS-001  Tests for specific task"
	@echo ""
	@echo "$(YELLOW)GIT:$(NC)"
	@echo "  make git-status         Show git status"
	@echo "  make git-branch TASK=FMS-001  Create feature branch"
	@echo "  make git-log            View commit history"
	@echo "  make git-commit         Make commit (with template)"
	@echo ""
	@echo "$(YELLOW)DOCUMENTATION:$(NC)"
	@echo "  make docs               List available docs"
	@echo "  make docs-quick         Quick start guide"
	@echo "  make docs-dev           Development guide"
	@echo "  make docs-spec          Technical specification"
	@echo "  make docs-commands      Command reference"
	@echo ""
	@echo "$(YELLOW)ODOO:$(NC)"
	@echo "  make odoo               Start server"
	@echo "  make odoo-install       Install FMS module"
	@echo "  make odoo-shell         Open interactive shell"
	@echo ""
	@echo "$(YELLOW)SHORTCUTS:$(NC)"
	@echo "  make s                  = make status"
	@echo "  make t                  = make test"
	@echo "  make o                  = make odoo"
	@echo "  make h                  = make help"
	@echo ""
	@make info

# ═════════════════════════════════════════════════════════════════════════════
# END OF MAKEFILE
# ═════════════════════════════════════════════════════════════════════════════
