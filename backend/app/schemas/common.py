from enum import Enum

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    not_found = "not_found"
    invalid_state_transition = "invalid_state_transition"
    invalid_callback = "invalid_callback"
    validation_error = "validation_error"
    conflict = "conflict"
    unauthorized = "unauthorized"
    unsupported_media_type = "unsupported_media_type"
    payload_too_large = "payload_too_large"
    internal_error = "internal_error"


class ErrorObject(BaseModel):
    code: ErrorCode
    message: str = Field(..., examples=["Requested job was not found."])
    request_id: str | None = Field(default=None, examples=["req_123456"])


class ErrorResponse(BaseModel):
    error: ErrorObject
