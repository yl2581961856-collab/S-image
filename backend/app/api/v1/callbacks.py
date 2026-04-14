from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from app.api.dependencies import get_job_service
from app.schemas.callbacks import ComfyUICallbackAck, ComfyUICallbackRequest
from app.schemas.common import ErrorResponse
from app.services.job_service import JobService

router = APIRouter(prefix="/callbacks", tags=["callbacks"])


@router.post(
    "/comfyui",
    response_model=ComfyUICallbackAck,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def comfyui_callback(
    payload: ComfyUICallbackRequest,
    request: Request,
    service: JobService = Depends(get_job_service),
    signature: Annotated[str | None, Header(alias="X-ComfyUI-Signature")] = None,
    timestamp: Annotated[str | None, Header(alias="X-ComfyUI-Timestamp")] = None,
    nonce: Annotated[str | None, Header(alias="X-ComfyUI-Nonce")] = None,
) -> ComfyUICallbackAck:
    raw_body = await request.body()
    return await service.handle_comfyui_callback(
        payload=payload,
        raw_body=raw_body,
        signature=signature,
        timestamp=timestamp,
        nonce=nonce,
    )
