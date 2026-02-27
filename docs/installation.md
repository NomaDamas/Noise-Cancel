# NoiseCancel — Agent Installation Guide

You are an AI coding agent setting up NoiseCancel for a user. Follow each phase in order. At decision points marked with **ASK USER**, stop and ask the user before proceeding. Do not assume answers.

## Phase 1: Core Installation

These steps are always required.

```bash
git clone https://github.com/NomaDamas/Noise-Cancel.git
cd noise-cancel
make install
uv run playwright install chromium
uv run noise-cancel init
```

This creates the default config at `~/.config/noise-cancel/config.yaml`.

## Phase 2: Environment Variables

**ASK USER:** "Do you have an Anthropic API key? NoiseCancel uses Claude to classify LinkedIn posts. If you don't have one, create one at https://console.anthropic.com/."

Once the user provides the key:

```bash
export ANTHROPIC_API_KEY="<user-provided-key>"
```

Add this export to the user's shell profile (`~/.zshrc`, `~/.bashrc`, etc.) so it persists across sessions.

## Phase 3: Classification Model

The default model is `claude-sonnet-4-6`.

**ASK USER:** "The default classification model is Claude Sonnet (fast, cheap). Do you want to use a different model? Options: `claude-sonnet-4-6` (default), `claude-haiku-4-5-20251001` (faster/cheaper), `claude-opus-4-6` (most accurate/expensive)."

If the user picks a non-default model, update `config.yaml`:

```yaml
classifier:
  model: <user-chosen-model>
```

## Phase 4: Summary Language

**ASK USER:** "What language should post summaries be written in? Default is English. Examples: english, korean, japanese, chinese, spanish, etc."

If non-default:

```yaml
general:
  language: <user-chosen-language>
```

## Phase 5: Delivery Configuration

**ASK USER:** "Where do you want to receive your filtered LinkedIn posts? Options:
1. **Slack** — sends curated posts to a Slack channel via webhook
2. **No delivery** — just use the CLI (`noise-cancel classify`) or mobile app to review
3. **Custom** — you want posts delivered somewhere else (Discord, Notion, email, etc.)

Which do you prefer?"

### If Slack:

**ASK USER:** "Please provide your Slack Incoming Webhook URL. You can create one at https://api.slack.com/messaging/webhooks."

```bash
export SLACK_WEBHOOK_URL="<user-provided-url>"
```

Add this to the user's shell profile as well. Then set config:

```yaml
delivery:
  plugins:
    - type: slack
      include_categories: [Read]
      include_reasoning: true
      max_text_preview: 300
```

### If No delivery:

Remove or empty the plugins list:

```yaml
delivery:
  plugins: []
```

### If Custom:

Explain to the user: "NoiseCancel has a plugin architecture for delivery. You can implement a custom delivery plugin by:

1. Creating a class that extends `DeliveryPlugin` in `noise_cancel/delivery/`
2. Implementing `validate_config(config)` and `deliver(posts, config) -> int`
3. Registering it in `noise_cancel/delivery/loader.py` (`_PLUGIN_REGISTRY`)
4. See `noise_cancel/delivery/slack.py` as a reference implementation.

Would you like me to scaffold a custom delivery plugin for you now?"

If yes, ask what service they want to deliver to and scaffold the plugin. If no, set `delivery.plugins: []` for now and move on.

## Phase 6: LinkedIn Login

```bash
uv run noise-cancel login
```

Tell the user: "A browser window will open. Please log in to LinkedIn manually. The session will be saved and encrypted locally. Sessions expire after 7 days by default — you'll need to re-run this command when that happens."

Wait for the user to confirm login is complete before proceeding.

## Phase 7: Test Run

```bash
uv run noise-cancel run
```

Verify the output shows scraped + classified + delivered counts. If errors occur, troubleshoot:

- `No session found` → Re-run `noise-cancel login`
- `Anthropic API key missing` → Check `ANTHROPIC_API_KEY` is exported
- `Slack plugin requires webhook_url` → Check `SLACK_WEBHOOK_URL` or add `webhook_url` to plugin config

## Phase 8: Mobile App Decision

**ASK USER:** "NoiseCancel has a mobile app with a Tinder-style swipe interface — swipe left to save posts, swipe right to skip. This requires running the API server. Do you want to set up the mobile app, or is receiving posts via your configured delivery channel (Slack, etc.) enough?"

### If Yes (mobile app):

Proceed to Phase 9, 10, and 11.

### If No:

Skip to Phase 12 (Scheduling). The CLI pipeline + delivery is fully functional without the server or app.

## Phase 9: Server Security

Only if user wants the mobile app.

**ASK USER:** "The API server needs to be accessible from your phone. Do you want to set an API key to protect it? (Recommended if the server is accessible from outside your local network.)"

### If Yes:

**ASK USER:** "Enter an API key (any string you choose), or type 'generate' and I'll create one for you."

If user says 'generate', create a random 32-character hex string. Then update config:

```yaml
server:
  api_key: "<chosen-or-generated-key>"
  cors_origins:
    - "*"
```

### If No:

```yaml
server:
  api_key: ""
  cors_origins:
    - "*"
```

## Phase 10: Start Server

Only if user wants the mobile app.

```bash
make server
```

The server runs at `http://0.0.0.0:8012`. Tell the user: "The API server is running. You'll need to keep this running for the mobile app to work. Consider running it in a terminal multiplexer (tmux, screen) or as a background service."

## Phase 11: Flutter App Setup

Only if user wants the mobile app.

**ASK USER:** "Do you have the Flutter SDK (3.5+) installed? If not, install it from https://docs.flutter.dev/get-started/install."

Once confirmed:

```bash
cd app
flutter pub get
flutter run
```

Tell the user: "In the app Settings screen, configure:
- **Server URL**: `http://localhost:8012` (emulator) or `http://<your-LAN-IP>:8012` (physical device)
- **API Key**: the same key from server config (leave empty if you didn't set one)"

## Phase 12: Scheduling

**ASK USER:** "Do you want to automatically run the pipeline on a schedule? This will periodically scrape your LinkedIn feed, classify posts, and deliver them. If yes, how often? Examples:
- Every 2 hours
- Every 6 hours
- Once a day (e.g., 8 AM)
- Custom cron expression"

### If Yes:

Based on the user's answer, construct the crontab entry. Examples:

- Every 2 hours: `0 */2 * * *`
- Every 6 hours: `0 */6 * * *`
- Daily at 8 AM: `0 8 * * *`

```bash
crontab -e
```

Add the following line (adjust paths and schedule):

```cron
<schedule> cd <absolute-path-to-noise-cancel> && export ANTHROPIC_API_KEY="<key>" && export SLACK_WEBHOOK_URL="<url>" && uv run noise-cancel run >> <absolute-path-to-noise-cancel>/logs/cron.log 2>&1
```

Create the logs directory:

```bash
mkdir -p <absolute-path-to-noise-cancel>/logs
```

Important notes to tell the user:
- "Make sure `noise-cancel login` has been run on this machine first."
- "LinkedIn sessions expire every 7 days. You'll need to re-login periodically."
- "Check `logs/cron.log` if posts stop arriving."

### If No:

Tell the user: "You can run `noise-cancel run` manually whenever you want to refresh your feed."

## Phase 13: Final Summary

Print a summary of what was configured:

```
NoiseCancel Setup Complete!

- Model: <model>
- Language: <language>
- Delivery: <slack / none / custom>
- Mobile app: <yes / no>
- Server API key: <set / not set>
- Schedule: <cron expression / manual>

Useful commands:
  noise-cancel run        # Run full pipeline manually
  noise-cancel scrape     # Scrape LinkedIn feed only
  noise-cancel classify   # Classify unprocessed posts
  noise-cancel deliver    # Deliver classified posts
  noise-cancel logs       # View run history
  noise-cancel stats      # View classification stats
  make server             # Start API server
```
