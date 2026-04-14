import hashlib
import hmac
import json
import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID, uuid4

from fastapi import status
from redis.asyncio import Redis
from redis.exceptions import WatchError

from app.core.config import Settings
from app.core.errors import DomainError
from app.schemas.callbacks import ComfyUICallbackAck, ComfyUICallbackRequest, ComfyUIEvent
from app.schemas.common import ErrorCode
from app.schemas.jobs import (
    JobCancelResponse,
    JobCreateRequest,
    JobCreateResponse,
    JobStatus,
    JobStatusResponse,
    TERMINAL_STATUSES,
)
from app.services.state_machine import can_transition
from app.services.upload_service import UploadService


@dataclass
class JobRecord:
    job_id: UUID
    status: JobStatus
    progress: float
    workflow_type: str
    workflow_version: str
    workflow_params: dict
    created_at: datetime
    updated_at: datetime
    output_urls: list[str] = field(default_factory=list)
    error_message: str | None = None


class JobService:
    def __init__(self, redis_client: Redis, settings: Settings, upload_service: UploadService) -> None:
        self._redis = redis_client
        self._settings = settings
        self._upload_service = upload_service
        self._key_prefix = settings.redis_key_prefix

    async def create_job(self, payload: JobCreateRequest, idempotency_key: str | None) -> JobCreateResponse:
        fingerprint = self._build_payload_fingerprint(payload)

        while True:
            pipe = self._redis.pipeline(transaction=True)
            try:
                idem_key = self._idem_key(idempotency_key) if idempotency_key else None
                if idem_key:
                    await pipe.watch(idem_key)
                    existing_raw = await pipe.get(idem_key)
                    if existing_raw:
                        return await self._build_idempotent_response(existing_raw, fingerprint, idempotency_key)

                now = self._utcnow()
                job = JobRecord(
                    job_id=uuid4(),
                    status=JobStatus.queued,
                    progress=0.0,
                    workflow_type=payload.workflow_type,
                    workflow_version=payload.workflow_version,
                    workflow_params=payload.workflow_params,
                    created_at=now,
                    updated_at=now,
                )

                pipe.multi()
                pipe.set(
                    self._job_key(job.job_id),
                    self._serialize_job(job),
                    ex=self._settings.job_ttl_seconds,
                )
                if idem_key:
                    idem_payload = json.dumps(
                        {
                            "job_id": str(job.job_id),
                            "fingerprint": fingerprint,
                        },
                        ensure_ascii=True,
                        sort_keys=True,
                    )
                    pipe.set(
                        idem_key,
                        idem_payload,
                        ex=self._settings.idempotency_ttl_seconds,
                        nx=True,
                    )

                exec_result = await pipe.execute()
                if idem_key and exec_result[-1] is None:
                    continue

                return JobCreateResponse(
                    job_id=job.job_id,
                    status=job.status,
                    progress=job.progress,
                    created_at=job.created_at,
                    idempotency_key=idempotency_key,
                )
            except WatchError:
                continue
            finally:
                await pipe.reset()

    async def get_job(self, job_id: UUID) -> JobStatusResponse:
        job = await self._get_job_or_raise(job_id)
        return self._to_status_response(job)

    async def cancel_job(self, job_id: UUID) -> JobCancelResponse:
        now = self._utcnow()

        def mutate(job: JobRecord) -> JobRecord:
            if job.status in TERMINAL_STATUSES:
                raise DomainError(
                    code=ErrorCode.invalid_state_transition,
                    message=f"cannot cancel job from terminal status={job.status.value}",
                    status_code=status.HTTP_409_CONFLICT,
                )
            if not can_transition(job.status, JobStatus.cancelled):
                raise DomainError(
                    code=ErrorCode.invalid_state_transition,
                    message=f"invalid transition: {job.status.value} -> cancelled",
                    status_code=status.HTTP_409_CONFLICT,
                )

            job.status = JobStatus.cancelled
            job.progress = min(max(job.progress, 0.0), 100.0)
            job.updated_at = now
            return job

        updated = await self._update_job_atomic(job_id=job_id, mutator=mutate)
        return JobCancelResponse(job_id=updated.job_id, status=updated.status, cancelled_at=updated.updated_at)

    async def handle_comfyui_callback(
        self,
        payload: ComfyUICallbackRequest,
        raw_body: bytes,
        signature: str | None = None,
        timestamp: str | None = None,
        nonce: str | None = None,
    ) -> ComfyUICallbackAck:
        await self._verify_callback_request(
            raw_body=raw_body,
            signature=signature,
            timestamp=timestamp,
            nonce=nonce,
        )

        if payload.provider_request_id:
            if not await self._register_callback_event(payload):
                existing = await self._get_job_or_raise(payload.job_id)
                return ComfyUICallbackAck(job_id=existing.job_id, status=existing.status)

        mirrored_output_urls: list[str] | None = None
        if payload.output_urls:
            mirrored_output_urls = await self._resolve_callback_output_urls(
                source_urls=[str(url) for url in payload.output_urls]
            )

        now = self._utcnow()

        def mutate(job: JobRecord) -> JobRecord:
            target = self._target_status(payload.event)
            if job.status in TERMINAL_STATUSES:
                return job
            if target == job.status:
                return job
            if not can_transition(job.status, target):
                raise DomainError(
                    code=ErrorCode.invalid_state_transition,
                    message=f"invalid transition: {job.status.value} -> {target.value}",
                    status_code=status.HTTP_409_CONFLICT,
                )

            job.status = target
            job.updated_at = now
            job.progress = self._compute_next_progress(job.progress, payload.event, payload.progress)
            if mirrored_output_urls is not None:
                job.output_urls = mirrored_output_urls
            if payload.error_message:
                job.error_message = payload.error_message
            return job

        updated = await self._update_job_atomic(job_id=payload.job_id, mutator=mutate)
        return ComfyUICallbackAck(job_id=updated.job_id, status=updated.status)

    async def _build_idempotent_response(
        self,
        idem_raw: str,
        expected_fingerprint: str,
        idempotency_key: str,
    ) -> JobCreateResponse:
        idem_data = json.loads(idem_raw)
        existing_fingerprint = str(idem_data.get("fingerprint", ""))
        if existing_fingerprint != expected_fingerprint:
            raise DomainError(
                code=ErrorCode.conflict,
                message="idempotency key was reused with a different request payload",
                status_code=status.HTTP_409_CONFLICT,
            )

        existing_job_id = UUID(str(idem_data["job_id"]))
        job = await self._get_job_or_raise(existing_job_id)
        return JobCreateResponse(
            job_id=job.job_id,
            status=job.status,
            progress=job.progress,
            created_at=job.created_at,
            idempotency_key=idempotency_key,
        )

    async def _update_job_atomic(self, job_id: UUID, mutator: Callable[[JobRecord], JobRecord]) -> JobRecord:
        job_key = self._job_key(job_id)

        while True:
            pipe = self._redis.pipeline(transaction=True)
            try:
                await pipe.watch(job_key)
                raw_job = await pipe.get(job_key)
                if not raw_job:
                    raise DomainError(
                        code=ErrorCode.not_found,
                        message=f"job_id={job_id} was not found",
                        status_code=status.HTTP_404_NOT_FOUND,
                    )

                current = self._deserialize_job(raw_job)
                updated = mutator(current)

                pipe.multi()
                pipe.set(job_key, self._serialize_job(updated), ex=self._settings.job_ttl_seconds)
                await pipe.execute()
                return updated
            except WatchError:
                continue
            finally:
                await pipe.reset()

    async def _get_job_or_raise(self, job_id: UUID) -> JobRecord:
        raw = await self._redis.get(self._job_key(job_id))
        if not raw:
            raise DomainError(
                code=ErrorCode.not_found,
                message=f"job_id={job_id} was not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return self._deserialize_job(raw)

    async def _register_callback_event(self, payload: ComfyUICallbackRequest) -> bool:
        dedup_key = self._callback_dedup_key(
            provider_request_id=payload.provider_request_id,
            event=payload.event.value,
            job_id=payload.job_id,
        )
        result = await self._redis.set(
            dedup_key,
            "1",
            nx=True,
            ex=self._settings.callback_event_dedup_ttl_seconds,
        )
        return bool(result)

    async def _verify_callback_request(
        self,
        raw_body: bytes,
        signature: str | None,
        timestamp: str | None,
        nonce: str | None,
    ) -> None:
        if not self._settings.callbacks_secret:
            return

        if not signature or not timestamp or not nonce:
            raise DomainError(
                code=ErrorCode.unauthorized,
                message="missing callback signature headers",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            ts = int(timestamp)
        except ValueError as exc:
            raise DomainError(
                code=ErrorCode.unauthorized,
                message="invalid callback timestamp",
                status_code=status.HTTP_401_UNAUTHORIZED,
            ) from exc

        now = int(time.time())
        if abs(now - ts) > self._settings.callback_clock_skew_seconds:
            raise DomainError(
                code=ErrorCode.unauthorized,
                message="callback timestamp outside allowed window",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        provided = signature.strip()
        if provided.startswith("sha256="):
            provided = provided[len("sha256=") :]

        signed_message = timestamp.encode("utf-8") + b"." + nonce.encode("utf-8") + b"." + raw_body
        expected = hmac.new(
            self._settings.callbacks_secret.encode("utf-8"),
            signed_message,
            hashlib.sha256,
        ).hexdigest()

        if not secrets.compare_digest(expected, provided):
            raise DomainError(
                code=ErrorCode.unauthorized,
                message="invalid callback signature",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        nonce_key = self._callback_nonce_key(nonce)
        nonce_saved = await self._redis.set(
            nonce_key,
            str(ts),
            nx=True,
            ex=self._settings.callback_nonce_ttl_seconds,
        )
        if not nonce_saved:
            raise DomainError(
                code=ErrorCode.unauthorized,
                message="replayed callback request",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

    def _target_status(self, event: ComfyUIEvent) -> JobStatus:
        mapping = {
            ComfyUIEvent.accepted: JobStatus.running,
            ComfyUIEvent.progress: JobStatus.running,
            ComfyUIEvent.completed: JobStatus.postprocessing,
            ComfyUIEvent.postprocess_completed: JobStatus.succeeded,
            ComfyUIEvent.failed: JobStatus.failed,
        }
        return mapping[event]

    def _serialize_job(self, job: JobRecord) -> str:
        payload = asdict(job)
        payload["job_id"] = str(job.job_id)
        payload["status"] = job.status.value
        payload["created_at"] = job.created_at.isoformat()
        payload["updated_at"] = job.updated_at.isoformat()
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)

    def _deserialize_job(self, raw: str) -> JobRecord:
        payload = json.loads(raw)
        return JobRecord(
            job_id=UUID(str(payload["job_id"])),
            status=JobStatus(str(payload["status"])),
            progress=float(payload.get("progress", 0.0)),
            workflow_type=str(payload["workflow_type"]),
            workflow_version=str(payload["workflow_version"]),
            workflow_params=dict(payload.get("workflow_params", {})),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            updated_at=datetime.fromisoformat(str(payload["updated_at"])),
            output_urls=list(payload.get("output_urls", [])),
            error_message=payload.get("error_message"),
        )

    def _build_payload_fingerprint(self, payload: JobCreateRequest) -> str:
        canonical_payload = json.dumps(
            payload.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
        )
        return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

    def _to_status_response(self, job: JobRecord) -> JobStatusResponse:
        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            progress=job.progress,
            workflow_type=job.workflow_type,
            workflow_version=job.workflow_version,
            created_at=job.created_at,
            updated_at=job.updated_at,
            output_urls=job.output_urls,
            error_message=job.error_message,
        )

    def _job_key(self, job_id: UUID) -> str:
        return f"{self._key_prefix}:job:{job_id}"

    def _idem_key(self, idempotency_key: str) -> str:
        return f"{self._key_prefix}:idem:{idempotency_key}"

    def _callback_nonce_key(self, nonce: str) -> str:
        return f"{self._key_prefix}:cb_nonce:{nonce}"

    def _callback_dedup_key(self, provider_request_id: str, event: str, job_id: UUID) -> str:
        return f"{self._key_prefix}:cb_event:{provider_request_id}:{event}:{job_id}"

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    async def _resolve_callback_output_urls(self, source_urls: list[str]) -> list[str]:
        if not self._settings.mirror_generated_outputs:
            return source_urls
        return await self._upload_service.mirror_generated_images(source_urls=source_urls)

    def _compute_next_progress(
        self,
        current_progress: float,
        event: ComfyUIEvent,
        callback_progress: float | None,
    ) -> float:
        if event == ComfyUIEvent.accepted:
            return max(current_progress, 1.0)
        if event == ComfyUIEvent.progress:
            normalized = (callback_progress or 0.0) * 100.0
            return min(89.0, max(current_progress, normalized))
        if event == ComfyUIEvent.completed:
            return max(current_progress, 90.0)
        if event == ComfyUIEvent.postprocess_completed:
            return 100.0
        return current_progress
