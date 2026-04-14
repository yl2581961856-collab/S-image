# MVP Runtime Profile (Single Node, x86 + RTX 4090 24GB)

## Input Baseline
- CPU arch: x86
- RAM: 16GB
- GPU: NVIDIA RTX 4090 24GB
- Deployment: single node
- Redis: standalone container on same host as API gateway
- Peak API concurrency: 5
- Initial throughput target: ~50 generated images/day

## Recommended Initial Settings

### API / Redis
- `REDIS_URL=redis://localhost:6379/0`
- `REDIS_KEY_PREFIX=imgwf_mvp`
- `JOB_TTL_SECONDS=604800`
- `IDEMPOTENCY_TTL_SECONDS=86400`
- `CALLBACK_CLOCK_SKEW_SECONDS=300`
- `CALLBACK_NONCE_TTL_SECONDS=600`
- `CALLBACK_EVENT_DEDUP_TTL_SECONDS=86400`

### Uvicorn
- Start with 2 workers:
  - `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2`
- If CPU < 70% and response latency is stable, test 3 workers.

### Redis container
- Use persistence (`AOF`) and no-eviction policy:
  - `appendonly yes`
  - `appendfsync everysec`
  - `maxmemory 512mb`
  - `maxmemory-policy noeviction`

## Concurrency Strategy for 4090
- API concurrency can be 5, but generation workers should be limited:
  - SDXL high-res path: start with 1 concurrent generation
  - SD1.5 path: start with 2 concurrent generations
- Queue all overflow requests to avoid VRAM spikes and OOM.

## Timeout / Retry Baseline
- ComfyUI callback skew window: 5 minutes (already configured).
- Suggest business timeouts:
  - single generation hard timeout: 10-15 minutes
  - callback retry backoff: 2s, 5s, 10s, 20s (max 4 retries)

## What to Measure During MVP
- Success rate (target >= 95%)
- P95 end-to-end latency
- GPU memory peak and OOM count
- Callback duplicate rate
- Cost per generated image

## Scale Trigger (when to move beyond current profile)
- Queue wait P95 > 60s for 3 consecutive days
- OOM events > 1% of jobs
- API CPU > 75% sustained during business peak
