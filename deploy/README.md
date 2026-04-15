# Deployment Assets (Gateway + Security Baseline)

This folder contains production-oriented templates for single-node MVP deployment.

## Files

- `deploy/nginx/S-image.conf`
  - Nginx reverse proxy for frontend + backend API.
  - Assumes backend listens on `127.0.0.1:9000`.
  - Exposes only `80/443`.
  - Upload route `/api/v1/uploads/images` uses dedicated `500m` body limit and `300s` timeout.
- `deploy/docker/docker-compose.gateway.yml`
  - Gateway runtime stack: `backend + redis` (Docker Compose, local build mode).
  - Suitable when server can reliably pull base images from Docker Hub.
- `deploy/docker/docker-compose.gateway.acr.yml`
  - Gateway runtime stack: `backend + redis` (ACR image pull mode, no local build).
  - Designed for ECS environments with Docker Hub instability.
- `deploy/docker/acr.env.example`
  - Image mapping template for ACR mode (`IMAGE_BACKEND`, `IMAGE_REDIS`).
- `deploy/docker/docker-compose.redis.yml`
  - Redis standalone compose (fallback when backend runs outside Docker).
- `deploy/docker/redis/redis.conf`
  - Redis persistence and safety profile.
- `deploy/systemd/s-image-backend.service`
  - Systemd unit for FastAPI/Uvicorn process management (fallback runtime).
- `deploy/security/ufw-baseline.sh`
  - Firewall bootstrap script (UFW).
- `scripts/pack-frontend.ps1`
  - Local Windows pack script for frontend artifact.
- `scripts/deploy-frontend.sh`
  - Linux server release switch script for frontend artifact deployment.
- `scripts/deploy-from-git.sh`
  - Linux server git pull deploy script for Codeup-based updates.
  - Supports `--backend-runtime systemd` and `--backend-runtime docker`.
  - Docker mode supports `--docker-env-file` and `--docker-no-build`.

## Before using in production

1. Replace domain, TLS cert paths, and frontend root path in Nginx config.
2. Set a strong `CALLBACKS_SECRET` in backend `.env`.
3. Confirm `PUBLIC_BASE_URL` is your real HTTPS domain.
4. Restrict SSH source IP at both cloud security-group and host firewall level.