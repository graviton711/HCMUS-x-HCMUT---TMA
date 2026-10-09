"""CLI. `serve` only; schemas come from `/openapi.json`."""

import argparse


def main() -> None:
    import sys

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Tour decision backend")
    parser.add_argument("command", choices=["serve"])
    parser.add_argument("--settings", default=None,
                        help="Path to settings.yaml (default: auto-resolve configs/settings.yaml)")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        from backend.settings import Settings

        settings = Settings.load(args.settings)
        host = args.host or settings.tuning.api.host
        port = args.port or settings.tuning.api.port
        uvicorn.run("backend.api:create_app", factory=True, host=host, port=port, workers=1)


if __name__ == "__main__":
    main()
