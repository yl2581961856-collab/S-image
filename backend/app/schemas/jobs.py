from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    postprocessing = "postprocessing"
    succeeded = "succeeded"
    failed = "failed"
    timeout = "timeout"
    cancelled = "cancelled"


TERMINAL_STATUSES: set[JobStatus] = {
    JobStatus.succeeded,
    JobStatus.failed,
    JobStatus.timeout,
    JobStatus.cancelled,
}


class JobCreateRequest(BaseModel):
    workflow_type: str = Field(..., min_length=1, max_length=64, examples=["model_photo_generation"])
    workflow_version: str = Field(..., min_length=1, max_length=32, examples=["v1"])
    workflow_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque workflow inputs. The schema is controlled by workflow_type/workflow_version.",
    )
    priority: int = Field(default=5, ge=1, le=10)
    callback_url: HttpUrl | None = Field(default=None)
    client_reference: str | None = Field(default=None, max_length=128)


class JobCreateResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    created_at: datetime
    idempotency_key: str | None = None


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    workflow_type: str
    workflow_version: str
    created_at: datetime
    updated_at: datetime
    output_urls: list[str] = Field(default_factory=list)
    error_message: str | None = None


class JobCancelResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    cancelled_at: datetime
