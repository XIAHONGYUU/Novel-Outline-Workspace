# Next Actions

最后更新：2026-07-05

## 现在优先做什么

### P1

1. 继续做厚 `timeline merge`  
   目标：把 `timeline_merge_inputs` 从“已可执行”继续推进成“更稳的执行层”。  
   重点检查：
   - 真实 workspace 里的场景/事件复用是否还有脆弱点
   - timeline 输入和 review writeback 之间如何对齐
   - 质量型字段如 location 是否需要更稳的确认落点
   当前进展：
   - `白塔档案室` 这类 compound location 当前已可直接进入 intake draft，不再退化成 `白塔`
   - `白塔议事厅 / 议事厅` 这类嵌套地点候选当前已收敛成更干净的单一候选
   - `update-existing-event` 当前在 chapter 漂移被确认时，会同步重排 `chronological_index`
   - `update-existing-scene` 当前已开始带最小地点兼容过滤：跨地点同标题 scene 不再直接误复用
   - `update-existing-event` 当前也已带最小地点兼容过滤：跨地点同标题 event 不再继续误命中旧记录
   - `update-existing-event` 当前已开始同步 draft 里的 `participant_ids`
   - `update-existing-scene` 当前已开始同步 draft 里的 `scene_pov / scene_character_ids`
   - `update-existing-scene` 当前已开始把 `scene_event_ids` 对齐到同一条已命中的旧 event
   - `update-existing-event / update-existing-scene` 当前都已把 `event_notes / scene_notes` 提前到 merge input 显式同步
   - `update-existing-scene` 当前已开始把旧的 `status` 收敛回默认 `planned` policy，而不再继续沿用旧值
   - notes 当前已不再只吃 `idea.content`，而是优先消费修过的 `draft.content`
   - `resolve-world-rule-by-delaying-event` 这条非 reuse 分支现在也已沿用同一条 `draft.content` 优先级，不再把旧 idea 描述带回延后后的 notes
   - `update-existing-scene` 当前已开始清掉与 draft 标题 / 地点不兼容的旧 `event_ids`，避免 scene reuse 单独 apply 时写出 stale 或悬空事件关联
   - `update-existing-scene` 当前在已命中 linked event 且 draft 没给新角色信息时，会优先向 event participants 对齐 `scene_pov / scene_character_ids`
   - `update-existing-event` 当前在已命中 linked scene 且 draft 没给新角色信息时，也会优先向 scene `characters` 对齐 `participant_ids`
   - linked scene / linked event 证据如果不唯一，planner 现在会显式保守：scene 不再继续保留歧义 `event_ids`，event 不再静默沿用旧 participants
   - 上述歧义 case 现在还会显式写出 warning，并进入 `unresolved_questions`，不再只靠空字段间接暴露
   - 上述歧义 case 现在还会产出结构化 `review_tokens`，并新增独立 `review` action 作为正式复核入口
   - `review_reuse.py` 现已把这条入口正式落成 `state/reuse-reviews/<idea-id>.json`
   - pipeline `auto` 现已能在有最新 consistency report 的前提下继续走到 `plan-merge -> review-reuse`，而不再被 `check-consistency` 原地卡住
   下一步重点：
   - `review-reuse` 现已补成 deterministic writeback：
     `review_reuse.py -> resolve_reuse_review.py -> apply-merge` 已有脚本级闭环
   - `review-reuse` 现已支持第二种正式终态：
     `rejected`
   下一步重点：
   - 检查 event / scene 复用时，是否还需要显式处理“空旧字段 vs. 新 draft 已有值”的优先级边界
   - 检查 `timeline_merge_inputs` 在同一条 plan 里是否需要继续收紧 id 唯一性，避免复核时出现语义不同但 id 相同的输入
   - 检查 `remaining_review_merge_inputs` 是否还需要继续细分“纯歧义待定”与“字段缺失待补”的剩余项类型

2. 维护 `deterministic review writeback`  
   当前进展：constraints / reuse 两条 review-only 主路径都已有第一版正式闭环。  
   已完成：
   - `state/constraint-reviews/<idea-id>.json` 已开始承载结构化 `decision`
   - `resolve_constraints_review.py` 已可写回 `approved-ready-merge-inputs`
   - pipeline `auto` 与 `apply-merge` 已能消费这类已确认的 ready merge inputs
   - `demo-workspace/idea-20260605-003` 已真实跑通 `review-constraints -> resolve_constraints_review -> apply-merge -> validate`
   - decision freshness 已从 `merge_plan.created_at` 收敛到 `merge_plan_fingerprint`
   - apply 后的 `constraint-review` 产物已收敛成 archive 语义，不再回显成 stale review
   - 第二种正式 decision 已补上：`rejected`
   - `state/reuse-reviews/<idea-id>.json` 现也已开始承载结构化 `decision`
   - `resolve_reuse_review.py` 已可写回 `approved-ready-merge-inputs / rejected`
   - pipeline `auto` 与 `apply-merge` 已能消费这类已确认的 reuse review decision
   - reuse review decision 现也已对齐 `merge_plan_fingerprint` freshness 与 archive 语义
   下一步重点：
   - 决定 pipeline 或视图层是否要为已 applied idea 单独做 review history 展示
   - 判断 reuse / constraints 两条 review history 是否需要统一展示结构
   - 判断 `rejected` 之外是否还需要第三种 review decision

3. 继续用真实 workspace 做工作区级验收  
   目标：保持 `P0` 已收口的前提下，验证 `P1` 新入口不会打断现有闭环。  
   当前验收对象：
   - `demo-workspace/`
   - `first-workflow-case/`
   重点看：
   - 是否都能保持清晰的 pending path
   - `review-constraints` 确认后能否自然续到 apply
   - apply 后的状态、视图、校验是否一致
   当前进展：
   - `P0` 已正式收口
   - `first-workflow-case/` 已完成首轮完整闭环
   - `demo-workspace/` 的 `idea-20260605-003` 已完成真实的 review writeback 验收：
     `review-constraints -> resolve_constraints_review -> apply-merge -> validate`
   - `review_constraints.py` 已能为这条 mixed-subject path 生成正式结构化报告
   - `resolve_constraints_review.py` + pipeline `apply-merge` 已能把同型 review-only path 从“人工确认”稳定续到真正 apply
   - `review-reuse` 的真实 workspace writeback 验收现已补齐：
     `demo-workspace/idea-20260705-001`
     `review-reuse -> resolve_reuse_review -> apply-merge -> validate`
   - constraints / reuse 两条 review-only 主路径当前都已有真实 workspace 级 writeback 样例

4. 补工作区级验收测试  
   目标：继续增加覆盖主流程成功路径的集成型测试，而不是继续主要堆规则微测例。  
   当前进展：
   - 已覆盖 `repair-intake -> plan-merge -> apply-merge` 的脚本级闭环
   - 已覆盖 `review-constraints` 的报告产出路径
   - 已覆盖 `plan-merge -> review-reuse` 的状态层 / orchestrator / report 产出路径
   - 已覆盖 `review-reuse -> resolve-reuse-review -> apply-merge`
   - 已覆盖 `review-reuse -> resolve-reuse-review(rejected)`

5. 收敛 skill 与 script 边界  
   目标：把确定性 `repair / merge / render` 动作继续沉到底层脚本，减少高层流程的模糊行为。

## 建议执行顺序

1. 先继续检查 `timeline merge` 的 event / scene reuse 判据与字段优先级
2. 再决定视图层是否要补 review history 展示
3. 然后判断 scene reuse 歧义的剩余待处理项是否需要结构化表达
4. 最后再判断是否真的需要第三种 review decision

## 顶层原则

接下来默认先补执行层，再补细节：

- 先看现有 review-only path 能不能自然续跑
- 再看是哪一个真实 workspace case 最适合补这条执行入口
- 不再默认因为某个微规则还能补，就把它提到顶层优先级

## 下一次开工时的最小切入点

如果只做一个任务，优先做这个：

`优先继续收紧 reuse path 里“空旧字段 vs. 新 draft 值”的优先级边界；如果这条线没有新缺口，就补 review history / 剩余待处理项的展示表达。`

## 这次方向调整的含义

- `P0` 已正式收口
- 接下来默认不再优先补新的中文句式微规则
- 只有当真实 workspace 闭环被明确卡住时，才回头修对应规则
- 当前更该补的，不再是新的 `world-rule / mixed-subjects` 微变体，而是把 `review-only` 终点继续推进成可写回、可续跑的正式执行层

## 暂时不要优先做

- 高交互前端
- 全自动语义重写章节摘要
- 复杂地图式展示
- 一次性扩太多 skill
