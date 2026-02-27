# noise-cancel


AI-powered LinkedIn feed noise filter. Scrape your feed, let Claude decide what's worth reading, and swipe through curated posts in a Tinder-style mobile app or get a digest in Slack.

```
LinkedIn Feed  -->  Scraper  -->  Claude (Read / Skip)  -->  Mobile App (swipe)
              (Playwright)       (Sonnet 4.6)                 or Slack (webhook)
```

Two delivery modes:
- **Mobile App** (new) -- Flutter cross-platform app with Tinder-style swipe UI. Swipe left to archive + forward to webhook, swipe right to dismiss.
- **Slack** -- Incoming webhook delivers classified posts to a Slack channel.

## Installation

> **Installation:** Give [this document](https://raw.githubusercontent.com/vkehfdl1/noise-cancel/main/docs/installation.md) to your AI coding agent and ask it to set up NoiseCancel for you.

Detailed human-readable guide: [docs/installation.md](docs/installation.md)

## Quick Start

### 1. Install

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/vkehfdl1/noise-cancel.git
cd noise-cancel
make install
uv run playwright install chromium
```

### 2. Set up Slack webhook

noise-cancel delivers classified posts to Slack via Incoming Webhooks. Follow the steps below to set one up.

**Step A. Create a Slack App**

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App**
3. Select **From scratch**
4. Enter any App Name (e.g. `noise-cancel`), select your workspace
5. Click **Create App**

**Step B. Enable Incoming Webhooks**

1. In the left sidebar, click **Incoming Webhooks**
2. Toggle it **On** (top right)
3. Click **Add New Webhook to Workspace** at the bottom
4. Select a channel to receive posts (e.g. `#linkedin-feed`) → click **Allow**
5. Copy the generated **Webhook URL** (`https://hooks.slack.com/services/T.../B.../...`)

**Step C. Set environment variables**

```bash
export ANTHROPIC_API_KEY="sk-ant-..."                              # Anthropic API key
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../..."  # Webhook URL from above
```

> **Tip**: Add these to `~/.zshrc` or `~/.bashrc` so they persist across sessions.
>
> ```bash
> echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc
> echo 'export SLACK_WEBHOOK_URL="https://hooks.slack.com/..."' >> ~/.zshrc
> source ~/.zshrc
> ```

### 3. Generate config

```bash
noise-cancel init
```

This creates `~/.config/noise-cancel/config.yaml` with sensible defaults. Open it and customize:

```yaml
classifier:
  categories:
    - name: Read
      description: "Worth reading - valuable insights, relevant industry news, useful knowledge"
      emoji: ":fire:"
    - name: Skip
      description: "Not worth reading - engagement bait, humble brag, ads, spam, irrelevant"
      emoji: ":mute:"
```

**Tip**: Edit the `description` fields to match your interests. The more specific you are, the better Claude classifies. For example:

```yaml
    - name: Read
      description: "AI/ML research, system design, open source releases, Python ecosystem news"
    - name: Skip
      description: "Engagement bait, humble brags, motivational quotes, crypto shilling, recruitment spam"
```

### 4. Login to LinkedIn

```bash
noise-cancel login
```

A browser opens for manual LinkedIn login. Session cookies are encrypted (Fernet) and saved locally.

#### Running on a remote / headless server

`noise-cancel login` requires a GUI browser. On a server without a display, you **cannot** simply transfer cookies from another machine — LinkedIn binds sessions to the originating IP and device fingerprint, and will invalidate the session (and log you out everywhere) if it detects reuse from a different environment.

The solution is to run a virtual display + VNC server so you can open a real browser on the server itself.

**One-time setup:**

```bash
# Install Xvfb (virtual display) and x11vnc (VNC server)
sudo apt-get install -y xvfb x11vnc

# Set a VNC password
x11vnc -storepasswd /tmp/x11vnc.pw

# Start virtual display and VNC server
Xvfb :99 -screen 0 1920x1080x24 &
x11vnc -display :99 -rfbauth /tmp/x11vnc.pw -listen localhost -rfbport 5900 -forever &
```

**From your local machine:**

```bash
# Open an SSH tunnel (adjust port/user/host as needed)
ssh -L 5900:localhost:5900 user@your-server

# Connect with a VNC client
# Mac:     open vnc://localhost:5900
# Windows: use RealVNC Viewer → localhost:5900
# Linux:   vncviewer localhost:5900
```

**In the SSH shell (with the tunnel open):**

```bash
DISPLAY=:99 noise-cancel login
```

A Chromium window will appear in your VNC client. Log in to LinkedIn, and the session is saved. After login, stop the VNC server and virtual display:

```bash
kill $(pgrep x11vnc)
kill $(pgrep Xvfb)
```

From this point on, `noise-cancel run` works headlessly — the session was created on the same IP, so LinkedIn won't flag it. Re-run the VNC setup when the session expires (`session_ttl_days`, default: 7 days).

### 5. Run

```bash
# Full pipeline: scrape -> classify -> deliver
noise-cancel run

# Or step by step
noise-cancel scrape       # Scrape feed posts
noise-cancel classify     # Classify with Claude
noise-cancel deliver      # Send "Read" posts to Slack
```

That's it. "Read" posts arrive in your Slack channel with author, preview, confidence score, and feedback buttons.

---

## Commands

| Command | Description |
|---------|-------------|
| `noise-cancel init` | Generate default config file |
| `noise-cancel config` | Show current configuration |
| `noise-cancel login` | Login to LinkedIn and save encrypted session |
| `noise-cancel run` | Run full pipeline (scrape + classify + deliver) |
| `noise-cancel scrape` | Scrape LinkedIn feed |
| `noise-cancel classify` | Classify unclassified posts |
| `noise-cancel deliver` | Deliver classified posts to Slack |
| `noise-cancel logs` | Show run history |
| `noise-cancel stats` | Show classification statistics |

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
  data_dir: ~/.local/share/noise-cancel  # Where SQLite DB and session live
  max_posts_per_run: 50                  # Max posts to scrape per run

scraper:
  headless: true           # Run browser headlessly (false to watch it)
  scroll_count: 10         # How many times to scroll the feed
  scroll_delay_min: 1.5    # Min delay between scrolls (seconds)
  scroll_delay_max: 3.5    # Max delay between scrolls (seconds)
  session_ttl_days: 7      # Re-login after this many days

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
  whitelist:                # Matches here → always Read
    keywords: ["arxiv", "research paper"]
    authors: ["Yann LeCun"]
  blacklist:                # Matches here → always Skip
    keywords: ["agree?", "thoughts?", "like if you"]
    authors: []

delivery:
  method: slack
  slack:
    include_categories: [Read]       # Only deliver "Read" posts
    include_reasoning: true          # Show why Claude classified it
    max_text_preview: 300            # Truncate post text in Slack
    enable_feedback_buttons: true    # Show Useful/Not Useful/Mute buttons
```

### Whitelist / Blacklist

You can force specific keywords or authors to always be classified as Read or Skip, regardless of the AI classification. These rules are applied after AI classification and always override the AI result.

```yaml
classifier:
  whitelist:                          # Matched → always Read
    keywords: ["arxiv", "research paper", "ICML", "NeurIPS"]
    authors: ["Yann LeCun", "Andrej Karpathy"]

  blacklist:                          # Matched → always Skip
    keywords: ["agree?", "thoughts?", "like if you", "#hiring"]
    authors: ["Spammy Recruiter"]
```

- Keyword matching is case-insensitive
- If both match, **whitelist wins** (benefit of the doubt)

## Slack Delivery

### Message format

Posts classified as "Read" arrive in Slack in the following format:

```
┌──────────────────────────────────────────┐
│ :fire: Read                              │  ← Category header
├──────────────────────────────────────────┤
│ Author: Jane Doe                         │  ← Includes LinkedIn profile link
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

### Delivery settings

```yaml
delivery:
  slack:
    include_categories: [Read]     # Which categories to send to Slack
    include_reasoning: true        # Show AI classification reasoning
    max_text_preview: 300          # Post preview character limit
    enable_feedback_buttons: true  # Show feedback buttons
```

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
| `GET` | `/api/posts` | Paginated feed of classified posts for the swipe UI |
| `GET` | `/api/posts/{classification_id}` | Single post detail |
| `POST` | `/api/posts/{classification_id}/archive` | Swipe left -- mark as archived, returns post data for webhook |
| `POST` | `/api/posts/{classification_id}/delete` | Swipe right -- mark as deleted (hidden forever) |
| `POST` | `/api/pipeline/run` | Trigger scrape + classify pipeline (runs in background) |
| `GET` | `/api/pipeline/status` | Latest pipeline run status |

### GET /api/posts

Fetches posts for the swipe UI. Only returns posts matching the given category and swipe status.

```bash
curl "http://localhost:8012/api/posts?category=Read&swipe_status=pending&limit=20&offset=0"
```

```json
{
  "posts": [
    {
      "id": "urn:li:activity:123",
      "classification_id": "abc123",
      "author_name": "Jane Doe",
      "author_url": "https://linkedin.com/in/janedoe",
      "post_url": "https://linkedin.com/feed/update/urn:li:activity:123",
      "post_text": "Full post content...",
      "summary": "AI-generated 2-3 sentence summary",
      "category": "Read",
      "confidence": 0.95,
      "reasoning": "Contains valuable technical insights about...",
      "classified_at": "2025-01-15T10:30:00+00:00",
      "swipe_status": "pending"
    }
  ],
  "total": 42,
  "has_more": true
}
```

| Query Param | Default | Description |
|-------------|---------|-------------|
| `category` | `Read` | Classification category filter |
| `swipe_status` | `pending` | `pending`, `archived`, or `deleted` |
| `limit` | `20` | Max posts per page |
| `offset` | `0` | Pagination offset |

### POST /api/posts/{id}/archive

Archives a post (swipe left). Returns the full post data so the client can forward it to a webhook.

```bash
curl -X POST "http://localhost:8012/api/posts/abc123/archive"
```

```json
{
  "status": "archived",
  "classification_id": "abc123",
  "author_name": "Jane Doe",
  "summary": "AI-generated summary...",
  "post_url": "https://linkedin.com/feed/update/...",
  "post_text": "Full post content...",
  "category": "Read"
}
```

### POST /api/posts/{id}/delete

Deletes a post from the feed (swipe right). The post is never shown again.

```bash
curl -X POST "http://localhost:8012/api/posts/abc123/delete"
```

```json
{
  "status": "deleted",
  "classification_id": "abc123"
}
```

### POST /api/pipeline/run

Triggers the scrape + classify pipeline as a background task. Returns immediately with a run ID.

```bash
curl -X POST "http://localhost:8012/api/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{"limit": 50, "skip_scrape": false}'
```

```json
{
  "run_id": "a1b2c3d4",
  "status": "accepted",
  "message": "Pipeline run started"
}
```

### GET /api/pipeline/status

Returns the latest pipeline run status.

```bash
curl "http://localhost:8012/api/pipeline/status"
```

```json
{
  "run_id": "a1b2c3d4",
  "run_type": "pipeline",
  "started_at": "2025-01-15T10:00:00",
  "finished_at": "2025-01-15T10:05:00",
  "status": "completed",
  "posts_scraped": 30,
  "posts_classified": 30,
  "posts_delivered": 0,
  "error_message": null
}
```

---

## Mobile App (Flutter)

A cross-platform (iOS + Android) app with a Tinder-style swipe interface for reviewing classified posts.

### Install and run

Requires [Flutter SDK](https://docs.flutter.dev/get-started/install) 3.5+.

```bash
cd app
flutter pub get
flutter run
```

### How it works

1. The app connects to the NoiseCancel server (URL configured in Settings)
2. Fetches posts classified as "Read" that haven't been swiped yet
3. Displays posts as a card stack:
   - **Author name** (bold, large)
   - **AI-generated summary** (2-3 sentences)
   - **"More"** button to expand full post text in a bottom sheet
   - **"Link"** button to open the original LinkedIn post in browser
4. Swipe interactions:
   - **Swipe left** -- Archives the post + forwards to your webhook (if configured)
   - **Swipe right** -- Deletes the post (never shown again)
5. Pre-fetches the next batch when fewer than 5 cards remain

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

Webhook forwarding is fire-and-forget -- it never blocks the swipe UI.

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
    post.dart                        # Post data model (mirrors server schema)
  services/
    api_service.dart                 # HTTP client for server API
    webhook_service.dart             # Client-side webhook forwarding
  screens/
    swipe_screen.dart                # Main Tinder-style swipe view
    settings_screen.dart             # Server + webhook configuration
  widgets/
    post_card.dart                   # Card: author, summary, buttons
    expanded_content.dart            # Bottom sheet: full post text
```

---

## Data Storage

Everything is local. No external database needed (SQLite is built into Python).

```
~/.local/share/noise-cancel/
  noise_cancel.db    # All posts, classifications, feedback, run history
  session.enc        # Encrypted LinkedIn session cookies
```

### Database schema

```
posts                    # Scraped LinkedIn posts
  id                     # LinkedIn activity URN
  author_name, author_url, post_url, post_text
  scraped_at, run_id

classifications          # AI classification results
  id, post_id            # 1:1 with posts
  category               # 'Read' or 'Skip'
  confidence             # 0.0 - 1.0
  reasoning, summary     # AI-generated
  swipe_status           # 'pending', 'archived', 'deleted'
  swiped_at              # When the user swiped

run_logs                 # Pipeline execution history
  id, run_type, status
  posts_scraped, posts_classified, posts_delivered
  started_at, finished_at, error_message
```

## Development

```bash
make install       # Install deps + pre-commit hooks
make test          # Run all Python tests (211 tests)
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
    scraper/                         # LinkedIn scraping (Playwright)
    classifier/                      # Claude API classification + rules
    delivery/                        # Slack Block Kit messages + feedback
    logger/                          # DB repository, CSV/JSON export, metrics
  server/                            # FastAPI REST API server
    main.py                          # App factory, lifespan, CORS
    schemas.py                       # API request/response Pydantic models
    dependencies.py                  # FastAPI dependency injection
    routers/                         # posts, actions, pipeline endpoints
    services/                        # Pipeline orchestration service
  app/                               # Flutter cross-platform mobile app
    lib/                             # Dart source (models, services, screens, widgets)
    pubspec.yaml                     # Flutter dependencies
  migrations/                        # SQL migration files
    001_initial.sql                  # Base schema (posts, classifications, run_logs)
    002_add_summary.sql              # Added summary column
    003_add_swipe_status.sql         # Added swipe_status + swiped_at columns
  tests/                             # Core library tests
  tests_server/                      # Server API tests
```

## License

See [LICENSE](LICENSE) for details.
