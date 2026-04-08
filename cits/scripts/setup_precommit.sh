#!/usr/bin/env bash
# Setup pre-commit hook for CITS that runs ruff check.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_PATH="${REPO_ROOT}/.git/hooks/pre-commit"

cat > "${HOOK_PATH}" << 'HOOK'
#!/usr/bin/env bash
# Pre-commit hook: lint CITS code with ruff
set -euo pipefail

echo "Running ruff check on cits/..."
ruff check cits/ --fix

# Re-add any files that were auto-fixed
git diff --name-only | grep '^cits/' | xargs -r git add
HOOK

chmod +x "${HOOK_PATH}"

echo "Pre-commit hook installed at ${HOOK_PATH}"
