from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.dependencies import get_upload_service
from app.schemas.common import ErrorResponse
from app.schemas.uploads import UploadImageResponse
from app.services.upload_service import UploadService

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "/images",
    response_model=UploadImageResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {"model": ErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def upload_image(
    file: UploadFile = File(..., description="Image file to upload."),
    service: UploadService = Depends(get_upload_service),
) -> UploadImageResponse:
    return await service.save_image(upload_file=file)
