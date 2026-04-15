# Gateway + Network Security Runbook (MVP)

- Target date: 2026-04-15
- Scope: Single-node CPU gateway + Redis + backend + external ComfyUI callback
- Host assumption: Linux (Ubuntu 22.04 compatible)

## 1. Target topology

1. Public internet -> `Nginx:443`
2. Nginx -> `FastAPI:127.0.0.1:9000`
3. FastAPI -> `Redis:6379` (same Docker compose network)
4. FastAPI -> external ComfyUI (outbound)
5. ComfyUI callback -> `https://<domain>/api/v1/callbacks/comfyui`

## 2. Security baseline checklist

1. Open public ports: `80/443` only.
2. `22` SSH must be restricted by cloud security group and host firewall.
3. `9000` (FastAPI) must bind only to loopback.
4. `6379` (Redis) must bind only to loopback publish (`127.0.0.1:6379:6379`) when exposed.
5. `CALLBACKS_SECRET` must be non-empty in production.
6. TLS certificate must be valid, with HTTP redirected to HTTPS.
7. Nginx rate limiting must be enabled for `/api/` and callback endpoint.
8. Upload endpoint must use route-level limit (`500m`) and longer timeout.

## 3. Deploy backend + Redis (Docker recommended)

Use template:

- `deploy/docker/docker-compose.gateway.yml`
- `deploy/docker/redis/redis.conf`
- `backend/Dockerfile`

Example:

```bash
cd /opt/S-image
cp -n backend/.env.example backend/.env
docker compose -f deploy/docker/docker-compose.gateway.yml up -d --build
docker compose -f deploy/docker/docker-compose.gateway.yml ps
```

Important env values in `backend/.env`:

```env
REDIS_KEY_PREFIX=imgwf_mvp
CALLBACKS_SECRET=<strong-random-secret>
PUBLIC_BASE_URL=https://<your-domain>
MIRROR_GENERATED_OUTPUTS=true
UPLOAD_IMAGE_MAX_BYTES=524288000
```

## 4. Runtime fallback (systemd)

If you do not use Docker for backend, use:

- `deploy/systemd/s-image-backend.service`

For commands, follow `docs/ops/codeup-closed-loop-runbook.md` section "systemd runtime".

## 5. Timeout and size strategy (recommended)

1. Generic API (`/api/*` except upload): `proxy_read_timeout/proxy_send_timeout=90s`
2. Callback endpoint (`/api/v1/callbacks/comfyui`): `30s`
3. Upload endpoint (`/api/v1/uploads/images`):

- `client_max_body_size=500m`
- `client_body_timeout=300s`
- `proxy_send_timeout=300s`
- `proxy_read_timeout=300s`

## 6. Configure Nginx reverse proxy

Use template:

- `deploy/nginx/S-image.conf`

Required edits before enabling:

1. `server_name your-domain.com`
2. `ssl_certificate` and `ssl_certificate_key`
3. `root /var/www/s-image-frontend`

Enable:

```bash
sudo cp deploy/nginx/S-image.conf /etc/nginx/sites-available/S-image.conf
sudo ln -sf /etc/nginx/sites-available/S-image.conf /etc/nginx/sites-enabled/S-image.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 7. Host firewall (UFW)

Use script:

- `deploy/security/ufw-baseline.sh`

Example:

```bash
sudo ADMIN_SSH_IP="<your-fixed-ip>" bash deploy/security/ufw-baseline.sh
```

## 8. Cloud security group rules

1. Inbound allow: `443`, `80`, `22` (22 restricted to fixed IP).
2. Inbound deny: `6379`, `9000`.
3. Outbound: allow required internet access for package updates and ComfyUI endpoint.

## 9. Verification commands

From gateway server:

```bash
curl -sS http://127.0.0.1:9000/healthz
curl -Ik https://<your-domain>/healthz
curl -Ik https://<your-domain>/api/v1/jobs/not-a-uuid
docker exec -it s-image-redis redis-cli ping
sudo ss -lntp | egrep ':80|:443|:9000|:6379'
```

Expected:

1. Local `/healthz` returns `{"status":"ok"}`.
2. Public `/healthz` reachable over HTTPS.
3. Invalid UUID API returns controlled `4xx` from backend.
4. Redis returns `PONG`.
5. `9000` and `6379` are not exposed on public interface.

## 10. Common mistakes

1. Running backend on `0.0.0.0` and exposing `9000` publicly.
2. Forgetting to set `CALLBACKS_SECRET` in production.
3. Nginx `/api` reverse proxy not stripping prefix (`proxy_pass` path mismatch).
4. Upload size too small in Nginx (`client_max_body_size`).
5. Upload route not using dedicated timeout policy.
6. Public domain not set in `PUBLIC_BASE_URL`, resulting in wrong image URLs.
