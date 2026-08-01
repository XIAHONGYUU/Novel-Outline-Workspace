# Workspace Acceptance Framework

最后更新：2026-08-01

这份文档不是记录单条规则，也不是记录单个样例细节。

它回答的是更上层的问题：

`P0 阶段到底按什么框架推进，以及 P0 收口后怎样继续约束 P1？`

## 核心思路

当前默认推进方式是：

1. 先定义一组稳定的 `acceptance tracks`
2. 每一轮优先补齐某一条 track 的真实闭环
3. 只有某条 track 被真实 workspace 卡住时，才回头修脚本、规则或 planner

这意味着 P0 已收口后，后续也不再默认问：

- “还能再补哪个句式？”
- “还能再加哪个局部规则？”

而是优先问：

- “当前缺的是哪一条工作区级闭环？”
- “这条闭环有没有被真实 workspace 验收？”
- “卡住它的是数据模型、planner、apply，还是 consistency？”

## P0 Acceptance Tracks

### Track 1: Base Flow

目标：

- `ingest -> check-consistency -> plan-merge -> apply-merge -> validate`

收口标准：

- 至少一个独立 workflow case 能完整跑通
- `state / outline / timeline / views` 同步更新
- validator `ok=true`

当前状态：

- 已完成
- 样例：`first-workflow-case/`

### Track 2: Repair Intake

目标：

- `needs-info / warning-only` case 能明确收敛到 `repair-intake`

收口标准：

- 缺字段不会被误判成 ready-to-apply
- intake patch 有确定性脚本入口
- patch 之后旧 report / plan 会失效

当前状态：

- 已完成
- 样例：`demo-workspace/idea-20260511-006`

### Track 3: Multi-Input Apply

目标：

- 同一条 idea 能一次性消费多个 `merge_input_id`

收口标准：

- CLI 支持重复传 `--merge-input-id`
- `timeline / outline / canon` 可组合落地
- `idea-log` 正确记录 `applied_merge_input_ids`

当前状态：

- 已完成
- 样例：`demo-workspace/idea-20260602-001`

### Track 4: Relationship First Node

目标：

- relationship 类 idea 第一次落成正式 `canon relationship`

收口标准：

- planner 产出 `scene + relationship` 两条可执行输入
- apply 后 scene 与 canon 同步写入

当前状态：

- 已完成
- 样例：`demo-workspace/idea-20260602-002`

### Track 5: Same-State Repeat Beat

目标：

- 处理“已有关系节点后，又出现同状态 repeat beat”

收口标准：

- 不覆写旧的 `canon relationship` 首次节点
- 默认落成 `scene-only` gate-resolving input
- rerun consistency 后冲突清空

当前状态：

- 已完成
- 样例：`demo-workspace/idea-20260602-003`

### Track 6: Relationship State Transition

目标：

- 处理“已有关系状态真正发生变化”

收口标准：

- planner 追加新的 `canon relationship` history node
- 不覆写旧节点
- `scene + canon` 一次性落地

当前状态：

- 已完成
- 样例：`demo-workspace/idea-20260602-004`

### Track 7: Relationship Reconciliation Chain

目标：

- 在已有 history chain 上继续追加后续复归节点

收口标准：

- 可稳定表达 `allied -> ruptured -> reconciled`
- 中间节点不会因后续恢复而丢失
- validator / consistency 保持正常

当前状态：

- 已完成
- 样例：`demo-workspace/idea-20260603-001`

### Track 8: Post-Reconciliation Repeat Beat

目标：

- 在已有 `reconciled` 节点之后，再处理 `再次结盟 / 再次和解` 一类 beat

当前状态：

- 已完成
- 样例：`demo-workspace/idea-20260603-002`

收口结论：

- 在已有 `reconciled` 节点之后，`再次和解 / 再次结盟` 这类 same-state repeat beat 仍默认回到 `scene-only`
- 不覆写最近的 `canon relationship` 节点
- rerun consistency 后冲突可清空

### Track 9: Knowledge-State Lifecycle

目标：

- 把 `knowledge-state` 也从“单次写入能力”推进成“真实 lifecycle 验收轨道”

待回答问题：

- 第一条正式 `knowledge-state` 节点怎样在真实 workspace 稳定落库
- 后续同一主体对同一事实的 recap / repeat beat，是否应只停留在 scene / timeline
- 新主体在更晚章节得知同一事实时，怎样与既有节点共存而不互相覆盖

当前状态：

- 已完成
- 样例：
  - `demo-workspace/idea-20260604-003`：first node
  - `demo-workspace/idea-20260604-001`：same-subject later recap
  - `demo-workspace/idea-20260604-004`：second-subject later learns

收口结论：

- 第一条正式 `knowledge-state` 节点现在已能在真实 workspace 中稳定落成 `timeline / outline + canon`
- same-subject later recap 默认会保留既有 `knowledge-state` 首次节点，只把后续确认 beat 落成 `scene-only`
- 新主体在更晚章节得知同一事实时，会追加新的 chapter-scoped `knowledge-state` 节点，而不会覆写旧主体记录

### Track 10: World-Rule Exception Lifecycle

目标：

- 把 `world-rule exception` 也从“规则检测 + planner explainers”推进成“真实 workspace lifecycle 验收轨道”

待回答问题：

- 第一条正式 exception 节点怎样在真实 workspace 稳定落库
- 已有 prior-exception 之后，后续叙事 beat 怎样继续沿用 / 注释 / 改写 exception chain
- mixed-subject / split-scope case 在已有 exception 基础上怎样稳定收口，而不误共用同一条 exception 记录

当前状态：

- 已完成
- 已完成样例：
  - `demo-workspace/idea-20260604-005`：first exception
  - `demo-workspace/idea-20260604-006`：prior-exception continuity
  - `demo-workspace/idea-20260605-002`：prior-exception + split-subjects claim-match direct closure
  - `demo-workspace/idea-20260605-003`：prior-exception + mixed-subjects local-signal review-only closure

阶段结论：

- 第一条正式 exception 节点现在已能在真实 workspace 中稳定落成 `timeline / outline + canon knowledge-state + world_rule_exception`
- 已有 prior-exception 之后，同一主体的后续 recap / repeat beat 现在会默认沿用既有 exception，并保留原始 `knowledge-state / exception` 首次节点，只把后续 beat 落成 `scene-only`
- `split-subjects` 现在也已有真实 direct closure：规则主体保留既有 exception，额外主体的新 knowledge-state 可以与 event / scene 一次性落库
- `mixed-subjects + local-signal` 现在也已有真实 review-only closure：planner、`workspace-status.json` 与 pipeline `auto` 会统一给出 `review-constraints`，并显式附带 `mixed-subjects-local-signal-review-only` 策略摘要
- `timeline_candidates[].participant_candidates` 现在也已成为 timeline merge 的正式参与者回填来源，因此这类 mixed-subject 样例不会再被 `repair-intake` 之类次级 blocker 抢优先级
- 对当前 `P0` 阶段而言，`World-Rule Exception Lifecycle` 已不再缺主处理矩阵：同主体 continuity、`split-subjects` direct closure、`mixed-subjects` review-only closure 三条路径都已有真实 workspace 样例

## 默认推进顺序

以后默认按这个顺序判断，而不是按灵感跳着做：

1. 先看哪条 acceptance track 还没真实闭环
2. 再找最小但真实的 workspace 样例去跑
3. 如果被卡住，先修脚本 / planner / apply
4. 只有脚本层确实解决不了，才回头补 consistency 微规则

## P1 Extension

P0 acceptance tracks 当前已作为收口基线保留。P1 不再新增一批泛化 track，而是沿着已验证主链路继续厚化执行层。

当前 P1 主线：

- `timeline merge` 执行层厚化：继续收紧 event / scene reuse、字段优先级、record 聚合、dedupe 后解释字段与 tri-state review hold
- deterministic review writeback 维护：constraints / reuse 两条路径都已落地，后续重点是保持 decision freshness、readiness hard gate 与 pipeline 路由一致
- archived / reuse 表达维护：继续让 archived report、首页和 review history 聚合页准确展示执行结果、剩余项类型与后续原因

当前不再把这些事当成 P0 blocker：

- 再补一条 relationship / knowledge / world-rule 微样例
- 把所有 review-only path 变成无人工确认的自动 apply
- 为 archived review 另造一层新事实源

## 当前结论

从顶层看：

- `P0` 已正式收口
- `constraints / reuse review writeback` 已落地
- 真实 workspace 已有 constraints 与 reuse 两条 review-only writeback 验收样例

下一阶段默认继续按 `P1：执行层厚化与 review 表达维护` 推进，优先处理 `timeline merge` 执行层厚化与 archived / reuse 剩余项表达，而不是回到 P0 收口审计。
