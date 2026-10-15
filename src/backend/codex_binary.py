"""Resolve the Codex CLI command on Windows and POSIX hosts."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def resolve_codex_command(binary: str = "codex") -> list[str]:
    """Return an executable prefix suitable for ``asyncio.create_subprocess_exec``."""
    resolved = shutil.which(binary) or (binary if Path(binary).is_file() else None)
    if resolved is None:
        raise FileNotFoundError("Codex CLI was not found. Install @openai/codex@0.162.1.")

    path = Path(resolved)
    if os.name == "nt":
        if path.suffix.lower() == ".ps1":
            command_shim = path.with_suffix(".cmd")
            if command_shim.is_file():
                path = command_shim
        if path.suffix.lower() in {".cmd", ".bat"}:
            script_candidates = (
                path.parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js",
                path.parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.mjs",
            )
            script = next((item for item in script_candidates if item.is_file()), None)
            node = shutil.which("node")
            if node is None:
                local_node = path.parent / "node.exe"
                node = str(local_node) if local_node.is_file() else None
            if script is not None and node is not None:
                return [node, str(script.resolve())]
            raise FileNotFoundError(
                "Could not resolve the Node.js Codex CLI package from its Windows npm shim."
            )

    return [str(path.resolve())]
