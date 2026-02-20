# noise-cancel

[![Release](https://img.shields.io/github/v/release/vkehfdl1/noise-cancel)](https://img.shields.io/github/v/release/vkehfdl1/noise-cancel)
[![Build status](https://img.shields.io/github/actions/workflow/status/vkehfdl1/noise-cancel/main.yml?branch=main)](https://github.com/vkehfdl1/noise-cancel/actions/workflows/main.yml?query=branch%3Amain)
[![License](https://img.shields.io/github/license/vkehfdl1/noise-cancel)](https://img.shields.io/github/license/vkehfdl1/noise-cancel)

AI-powered LinkedIn feed noise filter. Scrape your feed, let Claude decide what's worth reading, and get a curated digest in Slack.

```
LinkedIn Feed  -->  Scraper  -->  Claude (Read / Skip)  -->  Slack
              (Playwright)       (Sonnet 4.6)           (Webhook)
```

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

## Data Storage

Everything is local. No external database needed (SQLite is built into Python).

```
~/.local/share/noise-cancel/
  noise_cancel.db    # All posts, classifications, feedback, run history
  session.enc        # Encrypted LinkedIn session cookies
```

## Development

```bash
make install     # Install deps + pre-commit hooks
make test        # Run tests (137 tests)
make check       # Ruff lint + format + ty type check + deptry
make docs        # Build MkDocs documentation
```

### Project structure

```
noise_cancel/
  cli.py                  # Typer CLI commands
  config.py               # YAML config with defaults + init generation
  models.py               # Pydantic models (Post, Classification, etc.)
  database.py             # SQLite connection + migrations
  scraper/                # LinkedIn scraping (Playwright)
  classifier/             # Claude API classification + rules
  delivery/               # Slack Block Kit messages + feedback
  logger/                 # DB repository, CSV/JSON export, metrics
migrations/
  001_initial.sql         # Database schema
```

## License

See [LICENSE](LICENSE) for details.
