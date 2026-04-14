from functools import lru_cache

from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.services.job_service import JobService
from app.services.upload_service import UploadService


@lru_cache
def get_redis_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)


@lru_cache
def get_job_service() -> JobService:
    settings: Settings = get_settings()
    redis_client = get_redis_client()
    upload_service = get_upload_service()
    return JobService(redis_client=redis_client, settings=settings, upload_service=upload_service)


@lru_cache
def get_upload_service() -> UploadService:
    settings: Settings = get_settings()
    return UploadService(settings=settings)
