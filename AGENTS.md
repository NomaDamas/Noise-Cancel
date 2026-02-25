# AGENTS.md — NoiseCancel Project Context

## What This Project Does

AI-powered LinkedIn feed noise filter. Scrapes LinkedIn feed via Playwright, classifies posts with Claude API, and delivers curated content. Currently a CLI tool being extended into a monorepo with a FastAPI REST API server and Flutter cross-platform mobile app (Tinder-style swipe UI).

## Monorepo Layout

```
noise-cancel/
├── noise_cancel/          # Python core library (existing, DO NOT break)
│   ├── cli.py             # Typer CLI commands
│   ├── config.py          # YAML + env config loading (AppConfig pydantic model)
│   ├── models.py          # Pydantic models: Post, Classification, RunLog
│   ├── database.py        # SQLite connection + migration runner
│   ├── scraper/           # LinkedIn scraping (Playwright, Fernet auth, anti-detection)
│   ├── classifier/        # Claude API batch classification (engine, prompts, schemas)
│   ├── delivery/          # Slack webhook (slack.py, blocks.py)
│   └── logger/            # DB queries (repository.py), metrics, export
├── server/                # FastAPI REST API (new, imports from noise_cancel/)
│   ├── main.py            # App factory, lifespan, CORS
│   ├── dependencies.py    # FastAPI Depends() for db + config
│   ├── schemas.py         # API Pydantic request/response models
│   ├── routers/           # posts.py, actions.py, pipeline.py
│   └── services/          # pipeline.py, post.py, action.py
├── app/                   # Flutter mobile app (new)
│   └── lib/               # Dart source (models, services, screens, widgets)
├── migrations/            # SQL migration files (001, 002, 003...)
├── tests/                 # Python tests for noise_cancel/
├── tests_server/          # Python tests for server/
├── prd.md                 # Product requirements document
└── prd.json               # Machine-readable PRD for Ralph loop
```

## Tech Stack

- **Python 3.10+** — core + server
- **FastAPI + Uvicorn** — REST API server
- **Flutter/Dart** — cross-platform mobile app
- **SQLite** — database (WAL mode, foreign keys ON)
- **Pydantic** — all data models
- **Playwright** — LinkedIn scraping
- **Claude API (anthropic)** — post classification
- **httpx** — HTTP client (Python side)

## Critical Rules

1. **TDD**: Write tests first, then implement. Every story must have tests.
2. **`make check` must pass**: `ruff lint + ruff format + ty check + deptry`. Run before declaring any story done.
3. **`make test` must pass**: `pytest --doctest-modules`. All existing + new tests green.
4. **Do not break existing code**: The `noise_cancel/` package and all existing tests must continue to work. The CLI (`noise-cancel` command) must remain functional.
5. **Raw SQL only**: Use `sqlite3` directly — no ORM, no SQLAlchemy.
6. **Pydantic models**: All data classes must extend `pydantic.BaseModel`.

## DB Schema (after all migrations)

```sql
-- run_logs: pipeline execution tracking
run_logs(id TEXT PK, run_type TEXT, started_at TEXT, finished_at TEXT,
         status TEXT, posts_scraped INT, posts_classified INT,
         posts_delivered INT, error_message TEXT)

-- posts: scraped LinkedIn posts
posts(id TEXT PK, platform TEXT, author_name TEXT, author_url TEXT,
      post_url TEXT UNIQUE, post_text TEXT, media_type TEXT,
      post_timestamp TEXT, scraped_at TEXT, run_id TEXT FK→run_logs)

-- classifications: AI classification results
classifications(id TEXT PK, post_id TEXT UNIQUE FK→posts, category TEXT,
                confidence REAL, reasoning TEXT, summary TEXT,
                applied_rules TEXT, model_used TEXT, classified_at TEXT,
                delivered INT, delivered_at TEXT,
                swipe_status TEXT DEFAULT 'pending',  -- migration 003
                swiped_at TEXT)                        -- migration 003
```

`swipe_status` values: `'pending'` | `'archived'` | `'deleted'`

## Migration System

- Files in `migrations/` named `NNN_description.sql`, applied in sorted order
- Tracked in `_migrations` table (auto-created by `database.py:apply_migrations()`)
- Uses `conn.executescript(sql)` — supports multiple statements per file
- New migrations are auto-detected on server startup

## Key Existing Functions to Reuse

### Repository (`noise_cancel/logger/repository.py`)
- `insert_post(conn, post)`, `insert_classification(conn, classification)`, `insert_run_log(conn, run_log)`
- `update_run_log(conn, run_id, **kwargs)` — allowed columns: finished_at, status, posts_scraped/classified/delivered, error_message
- `get_unclassified_posts(conn, limit)` — LEFT JOIN posts without classifications
- `get_run_logs(conn, limit, run_type, status)` — query run history
- `mark_delivered(conn, classification_id)` — sets delivered=1

### Config (`noise_cancel/config.py`)
- `load_config(config_path=None)` → `AppConfig` — loads YAML + env vars + defaults
- `AppConfig` has: `.general`, `.scraper`, `.classifier`, `.delivery` (all `dict[str, Any]`)

### Database (`noise_cancel/database.py`)
- `get_connection(db_path)` → `sqlite3.Connection` — WAL mode, foreign keys, Row factory
- `apply_migrations(conn)` — runs all pending SQL migrations

### Scraper (`noise_cancel/scraper/linkedin.py`)
- `LinkedInScraper(config)` — async, `.scrape_feed(scroll_count)` returns `list[Post]`

### Classifier (`noise_cancel/classifier/engine.py`)
- `ClassificationEngine(config)` — `.classify_posts(posts)` returns `list[PostClassification]`

## API Endpoints (server)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/posts` | Feed for swipe UI (filtered by category + swipe_status) |
| GET | `/api/posts/{classification_id}` | Single post detail |
| POST | `/api/posts/{classification_id}/archive` | Swipe left — archive |
| POST | `/api/posts/{classification_id}/delete` | Swipe right — delete |
| POST | `/api/pipeline/run` | Trigger scrape+classify (background task) |
| GET | `/api/pipeline/status` | Latest pipeline run status |

## Flutter App Architecture

- **Webhook forwarding is client-side** — the app stores webhook URL + JSON template in local secure storage and forwards archived posts directly from the device. No webhook config on the server.
- Dark theme (#121212 background, #1E1E1E cards)
- `flutter_card_swiper` for Tinder-style swiping
- `provider` for state management
- `flutter_secure_storage` for settings persistence

## Commands

```bash
make check          # Lint + format + type check + dependency check
make test           # Run all Python tests
make server         # Start FastAPI dev server (port 8000)
make test-server    # Run server tests only
cd app && flutter run        # Run Flutter app
cd app && flutter analyze    # Dart static analysis
```
