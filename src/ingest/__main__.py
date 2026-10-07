from shared.runtime import run_cli

from .cli import main

if __name__ == "__main__":
    raise SystemExit(run_cli(main))
