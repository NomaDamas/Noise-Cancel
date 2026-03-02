from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from noise_cancel.config import AppConfig, default_config_path, generate_default_config, load_config
from noise_cancel.database import apply_migrations, get_connection

app = typer.Typer(name="noise-cancel", help="AI-powered LinkedIn feed noise filter.")
console = Console()


def _get_config(config_path: str | None = None) -> AppConfig:
    return load_config(config_path)


def _get_db(config: AppConfig):
    data_dir = Path(config.general["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "noise_cancel.db"
    conn = get_connection(str(db_path))
    apply_migrations(conn)
    return conn


def _metric_value(run_type: str, metric: str, value: int) -> int | None:
    applicable_metrics = {
        "scrape": {"posts_scraped"},
        "classify": {"posts_classified"},
        "deliver": {"posts_delivered"},
        "digest": {"posts_delivered"},
        "pipeline": {"posts_scraped", "posts_classified", "posts_delivered"},
    }
    if metric not in applicable_metrics.get(run_type, set()):
        return None
    return value


def _run_log_view(row: dict) -> dict:
    run_type = row["run_type"]
    return {
        "run_id": row["id"],
        "run_type": run_type,
        "status": row["status"],
        "started_at": row["started_at"],
        "posts_scraped": _metric_value(run_type, "posts_scraped", row["posts_scraped"]),
        "posts_classified": _metric_value(run_type, "posts_classified", row["posts_classified"]),
        "posts_delivered": _metric_value(run_type, "posts_delivered", row["posts_delivered"]),
        "error_message": row["error_message"],
    }


def _truncate_preview(value: str | None, max_len: int) -> str:
    if value is None:
        return "-"
    normalized = " ".join(value.split())
    if not normalized:
        return "-"
    if len(normalized) <= max_len:
        return normalized
    if max_len <= 3:
        return normalized[:max_len]
    return normalized[: max_len - 3] + "..."


def _build_stats_payload(conn, run_id: str | None, limit_posts: int) -> dict | None:
    from noise_cancel.logger.metrics import (
        get_category_counts_for_window,
        get_classification_count_for_window,
        get_classification_details_for_window,
        get_classify_run_by_id,
        get_latest_classify_run,
        get_next_classify_run_started_at,
    )

    if run_id is not None:
        target_run = get_classify_run_by_id(conn, run_id)
        if target_run is None:
            raise ValueError(run_id)
    else:
        target_run = get_latest_classify_run(conn)
        if target_run is None:
            return None

    window_end = get_next_classify_run_started_at(conn, target_run["started_at"], target_run["id"])
    inferred_total = get_classification_count_for_window(conn, target_run["started_at"], window_end)
    category_counts = get_category_counts_for_window(conn, target_run["started_at"], window_end)
    detail_rows = get_classification_details_for_window(
        conn,
        target_run["started_at"],
        window_end,
        limit=limit_posts,
    )

    detail_payload = [
        {
            "classification_id": row["classification_id"],
            "post_id": row["post_id"],
            "author_name": row["author_name"],
            "category": row["category"],
            "classified_at": row["classified_at"],
            "post_preview": _truncate_preview(row["post_text"], 180),
            "reasoning_preview": _truncate_preview(row["reasoning"], 160),
        }
        for row in detail_rows
    ]

    logged_count = int(target_run.get("posts_classified", 0))
    warning: str | None = None
    if inferred_total != logged_count:
        warning = (
            "Count mismatch: run log posts_classified="
            f"{logged_count}, inferred rows={inferred_total} (timestamp-window inference)."
        )

    return {
        "run": {
            "run_id": target_run["id"],
            "started_at": target_run["started_at"],
            "status": target_run["status"],
            "logged_posts_classified": logged_count,
            "inferred_total": inferred_total,
            "window_end": window_end,
        },
        "category_counts": category_counts,
        "details": detail_payload,
        "warning": warning,
    }


def _render_stats_output(payload: dict, limit_posts: int) -> None:
    console.print(f"[cyan]Classify Run:[/cyan] {payload['run']['run_id']}")
    console.print(f"[cyan]Started At:[/cyan] {payload['run']['started_at']}")
    console.print(f"[cyan]Status:[/cyan] {payload['run']['status']}")
    console.print(f"[cyan]Logged Classified:[/cyan] {payload['run']['logged_posts_classified']}")
    console.print(f"[cyan]Inferred Rows:[/cyan] {payload['run']['inferred_total']}")

    if payload["warning"] is not None:
        console.print(f"[yellow]{payload['warning']}[/yellow]")

    if payload["category_counts"]:
        category_table = Table(title="Category Counts")
        category_table.add_column("category")
        category_table.add_column("count", justify="right")
        for category, count in payload["category_counts"].items():
            category_table.add_row(category, str(count))
        console.print(category_table)
    else:
        console.print("No inferred classifications for this run.")

    if payload["details"]:
        detail_table = Table(title=f"Details (up to {limit_posts} rows)")
        detail_table.add_column("post_id")
        detail_table.add_column("author")
        detail_table.add_column("category")
        detail_table.add_column("post_preview")
        detail_table.add_column("reasoning_preview")
        for row in payload["details"]:
            detail_table.add_row(
                row["post_id"],
                row["author_name"] or "-",
                row["category"],
                row["post_preview"],
                row["reasoning_preview"],
            )
        console.print(detail_table)
    else:
        console.print("No classification details found for this run.")


def _render_feedback_breakdown(title: str, rows: list[dict], label_key: str) -> None:
    table = Table(title=title)
    table.add_column(label_key)
    table.add_column("archive", justify="right")
    table.add_column("delete", justify="right")
    table.add_column("total", justify="right")
    table.add_column("archive_ratio", justify="right")
    table.add_column("delete_ratio", justify="right")
    for row in rows:
        table.add_row(
            row[label_key],
            str(row["archive_count"]),
            str(row["delete_count"]),
            str(row["total"]),
            f"{row['archive_ratio']:.3f}",
            f"{row['delete_ratio']:.3f}",
        )
    console.print(table)


def _render_feedback_stats_output(payload: dict) -> None:
    total_feedback = payload["total_feedback"]
    console.print(f"Total Feedback: {total_feedback}")
    if total_feedback == 0:
        console.print("No feedback records found.")
        return

    _render_feedback_breakdown("Archive/Delete Ratio by Platform", payload["by_platform"], "platform")
    _render_feedback_breakdown("Archive/Delete Ratio by Category", payload["by_category"], "category")

    overrides = payload["override_confidence"]
    console.print(f"Override Count: {overrides['total_overrides']}")
    avg_confidence = overrides["average_confidence"]
    if avg_confidence is None:
        console.print("Average Override Confidence: -")
    else:
        console.print(f"Average Override Confidence: {avg_confidence:.3f}")

    distribution_table = Table(title='Override Confidence Distribution (delete "Read" or archive "Skip")')
    distribution_table.add_column("bucket")
    distribution_table.add_column("count", justify="right")
    for row in overrides["distribution"]:
        distribution_table.add_row(row["bucket"], str(row["count"]))
    console.print(distribution_table)


@app.command()
def init(
    config_path: str | None = typer.Option(None, "--config", help="Path to write config YAML"),
) -> None:
    """Generate default config file at ~/.config/noise-cancel/config.yaml."""
    path = Path(config_path) if config_path else default_config_path()
    if path.exists():
        console.print(f"[yellow]Config already exists:[/yellow] {path}")
        console.print("Edit it directly or delete it first to regenerate.")
        raise typer.Exit(1)
    generated = generate_default_config(path)
    console.print(f"[green]Config created:[/green] {generated}")
    console.print("Edit this file to customize categories, rules, and delivery settings.")


@app.command()
def config(
    config_path: str | None = typer.Option(None, "--config", help="Path to config YAML"),
) -> None:
    """Show current configuration."""
    cfg = _get_config(config_path)
    console.print(cfg.model_dump())


@app.command()
def login(
    config_path: str | None = typer.Option(None, "--config", help="Path to config YAML"),
    platform: str = typer.Option("linkedin", "--platform", help="Platform to login to"),
) -> None:
    """Open browser for manual platform login and save session cookies."""
    import asyncio

    from noise_cancel.scraper import SCRAPER_REGISTRY

    cfg = _get_config(config_path)
    data_dir = Path(cfg.general["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        scraper_class = SCRAPER_REGISTRY.get(platform)
    except KeyError:
        available = ", ".join(sorted(SCRAPER_REGISTRY.mappings().keys()))
        console.print(f"[red]Unknown platform '{platform}'. Available: {available}[/red]")
        raise typer.Exit(1) from None

    console.print(f"[cyan]Opening browser for {platform} login...[/cyan]")
    console.print("[cyan]Please log in manually. Waiting up to 5 minutes...[/cyan]")

    scraper = scraper_class(cfg)
    try:
        asyncio.run(scraper.login(headed=True))
    except KeyboardInterrupt:
        console.print("\n[yellow]Login cancelled.[/yellow]")
        raise typer.Exit(1) from None

    storage_state = getattr(scraper, "storage_state", None)
    if storage_state is None:
        console.print(f"[green]Login for {platform} completed.[/green]")
        return

    from noise_cancel.scraper.auth import generate_key, save_session

    # Use platform-specific session paths if available, else fall back to default
    session_paths_fn = getattr(scraper, "_session_paths", None)
    if session_paths_fn is not None:
        key_path, session_path = session_paths_fn()
    else:
        key_path = data_dir / "session.key"
        session_path = data_dir / "session.enc"

    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        key = key_path.read_text().strip()
    else:
        key = generate_key()
        key_path.write_text(key)
        key_path.chmod(0o600)

    save_session(storage_state, key, str(session_path))
    session_path.chmod(0o600)

    console.print(f"[green]Login successful! Session saved to {session_path}[/green]")


@app.command()
def scrape(  # noqa: C901
    config_path: str | None = typer.Option(None, "--config"),
    verbose: bool = typer.Option(False, "--verbose"),
    limit: int | None = typer.Option(None, "--limit", help="Max posts to save (overrides config)"),
    platform: str | None = typer.Option(None, "--platform", help="Platform to scrape (default: all enabled)"),
) -> None:
    """Scrape feed posts from one or all enabled platforms."""
    import asyncio
    import uuid

    from noise_cancel.content_hash import compute_content_hash
    from noise_cancel.logger.repository import insert_post, insert_run_log, update_run_log
    from noise_cancel.models import RunLog
    from noise_cancel.scraper import SCRAPER_REGISTRY

    cfg = _get_config(config_path)
    conn = _get_db(cfg)

    run_id = uuid.uuid4().hex
    run_log = RunLog(id=run_id, run_type="scrape")
    insert_run_log(conn, run_log)

    # Determine which platforms to scrape
    if platform is not None:
        platform_names = [platform.strip().lower()]
    else:
        # Use enabled platforms from config, defaulting to ["linkedin"] for backward compat
        platforms_cfg = cfg.scraper.get("platforms", {})
        if isinstance(platforms_cfg, dict) and platforms_cfg:
            platform_names = list(platforms_cfg.keys())
        else:
            platform_names = ["linkedin"]

    scroll_count = cfg.scraper.get("scroll_count", 10)
    max_posts = limit if limit is not None else cfg.general.get("max_posts_per_run", 50)

    total_saved = 0
    total_dupes = 0

    for plat_name in platform_names:
        try:
            scraper_class = SCRAPER_REGISTRY.get(plat_name)
        except KeyError:
            console.print(f"[yellow]Skipping unknown platform '{plat_name}'.[/yellow]")
            continue

        scraper = scraper_class(cfg)

        if verbose:
            console.print(f"[cyan]Scraping {plat_name} with {scroll_count} scrolls...[/cyan]")

        try:
            posts = asyncio.run(scraper.scrape_feed(scroll_count=scroll_count))
        except RuntimeError as exc:
            console.print(f"[red]Scrape failed for {plat_name}: {exc}[/red]")
            if len(platform_names) == 1:
                update_run_log(conn, run_id, status="error", error_message=str(exc))
                raise typer.Exit(1) from None
            continue
        except Exception as exc:
            console.print(f"[red]Scrape failed for {plat_name}: {exc}[/red]")
            if len(platform_names) == 1:
                update_run_log(conn, run_id, status="error", error_message=str(exc))
                raise typer.Exit(1) from None
            continue

        posts = posts[:max_posts]

        saved = 0
        dupes = 0
        for post in posts:
            post.run_id = run_id
            post.content_hash = compute_content_hash(post.post_text)
            if insert_post(conn, post):
                saved += 1
            else:
                dupes += 1

        total_saved += saved
        total_dupes += dupes

        if verbose:
            console.print(f"[cyan]{plat_name}: {saved} saved, {dupes} dupes[/cyan]")

    update_run_log(conn, run_id, status="completed", posts_scraped=total_saved)

    console.print(f"[green]Scraped {total_saved} posts ({total_dupes} duplicates skipped).[/green]")
    if verbose:
        console.print(f"Run ID: {run_id}")


@app.command()
def classify(
    config_path: str | None = typer.Option(None, "--config"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    limit: int | None = typer.Option(None, "--limit", help="Max posts to classify"),
) -> None:
    """Classify unclassified posts using AI."""
    import uuid

    from noise_cancel.logger.repository import (
        get_unclassified_posts,
        insert_classification,
        insert_run_log,
        update_run_log,
    )
    from noise_cancel.models import Classification, Post, RunLog

    cfg = _get_config(config_path)
    conn = _get_db(cfg)

    run_id = uuid.uuid4().hex
    run_log = RunLog(id=run_id, run_type="classify")
    insert_run_log(conn, run_log)

    max_posts = limit if limit is not None else cfg.general.get("max_posts_per_run", 50)
    rows = get_unclassified_posts(conn, limit=max_posts)

    if not rows:
        console.print("No unclassified posts found.")
        update_run_log(conn, run_id, status="completed", posts_classified=0)
        return

    posts = [Post(**row) for row in rows]
    posts_for_classification = posts

    semantic_dedup_cfg = cfg.dedup.get("semantic", {})
    if bool(semantic_dedup_cfg.get("enabled", False)):
        from noise_cancel.dedup.embedder import create_embedder_from_config
        from noise_cancel.dedup.semantic import ClaudeDuplicateVerifier, SemanticDeduplicator

        deduplicator = SemanticDeduplicator(
            conn=conn,
            config=cfg,
            embedder=create_embedder_from_config(cfg),
            verifier=ClaudeDuplicateVerifier(cfg).verify,
        )
        posts_for_classification = deduplicator.deduplicate(posts_for_classification)

        if not posts_for_classification:
            update_run_log(conn, run_id, status="completed", posts_classified=0)
            console.print("No non-duplicate posts remaining after semantic dedup.")
            return

    try:
        from noise_cancel.classifier.engine import ClassificationEngine

        engine = ClassificationEngine(cfg)
        results = engine.classify_posts(posts_for_classification)
    except Exception as exc:
        console.print(f"[red]Classification failed: {exc}[/red]")
        update_run_log(conn, run_id, status="error", error_message=str(exc))
        raise typer.Exit(1) from None

    model_used = cfg.classifier.get("model", "unknown")

    for pc in results:
        cls = Classification(
            id=uuid.uuid4().hex,
            post_id=posts_for_classification[pc.post_index].id,
            category=pc.category,
            confidence=pc.confidence,
            reasoning=pc.reasoning,
            summary=pc.summary,
            applied_rules=pc.applied_rules,
            model_used=model_used,
        )
        if dry_run:
            console.print(f"  [{cls.category}] {posts_for_classification[pc.post_index].author_name}: {cls.reasoning}")
        else:
            insert_classification(conn, cls)

    update_run_log(conn, run_id, status="completed", posts_classified=len(results))
    if dry_run:
        console.print(f"[yellow]Dry run: {len(results)} classifications (not saved).[/yellow]")
    else:
        console.print(f"[green]Classified {len(results)} posts.[/green]")


def _build_delivery_pairs(conn, cls_rows: list[dict]) -> list[tuple]:
    from noise_cancel.logger.repository import get_post_by_id
    from noise_cancel.models import Classification, Post

    pairs: list[tuple[Post, Classification]] = []
    for row in cls_rows:
        post_row = get_post_by_id(conn, row["post_id"])
        if post_row is None:
            continue
        applied_rules = row["applied_rules"]
        if isinstance(applied_rules, str):
            applied_rules = json.loads(applied_rules)
        # Scraped text may contain surrogate characters that break JSON encoding
        if post_row.get("post_text"):
            post_row["post_text"] = post_row["post_text"].encode("utf-8", errors="replace").decode("utf-8")
        post = Post(**post_row)
        cls = Classification(
            id=row["id"],
            post_id=row["post_id"],
            category=row["category"],
            confidence=row["confidence"],
            reasoning=row["reasoning"],
            summary=row.get("summary", ""),
            applied_rules=applied_rules,
            model_used=row["model_used"],
            classified_at=row["classified_at"],
            delivered=row["delivered"],
            delivered_at=row["delivered_at"],
        )
        pairs.append((post, cls))
    return pairs


def _deliver_with_plugins(pairs: list[tuple], cfg: AppConfig) -> int:
    from noise_cancel.delivery.loader import get_delivery_plugin_class

    delivered_count = 0
    plugins = cfg.delivery.get("plugins", [])
    for plugin_config in plugins:
        if not isinstance(plugin_config, dict):
            continue
        plugin_type = plugin_config.get("type")
        if not isinstance(plugin_type, str) or not plugin_type.strip():
            continue

        plugin_class = get_delivery_plugin_class(plugin_type)
        plugin = plugin_class()
        plugin.validate_config(plugin_config)
        delivered_count += plugin.deliver(pairs, cfg)
    return delivered_count


def _included_delivery_categories(cfg: AppConfig) -> set[str]:
    categories: set[str] = set()
    plugins = cfg.delivery.get("plugins", [])
    for plugin_config in plugins:
        if not isinstance(plugin_config, dict):
            continue
        include_categories = plugin_config.get("include_categories", [])
        if not isinstance(include_categories, list):
            continue
        categories.update(category for category in include_categories if isinstance(category, str))
    return categories


@app.command()
def deliver(
    config_path: str | None = typer.Option(None, "--config"),
    digest: bool = typer.Option(False, "--digest", help="Also generate and deliver daily digest."),
) -> None:
    """Deliver classified posts via configured delivery plugins."""
    import uuid

    from noise_cancel.digest.service import generate_and_deliver_digest
    from noise_cancel.logger.repository import (
        get_undelivered_classifications,
        insert_run_log,
        mark_delivered,
        update_run_log,
    )
    from noise_cancel.models import RunLog

    cfg = _get_config(config_path)
    conn = _get_db(cfg)

    run_id = uuid.uuid4().hex
    run_log = RunLog(id=run_id, run_type="deliver")
    insert_run_log(conn, run_log)

    cls_rows = get_undelivered_classifications(conn)
    if not cls_rows:
        console.print("No undelivered classifications found.")
        update_run_log(conn, run_id, status="completed", posts_delivered=0)
        return

    pairs = _build_delivery_pairs(conn, cls_rows)
    delivered_count = _deliver_with_plugins(pairs, cfg)

    include_categories = _included_delivery_categories(cfg)
    for _, cls in pairs:
        if cls.category in include_categories:
            mark_delivered(conn, cls.id)

    update_run_log(conn, run_id, status="completed", posts_delivered=delivered_count)
    console.print(f"[green]Delivered {delivered_count} posts.[/green]")

    if not digest:
        return

    try:
        digest_result = generate_and_deliver_digest(conn, cfg)
    except Exception as exc:
        console.print(f"[red]Digest generation failed: {exc}[/red]")
        return
    console.print(digest_result.digest_text)
    if digest_result.delivery_enabled:
        console.print(f"Delivered digest to {digest_result.delivered_plugins} plugin(s).")
    else:
        console.print("Digest delivery is disabled in config (delivery.digest.enabled=false).")


@app.command()
def digest(
    config_path: str | None = typer.Option(None, "--config"),
) -> None:
    """Generate and deliver the daily cross-platform digest."""
    import uuid

    from noise_cancel.digest.service import generate_and_deliver_digest
    from noise_cancel.logger.repository import insert_run_log, update_run_log
    from noise_cancel.models import RunLog

    cfg = _get_config(config_path)
    conn = _get_db(cfg)

    run_id = uuid.uuid4().hex
    run_log = RunLog(id=run_id, run_type="digest")
    insert_run_log(conn, run_log)

    try:
        digest_result = generate_and_deliver_digest(conn, cfg)
    except Exception as exc:
        update_run_log(conn, run_id, status="error", error_message=str(exc))
        console.print(f"[red]Digest generation failed: {exc}[/red]")
        raise typer.Exit(1) from None

    update_run_log(
        conn,
        run_id,
        status="completed",
        posts_delivered=digest_result.delivered_plugins,
    )
    console.print(digest_result.digest_text)
    if digest_result.delivery_enabled:
        console.print(f"Delivered digest to {digest_result.delivered_plugins} plugin(s).")
    else:
        console.print("Digest delivery is disabled in config (delivery.digest.enabled=false).")


@app.command()
def run(  # noqa: C901
    config_path: str | None = typer.Option(None, "--config"),
    verbose: bool = typer.Option(False, "--verbose"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    limit: int | None = typer.Option(None, "--limit", help="Max posts per step"),
) -> None:
    """Run full pipeline: scrape -> classify -> deliver."""
    import uuid

    from noise_cancel.logger.repository import get_run_logs, insert_run_log, update_run_log
    from noise_cancel.models import RunLog

    cfg = _get_config(config_path)
    conn = _get_db(cfg)

    run_id = uuid.uuid4().hex
    run_log = RunLog(id=run_id, run_type="pipeline")
    insert_run_log(conn, run_log)

    console.print("[cyan]Pipeline: scrape -> classify -> deliver[/cyan]")

    steps = [
        ("scrape", lambda: scrape(config_path=config_path, verbose=verbose, limit=limit, platform=None)),
        ("classify", lambda: classify(config_path=config_path, dry_run=dry_run, limit=limit)),
    ]
    if not dry_run:
        steps.append(("deliver", lambda: deliver(config_path=config_path, digest=False)))

    for step_name, step_fn in steps:
        try:
            step_fn()
        except (SystemExit, typer.Exit) as exc:
            if getattr(exc, "code", 1):
                update_run_log(conn, run_id, status="error", error_message=f"{step_name} failed")
                console.print(f"[red]Pipeline stopped at {step_name}.[/red]")
                raise typer.Exit(1) from None

    # Aggregate metrics from child run_logs into the pipeline run_log
    child_runs = get_run_logs(conn, limit=10)
    posts_scraped = 0
    posts_classified = 0
    for cr in child_runs:
        if cr["id"] == run_id:
            continue
        if cr.get("run_type") == "scrape":
            posts_scraped += cr.get("posts_scraped", 0) or 0
            break
    for cr in child_runs:
        if cr["id"] == run_id:
            continue
        if cr.get("run_type") == "classify":
            posts_classified += cr.get("posts_classified", 0) or 0
            break

    update_run_log(
        conn,
        run_id,
        status="completed",
        posts_scraped=posts_scraped,
        posts_classified=posts_classified,
    )
    console.print("[green]Pipeline complete.[/green]")


@app.command()
def logs(
    config_path: str | None = typer.Option(None, "--config"),
    limit: int = typer.Option(20, "--limit"),
    run_type: str | None = typer.Option(None, "--run-type"),
    status: str | None = typer.Option(None, "--status"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Show filtering logs."""
    from noise_cancel.logger.repository import get_run_logs

    cfg = _get_config(config_path)
    conn = _get_db(cfg)

    rows = get_run_logs(conn, limit=limit, run_type=run_type, status=status)
    if not rows:
        console.print("No run logs found.")
        return

    logs_payload = [_run_log_view(row) for row in rows]
    if as_json:
        typer.echo(json.dumps(logs_payload, indent=2))
        return

    table = Table(title="Run Logs")
    table.add_column("run_id")
    table.add_column("run_type")
    table.add_column("status")
    table.add_column("started_at")
    table.add_column("scraped", justify="right")
    table.add_column("classified", justify="right")
    table.add_column("delivered", justify="right")
    table.add_column("error")

    for row in logs_payload:
        table.add_row(
            row["run_id"],
            row["run_type"],
            row["status"],
            row["started_at"] or "-",
            str(row["posts_scraped"]) if row["posts_scraped"] is not None else "-",
            str(row["posts_classified"]) if row["posts_classified"] is not None else "-",
            str(row["posts_delivered"]) if row["posts_delivered"] is not None else "-",
            row["error_message"] or "-",
        )

    console.print(table)


@app.command()
def stats(
    config_path: str | None = typer.Option(None, "--config"),
    run_id: str | None = typer.Option(None, "--run-id", help="Specific classify run ID to inspect"),
    limit_posts: int = typer.Option(50, "--limit-posts", min=1, help="Max detailed posts to show"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show classify-run debugging statistics."""
    cfg = _get_config(config_path)
    conn = _get_db(cfg)

    try:
        payload = _build_stats_payload(conn, run_id, limit_posts)
    except ValueError as exc:
        console.print(f"[red]Classify run not found: {exc}[/red]")
        raise typer.Exit(1) from None

    if payload is None:
        console.print("No classify runs found.")
        return

    if as_json:
        typer.echo(json.dumps(payload, indent=2))
        return

    _render_stats_output(payload, limit_posts)


@app.command("feedback-stats")
def feedback_stats(
    config_path: str | None = typer.Option(None, "--config"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show swipe feedback accumulation statistics."""
    from noise_cancel.logger.repository import get_feedback_stats

    cfg = _get_config(config_path)
    conn = _get_db(cfg)
    payload = get_feedback_stats(conn)

    if as_json:
        typer.echo(json.dumps(payload, indent=2))
        return

    _render_feedback_stats_output(payload)
