# Workspace Acceptance Framework

最后更新：2026-06-03

这份文档不是记录单条规则，也不是记录单个样例细节。

它回答的是更上层的问题：

`P0 阶段到底按什么框架推进，而不是继续靠零散样例往前拱？`

## 核心思路

当前默认推进方式改成：

1. 先定义一组稳定的 `acceptance tracks`
2. 每一轮优先补齐某一条 track 的真实闭环
3. 只有某条 track 被真实 workspace 卡住时，才回头修脚本、规则或 planner

这意味着后续不再默认问：

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

待回答问题：

- 它是否仍应默认 `scene-only`
- 它是否需要附着到最近的 `reconciled` 节点解释
- 它何时会被视为新的状态变化而不是重复叙事 beat

当前状态：

- 未完成
- 这是当前最合适的下一条真实验收轨道

## 默认推进顺序

以后默认按这个顺序判断，而不是按灵感跳着做：

1. 先看哪条 acceptance track 还没真实闭环
2. 再找最小但真实的 workspace 样例去跑
3. 如果被卡住，先修脚本 / planner / apply
4. 只有脚本层确实解决不了，才回头补 consistency 微规则

## 当前结论

从顶层看，项目已经不缺“再多一个局部能力入口”。

当前更缺的是：

- 用统一框架追踪哪些工作区闭环已经收口
- 明确下一条该补的是哪一条 acceptance track
- 把零散样例推进，逐步沉成可复用的阶段框架

因此，下一步默认不是继续散着补细节，而是：

`优先补 Track 8：Post-Reconciliation Repeat Beat`
