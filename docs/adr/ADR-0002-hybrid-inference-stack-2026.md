# ADR-0002: 2026年推理底座升级为“双引擎并驾”（Creative + Constraint）

- Status: Proposed
- Date: 2026-04-14
- Deciders: Project Owner + Engineering
- Related:
  - `需求文档.txt`
  - `# Project Context & Tech Stack Selection.md`
  - `docs/adr/ADR-0001-mvp-workflow-state-machine-language.md`
  - `backend/openapi/v1.yaml`

## 背景

当前网关层（FastAPI + Redis + 状态机 + 回调）已经可用，但业务目标从“单一模特商拍图”扩展到：
1. 电商模特图（服装细节保真优先）
2. 种草图（审美与风格表达优先）

基于 2025-2026 的公开资料，纯 ComfyUI 单引擎在“审美上限、可维护性、可扩展性”上不再是最优解，尤其是在多风格、高迭代业务中。

## 要解决的问题

1. 如何在不推翻现有网关的前提下升级底层模型栈。
2. 如何兼顾“审美创作能力”和“服装细节约束能力”。
3. 如何避免非商用模型/许可证风险进入生产链路。
4. 如何让后续 Provider 替换不影响 API 合同与前端。

## 决策

1. **保持网关层不变，升级底层为“双引擎并驾”**
- 保留现有 `Job API + Redis 状态机 + 回调安全` 架构。
- 推理层拆为：
  - `Creative Engine`：负责风格创作与视觉质量上限（优先 API 模型）
  - `Constraint Engine`：负责结构约束/重绘/细节回正（Fill/Redux/结构控制）

2. **默认采用 `hybrid` 路由策略**
- 模特图场景：`constraint_first` 或 `hybrid`
- 种草图场景：`creative_first` 或 `hybrid`
- 由网关按 `quality_profile` 和失败类型自动降级/切换。

3. **将 VTON SOTA 作为“可插拔专项引擎”，不直接绑定生产主路径**
- OmniVTON / Voost / DEFT-VTON 进入评估池，用于高保真换装专项链路。
- 商用前必须通过许可证与法律审查，不满足则仅限研究/离线评估。

4. **合同优先：OpenAPI 外层语义稳定，内部引擎可迭代**
- 对前端保持统一任务语义：创建任务、查询状态、取结果。
- 内部新增 `engine_policy/provider_trace/quality_report`，避免以后每换模型都改前端。

## 关键依据（含时间锚点）

1. BFL 在 **2026-02-17** 明确 webhook 状态与轮询状态对齐，状态值从 `SUCCESS` 调整为 `Ready`。
2. BFL 在 **2026-03-03** 发布 `flux-2-pro-preview`，并说明约 2x 速度提升且 API 合同不变。
3. FLUX.2 官方文档已给出多参考图编辑、4MP 输出、端点“preview vs fixed snapshot”分层，这与“生产稳定 + 快速迭代”诉求一致。
4. OmniVTON 已进入 ICCV 2025 OpenAccess（Training-Free 方向成立）。
5. Voost 仓库声明 SIGGRAPH Asia 2025 接收，但仓库许可为 CC BY-NC-SA（非商用）。
6. DEFT-VTON 公开论文与 Amazon Science PDF显示发布时间在 2025 年（非 2026 首发）。

## 架构方案（v1）

### 1) 引擎分层

1. Creative Engine（默认主创作）
- 候选：FLUX.2 `pro/max/flex`（API）
- 输出：候选图 + provider request id + model endpoint

2. Constraint Engine（默认约束修正）
- 候选：FLUX Fill / Redux / Canny / Depth，或 SD3.5 ControlNet 链路
- 输出：结构回正图 + 局部修复图 + 保真评分

3. Optional VTON Engine（专项）
- 候选：OmniVTON / Voost / DEFT-VTON
- 用途：高保真换装专项任务或离线重处理

### 2) 状态机扩展（保持外层兼容）

建议从当前状态扩展为：
`queued -> running_creative -> running_constraint -> postprocessing -> succeeded | failed | timeout | cancelled`

说明：
1. 前端可继续把 `running_*` 视为 `running` 聚合态。
2. 后端保留细粒度状态用于可观测与故障定位。

### 3) 任务路由策略

新增策略字段：
1. `engine_policy`: `creative_first | constraint_first | hybrid`
2. `quality_profile`: `model_photo | seeding_photo`
3. `provider_preferences`（可选）

路由建议：
1. `model_photo`：优先 `constraint_first/hybrid`
2. `seeding_photo`：优先 `creative_first/hybrid`
3. 失败自动重试时可切换 provider 或阶段顺序

## OpenAPI 变更草案（建议）

`POST /v1/jobs` 请求体新增（向后兼容，可选）：
1. `engine_policy`
2. `quality_profile`
3. `provider_preferences`

`GET /v1/jobs/{job_id}` 响应新增：
1. `current_stage`（creative/constraint/postprocess）
2. `provider_trace[]`（provider、endpoint、latency、cost_estimate）
3. `quality_report`（garment_fidelity, face_usability, composition_score）

## 许可证与合规门禁

上线前必须通过：
1. 模型许可证审查（是否允许商用、是否限制输出再利用）
2. 数据合规审查（上传图与产物留存策略）
3. 供应商可用性与区域合规（如 EU/US endpoint 约束）

硬规则：
1. 标注为 `NC` 的模型不得进入商业生产主路径。
2. 研究模型必须隔离到 `research` profile，不得默认可调用。

## 实施计划（建议 3 周）

1. 第1周（接口与编排）
- 增加 `engine_policy/quality_profile` 字段与状态机阶段扩展。
- 抽象 `InferenceProvider` 接口，落地第一个 Creative Provider（API）。

2. 第2周（约束与质量）
- 接入 Constraint Provider（Fill/Redux/Control 路径）。
- 建立质量闸门与自动重试策略（按失败类型路由切换）。

3. 第3周（灰度与评估）
- 引入一个 VTON 专项引擎做离线 A/B。
- 形成“质量-成本-时延”周报，决定是否提升为主路径。

## 验收标准（MVP+）

1. 模特图服装保真通过率 >= 95%（内部标注集）
2. 种草图审美可用率 >= 90%（业务评审集）
3. 同输入重复任务的一致性可控（固定端点下可复现）
4. Provider 故障切换后可用率 >= 99%
5. 非商用许可证模型不得进入生产 profile

## 风险与缓解

1. 风险：preview 端点波动导致风格漂移  
缓解：生产默认固定端点；preview 仅灰度。

2. 风险：跨 provider 输出风格差异大  
缓解：引入质量闸门 + prompt 归一化模板 + A/B 评分。

3. 风险：回调字段变更造成状态错判  
缓解：事件映射表版本化；保留 provider contract tests。

4. 风险：商用许可不清导致法律风险  
缓解：上线前 License Gate；`research` 与 `prod` 严格隔离。

## 参考来源（2026-04-14 检索）

### 官方文档 / 官方仓库
1. BFL FLUX.2 Overview  
https://docs.bfl.ai/flux_2/flux2_overview
2. BFL Release Notes（含 2026-02-17 webhook 状态调整、2026-03-03 pro preview 变更）  
https://docs.bfl.ai/release-notes
3. BFL API Integration Guide（polling_url、delivery URL 不直连、10分钟过期）  
https://docs.bfl.ai/api_integration/integration_guidelines
4. FLUX 官方推理仓库（Fill/Redux/Canny/Depth、许可与商用说明）  
https://github.com/black-forest-labs/flux
5. ComfyUI Partner Nodes Overview（闭源 API 节点与接入约束）  
https://docs.comfy.org/tutorials/partner-nodes/overview
6. Stability SD3.5 官方仓库（含 SD3.5 Large ControlNets）  
https://github.com/Stability-AI/sd3.5

### 论文 / 学术页面
1. OmniVTON（ICCV 2025 OpenAccess）  
https://openaccess.thecvf.com/content/ICCV2025/html/Yang_OmniVTON_Training-Free_Universal_Virtual_Try-On_ICCV_2025_paper.html
2. OmniVTON arXiv  
https://arxiv.org/abs/2507.15037
3. Voost arXiv  
https://arxiv.org/abs/2508.04825
4. Voost GitHub（仓库声明 SIGGRAPH Asia 2025 接收）  
https://github.com/nxnai/Voost
5. DEFT-VTON arXiv  
https://arxiv.org/abs/2509.13506
6. DEFT-VTON Amazon Science PDF  
https://assets.amazon.science/5a/2b/0ef1b91f4f35996b293ae44dccf5/deft-vton-efficient-virtual-try-on-with-consistent-generalised-h-transform.pdf

### 许可证风险样例（用于合规提醒）
1. CatVTON（README License: CC BY-NC-SA 4.0）  
https://github.com/Zheng-Chong/CatVTON
2. IDM-VTON（README License: CC BY-NC-SA 4.0）  
https://github.com/yisol/IDM-VTON

## 推断说明

以下结论属于“基于公开资料的工程推断”，非单一官方声明：
1. “双引擎并驾”是当前最稳的工程折中（质量/可控/可运维）。
2. VTON 新模型适合作为专项分支，但是否可直接商用取决于许可证与法务结论。
3. 生产应优先固定端点，preview 用于灰度，以降低可复现性风险。

