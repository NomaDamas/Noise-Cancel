# noise-cancel


AI-powered social feed noise filter. Scrape feeds from LinkedIn, X, Threads, Reddit, and RSS — let Claude decide what's worth reading — then swipe through curated posts in a Tinder-style mobile app or get a digest in Slack.

```
Multiple Feeds  -->  Scrapers  -->  Dedup  -->  Claude (Read / Skip)  -->  Mobile App (swipe)
(LinkedIn, X,    (Playwright /    (hash +        (Sonnet 4.6)             or Slack (webhook)
 Threads,         PRAW /           semantic)                               or Daily Digest
 Reddit, RSS)     feedparser)
```

Delivery modes:
- **Mobile App** -- Flutter cross-platform app with Tinder-style swipe UI. Platform badges, archive search, notes, and share.
- **Slack** -- Incoming webhook delivers classified posts to a Slack channel.
- **Daily Digest** -- Claude-generated summary of the day's curated posts, delivered via Slack.

## Installation

**If you use an AI coding agent** (Claude Code, Cursor, Copilot, etc.), give it [this installation guide](https://raw.githubusercontent.com/NomaDamas/Noise-Cancel/main/docs/installation.md) and ask it to set up NoiseCancel for you. The guide is written as an interactive agent workflow with decision points — your agent will ask you what you need and configure everything accordingly.

**Manual setup** is below if you prefer doing it yourself.

## Quick Start (Manual)

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/NomaDamas/Noise-Cancel.git
cd noise-cancel
make install
uv run playwright install chromium
uv run noise-cancel init       # generates ~/.config/noise-cancel/config.yaml
```

Set environment variables:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."  # optional, only if using Slack
```

Login and run:

```bash
uv run noise-cancel login                # LinkedIn login (default)
uv run noise-cancel login --platform x   # X/Twitter login
uv run noise-cancel run                  # scrape -> classify -> deliver (all enabled platforms)
```

---

## Commands

| Command | Description |
|---------|-------------|
| `noise-cancel init` | Generate default config file |
| `noise-cancel config` | Show current configuration |
| `noise-cancel login` | Login to a platform and save encrypted session |
| `noise-cancel run` | Run full pipeline (scrape + classify + deliver) |
| `noise-cancel scrape` | Scrape feeds from one or all enabled platforms |
| `noise-cancel classify` | Classify unclassified posts |
| `noise-cancel deliver` | Deliver classified posts to Slack |
| `noise-cancel digest` | Generate and deliver AI daily digest |
| `noise-cancel feedback-stats` | Show swipe feedback analytics |
| `noise-cancel logs` | Show run history |
| `noise-cancel stats` | Show classification statistics |

### Platform options

```bash
noise-cancel login --platform linkedin   # default
noise-cancel login --platform x
noise-cancel login --platform threads

noise-cancel scrape                      # all enabled platforms
noise-cancel scrape --platform reddit    # specific platform only
```

Reddit and RSS don't require `login` — they use API credentials or URLs from config.

**Common flags**: `--config PATH`, `--verbose`, `--dry-run`, `--limit N`

### Logs command examples

`noise-cancel logs` shows run history from SQLite with per-run counters (`scraped`, `classified`, `delivered`), status, start time, and error message.

```bash
# Most recent 10 runs
noise-cancel logs --limit 10

# Only failed scrape runs
noise-cancel logs --run-type scrape --status error

# JSON output for automation
noise-cancel logs --json
```
### Stats command examples

`noise-cancel stats` is a classify-run debugging view that shows category counts and per-post previews (post text + reasoning) for a selected classification run.

```bash
# Latest classify run
noise-cancel stats

# Specific classify run ID
noise-cancel stats --run-id <run_id>

# Limit detail rows and emit JSON
noise-cancel stats --limit-posts 20 --json
```

`stats` uses classification timestamp windows to infer rows for a classify run (without schema changes). If inferred row count differs from `run_logs.posts_classified`, it prints a warning.

## Configuration

### Config file location

```
~/.config/noise-cancel/config.yaml      # Default
NC_CONFIG_PATH=/path/to/config.yaml     # Env var override
noise-cancel run --config ./my.yaml     # CLI flag override
```

### Full config reference

```yaml
general:
  data_dir: ~/.local/share/noise-cancel  # Where SQLite DB and sessions live
  max_posts_per_run: 50                  # Max posts to scrape per run

scraper:
  session_warning_days: 1                # Warn N days before session expiry
  platforms:
    linkedin:
      enabled: true
      headless: true
      scroll_count: 10
      session_ttl_days: 7
    x:
      enabled: false
      headless: true
      scroll_count: 10
      session_ttl_days: 7
    threads:
      enabled: false
      headless: true
      scroll_count: 10
      session_ttl_days: 7
    reddit:
      enabled: false
      client_id: ${REDDIT_CLIENT_ID}
      client_secret: ${REDDIT_CLIENT_SECRET}
      username: ${REDDIT_USERNAME}
      password: ${REDDIT_PASSWORD}
    rss:
      enabled: false
      feeds:
        - url: https://example.com/feed.xml
          name: Example Feed

classifier:
  model: claude-sonnet-4-6  # Claude model to use
  batch_size: 10            # Posts per API call
  temperature: 0.0          # 0.0 = deterministic
  categories:               # Binary: Read or Skip
    - name: Read
      description: "..."    # Customize this to your interests
      emoji: ":fire:"
    - name: Skip
      description: "..."    # Customize this to your noise
      emoji: ":mute:"
  whitelist:                # Regex patterns → always Read
    keywords: ["\\bAI\\b", "research paper", "arxiv"]
    authors: ["Yann LeCun"]
  blacklist:                # Regex patterns → always Skip
    keywords: ["agree\\?", "thoughts\\?", "hiring|job opening"]
    authors: []
  platform_prompts:         # Optional per-platform prompt overrides
    reddit:
      system_prompt: "You are classifying Reddit posts. Consider the subreddit context..."
    x:
      system_prompt: "You are classifying X/Twitter posts. These are short-form..."

dedup:
  semantic:
    enabled: false                      # Opt-in semantic dedup
    provider: sentence-transformers     # or openai, voyage
    model: all-MiniLM-L6-v2
    threshold: 0.85

delivery:
  method: slack
  digest:
    enabled: true                       # Enable daily digest generation
  slack:
    include_categories: [Read]
    include_reasoning: true
    max_text_preview: 300
    enable_feedback_buttons: true
```

### Whitelist / Blacklist

Force specific patterns or authors to always be classified as Read or Skip, regardless of the AI classification. Keywords are treated as **regex patterns** and applied as a pre-filter before the Claude API call.

```yaml
classifier:
  whitelist:                          # Matched → always Read
    keywords: ["\\bAI\\b", "research paper", "ICML|NeurIPS"]
    authors: ["Yann LeCun", "Andrej Karpathy"]

  blacklist:                          # Matched → always Skip
    keywords: ["agree\\?", "thoughts\\?", "#hiring"]
    authors: ["Spammy Recruiter"]
```

- Keywords are regex patterns (e.g., `\\bAI\\b` for whole-word match, `hiring|job opening` for alternation)
- Invalid regex patterns raise a `ConfigError` at startup
- If both match, **whitelist wins** (benefit of the doubt)

## Slack Delivery

### Message format

Posts classified as "Read" arrive in Slack in the following format:

```
┌──────────────────────────────────────────┐
│ :fire: Read                              │  ← Category header
├──────────────────────────────────────────┤
│ Author: Jane Doe                         │  ← Includes profile link
│                                          │
│ "Just published our research on          │  ← Post text preview
│  efficient transformer architectures..." │    (up to max_text_preview chars)
│                                          │
│ Confidence: 95% | AI research with...    │  ← Confidence score + reasoning
├──────────────────────────────────────────┤
│ [Useful] [Not Useful] [Mute Similar]     │  ← Feedback buttons
│ [View on LinkedIn ↗]                     │  ← Original post link
└──────────────────────────────────────────┘
```

### Feedback buttons

| Button | Action |
|--------|--------|
| **Useful** | Records that the classification was correct |
| **Not Useful** | Records that the classification was wrong (used for accuracy stats) |
| **Mute Similar** | Requests suppression of similar posts. After 3 cumulative mutes, an automatic suppress rule is created |

### Webhook security notes

- Each webhook URL is tied to **one channel**. Add a new webhook to post to a different channel.
- Incoming Webhooks work on the Slack Free plan.
- Anyone with the webhook URL can post to your channel. Store it in `.env` or environment variables and **never commit it to git**.

## REST API Server

The server exposes a FastAPI REST API that the mobile app (or any client) uses to fetch and act on classified posts. It reuses the existing core library (`noise_cancel/`) for scraping, classification, and storage.

### Start the server

```bash
make server    # uvicorn on port 8012, auto-reload
```

Swagger docs at `http://localhost:8012/docs`.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/posts` | Paginated feed with search, platform filter |
| `GET` | `/api/posts/{id}` | Single post detail |
| `POST` | `/api/posts/{id}/archive` | Archive post (swipe left) |
| `POST` | `/api/posts/{id}/delete` | Delete post (swipe right) |
| `POST` | `/api/posts/{id}/note` | Create/update note on a post |
| `GET` | `/api/posts/{id}/note` | Get note for a post |
| `DELETE` | `/api/posts/{id}/note` | Delete note from a post |
| `POST` | `/api/pipeline/run` | Trigger pipeline (background) |
| `GET` | `/api/pipeline/status` | Latest pipeline run status |
| `POST` | `/api/digest/generate` | Generate and deliver daily digest |
| `GET` | `/api/feedback/stats` | Swipe feedback analytics |

### GET /api/posts

Fetches posts for the swipe UI or archive browsing. Supports search, platform filter, and pagination.

```bash
curl "http://localhost:8012/api/posts?category=Read&swipe_status=pending&limit=20&offset=0"

# Search archived posts
curl "http://localhost:8012/api/posts?swipe_status=archived&q=transformer&platform=reddit"
```

| Query Param | Default | Description |
|-------------|---------|-------------|
| `category` | `Read` | Classification category filter |
| `swipe_status` | `pending` | `pending`, `archived`, or `deleted` |
| `platform` | (all) | Filter by platform: `linkedin`, `x`, `threads`, `reddit`, `rss` |
| `q` | (none) | Keyword search on post text |
| `limit` | `20` | Max posts per page |
| `offset` | `0` | Pagination offset |

Response includes `platform` and `note` fields per post:

```json
{
  "posts": [
    {
      "id": "urn:li:activity:123",
      "classification_id": "abc123",
      "author_name": "Jane Doe",
      "post_url": "https://linkedin.com/feed/update/...",
      "post_text": "Full post content...",
      "platform": "linkedin",
      "note": "My personal note about this post",
      "summary": "AI-generated 2-3 sentence summary",
      "category": "Read",
      "confidence": 0.95,
      "classified_at": "2025-01-15T10:30:00+00:00",
      "swipe_status": "pending"
    }
  ],
  "total": 42,
  "has_more": true
}
```

### POST /api/posts/{id}/archive

Archives a post (swipe left). Returns 409 if already processed.

```bash
curl -X POST "http://localhost:8012/api/posts/abc123/archive"
```

### POST /api/pipeline/run

Triggers the scrape + classify pipeline as a background task. Returns 409 if a pipeline is already running.

```bash
curl -X POST "http://localhost:8012/api/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{"limit": 50, "skip_scrape": false}'
```

### POST /api/digest/generate

Generates an AI daily digest summarizing all "Read" posts from the last 24 hours across all platforms.

```bash
curl -X POST "http://localhost:8012/api/digest/generate"
```

---

## Mobile App (Flutter)

A cross-platform (iOS + Android) app with a Tinder-style swipe interface for reviewing classified posts from all platforms.

### Install and run

Requires [Flutter SDK](https://docs.flutter.dev/get-started/install) 3.5+.

```bash
cd app
flutter pub get
flutter run
```

### Features

- **Platform badges** -- Each card shows which platform the post came from (LinkedIn blue, X black, Reddit orange, etc.)
- **Archive screen** -- Browse and search archived posts with platform filter chips. Access via the archive button in the top-left corner.
- **Post notes** -- Long-press a card to attach a personal note. Notes are synced to the server.
- **Share** -- Share post content + URL via the native OS share sheet.
- **Swipe interactions**:
  - **Swipe left** -- Archives the post + forwards to your webhook (if configured)
  - **Swipe right** -- Deletes the post (never shown again)

### Webhook forwarding

Webhook forwarding happens directly from the app (client-side). Configure it in Settings:

- **Webhook URL** -- Any HTTP endpoint (Slack, Discord, custom server, etc.)
- **Payload template** -- Customizable JSON with placeholders:

```json
{
  "author": "{{author_name}}",
  "summary": "{{summary}}",
  "url": "{{post_url}}",
  "category": "{{category}}"
}
```

Available placeholders: `{{author_name}}`, `{{summary}}`, `{{post_url}}`, `{{post_text}}`, `{{category}}`

### Settings

Open via the gear icon in the top-right corner:

- **Server URL** -- Your NoiseCancel server address (e.g., `http://192.168.1.100:8012`)
- **Webhook URL** -- Where to forward archived posts
- **Webhook template** -- JSON payload template with placeholders
- **Webhook toggle** -- Enable/disable forwarding

All settings are stored in the device's secure storage.

### App structure

```
app/lib/
  main.dart                          # Entry point
  app.dart                           # MaterialApp, dark theme, Provider setup
  app_state.dart                     # ChangeNotifier app state
  models/
    post.dart                        # Post data model (with platform, note fields)
  services/
    api_service.dart                 # HTTP client for server API
    share_service.dart               # Native share sheet integration
    webhook_service.dart             # Client-side webhook forwarding
  screens/
    swipe_screen.dart                # Main Tinder-style swipe view
    archive_screen.dart              # Archive browsing with search and filters
    settings_screen.dart             # Server + webhook configuration
  widgets/
    platform_badge.dart              # Shared platform badge styles and display names
    post_card.dart                   # Card: author, summary, platform badge, buttons
    expanded_content.dart            # Bottom sheet: full post text
```

---

## Data Storage

Everything is local. No external database needed (SQLite is built into Python).

```
~/.local/share/noise-cancel/
  noise_cancel.db          # All posts, classifications, feedback, run history
  session.enc              # Encrypted LinkedIn session
  x_session.enc            # Encrypted X session
  threads_session.enc      # Encrypted Threads session
```

### Database schema

```
posts                    # Scraped posts from all platforms
  id                     # Platform-specific ID (URN, tweet URL, etc.)
  author_name, author_url, post_url, post_text
  platform               # 'linkedin', 'x', 'threads', 'reddit', 'rss'
  metadata               # JSON: platform-specific data (subreddit, feed_name, etc.)
  scraped_at, run_id

classifications          # AI classification results
  id, post_id            # 1:1 with posts
  category               # 'Read' or 'Skip'
  confidence             # 0.0 - 1.0
  reasoning, summary     # AI-generated
  swipe_status           # 'pending', 'archived', 'deleted'
  swiped_at              # When the user swiped

embeddings               # Vector embeddings for semantic dedup
  post_id, vector, model, created_at

notes                    # User-attached notes on posts
  id, classification_id, note_text, created_at, updated_at

feedback                 # Swipe action data for future learning
  id, classification_id, action, platform, category, confidence, created_at

run_logs                 # Pipeline execution history
  id, run_type, status
  posts_scraped, posts_classified, posts_delivered
  started_at, finished_at, error_message
```

## Development

```bash
make install       # Install deps + pre-commit hooks
make test          # Run all Python tests (337 tests)
make check         # Ruff lint + format + ty type check + deptry
make server        # Start API server (dev mode, port 8012)
make test-server   # Run server tests only
make docs          # Build MkDocs documentation
```

### Project structure

```
noise-cancel/                        # Monorepo
  noise_cancel/                      # Core Python library
    cli.py                           # Typer CLI commands
    config.py                        # YAML config + defaults
    models.py                        # Pydantic models (Post, Classification, RunLog)
    database.py                      # SQLite connection + migrations
    scraper/                         # Multi-platform scraping
      base.py                        #   AbstractScraper interface
      playwright_base.py             #   PlaywrightScraper base (LinkedIn, X, Threads)
      linkedin.py, x.py, threads.py  #   Playwright-based scrapers
      reddit.py                      #   PRAW-based Reddit scraper
      rss.py                         #   feedparser-based RSS scraper
      registry.py                    #   ScraperRegistry for platform lookup
      utils.py                       #   Shared string utilities
    classifier/                      # Claude API classification + regex rules
    dedup/                           # Semantic deduplication (embeddings + Claude verify)
    digest/                          # AI daily digest generation
    delivery/                        # Slack Block Kit messages + digest delivery
    logger/                          # DB repository, CSV/JSON export, metrics
  server/                            # FastAPI REST API server
    main.py                          # App factory, lifespan, CORS
    schemas.py                       # API request/response Pydantic models
    dependencies.py                  # FastAPI dependency injection
    routers/                         # posts, actions, pipeline, digest, feedback endpoints
    services/                        # Pipeline orchestration service
  app/                               # Flutter cross-platform mobile app
    lib/                             # Dart source (models, services, screens, widgets)
    pubspec.yaml                     # Flutter dependencies
  migrations/                        # SQL migration files (001-009)
  tests/                             # Core library tests
  tests_server/                      # Server API tests
```

## License

See [LICENSE](LICENSE) for details.
