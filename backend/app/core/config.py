from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Image Generation Workflow API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/v1"

    redis_url: str = "redis://localhost:6379/0"
    redis_key_prefix: str = "imgwf"
    job_ttl_seconds: int = 7 * 24 * 60 * 60
    idempotency_ttl_seconds: int = 24 * 60 * 60

    callbacks_secret: str | None = None
    callback_clock_skew_seconds: int = 5 * 60
    callback_nonce_ttl_seconds: int = 10 * 60
    callback_event_dedup_ttl_seconds: int = 24 * 60 * 60

    upload_root_dir: str = "storage"
    upload_image_subdir: str = "images"
    generated_image_subdir: str = "generated"
    upload_image_max_bytes: int = 500 * 1024 * 1024
    generated_image_max_bytes: int = 20 * 1024 * 1024
    generated_image_fetch_timeout_seconds: int = 20
    upload_allowed_mime_types: str = "image/jpeg,image/png,image/webp"
    mirror_generated_outputs: bool = True
    public_base_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def upload_allowed_mime_type_set(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.upload_allowed_mime_types.split(",")
            if item.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
