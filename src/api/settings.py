import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, StrictInt, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True,
        hide_input_in_errors=True,
    )

    nvidia_nim_api: SecretStr = SecretStr("")
    nvidia_nim_model: str = "nvidia/nemotron-3-super-120b-a12b"
    nim_reasoning: Literal["none", "low", "high"] = "none"
    nim_reasoning_budget: int = Field(default=1024, ge=128, le=8192)
    nim_max_tokens: int = Field(default=4096, ge=512, le=16384)
    nim_timeout_seconds: float = Field(default=90, ge=1, le=300)
    semantic_assessment_enabled: bool = True
    what_if_explanation_enabled: bool = True
    what_if_explanation_timeout_seconds: float = Field(default=15, ge=1, le=30)
    semantic_timeout_seconds: float = Field(default=45, ge=1, le=120)
    semantic_max_candidates: int = Field(default=12, ge=1, le=20)
    semantic_max_pairs: int = Field(default=24, ge=1, le=100)
    semantic_excerpt_chars: int = Field(default=6000, ge=500, le=10000)
    semantic_max_input_chars: int = Field(default=60000, ge=1000, le=120000)
    database_url: str = "sqlite:///data/backend.db"
    data_provider: Literal["fixture", "http", "supabase"] = "fixture"
    supabase_tour_db_url: SecretStr = SecretStr("")
    supabase_tour_url: str | None = None
    supabase_tour_publishable_key: SecretStr = SecretStr("")
    supabase_tour_connect_timeout_seconds: int = Field(default=8, ge=1, le=30)
    supabase_tour_query_timeout_seconds: int = Field(default=15, ge=1, le=60)
    supabase_tour_pool_size: int = Field(default=2, ge=1, le=5)
    supabase_tour_scan_limit: int = Field(default=1000, ge=1, le=5000)
    supabase_tour_max_offers: int = Field(default=1000, ge=1, le=1000)
    supabase_tour_trusted_domains: list[str] = Field(default_factory=list, max_length=100)
    supabase_tour_freshness_seconds: dict[str, StrictInt] = Field(default_factory=dict, max_length=4)
    crawler_url: str | None = None
    crawler_registry_path: Path | None = None
    crawler_api_key: SecretStr = SecretStr("")
    crawler_timeout_seconds: float = Field(default=60, ge=1, le=300)
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    proposal_ttl_minutes: int = Field(default=30, ge=1, le=1440)
    admin_viewer_token: SecretStr = SecretStr("")
    admin_operator_token: SecretStr = SecretStr("")
    admin_token: SecretStr = SecretStr("")
    contact_resolved_retention_days: int = Field(default=30, ge=1, le=365)
    job_timeout_seconds: int = Field(default=180, ge=1, le=600)
    worker_poll_seconds: float = Field(default=0.2, ge=0.01, le=10)
    session_ttl_hours: int = Field(default=24, ge=1, le=168)
    retention_days: int = Field(default=7, ge=1, le=365)
    max_pending_jobs: int = Field(default=10, ge=1, le=100)
    worker_enabled: bool = True

    @model_validator(mode="after")
    def deployment(self):
        if len(set(self.supabase_tour_trusted_domains)) != len(self.supabase_tour_trusted_domains) or any(
            not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", d)
            for d in self.supabase_tour_trusted_domains
        ):
            raise ValueError("Trusted domains must be unique exact lowercase hostnames")
        if set(self.supabase_tour_freshness_seconds) - {
            "price",
            "departure_date",
            "return_date",
            "availability",
        } or any(
            type(seconds) is not int or seconds <= 0
            for seconds in self.supabase_tour_freshness_seconds.values()
        ):
            raise ValueError("Catalog freshness requires supported volatile fields and positive seconds")
        tokens = [
            t.get_secret_value()
            for t in (self.admin_token, self.admin_operator_token, self.admin_viewer_token)
            if t.get_secret_value()
        ]
        if len(set(tokens)) != len(tokens) or any(len(t) < 32 for t in tokens):
            raise ValueError("Admin tokens must be distinct secrets of at least 32 characters")
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("v1 runtime supports local SQLite only")
        if "*" in self.cors_origins:
            raise ValueError("Explicit CORS origins required")
        if self.data_provider == "supabase":
            try:
                u = urlsplit(self.supabase_tour_db_url.get_secret_value())
                valid = u.scheme in {"postgres", "postgresql", "postgresql+psycopg"} and u.hostname and u.path
                _ = u.port
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("Supabase provider requires a valid PostgreSQL tour database URL")
        if self.crawler_url:
            u = urlsplit(self.crawler_url)
            if u.scheme not in {"https", "http"} or not u.hostname or u.username or u.password:
                raise ValueError("Crawler URL must be server-configured http(s) endpoint")
        return self
