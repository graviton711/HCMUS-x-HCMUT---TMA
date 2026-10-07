from shared.runtime import run_cli

from .pipeline import main

if __name__ == "__main__":
    raise SystemExit(run_cli(main))
