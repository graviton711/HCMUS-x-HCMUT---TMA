"""Backend settings. Every tunable comes from YAML or env; code holds no values.

Precedence: explicit constructor args > env vars > YAML file.
Missing YAML keys fail loud with ValidationError. Only credentials may be
empty (absent key = feature off, guarded at use time).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class PromptCfg(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    system: str
    max_tokens: int
    temperature: float
    timeout_s: float


class InputCfg(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    money_units: dict[str, int]
    budget_words: list[str]
    departure_markers: list[str]
    required_slots: list[str]
    window_before: int
    window_budget: int
    quote_chars: int


class DecideCfg(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    soft_fields: list[str]
    excerpt_chars: int
    quote_chars: int
    risk_words: list[str]
    analysis_chars: int
    analysis_items: int
    top_n: int


class DataCfg(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    providers_limit: int
    connect_timeout_s: int


class ApiCfg(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    host: str
    port: int
    candidate_min: int
    candidate_max: int
    session_ttl_seconds: int


class Tuning(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    extract: PromptCfg
    assess: PromptCfg
    input: InputCfg
    decide: DecideCfg
    data: DataCfg
    api: ApiCfg


def _resolve(path: str | Path | None, *parts: str) -> Path | None:
    base = None
    if path is not None:
        p = Path(path)
        base = p.parent if p.suffix == ".yaml" else p
    candidates = ([base.joinpath(*parts)] if base is not None else []) + [
        Path(__file__).resolve().parents[2] / "configs" / Path(*parts),
        Path.cwd() / "configs" / Path(*parts),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _read_settings(path: str | Path | None) -> dict[str, Any]:
    import yaml

    resolved = _resolve(path, "settings.yaml")
    if resolved is None:
        return {}
    data = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Settings must be a mapping: {resolved}")
    backend = data.get("backend", {})
    return backend if isinstance(backend, dict) else {}


def _read_prompt(path: str | Path | None, name: str) -> dict[str, Any]:
    import yaml

    resolved = _resolve(path, "prompts", f"{name}.yaml")
    if resolved is None:
        return {}
    data = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Prompt must be a mapping: {resolved}")
    return {"system": data.get("system"),
            "max_tokens": data.get("max_tokens"),
            "temperature": data.get("temperature"),
            "timeout_s": data.get("timeout_s")}


# YAML key -> flat Settings field. Env var of the same name wins over YAML.
_FLAT_MAP = {
    "database_url": "database_url",
    "data_provider": "data_provider",
    ("data", "trusted_domains"): "supabase_tour_trusted_domains",
    ("data", "freshness_seconds"): "supabase_tour_freshness_seconds",
    ("api", "candidate_default"): "candidate_limit",
    ("data", "scan_limit"): "supabase_scan_limit",
    ("nim", "model"): "nvidia_nim_model",
    ("nim", "timeout_s"): "nim_timeout_seconds",
    ("nim", "connect_timeout_s"): "nim_connect_timeout_s",
    "cors_origins": "cors_origins",
    "cors_origin_regex": "cors_origin_regex",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    database_url: str
    data_provider: str
    candidate_limit: int

    supabase_tour_db_url: str = ""
    supabase_scan_limit: int
    supabase_tour_trusted_domains: list[str] = Field(default_factory=list)
    supabase_tour_freshness_seconds: dict[str, int] = Field(
        default_factory=lambda: {"departure_date": 86400, "price": 86400}
    )

    nvidia_nim_api: SecretStr = SecretStr("")
    nvidia_nim_model: str
    nim_timeout_seconds: float
    nim_connect_timeout_s: float
    cors_origins: list[str] = Field(default_factory=list)
    cors_origin_regex: str = ""

    tuning: Tuning

    @classmethod
    def load(cls, path: str | Path | None = None, **overrides: Any) -> Settings:
        """Build settings from configs, letting env and kwargs win.

        `path` is a settings file or a configs dir. Prompts load from
        `prompts/<name>.yaml` beside it.
        """
        backend = _read_settings(path)
        from dotenv import dotenv_values

        try:
            dot_values = {
                key.lower(): value
                for key, value in dotenv_values(overrides.get("_env_file", ".env")).items()
                if value is not None
            }
        except Exception:
            dot_values = {}
        process_values = {key.lower(): value for key, value in os.environ.items()}
        env = set(process_values) | set(dot_values)
        if "supabase_tour_db_url" in overrides:
            supabase_tour_db_url = overrides["supabase_tour_db_url"]
        elif "supabase_tour_db_url" in process_values:
            supabase_tour_db_url = process_values["supabase_tour_db_url"]
        else:
            supabase_tour_db_url = dot_values.get("supabase_tour_db_url")
        tuning: dict[str, Any] = {
            name: {k: v for k, v in _read_prompt(path, name).items() if v is not None}
            for name in ("extract", "assess")
        }
        tuning.update({k: v for k, v in backend.items()
                       if k in Tuning.model_fields and v is not None})
        init: dict[str, Any] = {"tuning": tuning}
        for key, field in _FLAT_MAP.items():
            if isinstance(key, tuple):
                section, sub = key
                section_data = backend.get(section)
                value = section_data.get(sub) if isinstance(section_data, dict) else None
            else:
                value = backend.get(key)
            if value is not None and field.lower() not in env and field not in overrides:
                init[field] = value
        if supabase_tour_db_url:
            if "database_url" not in overrides:
                init["database_url"] = supabase_tour_db_url
            if "data_provider" not in overrides and "data_provider" not in env:
                init["data_provider"] = "supabase"
        init.update(overrides)
        return cls(**init)
