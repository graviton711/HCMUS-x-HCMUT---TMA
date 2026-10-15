"""CLI. `serve` only; schemas come from `/openapi.json`."""

import argparse


def main() -> None:
    from shared import ensure_utf8_stdout

    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description="Tour decision backend")
    parser.add_argument("command", choices=["serve"])
    parser.add_argument("--settings", default=None,
                        help="Path to settings.yaml (default: auto-resolve configs/settings.yaml)")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--reload", action="store_true",
                        help="Auto-restart on source changes (dev only).")
    args = parser.parse_args()
    if args.command == "serve":
        from pathlib import Path

        import uvicorn

        from backend.settings import Settings

        settings = Settings.load(args.settings)
        host = args.host or settings.tuning.api.host
        port = args.port or settings.tuning.api.port
        root = Path(__file__).resolve().parents[2]
        uvicorn.run("backend.api:create_app", factory=True, host=host, port=port,
                    workers=1, reload=args.reload,
                    reload_dirs=[str(root / "src" / name) for name in ("backend", "shared")]
                    + [str(root / "configs")] if args.reload else None)


if __name__ == "__main__":
    main()
