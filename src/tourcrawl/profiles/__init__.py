"""Profile + settings loading. Engine never branches on source names."""

from __future__ import annotations

import os
from pathlib import Path
from types import ModuleType

DEFAULT_SETTINGS = Path("configs/settings.yaml")
DEFAULT_PROFILES = Path("configs/profiles")


def _resolve(path: Path) -> Path:
    """Find configs in a checkout or an installed deployment.

    Order: explicit path > TOURCRAWL_CONFIGS env > package-relative configs/
    (repo checkout) > current-directory configs/. Deployment ships configs/
    alongside the code (see profiles README); it is data, not code.
    """
    candidates = [path]
    if env_root := os.getenv("TOURCRAWL_CONFIGS"):
        candidates.append(Path(env_root) / path.name)
    candidates.append(Path(__file__).resolve().parents[3] / path)
    candidates.append(Path.cwd() / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _yaml() -> ModuleType:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("This package requires PyYAML (see pyproject dependencies).") from exc
    return yaml


def load_settings(path: str | Path | None = None) -> dict:
    yaml = _yaml()
    target = _resolve(Path(path) if path is not None else DEFAULT_SETTINGS)
    with target.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Settings must be a mapping: {target}")
    return data


def load_profile(name: str, profiles_dir: str | Path | None = None) -> dict:
    yaml = _yaml()
    if profiles_dir is not None:
        target = Path(profiles_dir) / f"{name}.yaml"
    else:
        target = _resolve(DEFAULT_PROFILES / f"{name}.yaml")
    if not target.exists():
        raise ValueError(f"Unknown profile: {name} ({target} not found)")
    with target.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict) or not data.get("origin") or not data.get("flows"):
        raise ValueError(f"Profile needs origin + flows: {target}")
    data["name"] = name
    return data
