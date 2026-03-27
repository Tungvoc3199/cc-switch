from __future__ import annotations

from pathlib import Path

import typer

from tool.config import AppConfig, load_config
from tool.queue import JobQueue
from tool.runner import FlowRunner
from tool.storage import JobStorage

app = typer.Typer(help="Google Labs Flow UI Automation (BYOA, local-only)")


def _load(config_file: Path) -> tuple[AppConfig, JobStorage, JobQueue]:
    cfg = load_config(config_file)
    storage = JobStorage(cfg.database_path)
    queue = JobQueue(storage, retry_limit=cfg.retry_limit)
    return cfg, storage, queue


@app.command()
def init(config_file: Path = typer.Option(Path("assets/config.yaml"), "--config", "-c")) -> None:
    """Open Flow with persistent profile and verify login manually."""
    cfg, storage, queue = _load(config_file)
    try:
        runner = FlowRunner(cfg, queue)
        runner.run()
        runner.print_summary()
    finally:
        storage.close()


@app.command()
def enqueue(
    config_file: Path = typer.Option(Path("assets/config.yaml"), "--config", "-c"),
    prompts_file: Path | None = typer.Option(None, "--prompts", "-p"),
) -> None:
    """Load prompts.txt into SQLite queue as PENDING jobs."""
    cfg, storage, _queue = _load(config_file)
    try:
        source = prompts_file or cfg.prompts_file
        prompts = [line.strip() for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
        count = storage.enqueue_prompts(prompts)
        typer.echo(f"Enqueued {count} job(s) from {source}.")
    finally:
        storage.close()


@app.command()
def run(config_file: Path = typer.Option(Path("assets/config.yaml"), "--config", "-c")) -> None:
    """Run pending jobs; includes retry/resume logic."""
    cfg, storage, queue = _load(config_file)
    try:
        runner = FlowRunner(cfg, queue)
        runner.run()
        runner.print_summary()
    finally:
        storage.close()


@app.command()
def resume(config_file: Path = typer.Option(Path("assets/config.yaml"), "--config", "-c")) -> None:
    """Alias of run, intended after crash/kill."""
    run(config_file=config_file)


@app.command()
def status(config_file: Path = typer.Option(Path("assets/config.yaml"), "--config", "-c")) -> None:
    """Print current queue status."""
    _cfg, storage, queue = _load(config_file)
    try:
        stats = queue.stats()
        typer.echo(
            f"total={stats.total} done={stats.done} failed={stats.failed} paused={stats.paused}"
        )
        for job in storage.list_jobs():
            typer.echo(f"#{job.id} [{job.state}] retries={job.retries} prompt={job.prompt[:80]}")
    finally:
        storage.close()


if __name__ == "__main__":
    app()
