from fastapi import Request
from fastapi.responses import JSONResponse

from app.schemas.common import ErrorCode, ErrorObject, ErrorResponse


class DomainError(Exception):
    def __init__(self, *, code: ErrorCode, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def build_error_response(request: Request, code: ErrorCode, message: str) -> dict:
    request_id = request.headers.get("X-Request-Id")
    payload = ErrorResponse(error=ErrorObject(code=code, message=message, request_id=request_id))
    return payload.model_dump(mode="json")


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(request=request, code=exc.code, message=exc.message),
    )
