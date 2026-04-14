# 阿里云网关安全配置清单（MVP）

适用场景：
- 前端 + FastAPI 网关部署在阿里云 ECS
- ComfyUI 部署在 AutoDL（公网回调）
- Redis 与网关同机（Docker 独立容器）

## 1. 网络拓扑与暴露面

目标原则：
1. 仅暴露 `80/443`（建议最终只保留 `443`）。
2. `FastAPI` 仅本机回环监听（如 `127.0.0.1:8000`）。
3. `Redis 6379` 不对公网开放，仅容器内部或本机访问。

推荐拓扑：
1. Internet -> `Nginx:443` -> `FastAPI:127.0.0.1:8000`
2. FastAPI -> AutoDL ComfyUI（出站 HTTPS）
3. AutoDL -> `/v1/callbacks/comfyui`（入站 HTTPS + 签名校验）

## 2. 阿里云安全组（ECS）

入方向（Inbound）：
1. `443/tcp`：`0.0.0.0/0`（必须）
2. `80/tcp`：`0.0.0.0/0`（仅用于跳转 HTTPS，可选）
3. `22/tcp`：仅你的固定办公 IP（禁止 `0.0.0.0/0`）
4. 禁止开放：`6379`、`8000`、`5555` 等内部端口

出方向（Outbound）：
1. 默认允许即可（MVP）
2. 若要收紧：仅放行 DNS、NTP、AutoDL 域名/IP、系统更新源

## 3. 主机与容器层

1. 系统定期更新安全补丁。
2. 禁止 root 远程登录，启用 SSH key 登录。
3. Docker 不暴露 Redis 到公网，建议绑定 `127.0.0.1:6379` 或仅 bridge 网络。
4. Redis 建议配置：
   - `appendonly yes`
   - `appendfsync everysec`
   - `maxmemory 512mb`
   - `maxmemory-policy noeviction`
   - `protected-mode yes`
5. `.env` 文件权限收紧（仅部署用户可读）。

## 4. Nginx 安全配置（可直接改造）

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_session_timeout 10m;
    ssl_session_cache shared:SSL:10m;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy no-referrer-when-downgrade always;

    client_max_body_size 20m;
    client_body_timeout 15s;
    client_header_timeout 15s;
    send_timeout 30s;
    keepalive_timeout 30s;

    limit_req_zone $binary_remote_addr zone=api_rl:10m rate=20r/s;

    location /api/ {
        limit_req zone=api_rl burst=40 nodelay;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-Id $request_id;

        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_pass http://127.0.0.1:8000/;
    }

    location = /api/v1/callbacks/comfyui {
        limit_req zone=api_rl burst=20 nodelay;
        proxy_set_header Host $host;
        proxy_set_header X-Request-Id $request_id;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://127.0.0.1:8000/v1/callbacks/comfyui;
    }

    location / {
        # 前端部署位置（静态或 Node SSR）
        root /var/www/frontend;
        try_files $uri /index.html;
    }
}
```

说明：
1. 如果前端不是静态站点（如 Next SSR），`location /` 改成反向代理到前端进程端口。
2. 如果后端不做 `/api` 前缀，请按实际路由调整转发路径。

## 5. 回调安全（与你现有代码对齐）

1. 强制配置 `CALLBACKS_SECRET`。
2. 回调必须携带：
   - `X-ComfyUI-Signature`
   - `X-ComfyUI-Timestamp`
   - `X-ComfyUI-Nonce`
3. 代码端已支持：
   - HMAC-SHA256 签名校验
   - 时间窗口校验
   - nonce 防重放
   - `provider_request_id` 事件去重

## 6. 日志与告警

1. 记录 `request_id`、`job_id`、回调签名校验结果。
2. 对以下事件告警：
   - 回调 `401` 持续上升
   - 状态迁移 `409` 异常上升
   - Redis 连接失败或 `used_memory` 超阈值
3. 日志脱敏：token、密钥、手机号、地址不落明文。

## 7. 上线前核对（Checklist）

1. 安全组确认仅开放 `443/80/22`（22 为办公 IP 白名单）。
2. `FastAPI` 与 `Redis` 均未公网监听。
3. `CALLBACKS_SECRET` 已配置且非默认值。
4. HTTPS 证书有效，HTTP 已跳转 HTTPS。
5. Nginx 限流已开启，回调路径可用。
6. 进行一次回调重放攻击自测（同 nonce 重放应返回 `401`）。
7. Redis AOF 已开启并验证重启后数据恢复。

## 8. 迭代升级（流量上来后）

1. 加阿里云 WAF（Web 攻击与 CC 防护）。
2. 网关与 Redis 分机部署。
3. 上 SLB + 多实例网关。
4. 出站访问收敛（白名单域名/IP）。
