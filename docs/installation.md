# NoiseCancel Installation Guide

Use this document for a full end-to-end setup of the CLI pipeline, FastAPI server, and Flutter app.

## Setup Steps

1. Install prerequisites.
   - Python 3.10+
   - [uv](https://docs.astral.sh/uv/)
   - Chromium dependencies for Playwright
   - [Flutter SDK](https://docs.flutter.dev/get-started/install) 3.5+ (for mobile app)
   - Git

2. Clone the repository.

   ```bash
   git clone https://github.com/vkehfdl1/noise-cancel.git
   cd noise-cancel
   ```

3. Install project dependencies and browser runtime.

   ```bash
   make install
   uv run playwright install chromium
   ```

4. Generate the default config file.

   ```bash
   noise-cancel init
   ```

   Default path: `~/.config/noise-cancel/config.yaml`

5. Set required environment variables.

   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../..."
   ```

   Notes:
   - `ANTHROPIC_API_KEY` is required for classification.
   - `SLACK_WEBHOOK_URL` is required only if your Slack plugin config does not include `webhook_url`.
   - Optional: `NC_CONFIG_PATH=/absolute/path/to/config.yaml` to override config location.

6. Update `config.yaml` for your categories and MVP server/delivery settings.

   ```yaml
   general:
     data_dir: ~/.local/share/noise-cancel
     max_posts_per_run: 50

   scraper:
     headless: true
     scroll_count: 10
     session_ttl_days: 7

   classifier:
     model: claude-sonnet-4-6
     categories:
       - name: Read
         description: "Posts worth reading"
         emoji: ":fire:"
       - name: Skip
         description: "Posts to ignore"
         emoji: ":mute:"

   delivery:
     plugins:
       - type: slack
         include_categories: ["Read"]
         include_reasoning: true
         max_text_preview: 300
         # Optional when SLACK_WEBHOOK_URL env var is set:
         # webhook_url: "https://hooks.slack.com/services/..."

   server:
     cors_origins:
       - "http://localhost:8012"
       - "http://localhost:3000"
     api_key: "replace-with-your-api-key"  # Empty string disables API auth
   ```

   Notes:
   - `delivery.plugins` is the new preferred format.
   - Legacy `delivery.method` / `delivery.slack` still auto-converts for backward compatibility.
   - `server.api_key` protects `/api/*` routes through `X-API-Key`.
   - `server.cors_origins` defaults to `["*"]` when omitted.

7. Log in to LinkedIn once to create an encrypted session.

   ```bash
   noise-cancel login
   ```

   Notes:
   - This opens a browser and saves encrypted session files in `general.data_dir`.
   - If the session expires, run `noise-cancel login` again.
   - Session lifetime is controlled by `scraper.session_ttl_days` (default: 7).
   - For remote/headless hosts, run login through a virtual display (Xvfb + VNC) so the browser runs on the same machine/IP as scheduled jobs.

8. Run the pipeline once from CLI.

   ```bash
   noise-cancel run
   ```

   Useful commands:

   ```bash
   noise-cancel scrape
   noise-cancel classify
   noise-cancel deliver
   noise-cancel logs --limit 10
   ```

9. Start the API server.

   ```bash
   make server
   ```

   Default local URL: `http://0.0.0.0:8012`

10. Set up and run the Flutter app.

    ```bash
    cd app
    flutter pub get
    flutter run
    ```

11. Configure app settings (inside the Flutter app).
    - `Server URL`: e.g. `http://localhost:8012` (emulator) or `http://<your-lan-ip>:8012` (physical device)
    - `API Key`: same value as `server.api_key` in `config.yaml` (leave blank if server auth is disabled)

12. (Optional) Schedule automated runs with cron.

    Example crontab (`crontab -e`) running every 2 hours:

    ```cron
    0 */2 * * * cd /absolute/path/to/noise-cancel && \
    export ANTHROPIC_API_KEY="sk-ant-..." && \
    export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../..." && \
    uv run noise-cancel run >> /absolute/path/to/noise-cancel/logs/cron.log 2>&1
    ```

    Recommendations:
    - Use absolute paths in cron jobs.
    - Confirm `noise-cancel login` already succeeded on that host before enabling cron.
    - Rotate logs if you expect long-running automation.

## Troubleshooting

- `No session found` or `Session expired`
  - Run `noise-cancel login` again.
  - Verify `scraper.session_ttl_days` and system clock correctness.

- `Anthropic API key missing` / classification failures
  - Check `ANTHROPIC_API_KEY` is exported in the shell environment that runs commands (interactive shell, cron, or service).

- `Slack plugin requires webhook_url or SLACK_WEBHOOK_URL`
  - Add `webhook_url` under the Slack plugin in `delivery.plugins`, or export `SLACK_WEBHOOK_URL`.

- API returns `401 Unauthorized`
  - Ensure client sends `X-API-Key` matching `server.api_key`.
  - In Flutter Settings, verify API Key value and save again.

- Browser CORS errors from frontend clients
  - Add the client origin to `server.cors_origins`.
  - Restart server after config changes.

- Flutter app cannot reach server from physical phone
  - `localhost` on phone points to the phone itself, not your computer.
  - Use your computer's LAN IP in app settings (example: `http://192.168.1.50:8012`).

## Custom Delivery Plugin (Brief Guide)

1. Create a plugin class implementing `DeliveryPlugin` in `noise_cancel/delivery/`.
2. Implement:
   - `validate_config(config: dict[str, Any]) -> None`
   - `deliver(posts: list[tuple[Post, Classification]], config: AppConfig) -> int`
3. Register the plugin in `noise_cancel/delivery/loader.py` (`_PLUGIN_REGISTRY`).
4. Add plugin config under `delivery.plugins` in `config.yaml`.
5. Run:

   ```bash
   make test
   noise-cancel deliver
   ```

Start from `noise_cancel/delivery/slack.py` as the reference implementation.
