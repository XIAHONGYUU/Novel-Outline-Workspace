# Project Status

最后更新：2026-07-28

## 项目定位

这个仓库在构建一个“小说大纲工作区”系统。

目标不是一次性生成大纲，而是把：

- `canon`
- `outline`
- `timeline`
- `inbox`
- `views`

放进一个可持续维护、可校验、可回滚的工作区流程里。

## 当前阶段

当前处于 `P1 执行层厚化与 review writeback 期`。

## 本轮推进

当前推进重点仍在 `timeline merge` 执行层稳定性，但这轮把 `review-reuse` 从 report-only 推进成了第一版 deterministic writeback，并已在真实 workspace 跑通首条验收样例：

- `review-reuse` 不再只是 merge plan 里的一条 `review` action
- `review_reuse.py` 现在会正式写出 `state/reuse-reviews/<idea-id>.json`
- `resolve_reuse_review.py` 现在已可把人工确认结果写回同一份 state
- pipeline `auto` 现在也能识别这类已确认 decision，并继续推荐 `apply-merge`
- `run_outline_workspace_pipeline.py --action apply-merge --execute` 现在已能直接消费 apply-ready 的 reuse review decision
- reuse review decision 当前同样按 `merge_plan_fingerprint` 而不是按重跑时间判断 freshness
- reuse review decision 被消费后，`state/reuse-reviews/<idea-id>.json` 会自动切成 archive 语义，而不再回显成 live review
- 对这类 idea，当前默认工作流已从 `plan-merge -> review-reuse` 继续推进成 `plan-merge -> review-reuse -> apply-merge`
- `demo-workspace/` 的 `idea-20260705-001 档案夜审` 已真实跑通：
  `ingest -> check-consistency -> plan-merge -> review-reuse -> resolve-reuse-review -> apply-merge -> validate`
- 这轮真实验收确认：
  - `approved-ready-merge-inputs` 已可在真实 workspace 中只消费非歧义 merge input
  - 被选中的 `timeline-merge-003` 会正式写回 `timeline/events.json`
  - 未被批准的 scene reuse 歧义会继续留在 review note 中，而不是被静默并入
  - apply 后 `state/reuse-reviews/idea-20260705-001.json` 会稳定归档成 consumed history
  - apply 后未被消费的 reuse 歧义输入现在也会继续保留成结构化 `remaining_review_merge_inputs`，而不再只埋在说明文字里
  - 同一条 reuse review 里如果同时存在“scene / event 复用歧义”和“默认 timeline 输入字段缺失”，两类剩余项现在也会一起保留在 `remaining_review_merge_inputs`
  - 每条剩余项当前都会显式带上 `remaining_kind / remaining_summary`，区分是 `reuse-ambiguity` 还是 `missing-fields`
  - `workspace-status` / `recommended_next_step` 现在也开始真正消费这些剩余项：纯 `reuse-ambiguity` 继续收敛到 `review-reuse`，而显式 `missing-fields` 则会改走 `repair-intake`
  - `scripts/review_reuse.py` 的非 JSON 输出现在也会直接列出 `ready_merge_inputs` 与 `remaining_review_merge_inputs`，并显示 `remaining_kind / remaining_summary`
  - 对历史 `applied` reuse review，如果旧 report 当时还没写出 `remaining_review_merge_inputs`，当前归档重建逻辑也会从旧 merge plan 自动回填 remaining 项，`demo-workspace/idea-20260705-001` 已重刷到这套新语义

同时，timeline merge 这条主线继续保持收紧：

- intake location 推断现在更接近“单一可执行候选”：
  - `白塔档案室` 这类 compound 室内地点不再退化成 `白塔`
  - `白塔议事厅` 这类完整地点也不再并行带出裸 `议事厅`
- `update-existing-event` 在 `timeline-order-conflict` 下不再只改 `reading_chapter`
- 如果事件被确认前移或后移章节，merge input 现在也会同步重排 `chronological_index`
- `update-existing-event / update-existing-scene` 当前在旧 `label / title` 为空、但新 draft 已有标题时，也会优先回填新标题，而不再继续把它们留成 `missing_fields`
- `update-existing-event` 当前在旧 `location` 为空、但新 draft 已有地点时，也会优先回填 draft 地点，而不要求先额外命中一条独立 `location-continuity-conflict`
- `update-existing-scene` 当前在旧 `pov` 为空、但 scene 自己已保留稳定 `characters` 时，也会优先从角色列表回填 POV，而不再继续保留空 POV 残留
- `update-existing-scene` 当前在匹配 linked event 时，也会优先吃新 draft 的 `scene_title`，而不再让旧 scene 标题压过新的匹配信号
- `update-existing-event` 当前在回收 linked scene `characters` 时，如果旧 scene 标题已经过时，但 `event_id` 直连和地点仍然稳定，也会优先沿用这条直接关联，而不再被旧标题挡掉
- `update-existing-scene` 当前在保留旧 `event_ids` 时，如果旧 event 标题已经过时，但 `event_id` 直连和地点仍然稳定，也会优先保住这条直接关联，而不再被旧标题挡掉
- 上述 `update-existing-*` 的标题优先 / 直连回退 / 空值回填规则，这一轮也已开始收敛到共享 helper，而不再继续散落在 event / scene 两边各写一份
- 其中 `event participants` 与 `scene event_ids` 两条最容易继续长分支的复用决策，当前已正式拆成独立 resolver helper，后续补规则时不必再直接改主拼装函数
- `timeline_merge_inputs` 当前也会在整份 plan 内统一重编号，`issue-driven + default` 混合场景下不再出现重复的 `timeline-merge-001`
- 对同一 `event / scene record` 同时命中多条 timeline 相关 issue 的 case，planner 现在也会先按 `(record_type, record_id)` 聚合，再生成一条最终 merge input，而不再把 chapter / location 修正拆成多条半更新输入
- 对同一 identity 的 merge input，后置 dedupe 当前也不再只是“选一个主项再丢次项字段”：
  - `review_tokens / resolves_issue_codes / source_patch_suggestion_ids` 现在会显式并集
  - `apply_args` 现在会保守回填缺失键，而不再静默吞掉另一条路径已经补齐的字段
  - 如果两条输入在同一个非空 scalar `apply_args` 键上冲突，当前也会显式写出 `dedupe-apply-args-conflict:*` warning
- `review_reuse()` 当前也会在重建最新 merge plan 后重新判定旧 decision 是否仍然 `apply_ready`
- 这意味着 reuse review 不会再因为旧 decision 还留在 state 里，就在 plan 已变化后继续被误当作可直接 `apply-merge`
- 这修掉了一条真实执行层裂缝：事件不会再出现“章节已改到第 3 章，但时间顺序仍停在旧 index”的半更新状态
- 对应回归测试已经补齐，因此这轮推进不只是样例修补，而是正式执行层行为收紧
- reuse review 当前也补上了两条脚本级闭环测试：
  - `review-reuse -> resolve-reuse-review -> apply-merge`
  - `review-reuse -> resolve-reuse-review(rejected)`
  - 以及两条新的执行层回归：
    - 同 identity merge input dedupe 不再静默丢 `apply_args / review_tokens / resolves_issue_codes`
    - merge plan 指纹变化后，旧 reuse review decision 会失效

## 当前战略判断

项目的主要矛盾已经变了。

前一阶段的重点是把：

- consistency-check
- merge plan
- exception / grouped summary
- claim / subject-scope

这些底层能力做厚，避免主链路还没站稳时就过早进入工作区验收。

但到当前这一轮，继续深挖中文句式级边界的收益已经开始下降。  
接下来更重要的不是“还能再补多少误判规则”，而是：

- `ingest -> check-consistency -> plan-merge -> apply-merge -> validate` 能不能在真实 workspace 里稳定闭环
- `plan_idea_merge / apply_idea_merge` 是否已经足够可执行
- `demo-workspace/` 与 `first-workflow-case/` 是否始终维持清晰的 pending path

因此上一阶段的默认工作重点调整为：

1. 先定义 `P0` 收口标准
2. 再做工作区级验收
3. 只有在真实闭环被卡住时，才回头修对应规则
4. 顶层上按固定 `acceptance tracks` 推进，而不再按零散样例堆进度

当前这条判断已经有了第一轮实证支撑：

- `docs/p0-closure-checklist.md` 已建立
- `first-workflow-case/` 已完成首轮完整闭环
- 这轮验收暴露出的核心问题，不再是新的句式误判，而是 `apply_idea_merge.py` 的 CLI 能力缺口与“多 merge inputs 如何顺滑消费”的执行层问题

第二轮工作区级验收也已经补上：

- `demo-workspace/` 已完成一轮 `pending -> consistency -> plan` 验收
- 暴露出的核心问题不是新的 consistency 规则缺口，而是 `warning-only / needs-info` case 的工作流提示不够具体
- `workspace-status.json` 与 pipeline `auto` 现在已经开始把这类 case 明确收敛到 `repair-intake` 路径，而不再泛化成继续 `plan-merge`
- `apply_idea_merge.py` 现已支持一次性消费多条 `merge_input_id`，`timeline / outline / canon` 的组合写入不再需要手工拼参数
- `update_intake_draft.py` 已补上“人类确认字段如何写回 intake draft”的确定性入口，`repair-intake -> plan-merge -> apply-merge` 现在已有脚本级闭环测试

第三轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260511-006` 已从 `repair-intake` 真正走到 `apply`
- 这轮验证表明：`repair-intake -> check-consistency -> plan-merge -> apply-merge -> validate` 已不只是临时测试工作区能跑通，真实样例工作区也能闭环
- 验收过程还顺手确认了一点：对这类 `character` beat，当前最稳的 direct apply 形态是落成 outline 场景，而不是勉强制造新的 canon 结构记录

第四轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260602-001` 已从 `ingest` 真正走到一次性 multi-input `apply`
- 这轮验证表明：重复传入 `--merge-input-id` 不只是 CLI 能力已经补齐，真实 workspace 里也能一口气把 `timeline / outline + canon knowledge-state` 落地
- 当前更真实的剩余缺口，已经开始从“多 input 能不能一起 apply”转向“`relationship / character` 类 idea 怎样更稳定地产生 canon 结构联动”

第五轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260602-002` 已从 `ingest` 真正走到一次性 `outline scene + canon relationship` 的 apply
- 这轮验证表明：`relationship` 类 idea 不只是能在测试里写入 `state/canon-index.json`，真实 workspace 里也能稳定生成结构化关系记录
- 当前更真实的剩余缺口，已经继续前移到“已有关系记录的后续状态转移、复用与冲突收敛”这一层，而不再是“关系能不能第一次落库”

第六轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260602-003` 已把“已有关系继续变化”收敛成真实的 `relationship-history-conflict`
- 这轮先暴露并修掉了一个 planner 缺口：同一条 relationship reuse input 不再重复出现在 plan 里，`canon` action 现在也会稳定带上对应 `merge_input_id`
- 但这轮也把更深一层的真实空白暴露出来了：对“第 6 章再次结盟”这类 same-state repeat beat，当前 `update-existing-relationship` 会倾向于把既有关系记录整体改写到新章节，这在语义上还不够稳

第七轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260602-003` 已从 `relationship-history-conflict` 真正走到 `apply`
- 这轮验证表明：对“第 6 章再次结盟”这类 same-state repeat beat，planner 现在会优先产出 `scene-only` 的 gate-resolving input，而不是直接改写第 5 章既有 `canon relationship`
- apply 后 `state/canon-index.json` 仍保留第 5 章的首次结盟记录，第 6 章则新增 narrative scene，随后 consistency 已清空，`demo-workspace/` 当前回到 `pending=0 / applied=7 / rejected=4`
- 当前更真实的剩余缺口已经继续前移到：什么情况下应当把“既有关系后续变化”落成新的 `canon relationship` 历史节点，而不只是 scene 或覆写旧节点

第八轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260602-004` 已从 `ingest` 真正走到一次性 `scene + new canon relationship history node` 的 `apply`
- 这轮验证表明：对“第 7 章决裂”这类真实状态转移，planner 现在会稳定追加新的 `canon relationship` 历史节点，而不是复用或覆写第 5 章旧的 `allied` 节点
- apply 后 `state/canon-index.json` 当前已形成 `allied@5 -> ruptured@7` 的正式关系链，`outline/scene-index.json` 也同步新增了第 7 章 scene，consistency / validator 均保持 `ok=true`
- 当前更真实的剩余缺口已经继续前移到：多段 relationship history chain 之后，后续 `reconciled / allied again` 这类再变化在真实 workspace 中应如何继续落库

第九轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260603-001` 已从 `ingest` 真正走到一次性 `scene + new canon relationship history node` 的 `apply`
- 这轮验证表明：在已有 `allied@5 -> ruptured@7` 的关系链上，后续 `reconciled@9` 也能稳定追加成新的正式 history 节点，而不会打断既有链条
- apply 后 `state/canon-index.json` 当前已形成 `allied@5 -> ruptured@7 -> reconciled@9` 的三段关系链，`outline/scene-index.json` 也同步新增了第 9 章 scene，consistency / validator 均保持 `ok=true`
- 当前更真实的剩余缺口已经继续前移到：在已有 `reconciled` 节点之后，未来的 `再次结盟 / 再次和解` 这类 repeat beat，是否仍应只落 scene，以及怎样避免与已有 history chain 冲突

第十轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260603-002` 已从 `relationship-history-conflict` 真正走到 `apply`
- 这轮验证表明：在已有 `reconciled@9` 节点之后，`再次和解@10` 这类 repeat beat 仍能稳定收敛成 `scene-only`，不会覆写第 9 章正式关系节点
- apply 后 `state/canon-index.json` 继续保持 `allied@5 -> ruptured@7 -> reconciled@9`，第 10 章只新增 narrative scene，随后 consistency / validator 仍保持 `ok=true`
- 这也意味着 relationship 这条 acceptance line 到当前阶段已经基本成型，顶层默认优先级应当开始转向下一条非 relationship 的 acceptance track

第十四轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260604-005` 已把 `world-rule exception` 的 first exception 跑成真实闭环：第 10 章 `林舟提前知道黑潮真正目标` 会一次性写入 `timeline / outline + canon knowledge-state + world_rule_exception`
- `demo-workspace/` 的 `idea-20260604-006` 已把 prior-exception continuity 跑成真实闭环：第 11 章 `林舟再次确认黑潮真正目标` 会沿用第 10 章既有 exception，只把后续 beat 收敛成 `scene-only`
- apply 后 `state/canon-index.json` 当前同时保留：
  - `know-char-protagonist-黑潮真正目标-ch10`
  - `rulex-rule-001-林舟-黑潮真正目标-ch10`
- rerun consistency 后，`idea-20260604-006` 不再残留 `world-rule-conflict` 或 `knowledge-state-conflict`，只会显式保留 `world-rule-exemption-applied`
- 这说明 `World-Rule Exception Lifecycle` 已经不再停留在 tests / planner explainers，而是已经有了真实的 first exception 与 prior-exception continuity 两段闭环
- 当前更真实的剩余缺口已经继续前移到：已有 exception chain 之后，`mixed-subject / split-scope` case 应如何稳定收口，而不误共用同一条 exception 记录

第十五轮真实 workspace 验收也已经推进：

- `demo-workspace/` 新增了 `idea-20260605-002 双人同章知道黑潮目标`
- 这条 idea 当前不会被直接 apply，而是被明确收敛成 `review-constraints`
- `check-consistency` 会稳定写出：
  - `exception_scope=prior-exception-split-subjects-claim-match`
  - `exception_subject_scope=split-subjects`
- `plan_idea_merge` 会把 constraints explainer 明确标成 `needs-review`
- `workspace-status.json` 与 orchestrator 现在也不再把这类 case 泛化成 `plan-merge`，而是显式推荐：先复核 `world-rule / exception` 主体范围
- `demo-workspace/` 当前因此变成一个更真实的状态：不是“没有 pending idea”，而是“存在一条定义清晰的 pending review path”
- 这说明 Track 10 的剩余缺口已经不只是“有没有样例”，而是“这条 split / mixed subject review path 最终要如何收口成正式处理策略”

第十六轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260605-002 双人同章知道黑潮目标` 已从 `review-constraints` 真正走到 `apply`
- planner 现在会对 `prior-exception + split-subjects + claim-match + narrative targets` 走一条更窄但可执行的策略：
  - 保留规则主体既有 `world_rule_exception`
  - 不再回写规则主体旧的 `knowledge-state`
  - 为额外主体生成新的 chapter-scoped `knowledge-state`
  - 同时继续把 event / scene 正式落库
- apply 后 `state/canon-index.json` 当前同时保留：
  - `rulex-rule-001-林舟-黑潮真正目标-ch10`
  - `know-char-shijie-黑潮真正目标-ch11`
- `demo-workspace/` 当前已回到 `pending=0 / applied=16 / rejected=6`
- 这说明 Track 10 的剩余空白已经继续收缩：`split-subjects` 不再只是 review path，而是已经有了真实 direct closure；当前真正还没定死的，只剩 `mixed-subjects`

第十七轮真实 workspace 验收也已经推进：

- `demo-workspace/` 新增了 `idea-20260605-003 林舟和师姐都知道黑潮真正目标`
- 这条 idea 当前会稳定命中：
  - `exception_scope=prior-exception-mixed-subjects-local-signal`
  - `exception_subject_scope=mixed-subjects`
  - `exception_match_mode=local-signal`
- 当前 planner 仍不会直接 apply 它，而是显式把 constraints explainer 标成 `needs-review`
- 同时这轮也补了一条执行层小修正：`timeline merge` 现在会从 `timeline_candidates[].participant_candidates` 回填 `participant_ids`，所以这条真实 mixed-subject 样例不再被 `repair-intake` 抢优先级，而是稳定落到 `review-constraints`
- `demo-workspace/` 当前因此变成 `pending=1 / applied=16 / rejected=6`
- 这说明 Track 10 当前已经不缺 mixed-subject 样例，剩余问题已经继续收缩成：这条 mixed-subject review path 最终要不要保留为 review-only，还是也拆出一条更窄的局部直通策略

第十八轮真实 workspace 验收也已经推进：

- `demo-workspace/idea-20260605-003` 当前已不再只是“一个待决定的 mixed-subject 样例”，而是被正式收口成：
  - `exception_scope=prior-exception-mixed-subjects-local-signal`
  - `recommended_action=review-constraints`
  - `review_policy=mixed-subjects-local-signal-review-only`
- planner、`workspace-status.json` 与 pipeline `auto` 现在都会显式给出同一条策略摘要：这类 `mixed-subjects + local-signal` 当前默认只做 review，不自动扩写 exception 或 canon knowledge-state
- `timeline merge` 同时已支持从 `timeline_candidates[].participant_candidates` 回填 `participant_ids`，因此这条真实 mixed-subject 样例不再被 `repair-intake` 抢优先级，而是能稳定停在真正的 constraints review path
- 这说明 `World-Rule Exception Lifecycle` 到当前阶段已经具备完整的主处理矩阵：
  - same-subject continuity：`scene-only`
  - `split-subjects + claim-match + narrative targets`：direct closure
  - `mixed-subjects + local-signal`：review-only closure
- 顶层上，当前下一步不该继续横向补更多 `world-rule / mixed-subject` 微变体，而应转向把 `review-constraints` 作为正式终点继续做厚，并据此检查 `P0` 是否已经接近收口

第十九轮真实 workspace 验收也已经推进：

- `review_constraints.py` 已补成独立脚本入口，不再只依赖 orchestrator 的一句推荐语
- `state/constraint-reviews/<idea-id>.json` 现在会为 `review-constraints` 路径写出正式结构化报告，显式包含：
  - `review_policy`
  - `review_policy_summary`
  - `review_checklist`
  - `ready_merge_inputs`
  - `action_matrix`
- `demo-workspace/idea-20260605-003` 现在不仅会停在 `review-constraints`，而且已经能稳定产出一份可回看的正式 review 报告
- 这说明 `review-constraints` 已不再只是“状态层的推荐动作”，而是开始具备正式工作流终点所需的可追踪产物
- 顶层上，当前默认下一步已继续前移到：做一次 `P0` 收口审计，把哪些 review-only path 属于阶段内够用、哪些已知限制留到下一阶段，统一写清楚

第二十轮顶层收口审计也已经推进：

- `docs/p0-known-limitations.md` 已正式建立

第二十一轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260705-001 档案夜审` 已把 `review-reuse` 真正跑成真实工作区闭环
- 这轮验证表明：reuse review writeback 不再只停留在 tests / 临时工作区，而是已经能在正式 demo workspace 中稳定消费部分 ready merge inputs
- apply 后 `timeline/events.json` 当前保留了“地点更具体的旧 event 前移到第 13 章”这一决策，而带双 event 关联的 scene reuse 歧义仍保持未自动并入
- `workspace-status.json` 与 validator 当前仍保持 `pending=0 / applied=18 / rejected=6 / ok=true`
- 这说明 `review-only` 主路径当前都已有真实 workspace writeback 验收，下一步默认优先级应继续前移到 timeline reuse 判据和 review history 表达的一致性
- `P0` 当前可接受的 review-only path、人工确认点与结构表达边界已被集中列出
- `docs/p0-closure-checklist.md` 里“边缘句式已知限制可以列出来”这一项现在已可正式勾掉
- 这意味着当前阶段不再只是“感觉上已经够用”，而是已经把阶段内接受哪些限制写成了可审计清单
- 顶层上，下一步默认不再是继续补 `mixed-subjects` 或 `review-constraints` 入口，而是判断：在这份已知限制清单成立的前提下，`P0` 是否已经可以正式宣布收口，还是还缺最后一条 deterministic review writeback

第二十一轮正式收口判断也已经完成：

- `first-workflow-case/` 当前仍保持 `pending=0 / applied=1 / validate ok`
- `demo-workspace/` 当前虽然仍有 `pending=1`，但这条 pending 已被正式归类成阶段内接受的 `review-only` path，而不是主链路缺口
- `python3 -m unittest discover -s tests -v` 当前仍为 `145` 个测试，`OK`
- `docs/p0-known-limitations.md` 已明确写出：`review-constraints` 当前可以以“报告 + 人工决策”形态视为阶段内够用
- 因此当前不再需要把 `deterministic review writeback` 视作 `P0` 最后一项 blocker

结论：

- `P0` 正式收口
- 下一阶段转入 `P1 执行层厚化与 review writeback`

第二十二轮 `P1 deterministic review writeback` 也已经推进：

- `mixed-subjects + local-signal` 这类 review-only path 当前已不再只能停在报告层
- 对 `demo-workspace/idea-20260605-003` 同型 case，人工确认现在可以稳定写成：
  - `decision.status=approved-ready-merge-inputs`
  - `decision.selected_merge_input_ids=[...]`
  - `decision.resolution_note=...`
- 只要这份决策仍对齐当前 merge plan，状态层就不会再把这条 idea 误打回 `repair-intake` 或重复停在 `review-constraints`
- pipeline 执行层现在可以继续自动消费这些已批准的 ready inputs，把 review-only path 自然续到真正的 `apply`
- `python3 -m unittest discover -s tests -v` 预计将从 `145` 个测试增长到 `146` 个测试

第二十三轮真实 workspace 验收也已经推进：

- `demo-workspace/idea-20260605-003` 已不再只停在 `review-constraints`
- 这条 mixed-subject review-only case 现在已经真实跑通：
  - `review-constraints`
  - `resolve_constraints_review`
  - `apply-merge`
  - `validate`
- 验收过程中还暴露并修掉了一个执行层缺口：
  - `decision` 不能再拿 `merge_plan.created_at` 当 freshness token
  - 否则同一条 merge plan 只要隔几秒重跑，就会把已确认 decision 误判成失效
  - 当前已改成 `merge_plan_fingerprint`，按计划内容而不是按重跑时间判断 decision 是否仍可继续消费
- `demo-workspace/` 当前已变成：
  - `pending=0`
  - `applied=17`
  - `validate ok`
- 这说明 `deterministic review writeback` 已不再只是测试工作区里的脚本级闭环，而是已经在真实长期样例工作区中完成了一次端到端验收

第二十四轮执行层收尾也已经推进：

- `constraint-reviews/<idea-id>.json` 在 apply 后不再回显成一个“看起来还卡在 stale gate / needs-review”的 live report
- 当前已新增：
  - `review_state`
  - `review_status_summary`
  - `applied_result`
- 当一条 review decision 已被真正消费后，report 现在会稳定收敛成 archive 语义：
  - `review_required=false`
  - `review_state=applied`
  - `ready_merge_inputs=[]`
  - `blocked_merge_inputs=[]`
  - `consistency_gate.status=consumed`
- 这轮收尾意味着：`review writeback` 的第一版不只会写回并 apply，也已经补齐了 apply 后的状态表达，不再把已完成 case 误展示成待继续处理

第二十五轮 `review decision matrix` 也已经推进：

- `resolve_constraints_review.py` 当前不再只支持 `approved-ready-merge-inputs`
- 第二种正式 decision 已补上：`rejected`
- 这意味着同一类 `review-only` path 现在至少已有两种确定性收口：
  - 确认后继续 apply 已批准的 ready inputs
  - 确认后不进入 apply，并把 idea 正式移出 pending path
- 对 `rejected` 路径，report 当前也已对齐到 archive 语义：
  - `review_state=rejected`
  - `consistency_gate.status=closed`
  - `rejected_result=...`
- 这说明 `deterministic review writeback` 的第一版已经不再只是“单一路径直通 apply”，而是开始具备最小可用的 decision matrix

第二十六轮 `timeline merge` 执行层厚化也已经推进：

- 当前已补一条真实 location 推断缺口：
  - `白塔档案室` 这类 compound 室内地点不再退化成 `白塔`
- 同时也收掉了一条低质量噪音：
  - `白塔议事厅` 这类完整地点不再继续并行产出裸 `议事厅`
- 这意味着 intake / timeline merge 当前在 location 上已经更接近“单一可执行候选”而不是“一长串长短混杂的碎片”
- 这一轮还补了对应回归测试，因此这不再只是对单个样例的临时修补，而是已经进入正式执行层行为

第二十七轮 `event reuse` 执行层也已经推进：

- `update-existing-event` 现在不再只改 `reading_chapter`
- 如果一条正式事件因 `timeline-order-conflict` 被确认前移或后移章节，
  当前 merge input 也会同步重排 `chronological_index`
- 这修掉了一条真实执行层裂缝：
- 以前事件可能“挂在第 3 章”
- 但时间顺序仍停在旧的 `chronological_index=7`
- 当前这条路径已补上回归测试，因此 event reuse 不再只是在章节层面看起来更新了，而是时间线排序也一起对齐

第二十八轮 `scene reuse` 判据也已经推进：

- `update-existing-scene` 当前不再只按标题复用旧 scene
- 如果旧 scene 从 notes 里能稳定抽到地点，而 intake draft 的地点与它明显冲突，
  `consistency` 现在会直接跳过这条旧 scene，不再把它误当成同一条记录
- 同时，`白塔 / 白塔议事厅` 这类宽窄兼容地点仍然允许继续命中同一条旧 scene
- 这也顺手收掉了一条次级误判：
- `knowledge-state-conflict` 不再把跨地点的同标题 scene 误当成“更晚才知道”的正式旧记录
- 当前这条路径已补上正反两组回归测试，因此 scene reuse 现在开始具备最小地点判别，而不再完全依赖 title-only matching

第二十九轮 `event reuse` 判据也已经推进：

- `update-existing-event` 当前同样不再完全依赖 title-only matching
- 如果 intake draft 的地点与旧 event 的地点明显不兼容，
  `consistency` 现在会直接跳过这条旧 event，不再继续产出：
  - `timeline-order-conflict`
  - `location-continuity-conflict`
  - 以及对应的 `update-existing-event`
- 但 `白塔 / 白塔议事厅` 这类宽窄兼容地点，仍然允许继续命中同一条旧 event，并保留必要的 drift 提示
- 这意味着 event reuse 现在也有了和 scene reuse 对齐的最小地点过滤，不会再因为“同标题”就把跨地点事件硬并成一条
- 当前这条路径同样已补上正反两组回归测试，因此 `event / scene reuse` 的第一层地点判据已经基本对齐

第三十轮 `reuse input` 写入层也已经推进：

- `update-existing-event` 当前不再只搬章节和地点
- 如果 draft 本身已经给出更完整的参与者信号，merge input 现在会直接同步到 `participant_ids`
- `update-existing-scene` 当前也不再只搬章节
- 如果 draft 已能稳定推断 POV 与出场角色，merge input 现在会同步写入：
- `scene_pov`
- `scene_character_ids`
- 这意味着 `event / scene reuse` 现在开始不只会“命中旧记录”，也会把新 intake 里已经确认过的结构化信息真正带进 apply
- 当前这条路径已补上对应回归测试，因此复用输入不再只是章节重挂，而是开始具备最小字段同步能力

第三十一轮 `scene-event relink` 也已经推进：

- `update-existing-scene` 当前不再只同步 chapter / POV / characters
- 如果同一条 idea 也稳定命中了一个地点兼容的旧 event，
  scene merge input 现在会把 `scene_event_ids` 直接对齐到那条已有 event
- 这修掉了一条真实执行层空洞：
  - 以前 scene 虽然会复用旧记录
  - 但 `event_ids` 可能仍为空，或者继续停在旧的弱关联状态
- 现在复用 scene 已经能和同一条复用 event 保持结构化联动，而不再只是两条彼此独立的 update
- 当前这条路径已补上回归测试，因此 `scene -> event` 关联在复用路径上也开始具备最小自动对齐能力

第三十二轮 `notes sync` 也已经推进：

- `update-existing-event` 当前不再只在 apply 阶段隐式回写 idea content
- merge input 自身现在就会显式带上 `event_notes`
- `update-existing-scene` 同样也会显式带上 `scene_notes`
- 这意味着复用路径上的 notes 同步不再只是执行层的兜底行为，而是已经提升到 planning 层的明确写入意图
- 当前这条路径已补上回归测试，因此 `participants / POV / event_ids / notes` 这几类主要复用字段现在都已进入可见、可测试的 merge input 结构

第三十三轮 `scene status sync` 也已经推进：

- `update-existing-scene` 当前不再继续沿用旧 scene 的 `status`
- merge input 现在会优先吃当前默认 scene policy，对复用场景显式回到 `planned`
- 这修掉了一条轻量但真实的旧噪音：
  - 以前老 scene 如果残留 `draft` 一类状态
  - 复用时会被原样带进新的正式 merge
- 现在 `scene_status` 也已经和 `POV / event_ids / notes` 一样，进入了明确、可测试的同步路径
- 当前这条路径已补上回归测试，因此复用 scene 的主要结构字段当前都已开始受统一 policy 约束

第三十四轮 `draft content precedence` 也已经推进：

- `update-existing-event / update-existing-scene` 当前在构造 notes 时，不再默认只吃 `idea.content`
- 如果 intake draft 的 `content` 已经被人工修正，merge input 现在会优先使用：
  - `draft.content`
  - 只有 draft 没内容时，才退回 `idea.content`
- 这修掉了一条真实执行层断层：
  - 用户虽然已经在 intake repair 里改过描述
  - 但复用路径上的 notes 仍可能继续写回旧的 inbox 原文
- 现在 notes 同步不只显式化了，而且开始真正消费修过的 draft 内容，和 `repair-intake -> plan-merge -> apply-merge` 的闭环语义对齐
- 当前这条路径已补上回归测试，因此复用写入层已经开始把“修过的 intake 文本”当成正式输入，而不再把它当旁路信息

当前测试状态：

- `python3 -m unittest discover -s tests -v`
- `160` 个测试，`OK`

已经完成的方向：

- 工作区模板与初始化
- idea inbox 录入
- workspace 状态刷新
- 基础校验
- 基础 HTML 视图渲染
- merge plan / apply merge 基础流
- orchestrator 入口
- idea intake 第二层草案推断
- idea-level consistency check 可用版
- gate-aware merge
- world-rule 多策略 merge input
- graph-aware consistency 豁免
- formal intake backfill / repair 入口
- confirmed intake patch 入口
- domain-specific merge plan explainers
- `needs-info` pending path 显式化：当 merge plan 缺少 `chapter_number` 等关键字段时，状态层与 orchestrator 已会优先提示 `repair-intake`
- multi-input apply 入口：CLI 与底层 `apply_idea_merge` 已支持一条 idea 一次性消费一组 merge inputs
- `demo-workspace/` 已补齐真实 multi-input apply 样例，当前 pending 已清空，pipeline `auto` 已回到 `validate`
- `demo-workspace/` 已补齐真实 relationship 样例，`state/canon-index.json` 中已有正式 `relationships` 记录
- relationship reuse planner 已去重并修正 action 绑定；same-state repeat beat 现已稳定落成 `scene-only` 闭环
- 真实 relationship state transition 现已能稳定追加新的 `canon relationship` 历史节点
- 多段 relationship history chain 现已能在真实 workspace 中稳定扩展到 `reconciled`
- post-reconciliation repeat beat 现也已在真实 workspace 中收口为 `scene-only`
- `knowledge-state` 现也已补齐真实 lifecycle 样例：同主体 later recap 会收敛成 `scene-only`，新主体 later learns 会追加新的 chapter-scoped knowledge-state 节点
- `world-rule exception` 现也已补齐真实 lifecycle 的前两段：`first exception` 与 `prior-exception continuity`
- `world-rule exception` 现也已补齐真实的 `split-subjects` direct closure 样例；规则主体既有 exception 与额外主体的新 knowledge-state 已能在真实 workspace 中同时落库
- `world-rule exception` 现也已补齐真实的 `mixed-subjects` review-only closure；状态层、planner 与 orchestrator 已能稳定给出显式 `review_policy`
- `review-constraints` 现也已开始写出正式结构化产物，不再只是临时推荐动作
- `P0` 已知限制清单现也已正式落地；主链路、acceptance tracks 与阶段边界都已有可审计文档
- 顶层上，relationship、knowledge-state 与 `world-rule exception` 三条主要 acceptance line 当前都已阶段成型；`P0` 已正式收口，下一步默认应转向 `P1` 的执行层厚化
- 这条推进路线现已在 `docs/workspace-acceptance-framework.md` 里收敛成显式 framework，避免顶层继续被零散 case 主导

## 已完成能力

### 1. 工作区骨架

- `scripts/init_workspace.py`
- `workspace-template/`
- `src/novel_outline_workspace/workspace.py`

### 2. idea 录入主流程

- `scripts/ingest_idea.py`
- 写入 `state/idea-log.json`
- 写入 `inbox/*.md`

### 3. idea intake 推断

已支持自动推断：

- `kind`
- `tags`
- `target_files`
- `suggested_domains`
- `chapter_hints`
- `location_candidates`
- `character_mentions`

并自动生成：

- `state/intake-drafts/<idea-id>.json`
- `views/intake-drafts/<idea-id>.html`

### 4. 基础校验与渲染

- `scripts/validate_workspace.py`
- `scripts/check_idea_consistency.py`
- `scripts/render_workspace_views.py`
- `scripts/refresh_workspace_status.py`

### 5. merge 基础流

- `scripts/plan_idea_merge.py`
- `scripts/apply_idea_merge.py`
- `scripts/run_outline_workspace_pipeline.py`
- merge 默认受 consistency gate 约束
- `plan_idea_merge` 的 `proposed_actions` 已升级为更接近执行层的 domain explainers

### 6. consistency-check 增强

已支持：

- claim-level `knowledge-state` 提取
- `knowledge-state conflict` 的非同标题匹配
- 当同一知情事实同时存在更早与更晚记录时，优先只报告更早冲突，避免重复告警
- `title-based drift` 对带括注 / 副标题的扩写事件名和场景名开始支持安全的部分匹配
- `knowledge object` 开始支持有限的同义归一与对象家族匹配，并压缩公共前缀导致的误报
- `world-rule conflict` / `world_rule_exception` 开始复用结构化 `knowledge_claims` 做 subject/object 协同匹配
- 单条 idea 中的多条 `knowledge_claims` 开始能稳定抽出，并按 rule 精确回流到 world-rule merge input
- 多条 `world-rule` 同时命中时，`proposed_actions` 开始先给出 constraints 级分组摘要，再保留每条 rule 的具体输入
- constraints 分组摘要开始直接列出每条 rule 的策略、direct/override 状态、目标文件，以及按 direct / review 拆开的跨 domain impacts
- constraints 分组摘要开始区分 `shared-subject` 与 `split-subjects`，避免多主体 world-rule 被误看成可共用同一条 exception 解释
- 同一主体下如果标题 object 和正文 object 同时落成 claim，且前者只是同一家族的泛化说法，claim 层开始优先保留更具体那条
- 多主体句子里如果前后主体分别对应不同 object，claim 提取开始按主体窗口截断，避免把后一个主体的 object 串回前一个主体
- `identity` family 里的近义 object 开始按更具体 claim 收敛，例如“首领身份 / 组织首领是谁”会优先保留后者
- `leak / same-camp / separate-camp` family 里的近义 object 也开始按更具体 claim 收敛，例如“有人泄密 / 议会有内鬼”“他们是一路人 / 议会和黑潮是同一阵营”“他们不是一路人 / 议会和黑潮不是同一阵营”会优先保留后者
- 在 `same-camp / separate-camp` family 内，如果只是“同一阵营 / 一伙人 / 一路人”这类 wording 差异，claim 层也开始优先保留更标准表达
- cross-family claim 当前会继续保持分离，避免把同一主体在同章知道的两类不同事实误收敛到一条
- 如果同章已经有正式 event / scene / canon `knowledge-state` 记录，future duplicate 不再把当前 idea 误报成知情点前移
- `world-rule` 在缺少 `knowledge_claims` 时，也开始按主体局部窗口抽取 knowledge signal；同章 exception 的同义 object 不再只靠整句字面命中，mixed-subject 句子里别人的 object 也不会误触发当前 rule
- consistency report 开始显式输出 `world-rule-exemption-applied`，merge plan 在 clean gate 下也会补一条 exemption explainer，说明这是“已落地豁免”而不是“没有命中规则”
- 对已落地的 world-rule exception，grouped summary 开始区分 `direct` 沿用和仍需 `review` 的主体范围；如果同一 idea 同时存在冲突 rule 和已豁免 rule，也会收敛进同一条 constraints 摘要
- 如果多条 `world-rule conflict` 之间共享同一批 context，grouped summary 现在会先提一条 `shared-conflict-context`，把公共 `domains / targets` 上提
- 如果多条 `world-rule conflict` 连动作层也完全相同，grouped summary 现在还会再提一条 `shared-conflict-actions`，把公共 `direct/review impacts` 与 `write_shapes` 上提
- 如果只有一部分 conflict rule 共享同一套动作签名，grouped summary 现在也会按 `rules=...` 再提 subset 级 `shared-conflict-actions`
- 如果同一批 conflict 连策略、direct/override 和主体范围也完全一致，grouped summary 现在还会再提一条 `shared-conflict-structure`
- 如果策略或主体不同、但 `direct / override / subject_scope` 仍重复，grouped summary 现在也会按 `rules=...` 再提一条 `shared-conflict-structure-tokens`
- 如果同一批 mixed conflict 子组同时共享结构 token 和 `strategies/subjects + domains/targets`，grouped summary 现在也会把这两层局部描述合成一条 `shared-conflict-rule-metadata`
- 如果同一批 mixed conflict 子组同时共享 `shared-conflict-rule-metadata` 和 action fields，grouped summary 现在也会再合成一条 `shared-conflict-rule-summary`
- 如果当前批次的全局 conflict context 和全局 conflict actions 同时存在，grouped summary 现在也会把 `shared-conflict-context + shared-conflict-actions` 合成一条顶层 `shared-conflict-summary`
- 如果这条顶层 conflict summary 对应的全部 rule 结构也完全一致，grouped summary 现在还会继续把 `shared-conflict-summary + shared-conflict-structure` 合成一条 `shared-conflict-overview`
- 如果 mixed conflict 子组里 `strategies=` 或 `subjects=` 仍重复，grouped summary 现在也会按 `rules=...` 再提一条 `shared-conflict-rule-tokens`
- 如果同一批 mixed conflict 子组同时共享 `strategies/subjects` 和 `domains/targets`，grouped summary 现在也会把这两条局部描述行合成一条 `shared-conflict-rule-details`
- 如果 mixed conflict 子组里 `domains=` 或 `targets=` 仍重复，grouped summary 现在也会按 `rules=...` 再提一条 `shared-conflict-rule-context`
- 如果 mixed conflict 子组里 `direct_impacts=` 或 `review_impacts=` 仍重复，grouped summary 现在也会按 `rules=...` 再提一条 `shared-conflict-rule-impacts`
- 如果不同 conflict 子组虽然整体签名不同，但还共享同一批 `write_shapes`，grouped summary 现在也会按 `rules=...` 再提一条 `shared-conflict-write-shapes`
- 如果同一批 mixed conflict 子组同时共享 `impacts` 和 `write_shapes`，grouped summary 现在也会把这两条局部 action 行合成一条 `shared-conflict-rule-actions`
- 如果某条 conflict / exemption rule 行里的 `impacts=` 或 `write_shapes=` 只是 `direct_/review_` 桶的并集，grouped summary 现在也会直接省掉这层泛化字段，避免同一 token 在明细行里重复两次
- 如果 `shared-exemption-base` 已经承载了公共 `domains / targets / reuse-exception impacts`，`shared-exemption-review` 现在也会自动扣掉这部分 base token，只保留 review 专属补充
- 如果多条 exemption 共享同一批 `subject_scope / exception_scope_*` 元信息，grouped summary 现在也会按 `rules=...` 再提一条 `shared-exemption-scope`
- 如果多条 exemption 共享同一批 `direct / review / subjects` 元信息，grouped summary 现在也会按 `rules=...` 再提一条 `shared-exemption-rule-tokens`
- 如果某批 exemption 行在扣掉共享 token 后只剩 exception id，grouped summary 现在也会再提一条 `shared-exemption-links`，把这些壳行收成一条映射
- 如果同一 rule 同时命中更早的 prior exception 和当前章 same-chapter exception，consistency / merge 现在也会优先选当前章那条，避免把本可 direct 的 case 误降成 review
- relationship repeat hint 现在也开始覆盖 `再度` 这类常见重启关系 wording，减少“再度结盟 / 再度和解”被误报成 future drift
- relationship state / repeat 词表现在也开始覆盖 `重归于好`、`反目` 这类常见关系表达，减少 reconciliation / rupture 场景的漏判与误报
- relationship state / repeat 词表现在也开始覆盖 `冰释前嫌`、`翻脸` 这类常见关系表达，进一步补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现在也开始覆盖 `破镜重圆`、`闹翻` 这类常见关系表达，继续补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现在也开始覆盖 `言归于好`、`彻底翻脸` 这类常见关系表达，继续补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现在也开始覆盖 `握手言和`、`恩断义绝` 这类常见关系表达，继续补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现在也开始覆盖 `重修旧好`、`撕破脸` 这类常见关系表达，继续补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现在也开始覆盖 `一笑泯恩仇`、`反目成仇` 这类常见关系表达，并处理 `反目` 前缀长短词的命中顺序
- relationship state / repeat 词表现在也开始覆盖 `化干戈为玉帛`、`撕破脸皮` 这类常见关系表达，并处理 `撕破脸` 前缀长短词的命中顺序
- relationship state / repeat 词表现在也开始覆盖 `尽释前嫌`、`反目为仇` 这类常见关系表达，并继续补齐 `反目*` 前缀长短词的命中顺序
- conflict 侧成对出现的 `timeline / outline` 章节改写说明，现已开始收敛成跨域 `story-beat:*` token，减少不同子组之间重复的 scene/event 文案
- conflict 侧 `constraints:rewrite-cutoff + story-beat:carry-forward`，现已开始收敛成跨域 `cutoff-resolution:carry-forward`
- conflict 侧 `timeline / outline` 章节改写直写路径，现已开始收敛成跨域 `delay-resolution:rewrite-chapter`
- conflict 侧成对出现的 exception note 写入说明，现已开始收敛成跨域 `exception-note:record`，减少重复的 canon / constraints review write-shape 文案
- conflict 侧 `resolve-world-rule-by-updating-cutoff / resolve-world-rule-by-delaying-event` 的 impact，现已开始收敛成跨域 `cutoff-resolution:update-placement / delay-resolution:update-placement`
- 如果某条 conflict rule 已被这些共享行完整覆盖，grouped summary 现在也不会再留空的 `rule-xxx:` 占位行
- `exception_scope` 开始细分成 `exception_scope_base / exception_subject_scope / exception_match_mode`，并把 `review-subject-scope / review-exception-chain / review-exception-evidence` 这类 impact token 稳定写出
- 对 `prior-exception`，review impacts 开始细分到 `canon:review-exception-continuity`、`constraints:review-exception-chain`、`timeline:review-post-exception-beat`、`outline:review-post-exception-scene`
- 对 `prior-exception`，grouped summary 现在还会继续细分 `write_shapes`，直接区分 `keep-existing-exception-record / carry-forward-exception-note / append-post-exception-beat / append-post-exception-scene-note` 这类更接近执行层的复核动作
- 如果 `prior-exception` 下的默认 merge 输入实际命中既有 `event_id / scene_id`，对应 `write_shapes` 现在也会自动从 `append-post-exception-*` 收紧成 `rewrite-post-exception-*`
- 如果 `prior-exception` 当前不需要继续动 timeline / outline，grouped summary 现在会继续收紧成 `annotate-existing-exception-record / annotate-existing-rule-note`，明确这轮只补 canon / constraints 注释
- 对 `prior-exception + local-signal`，如果这轮没有可落地的 `event_id / scene_id`，grouped summary 现在会优先收敛到 `review-exception-evidence`，不再误带 `review-exception-chain`
- 对 `prior-exception + local-signal`，如果别的主体只出现在主体窗口外，grouped summary 现在仍保持 `review-exception-evidence`；只有主体窗口内已经混进别的主体时，才会额外升级到 `review-subject-scope`
- 对 `prior-exception + local-signal`，如果句子先提到别的主体、但在知识谓词前又重新落回规则主体，consistency 现在会继续保持 `shared-subject`，不再误升成 `mixed-subjects`
- 对 `prior-exception + local-signal`，如果别的主体出现在知识谓词后、并自己带第二个 knowledge verb，consistency 现在也会稳定升级成 `mixed-subjects`
- 对 `prior-exception + local-signal`，如果别的主体出现在知识谓词后、但后续 knowledge verb 前又重新落回规则主体，consistency 现在也会继续保持 `shared-subject`
- 对 `claim-match`，如果另一个角色只是旁观出场、但自己附近没有 knowledge signal，exception scope 现在也会继续保持 `shared-subject`，不再仅凭 `character_mentions` 误升成 `split-subjects`
- 对 `claim-match`，如果中间只是提到别的角色、后面又回到规则主体的第二个 knowledge verb，draft claim 抽取现在也不会再凭空造出那名角色的假 claim
- 对 draft claim 抽取，像“林舟和苏岚都知道...”这类并列主体共用一个 knowledge verb 的句式，仍会继续稳定拆成多主体 claim，不会被窗口收紧误截断
- 对 draft claim 抽取，像“林舟与阿岚知道...”这种别名参与的并列主体共享 knowledge verb，现也会继续稳定拆成 `林舟 / 苏岚` 两条 claim
- 对 draft claim 抽取与 subject-scope 扫描，如果第二主体只是落在“告诉 / 告知 / 提醒 / 通知”后的受词位置，后面的 knowledge verb 现在也会继续归给规则主体，不会再把“林舟告诉苏岚自己知道...”误抽成苏岚知情，或误升成 `mixed-subjects`
- 对 draft claim 抽取与 subject-scope 扫描，如果第二主体只是落在“从 / 由 / 经 + 某人 + 那里 / 这边 / 口中 / 处”这类来源短语里，后面的 knowledge verb 现在也会继续归给规则主体，不会再把“林舟从苏岚那里知道...”误抽成来源角色知情，或误升成 `mixed-subjects`
- 对 draft claim 抽取与 subject-scope 扫描，如果第二主体只是落在“听某人提起 / 说起 / 讲起”这类转述来源短语里，后面的 knowledge verb 现在也会继续归给规则主体，不会再把“林舟听苏岚提起后知道...”误抽成来源角色知情
- 对 draft claim 抽取与 subject-scope 扫描，如果第二主体只是落在“因 / 因为某人一句话 / 提醒 / 提点”这类触发短语里，后面的 knowledge verb 现在也会继续归给规则主体，不会再把“林舟因苏岚一句话才知道...”误抽成触发角色知情
- 对 draft claim 抽取与 subject-scope 扫描，如果另一角色只有短 alias 或称谓，且这枚 token 只是嵌在“岚城 / 阿岚街 / 白狼营 / 白狼帮 / 白狼会 / 白狼令 / 白狼封阵术 / 持白狼封阵术 / 借白狼封阵术 / 操控白狼巨舰”这类地名、设定名词、组织名、机构名或物件/术式名里，consistency 现在也不会再把它误当主体命中，更不会因此截断规则主体窗口或凭空造出假 claim
- 对 draft claim 抽取，如果规则主体只是“意识到 / 知道 / 发现”另一个角色已经知情，后面的嵌套 knowledge 子句现在也不会再反向污染规则主体本人，不会再把“林舟意识到苏岚知道...”误抽成林舟直接知道该事实
- 对 draft claim 抽取，如果外层只是“怀疑 / 猜测 / 听说 / 觉得 / 担心”另一个角色已经知情，内层 knowledge 子句现在也不会再被当成该角色已被正式证实的 direct claim，不会再把“林舟怀疑白狼知道...”误报成白狼真的知道
- 对 draft claim 抽取，如果 speculative 外层和内层主体之间只插了“那个 / 这名 / 那位”这类指代修饰，内层 knowledge 子句现在也仍会继续被视为未证实，不会再把“林舟怀疑那个白狼知道...”误报成白狼真的知道
- 对 draft claim 抽取，如果 speculative 外层和内层主体之间再夹着“那时 / 当时 / 第七章 / 在”这类时间或章节 filler，内层 knowledge 子句现在也仍会继续被视为未证实，不会再把“林舟怀疑那时那个白狼知道...”误报成白狼真的知道
- 对 draft claim 抽取，如果外层只是“据说 / 传闻 / 听闻”这类更弱的传闻前缀，内层 knowledge 子句现在也仍会继续被视为未证实，不会再把“据说那时那个白狼知道...”误报成白狼真的知道
- `same-chapter exemption` 的 review case 现在也开始补 `timeline:review-same-chapter-beat` / `outline:review-same-chapter-scene`，并和 `evidence-only / review-subject-scope` 规则保持一致
- 如果同一条 idea 同时还有 `world-rule conflict`，grouped summary 现在会先提一条 `shared-world-rule-context`，把 conflict 行和 exemption 行共同拥有的 `domains / targets` 上提
- 多条 exemption rule 共享同一批 review token 时，grouped summary 现在会先提一条 `shared-exemption-review`，把公共 `review_impacts / review_write_shapes / targets` 上提，减少逐条重复
- 如果同一组 exemption 同时混有 `direct` 和 `review`，grouped summary 现在还会再提一条 `shared-exemption-base`，把公共 `impacts / targets / domains` 再上提一层
- 对 `prior-exception + claim-match` 的叙事型 idea，如果这轮还没落到具体 event / scene，但已经是明确剧情 beat，grouped summary 现在仍会保留 `carry-forward-exception-note`
- 如果这类 `claim-match` 叙事型 case 同时落在 `split-subjects / mixed-subjects`，grouped summary 现在会退回 `annotate-existing-rule-note + review-subject-scope`，不再默认共用 exception chain
- world-rule 相关的 canon explainer 开始引用各自命中的 claim，而不是回退到第一条 claim
- 多条 rule 共享同一事件/场景写入时，重复的 timeline / outline explainers 开始做去重收敛
- conflict / exemption 的逐条 rule 行开始省掉和 `direct_/review_` 完全重合的 `impacts=` / `write_shapes=`，减少 grouped summary 明细噪音
- report 级结构化 `patch_suggestions`
- 对后文“再次意识到 / 已经知道”类复述记录的豁免
- relationship-history 对未来重复状态的图谱级豁免
- 如果同章已经有正式 relationship beat，future same-state 记录不再把当前 idea 误报成关系漂移

### 7. timeline merge 输入层

已支持：

- `plan_idea_merge` 输出结构化 `timeline_merge_inputs`
- `apply_idea_merge` 通过 `merge_input_id` 直接消费 merge plan 输入
- 对已有 scene 做跨章节移动时避免重复 scene id
- event / scene note 已可由 merge input 显式携带
- plan explainers 已可输出 `readiness / merge_input_id / planned_writes / source_signals`

### 8. canon relationship 联动

已支持：

- `state/canon-index.json` 新增 `relationships`
- relationship idea 可生成 `upsert-canon-relationship` merge input
- relationship / first-meeting 相关 issue 开始能驱动 canon 关系写入
- relationship-history 重复状态去重
- 关系在存在中间状态转移时的豁免规则
- 对“重新结盟 / 再次和解”且未来已有同状态记录的 case 开始按图谱路径豁免

### 9. world-rule 闭环

已支持：

- `world-rule conflict` 生成结构化 merge input
- merge input 可按不同策略更新事件/场景、`constraints` cutoff 或规则说明
- `resolve-world-rule-by-delaying-event` 可把 idea 事件延后到 cutoff 之后
- `resolve-world-rule-by-updating-cutoff` 可把 rule cutoff 对齐到新事件
- `document-world-rule-exception` 可只记录规则说明，并显式要求 override

### 10. demo / case workspace 整理

已支持：

- 对 legacy duplicate idea 进行收敛
- 为缺 intake draft 的历史 idea 补回最小 draft
- 让 demo workspace 回到“有一条可继续 plan-merge 的 pending idea”状态
- 新增 `first-workflow-case/` 作为首个独立 workflow 案例工作区，并停在 `clear gate + ready merge plan` 状态

### 11. intake backfill / repair

已支持：

- `scripts/backfill_intake_drafts.py`
- 对缺 draft / 缺 view / 缺 path 元数据的 pending idea 做正式 backfill
- 按 `--all-pending` 或 `--all-ideas` 批量修复
- 按 `--force-rebuild` 重建已有 draft

## 当前状态判断

项目已经从“蓝图阶段”进入“主链路闭环可跑”的阶段。

现在最缺的不是更多零散脚本，而是把以下链路继续做厚：

- merge plan 的影响面表达
- intake 对 legacy / 模糊 idea 的修复能力
- 更稳定的 timeline / outline / canon 联动
- 更明确的 skill 与 script 边界
- 更完整的 demo / case workspace / 文档闭环

当前最值得继续推进的，不再是继续堆顶层 grouped summary 压缩，而是：

- 更细的 `knowledge-state / world-rule` claim 提取边界
- 更少误报的 `subject-scope / mixed-subject` 判定
- 以及把这些边界稳定沉到可测试的脚本规则里

## 最近完成

- 为 intake 增加结构化 draft 层
- 新增 intake draft 的 JSON 与 HTML 产物
- 修复地点短语推断，使 `白塔议事厅` 这类地点可被正确提取
- 补齐对应测试并确认通过
- 落地 `novel-consistency-check` 的可用版，并接入 pipeline / 首页入口
- 新增 `relationship-history` 与 `world-rule` 两类冲突检查
- 让 merge plan 与 apply merge 显式读取 consistency gate
- 让 orchestrator 在 pending idea 上优先跑 consistency gate
- 扩展 claim-level `knowledge-state` 检查
- 让 consistency report 输出结构化 `patch_suggestions`
- 让 merge plan 输出 `timeline_merge_inputs`
- 让 apply merge 能直接消费 `merge_input_id`
- 让 canon relationship 进入机器真相源并接入 merge
- 让 relationship merge input 优先复用已有关系节点
- 为 relationship-history 增加图谱级去重和转移豁免
- 让 world-rule conflict 接入 plan/apply 闭环
- 把 world-rule 的单一路径扩成多策略输入
- 为 world-rule 增加“延后事件 / 只记规则说明”两条分支
- 为 knowledge-state 增加后文复述型豁免
- 为 relationship-history 增加未来重复状态的图谱级豁免
- 清理 demo workspace 的 legacy duplicate idea，并补回代表样本的 intake draft / plan
- 落地正式的 intake backfill / repair 脚本入口
- 为 legacy idea backfill 增加测试覆盖
- 把 merge plan 的影响面说明升级成 domain-specific explainers
- 为 timeline / outline / canon / constraints explainers 增加测试覆盖
- 为 `state/canon-index.json` 增加 `knowledge_states` / `world_rule_exceptions`
- 新增 `upsert-canon-knowledge-state` / `update-existing-knowledge-state`
- `document-world-rule-exception` 开始同步写入 canon 机器事实源
- consistency-check 开始读取 canon knowledge / world-rule exception 回流结果
- validator 开始校验 knowledge-state / world-rule exception 的引用完整性
- 收紧 `knowledge-state conflict` 边界：当更早 canon / timeline 记录已足够解释冲突时，不再同时报未来重复记录
- 收紧 `title-based drift` 边界：正式事件 / 场景标题即使带有地点括注或副标题，也能继续命中同一 idea
- 收紧 `knowledge object` 边界：`内鬼 / 泄密`、`身份 / 是谁`、`不是一路 / 不是同一阵营` 这类常见表达开始做保守归一，同时不再把“有人调查”误判成“有人泄密”
- 收紧 `world-rule exception` 边界：规则检测与例外豁免开始共用 `knowledge_claims`，`组织首领身份 / 组织首领是谁` 这类同义 object 不再依赖原句字面命中
- 收紧多 claim / 多 rule 闭环：`plan_idea_merge` 现在能把不同 rule 绑定回各自命中的 claim，而不再把第一条 subject claim 错绑到所有 rule
- 收紧 constraints explainer 边界：多条 world-rule 冲突时，plan 已开始先按 rule 分组摘要，减少人工在多条输入间来回对照
- 细化 constraints 影响面说明：grouped summary 已开始把每条 rule 的目标文件、direct/override 信息，以及 `timeline / outline / canon / constraints` 的 direct / review impact 类型直接摊开
- 细化 canon 影响面说明：多条 world-rule exception 的 canon explainer 已开始按各自命中的 claim 输出 source signal
- 收敛 explainers 噪音：同一事件/场景的重复 timeline / outline 说明开始优先保留一条更高可执行性的版本
- 细化 `prior-exception` 写入组合：grouped summary 已开始把“沿用旧 exception 但还需复核什么”继续拆成更接近执行的 `write_shapes`
- 收紧 `prior-exception` 写入形态：如果默认 merge 输入实际命中既有 event / scene，grouped summary 已开始把 `append` 自动改判成 `rewrite`
- 收紧 `prior-exception` 注释边界：如果当前 case 不需要 timeline / outline 写入，grouped summary 已开始把 review 收敛到纯 `annotate` 组合
- 收紧 `local-signal` 证据边界：如果这轮没有可落地的 event / scene 标识，grouped summary 已开始只提示 evidence note，而不再误判成 chain 更新
- 细化 `local-signal` 多主体边界：如果别的主体只出现在窗口外，grouped summary 继续只做 evidence review；只有窗口内混主体时才升级 subject-scope review
- 收敛 `same-chapter` 说明层：同章 exemption 的 grouped summary 已开始和 `prior-exception` 共用同一套 evidence / subject-scope / timeline-outline review 规则
- 收敛 grouped summary 噪音：多条 exemption 的公共 review token 已开始集中上提，不再在每条 rule 行里重复展开
- 收敛 rule-line 噪音：如果 `impacts=` / `write_shapes=` 只是 `direct_/review_` 的并集，明细行现在直接省掉泛化字段，避免同一 token 同行重复
- 收敛 exemption shared-line 噪音：`shared-exemption-review` 现在不再重复 `shared-exemption-base` 已经承载的 `domains / targets / reuse-exception` 公共项
- 收敛 exemption scope 噪音：多条 `reuse-existing-exception` 行里重复的 `subject_scope / exception_scope_*` 现在会先上提到 `shared-exemption-scope`
- 收敛 exemption rule-token 噪音：多条 `reuse-existing-exception` 行里重复的 `direct / review / subjects` 现在会先上提到 `shared-exemption-rule-tokens`
- 收敛 exemption 壳行噪音：如果若干 exemption 行只剩 exception id，grouped summary 现在会改成一条 `shared-exemption-links`
- 收紧 exception 选取边界：同一 rule 命中多条 exception 时，现在会优先选最贴近当前 draft chapter 的匹配记录，不再按存储顺序误选更早链路
- 收紧 relationship repeat 词表边界：`再度` 现在也会触发 future repeat after transition 的豁免，不再只识别 `重新 / 再次 / 又`
- 收紧 relationship 语义词表边界：`重归于好` 现在会同时触发 `reconciled` 状态与 repeat hint，`反目` 现在会映射到 `ruptured`
- 收紧 relationship 语义词表边界：`冰释前嫌` 现在也会同时触发 `reconciled` 状态与 repeat hint，`翻脸` 现在会映射到 `ruptured`
- 收紧 relationship 语义词表边界：`破镜重圆` 现在也会同时触发 `reconciled` 状态与 repeat hint，`闹翻` 现在会映射到 `ruptured`
- 收紧 relationship 语义词表边界：`言归于好` 现在也会同时触发 `reconciled` 状态与 repeat hint，`彻底翻脸` 现在会映射到 `ruptured`
- 收紧 relationship 语义词表边界：`握手言和` 现在也会同时触发 `reconciled` 状态与 repeat hint，`恩断义绝` 现在会映射到 `ruptured`
- 细化 `claim-match` 注释边界：叙事型 idea 在无 event / scene targets 时，grouped summary 已开始保留 `carry-forward`，而纯设定型则继续只走 `annotate`
- 收紧多主体 `claim-match` 边界：叙事型 idea 在 `split-subjects / mixed-subjects` 下，grouped summary 已开始从 `carry-forward` 退回 `annotate + review-subject-scope`
- 收紧同章锚点边界：如果当前 chapter 已经有正式的 knowledge-state / relationship 记录，future duplicate 不再反向把 idea 报成前移或漂移
- 收紧无 claim 的 world-rule 边界：exception fallback 与规则命中都开始按主体局部窗口判断，不再把另一主体的 object 误算进来
- 增加 exemption 可见性：同章 / 既有 world-rule exception 不再只在底层放行，report 与 plan 都开始显式标记
- 收敛 world-rule 说明噪音：已豁免 rule 不再单独挂一条 summary，而是开始和冲突 rule 共享一条 grouped constraints 说明
- 收紧 `repair-intake -> world-rule delay` 的备注来源：`resolve-world-rule-by-delaying-event` 现在也会优先吃修过的 `draft.content`，不再把旧 `idea.content` 回填进延后后的 event / scene notes
- 收紧 `update-existing-scene` 的旧关联残留：如果旧 scene 挂着的 `event_ids` 与当前 draft 的标题 / 地点不兼容，reuse input 现在会直接清掉这类 stale 关联，而不再继续保留旧 event 或写入一个并不存在的默认 event 占位
- 收紧 `update-existing-scene` 的旧 POV / characters 残留：如果 scene reuse 已稳定命中同一条旧 event，但当前 draft 没给出新的角色信息，scene 现在会优先向这条 linked event 的 participants 对齐，而不再继续沿用旧 scene 自己残留的 `pov / characters`
- 收紧 `update-existing-event` 的旧 participants 残留：如果 event reuse 已稳定命中一条明确 linked scene，而当前 draft 没给出新的角色信息，event 现在也会优先向这条 scene 的 `characters` 对齐，不再继续保留旧 event 自己残留的 participants
- 收紧 reuse 歧义回退：如果 linked scene / linked event 给出的结构化证据不唯一，planner 现在不会再静默沿用旧关联；`event` 会把 `participant_ids` 留空并暴露 `missing_fields`，`scene` 会清掉歧义 `event_ids`
- 收紧 reuse 歧义表达：这类“保守清空”的 case 不再只靠空字段间接暴露，merge plan 现在也会显式写出 warning，并把同一条 warning 抬进 `unresolved_questions`
- 收紧 reuse 歧义治理入口：这类 case 现在还会正式产出 `review_tokens`，并在 `proposed_actions` 里新增一条独立 `review` action，不再只散落在 warning 文本里
- 但 `prior-exception` 的 domain impact 仍是第一层保守拆分，后续还可以继续细化到更明确的写入组合

## 第十二轮真实 workspace 验收

- `demo-workspace/idea-20260604-001` 已把“同主体 later recap”跑成真实闭环：第 4 章既有 `knowledge-state` 保持不动，第 6 章 `再次确认议会内部泄密` 默认收敛成 `scene-only`
- `demo-workspace/idea-20260604-003` 已把新 fact `议长遇刺另有内情` 的 first node 正式写入 `timeline / outline + canon knowledge-state`
- `demo-workspace/idea-20260604-004` 已把同一 fact 的 second-subject-later-learns 跑通：第 9 章 `师姐` 的知情变化会追加新的 chapter-scoped `knowledge-state` 节点，而不是覆写 `林舟` 的第 8 章节点
- `demo-workspace/` 当前已回到 `pending=0 / applied=13 / rejected=5`，validator 继续保持 `ok=true`

这轮说明了一件更顶层的事：

- `knowledge-state` 已经不再只是“能写一条 canon 记录”
- 它现在已经有了 first node / later recap / second subject later learns 这三种真实 workspace 验收形态
- 因此默认优先级不该继续停在 relationship 或 knowledge-state 的横向补丁上，而应切到下一条大的 acceptance track

## 当前风险

- 语义级 merge 仍然偏弱
- consistency-check 已能输出 claim-level knowledge-state，但还不是完整知识图谱推理
- timeline merge 已接上第一层 canon knowledge / exception 联动，但还不是完整知识图谱推理
- relationship 目前已入 canon，但仍缺更丰富的状态图谱和更细的豁免边界，不过这些已不再是当前顶层默认优先级
- knowledge-state lifecycle 已有真实 workspace 验收，但 participant / POV 推断仍带有 intake 启发式噪音
- world-rule exception 已能处理 claim 级 subject/object 对齐，也已有真实的 `first exception / prior-exception continuity / split-subjects direct closure` 验收线；但 `mixed-subjects` 的最终 apply 策略仍未完全收口
- world-rule 已有多策略输入，但“只改说明”的策略仍依赖人工 override
- world-rule 现在已处理单 idea 下的多 claim / 多 rule 基本分流，并补上第一层 rule 级 direct / review impact 摘要、`shared-subject / split-subjects` 边界、标题/正文泛化 claim 收敛、mixed-subject claim 串绑收紧，以及 `identity / leak / same-camp / separate-camp` family 的更具体与更标准 wording 收敛；但更多 object family 仍偏薄
- intake backfill 目前仍以启发式推断为主，手工增强字段在 force rebuild 下会被重建
- canon 侧 explainers 仍有一部分 fallback case，尤其是更复杂的知识图谱与关系状态转移
- skill 规划已写出，但执行优先级还需要持续收敛

## 近期目标

1. 先补 `deterministic review writeback`，让 `review-constraints` 不只会停在报告，还能承接正式确认结果
2. 继续扩展 timeline-order / world-rule exception 规则
3. 继续增强 repair / merge explainers 的边界说明
4. 继续收敛 skill 与 script 的边界
