# Frontend (React + TypeScript)

## Stack

- React 18 + TypeScript
- Vite 5
- react-dropzone (drag & drop upload)

## Local run

```bash
cd frontend
npm install
npm run dev
```

Default dev URL: `http://localhost:5173`

## Env

Copy `.env.example` to `.env` if needed:

```bash
cp .env.example .env
```

- `VITE_API_BASE_URL=/api` by default.
- Vite dev server proxies:
  - `/api/* -> http://localhost:8000/*`
  - `/uploads/* -> http://localhost:8000/uploads/*`

## Implemented flow

1. Drag/drop or click upload source image.
2. Frontend calls `POST /v1/uploads/images` with `FormData`.
3. Frontend submits `POST /v1/jobs` using returned `image_url` in `workflow_params`.
4. Frontend polls `GET /v1/jobs/{job_id}` every 2s.
5. Progress bar updates from backend `progress` (`0-100`).
6. On success, show first item in `output_urls`.
7. Supports `POST /v1/jobs/{job_id}/cancel`.

## API contract alignment

- Uses backend `job_id` naming.
- Uses backend status enum:
  - `queued | running | postprocessing | succeeded | failed | timeout | cancelled`
- Uses backend upload route:
  - `POST /v1/uploads/images`
