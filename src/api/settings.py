from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    nvidia_nim_api: SecretStr = SecretStr("")
    nvidia_nim_model: str = "nvidia/nemotron-3-super-120b-a12b"
    nim_reasoning: Literal["none", "low", "high"] = "none"
    nim_reasoning_budget: int = Field(default=1024, ge=128, le=8192)
    nim_max_tokens: int = Field(default=4096, ge=512, le=16384)
    nim_timeout_seconds: float = Field(default=90, ge=1, le=300)
    database_url: str = "sqlite:///data/backend.db"
    data_provider: Literal["fixture", "http"] = "fixture"
    crawler_url: str | None = None
    crawler_registry_path: Path | None = None
    crawler_api_key: SecretStr = SecretStr("")
    crawler_timeout_seconds: float = Field(default=60, ge=1, le=300)
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    job_timeout_seconds: int = Field(default=180, ge=1, le=600)
    worker_poll_seconds: float = Field(default=0.2, ge=0.01, le=10)
    session_ttl_hours: int = Field(default=24, ge=1, le=168)
    retention_days: int = Field(default=7, ge=1, le=365)
    max_pending_jobs: int = Field(default=10, ge=1, le=100)
    worker_enabled: bool = True

    @model_validator(mode="after")
    def deployment(self):
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("v1 runtime supports local SQLite only")
        if "*" in self.cors_origins:
            raise ValueError("Explicit CORS origins required")
        if self.crawler_url:
            u = urlsplit(self.crawler_url)
            if u.scheme not in {"https", "http"} or not u.hostname or u.username or u.password:
                raise ValueError("Crawler URL must be server-configured http(s) endpoint")
        return self
