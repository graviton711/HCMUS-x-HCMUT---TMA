"""Resolve the configured OpenCode executable across common install layouts."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

_WINDOWS_EXE_IN_SHIM = re.compile(r'"([^"\r\n]+\.exe)"|([^\s"\']+\.exe)', re.IGNORECASE)


def _native_target_from_shim(shim: Path) -> Path | None:
    try:
        contents = shim.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    for match in _WINDOWS_EXE_IN_SHIM.finditer(contents):
        target = match.group(1) or match.group(2)
        if target is None:
            continue
        target = re.sub(
            r"%~?dp0%",
            lambda _: str(shim.parent),
            target,
            flags=re.IGNORECASE,
        )
        path = Path(target)
        if not path.is_absolute():
            path = shim.parent / path
        if path.is_file():
            return path
    return None


def resolve_opencode_binary(binary: str) -> str:
    """Return an executable path, following Windows npm shims to their target."""
    resolved = shutil.which(binary) or (binary if Path(binary).is_file() else None)
    if resolved is None:
        raise FileNotFoundError("OpenCode CLI was not found. Install it or set OPENCODE_BINARY.")

    path = Path(resolved)
    if os.name == "nt" and path.suffix.lower() not in {".exe", ".cmd", ".bat"}:
        command_shim = path.with_suffix(".cmd")
        if command_shim.is_file():
            path = command_shim

    if os.name == "nt" and path.suffix.lower() in {".cmd", ".bat"}:
        native = _native_target_from_shim(path)
        if native is None:
            candidates = (
                path.parent / "node_modules" / "@opencode" / "cli" / "bin" / "opencode.exe",
                path.parent / "node_modules" / "opencode-ai" / "bin" / "opencode.exe",
            )
            native = next((candidate for candidate in candidates if candidate.is_file()), None)
        if native is None:
            raise FileNotFoundError(
                "Could not resolve the native OpenCode executable from its Windows command shim. "
                "Set OPENCODE_BINARY to the path of opencode.exe."
            )
        path = native

    return str(path.resolve())
