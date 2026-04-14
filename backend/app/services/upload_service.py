from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx
from fastapi import UploadFile, status

from app.core.config import Settings
from app.core.errors import DomainError
from app.schemas.common import ErrorCode
from app.schemas.uploads import UploadImageResponse

CHUNK_SIZE = 1024 * 1024


class UploadService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._root_dir = Path(settings.upload_root_dir).resolve()
        self._image_dir = self._root_dir / settings.upload_image_subdir
        self._generated_dir = self._root_dir / settings.generated_image_subdir
        self._image_dir.mkdir(parents=True, exist_ok=True)
        self._generated_dir.mkdir(parents=True, exist_ok=True)

    async def save_image(self, upload_file: UploadFile) -> UploadImageResponse:
        content_type = (upload_file.content_type or "").lower().strip()
        if content_type not in self._settings.upload_allowed_mime_type_set:
            raise DomainError(
                code=ErrorCode.unsupported_media_type,
                message=f"unsupported content_type={content_type!r}",
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )

        upload_id = uuid4()
        extension = self._resolve_extension(content_type=content_type, original_name=upload_file.filename)
        file_name = f"{upload_id.hex}{extension}"
        destination = self._image_dir / file_name

        size_bytes = 0
        try:
            with destination.open("wb") as out:
                while True:
                    chunk = await upload_file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > self._settings.upload_image_max_bytes:
                        raise DomainError(
                            code=ErrorCode.payload_too_large,
                            message=f"file exceeds max size={self._settings.upload_image_max_bytes} bytes",
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        )
                    out.write(chunk)
        except Exception:
            if destination.exists():
                destination.unlink(missing_ok=True)
            raise
        finally:
            await upload_file.close()

        created_at = datetime.now(timezone.utc)
        return UploadImageResponse(
            upload_id=upload_id,
            file_name=file_name,
            content_type=content_type,
            size_bytes=size_bytes,
            image_url=self._build_public_url(subdir=self._settings.upload_image_subdir, file_name=file_name),
            created_at=created_at,
        )

    async def mirror_generated_images(self, source_urls: list[str]) -> list[str]:
        if not source_urls:
            return []

        timeout = httpx.Timeout(self._settings.generated_image_fetch_timeout_seconds)
        mirrored: list[str] = []
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for source_url in source_urls:
                mirrored_url = await self._mirror_single_image(client=client, source_url=source_url)
                mirrored.append(mirrored_url)
        return mirrored

    async def _mirror_single_image(self, client: httpx.AsyncClient, source_url: str) -> str:
        file_id = uuid4()
        parsed_url = urlparse(source_url)
        if parsed_url.scheme not in {"http", "https"}:
            raise DomainError(
                code=ErrorCode.invalid_callback,
                message=f"generated output url must be http(s), got={source_url!r}",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        original_name = Path(parsed_url.path).name if parsed_url.path else None

        try:
            async with client.stream("GET", source_url) as response:
                if response.status_code >= 400:
                    raise DomainError(
                        code=ErrorCode.invalid_callback,
                        message=f"failed to fetch generated image, status={response.status_code}",
                        status_code=status.HTTP_502_BAD_GATEWAY,
                    )

                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if content_type and not content_type.startswith("image/"):
                    raise DomainError(
                        code=ErrorCode.invalid_callback,
                        message=f"generated asset is not an image, content_type={content_type!r}",
                        status_code=status.HTTP_502_BAD_GATEWAY,
                    )

                extension = self._resolve_extension(content_type=content_type, original_name=original_name)
                file_name = f"{file_id.hex}{extension}"
                destination = self._generated_dir / file_name
                size_bytes = 0
                try:
                    with destination.open("wb") as out:
                        async for chunk in response.aiter_bytes(CHUNK_SIZE):
                            size_bytes += len(chunk)
                            if size_bytes > self._settings.generated_image_max_bytes:
                                raise DomainError(
                                    code=ErrorCode.payload_too_large,
                                    message=(
                                        "generated image exceeds max size="
                                        f"{self._settings.generated_image_max_bytes} bytes"
                                    ),
                                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                )
                            out.write(chunk)
                except Exception:
                    if destination.exists():
                        destination.unlink(missing_ok=True)
                    raise
        except httpx.HTTPError as exc:
            raise DomainError(
                code=ErrorCode.invalid_callback,
                message=f"failed to fetch generated image, error={exc.__class__.__name__}",
                status_code=status.HTTP_502_BAD_GATEWAY,
            ) from exc

        return self._build_public_url(subdir=self._settings.generated_image_subdir, file_name=file_name)

    def _resolve_extension(self, content_type: str, original_name: str | None) -> str:
        mapping = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/jpg": ".jpg",
        }
        if content_type in mapping:
            return mapping[content_type]

        if original_name:
            suffix = Path(original_name).suffix.lower()
            if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
                return ".jpg" if suffix == ".jpeg" else suffix
        return ".bin"

    def _build_public_url(self, subdir: str, file_name: str) -> str:
        relative_path = f"/uploads/{subdir}/{file_name}"
        if self._settings.public_base_url:
            return self._settings.public_base_url.rstrip("/") + relative_path
        return relative_path
