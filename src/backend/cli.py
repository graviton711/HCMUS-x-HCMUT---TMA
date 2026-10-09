"""CLI. `serve` only; schemas come from `/openapi.json`."""

import argparse


def main() -> None:
    import sys

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Tour decision backend")
    parser.add_argument("command", choices=["serve"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("backend.api:create_app", factory=True, host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
