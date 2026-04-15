# ACR Personal Edition Runbook (Gateway Docker)

- Last Updated: 2026-04-15
- Goal: Avoid Docker Hub instability on ECS by using Alibaba Cloud ACR Personal as image source.

## 1. Create ACR repos

In ACR Personal:

1. Create namespace (example: `simage`).
2. Create repositories:
- `s-image-backend`
- `redis`

## 2. Build and push images from local machine

```bash
# login (replace region)
docker login registry.cn-hangzhou.aliyuncs.com

# push redis mirror once
docker pull redis:7.2-alpine
docker tag redis:7.2-alpine registry.cn-hangzhou.aliyuncs.com/<namespace>/redis:7.2-alpine
docker push registry.cn-hangzhou.aliyuncs.com/<namespace>/redis:7.2-alpine

# build backend image and push
cd backend
docker build -t registry.cn-hangzhou.aliyuncs.com/<namespace>/s-image-backend:latest .
docker push registry.cn-hangzhou.aliyuncs.com/<namespace>/s-image-backend:latest
```

## 3. Prepare env mapping on server

```bash
cd /data/S-image
cp -n deploy/docker/acr.env.example deploy/docker/acr.env
```

Edit `deploy/docker/acr.env`:

```env
IMAGE_BACKEND=registry.cn-hangzhou.aliyuncs.com/<namespace>/s-image-backend:latest
IMAGE_REDIS=registry.cn-hangzhou.aliyuncs.com/<namespace>/redis:7.2-alpine
```

## 4. Switch runtime and deploy

```bash
sudo systemctl disable --now s-image-backend || true

docker login registry.cn-hangzhou.aliyuncs.com

bash scripts/deploy-from-git.sh \
  --repo-dir /data/S-image \
  --remote origin \
  --branch main \
  --backend-runtime docker \
  --docker-compose-file deploy/docker/docker-compose.gateway.acr.yml \
  --docker-env-file deploy/docker/acr.env \
  --docker-no-build \
  --docker-services "backend" \
  --reload-nginx
```

## 5. Verify

```bash
docker compose \
  -f deploy/docker/docker-compose.gateway.acr.yml \
  --env-file deploy/docker/acr.env \
  ps

curl -sS http://127.0.0.1:9000/healthz
```

Expected:

1. `s-image-backend` and `s-image-redis` are `Up`.
2. `healthz` returns `{"status":"ok"}`.

## 6. Update release flow

When backend code changes:

1. Local: rebuild and push backend image to ACR.
2. Local: push git to Codeup.
3. Server: run the deploy command in section 4.