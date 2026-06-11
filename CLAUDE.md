# CLAUDE.md

Guidance for AI assistants (Claude Code) working in this repository.

## What this is

**HIROKI AI Empire** — a 4-system automated revenue platform for a Japanese
real estate / construction coordinator ("HIROKI"). It generates and posts
Japanese X (Twitter) content, processes freelance orders into PDF deliverables,
collects market data, and broadcasts results — all gated by an AI quality
checker.

- **Primary language of content, prompts, and comments is Japanese (`ja`).**
  Match this when writing user-facing strings, prompts, and posts. Code
  identifiers and docstrings are English.
- All scheduling is **JST (Asia/Tokyo)**.
- Python **3.12**. Node is only used for the X MCP server (`@mbelinky/x-mcp-server`).

### The four systems

| System | Dir | Role |
|---|---|---|
| **A** | `system_a/` | X hybrid posting pipeline (generate → fact-check → quality-check → image → post) |
| **B** | `system_b/` | Order processing engine (order → data → report → PDF delivery) |
| **C** | `system_c/` | Data-collection agent crew (real estate, market, regulation, tech trends) |
| **D** | `system_d/` | Results broadcasting (turns B/C output into X content, fed back into A) |

Plus `inquiry_bot/` — a FastAPI LINE/web chatbot, deployed separately on Render.

`core/` holds shared modules used across all systems:
`claude_client.py`, `quality_checker.py`, `fact_checker.py`, `image_generator.py`,
`pdf_generator.py`, `sheets_client.py`, `notifier.py`, `engagement_learner.py`.

`README.md` has a full architecture writeup, data-flow diagrams, the content
"5 pillars," the product lineup, and the quality-gate scoring rubric. Read it
for domain detail. **Where the README and actual code/config disagree, the
code is the source of truth** (see Gotchas).

## Setup & commands

`PYTHONPATH` must include the repo root so `core/` etc. resolve. The Makefile
and the web SessionStart hook set this automatically; in a raw shell, prefix
with `PYTHONPATH=.`.

```bash
pip install -r requirements.txt      # Python deps
npm install                          # X MCP server (Node)
cp config/.env.example .env          # then fill in API keys

make help                            # full command list
make test                            # pytest tests/ -v --tb=short  (PYTHONPATH=. set)
make lint                            # ruff check, see below
```

### Testing

```bash
PYTHONPATH=. python -m pytest tests/ -q     # 305 tests, ~4s, all should pass
```

- `tests/conftest.py` sets **dummy env vars** and provides a
  `mock_claude_client` fixture. **Tests must never make real Claude/X/network
  calls** — mock `core.claude_client.Anthropic` (and any HTTP client) as the
  existing tests do. Add fixtures to `conftest.py` rather than re-stubbing.
- There is one test file per module (`test_<module>.py`). Add tests alongside
  the matching pattern when you add or change behavior.

### Linting

```bash
ruff check inquiry_bot/ core/ system_a/ system_b/ system_c/ system_d/ --select E,W,F --ignore E501
```

`E501` (line length) is intentionally ignored. CI lints only `inquiry_bot/`
and `core/`, but run the full set before pushing.

## Conventions

- **Claude API access goes through `core/claude_client.py`** (`ClaudeClient`).
  Use `.generate()` for text and `.generate_json()` for structured output —
  the latter already strips markdown code fences before `json.loads`. Don't
  instantiate `anthropic.Anthropic` directly elsewhere.
- **Prompts live in `prompts/*.txt`** as templates with `{placeholder}` tokens
  filled by `str.replace`. Edit prompt behavior there, not inline in code.
- **Report output templates** are Markdown in `templates/`, rendered to PDF via
  `core/pdf_generator.py` (WeasyPrint).
- **Quality gate**: every generated artifact passes through
  `core/quality_checker.py` with one of three profiles — `x_post` (threshold
  84), `report` (75), `data_collection` (70). Failures retry up to
  `max_retries` (3), then escalate via `core/notifier.py` (LINE/Slack). Logs
  land in `data/quality_logs/`. Preserve this gate when touching generation
  flows.
- **System A also runs `core/fact_checker.py`** before the quality check —
  posts with unverifiable factual claims are rejected, not just low-scored.
- Logging uses the stdlib `logging` module (`logger = logging.getLogger(__name__)`),
  not `print`, in library code.
- Config is centralized in `config/config.yaml` (thresholds, ratios, schedules,
  models). Read settings from there rather than hardcoding.

## Data & secrets

- `data/` and `reports/` are **gitignored**, but the X auto-post workflow
  **force-adds `data/`** (`git add -f data/`) and commits generated posts back
  to `main`. The steady stream of `auto: X post data update ...` commits comes
  from this. Don't be surprised by, or try to "clean up," that committed data.
- Secrets come from `.env` locally (loaded via `python-dotenv`), GitHub Actions
  Secrets in CI, and Render env vars in prod. **Never commit real keys**;
  `config/credentials.json` and `config/google_credentials.json` are gitignored.
  Keep `config/.env.example` in sync when you add a new variable.

## CI / deploy

- `.github/workflows/x-auto-post.yml` — daily **18:30 JST** (`cron: 30 9 * * *`,
  UTC), runs `python -m system_a.generate_and_post`, commits new data, pushes.
  Supports `workflow_dispatch` with `pillar` (1–5) and `dry_run` inputs.
- `.github/workflows/deploy-bot.yml` — on push/PR to `main` touching
  `inquiry_bot/**` or `core/**`: runs pytest + ruff, then on `main` push fires
  the Render deploy hook and Slack notification; also validates the bot YAML
  files.
- `render.yaml` deploys `inquiry_bot` as a free FastAPI web service
  (`uvicorn inquiry_bot.server:app`), health check `/api/health`. cron-job.org
  hits its trigger API to run System A/C, avoiding paid cron.

## Gotchas (code vs. README)

- **Posting cadence**: `README.md` describes a 3-posts/day, 3-pipeline
  orchestration (`system_a/daily_pipeline.py`). The **live production path is
  1 post/day** via `system_a/generate_and_post.py` (Pipeline 3 / `ai_original.txt`),
  driven by the GitHub Action. `config/config.yaml` agrees: `posts_per_day: 1`,
  `post_times: ["19:00"]`. Treat `generate_and_post.py` as the current entry
  point.
- **Model id mismatch**: `core/claude_client.py` `DEFAULT_MODEL` is
  `claude-sonnet-4-5-20250929`; `config/config.yaml` still lists
  `claude-sonnet-4-20250514`. The client default wins unless a caller passes a
  model explicitly. When upgrading models, prefer the latest Claude model and
  update both places.
- `render.yaml` pins `branch: claude/navigate-desktop-AYs6B` for auto-deploy —
  not `main`.

## Git workflow for this session

- Develop on branch **`claude/claude-md-docs-fp71kr`**; create it locally if
  missing. Don't push to other branches without explicit permission.
- Commit with clear messages; push with `git push -u origin <branch>`.
- **Do not open a pull request unless explicitly asked.**
