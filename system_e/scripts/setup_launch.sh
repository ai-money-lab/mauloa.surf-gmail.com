#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# System E — One-Click Launch Setup
# Automates pre-launch checks, content seeding, and deployment info.
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

# ─── Colors & Formatting ─────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ─── Resolve project root (two levels up from this script) ───────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# ─── Helper functions ────────────────────────────────────────────
info()    { echo -e "  ${BLUE}[INFO]${RESET}  $*"; }
ok()      { echo -e "  ${GREEN}[ OK ]${RESET}  $*"; }
warn()    { echo -e "  ${YELLOW}[WARN]${RESET}  $*"; }
fail()    { echo -e "  ${RED}[FAIL]${RESET}  $*"; }
section() { echo -e "\n${BOLD}${CYAN}── $* ──${RESET}"; }
prompt_yn() {
    local msg="$1" default="${2:-n}"
    if [[ "$default" == "y" ]]; then
        echo -en "  ${YELLOW}$msg [Y/n]:${RESET} "
    else
        echo -en "  ${YELLOW}$msg [y/N]:${RESET} "
    fi
    read -r answer
    answer="${answer:-$default}"
    [[ "$answer" =~ ^[Yy] ]]
}

# ═══════════════════════════════════════════════════════════════════
# 1. Banner
# ═══════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${CYAN}"
echo "  ================================================================="
echo "     System E  —  One-Click Launch Setup"
echo "     Maia AI Character Pipeline"
echo "  ================================================================="
echo -e "${RESET}"
echo -e "  ${DIM}This script will:${RESET}"
echo -e "    1. Verify all required environment variables"
echo -e "    2. Run the full launch readiness check"
echo -e "    3. Optionally seed 7 days of content"
echo -e "    4. Optionally run a dry-run of the pipeline"
echo -e "    5. Print GitHub Secrets and X account setup info"
echo ""
echo -e "  ${DIM}Project root: ${PROJECT_ROOT}${RESET}"
echo ""

# ═══════════════════════════════════════════════════════════════════
# 2. Environment Variable Check
# ═══════════════════════════════════════════════════════════════════
section "Step 1/5: Environment Variables"

MISSING=()
FOUND=()

check_env() {
    local var_name="$1"
    local required="${2:-required}"
    local val="${!var_name:-}"
    if [[ -n "$val" ]]; then
        ok "$var_name is set"
        FOUND+=("$var_name")
    elif [[ "$required" == "required" ]]; then
        fail "$var_name is NOT set"
        MISSING+=("$var_name")
    else
        warn "$var_name is not set (optional)"
    fi
}

# Load .env if present
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    info "Loading .env file..."
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env" 2>/dev/null || true
    set +a
fi

echo ""

# Core API key
check_env "ANTHROPIC_API_KEY"

# System E dedicated X account credentials
check_env "SYSTEM_E_X_API_KEY"
check_env "SYSTEM_E_X_API_SECRET_KEY"
check_env "SYSTEM_E_X_ACCESS_TOKEN"
check_env "SYSTEM_E_X_ACCESS_TOKEN_SECRET"
check_env "SYSTEM_E_X_BEARER_TOKEN"
check_env "SYSTEM_E_X_USER_ID" "optional"

# Fallback X credentials (used by posting_scheduler if SYSTEM_E_X_* not set)
check_env "X_API_KEY"
check_env "X_API_SECRET_KEY"
check_env "X_ACCESS_TOKEN"
check_env "X_ACCESS_TOKEN_SECRET"

# Image generation
check_env "RUNPOD_API_KEY" "optional"
check_env "RUNPOD_POD_ID" "optional"
check_env "FAL_API_KEY" "optional"
check_env "GEMINI_API_KEY" "optional"

# Notifications
check_env "LINE_CHANNEL_ACCESS_TOKEN" "optional"
check_env "LINE_USER_ID" "optional"

echo ""
if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo -e "  ${RED}${BOLD}Missing required variables (${#MISSING[@]}):${RESET}"
    for var in "${MISSING[@]}"; do
        echo -e "    ${RED}- $var${RESET}"
    done
    echo ""
    echo -e "  ${DIM}Set them in .env or export them before re-running this script.${RESET}"
    echo ""
    if ! prompt_yn "Continue anyway? (checks will likely fail)"; then
        echo -e "\n  Exiting. Set the missing variables and try again.\n"
        exit 1
    fi
else
    ok "All required environment variables are set."
fi

# ═══════════════════════════════════════════════════════════════════
# 3. Launch Readiness Check
# ═══════════════════════════════════════════════════════════════════
section "Step 2/5: Launch Readiness Check"
echo ""
info "Running: make system-e-check"
echo ""

CHECK_RESULT=0
PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}" python "$PROJECT_ROOT/system_e/scripts/launch_check.py" || CHECK_RESULT=$?

echo ""
if [[ $CHECK_RESULT -eq 0 ]]; then
    ok "Launch readiness check passed!"
else
    warn "Launch readiness check reported failures (exit code: $CHECK_RESULT)."
    warn "Review the output above and fix any FAIL items."
    if ! prompt_yn "Continue with remaining steps?"; then
        echo -e "\n  Fix the issues above and re-run this script.\n"
        exit 1
    fi
fi

# ═══════════════════════════════════════════════════════════════════
# 4. Seed Content (Optional)
# ═══════════════════════════════════════════════════════════════════
section "Step 3/5: Seed Content"
echo ""
info "Seeding pre-generates 7 days of content so the pipeline has"
info "posts ready to go from day one."
echo ""

if prompt_yn "Seed 7 days of content now?"; then
    echo ""
    info "Running: make system-e-seed"
    echo ""
    PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}" python "$PROJECT_ROOT/system_e/scripts/seed_content.py" --days 7 || {
        warn "Content seeding encountered errors. Check output above."
    }
    echo ""
    ok "Content seeding complete."
else
    info "Skipping content seeding. Run later with: make system-e-seed"
fi

# ═══════════════════════════════════════════════════════════════════
# 5. Dry Run (Optional)
# ═══════════════════════════════════════════════════════════════════
section "Step 4/5: Dry Run"
echo ""
info "A dry run initializes the full pipeline without posting."
info "This verifies that all modules load and connect correctly."
echo ""

if prompt_yn "Run a dry-run of the full pipeline?"; then
    echo ""
    info "Running dry-run..."
    echo ""
    PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}" python -c "
from system_e.daily_pipeline import SystemEPipeline
p = SystemEPipeline()
print('  SystemEPipeline initialized OK')
print(f'  Image provider: {p.image_pipeline.provider}')
print(f'  Image enabled:  {p.image_pipeline.enabled}')
print()

from system_e.content_generator import ContentGenerator
g = ContentGenerator()
print('  ContentGenerator initialized OK')

from system_e.posting_scheduler import PostingScheduler
s = PostingScheduler()
print('  PostingScheduler initialized OK')

from system_e.engagement_collector import EngagementCollector
e = EngagementCollector()
print('  EngagementCollector initialized OK')

from system_e.mention_responder import MentionResponder
r = MentionResponder()
print('  MentionResponder initialized OK')

from system_e.analytics import Analytics
a = Analytics()
print('  Analytics initialized OK')

print()
print('  All modules loaded successfully.')
" || {
        warn "Dry run encountered errors. Check output above."
    }
    echo ""
    ok "Dry run complete."
else
    info "Skipping dry run."
fi

# ═══════════════════════════════════════════════════════════════════
# 6. GitHub Secrets Reference
# ═══════════════════════════════════════════════════════════════════
section "Step 5/5: Deployment Information"
echo ""
echo -e "  ${BOLD}GitHub Secrets to configure:${RESET}"
echo -e "  ${DIM}(Settings > Secrets and variables > Actions > New repository secret)${RESET}"
echo ""
echo -e "  ${CYAN}Required:${RESET}"
echo "    ANTHROPIC_API_KEY              Anthropic API key for content generation"
echo "    X_API_KEY                      X/Twitter API key (consumer key)"
echo "    X_API_SECRET_KEY               X/Twitter API secret"
echo "    SYSTEM_E_X_ACCESS_TOKEN        System E dedicated X account access token"
echo "    SYSTEM_E_X_ACCESS_TOKEN_SECRET System E dedicated X account access token secret"
echo "    SYSTEM_E_X_BEARER_TOKEN        System E dedicated X account bearer token"
echo ""
echo -e "  ${CYAN}Image Generation (at least one):${RESET}"
echo "    RUNPOD_API_KEY                 RunPod API key"
echo "    RUNPOD_POD_ID                  RunPod GPU Pod ID (for ComfyUI)"
echo "    RUNPOD_ENDPOINT_ID             RunPod serverless endpoint ID"
echo "    FAL_API_KEY                    fal.ai API key"
echo "    GEMINI_API_KEY                 Google Gemini API key (Imagen fallback)"
echo ""
echo -e "  ${CYAN}Optional:${RESET}"
echo "    X_BEARER_TOKEN                 Main account bearer token (engagement)"
echo "    SYSTEM_E_X_API_KEY             System E dedicated API key (if separate app)"
echo "    SYSTEM_E_X_API_SECRET_KEY      System E dedicated API secret"
echo "    LINE_CHANNEL_ACCESS_TOKEN      LINE notifications"
echo "    LINE_USER_ID                   LINE user ID for alerts"
echo ""

# ═══════════════════════════════════════════════════════════════════
# 7. X Account Bio Text
# ═══════════════════════════════════════════════════════════════════
echo -e "  ${BOLD}X Account Bio (copy-paste to your profile):${RESET}"
echo ""
echo -e "  ${GREEN}┌─────────────────────────────────────────────────────────┐${RESET}"
echo -e "  ${GREEN}│${RESET}                                                         ${GREEN}│${RESET}"
echo -e "  ${GREEN}│${RESET}  Maia | AI wellness creator sharing mindful living &    ${GREEN}│${RESET}"
echo -e "  ${GREEN}│${RESET}  fitness                                                ${GREEN}│${RESET}"
echo -e "  ${GREEN}│${RESET}                                                         ${GREEN}│${RESET}"
echo -e "  ${GREEN}│${RESET}  AI-generated wellness creator | Powered by AI          ${GREEN}│${RESET}"
echo -e "  ${GREEN}│${RESET}                                                         ${GREEN}│${RESET}"
echo -e "  ${GREEN}└─────────────────────────────────────────────────────────┘${RESET}"
echo ""
echo -e "  ${DIM}The bio includes FTC-compliant AI disclosure.${RESET}"
echo -e "  ${DIM}Bio-based disclosure avoids per-post hashtags (+40% reach).${RESET}"
echo ""

# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════
echo -e "${BOLD}${CYAN}"
echo "  ================================================================="
echo "     Setup Complete!"
echo "  ================================================================="
echo -e "${RESET}"
echo -e "  ${BOLD}Next steps:${RESET}"
echo "    1. Set any missing GitHub Secrets (see list above)"
echo "    2. Set the X account bio text"
echo "    3. Consider subscribing to X Premium for 2-10x reach boost"
echo "    4. Enable the GitHub Actions workflow"
echo ""
echo -e "  ${BOLD}Useful commands:${RESET}"
echo "    make system-e          Run full pipeline"
echo "    make system-e-gen      Generate content only"
echo "    make system-e-post     Post scheduled content"
echo "    make system-e-engage   Collect engagement & reply to mentions"
echo "    make system-e-check    Re-run readiness check"
echo "    make system-e-seed     Seed content (7 days)"
echo ""
