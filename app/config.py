from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "online-deanery"
    database_path: Path = Path("./artifacts/audit.sqlite3")
    policy_path: Path = Path("./data/policies/admission_policy.md")
    ocr_languages: str = "rus+eng"
    max_upload_bytes: int = 12_000_000
    max_question_chars: int = 2_000
    top_k_policy_chunks: int = 4
    log_level: str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
