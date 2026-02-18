# NoiseCancel

AI-powered LinkedIn feed noise filter. Scrapes feed → classifies with Claude API → delivers to Slack.

## Stack
Python 3.9+ | Typer CLI | Playwright | Claude API (anthropic) | Slack SDK | SQLite | Pydantic

## Architecture
```
[LinkedIn Feed] → [Scraper/Playwright] → [SQLite] → [Classifier/Claude] → [Delivery/Slack]
```
CLI: `noise-cancel login|scrape|classify|deliver|run|logs|stats|feedback|config`

## Project Structure
```
noise_cancel/
├── cli.py              # Typer app, all CLI commands
├── config.py           # YAML + env var loading (pydantic-settings)
├── models.py           # Shared Pydantic models
├── database.py         # SQLite connection/migration
├── scraper/            # linkedin.py, auth.py, anti_detection.py, base.py
├── classifier/         # engine.py, prompts.py, schemas.py
├── delivery/           # slack.py, blocks.py, feedback.py
└── logger/             # repository.py, export.py, metrics.py
```

## Key Conventions
- TDD: write tests first, then implement
- `make check` = ruff lint + ruff format + ty check + deptry
- `make test` = pytest --doctest-modules
- Raw SQL with sqlite3 (no ORM)
- Fernet encryption for cookies
- Batch classification: 10 posts per Claude API call
- Config: `~/.config/noise-cancel/config.yaml` + `.env`

## DB Tables
posts, classifications, user_feedback, rules_history, run_logs

## Dependencies
typer, playwright, anthropic, pydantic, pydantic-settings, pyyaml, httpx, cryptography, rich, slack-sdk
