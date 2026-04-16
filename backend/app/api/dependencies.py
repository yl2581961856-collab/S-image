from functools import lru_cache

from fastapi import Request
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.services.job_service import JobService
from app.services.upload_service import UploadService


@lru_cache
def _build_redis_client() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)


@lru_cache
def _build_upload_service() -> UploadService:
    settings: Settings = get_settings()
    return UploadService(settings=settings)


@lru_cache
def _build_job_service() -> JobService:
    settings: Settings = get_settings()
    redis_client = _build_redis_client()
    upload_service = _build_upload_service()
    return JobService(redis_client=redis_client, settings=settings, upload_service=upload_service)


def get_redis_client(request: Request) -> Redis:
    state_client = getattr(request.app.state, "redis_client", None)
    if state_client is not None:
        return state_client
    return _build_redis_client()


def get_upload_service(request: Request) -> UploadService:
    state_service = getattr(request.app.state, "upload_service", None)
    if state_service is not None:
        return state_service
    return _build_upload_service()


def get_job_service(request: Request) -> JobService:
    state_service = getattr(request.app.state, "job_service", None)
    if state_service is not None:
        return state_service
    return _build_job_service()
