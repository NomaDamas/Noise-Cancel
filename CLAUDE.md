# NoiseCancel

AI-powered LinkedIn feed noise filter in a monorepo. The existing CLI remains intact, and new server + mobile layers are added for a Tinder-style swipe experience.

## Stack
Python 3.10+ | Typer CLI | FastAPI + Uvicorn | Flutter | SQLite | Pydantic | Playwright | Claude API (anthropic)

## Monorepo Structure
```
noise-cancel/
├── noise_cancel/        # Existing Python core library + CLI (must remain stable)
├── server/              # FastAPI REST API that reuses noise_cancel modules
├── app/                 # Flutter mobile client (cross-platform)
├── migrations/          # SQL migrations applied by noise_cancel.database
├── tests/               # Core library tests
├── tests_server/        # FastAPI server tests
├── Makefile             # Dev commands for check, test, server, flutter-run
└── pyproject.toml       # Python project config + test/lint/type tooling
```

## Architecture
### Core Pipeline (`noise_cancel/`)
```
[LinkedIn Feed] -> [Scraper/Playwright] -> [SQLite] -> [Classifier/Claude] -> [Delivery]
```
CLI commands stay available: `noise-cancel login|scrape|classify|deliver|run|logs|stats|feedback|config|init`

### Server Architecture (`server/`)
- FastAPI app factory in `server.main:create_app()`
- Lifespan startup loads config, opens SQLite connection, and applies migrations
- Dependencies in `server/dependencies.py` provide DB + config via `request.app.state`
- Routers:
  - `GET /api/posts`, `GET /api/posts/{classification_id}`
  - `POST /api/posts/{classification_id}/archive`
  - `POST /api/posts/{classification_id}/delete`
  - `POST /api/pipeline/run`, `GET /api/pipeline/status`
- Services call existing `noise_cancel` components (scraper, classifier, repository)

### Flutter App (`app/`)
- Tinder-style swipe UI powered by `flutter_card_swiper`
- Swipe left archive, swipe right delete
- Dark theme (`#121212` background, `#1E1E1E` cards)
- `provider` for state management
- `flutter_secure_storage` for server URL + webhook settings
- Webhook forwarding happens client-side when archive swipe succeeds

## Conventions
- TDD first: tests before implementation
- `make check` runs lock/lint/format/type/dependency checks
- `make test` runs `tests/` and `tests_server/`
- Raw SQL with sqlite3 only (no ORM)
- Pydantic `BaseModel` for schema models
