from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

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


@app.command()
def deliver(
    config_path: str | None = typer.Option(None, "--config"),
) -> None:
    """Deliver classified posts to Slack."""
    import json
    import uuid

    from noise_cancel.delivery.slack import deliver_posts
    from noise_cancel.logger.repository import (
        get_post_by_id,
        get_undelivered_classifications,
        insert_run_log,
        mark_delivered,
        update_run_log,
    )
    from noise_cancel.models import Classification, Post, RunLog

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

    delivered_count = deliver_posts(pairs, cfg)

    include_categories = cfg.delivery.get("slack", {}).get("include_categories", [])
    for _, cls in pairs:
        if cls.category in include_categories:
            mark_delivered(conn, cls.id)

    update_run_log(conn, run_id, status="completed", posts_delivered=delivered_count)
    console.print(f"[green]Delivered {delivered_count} posts to Slack.[/green]")


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
) -> None:
    """Show filtering logs."""
    console.print("[yellow]Logs command - not yet implemented[/yellow]")


@app.command()
def stats(
    config_path: str | None = typer.Option(None, "--config"),
) -> None:
    """Show classification accuracy and statistics."""
    console.print("[yellow]Stats command - not yet implemented[/yellow]")


@app.command(name="session-export")
def session_export(
    config_path: str | None = typer.Option(None, "--config"),
    output: str = typer.Option("session.json", "--output", "-o", help="Path to write exported session JSON"),
) -> None:
    """Export session to a portable JSON file (for transfer to remote server)."""
    import json

    from noise_cancel.scraper.auth import load_session

    cfg = _get_config(config_path)
    data_dir = Path(cfg.general["data_dir"])
    key_path = data_dir / "session.key"
    session_path = data_dir / "session.enc"

    if not session_path.exists() or not key_path.exists():
        console.print("[red]No session found. Run 'noise-cancel login' first.[/red]")
        raise typer.Exit(1)

    key = key_path.read_text().strip()
    session_data = load_session(key, str(session_path))
    if session_data is None:
        console.print("[red]Failed to decrypt session.[/red]")
        raise typer.Exit(1)

    out_path = Path(output)
    out_path.write_text(json.dumps(session_data))
    out_path.chmod(0o600)
    console.print(f"[green]Session exported to {out_path}[/green]")
    console.print("[yellow]Transfer this file to the server, then run:[/yellow]")
    console.print(f"  noise-cancel session-import {out_path.name}")
    console.print("[yellow]Delete the file after import![/yellow]")


@app.command(name="session-import")
def session_import(
    session_file: str = typer.Argument(..., help="Path to session JSON file from session-export"),
    config_path: str | None = typer.Option(None, "--config"),
) -> None:
    """Import session from a JSON file exported by session-export."""
    import json

    from noise_cancel.scraper.auth import generate_key, save_session

    cfg = _get_config(config_path)
    data_dir = Path(cfg.general["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    key_path = data_dir / "session.key"
    session_path = data_dir / "session.enc"

    in_path = Path(session_file)
    if not in_path.exists():
        console.print(f"[red]File not found: {in_path}[/red]")
        raise typer.Exit(1)

    try:
        session_data = json.loads(in_path.read_text())
    except Exception as exc:
        console.print(f"[red]Failed to read session file: {exc}[/red]")
        raise typer.Exit(1) from None

    if key_path.exists():
        key = key_path.read_text().strip()
    else:
        key = generate_key()
        key_path.write_text(key)
        key_path.chmod(0o600)

    save_session(session_data, key, str(session_path))
    session_path.chmod(0o600)
    console.print(f"[green]Session imported and saved to {session_path}[/green]")
    console.print("[yellow]Delete the source JSON file now:[/yellow]")
    console.print(f"  rm {in_path}")
