# Context Map (S-image)

- Status: Active
- Last Reviewed: 2026-04-15
- Purpose: Provide one stable navigation map for humans and agents, based on files that actually exist in this repository.

## 1. Read Order (Cold Start)

1. `需求文档.txt`
2. `# Project Context & Tech Stack Selection.md`
3. `docs/adr/ADR-0001-mvp-workflow-state-machine-language.md`
4. `docs/adr/ADR-0002-hybrid-inference-stack-2026.md`
5. `backend/README.md`
6. `frontend/README.md`
7. `docs/harness/context-harness-spec.md`
8. `docs/ops/gateway-security-runbook.md`
9. `docs/ops/backend-docker-runbook.md`
10. `docs/ops/acr-personal-runbook.md`
11. `docs/ops/frontend-artifact-release.md`
12. `docs/ops/codeup-closed-loop-runbook.md`

## 2. Single Source of Truth (SoT)

| Domain | SoT File | Notes |
| --- | --- | --- |
| Product scope and boundaries | `需求文档.txt` | Current iteration is image-generation only. |
| Architecture direction | `# Project Context & Tech Stack Selection.md` | High-level stack and layering principles. |
| State-machine and language decision | `docs/adr/ADR-0001-mvp-workflow-state-machine-language.md` | MVP stays Python-first; Rust is metric-triggered. |
| Backend API contract | `backend/openapi/v1.yaml` | External contract for frontend and integration. |
| Backend runtime and routes | `backend/README.md` | Runbook, routes, env switches, callback signature format. |
| Frontend integration behavior | `frontend/README.md` | Upload -> create job -> polling -> result display. |
| Context/harness strategy | `docs/harness/context-harness-spec.md` | Reproducibility, replay, and quality gate strategy. |
| Deferred phase-2 features | `docs/todo/TODO-phase2-agent-workflow.md` | Explicitly out of current scope. |

## 3. Task Routing (What To Read First)

### 3.1 API contract or request/response model changes
- Start: `backend/openapi/v1.yaml`
- Then: `backend/app/schemas/*.py`
- Then: `backend/app/api/v1/*.py`

### 3.2 Job lifecycle, retry, idempotency, callback transitions
- Start: `backend/app/services/state_machine.py`
- Then: `backend/app/services/job_service.py`
- Then: `docs/adr/ADR-0001-mvp-workflow-state-machine-language.md`

### 3.3 Upload, file storage, output URL mirroring
- Start: `backend/app/api/v1/uploads.py`
- Then: `backend/app/services/upload_service.py`
- Then: `backend/app/core/config.py`

### 3.4 Callback security or replay protection
- Start: `backend/app/api/v1/callbacks.py`
- Then: `backend/app/services/job_service.py`
- Then: `backend/app/core/config.py`
- Reference: `docs/ops/alicloud-nginx-security-checklist.md`

### 3.5 Frontend-backend alignment
- Start: `frontend/src/types/api.ts`
- Then: `frontend/src/lib/apiClient.ts`
- Then: `frontend/src/App.tsx` and `frontend/src/components/*.tsx`
- Contract check: `backend/openapi/v1.yaml`

### 3.6 Deployment and operations tuning
- Runtime profile: `docs/ops/mvp-single-node-4090.md`
- Docker backend profile: `docs/ops/backend-docker-runbook.md`
- ACR profile: `docs/ops/acr-personal-runbook.md`
- Security hardening: `docs/ops/alicloud-nginx-security-checklist.md`

## 4. Active Documents Inventory

| Path | Type | Status |
| --- | --- | --- |
| `需求文档.txt` | Product requirement | active |
| `# Project Context & Tech Stack Selection.md` | Architecture context | active |
| `docs/adr/ADR-0001-mvp-workflow-state-machine-language.md` | ADR | proposed/active in MVP |
| `docs/adr/ADR-0002-hybrid-inference-stack-2026.md` | ADR | proposed |
| `docs/harness/context-harness-spec.md` | Harness spec | active |
| `docs/ops/mvp-single-node-4090.md` | Ops profile | active |
| `docs/ops/gateway-security-runbook.md` | Gateway/security runbook | active |
| `docs/ops/backend-docker-runbook.md` | Backend docker runbook | active |
| `docs/ops/acr-personal-runbook.md` | ACR runbook | active |
| `docs/ops/frontend-artifact-release.md` | Frontend artifact release | active |
| `docs/ops/codeup-closed-loop-runbook.md` | Codeup closed-loop release | active |
| `docs/ops/alicloud-nginx-security-checklist.md` | Security checklist | active |
| `docs/todo/TODO-phase2-agent-workflow.md` | Deferred backlog | deferred |
| `backend/openapi/v1.yaml` | API contract | active |
| `backend/README.md` | Backend runbook | active |
| `frontend/README.md` | Frontend runbook | active |

## 5. Planned Docs (Not Yet Created)

The following paths are referenced by your target documentation structure but are currently missing:

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/DESIGN.md`
- `docs/FRONTEND.md`
- `docs/PLANS.md`
- `docs/PRODUCT_SENSE.md`
- `docs/QUALITY_SCORE.md`
- `docs/RELIABILITY.md`
- `docs/SECURITY.md`

Recommendation:

1. Add them incrementally as thin files.
2. Link each file back to this context map.
3. Keep one SoT per domain to avoid conflict between markdown files.

## 6. Context Loading Rules (For Agents)

1. Always read only the files needed by the current task route.
2. Treat `需求文档.txt` + `backend/openapi/v1.yaml` as hard contract constraints.
3. Treat `docs/todo/TODO-phase2-agent-workflow.md` as out-of-scope guardrail for current MVP.
4. Do not expand scope to phase-2 features unless explicitly requested.
5. For deployment/security tasks, use files under `deploy/` as implementation baseline.