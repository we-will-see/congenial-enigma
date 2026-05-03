import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:  # Allows lightweight parser tests before requirements are installed.
    BaseSettings = object  # type: ignore[assignment,misc]
    SettingsConfigDict = None  # type: ignore[assignment]


@dataclass
class _FallbackSettings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://indiair:password@localhost:5432/indiair")
    es_host: str = os.getenv("ES_HOST", "http://localhost:9200")
    es_index_name: str = os.getenv("ES_INDEX_NAME", "india_ir_content")
    s3_bucket: str | None = os.getenv("S3_BUCKET", "indiair-raw-pdfs")
    local_storage_path: Path = Path(os.getenv("LOCAL_STORAGE_PATH", "./data/raw_pdfs"))
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    use_aws_textract: bool = os.getenv("USE_AWS_TEXTRACT", "false").lower() == "true"
    aws_access_key_id: str | None = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region: str = os.getenv("AWS_REGION", "ap-south-1")
    bse_poll_interval_seconds: int = int(os.getenv("BSE_POLL_INTERVAL_SECONDS", "86400"))
    bse_request_delay_seconds: float = float(os.getenv("BSE_REQUEST_DELAY_SECONDS", "1.0"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    retry_backoff_seconds: int = int(os.getenv("RETRY_BACKOFF_SECONDS", "5"))
    min_chars_per_page: int = int(os.getenv("MIN_CHARS_PER_PAGE", "200"))
    min_text_quality_score: float = float(os.getenv("MIN_TEXT_QUALITY_SCORE", "0.7"))
    restatement_threshold: float = float(os.getenv("RESTATEMENT_THRESHOLD", "0.05"))
    financial_consistency_tolerance: float = float(os.getenv("FINANCIAL_CONSISTENCY_TOLERANCE", "0.02"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = os.getenv("LOG_FORMAT", "json")
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")


class Settings(BaseSettings):  # type: ignore[misc,valid-type]
    database_url: str = "postgresql://indiair:password@localhost:5432/indiair"
    es_host: str = "http://localhost:9200"
    es_index_name: str = "india_ir_content"
    s3_bucket: str | None = "indiair-raw-pdfs"
    local_storage_path: Path = Path("./data/raw_pdfs")
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    use_aws_textract: bool = False
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
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
    api_base_url: str = "http://localhost:8000"

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings | _FallbackSettings:
    if SettingsConfigDict is None:
        return _FallbackSettings()
    return Settings()
