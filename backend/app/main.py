from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.api.dependencies import get_redis_client
from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import DomainError, domain_error_handler
from app.services.job_service import JobService
from app.services.upload_service import UploadService

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    upload_service = UploadService(settings=settings)
    job_service = JobService(redis_client=redis_client, settings=settings, upload_service=upload_service)

    app.state.redis_client = redis_client
    app.state.upload_service = upload_service
    app.state.job_service = job_service

    try:
        yield
    finally:
        await redis_client.aclose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_exception_handler(DomainError, domain_error_handler)
app.include_router(api_router)

upload_root = Path(settings.upload_root_dir).resolve()
upload_root.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_root)), name="uploads")


@app.get("/healthz", tags=["system"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["system"])
async def readyz(redis_client: Redis = Depends(get_redis_client)) -> dict[str, str]:
    try:
        await redis_client.ping()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="redis unavailable") from exc
    return {"status": "ready"}
