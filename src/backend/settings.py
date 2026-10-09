"""Backend settings. Env only; no secrets committed (see `.gitignore`)."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


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
