# Codeup Closed-Loop Runbook

- Last Updated: 2026-04-15
- Goal: Use Alibaba Cloud Codeup as the primary git source for server pull-based deployment.

## 1. Target flow

1. Local dev machine: code changes, commit, push to Codeup.
2. Gateway server: `git pull` from Codeup and restart services.
3. Frontend static assets: still recommended via local artifact release (`pack-frontend.ps1` + `deploy-frontend.sh`).

## 2. Local remote setup

Keep Codeup as `origin`, keep GitHub as backup mirror remote:

```bash
git remote rename origin github
git remote add origin git@codeup.aliyun.com:<org>/<repo>.git
git push -u origin main
```

Optional mirror push:

```bash
git push github main
```

## 3. Server SSH key for Codeup

On server:

```bash
ssh-keygen -t ed25519 -C "s-image-deploy" -f ~/.ssh/codeup_deploy_key
cat ~/.ssh/codeup_deploy_key.pub
```

Add that public key to Codeup repo Deploy Key (read-only recommended).

`~/.ssh/config` example:

```sshconfig
Host codeup.aliyun.com
  HostName codeup.aliyun.com
  User git
  IdentityFile ~/.ssh/codeup_deploy_key
  IdentitiesOnly yes
```

Test:

```bash
ssh -T git@codeup.aliyun.com
```

## 4. First clone on server

```bash
git clone git@codeup.aliyun.com:<org>/<repo>.git /opt/S-image
cd /opt/S-image
git checkout main
```

## 5. Daily deploy from git

Use script:

### 5.1 Docker runtime (recommended, local build mode)

```bash
chmod +x /opt/S-image/scripts/deploy-from-git.sh
bash /opt/S-image/scripts/deploy-from-git.sh \
  --repo-dir /opt/S-image \
  --remote origin \
  --branch main \
  --backend-runtime docker \
  --docker-compose-file deploy/docker/docker-compose.gateway.yml \
  --docker-services "backend" \
  --reload-nginx
```

### 5.2 Docker runtime (recommended on ECS, ACR mode)

```bash
cp -n /opt/S-image/deploy/docker/acr.env.example /opt/S-image/deploy/docker/acr.env
# edit acr.env before deploy

bash /opt/S-image/scripts/deploy-from-git.sh \
  --repo-dir /opt/S-image \
  --remote origin \
  --branch main \
  --backend-runtime docker \
  --docker-compose-file deploy/docker/docker-compose.gateway.acr.yml \
  --docker-env-file deploy/docker/acr.env \
  --docker-no-build \
  --docker-services "backend" \
  --reload-nginx
```

### 5.3 Systemd runtime (fallback)

```bash
bash /opt/S-image/scripts/deploy-from-git.sh \
  --repo-dir /opt/S-image \
  --remote origin \
  --branch main \
  --backend-runtime systemd \
  --backend-service s-image-backend \
  --reload-nginx
```

If requirements changed and you are on systemd runtime:

```bash
bash /opt/S-image/scripts/deploy-from-git.sh \
  --repo-dir /opt/S-image \
  --backend-runtime systemd \
  --install-backend-deps \
  --pip-index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

## 6. Release discipline

1. Production server should not be used as a dev machine.
2. Keep server repo clean (no local edits in `/opt/S-image`).
3. Use `pull --ff-only` style updates only.
4. Frontend artifact release remains best for low-memory servers.

## 7. Fallback path

If Codeup access is temporarily degraded, use artifact path:

1. Local pack: `scripts/pack-frontend.ps1`
2. Server deploy: `scripts/deploy-frontend.sh`