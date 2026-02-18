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
) -> None:
    """Scrape LinkedIn feed posts."""
    console.print("[yellow]Scrape command - not yet implemented[/yellow]")


@app.command()
def classify(
    config_path: str | None = typer.Option(None, "--config"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Classify unclassified posts using AI."""
    console.print("[yellow]Classify command - not yet implemented[/yellow]")


@app.command()
def deliver(
    config_path: str | None = typer.Option(None, "--config"),
) -> None:
    """Deliver classified posts to Slack."""
    console.print("[yellow]Deliver command - not yet implemented[/yellow]")


@app.command()
def run(
    config_path: str | None = typer.Option(None, "--config"),
    verbose: bool = typer.Option(False, "--verbose"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Run full pipeline: scrape -> classify -> deliver."""
    console.print("[yellow]Run command - not yet implemented[/yellow]")


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


@app.command()
def feedback(
    post_id: str = typer.Argument(..., help="Post ID"),
    feedback_type: str = typer.Argument(..., help="useful/not_useful/mute_similar"),
    config_path: str | None = typer.Option(None, "--config"),
) -> None:
    """Submit feedback for a classified post."""
    console.print("[yellow]Feedback command - not yet implemented[/yellow]")
