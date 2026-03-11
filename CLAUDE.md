# IntelFlow — AI-Powered Daily Intelligence Engine

## Project Overview

IntelFlow is an open-source, self-hosted AI intelligence briefing system. It collects data from 30+ sources across configurable dimensions, uses AI models (Claude/Gemini) for deep analysis, generates bilingual reports, and auto-publishes to multiple platforms.

## Project Structure

```
IntelFlow/
├── config/          # User configuration (gitignored, use *.example to start)
├── scripts/         # Data collection, processing, and publishing scripts
├── templates/       # Report generation templates
├── web/             # Flask web UI for configuration
│   ├── app.py       # Flask application
│   ├── static/      # CSS, JS
│   └── templates/   # HTML templates (Jinja2)
├── output/          # Generated reports (gitignored)
├── state/           # Runtime state, locks, logs (gitignored)
├── assets/          # Static assets (style reference images)
└── docs/            # User-facing documentation
```

## Key Scripts

| Script | Purpose |
|--------|---------|
| `run_daily.sh` | Main pipeline orchestrator |
| `collect_*.py` | Data collection (one per source type) |
| `prepare_briefing.py` | Aggregate + score + dedup raw data |
| `split_briefing.py` | Split briefing into per-dimension files |
| `assemble_report.py` | Combine section MDs into final report |
| `publish_*.py` | Platform-specific publishers |
| `utils.py` | Shared utilities |

## Pipeline Flow

1. Parallel data collection (8 scripts, 10min timeout each)
2. `prepare_briefing.py` → `briefing.json`
3. `split_briefing.py` → dimension data files in `sections/`
4. Parallel AI generation (one call per dimension)
5. `assemble_report.py` → `daily_zh.md` + `daily_en.md`
6. Optional: AI cover images, style review, fact-check
7. Auto-publish to configured platforms

## Configuration

All user config lives in `config/` (gitignored). Start from `*.example` files.
API keys go in `.env` (gitignored). Start from `.env.example`.

## Development Notes

- Python 3.11+ required
- Flask for web UI (port 5050)
- All scripts use `ROOT = Path(__file__).resolve().parent.parent` pattern
- Config loaded via `utils.load_config()` helper
- No personal information should ever be committed
