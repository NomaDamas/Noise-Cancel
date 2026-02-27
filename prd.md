# PRD — NoiseCancel MVP Public Launch

## Project
- Name: NoiseCancel MVP
- Branch: main
- Description: Implement all MVP features required for public launch of NoiseCancel — an AI-powered LinkedIn feed noise filter for self-hosted users. Covers delivery plugin architecture, server security (API key auth + CORS config), duplicate post deduplication, clickable URLs in the Flutter app, and a comprehensive installation guide.

## User Stories

### US-001: Delivery plugin base architecture
- Title: Refactor delivery system to pluggable architecture with abstract base class
- Priority: 1
- Description: |
    Extract a `DeliveryPlugin` abstract base class in `noise_cancel/delivery/base.py`.
    Define the plugin contract: `deliver()` and `validate_config()` methods.
    Create a plugin registry/loader that resolves plugins by `type` string from config.
    Update `_DEFAULT_DELIVERY` in `noise_cancel/config.py` to use new `plugins` list format:
    ```yaml
    delivery:
      plugins:
        - type: slack
          webhook_url: ${SLACK_WEBHOOK_URL}
          include_categories: [Read]
          include_reasoning: true
          max_text_preview: 300
    ```
    The old `delivery.method` / `delivery.slack` format must still work as fallback for backward compatibility during transition.
- Acceptance Criteria:
  - REQ-001: `noise_cancel/delivery/base.py` exists with `DeliveryPlugin` ABC defining `deliver(posts, config) -> int` and `validate_config(config) -> None`
  - REQ-002: A plugin loader function exists that takes a plugin `type` string and returns the corresponding `DeliveryPlugin` subclass
  - REQ-003: Config supports `delivery.plugins` as a list of plugin configs, each with a `type` field
  - REQ-004: Legacy `delivery.method`/`delivery.slack` config format still works (auto-converted to plugins list internally)
  - REQ-005: Unit tests cover plugin loader, base class contract, and legacy config conversion

### US-002: Slack delivery plugin refactor
- Title: Refactor existing Slack delivery into a DeliveryPlugin subclass
- Priority: 2
- Description: |
    Convert `noise_cancel/delivery/slack.py` to implement `DeliveryPlugin`.
    The `SlackPlugin.deliver()` method replaces the current `deliver_posts()` function.
    `SlackPlugin.validate_config()` checks for webhook_url presence.
    Update `noise_cancel/cli.py` `deliver` command to use the plugin system — iterate over configured plugins and call `deliver()` on each.
    The `deliver` command's behavior must remain identical from the user's perspective.
- Acceptance Criteria:
  - REQ-006: `SlackPlugin` class in `noise_cancel/delivery/slack.py` extends `DeliveryPlugin`
  - REQ-007: `SlackPlugin.deliver()` sends posts to Slack webhook and returns delivered count (same behavior as current `deliver_posts()`)
  - REQ-008: `SlackPlugin.validate_config()` raises if webhook_url is missing from plugin config and env var `SLACK_WEBHOOK_URL` is not set
  - REQ-009: CLI `deliver` command uses plugin system to dispatch to all configured plugins
  - REQ-010: CLI `run` command (full pipeline) still works end-to-end with the refactored delivery
  - REQ-011: All existing delivery tests pass (updated to new plugin interface)
  - REQ-012: Server `POST /api/pipeline/run` still works with refactored delivery

### US-003: Configurable CORS origins
- Title: Make CORS origins configurable via config.yaml
- Priority: 3
- Description: |
    Replace hardcoded `allow_origins=["*"]` in `server/main.py` with a configurable list.
    Add a `server` section to the config system (new `_DEFAULT_SERVER` dict in `config.py`).
    Read `server.cors_origins` from config. Default to `["*"]` if not set (backward compatible).
    Log a warning at startup if wildcard origins are used.
    The `create_app()` function needs access to the config at construction time, so it must accept config as parameter or the lifespan must configure CORS differently.
- Acceptance Criteria:
  - REQ-013: `config.yaml` supports a `server` section with `cors_origins` as a list of origin strings
  - REQ-014: `noise_cancel/config.py` has `_DEFAULT_SERVER` defaults and `AppConfig` includes `server` field
  - REQ-015: `server/main.py` reads `cors_origins` from config and passes to `CORSMiddleware`
  - REQ-016: Default value is `["*"]` when `server.cors_origins` is not configured
  - REQ-017: A log warning is emitted at server startup when wildcard origins are active
  - REQ-018: Tests verify custom CORS origins are applied and default fallback works

### US-004: API Key authentication for REST API
- Title: Add configurable API key authentication middleware to the server
- Priority: 4
- Description: |
    Add `server.api_key` to the `server` config section (introduced in US-003).
    If set, all `/api/*` requests require `X-API-Key` header matching the configured key.
    Implement as FastAPI dependency or middleware. Return 401 if key missing/wrong.
    If `server.api_key` is empty or absent, auth is disabled (backward compatible).
    `/docs` and `/openapi.json` should remain accessible without auth.
    Update Flutter `ApiService` to read API key from `flutter_secure_storage` and send `X-API-Key` header on all requests.
    Add API key field to Flutter `SettingsScreen`.
- Acceptance Criteria:
  - REQ-019: `config.yaml` `server` section supports `api_key` string field
  - REQ-020: When `server.api_key` is set, requests to `/api/*` without valid `X-API-Key` header return 401
  - REQ-021: When `server.api_key` is empty/absent, all requests pass through (no auth)
  - REQ-022: `/docs` and `/openapi.json` are accessible without API key regardless of config
  - REQ-023: Flutter `ApiService` reads `api_key` from secure storage and includes `X-API-Key` header in all requests
  - REQ-024: Flutter `SettingsScreen` has an API Key input field (obscured) that saves to secure storage
  - REQ-025: Server tests verify 401 on missing/wrong key, 200 on correct key, and pass-through when auth disabled
  - REQ-026: Flutter tests verify API key header is sent when configured

### US-005: Duplicate post deduplication
- Title: Prevent duplicate posts from appearing in the feed via content hashing
- Priority: 5
- Description: |
    Currently `posts.post_url` has a UNIQUE constraint, so URL-based duplicates are caught at insert time
    with `IntegrityError` (already handled in `cli.py:scrape`). However posts with different URLs
    but identical content can still appear.

    Add content-hash-based deduplication:
    - Compute SHA-256 hash of normalized `post_text` (strip whitespace, lowercase) before insert
    - Store hash in a new `content_hash` column on `posts` table (migration 004)
    - Skip insert if a post with the same `content_hash` already exists
    - Add unique index on `content_hash` for fast lookup (allowing NULL for existing rows)
    - Update the `Post` model in `noise_cancel/models.py` to include `content_hash` field
    - Update `insert_post()` in repository to handle `content_hash`
    - Update scraper CLI to compute hash before insert
- Acceptance Criteria:
  - REQ-027: Migration `004_add_content_hash.sql` adds `content_hash TEXT` column to `posts` table
  - REQ-028: Migration creates unique index on `content_hash` that allows NULL values
  - REQ-029: A utility function computes SHA-256 of normalized post text (whitespace-stripped, lowercased)
  - REQ-030: CLI `scrape` command computes `content_hash` for each post and sets it before insert
  - REQ-031: Duplicate content posts are caught by `IntegrityError` on `content_hash` index, counted as duplicates
  - REQ-032: Existing posts without `content_hash` continue to work (NULL is allowed)
  - REQ-033: Tests verify content-hash deduplication catches same-text-different-URL posts
  - REQ-034: Tests verify URL-based deduplication still works

### US-006: Clickable URLs in Flutter expanded content
- Title: Make URLs in post text clickable in the expanded content view
- Priority: 6
- Description: |
    In `app/lib/widgets/expanded_content.dart`, the post text is rendered as a plain `Text` widget.
    URLs within the text should be detected via regex and rendered as clickable links.
    Replace the `Text` widget with a `RichText` / `Text.rich` using `TextSpan` children.
    URL segments get a `TapGestureRecognizer` that calls `url_launcher.launchUrl()`.
    Apply only to the expanded content bottom sheet (full post text view), not the summary on PostCard.
- Acceptance Criteria:
  - REQ-035: URLs in post text (expanded content view) are rendered as clickable styled links (e.g., blue/underlined)
  - REQ-036: Tapping a URL opens it in the external browser via `url_launcher`
  - REQ-037: Non-URL text renders normally alongside clickable URLs
  - REQ-038: URL regex handles common patterns: `http://`, `https://`, with paths, query params, fragments
  - REQ-039: Widget tests verify URL segments are created as clickable spans and non-URL text is plain

### US-007: Installation guide and agent-friendly README
- Title: Write comprehensive installation document and update README
- Priority: 7
- Description: |
    Create `docs/installation.md` with the full setup process, written to be both human-readable
    and machine-readable enough for an AI coding agent to follow step-by-step.

    Update `README.md` with a one-liner installation section:
    > **Installation:** Give [this document](raw-link) to your AI coding agent and ask it to set up NoiseCancel for you.

    The installation doc must cover:
    - Prerequisites (Python 3.10+, uv, Playwright, Flutter SDK)
    - Clone + `make install` + `playwright install chromium`
    - `noise-cancel init` + config.yaml structure explanation
    - Environment variables (`ANTHROPIC_API_KEY`, `SLACK_WEBHOOK_URL`)
    - `noise-cancel login` (LinkedIn session management, headless notes, session TTL)
    - New config fields from this MVP: `server.api_key`, `server.cors_origins`, `delivery.plugins`
    - Server startup (`make server`)
    - Flutter app setup + settings (server URL, API key)
    - Cron scheduling example for automated pipeline runs
    - Troubleshooting section (session expiry, common errors)
    - How to write a custom delivery plugin (brief guide referencing `DeliveryPlugin` base class)

    This story must be done LAST because it documents the final state after all other changes.
- Acceptance Criteria:
  - REQ-040: `docs/installation.md` exists with sequential, numbered setup steps
  - REQ-041: Document covers all prerequisites, install commands, config, env vars, login, server, and app setup
  - REQ-042: Document includes new MVP features: delivery plugins config, `server.api_key`, `server.cors_origins`
  - REQ-043: Document includes a cron scheduling example for automated pipeline runs
  - REQ-044: Document includes troubleshooting section
  - REQ-045: Document includes brief custom delivery plugin guide
  - REQ-046: `README.md` contains an installation section with link to `docs/installation.md` raw URL and agent-friendly one-liner
