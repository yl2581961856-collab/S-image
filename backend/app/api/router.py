from fastapi import APIRouter

from app.api.v1.callbacks import router as callbacks_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.uploads import router as uploads_router

api_router = APIRouter()
api_router.include_router(jobs_router, prefix="/v1")
api_router.include_router(callbacks_router, prefix="/v1")
api_router.include_router(uploads_router, prefix="/v1")
