# Frontend Artifact Release Runbook

- Last Updated: 2026-04-15
- Goal: Build frontend locally, upload artifact, deploy on server without running npm build on production host.

## 1. Local build and pack (Windows)

From repo root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\pack-frontend.ps1
```

Output files:
1. `release-artifacts/sqtoimage-frontend-<tag>.zip`
2. `release-artifacts/sqtoimage-frontend-<tag>.zip.sha256`

## 2. Upload artifact to server

Example:

```powershell
scp .\release-artifacts\sqtoimage-frontend-20260415_143433.zip root@<server-ip>:/data/releases/
scp .\scripts\deploy-frontend.sh root@<server-ip>:/data/sqtoimage/scripts/
```

## 3. Deploy on server

```bash
chmod +x /data/sqtoimage/scripts/deploy-frontend.sh
bash /data/sqtoimage/scripts/deploy-frontend.sh \
  --artifact /data/releases/sqtoimage-frontend-20260415_143433.zip \
  --app-root /var/www/sqtoimage-frontend \
  --reload-nginx
```

## 4. Nginx path expectation

Nginx static root should point to:

```nginx
root /var/www/sqtoimage-frontend/current;
```

## 5. Rollback

List releases:

```bash
ls -1 /var/www/sqtoimage-frontend/releases
```

Switch symlink back:

```bash
ln -sfn /var/www/sqtoimage-frontend/releases/<old_tag> /var/www/sqtoimage-frontend/current
nginx -t && systemctl reload nginx
```

## 6. Notes

1. Production server should not run `npm install` or `npm run build`.
2. Build dependencies remain local; production only serves static files.
3. Keep at least 2-3 recent release folders for fast rollback.

