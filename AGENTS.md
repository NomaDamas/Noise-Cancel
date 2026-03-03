# AGENTS.md — NoiseCancel v2 Project Context

## What This Project Does

AI-powered multi-platform social feed noise filter. Scrapes home feeds from LinkedIn, X (Twitter), Threads, Reddit, and RSS; classifies posts with Claude API (per-platform prompts); deduplicates across platforms with semantic similarity; and delivers curated content. Monorepo with Python core library + CLI, FastAPI REST API server, and Flutter cross-platform mobile app (Tinder-style swipe UI with archive browsing).

## Monorepo Layout

```
noise-cancel/
├── noise_cancel/          # Python core library (existing, DO NOT break)
│   ├── cli.py             # Typer CLI commands
│   ├── config.py          # YAML + env config loading (AppConfig pydantic model)
│   ├── models.py          # Pydantic models: Post, Classification, RunLog
│   ├── database.py        # SQLite connection + migration runner
│   ├── scraper/           # Platform scrapers (base.py, linkedin.py, x.py, threads.py, reddit.py, rss.py, auth.py, anti_detection.py)
│   ├── classifier/        # Claude API batch classification (engine, prompts, schemas) — per-platform prompts
│   ├── dedup/             # Semantic dedup (embedder.py, semantic.py) — optional embedding-based cross-platform dedup
│   ├── delivery/          # Plugin-based delivery (base.py, loader.py, slack.py, blocks.py)
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
- **Playwright** — Browser scraping (LinkedIn, X, Threads)
- **PRAW** — Reddit API wrapper (OAuth)
- **feedparser** — RSS/Atom feed parsing
- **sentence-transformers** (optional) — Local embedding for semantic dedup
- **Claude API (anthropic)** — Post classification + dedup verification + daily digest
- **httpx** — HTTP client (Python side)
- **share_plus** (Flutter) — Native OS share sheet

## Critical Rules

1. **TDD**: Write tests first, then implement. Every story must have tests.
2. **`make check` must pass**: `ruff lint + ruff format + ty check + deptry`. Run before declaring any story done.
3. **`make test` must pass**: `pytest --doctest-modules`. All existing + new tests green.
4. **Do not break existing code**: The `noise_cancel/` package and all existing tests must continue to work. The CLI (`noise-cancel` command) must remain functional.
5. **Raw SQL only**: Use `sqlite3` directly — no ORM, no SQLAlchemy.
6. **Pydantic models**: All data classes must extend `pydantic.BaseModel`.
7. **Backward compatibility**: Config changes must support old format as fallback. Users who upgrade should not need to rewrite their config.yaml.

## v2 Scope (prd.json stories)

15 user stories across 5 phases. Closes GitHub issues #1, #11, #12, #16, #17, #22, #23, #24.

### Phase 1: Core Foundation
- **US-001**: Multi-platform scraper architecture — ScraperRegistry, per-platform config, pipeline iterates enabled platforms
- **US-002**: Regex keyword matching — whitelist/blacklist as `re.Pattern`, remove from LLM prompt (#1)
- **US-003**: Per-platform classifier prompts — `classifier.platform_prompts` dict with system_prompt overrides

### Phase 2: Platform Scrapers
- **US-004**: X (Twitter) scraper — Playwright, home timeline, encrypted session (#17)
- **US-005**: Threads scraper — Playwright, home feed, encrypted session (#17)
- **US-006**: Reddit scraper — PRAW + OAuth, home feed, free tier (#17)
- **US-007**: RSS feed integration — feedparser, arbitrary feed URLs (#16)

### Phase 3: Dedup & Stability
- **US-008**: Semantic dedup — embedding similarity + Claude verification, configurable provider, optional (#new)
- **US-009**: Session expiry notification — pre-expiry warning + post-expiry alert via delivery plugins (#24)

### Phase 4: App UX
- **US-010**: Flutter platform indicator — platform badge with brand colors on cards (#17)
- **US-011**: Archive view + search — "저장고" button, keyword search, platform filter, newest-first (#new)
- **US-012**: Post notes/comments — long-press to add memo, notes table, indicator icon (#12)
- **US-013**: Cross-platform share — share_plus package, native share sheet (#11)

### Phase 5: AI & Feedback
- **US-014**: AI unified daily digest — Claude summarization across all platforms, delivery plugin (#23)
- **US-015**: Feedback data accumulation — store swipe decisions for future learning (#22)

## DB Schema (after all migrations)

```sql
-- run_logs: pipeline execution tracking
run_logs(id TEXT PK, run_type TEXT, started_at TEXT, finished_at TEXT,
         status TEXT, posts_scraped INT, posts_classified INT,
         posts_delivered INT, error_message TEXT)

-- posts: scraped social feed posts (multi-platform)
posts(id TEXT PK, platform TEXT, author_name TEXT, author_url TEXT,
      post_url TEXT UNIQUE, post_text TEXT, content_hash TEXT UNIQUE,
      media_type TEXT, post_timestamp TEXT, scraped_at TEXT, run_id TEXT FK→run_logs)

-- classifications: AI classification results
classifications(id TEXT PK, post_id TEXT UNIQUE FK→posts, category TEXT,
                confidence REAL, reasoning TEXT, summary TEXT,
                applied_rules TEXT, model_used TEXT, classified_at TEXT,
                delivered INT, delivered_at TEXT,
                swipe_status TEXT DEFAULT 'pending',  -- migration 003
                swiped_at TEXT)                        -- migration 003

-- New tables (v2):
-- embeddings: semantic dedup vectors (migration 005)
embeddings(post_id TEXT PK FK→posts, vector BLOB, model TEXT, created_at TEXT)

-- notes: user notes on posts (migration 006)
notes(id TEXT PK, classification_id TEXT UNIQUE FK→classifications,
      note_text TEXT, created_at TEXT, updated_at TEXT)

-- feedback: swipe action data for future learning (migration 007)
feedback(id TEXT PK, classification_id TEXT FK→classifications,
         action TEXT, platform TEXT, category TEXT, confidence REAL, created_at TEXT)
```

`swipe_status` values: `'pending'` | `'archived'` | `'deleted'`
`platform` values: `'linkedin'` | `'x'` | `'threads'` | `'reddit'` | `'rss'`

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
| GET | `/api/posts` | Feed for swipe UI (category, swipe_status, platform, q params) |
| GET | `/api/posts/{classification_id}` | Single post detail |
| POST | `/api/posts/{classification_id}/archive` | Swipe left — archive |
| POST | `/api/posts/{classification_id}/delete` | Swipe right — delete |
| POST | `/api/posts/{classification_id}/note` | Create/update note |
| GET | `/api/posts/{classification_id}/note` | Get note |
| DELETE | `/api/posts/{classification_id}/note` | Delete note |
| POST | `/api/pipeline/run` | Trigger scrape+classify (background task) |
| GET | `/api/pipeline/status` | Latest pipeline run status |
| POST | `/api/digest/generate` | Generate and return daily digest |
| GET | `/api/feedback/stats` | Feedback data analytics |

## Flutter App Architecture

- **Webhook forwarding is client-side** — the app stores webhook URL + JSON template in local secure storage and forwards archived posts directly from the device. No webhook config on the server.
- Dark theme (#121212 background, #1E1E1E cards)
- `flutter_card_swiper` for Tinder-style swiping
- `provider` for state management
- `flutter_secure_storage` for settings persistence
- **New screens**: ArchiveScreen (저장고 — keyword search, platform filter, infinite scroll)
- **New widgets**: platform badge (brand color + icon per platform), note indicator, share button
- **Platform colors**: LinkedIn (#0A66C2), X (#000000), Threads (#000000), Reddit (#FF4500), RSS (#F26522)

## Commands

```bash
make check          # Lint + format + type check + dependency check
make test           # Run all Python tests
make server         # Start FastAPI dev server (port 8012)
make test-server    # Run server tests only
cd app && flutter run        # Run Flutter app
cd app && flutter analyze    # Dart static analysis
```
