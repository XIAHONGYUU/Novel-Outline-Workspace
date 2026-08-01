# Next Actions

最后更新：2026-08-01

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
   - `update-existing-event / update-existing-scene` 当前在旧 `label / title` 为空时，也会优先回填 draft 标题，不再继续暴露假性 `missing_fields`
   - `update-existing-event` 当前在旧 `location` 为空时，也会优先回填 draft 地点，不再继续保留空地点残留
   - `update-existing-scene` 当前在旧 `pov` 为空、但旧 `characters` 仍稳定时，也会优先回填 POV，不再继续保留空视角残留
   - `update-existing-scene` 当前在旧 scene、自身 draft、linked event 三边都给不出稳定角色来源时，也会把 `scene_character_ids / scene_pov` 正式记成 `missing_fields`，不再继续把空角色、空 POV scene update 误当成可执行输入
   - `update-existing-scene` 当前在命中的 linked event 缺少参与者时，也不会再继续沿用旧 scene 的 `scene_character_ids / scene_pov`，而是显式退回缺字段
   - `update-existing-event` 当前在 draft 已给出明确参与者时，会优先使用 draft `participant_ids`，不会被 stale linked scene `characters` 覆盖
   - `update-existing-event` 当前在多条 linked scenes 指向同一 event、且角色集合一致时，会稳定复用这组角色，不会误报 `reuse-ambiguity-linked-scenes`
   - `update-existing-scene` 当前在匹配 linked event 时，也会优先使用新 draft 的 `scene_title`，不再让旧标题压过新的关联信号
   - `update-existing-event` 当前在 linked scene 标题过时、但 `event_id` 直连仍稳定时，也会优先回收这条 scene 的 `characters`，不再被旧标题挡掉
   - `update-existing-scene` 当前在旧 event 标题过时、但 `event_id` 直连仍稳定时，也会优先保住这条 `event_ids` 关联，不再被旧标题挡掉
   - 上述标题优先 / 直连回退 / 空值回填逻辑当前已开始收敛到共享 helper；其中 `event participants` / `scene event_ids` 两条复用决策已拆成独立 resolver，后续优先继续做策略层收口，不再主要靠局部 if 补边角
   - linked scene / linked event 证据如果不唯一，planner 现在会显式保守：scene 不再继续保留歧义 `event_ids`，event 不再静默沿用旧 participants
   - 上述歧义 case 现在还会显式写出 warning，并进入 `unresolved_questions`，不再只靠空字段间接暴露
   - 上述歧义 case 现在还会产出结构化 `review_tokens`，并新增独立 `review` action 作为正式复核入口
   - `review_reuse.py` 现已把这条入口正式落成 `state/reuse-reviews/<idea-id>.json`
   - pipeline `auto` 现已能在有最新 consistency report 的前提下继续走到 `plan-merge -> review-reuse`，而不再被 `check-consistency` 原地卡住
   - `remaining_review_merge_inputs` 当前已开始同时保留 reuse 歧义项与缺字段 blocked 项，不再只剩 scene / event 歧义
   - 每条 remaining input 当前也会显式带 `remaining_kind / remaining_summary`，方便归档后继续区分“纯歧义待定”与“字段缺失待补”
   - 历史 reuse archive 回填当前也会保留未消费的 warning-only / needs-review 输入，不再只回填 reuse 歧义和缺字段项
   - `workspace-status` 与 `recommended_next_step` 当前也已开始消费这层 remaining 类型：显式 `missing-fields` 会优先收敛到 `repair-intake`，纯 `reuse-ambiguity` 则继续停在 `review-reuse`
   - `scripts/review_reuse.py` 的非 JSON 输出当前也已开始直接列出 `ready / remaining` 输入与对应 `remaining_kind`
   - 历史 `applied` reuse review 在缺少 `remaining_review_merge_inputs` 时，当前也已能从旧 merge plan 自动回填，`demo-workspace/idea-20260705-001` 已重刷到这套新语义
   - `timeline_merge_inputs` 当前也已开始在整份 plan 内统一重编号，`issue-driven + default` 混合场景下不再出现重复的 story merge input id
   - 对同一 `event / scene record` 同时命中多条 timeline 相关 issue 的 case，planner 当前也已改成先按 record 聚合，再生成一条最终 merge input，而不再把 chapter / location 修正拆成多条半更新输入
   - 对同一 identity 的 merge input，后置 dedupe 当前也已升级到第一版冲突可解释合并：会并集 `review_tokens / resolves_issue_codes`，回填缺失 `apply_args`，为 scalar/list/dict 差异补 warning，并把 list/dict 差异写进 `apply_arg_conflicts`
   - `scene_event_ids / participant_ids` 这类复用歧义字段当前也已开始保留 review-hold 语义，不会因为另一条路径给了非空值，就自动清掉 `missing_fields`
   - `review_reuse()` 当前也已开始在重建最新 merge plan 后重新判定旧 decision 的 `apply_ready`，plan 指纹变化后不会继续沿用过期的 ready decision
   已完成：
   - `review-reuse` 现已补成 deterministic writeback：
     `review_reuse.py -> resolve_reuse_review.py -> apply-merge` 已有脚本级闭环
   - `review-reuse` 现已支持第二种正式终态：
     `rejected`
   下一步重点：
   - 决定 pipeline / orchestrator 是否也要继续按 `remaining_kind` 细分 reason，而不只看 `needs_reuse_review / needs_intake_repair` 两个粗状态
   - 检查 event / scene 复用 resolver 是否还要继续覆盖 `location / notes / title` 这类字段，避免主拼装函数里残留更多局部优先级判断
   - 检查 `event participants -> scene characters -> scene POV` 这条人物联动链是否还要继续收敛成共享 helper，而不再保持两套近似但不完全对称的局部优先级分支
   - 检查 `_dedupe_merge_inputs` 是否还需要把当前的第一版冲突可解释合并继续扩到更多 tri-state 字段；`participant_ids` 已补上，下一步重点转向是否还有别的字段也应具备同类 hold 语义
   - 同一 `record` 多 issue 聚合后的 merge input，当前也已开始显式写回 `source_issue_codes`，不再只保留单个 `source_issue_code`
   - `review-reuse` 报告层当前也已开始直接暴露 `source_issue_codes / apply_arg_conflicts / apply_arg_review_holds`，不再只停留在 merge input JSON
   - `merge plan HTML / workspace-status / orchestrator` 当前也已开始继续消费这批解释字段，plan 页和下一步建议不再只停留在泛化文案
   - pipeline 显式 `apply-merge` 当前已补 direct-ready fallback：没有 review decision 且整份 plan 都无 review / repair / override 风险时，才会消费直接可执行 inputs，不再误走 constraints review apply
   - pipeline 显式 `apply-merge` 当前也已拒绝同一 idea 同时存在 constraints/reuse apply-ready decision 的脏状态，避免静默消费其中一侧
   - direct-ready / review-ready 当前已收敛到共享判定，避免 reuse / constraints review 与 pipeline fallback 各自使用不同的 ready 条件
   - `views/index.html` 当前也已开始展示最近几条 archived review outcome，并带出剩余项摘要与首条结构化 detail reason
   - `views/review-history/index.html` 当前也已落成正式聚合页；archived review 不再只在首页显示一段摘要
   - `review-history` 当前也已补上到 archived review JSON / merge plan HTML / validation report 的 cross-link
   - archived review history 当前也已开始继续展示 `action_matrix` 的首条执行结果摘要，首页与聚合页都能直接看到这次归档把执行结果落到了哪一层
   - archived review history 当前也会直接展示首条剩余项的 `remaining_kind`，首页与聚合页不再只显示摘要文本
   - 首页与 consistency index 当前也会把已 applied/rejected idea 的历史 consistency report 标成 `archived applied / archived rejected`，避免把旧冲突误看成当前 pending gate
   - apply 成功后，磁盘上的 merge plan 当前也会同步切到 `status=applied` 并记录应用结果，样本工作区不再残留 idea 与 plan 状态不一致
   - 下一步检查这些解释字段是否还需要继续下沉到 archived report action rows / idea-level detail view，而不只停留在 index 摘要、执行结果、剩余类型与链接
   - 判断 `remaining_review_merge_inputs` 是否还需要在 `needs-review` 之下继续拆更细原因
   - `update-existing-scene` 的人物优先级当前已补一条防回归测试：draft 已给明确人物时，不会被 stale linked event participants 覆盖
   - `update-existing-event` 的人物优先级当前也已补对称防回归测试：draft 已给明确参与者时，不会被 stale linked scene characters 覆盖
   - `update-existing-event` 的 linked scene 复用边界当前也已补正例测试：多 linked scenes 只要角色集合一致，就不进入 reuse 歧义

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
   - constraints review archive 现也会保留 `remaining_review_merge_inputs`，旧归档缺字段时可从原 merge plan 回填
   - constraints review 的 `remaining_kind=missing-fields` 现也会被 status/orchestrator 路由到 `repair-intake`
   - `state/reuse-reviews/<idea-id>.json` 现也已开始承载结构化 `decision`
   - `resolve_reuse_review.py` 已可写回 `approved-ready-merge-inputs / rejected`
   - pipeline `auto` 与 `apply-merge` 已能消费这类已确认的 reuse review decision
   - reuse review decision 现也已对齐 `merge_plan_fingerprint` freshness 与 archive 语义
   - `apply_idea_merge()` 已补上入口层 readiness hard gate，直接传 `merge_input_id` 时也不能绕过 `missing_fields / review_tokens / apply_arg_conflicts / apply_arg_review_holds`；`warnings` 仍只阻止自动 fallback，不阻止人工显式 apply
   - `apply_idea_merge()` 直接消费 `merge_input_id(s)` 前也会拒绝 stale/missing merge plan，要求先重跑 `plan-merge`
   下一步重点：
   - 决定 pipeline 或视图层是否要为已 applied idea 单独做 review history 展示
   - 判断 reuse / constraints 两条 review history 是否需要统一展示结构
   - 判断 `rejected` 之外是否还需要第三种 review decision
   - legacy workspace 状态刷新当前已能把新增的默认 `view_files` key 合并回旧 `workspace-status.json`，后续只需继续检查真实样例状态是否还存在旧快照字段

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
   - 已覆盖同 identity merge input dedupe 的第一版冲突可解释合并
   - 已覆盖 merge plan 指纹变化后 reuse review ready decision 的失效路径
   - 已覆盖 `scene_event_ids / participant_ids` 这类复用歧义字段在 dedupe 后继续保留 review-hold 语义
   - 已覆盖 list 型 `apply_args` 冲突写入 `apply_arg_conflicts`
   - 已覆盖 merge plan HTML 展示结构化 `source_issue_codes / apply_arg_conflicts / apply_arg_review_holds`
   - 已覆盖 `workspace-status / orchestrator` 在 reuse-review 路径上继续带出更细的 `source issue` 原因
   - 已覆盖首页 `views/index.html` 展示 archived reuse review history
   - 已覆盖独立 `views/review-history/index.html` 展示 archived reuse review history
   - 已覆盖 `review-history` 页展示 archived review 的 cross-link
   - 已覆盖 archived review history 展示 `remaining_kind`
   - 已覆盖 reuse legacy archive 回填 warning-only remaining input
   - 已覆盖 applied/rejected 历史 consistency report 的 archived 展示语义
   - 已覆盖 apply 后 merge plan 状态同步为 `applied`
   - 已覆盖 reuse review partial apply 不会应用未批准的 scene reuse remaining input

5. 收敛 skill 与 script 边界  
   目标：把确定性 `repair / merge / render` 动作继续沉到底层脚本，减少高层流程的模糊行为。

## 建议执行顺序

1. 先继续检查 `timeline merge` 的 event / scene reuse 判据与字段优先级
2. 再检查 archived review 的结构化解释是否需要下沉到更细 detail 行
3. 然后判断 `needs-review` 剩余待处理项是否需要继续细分，尤其是 `demo-workspace/idea-20260705-001` 的 archived remaining scene reuse 歧义
4. 最后再判断是否真的需要第三种 review decision

## 顶层原则

接下来默认先补执行层，再补细节：

- 先看现有 review-only path 能不能自然续跑
- 再看是哪一个真实 workspace case 最适合补这条执行入口
- 不再默认因为某个微规则还能补，就把它提到顶层优先级

## 下一次开工时的最小切入点

如果只做一个任务，优先做这个：

`优先继续收紧 reuse path 里“空旧字段 vs. 新 draft 值”的优先级边界；如果这条线没有新缺口，就检查 archived review detail 行是否还需要继续下沉结构化解释。`

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
