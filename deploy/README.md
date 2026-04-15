# Deployment Assets (Gateway + Security Baseline)

This folder contains production-oriented templates for single-node MVP deployment.

## Files

- `deploy/nginx/sqtoimage.conf`
  - Nginx reverse proxy for frontend + backend API.
  - Assumes backend listens on `127.0.0.1:9000`.
  - Exposes only `80/443`.
  - Upload route `/api/v1/uploads/images` uses dedicated `500m` body limit and `300s` timeout.
- `deploy/docker/docker-compose.redis.yml`
  - Redis standalone container bound to `127.0.0.1:6379`.
- `deploy/docker/redis/redis.conf`
  - Redis persistence and safety profile.
- `deploy/systemd/sqtoimage-backend.service`
  - Systemd unit for FastAPI/Uvicorn process management.
- `deploy/security/ufw-baseline.sh`
  - Firewall bootstrap script (UFW).
- `scripts/pack-frontend.ps1`
  - Local Windows pack script for frontend artifact.
- `scripts/deploy-frontend.sh`
  - Linux server release switch script for frontend artifact deployment.

## Before using in production

1. Replace domain, TLS cert paths, and frontend root path in Nginx config.
2. Set a strong `CALLBACKS_SECRET` in backend `.env`.
3. Confirm `PUBLIC_BASE_URL` is your real HTTPS domain.
4. Restrict SSH source IP at both cloud security-group and host firewall level.
