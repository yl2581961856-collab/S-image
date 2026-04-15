# S-image

电商 AI 生图网关项目（MVP）：聚焦“模特图/种草图”生成流程，提供上传、任务创建、状态追踪、回调处理与结果分发能力。

## 项目结构

- `backend/`：FastAPI 网关与任务状态机（Redis）
- `frontend/`：React + TypeScript 前端页面
- `docs/`：需求、ADR、运维与安全文档
- `deploy/`：Nginx / systemd / Redis / 防火墙部署模板

## 快速开始

1. 启动后端并检查健康：
   - `cd backend && uvicorn app.main:app --host 127.0.0.1 --port 9000`
   - `curl http://127.0.0.1:9000/healthz`
2. 启动前端：
   - `cd frontend && npm install && npm run dev`

## 本地打包前端（推荐）

在本地执行一键打包脚本：

- `powershell -ExecutionPolicy Bypass -File scripts/pack-frontend.ps1`

产物输出到：

- `release-artifacts/sqtoimage-frontend-<timestamp>.zip`
- `release-artifacts/sqtoimage-frontend-<timestamp>.zip.sha256`

服务端发布命令见：

- `docs/ops/frontend-artifact-release.md`
- `docs/ops/codeup-closed-loop-runbook.md`

## 关键文档

- 需求：`需求文档.txt`
- 推理策略 ADR：`docs/adr/ADR-0002-hybrid-inference-stack-2026.md`
- 网关与网络安全：`docs/ops/gateway-security-runbook.md`
