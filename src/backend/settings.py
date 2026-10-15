"""Backend settings. Runtime values come from YAML or env; code holds no secrets.

Precedence: explicit constructor args > env vars > YAML file. Local chat and survey
models have separate settings: Codex for chat, OpenCode for survey. Render retains
OpenCode chat until the Codex rollout is eligible.
Missing YAML keys fail loud with ValidationError. Only credentials may be
empty (absent key = feature off, guarded at use time).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class DecideCfg(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    quote_chars: int
    risk_words: list[str]
    analysis_chars: int
    analysis_items: int
    top_n: int
    near_miss_max_fails: int = 2


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

    decide: DecideCfg
    data: DataCfg
    api: ApiCfg


class OpenCodeConfig(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    model: str = Field(min_length=1)

    @field_validator("model")
    @classmethod
    def _strip_model(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("OpenCode model must not be empty.")
        return value


class CodexConfig(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    model: str = "gpt-6-luna"
    reasoning_effort: Literal["low", "medium", "high", "xhigh"] = "medium"

    @field_validator("model")
    @classmethod
    def _strip_model(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Codex model must not be empty.")
        return value


def _string_list(value: Any) -> list[str]:
    """Env/dashboard operators hand-edit these; accept JSON or bare CSV."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except ValueError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        return [part.strip() for part in text.split(",") if part.strip()]
    return [str(value)]


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


def _read_config(path: str | Path | None) -> dict[str, Any]:
    import yaml

    resolved = _resolve(path, "settings.yaml")
    if resolved is None:
        return {}
    data = yaml.safe_load(resolved.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Settings must be a mapping: {resolved}")
    return data


# YAML key -> flat Settings field. Env var of the same name wins over YAML.
_FLAT_MAP = {
    "database_url": "database_url",
    "data_provider": "data_provider",
    ("data", "freshness_seconds"): "supabase_tour_freshness_seconds",
    ("api", "candidate_default"): "candidate_limit",
    ("data", "scan_limit"): "supabase_scan_limit",
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
    supabase_tour_freshness_seconds: dict[str, int | None] = Field(
        default_factory=lambda: {"departure_date": None}
    )

    opencode: OpenCodeConfig
    codex: CodexConfig = Field(default_factory=CodexConfig)
    agent_provider: Literal["codex", "opencode"] = "codex"
    codex_server_url: str = "http://127.0.0.1:4099"
    codex_binary: str = "codex"
    opencode_server_url: str = ""
    opencode_server_password: str = ""
    opencode_binary: str = "opencode"
    opencode_agent: str = "travel-consultant"
    # OpenCode CLI working directory / shared project path. Empty uses repo root.
    opencode_project_dir: str = ""
    agent_max_message_chars: int = 8000
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    cors_origin_regex: str = ""

    tuning: Tuning

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_string_list(cls, value: Any) -> list[str]:
        return _string_list(value)

    @field_validator("supabase_tour_freshness_seconds", mode="before")
    @classmethod
    def _departure_freshness_only(cls, value: Any) -> dict[str, int | None]:
        if not isinstance(value, dict):
            return {}
        if "departure_date" not in value:
            return {}
        departure_ttl = value["departure_date"]
        if departure_ttl is None:
            return {"departure_date": None}
        if isinstance(departure_ttl, int) and not isinstance(departure_ttl, bool):
            return {"departure_date": departure_ttl}
        return {}

    @field_validator("database_url", "supabase_tour_db_url", mode="before")
    @classmethod
    def _strip_url(cls, value: Any) -> Any:
        # Dashboard paste often leaves trailing newlines in secret URLs.
        return value.strip() if isinstance(value, str) else value

    @classmethod
    def load(cls, path: str | Path | None = None, **overrides: Any) -> Settings:
        """Build settings from configs, letting env and kwargs win."""
        config = _read_config(path)
        backend = config.get("backend", {})
        backend = backend if isinstance(backend, dict) else {}
        opencode = config.get("opencode", {})
        opencode = opencode if isinstance(opencode, dict) else {}
        codex = config.get("codex", {})
        codex = codex if isinstance(codex, dict) else {}
        from dotenv import dotenv_values

        # Resolve the dotenv file from the repo root so every entry point
        # (repo root, src/frontend, deploy boxes) reads the same `.env`.
        # An explicit `_env_file` (tests) always wins.
        repo_env = str(Path(__file__).resolve().parents[2] / ".env")
        env_file = overrides.get("_env_file", repo_env)
        try:
            dot_values = {
                key.lower(): value
                for key, value in dotenv_values(env_file).items()
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
        tuning: dict[str, Any] = {}
        tuning.update({k: v for k, v in backend.items()
                       if k in Tuning.model_fields and v is not None})
        init: dict[str, Any] = {
            "tuning": tuning,
            "opencode": opencode,
            "codex": codex,
            "_env_file": env_file,
        }
        if "codex_model" in env or "codex_reasoning_effort" in env:
            codex = dict(codex)
            if "codex_model" in env:
                codex["model"] = process_values.get("codex_model", dot_values.get("codex_model"))
            if "codex_reasoning_effort" in env:
                codex["reasoning_effort"] = process_values.get(
                    "codex_reasoning_effort", dot_values.get("codex_reasoning_effort")
                )
            init["codex"] = codex
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
