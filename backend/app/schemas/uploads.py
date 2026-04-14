from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class UploadImageResponse(BaseModel):
    upload_id: UUID
    file_name: str = Field(..., examples=["7f2e9b4ea0bc4b0d8dd4f3f17a5e6ab1.png"])
    content_type: str = Field(..., examples=["image/png"])
    size_bytes: int = Field(..., ge=1)
    image_url: HttpUrl | str
    created_at: datetime
