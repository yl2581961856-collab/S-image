from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status

from app.api.dependencies import get_job_service
from app.schemas.common import ErrorResponse
from app.schemas.jobs import JobCancelResponse, JobCreateRequest, JobCreateResponse, JobStatusResponse
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def create_job(
    payload: JobCreateRequest,
    service: JobService = Depends(get_job_service),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> JobCreateResponse:
    return await service.create_job(payload=payload, idempotency_key=idempotency_key)


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def get_job(job_id: UUID, service: JobService = Depends(get_job_service)) -> JobStatusResponse:
    return await service.get_job(job_id)


@router.post(
    "/{job_id}/cancel",
    response_model=JobCancelResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
async def cancel_job(job_id: UUID, service: JobService = Depends(get_job_service)) -> JobCancelResponse:
    return await service.cancel_job(job_id)
