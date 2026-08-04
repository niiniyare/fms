#!/bin/bash
set -e

# ═════════════════════════════════════════════════════════════════════
# FMS Git Workflow Setup
# ═════════════════════════════════════════════════════════════════════
# 
# Initializes git repository with proper configuration:
# - Branches (main, development, feature branches)
# - Git hooks
# - Configuration
#
# Usage: bash setup-git-workflow.sh [PROJECT_ROOT]

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="${1:-.}"

echo -e "${BLUE}═════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}FMS Git Workflow Setup${NC}"
echo -e "${BLUE}═════════════════════════════════════════════════════════════${NC}\n"

# ═════════════════════════════════════════════════════════════════════
# 1. Check if git initialized
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Checking git status...${NC}"

if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo -e "${YELLOW}Git repository not found. Initializing...${NC}"
    cd "$PROJECT_ROOT"
    git init
    echo -e "${GREEN}✓ Git repository initialized${NC}"
else
    echo -e "${GREEN}✓ Git repository exists${NC}"
fi

cd "$PROJECT_ROOT"
echo ""

# ═════════════════════════════════════════════════════════════════════
# 2. Configure git
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Configuring git...${NC}"

git config user.name "${GIT_USER_NAME:-FMS Developer}" 2>/dev/null || echo -e "${YELLOW}→ Set git user name (git config user.name 'Your Name')${NC}"
git config user.email "${GIT_USER_EMAIL:-dev@fms.local}" 2>/dev/null || echo -e "${YELLOW}→ Set git user email (git config user.email 'email@example.com')${NC}"

echo -e "${GREEN}✓ Git configured${NC}"
echo ""

# ═════════════════════════════════════════════════════════════════════
# 3. Create main branch (if doesn't exist)
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Setting up branches...${NC}"

# Check if main branch exists
if ! git rev-parse --verify main > /dev/null 2>&1; then
    echo -e "${YELLOW}Creating main branch...${NC}"
    
    # Create initial commit if none exists
    if ! git rev-parse HEAD > /dev/null 2>&1; then
        touch README.md
        git add README.md
        git commit -m "Initial commit"
    fi
    
    # Rename master to main (if exists)
    if git rev-parse --verify master > /dev/null 2>&1; then
        git branch -m master main
        echo -e "${GREEN}✓ Renamed master → main${NC}"
    else
        # Create main from current branch
        git checkout -b main 2>/dev/null || true
        echo -e "${GREEN}✓ Created main branch${NC}"
    fi
else
    echo -e "${GREEN}✓ Main branch exists${NC}"
fi

# Create development branch (if doesn't exist)
if ! git rev-parse --verify development > /dev/null 2>&1; then
    git checkout -b development main
    echo -e "${GREEN}✓ Created development branch${NC}"
else
    echo -e "${GREEN}✓ Development branch exists${NC}"
fi

echo ""

# ═════════════════════════════════════════════════════════════════════
# 4. Create git hooks
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Setting up git hooks...${NC}"

mkdir -p .git/hooks

# Pre-commit hook (lint checks)
cat > .git/hooks/pre-commit << 'HOOK_EOF'
#!/bin/bash
# FMS Pre-Commit Hook
# Runs checks before allowing commit

set -e

echo "Running pre-commit checks..."

# Check for Python syntax errors
python_files=$(git diff --cached --name-only | grep '\.py$' || true)
if [ -n "$python_files" ]; then
    echo "Checking Python syntax..."
    python -m py_compile $python_files || {
        echo "❌ Python syntax error"
        exit 1
    }
fi

# Check for merge conflicts
if git diff --cached | grep -q "<<<<<<< HEAD"; then
    echo "❌ Unresolved merge conflicts"
    exit 1
fi

echo "✓ Pre-commit checks passed"
exit 0
HOOK_EOF

chmod +x .git/hooks/pre-commit
echo -e "${GREEN}✓ Created pre-commit hook${NC}"

# Prepare-commit-msg hook (add task reference)
cat > .git/hooks/prepare-commit-msg << 'HOOK_EOF'
#!/bin/bash
# FMS Prepare-Commit-Msg Hook
# Adds task reference template

COMMIT_MSG_FILE=$1
COMMIT_SOURCE=$2

# Only add template for new commits (not amends, squash, etc.)
if [ "$COMMIT_SOURCE" != "" ]; then
    exit 0
fi

# Get current branch name
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Extract task ID from branch name (e.g., fms-001-core-models -> FMS-001)
if [[ $BRANCH =~ fms-([0-9]+) ]]; then
    TASK_ID="FMS-${BASH_REMATCH[1]^^}"
    
    # Check if commit message already has task reference
    if ! grep -q "Task: $TASK_ID" "$COMMIT_MSG_FILE"; then
        # Add template at end of message
        cat >> "$COMMIT_MSG_FILE" << MSG_TEMPLATE

Ref: (Spec Section X.Y)
Task: $TASK_ID
Tests: (N/N passing)
Time: (X hours)
MSG_TEMPLATE
    fi
fi

exit 0
HOOK_EOF

chmod +x .git/hooks/prepare-commit-msg
echo -e "${GREEN}✓ Created prepare-commit-msg hook${NC}"

echo ""

# ═════════════════════════════════════════════════════════════════════
# 5. Create .gitattributes
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Creating git attributes...${NC}"

cat > .gitattributes << 'EOF'
# Auto-normalize line endings
* text=auto

# Python
*.py text eol=lf
*.pyw text eol=lf

# Shell
*.sh text eol=lf

# XML/YAML
*.xml text eol=lf
*.yaml text eol=lf
*.yml text eol=lf

# Markdown
*.md text eol=lf

# JSON
*.json text eol=lf

# Don't merge certain files
PROGRESS.md merge=ours
REPORT.md merge=ours
*.lock merge=ours
EOF

git add .gitattributes
echo -e "${GREEN}✓ Created .gitattributes${NC}"

echo ""

# ═════════════════════════════════════════════════════════════════════
# 6. Set up standard gitignore additions
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Verifying .gitignore...${NC}"

if [ -f ".gitignore" ]; then
    echo -e "${GREEN}✓ .gitignore exists${NC}"
else
    echo -e "${YELLOW}.gitignore not found${NC}"
fi

echo ""

# ═════════════════════════════════════════════════════════════════════
# 7. Initial commit
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Creating initial commit...${NC}"

# Check if there are uncommitted changes
if [ -z "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}→ No changes to commit${NC}"
else
    git add -A
    git commit -m "chore: initial FMS project structure setup" \
        -m "- Created Odoo 18 module structure
- Added model, view, security placeholders
- Created documentation templates
- Configured git workflow
- Set up gitignore and git hooks" || {
        echo -e "${YELLOW}→ Could not commit (already committed?)${NC}"
    }
    echo -e "${GREEN}✓ Initial commit created${NC}"
fi

echo ""

# ═════════════════════════════════════════════════════════════════════
# 8. Display workflow summary
# ═════════════════════════════════════════════════════════════════════

echo -e "${BLUE}═════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Git Workflow Setup Complete!${NC}"
echo -e "${BLUE}═════════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Current Status:${NC}"
git status --short || true

echo ""
echo -e "${YELLOW}Current Branch:${NC}"
git branch -a

echo ""
echo -e "${YELLOW}Recommended Workflow:${NC}\n"

echo "1. For each task (FMS-001, FMS-002, etc.):
   
   a. Create feature branch:
      $ git checkout development
      $ git checkout -b fms-001-core-models
   
   b. Make changes (add models, views, tests)
   
   c. Commit changes (hooks will add template):
      $ git add .
      $ git commit -m 'feat(models): implement core FMS models
      
      - fms.shift model
      - fms.pump and fms.pump.nozzle
      - fms.meter_log and fms.dip_log
      
      Ref: Spec Section 8.1
      Task: FMS-001
      Tests: 12/12 passing
      Time: 2h 34m'
   
   d. Tag task completion:
      $ git tag v0.1-core-models
   
   e. Merge to development:
      $ git checkout development
      $ git merge --no-ff fms-001-core-models
   
   f. Delete feature branch:
      $ git branch -d fms-001-core-models

2. When Phase 1 MVP complete:
   
   $ git checkout main
   $ git merge --no-ff development
   $ git tag v1.0.0-mvp

3. View commit history:
   $ git log --oneline --graph --all"

echo ""
echo -e "${YELLOW}Useful Commands:${NC}\n"

echo "  # Show log with graph
  $ git log --oneline --graph --all

  # Show commits for a task
  $ git log --oneline --grep='FMS-001'

  # Create release branch
  $ git checkout -b release/v1.0

  # Show what changed since main
  $ git diff main..development"

echo ""
echo -e "${GREEN}Ready to commit! 🚀${NC}\n"
