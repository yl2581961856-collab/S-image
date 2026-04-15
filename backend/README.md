# Backend Skeleton

## Run locally

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

MVP production-like start (single-node profile):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

## Run with Docker (recommended on gateway)

```bash
cd /data/S-image
cp -n backend/.env.example backend/.env
docker compose -f deploy/docker/docker-compose.gateway.yml up -d --build
curl http://127.0.0.1:9000/healthz
```

## API docs

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Static contract file: `backend/openapi/v1.yaml`

## Current routes

- `POST /v1/uploads/images`
- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `POST /v1/jobs/{job_id}/cancel`
- `POST /v1/callbacks/comfyui`
- `GET /healthz`

## Runtime behavior

- Job state is persisted in Redis.
- Idempotency is indexed in Redis via `Idempotency-Key`.
- Callback requests support signature verification + replay protection when `CALLBACKS_SECRET` is configured.
- Callback event de-dup is enabled when `provider_request_id` is present.
- Job responses include `progress` in `0-100` scale.
- Uploaded images are served under `/uploads/*`.
- Generated output URLs from callback are mirrored to local storage (`/uploads/generated/*`) by default.

## Upload flow (real file)

1. Upload source file with `multipart/form-data` to `POST /v1/uploads/images`.
2. Use the returned `image_url` inside `workflow_params` when creating job via `POST /v1/jobs`.
3. After callback completes, query `GET /v1/jobs/{job_id}` and read mirrored `output_urls`.

Note:

- Drag-and-drop upload in frontend still sends `FormData` under the hood (same backend API).
- Allowed MIME types are controlled by `UPLOAD_ALLOWED_MIME_TYPES`.
- Upload max size is controlled by `UPLOAD_IMAGE_MAX_BYTES` (default `500 MiB`).

## Callback signature format

Signed message:

```text
timestamp + "." + nonce + "." + raw_body
```

Headers:

- `X-ComfyUI-Signature: sha256=<hex_digest>`
- `X-ComfyUI-Timestamp: <unix_seconds>`
- `X-ComfyUI-Nonce: <random_nonce>`

Callback payload note:

- `event=progress` expects `progress` in `0-1` scale.
- API response converts and exposes progress in `0-100` scale.

## Useful environment variables

- `REDIS_URL`
- `REDIS_KEY_PREFIX`
- `JOB_TTL_SECONDS`
- `IDEMPOTENCY_TTL_SECONDS`
- `CALLBACKS_SECRET`
- `CALLBACK_CLOCK_SKEW_SECONDS`
- `CALLBACK_NONCE_TTL_SECONDS`
- `CALLBACK_EVENT_DEDUP_TTL_SECONDS`
- `UPLOAD_ROOT_DIR`
- `UPLOAD_IMAGE_SUBDIR`
- `GENERATED_IMAGE_SUBDIR`
- `UPLOAD_IMAGE_MAX_BYTES`
- `GENERATED_IMAGE_MAX_BYTES`
- `GENERATED_IMAGE_FETCH_TIMEOUT_SECONDS`
- `UPLOAD_ALLOWED_MIME_TYPES`
- `MIRROR_GENERATED_OUTPUTS`
- `PUBLIC_BASE_URL`

## Profiles

- Example env template: `backend/.env.example`
- Single-node 4090 tuning guide: `docs/ops/mvp-single-node-4090.md`
- Alibaba Cloud security checklist: `docs/ops/alicloud-nginx-security-checklist.md`
- Gateway security runbook: `docs/ops/gateway-security-runbook.md`
- Backend docker runbook: `docs/ops/backend-docker-runbook.md`
- Deployment templates: `deploy/README.md`
