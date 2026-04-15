# Backend Docker Runbook (Gateway 4G Profile)

- Last Updated: 2026-04-15
- Scope: Run `backend + redis` on gateway host with Docker Compose.
- Target path example: `/data/S-image`

## 1. Prerequisites

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

## 2. Prepare backend env

```bash
cd /data/S-image/backend
cp -n .env.example .env
```

Recommended key values in `backend/.env`:

```env
REDIS_KEY_PREFIX=imgwf_mvp
CALLBACKS_SECRET=<strong-random-secret>
PUBLIC_BASE_URL=https://<your-domain>
MIRROR_GENERATED_OUTPUTS=true
UPLOAD_IMAGE_MAX_BYTES=524288000
```

## 3. Switch runtime from systemd to docker

If you were previously running systemd backend:

```bash
sudo systemctl disable --now s-image-backend || true
```

Bring up Docker stack:

```bash
cd /data/S-image
docker compose -f deploy/docker/docker-compose.gateway.yml up -d --build
```

## 4. Verify

```bash
docker compose -f deploy/docker/docker-compose.gateway.yml ps
curl -sS http://127.0.0.1:9000/healthz
docker logs --tail 80 s-image-backend
docker logs --tail 80 s-image-redis
```

Expected:

1. `s-image-backend` and `s-image-redis` are `Up`.
2. `/healthz` returns `{"status":"ok"}`.

## 5. Daily deploy from Codeup (docker mode)

```bash
cd /data/S-image
bash scripts/deploy-from-git.sh \
  --repo-dir /data/S-image \
  --remote origin \
  --branch main \
  --backend-runtime docker \
  --docker-compose-file deploy/docker/docker-compose.gateway.yml \
  --docker-services "backend" \
  --reload-nginx
```

If Redis config changed, deploy both services:

```bash
bash scripts/deploy-from-git.sh \
  --repo-dir /data/S-image \
  --backend-runtime docker \
  --docker-compose-file deploy/docker/docker-compose.gateway.yml \
  --docker-services "backend redis"
```

## 6. Rollback

```bash
cd /data/S-image
git log --oneline -n 5
git checkout <good_commit_sha>
docker compose -f deploy/docker/docker-compose.gateway.yml up -d --build
```

## 7. Notes

1. Backend and Redis ports are loopback-only by design (`127.0.0.1`).
2. Nginx stays on host and reverse-proxies to `127.0.0.1:9000`.
3. For 4G host, avoid building frontend on server.
