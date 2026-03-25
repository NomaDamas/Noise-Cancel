# PRD — NoiseCancel v2: Multi-Platform Feed Intelligence

## Project
- Name: NoiseCancel v2
- Branch: `feature/v2-multi-platform`
- Description: Evolve NoiseCancel from a LinkedIn-only CLI tool into a multi-platform social feed intelligence system. Add X, Threads, Reddit, and RSS scrapers; semantic deduplication across platforms; archive browsing with search; per-platform classification; AI daily digest; and enhanced mobile UX features.

## Closes GitHub Issues
#1, #11, #12, #16, #17, #22, #23, #24

---

## Phase 1: Core Foundation

### US-001 — Multi-Platform Scraper Architecture
- Title: Refactor scraper and DB to support multiple platforms
- Priority: 1
- Description: Extend the existing `AbstractScraper` base class pattern and database schema to support multiple platforms beyond LinkedIn. The `posts` table already has a `platform` column (default `'linkedin'`). Add a scraper registry that loads platform scrapers by config, update the pipeline to iterate over enabled platforms, and restructure config to hold per-platform scraper settings. The existing LinkedIn scraper must remain fully functional.
- Acceptance Criteria:
  - REQ-001: A `ScraperRegistry` maps platform names to scraper classes (e.g., `{"linkedin": LinkedInScraper}`). New scrapers register via the same mechanism.
  - REQ-002: `AppConfig.scraper` gains a `platforms` dict, each key being a platform name with platform-specific settings. Legacy flat scraper config is auto-migrated to `platforms.linkedin`.
  - REQ-003: `run_pipeline()` iterates over all enabled platforms in `config.scraper.platforms`, instantiates the correct scraper, and merges results before classification.
  - REQ-004: DB migration adds no new tables but validates `posts.platform` usage; all INSERT statements in the codebase explicitly set `platform`.
  - REQ-005: Existing LinkedIn scraper and all existing tests pass unchanged.
  - REQ-006: `make check && make test` passes.

### US-002 — Regex Keyword Matching
- Title: Replace substring whitelist/blacklist matching with regex
- Priority: 2
- Description: Currently `classifier/prompts.py` injects whitelist/blacklist keywords into the LLM prompt for substring matching. Change the pre-filter in `ClassificationEngine.classify_posts()` to use compiled `re.Pattern` matching instead. Remove keyword injection from the LLM prompt — regex matching should happen purely in Python before the API call.
- Acceptance Criteria:
  - REQ-007: Whitelist/blacklist keywords in config are treated as regex patterns (e.g., `"\\bAI\\b"` matches whole-word only).
  - REQ-008: `ClassificationEngine._apply_rules()` (or equivalent) compiles patterns once and matches against post text using `re.search()`.
  - REQ-009: The Claude system prompt no longer contains whitelist/blacklist keyword lists.
  - REQ-010: Invalid regex patterns raise a clear `ConfigError` at startup with the offending pattern.
  - REQ-011: Existing whitelist/blacklist test cases updated; new tests cover regex edge cases (anchors, groups, flags).
  - REQ-012: `make check && make test` passes.

### US-003 — Per-Platform Classifier Prompts
- Title: Support platform-specific classification prompts
- Priority: 3
- Description: Different platforms have different content characteristics (X is short-form, Reddit has subreddit context, Threads is conversational). Allow per-platform system prompt overrides in config while keeping a shared default prompt as fallback.
- Acceptance Criteria:
  - REQ-013: `config.classifier` accepts an optional `platform_prompts` dict keyed by platform name, each containing a `system_prompt` override string.
  - REQ-014: `ClassificationEngine.classify_posts()` groups posts by platform and uses the appropriate prompt for each batch.
  - REQ-015: If no platform-specific prompt exists, the default system prompt is used (backward compatible).
  - REQ-016: The classifier test suite includes a test classifying mixed-platform batches with different prompts.
  - REQ-017: `make check && make test` passes.

---

## Phase 2: Platform Scrapers

### US-004 — X (Twitter) Scraper
- Title: Add Playwright-based X home feed scraper
- Priority: 4
- Description: Implement `XScraper(AbstractScraper)` using Playwright to scrape the authenticated user's X home timeline. Follow the same pattern as `LinkedInScraper`: encrypted session storage, anti-detection measures, DOM extraction via JavaScript. Register in the scraper registry.
- Acceptance Criteria:
  - REQ-018: `XScraper` extends `AbstractScraper` and implements `login()`, `scrape_feed()`, `close()`.
  - REQ-019: `login()` opens `https://x.com` in headed mode for manual authentication, stores cookies encrypted via `auth.py`.
  - REQ-020: `scrape_feed()` loads stored cookies, navigates to home timeline, scrolls and extracts posts (author, text, URL, timestamp).
  - REQ-021: Posts are created with `platform="x"` and `id` derived from tweet URL or data attribute.
  - REQ-022: Anti-detection measures applied (random viewport, realistic scroll delays via `anti_detection.py`).
  - REQ-023: Session TTL validation reuses existing `validate_session()` logic with platform-specific cookie path.
  - REQ-024: Config example added to README or config template: `scraper.platforms.x.enabled: true`.
  - REQ-025: Unit tests with mocked Playwright covering login flow, scrape extraction, and error handling.
  - REQ-026: `make check && make test` passes.

### US-005 — Threads Scraper
- Title: Add Playwright-based Threads home feed scraper
- Priority: 5
- Description: Implement `ThreadsScraper(AbstractScraper)` using Playwright to scrape the authenticated user's Threads home feed. Threads has no public API for home feed access, so Playwright browser automation is required. Follow the same encrypted session + anti-detection pattern.
- Acceptance Criteria:
  - REQ-027: `ThreadsScraper` extends `AbstractScraper` and implements `login()`, `scrape_feed()`, `close()`.
  - REQ-028: `login()` opens `https://www.threads.net` in headed mode for manual authentication, stores cookies encrypted.
  - REQ-029: `scrape_feed()` loads cookies, navigates to home feed, scrolls and extracts posts (author, text, URL, timestamp).
  - REQ-030: Posts are created with `platform="threads"`.
  - REQ-031: Anti-detection and session TTL applied.
  - REQ-032: Unit tests with mocked Playwright.
  - REQ-033: `make check && make test` passes.

### US-006 — Reddit Scraper
- Title: Add Reddit home feed scraper using PRAW (official API)
- Priority: 6
- Description: Implement `RedditScraper(AbstractScraper)` using PRAW (Python Reddit API Wrapper) with OAuth. Reddit's free API tier supports reading the authenticated user's home feed at 60-100 QPM. Store OAuth credentials securely. No Playwright needed.
- Acceptance Criteria:
  - REQ-034: `RedditScraper` extends `AbstractScraper` and implements `login()`, `scrape_feed()`, `close()`.
  - REQ-035: `login()` performs OAuth flow using PRAW with `client_id`, `client_secret`, `username`, `password` from config (or env vars).
  - REQ-036: `scrape_feed()` reads the user's home feed (`reddit.front.hot()` or `reddit.front.best()`) and extracts posts (author, title+selftext, URL, subreddit, timestamp).
  - REQ-037: Posts are created with `platform="reddit"` and subreddit stored in post metadata.
  - REQ-038: Config: `scraper.platforms.reddit.client_id`, `client_secret`, `username`, `password` (or env var references).
  - REQ-039: Dependency `praw` added to `pyproject.toml`.
  - REQ-040: Unit tests with mocked PRAW client.
  - REQ-041: `make check && make test` passes.

### US-007 — RSS Feed Integration
- Title: Add RSS feed scraper for arbitrary feed URLs
- Priority: 7
- Description: Implement `RssScraper(AbstractScraper)` that fetches and parses RSS/Atom feeds from a configured list of URLs. Use `feedparser` library. No login required. Each feed item becomes a Post with `platform="rss"`.
- Acceptance Criteria:
  - REQ-042: `RssScraper` extends `AbstractScraper`; `login()` is a no-op; `scrape_feed()` fetches all configured feed URLs.
  - REQ-043: Config: `scraper.platforms.rss.feeds` is a list of `{url, name}` objects.
  - REQ-044: Each feed entry is mapped to a `Post` with: author from feed/entry, text from `summary` or `content`, URL from `link`, platform `"rss"`.
  - REQ-045: Dependency `feedparser` added to `pyproject.toml`.
  - REQ-046: Handles common RSS errors gracefully (timeout, malformed XML, 404).
  - REQ-047: Unit tests with sample RSS XML fixtures.
  - REQ-048: `make check && make test` passes.

---

## Phase 3: Deduplication & Stability

### US-008 — Semantic Deduplication
- Title: Add embedding-based cross-platform duplicate detection
- Priority: 8
- Description: Beyond SHA-256 exact hash dedup, add an optional semantic dedup pipeline stage. Use a configurable embedding model to compute vector embeddings for each post, detect high-similarity pairs (cosine similarity above threshold), then have Claude verify whether the pair is truly duplicate content. If confirmed, mark the newer post as a duplicate and skip classification. This is especially valuable for cross-platform dedup (same news on X, Reddit, LinkedIn).
- Acceptance Criteria:
  - REQ-049: New module `noise_cancel/dedup/` with `embedder.py` (abstract + implementations) and `semantic.py` (dedup logic).
  - REQ-050: `AbstractEmbedder` interface with `embed(texts: list[str]) -> list[list[float]]`. Implementations: `SentenceTransformerEmbedder` (local, default), `OpenAIEmbedder`, `VoyageEmbedder`.
  - REQ-051: Config: `dedup.semantic.enabled: false` (opt-in), `dedup.semantic.provider: "sentence-transformers"`, `dedup.semantic.model: "all-MiniLM-L6-v2"`, `dedup.semantic.threshold: 0.85`.
  - REQ-052: DB migration adds `embeddings` table: `post_id TEXT PRIMARY KEY, vector BLOB, model TEXT, created_at TEXT`.
  - REQ-053: Dedup stage runs after scraping, before classification. For each new post: compute embedding, query existing embeddings for cosine similarity > threshold, if found → call Claude to verify → if confirmed duplicate → mark post as `duplicate` (new status) and skip.
  - REQ-054: Claude verification prompt is minimal: given two post texts, answer "same content: yes/no" with one-sentence reasoning.
  - REQ-055: `sentence-transformers` added as optional dependency (`pip install noise-cancel[semantic]`).
  - REQ-056: Unit tests covering: embedding computation, similarity search, Claude verification mock, end-to-end dedup flow.
  - REQ-057: `make check && make test` passes.

### US-009 — Session Expiry Notification
- Title: Alert user when scraper sessions are expiring or expired
- Priority: 9
- Description: For Playwright-based scrapers (LinkedIn, X, Threads), detect session age and send notifications via delivery plugins. Pre-expiry warning (N days before) and post-expiry alert (when validation fails). Reddit/RSS don't need this.
- Acceptance Criteria:
  - REQ-058: `AbstractScraper` gains `session_age_days() -> float | None` and `session_expires_in_days() -> float | None` methods.
  - REQ-059: Config: `scraper.session_warning_days: 1` (default, notify this many days before expiry).
  - REQ-060: Pipeline checks session age before scraping; if within warning threshold, sends warning via delivery plugins: "⚠️ {Platform} session expires in ~{N}h. Run `noise-cancel login --platform {name}` to refresh."
  - REQ-061: On session validation failure, sends alert via delivery plugins before raising error: "❌ {Platform} session expired."
  - REQ-062: Falls back to stderr logging if no delivery plugins configured.
  - REQ-063: Unit tests with time-mocked session ages.
  - REQ-064: `make check && make test` passes.

---

## Phase 4: App UX Enhancements

### US-010 — Flutter Platform Indicator
- Title: Show platform origin on feed cards in Flutter app
- Priority: 10
- Description: Display which platform each post came from (LinkedIn, X, Threads, Reddit, RSS) on the swipe card UI. Use platform icons/badges with distinct colors.
- Acceptance Criteria:
  - REQ-065: Server `PostResponse` schema includes `platform` field (already in DB, expose via API).
  - REQ-066: Flutter `Post` model includes `platform` field parsed from JSON.
  - REQ-067: `PostCard` widget displays a platform badge (icon + label) in the top-right corner. Icons: LinkedIn (blue), X (black/white), Threads (black), Reddit (orange), RSS (orange).
  - REQ-068: Platform badge uses the platform's brand color as background with white text/icon.
  - REQ-069: `GET /api/posts` supports optional `platform` query parameter for filtering.
  - REQ-070: `make check && make test` passes.

### US-011 — Archive View with Search
- Title: Add browsable archive screen with keyword search and platform filter
- Priority: 11
- Description: Users who swiped left (archived) posts should be able to browse and search them. Add a "저장고" (Archive) button in the top-left of the swipe screen. Tapping it opens an archive screen with a search bar (keyword search on post body), platform filter chips, and a list of archived posts sorted newest-first.
- Acceptance Criteria:
  - REQ-071: Server endpoint `GET /api/posts?swipe_status=archived&q={keyword}&platform={platform}` supports keyword search via SQL `LIKE '%keyword%'` on `post_text` and optional platform filter.
  - REQ-072: Flutter `ArchiveScreen` widget with: AppBar titled "저장고", search bar at top, horizontal platform filter chips (All, LinkedIn, X, Threads, Reddit, RSS), scrollable list of archived posts.
  - REQ-073: Search is debounced (300ms) and triggers API call with `q` parameter.
  - REQ-074: Posts displayed as compact list items (not swipe cards): platform badge, author, truncated text, date.
  - REQ-075: Tapping a list item expands to show full post content (reuse `ExpandedContent` widget).
  - REQ-076: "저장고" button added to SwipeScreen AppBar leading position (left side). Shows archive icon with count badge.
  - REQ-077: Infinite scroll pagination (20 items per page).
  - REQ-078: `make check && make test` passes.

### US-012 — Post Notes/Comments Feature
- Title: Allow users to add personal notes to feed items
- Priority: 12
- Description: Users can attach short text notes to any post (from swipe view or archive view). Notes are stored locally and synced to server. Posts with notes show a note indicator icon.
- Acceptance Criteria:
  - REQ-079: DB migration adds `notes` table: `id TEXT PRIMARY KEY, classification_id TEXT UNIQUE REFERENCES classifications(id), note_text TEXT NOT NULL, created_at TEXT, updated_at TEXT`.
  - REQ-080: Server endpoints: `POST /api/posts/{id}/note` (create/update), `GET /api/posts/{id}/note` (read), `DELETE /api/posts/{id}/note`.
  - REQ-081: `PostResponse` includes `note: string | null` field.
  - REQ-082: Flutter: long-press on a post card opens a bottom sheet with a text field for note entry. Save button persists to server.
  - REQ-083: Posts with notes display a small note icon (📝) indicator on the card.
  - REQ-084: In archive view, notes are shown below the post text if present.
  - REQ-085: `make check && make test` passes.

### US-013 — Cross-Platform Share Feature
- Title: Add share functionality using share_plus package
- Priority: 13
- Description: Allow users to share post content externally via the native OS share sheet (iOS, Android, etc.). Share includes post text + original URL. Accessible from both swipe cards and archive view.
- Acceptance Criteria:
  - REQ-086: `share_plus` dependency added to `app/pubspec.yaml`.
  - REQ-087: Share button on post cards (bottom-right area) and in archive expanded view.
  - REQ-088: Share content format: `"{author_name} ({platform})\n\n{post_text}\n\n{post_url}"`. If note exists, append `"\n\n💭 My note: {note_text}"`.
  - REQ-089: Share action triggers native share sheet on both iOS and Android.
  - REQ-090: `make check && make test` passes (Flutter build succeeds).

---

## Phase 5: AI & Feedback

### US-014 — AI Unified Daily Digest
- Title: Generate and deliver a cross-platform daily feed digest via Claude
- Priority: 14
- Description: After daily classification, generate a consolidated digest summarizing all "Read"-classified posts across all platforms. Use Claude to produce a 3-5 line summary with themes and highlights. Deliver via existing delivery plugins (Slack, etc.).
- Acceptance Criteria:
  - REQ-091: New CLI command `noise-cancel digest` (or `--digest` flag on `deliver` command).
  - REQ-092: Digest logic: query all Read-classified posts from the last 24h (across all platforms), send to Claude with a digest prompt, receive structured summary.
  - REQ-093: Digest output format includes: date, platform breakdown (count per platform), theme summary (3-5 bullets), notable posts, and total stats (saved/filtered counts).
  - REQ-094: Delivered via existing `DeliveryPlugin.deliver()` — add `deliver_digest(digest_text)` method to `DeliveryPlugin` base class.
  - REQ-095: Config: `delivery.digest.enabled: true`.
  - REQ-096: SlackPlugin formats digest using Block Kit (header, sections, dividers).
  - REQ-097: Server endpoint `POST /api/digest/generate` triggers digest generation and returns the text.
  - REQ-098: Unit tests with mocked Claude response and delivery.
  - REQ-099: `make check && make test` passes.

### US-015 — Feedback Data Accumulation Infrastructure
- Title: Store swipe feedback data for future classifier learning
- Priority: 15
- Description: Build the data accumulation infrastructure so swipe decisions (archive = positive signal, delete = negative signal) are stored in a structured format suitable for future model improvement. No actual learning/fine-tuning in this story — just data capture and basic analytics.
- Acceptance Criteria:
  - REQ-100: DB migration adds `feedback` table: `id TEXT PRIMARY KEY, classification_id TEXT REFERENCES classifications(id), action TEXT NOT NULL ('archive'|'delete'), platform TEXT, category TEXT, confidence REAL, created_at TEXT`.
  - REQ-101: When `archive_post()` or `delete_post()` is called, a feedback record is automatically inserted.
  - REQ-102: New CLI command `noise-cancel feedback-stats` showing: total feedback count, archive/delete ratio per platform, archive/delete ratio per category, confidence distribution of overrides (deleted "Read" posts or archived "Skip" posts).
  - REQ-103: Server endpoint `GET /api/feedback/stats` returns the same data as JSON.
  - REQ-104: Feedback data includes enough context for future few-shot injection or preference profiling (links to classification details).
  - REQ-105: Unit tests covering feedback insertion and stats queries.
  - REQ-106: `make check && make test` passes.

---

## Implementation Notes

### Dependency Additions
- `praw` — Reddit API wrapper
- `feedparser` — RSS/Atom feed parsing
- `sentence-transformers` (optional) — local embedding model for semantic dedup
- `share_plus` (Flutter) — native OS share sheet

### Database Migrations Required
- `005_add_embeddings.sql` — embeddings table for semantic dedup
- `006_add_notes.sql` — notes table for post comments
- `007_add_feedback.sql` — feedback table for swipe data accumulation

### Config Structure Evolution
```yaml
scraper:
  session_warning_days: 1
  platforms:
    linkedin:
      enabled: true
      headless: true
      scroll_count: 10
    x:
      enabled: false
      headless: true
      scroll_count: 10
    threads:
      enabled: false
      headless: true
      scroll_count: 10
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
  whitelist:
    keywords: ["\\bAI\\b", "machine learning"]  # Now regex patterns
  blacklist:
    keywords: ["hiring|job opening"]
  platform_prompts:
    reddit:
      system_prompt: "You are classifying Reddit posts. Consider the subreddit context..."
    x:
      system_prompt: "You are classifying X/Twitter posts. These are short-form..."

dedup:
  semantic:
    enabled: false
    provider: sentence-transformers  # or openai, voyage
    model: all-MiniLM-L6-v2
    threshold: 0.85
    # provider-specific settings
    openai_api_key: ${OPENAI_API_KEY}
    voyage_api_key: ${VOYAGE_API_KEY}

delivery:
  digest:
    enabled: true
```
