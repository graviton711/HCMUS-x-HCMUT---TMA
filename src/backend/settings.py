"""Backend settings. Tunables live in `configs/settings.yaml`; secrets live in env.

Precedence: explicit constructor args > env vars > YAML file > code fallbacks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class PromptCfg(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    system: str = ""
    max_tokens: int = 1024
    temperature: float = 0


class ExtractPromptCfg(PromptCfg):
    system: str = (
        "Trích yêu cầu tour tiếng Việt thành JSON"
        " {hard: [{field, operator, value}], soft: [{text}], travelers: int}."
        " Hard fields: destination, departure_city, date_from, date_to,"
        " budget_max, duration_days, transport, accommodation."
        " budget_max là số nguyên VND. date ISO YYYY-MM-DD."
        " Chỉ dùng thông tin trong câu, không đoán. Thiếu thì bỏ qua."
    )


class AssessPromptCfg(PromptCfg):
    system: str = (
        "Chấm từng tour theo từng tiêu chí mềm."
        " Trả JSON {scores: [{tour_id, condition_id, score 0..1, quote}]}."
        " quote là trích nguyên văn ngắn từ văn bản tour."
        " Không suy đoán ngoài văn bản."
    )
    max_tokens: int = 2048


class InputCfg(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    money_units: dict[str, int] = {"tỷ": 1_000_000_000, "tỉ": 1_000_000_000,
                                   "ty": 1_000_000_000, "ti": 1_000_000_000,
                                   "triệu": 1_000_000, "tr": 1_000_000, "trieu": 1_000_000,
                                   "nghìn": 1_000, "k": 1_000, "nghin": 1_000}
    window_before: int = 16
    window_budget: int = 40
    quote_chars: int = 200


class DecideCfg(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    soft_fields: list[str] = ["itinerary", "inclusions", "exclusions",
                              "child_policy", "cancellation_policy"]
    excerpt_chars: int = 6000
    quote_chars: int = 300
    risk_words: list[str] = ["không hoàn", "thu phí 100%", "sold_out", "unknown"]
    analysis_chars: int = 160
    analysis_items: int = 6
    top_n: int = 3


class DataCfg(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    providers_limit: int = 100
    connect_timeout_s: int = 8


class ApiCfg(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000
    candidate_min: int = 1
    candidate_max: int = 100


class Tuning(BaseModel):
    model_config = SettingsConfigDict(extra="ignore")

    extract: ExtractPromptCfg = ExtractPromptCfg()
    assess: AssessPromptCfg = AssessPromptCfg()
    input: InputCfg = InputCfg()
    decide: DecideCfg = DecideCfg()
    data: DataCfg = DataCfg()
    api: ApiCfg = ApiCfg()


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
            "temperature": data.get("temperature")}


# YAML key -> flat Settings field. Env var of the same name wins over YAML.
_FLAT_MAP = {
    ("api", "candidate_default"): "candidate_limit",
    ("data", "scan_limit"): "supabase_scan_limit",
    ("nim", "model"): "nvidia_nim_model",
    ("nim", "timeout_s"): "nim_timeout_seconds",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    database_url: str = "sqlite:///data/backend.db"
    data_provider: str = "fixture"
    candidate_limit: int = 20

    supabase_tour_db_url: str = ""
    supabase_scan_limit: int = 1000

    nvidia_nim_api: SecretStr = SecretStr("")
    nvidia_nim_model: str = "nvidia/nemotron-3-super-120b-a12b"
    nim_timeout_seconds: float = 45.0

    tuning: Tuning = Tuning()

    @classmethod
    def load(cls, path: str | Path | None = None, **overrides: Any) -> Settings:
        """Build settings from configs, letting env and kwargs win.

        `path` is a settings file or a configs dir. Prompts load from
        `prompts/<name>.yaml` beside it; missing files fall back to code.
        """
        backend = _read_settings(path)
        env = {k.lower() for k in os.environ}
        tuning: dict[str, Any] = {
            name: {k: v for k, v in _read_prompt(path, name).items() if v is not None}
            for name in ("extract", "assess")
        }
        tuning.update({k: v for k, v in backend.items()
                       if k in Tuning.model_fields and v is not None})
        init: dict[str, Any] = {"tuning": tuning}
        for (section, key), field in _FLAT_MAP.items():
            section_data = backend.get(section)
            value = section_data.get(key) if isinstance(section_data, dict) else None
            if value is not None and field.lower() not in env and field not in overrides:
                init[field] = value
        init.update(overrides)
        return cls(**init)
