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

noise-cancel은 Slack Incoming Webhook으로 분류된 포스트를 전달합니다. 처음이라면 아래 순서대로 진행하세요.

**Step A. Slack App 만들기**

1. [https://api.slack.com/apps](https://api.slack.com/apps) 접속
2. **Create New App** 클릭
3. **From scratch** 선택
4. App Name에 `noise-cancel` (아무 이름이나 가능), Workspace에 본인 워크스페이스 선택
5. **Create App** 클릭

**Step B. Incoming Webhook 활성화**

1. 왼쪽 사이드바에서 **Incoming Webhooks** 클릭
2. 우측 상단 토글을 **On**으로 변경
3. 페이지 하단 **Add New Webhook to Workspace** 클릭
4. 포스트를 받을 채널 선택 (예: `#linkedin-feed`) → **Allow** 클릭
5. 생성된 **Webhook URL**을 복사 (`https://hooks.slack.com/services/T.../B.../...` 형식)

**Step C. 환경변수 설정**

```bash
export ANTHROPIC_API_KEY="sk-ant-..."                              # Anthropic API 키
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../..."  # 위에서 복사한 URL
```

> **Tip**: `~/.zshrc` 또는 `~/.bashrc`에 추가해두면 매번 설정하지 않아도 됩니다.
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

#### Running on a remote / headless server?

`noise-cancel login` requires a GUI browser. On a server without a display, copy cookies directly from your browser.

**Step 1 — Get cookies from your browser**

Open DevTools on any LinkedIn page (F12 → Application → Cookies → `https://www.linkedin.com`) and copy the values of:
- **`li_at`** — main auth token (long string starting with `AQEDAT...`)
- **`JSESSIONID`** — session ID (string wrapped in double quotes like `"ajax:123..."`)

**Step 2 — Import on the remote server**

```bash
noise-cancel cookie-import \
  --li-at "AQEDATxxxxxx..." \
  --jsessionid "ajax:1234567890123456789"
```

The cookies are encrypted and saved locally — no file transfer needed.

> **Note**: These cookies are your LinkedIn auth tokens. Keep them secret. If scraping starts failing with session errors, repeat this step with fresh cookie values.

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
| `noise-cancel cookie-import` | Build session from raw browser cookies — `--li-at` and `--jsessionid` required |

**Common flags**: `--config PATH`, `--verbose`, `--dry-run`, `--limit N`

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

AI 분류와 별개로, 특정 키워드나 저자를 강제로 Read 또는 Skip으로 지정할 수 있습니다. AI 분류 후에 적용되며, 항상 AI 결과를 덮어씁니다.

```yaml
classifier:
  whitelist:                          # 매칭되면 무조건 Read
    keywords: ["arxiv", "research paper", "ICML", "NeurIPS"]
    authors: ["Yann LeCun", "Andrej Karpathy"]

  blacklist:                          # 매칭되면 무조건 Skip
    keywords: ["agree?", "thoughts?", "like if you", "#hiring"]
    authors: ["Spammy Recruiter"]
```

- 키워드 매칭은 대소문자 구분 없음 (case-insensitive)
- 둘 다 매칭되면 **whitelist가 이김** (benefit of the doubt)

## Slack Delivery

### 메시지 구성

"Read"로 분류된 포스트가 Slack 채널에 아래와 같은 형태로 도착합니다:

```
┌──────────────────────────────────────────┐
│ :fire: Read                              │  ← 카테고리 헤더
├──────────────────────────────────────────┤
│ Author: Jane Doe                         │  ← LinkedIn 프로필 링크 포함
│                                          │
│ "Just published our research on          │  ← 포스트 본문 미리보기
│  efficient transformer architectures..." │    (max_text_preview 글자까지)
│                                          │
│ Confidence: 95% | AI research with...    │  ← 분류 신뢰도 + 이유
├──────────────────────────────────────────┤
│ [Useful] [Not Useful] [Mute Similar]     │  ← 피드백 버튼
│ [View on LinkedIn ↗]                     │  ← 원본 링크
└──────────────────────────────────────────┘
```

### 피드백 버튼

| 버튼 | 동작 |
|------|------|
| **Useful** | 분류가 정확했음을 기록 |
| **Not Useful** | 분류가 틀렸음을 기록 (정확도 통계에 반영) |
| **Mute Similar** | 비슷한 포스트 차단 요청. 누적 3회 시 자동으로 suppress 규칙 생성 |

### 설정 옵션

```yaml
delivery:
  slack:
    include_categories: [Read]     # 어떤 카테고리를 Slack에 보낼지
    include_reasoning: true        # AI 분류 이유 표시 여부
    max_text_preview: 300          # 포스트 미리보기 글자 수
    enable_feedback_buttons: true  # 피드백 버튼 표시 여부
```

### Webhook 관련 주의사항

- Webhook URL은 **채널당 하나**입니다. 다른 채널로 보내려면 새 webhook을 추가하세요.
- Slack Free 플랜에서도 Incoming Webhook은 정상 동작합니다.
- Webhook URL이 노출되면 누구나 해당 채널에 메시지를 보낼 수 있으므로, `.env` 파일이나 환경변수로 관리하고 **절대 git에 커밋하지 마세요**.

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
