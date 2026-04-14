# Project Context & Tech Stack Selection (Image Workflow)

## 1. Project Overview
**Project Name:** E-commerce Image Generation Hub (女装电商生图中台)
**Core Objective:**
1. `Visual Pipeline`: Automated AI model image generation replacing physical shoots while preserving clothing details.

**Current Scope (Strict):**
- Only image generation workflow is in scope.

**Architectural Principle:**
- High performance, cost efficiency, and strict separation of concerns (CPU Gateway vs. GPU Inference).

---

## 2. Technology Stack Definition

### 2.1 Frontend (User Interface)
- **Framework:** Next.js 14 (App Router) + React 18
- **Language:** TypeScript (Strict mode)
- **Styling:** Tailwind CSS + Shadcn UI
- **State Management:** Zustand
- **Data Fetching:** SWR or React Query
- **Engineering Note:** Focus on job submission, status tracking, and result preview pages.

### 2.2 Backend (API Gateway & Dispatcher)
- **Framework:** FastAPI (Python 3.10+)
- **Server:** Uvicorn
- **Data Validation:** Pydantic V2
- **Async Task Queue:** ARQ (preferred) or Celery + Redis
- **Cache & State:** Redis (idempotency, job status cache, rate limiting)
- **Engineering Note:** Use `async/await` for all I/O. All endpoints must declare Pydantic request/response models.

### 2.3 AI Inference Engine (Vision - Serverless GPU)
- **Engine:** ComfyUI (Headless API)
- **Base Models:** SD 1.5 (majicMIX realistic) or SDXL
- **Control Mechanisms:** ControlNet (Canny/Depth), IP-Adapter, ADetailer
- **Integration Method:** Backend sends workflow JSON to ComfyUI API and handles callback/polling.
- **Engineering Note:** Do not load PyTorch models inside FastAPI. All generation logic is externalized via HTTP/WS to ComfyUI.

### 2.4 Storage & External Integration
- **Object Storage:** S3-compatible storage (MinIO/OSS/S3) for generated assets
- **ERP (Optional in this phase):** Jushuitan Open API (read-only) only if SKU/order metadata is needed for generation context
- **Engineering Note:** Keep external integrations optional and isolated from core generation path.

---

## 3. Directory Structure (Expected)
```text
.
├── frontend/              # Next.js frontend
├── backend/               # FastAPI backend
│   ├── api/               # Router endpoints (e.g., /jobs, /callbacks)
│   ├── core/              # Config, security, connections
│   ├── services/          # Business logic (ComfyUI client, job service, storage client)
│   └── worker/            # ARQ/Celery tasks
├── comfyui_workflows/     # Exported ComfyUI workflow JSON
├── docs/adr/              # Architecture decision records
└── docker-compose.yml     # Redis + API + worker infrastructure
```

## 4. Coding Rules & Constraints
- **Type Safety:** Always use Python type hints and TypeScript interfaces.
- **Error Handling:** Use custom FastAPI exceptions. Handle external API timeout/retry explicitly.
- **Frontend:** Use Toast for API failures and clear job-state indicators.
- **API Evolution:** Keep `/v1` versioning, additive fields only, and backward-compatible contracts.
- **Security:** Never hardcode keys/tokens/URLs. Use `.env` + `pydantic-settings`.
- **Stateless API:** Backend stays stateless. Persist job/session state in Redis with TTL.
- **Concurrency:** Add rate-limiting for ComfyUI load tests to avoid GPU OOM.
