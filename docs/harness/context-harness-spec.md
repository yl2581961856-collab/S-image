# Context Harness 规范（MVP）

- Version: v1
- Scope: 生图网关链路（upload -> create job -> callback -> get job）
- Last Updated: 2026-04-14

## 1. 目标

把“上下文”从临时运行态变量，升级为可复用、可追踪、可回放的工程资产，解决以下问题：
1. 同一用例多次执行结果不一致。
2. 配置漂移导致无法定位回归问题。
3. 故障难以复现（尤其是回调顺序、幂等冲突、进度异常）。

## 2. 上下文定义

在本项目中，“上下文”由以下 6 类信息组成：
1. 输入上下文：上传图片、风格参数、比例、workflow_version。
2. 运行上下文：run_id、env、redis_key_prefix、api_base_url。
3. 事件上下文：回调事件序列（accepted/progress/completed/postprocess_completed）。
4. 安全上下文：签名策略、nonce/时间窗校验开关。
5. 输出上下文：job 状态轨迹、progress 曲线、output_urls。
6. 指标上下文：成功率、P95、失败分类、幂等冲突率。

## 3. 目录约定

建议 harness 工程目录：

```text
harness/
  cases/
    case_001_basic.yaml
    case_002_idempotency_conflict.yaml
  runs/
    2026-04-14T10-10-00Z_run-001/
      context.json
      events.jsonl
      snapshots/
        t0_create_job.json
        t1_progress.json
        t2_succeeded.json
      report.json
  scripts/
    run_case.py
    replay_events.py
    diff_report.py
```

## 4. Context Manifest（单用例）

每个用例必须有一个 manifest 文件，作为唯一上下文来源。

示例：`harness/cases/case_001_basic.yaml`

```yaml
case_id: case_001_basic
name: basic_generate_success

context:
  workflow_type: model_photo_generation_french_street_asian_sweet
  workflow_version: v1
  workflow_params:
    style_id: french_street
    model_face: asian_sweet
    aspect_ratio: "3:4"
  image_path: fixtures/input/test1.jpg

runtime:
  api_base_url: http://127.0.0.1:9000
  redis_key_prefix: imgwf_harness_case001
  idempotency_key: idem-case001-001

callback_plan:
  - event: accepted
  - event: progress
    progress: 0.35
  - event: progress
    progress: 0.72
  - event: completed
    output_urls:
      - http://127.0.0.1:9000/uploads/images/mock.jpg
  - event: postprocess_completed

assertions:
  final_status: succeeded
  progress_monotonic: true
  output_urls_min_count: 1
```

## 5. Context Envelope（运行注入）

每次运行动态生成并保存 `context.json`，包含：
1. `run_id`（全局唯一）
2. `case_id`
3. `started_at/ended_at`
4. `git_sha`（如有）
5. `env_fingerprint`（关键配置哈希）
6. `api_base_url`
7. `redis_key_prefix`

用途：
1. 追踪一次执行全链路。
2. 支持跨环境结果对比。

## 6. 上下文隔离策略

每次运行必须隔离：
1. Redis：`redis_key_prefix = imgwf_harness_<run_id>`。
2. 上传目录：`storage/harness/<run_id>/...`（建议后续接入）。
3. 幂等键：不可跨 run 复用。
4. 日志文件：按 run_id 独立目录保存。

## 7. 事件回放策略

所有回调事件写入 `events.jsonl`：
1. 每行一条 JSON，包含 `timestamp/event/payload_hash/http_status`。
2. 回放脚本按文件顺序重放，必须可复现原始状态轨迹。
3. 若顺序变化导致状态冲突（409），标记为上下文漂移风险。

推荐事件记录格式：

```json
{"ts":"2026-04-14T10:11:01Z","event":"accepted","status":200}
{"ts":"2026-04-14T10:11:03Z","event":"progress","progress":0.35,"status":200}
{"ts":"2026-04-14T10:11:05Z","event":"completed","status":200}
```

## 8. 快照与 Diff

在关键节点保存快照：
1. `t0_create_job.json`
2. `t1_progress.json`
3. `t2_terminal.json`

Diff 规则：
1. 允许变化：`job_id`、时间戳、request_id。
2. 不允许变化：状态终态、进度单调性、错误码语义、输出数量下限。
3. 发现不允许变化即判为回归。

## 9. 质量门禁（Gate）

建议最低门禁：
1. `contract_pass_rate = 100%`
2. `final_status_success_rate >= 95%`
3. `progress_monotonic_violation = 0`
4. `idempotency_conflict_behavior_pass = 100%`
5. `callback_replay_reject_pass = 100%`（同 nonce 重放应拒绝）

发布规则：
1. 任一硬门禁失败，禁止进入生产发布流程。

## 10. 与当前后端对齐点

当前已具备：
1. 任务状态机与 progress（0-100）响应。
2. 幂等键冲突返回 409。
3. 回调签名与重放防护（配置 secret 后生效）。
4. 回调输出可镜像到网关存储。

建议下一步（Harness 实施）：
1. 增加 `harness/cases` 样例集（先 5 个核心用例）。
2. 编写 `run_case.py` 一键执行脚本。
3. 输出 `report.json` 并接入发布门禁。
