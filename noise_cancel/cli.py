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
) -> None:
    """Open browser for manual LinkedIn login and save session cookies."""
    import asyncio

    cfg = _get_config(config_path)
    data_dir = Path(cfg.general["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)

    console.print("[cyan]Opening browser for LinkedIn login...[/cyan]")
    console.print("[cyan]Please log in manually. Waiting up to 5 minutes...[/cyan]")

    from noise_cancel.scraper.linkedin import LinkedInScraper

    scraper = LinkedInScraper(cfg)
    try:
        asyncio.run(scraper.login(headed=True))
    except KeyboardInterrupt:
        console.print("\n[yellow]Login cancelled.[/yellow]")
        raise typer.Exit(1) from None

    storage_state = scraper.storage_state
    if storage_state is None:
        console.print("[red]Login failed — no session captured.[/red]")
        raise typer.Exit(1)

    from noise_cancel.scraper.auth import generate_key, save_session

    key_path = data_dir / "session.key"
    session_path = data_dir / "session.enc"

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
def scrape(
    config_path: str | None = typer.Option(None, "--config"),
    verbose: bool = typer.Option(False, "--verbose"),
    limit: int | None = typer.Option(None, "--limit", help="Max posts to save (overrides config)"),
) -> None:
    """Scrape LinkedIn feed posts."""
    import asyncio
    import sqlite3
    import uuid

    from noise_cancel.content_hash import compute_content_hash
    from noise_cancel.logger.repository import insert_post, insert_run_log, update_run_log
    from noise_cancel.models import RunLog
    from noise_cancel.scraper.auth import is_session_valid, load_session
    from noise_cancel.scraper.linkedin import LinkedInScraper

    cfg = _get_config(config_path)
    data_dir = Path(cfg.general["data_dir"])
    conn = _get_db(cfg)

    run_id = uuid.uuid4().hex
    run_log = RunLog(id=run_id, run_type="scrape")
    insert_run_log(conn, run_log)

    key_path = data_dir / "session.key"
    session_path = data_dir / "session.enc"
    ttl_days = cfg.scraper.get("session_ttl_days", 7)

    if not session_path.exists() or not key_path.exists():
        console.print("[red]No session found. Run 'noise-cancel login' first.[/red]")
        update_run_log(conn, run_id, status="error", error_message="No session found")
        raise typer.Exit(1)

    if not is_session_valid(str(session_path), ttl_days=ttl_days):
        console.print("[red]Session expired. Run 'noise-cancel login' to refresh.[/red]")
        update_run_log(conn, run_id, status="error", error_message="Session expired")
        raise typer.Exit(1)

    key = key_path.read_text().strip()
    session_data = load_session(key, str(session_path))
    if session_data is None:
        console.print("[red]Failed to decrypt session. Run 'noise-cancel login' again.[/red]")
        update_run_log(conn, run_id, status="error", error_message="Decryption failed")
        raise typer.Exit(1)

    scraper = LinkedInScraper(cfg)
    scraper.load_storage_state(session_data)

    scroll_count = cfg.scraper.get("scroll_count", 10)
    if verbose:
        console.print(f"[cyan]Scraping with {scroll_count} scrolls...[/cyan]")

    try:
        posts = asyncio.run(scraper.scrape_feed(scroll_count=scroll_count))
    except RuntimeError as exc:
        console.print(f"[red]Scrape failed: {exc}[/red]")
        update_run_log(conn, run_id, status="error", error_message=str(exc))
        raise typer.Exit(1) from None

    max_posts = limit if limit is not None else cfg.general.get("max_posts_per_run", 50)
    posts = posts[:max_posts]

    saved = 0
    dupes = 0
    for post in posts:
        post.run_id = run_id
        post.content_hash = compute_content_hash(post.post_text)
        try:
            insert_post(conn, post)
            saved += 1
        except sqlite3.IntegrityError:
            dupes += 1

    update_run_log(conn, run_id, status="completed", posts_scraped=saved)

    console.print(f"[green]Scraped {saved} posts ({dupes} duplicates skipped).[/green]")
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

    try:
        from noise_cancel.classifier.engine import ClassificationEngine

        engine = ClassificationEngine(cfg)
        results = engine.classify_posts(posts)
    except Exception as exc:
        console.print(f"[red]Classification failed: {exc}[/red]")
        update_run_log(conn, run_id, status="error", error_message=str(exc))
        raise typer.Exit(1) from None

    model_used = cfg.classifier.get("model", "unknown")

    for pc in results:
        cls = Classification(
            id=uuid.uuid4().hex,
            post_id=posts[pc.post_index].id,
            category=pc.category,
            confidence=pc.confidence,
            reasoning=pc.reasoning,
            summary=pc.summary,
            applied_rules=pc.applied_rules,
            model_used=model_used,
        )
        if dry_run:
            console.print(f"  [{cls.category}] {posts[pc.post_index].author_name}: {cls.reasoning}")
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
) -> None:
    """Deliver classified posts via configured delivery plugins."""
    import uuid

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


@app.command()
def run(
    config_path: str | None = typer.Option(None, "--config"),
    verbose: bool = typer.Option(False, "--verbose"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    limit: int | None = typer.Option(None, "--limit", help="Max posts per step"),
) -> None:
    """Run full pipeline: scrape -> classify -> deliver."""
    import uuid

    from noise_cancel.logger.repository import insert_run_log, update_run_log
    from noise_cancel.models import RunLog

    cfg = _get_config(config_path)
    conn = _get_db(cfg)

    run_id = uuid.uuid4().hex
    run_log = RunLog(id=run_id, run_type="pipeline")
    insert_run_log(conn, run_log)

    console.print("[cyan]Pipeline: scrape -> classify -> deliver[/cyan]")

    steps = [
        ("scrape", lambda: scrape(config_path=config_path, verbose=verbose, limit=limit)),
        ("classify", lambda: classify(config_path=config_path, dry_run=dry_run, limit=limit)),
    ]
    if not dry_run:
        steps.append(("deliver", lambda: deliver(config_path=config_path)))

    for step_name, step_fn in steps:
        try:
            step_fn()
        except (SystemExit, typer.Exit) as exc:
            if getattr(exc, "code", 1):
                update_run_log(conn, run_id, status="error", error_message=f"{step_name} failed")
                console.print(f"[red]Pipeline stopped at {step_name}.[/red]")
                raise typer.Exit(1) from None

    update_run_log(conn, run_id, status="completed")
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
