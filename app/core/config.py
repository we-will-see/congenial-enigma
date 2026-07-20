from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://indiair:password@localhost:5432/indiair"
    local_storage_path: Path = Path("./data/documents")
    max_upload_bytes: int = 50 * 1024 * 1024
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    embedding_model: str = "text-embedding-3-small"
    use_aws_textract: bool = False
    aws_region: str = "ap-south-1"
    bse_poll_interval_seconds: int = 86400
    bse_request_delay_seconds: float = 1.0
    max_retries: int = 3
    retry_backoff_seconds: int = 5
    min_chars_per_page: int = 200
    min_text_quality_score: float = 0.7
    restatement_threshold: float = 0.05
    financial_consistency_tolerance: float = 0.02
    log_level: str = "INFO"
    log_format: str = "json"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
