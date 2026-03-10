from __future__ import annotations

import argparse
from pathlib import Path

from tool.config import load_config
from tool.doctor import print_doctor_report, run_doctor

try:
    import typer
except ModuleNotFoundError:  # pragma: no cover - fallback for offline bootstrap env
    typer = None


if typer is not None:
    app = typer.Typer(help="Google Labs Flow local automation tool (BYOA)")


def _read_prompts(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if typer is not None:

    @app.command()
    def init(config: Path = typer.Option(Path("assets/config.example.yaml"), "--config", "-c")) -> None:
        from tool.runner import Runner

        cfg = load_config(config)
        runner = Runner(cfg)
        runner.init()
        typer.echo("Initialized storage/log directories.")


    @app.command()
    def enqueue(config: Path = typer.Option(Path("assets/config.example.yaml"), "--config", "-c")) -> None:
        from tool.runner import Runner

        cfg = load_config(config)
        prompts = _read_prompts(cfg.prompts_file)
        runner = Runner(cfg)
        added = runner.enqueue_prompts(prompts)
        typer.echo(f"Enqueued {added} jobs from {cfg.prompts_file}")


    @app.command()
    def resume(config: Path = typer.Option(Path("assets/config.example.yaml"), "--config", "-c")) -> None:
        from tool.runner import Runner

        cfg = load_config(config)
        runner = Runner(cfg)
        count = runner.resume()
        typer.echo(f"Resumed {count} paused job(s).")


    @app.command("run")
    def run_cmd(config: Path = typer.Option(Path("assets/config.example.yaml"), "--config", "-c")) -> None:
        from tool.runner import Runner

        cfg = load_config(config)
        if cfg.headless:
            typer.echo("[Warning] headless=true có thể bị anti-bot chặn. Khuyến nghị headless=false.")
        runner = Runner(cfg)
        runner.run()


    @app.command()
    def doctor(config: Path = typer.Option(Path("assets/config.example.yaml"), "--config", "-c")) -> None:
        ok, checks = run_doctor(config)
        print_doctor_report(ok, checks)
        raise typer.Exit(code=0 if ok else 1)


def _fallback_cli() -> None:
    parser = argparse.ArgumentParser(description="Google Labs Flow local automation tool (BYOA)")
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ("init", "enqueue", "resume", "run", "doctor"):
        c = sub.add_parser(cmd)
        c.add_argument("-c", "--config", default="assets/config.example.yaml")
    args = parser.parse_args()

    from tool.runner import Runner

    cfg = load_config(Path(args.config))
    runner = Runner(cfg)
    if args.command == "init":
        runner.init()
        print("Initialized storage/log directories.")
    elif args.command == "enqueue":
        prompts = _read_prompts(cfg.prompts_file)
        added = runner.enqueue_prompts(prompts)
        print(f"Enqueued {added} jobs from {cfg.prompts_file}")
    elif args.command == "resume":
        count = runner.resume()
        print(f"Resumed {count} paused job(s).")
    elif args.command == "run":
        if cfg.headless:
            print("[Warning] headless=true có thể bị anti-bot chặn. Khuyến nghị headless=false.")
        runner.run()
    elif args.command == "doctor":
        ok, checks = run_doctor(Path(args.config))
        print_doctor_report(ok, checks)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    if typer is not None:
        app()
    else:
        _fallback_cli()
