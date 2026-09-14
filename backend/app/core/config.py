from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.detection.config import DetectionConfig


class Settings(BaseSettings):
    app_name: str = "HAWKEYE V2"
    app_version: str = "2.0.0"
    environment: str = "development"
    debug: bool = True

    database_url: str = Field(
        default="postgresql+psycopg://hawkeye:hawkeye@localhost:5432/hawkeye"
    )

    api_prefix: str = "/api/v1"

    log_level: str = "INFO"

    max_upload_size_bytes: int = Field(default=500_000_000, gt=0)

    media_root: str = Field(default="media")

    storage_provider: str = Field(default="local")  # 'local' or 'supabase'
    supabase_url: str | None = None
    supabase_service_role_key: str | None = Field(default=None, alias="supabase_secret_key")
    supabase_storage_bucket: str = "hawkeye-media"

    @model_validator(mode='after')
    def validate_supabase_config(self):
        if self.storage_provider == 'supabase':
            if not self.supabase_url or not self.supabase_service_role_key:
                raise ValueError("supabase_url and supabase_service_role_key (or SUPABASE_SECRET_KEY) must be set when storage_provider is 'supabase'")
        return self
        
    yolo_model_name: str = "yolo11n.pt"

    yolo_confidence_threshold: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
    )

    @field_validator('yolo_model_name')
    @classmethod
    def validate_yolo_model_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("yolo_model_name must not be empty")
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def get_detection_config() -> DetectionConfig:
    s = get_settings()
    return DetectionConfig(
        model_name=s.yolo_model_name,
        confidence_threshold=s.yolo_confidence_threshold,
    )
