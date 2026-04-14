from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.jobs import JobStatus


class ComfyUIEvent(str, Enum):
    accepted = "accepted"
    progress = "progress"
    completed = "completed"
    postprocess_completed = "postprocess_completed"
    failed = "failed"


class ComfyUICallbackRequest(BaseModel):
    job_id: UUID
    event: ComfyUIEvent
    provider_request_id: str | None = Field(default=None, max_length=128)
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    output_urls: list[str] = Field(default_factory=list)
    error_message: str | None = Field(default=None, max_length=2000)
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_by_event(self) -> "ComfyUICallbackRequest":
        if self.event == ComfyUIEvent.progress and self.progress is None:
            raise ValueError("progress is required when event=progress")
        if self.event == ComfyUIEvent.completed and not self.output_urls:
            raise ValueError("output_urls is required when event=completed")
        if self.event == ComfyUIEvent.failed and not self.error_message:
            raise ValueError("error_message is required when event=failed")
        return self


class ComfyUICallbackAck(BaseModel):
    job_id: UUID
    accepted: bool = True
    status: JobStatus
