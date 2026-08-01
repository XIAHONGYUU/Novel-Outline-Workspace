# Data Model

第一版采用“三层”：

- JSON 负责结构化索引和基础校验
- Markdown 负责人工输入和少量源码说明
- HTML 负责正式展示产物

## `state/workspace-status.json`

记录当前工作区的摘要状态：

- 小说名
- 主角名
- 角色数 / 事件数 / 场景数
- 想法数
- 最近一次校验结果
- 推荐下一步

其中 `view_files` 会以当前默认 key 为基础，再合并旧 `workspace-status.json` 里已有的自定义 key；这样 legacy workspace 在刷新状态时会自然补上新增视图入口，例如 `consistency_index` 与 `review_history_index`。

## `state/merge-plans/<idea-id>.json`

记录某条 idea 的半自动 merge 计划：

- 建议影响的 domain
- 建议写入的目标文件
- 当前 `consistency_gate`
- intake draft 摘要
- `timeline_merge_inputs`
- `proposed_actions`
- 还缺哪些结构化信息
- 对应的 HTML 计划页路径

其中 `timeline_merge_inputs` 可用于承载后续 `novel-timeline-merge` 的第一层可执行输入。

建议字段包括：

- `id`
- `strategy`
- `summary`
- `target_files`
- `source_issue_code`
- `source_issue_codes`
- `missing_fields`
- `warnings`
- `review_tokens`
- `apply_arg_conflicts`
- `apply_arg_review_holds`
- `can_apply_directly`
- `resolves_blocked_gate`
- `requires_override`
- `resolution_note_suggestion`
- `apply_args`

其中：

- `source_issue_code` 当前仍保留为兼容性的“主来源 issue code”
- `source_issue_codes` 用于显式记录这条 merge input 当前实际聚合了哪些 consistency issue，尤其用于同一 `event / scene record` 多 issue 合并后的来源保真
- `apply_arg_conflicts` 用于显式记录 dedupe 后仍存在解释风险的 `apply_args` 差异；当前主要先覆盖 list/dict 型字段的合并冲突
- `apply_arg_review_holds` 用于显式记录 dedupe 后仍需保留人工复核语义的字段；当前主要先覆盖 `participant_ids / scene_event_ids`
- `update-existing-scene` 当前也会把 `scene_character_ids / scene_pov` 缺口正式写进 `missing_fields`；当旧 scene、自身 draft、linked event 都给不出稳定角色来源时，这条输入不会再继续伪装成可直接 apply
- `update-existing-event` 的人物来源优先级是 `draft participant_ids -> linked scene characters -> existing event participants`；因此 draft 已给明确参与者时，旧 linked scene 角色只作为可被覆盖的次级信号
- 如果多条 linked scenes 指向同一 event 且 `characters` 集合一致，这组 scene 会被视为同一个稳定角色来源；只有角色集合实际冲突时才进入 `reuse-ambiguity-linked-scenes`
- `resolves_blocked_gate` 用于标记这条 merge input 是否能在不手动 override 的前提下结构化消解原有 gate blocker
- `apply_args` 现在既可承载 timeline / outline / relationship，也可承载 constraint rule 更新参数

当前常见的 `apply_arg_conflicts` 结构包括：

- `key`
- `value_kind`
- `primary_only`
- `secondary_only`
- `conflicting_subkeys`

其中：

- `value_kind=list` 常用于 `scene_event_ids` 这类列表字段在 dedupe 后出现成员差异
- `participant_ids` / `scene_event_ids` 这类字段当前还带有 review-hold 语义：即使 dedupe 后合并出了非空值，只要对应 reuse 歧义 token 仍在，`missing_fields` 也不会自动清空
- `value_kind=dict` 当前主要作为前向兼容壳子，用于显式记录未来嵌套参数键冲突

当前常见的 `apply_arg_review_holds` 结构包括：

- `field`
- `reason`
- `review_tokens`

当前执行层区分两类 ready：

- `direct-ready`：用于无 review decision 的显式 `apply-merge` fallback，必须 `can_apply_directly=true` 且没有 `missing_fields / warnings / review_tokens / apply_arg_conflicts / apply_arg_review_holds / requires_override`
- `review-ready`：用于 constraints / reuse review 里可被人工批准的输入，允许 `requires_override=true` 来消解当前 gate，但仍不能带 `missing_fields / warnings / review_tokens / apply_arg_conflicts / apply_arg_review_holds`

`apply_idea_merge()` 在实际写入前也会执行最终 hard gate：显式传入 `merge_input_id` 时，不能绕过 `missing_fields / review_tokens / apply_arg_conflicts / apply_arg_review_holds`；`requires_override` 必须显式传 `override_consistency_gate` 才能消费。`warnings` 仍会让输入不属于自动 `direct-ready / review-ready`，但保留给人工显式选择 caveat strategy 时使用。

显式传入 `merge_input_id(s)` 时，`apply_idea_merge()` 还会要求对应 merge plan 存在且不早于 idea 的 `updated_at`；旧 plan 必须先重跑 `plan-merge`，不能直接作为写入来源。

`proposed_actions` 现在不再只是泛化 domain 提示，而是更接近执行层的 explainer。

建议字段包括：

- `domain`
- `action`
- `summary`
- `target_files`
- `merge_input_id`
- `readiness`
- `review_policy`
- `review_policy_summary`
- `planned_writes`
- `source_signals`
- `missing_fields`
- `warnings`
- `review_tokens`

其中：

- `merge_input_id` 用于把 domain explainer 指回某条具体 merge input
- `readiness` 用于表示当前是 `ready / needs-info / needs-review / blocked-by-gate / planned`
- `review_policy` 用于把 `needs-review` 类 constraints action 的默认处理策略显式写出来，例如 `mixed-subjects-local-signal-review-only`
- `review_policy_summary` 用于给状态层、pipeline 与人工协作界面提供一句可直接展示的策略摘要
- `planned_writes` 用于把这一层准备写什么字段直接列出来
- `source_signals` 用于说明这条 explainer 是由哪些 intake / consistency 信号驱动的
- `warnings` 用于把“当前为什么不能静默复用旧记录”直接抬到 plan 层
- `review_tokens` 用于把需要单独人工复核的 planner 信号固化成稳定 token，方便状态层和后续 review report 继续消费

当 `proposed_actions[].domain == "constraints"` 且 `readiness == "needs-review"` 时，
`planned_writes` 现在也可能显式带出策略 token，例如：

- `policy=mixed-subjects-local-signal-review-only`

当前常见策略包括：

- `mixed-subjects-local-signal-review-only`
- `mixed-subjects-claim-match-review-only`
- `same-chapter-exemption-review`
- `prior-exception-continuity-review`

当前常见 `timeline_merge_inputs[].strategy` 包括：

- `create-event-and-scene`
- `update-existing-event`
- `update-existing-scene`
- `upsert-canon-knowledge-state`
- `update-existing-knowledge-state`
- `upsert-canon-relationship`
- `update-existing-relationship`
- `resolve-world-rule-by-delaying-event`
- `resolve-world-rule-by-updating-cutoff`
- `document-world-rule-exception`

`views/merge-plans/<idea-id>.html` 当前也会继续直接展示每条 `timeline_merge_input` 的以下解释字段，避免只能回看原始 JSON：

- `source_issue_codes`
- `missing_fields`
- `review_tokens`
- `warnings`
- `apply_arg_conflicts`
- `apply_arg_review_holds`

`views/index.html` 当前也会继续展示最近几条已归档的 review 结果，直接消费：

- `state/reuse-reviews/*.json`
- `state/constraint-reviews/*.json`

首页的 review history 区块当前主要展示：

- `review_state`
- `review_status_summary`
- `action_matrix` 的首条执行结果摘要
- `remaining_review_merge_inputs` 的首条 `remaining_kind + remaining_summary`
- 结构化剩余原因的首条 detail summary（例如 `source_issue_codes` / `apply_arg_conflicts` / `apply_arg_review_holds` 收敛出的说明）

`views/review-history/index.html` 当前会把这两类 archived review 继续汇总成独立索引页：

- `state/reuse-reviews/*.json`
- `state/constraint-reviews/*.json`

当前索引页按最新 archive 时间优先展示，并显式列出：

- `idea_id`
- `title`
- `kind`
- `review_state`
- `review_status_summary`
- `action_matrix` 的首条执行结果摘要
- 剩余项类型、摘要与首条结构化 detail reason
- `validation_ok`
- cross-links to:
  - archived review `report_path`（HTML 中使用 workspace 相对链接，避免把本机绝对路径写进页面）
  - `merge_plan_view_path`
  - latest `validation_report_path` when available

其中 world-rule 相关输入常会在 `apply_args` 里额外携带：

- `event_notes`
- `scene_notes`
- `rule_id`
- `rule_label`
- `rule_applies_until_event_id`
- `rule_notes`
- `world_rule_exception_id`
- `world_rule_exception_subject_name`
- `world_rule_exception_object_key`
- `world_rule_exception_reading_chapter`

当某条 plan 里出现 reuse 歧义时，当前还会在顶层额外聚合：

- `review_tokens`

它用于把 `timeline_merge_inputs` 里的歧义信号直接抬到 plan 顶层，方便 pipeline / review report 直接读取。

## `state/constraint-reviews/<idea-id>.json`

记录一条 idea 进入 `review-constraints` 后的结构化复核报告。

建议字段包括：

- `idea_id`
- `title`
- `status`
- `review_required`
- `review_state`
- `review_status_summary`
- `review_policy`
- `review_policy_summary`
- `constraints_summary`
- `review_checklist`
- `remaining_review_merge_inputs`
- `ready_merge_inputs`
- `blocked_merge_inputs`
- `action_matrix`
- `consistency_gate`
- `merge_plan_path`
- `merge_plan_view_path`
- `decision`
- `applied_result`
- `created_at`

其中：

- `review_required` 用于显式区分“这条 idea 当前是否真的停在 review-only 终点”
- `review_state` 用于显式区分当前 report 处于 `needs-review`、`approved-ready-merge-inputs`、`applied` 等哪一种阶段
- `review_status_summary` 用于给状态层、脚本输出和人工查看提供一句稳定摘要，避免已消费的 report 仍看起来像待处理 case
- `review_policy` / `review_policy_summary` 用于把当前默认策略矩阵写成稳定 token 与可展示摘要
- `review_checklist` 用于给人工复核提供一组确定性检查项
- `remaining_review_merge_inputs` 用于在 live review 与 archived history 里都显式保留“这轮没有被消费、仍待后续收口的 constraints/blocked 输入”
- `ready_merge_inputs` 用于列出“复核通过后可以直接消费”的 merge inputs，避免这类 case 被误打回 `repair-intake`
- `action_matrix` 用于把 `constraints / timeline / outline / canon` 各层当前的 `readiness` 一次性摊平，方便判断这条 idea 是“纯 review-only”还是“review + ready inputs 共存”
- `remaining_review_merge_inputs[].remaining_kind` 当前常见值包括 `constraints-review`、`missing-fields`、`needs-review`
- `remaining_review_merge_inputs[].remaining_summary` 用于把这条剩余输入当前还缺什么或仍需哪类复核写成一句稳定摘要
- `decision` 用于把人工复核后的确定性写回结果正式落进同一份 state 产物，而不是只停在口头备注
- `applied_result` 用于在 decision 已被消费后保留一份轻量的执行结果摘要，而不必回头重算 live review 状态

当 `decision` 已写回时，当前常见字段包括：

- `status`
- `summary`
- `resolution_note`
- `reviewer`
- `selected_merge_input_ids`
- `selected_merge_inputs`
- `apply_ready`
- `merge_plan_created_at`
- `merge_plan_fingerprint`
- `decided_at`
- `applied`
- `applied_at`
- `applied_merge_input_ids`

其中：

- `status=approved-ready-merge-inputs` 表示这条 review-only path 已被人工确认，可直接续到 `apply-merge`
- `status=rejected` 表示这条 review-only path 已被人工确认不进入 apply，并会把 idea 正式移出 pending path
- `selected_merge_input_ids` / `selected_merge_inputs` 用于显式列出这次确认后允许消费的 ready merge inputs
- `apply_ready=true` 表示当前决策仍与最新 merge plan 对齐，pipeline 可以直接消费
- `merge_plan_fingerprint` 用于按计划内容而不是按重跑时间判断决策是否仍对齐，避免同一条 plan 仅因重新生成就被误判失效
- `merge_plan_created_at` 当前主要保留为审计信息，说明这份 decision 最初是基于哪一轮 plan 产生的
- `applied=true` 表示这份 review 决策已经被真正消费过，不应再继续作为 pending apply 入口

当 `review_state=applied` 或 `review_state=rejected` 时，当前 report 还会遵循这些约定：

- `review_required=false`
- `review_checklist=[]`
- `remaining_review_merge_inputs` 继续保留未消费输入；旧归档如果缺这个字段，会优先从原 merge plan 回填
- `ready_merge_inputs=[]`
- `blocked_merge_inputs=[]`
- `consistency_gate.status=consumed` 或 `closed`

也就是这份 report 会从“待人工复核的 live review”切成“已消费的 review history”。

当 `review_state=rejected` 时，当前还可能额外带：

- `rejected_result`

它通常包含：

- `status`
- `resolution_note`
- `validation_ok`
- `validation_report_path`
- `validated_at`

## `state/reuse-reviews/<idea-id>.json`

记录一条 idea 进入 `review-reuse` 后的结构化复核报告。

建议字段包括：

- `idea_id`
- `title`
- `status`
- `review_required`
- `review_state`
- `review_status_summary`
- `review_summary`
- `review_tokens`
- `review_checklist`
- `review_merge_inputs`
- `remaining_review_merge_inputs`
- `ready_merge_inputs`
- `blocked_merge_inputs`
- `action_matrix`
- `consistency_gate`
- `merge_plan_path`
- `merge_plan_view_path`
- `decision`
- `applied_result`
- `created_at`

其中：

- `review_tokens` 当前主要用于稳定标识 `reuse-ambiguity-linked-scenes` / `reuse-ambiguity-linked-events`
- `review_merge_inputs` 用于单独列出真正停在 reuse 复核上的那几条 merge inputs
- `remaining_review_merge_inputs` 用于在 live review 与 archived history 里都显式保留“这轮没有被消费、仍待后续收口的输入”，避免只剩一条 resolution note；
  它当前既可能包含 reuse 歧义输入，也可能包含仍缺字段的 blocked 输入
- 上述 `review_merge_inputs / remaining_review_merge_inputs / ready_merge_inputs / blocked_merge_inputs` 当前也会继续保留 merge input 上的 `source_issue_codes / apply_arg_conflicts / apply_arg_review_holds`，方便 review report 和 CLI 直接解释这条输入为什么仍要人工确认
- `remaining_review_merge_inputs[].remaining_kind` 用于区分这条剩余输入当前为什么还没被消费；当前常见值包括：
  - `reuse-ambiguity`
  - `missing-fields`
  - `needs-review`
- `remaining_review_merge_inputs[].remaining_summary` 用于把这条剩余输入当前还缺什么直接写成一句稳定摘要，方便 review history 与后续 repair 路径继续消费
- `review_status_summary` 用于给状态层、脚本输出和人工查看提供一句稳定摘要，区分 live review、已确认待 apply、已消费归档等不同阶段
- `ready_merge_inputs` / `blocked_merge_inputs` 用于把“同一条 idea 里哪些输入在 reuse 歧义之外已结构完整、哪些仍缺字段”一次性摊平；
  对 `review-reuse` 来说，`ready_merge_inputs` 当前表示“复核 reuse 歧义后即可继续消费”的输入，
  不要求这些输入在原始 gate 下已经是 `can_apply_directly=true`
- `workspace-status` / orchestrator 当前也会继续消费 `remaining_review_merge_inputs` 里的结构化剩余原因；除 `remaining_kind / remaining_summary` 外，也可能继续把 `source_issue_codes / apply_arg_conflicts / apply_arg_review_holds` 收敛进推荐下一步的说明文案
- `decision` 用于把 reuse 复核后的确定性写回结果正式落进同一份 state 产物，而不是只停在口头备注
- `applied_result` 用于在 decision 已被消费后保留一份轻量的执行结果摘要
- 当 review report 从 live review 切到 archive 后，当前也会重新触发一次 workspace views 渲染，避免 `views/index.html` 仍停留在旧的“看不到 review history”状态

当 `decision` 已写回时，当前常见字段包括：

- `status`
- `summary`
- `resolution_note`
- `reviewer`
- `selected_merge_input_ids`
- `selected_merge_inputs`
- `remaining_review_merge_input_ids`
- `remaining_review_merge_inputs`
- `apply_ready`
- `merge_plan_created_at`
- `merge_plan_fingerprint`
- `decided_at`
- `applied`
- `applied_at`
- `applied_merge_input_ids`

其中：

- `status=approved-ready-merge-inputs` 表示这条 reuse review path 已被人工确认，可直接续到 `apply-merge`
- `status=rejected` 表示这条 reuse review path 已被人工确认不进入 apply，并会把 idea 正式移出 pending path
- `selected_merge_input_ids` / `selected_merge_inputs` 用于显式列出这次确认后允许消费的非歧义 merge inputs
- `remaining_review_merge_input_ids` / `remaining_review_merge_inputs` 用于显式列出这次 decision 之后仍保留为后续待处理项的输入；
  这些剩余项当前会继续带上 `remaining_kind / remaining_summary`
- `apply_ready=true` 表示当前决策仍与最新 merge plan 对齐，pipeline 可以直接消费
- `merge_plan_fingerprint` 用于按计划内容而不是按重跑时间判断决策是否仍对齐，避免同一条 plan 仅因重新生成就被误判失效
- `applied=true` 表示这份 reuse review 决策已经被真正消费过，不应再继续作为 pending apply 入口

当 `review_state=applied` 或 `review_state=rejected` 时，当前 report 还会遵循这些约定：

- `review_required=false`
- `review_checklist=[]`
- `review_merge_inputs=[]`
- `remaining_review_merge_inputs` 保留归档时仍未消费的输入，包括 reuse 歧义与字段缺失待补项
- `ready_merge_inputs=[]`
- `blocked_merge_inputs=[]`
- `consistency_gate.status=consumed` 或 `closed`

也就是这份 report 会从“待人工复核的 live review”切成“已消费的 review history”。

当 `review_state=rejected` 时，当前还可能额外带：

- `rejected_result`

它通常包含：

- `status`
- `resolution_note`
- `validation_ok`
- `validation_report_path`
- `validated_at`

## `state/intake-drafts/<idea-id>.json`

记录一条 raw idea 在 intake 阶段推断出的结构化草案。

建议字段包括：

- `kind`
- `suggested_domains`
- `chapter_hints`
- `location_candidates`
- `character_mentions`
- `timeline_candidates`
- `outline_candidates`
- `canon_update_candidates`
- `open_questions`
- `confidence`

其中：

- `timeline_candidates[].participant_candidates` 除了作为 intake 提示外，当前也可作为 timeline merge 的 `participant_ids` 回填来源；这类回填主要用于保留某些 `mixed-subjects` 草案的原始形态，同时避免它们被误打回 `repair-intake`

## `state/consistency-checks/<idea-id>.json`

记录一条 idea 在 merge 前做的独立 consistency 检查结果。

建议字段包括：

- `idea_id`
- `ok`
- `conflict_count`
- `error_count`
- `warning_count`
- `issues`
- `issues[].details`
- `exemptions`
- `knowledge_claims`
- `patch_suggestions`
- `draft_path`
- `checked_at`

其中：

- `issues[].details` 可携带具体 `record_id / existing_chapter / draft_chapter / rule_id` 等机器可消费上下文
- `exemptions` 用于记录“这条 idea 本来会命中规则，但已被正式 canon / exception 放行”的结构化说明
- `knowledge_claims` 用于记录从这条 idea 中提取出的“谁在何章知道了什么”的结构化信号
- `patch_suggestions` 用于记录后续 merge 可直接消费的结构化修补建议

对于 `world-rule conflict`，`issues[].details` 现在通常还会包含：

- `rule_subject`
- `rule_positive_token`
- `rule_object`
- `suggested_delay_chapter`

对于已被正式例外放行的 `world-rule`，`exemptions[].details` 现在通常还会包含：

- `matched_exception_id`
- `matched_exception_subject_name`
- `matched_exception_object_key`
- `matched_exception_chapter`
- `exception_scope`
- `exception_scope_base`
- `exception_subject_scope`
- `exception_match_mode`

对于 `knowledge_claims`，当前单条 claim 通常还会包含：

- `subject_id`
- `subject_name`
- `verb`
- `object_phrase`
- `object_key`
- `chapter`
- `first_claim`
- `is_recap`

其中：

- `is_recap=true` 表示这条 claim 更像“同一主体对同一事实的后续再次确认 / 再次知道”，后续 planner 可据此优先收敛到 `scene-only` repeat beat，而不是改写既有 `knowledge-state` 首次节点

在 `proposed_actions` 的 constraints grouped summary 里，如果某条 rule 已被正式 exception 覆盖，当前通常会写成：

- `reuse-existing-exception`
- `direct=1 / review=0` 或反过来
- `subject_scope`
- `exception_scope`
- `exception_scope_base`
- `exception_subject_scope`
- `exception_match_mode`

当前常见 token 约定：

- `exception_scope_base`
  例如 `same-chapter`、`prior-exception`
- `exception_subject_scope`
  例如 `shared-subject`、`split-subjects`
- `exception_match_mode`
  例如 `claim-match`、`local-signal`

如果多条 exemption 共享同一批 scope 元信息，当前 constraints grouped summary 还可能再提一条：

- `shared-exemption-scope`

这条共享行通常承载：

- `rules=...`
- `subject_scope=...`
- `exception_scope=...`
- `exception_scope_base=...`
- `exception_subject_scope=...`
- `exception_match_mode=...`

也就是把多条 `reuse-existing-exception` 行里重复出现的 scope 元信息先上提，
而各自的 `rule-xxx:` 行只再保留不共享的 scope 字段。

如果多条 exemption 共享同一批非 scope 的 rule 元信息，当前 constraints grouped summary 还可能再提一条：

- `shared-exemption-rule-tokens`

这条共享行通常承载：

- `rules=...`
- `direct=...`
- `review=...`
- `subjects=...`

也就是把多条 `reuse-existing-exception` 行里重复出现的 rule 元信息先上提，
而各自的 `rule-xxx:` 行只再保留不共享的 `direct / review / subjects` 字段。

如果若干 exemption 行在扣掉这些共享 token 之后只剩下 exception id 映射，
当前 constraints grouped summary 还可能再提一条：

- `shared-exemption-links`

这条共享行通常承载：

- `pairs=rule-xxx:exception-id, ...`

也就是把“只剩 `exceptions=` 的壳行”收成一条 rule->exception 的映射行，
而不再保留多条只差 exception id 的 `rule-xxx:` 行。

如果一条 idea 同时命中多条 `world-rule conflict`，且这些冲突共享同一批 context，
当前 constraints grouped summary 还可能先提一条：

- `shared-conflict-context`

这条共享行通常承载：

- `domains`
- `targets`

也就是多条 conflict rule 共同拥有的公共上下文；各自的 `impacts / write_shapes`
仍会留在对应的 `rule-xxx:` 行里。

如果这些 conflict 连动作层也完全相同，当前 constraints grouped summary 还可能再提一条：

- `shared-conflict-actions`

这条共享行通常承载：

- `direct_impacts`
- `review_impacts`
- `direct_write_shapes`
- `review_write_shapes`

而各自的 `rule-xxx:` 行则只继续保留策略、主体范围和差异字段。

如果不是“全部 conflict 都一致”，而只是其中一个子集动作签名一致，
当前 `shared-conflict-actions` 还可能进一步带出：

- `rules=rule-001, rule-002`

也就是一条 subset 级共享动作行，只把这部分冲突共同拥有的动作 token 上提。

如果这些 conflict 连策略和主体范围也一致，当前 constraints grouped summary 还可能再提一条：

- `shared-conflict-structure`

这条共享行通常承载：

- `rules=...`
- `strategies=...`
- `direct=...`
- `override=...`
- `subjects=...`
- `subject_scope=...`

也就是把重复的冲突元信息从逐条 `rule-xxx:` 行里再拿掉一层。

如果策略或主体不同、但仍共享同一批结构 token，
当前 constraints grouped summary 还可能再提一条：

- `shared-conflict-structure-tokens`

这条共享行通常承载：

- `rules=...`
- `direct=...`
- `override=...`
- `subject_scope=...`

也就是只把重复的结构字段单独上提，而把各自不同的 `strategies / subjects`
继续留在对应的 `rule-xxx:` 行里。

如果同一批 mixed conflict 子组同时共享 `direct/override/subject_scope`
以及 `strategies/subjects + domains/targets`，当前 constraints grouped summary
还可能直接收成一条：

- `shared-conflict-rule-metadata`

这条共享行通常承载：

- `rules=...`
- `direct=...`
- `override=...`
- `subject_scope=...`
- `strategies=...`
- `subjects=...`
- `domains=...`
- `targets=...`

也就是把原本分成 `shared-conflict-structure-tokens` 和
`shared-conflict-rule-details` 的局部描述再合成一条。

如果同一批 mixed conflict 子组同时共享 `shared-conflict-rule-metadata`
以及 `direct/review impacts + direct/review write_shapes`，当前 constraints grouped summary
还可能再进一步收成一条：

- `shared-conflict-rule-summary`

这条共享行通常承载：

- `rules=...`
- `direct=...`
- `override=...`
- `subject_scope=...`
- `strategies=...`
- `subjects=...`
- `domains=...`
- `targets=...`
- `direct_impacts=...`
- `review_impacts=...`
- `direct_write_shapes=...`
- `review_write_shapes=...`

也就是把原本分成 `shared-conflict-rule-metadata` 和
`shared-conflict-rule-actions` 的局部 summary 再合成一条。

如果当前批次的 conflict rule 还共享同一批顶层 `domains / targets`，
并且也共享同一批顶层 `impacts / write_shapes`，当前 constraints grouped summary
还可能把原本分开的：

- `shared-conflict-context`
- `shared-conflict-actions`

直接合成一条：

- `shared-conflict-summary`

这条共享行通常承载：

- `domains=...`
- `targets=...`
- `impacts=...`
- `direct_impacts=...`
- `review_impacts=...`
- `write_shapes=...`
- `direct_write_shapes=...`
- `review_write_shapes=...`

也就是把全局 conflict context 和全局 conflict actions 收成一条顶层 summary。

如果这条顶层 `shared-conflict-summary` 对应的 conflict rule 同时也共享同一套
`strategies / direct / override / subjects / subject_scope` 结构签名，当前
constraints grouped summary 还可能再把：

- `shared-conflict-summary`
- `shared-conflict-structure`

继续合成一条：

- `shared-conflict-overview`

这条共享行通常承载：

- `rules=...`
- `strategies=...`
- `direct=...`
- `override=...`
- `subjects=...`
- `subject_scope=...`
- `domains=...`
- `targets=...`
- `impacts=...`
- `direct_impacts=...`
- `review_impacts=...`
- `write_shapes=...`
- `direct_write_shapes=...`
- `review_write_shapes=...`

也就是把顶层 conflict summary 和“全部 rule 共享的一条结构行”再收成一条 overview。

如果 mixed conflict 子组里 `strategies / subjects` 也还有局部重复，
当前 constraints grouped summary 还可能再提一条：

- `shared-conflict-rule-tokens`

这条共享行通常承载：

- `rules=...`
- `strategies=...`
- `subjects=...`

也就是只把重复的 rule 标签字段单独上提，而把各自仍不同的部分继续留在
对应的 `rule-xxx:` 行里。

如果同一批 mixed conflict 子组同时共享 `strategies/subjects` 和
`domains/targets`，当前 constraints grouped summary 还可能直接收成一条：

- `shared-conflict-rule-details`

这条共享行通常承载：

- `rules=...`
- `strategies=...`
- `subjects=...`
- `domains=...`
- `targets=...`

也就是把原本分成 `shared-conflict-rule-tokens` 和
`shared-conflict-rule-context` 的局部共享描述合成一条。

如果 mixed conflict 子组里 `domains / targets` 也还有局部重复，
当前 constraints grouped summary 还可能再提一条：

- `shared-conflict-rule-context`

这条共享行通常承载：

- `rules=...`
- `domains=...`
- `targets=...`

也就是只把重复的 rule 级 context 单独上提，而把各自仍不同的部分继续留在
对应的 `rule-xxx:` 行里。

如果 mixed conflict 子组里 `direct_impacts / review_impacts` 也还有局部重复，
当前 constraints grouped summary 还可能再提一条：

- `shared-conflict-rule-impacts`

这条共享行通常承载：

- `rules=...`
- `direct_impacts=...`
- `review_impacts=...`

也就是只把重复的 rule 级 impact 字段单独上提，而把各自仍不同的部分继续留在
对应的 `rule-xxx:` 行里。

如果同一批 mixed conflict 子组同时共享 `direct/review impacts` 和
`direct/review write_shapes`，当前 constraints grouped summary 还可能直接收成一条：

- `shared-conflict-rule-actions`

这条共享行通常承载：

- `rules=...`
- `direct_impacts=...`
- `review_impacts=...`
- `direct_write_shapes=...`
- `review_write_shapes=...`

也就是把原本两条分别承载 impacts / write_shapes 的局部共享 action 行合成一条，
避免连续重复同一组 `rules=...`。

如果不同 conflict 子组虽然整体动作签名不同，但共享同一批写入形态，
当前 constraints grouped summary 还可能再提一条：

- `shared-conflict-write-shapes`

这条共享行通常承载：

- `rules=...`
- `direct_write_shapes=...`
- `review_write_shapes=...`

也就是只把局部重合的 scene/event 写入形态单独上提。

对于 conflict 侧直写路径的 scene/event 写入，当前 `write_shapes` 还可能进一步收敛成：

- `cutoff-resolution:carry-forward`
- `delay-resolution:rewrite-chapter`
- `exception-note:record`

其中 `cutoff-resolution:carry-forward` 用于把原本需要同时写出的
`constraints:rewrite-cutoff / story-beat:carry-forward`
压成一个跨域 token。

其中 `delay-resolution:rewrite-chapter` 用于把原本需要同时写出的
`timeline:rewrite-event-chapter / outline:rewrite-scene-chapter`
压成一个跨域 token。

其中 `exception-note:record` 用于把原本需要同时写出的
`canon:record-exception-entry / constraints:append-exception-note`
压成一个跨域 token。

对应的直写路径 impact，当前也可能进一步收敛成：

- `cutoff-resolution:update-placement`
- `delay-resolution:update-placement`

也就是把原本需要同时写出的冲突直写 impact 压成更稳定的跨域 token。

如果某条 `world-rule conflict` 在扣掉这些共享行后已没有剩余字段，
当前 grouped summary 也不会再保留一个空的：

- `rule-001:`

而是直接由对应的 `shared-conflict-*` 行代表它。

当前常见 review impact token：

- `constraints:review-subject-scope`
- `constraints:review-exception-chain`
- `canon:review-exception-evidence`
- `canon:review-exception-continuity`
- `timeline:review-post-exception-beat`
- `outline:review-post-exception-scene`

其中 `prior-exception` 常见会组合出：

- `canon:review-exception-continuity`
- `constraints:review-exception-chain`
- `timeline:review-post-exception-beat`
- `outline:review-post-exception-scene`

当前 grouped summary 里，如果继续往写入动作收敛，常见还会带出：

- `canon:reuse-existing-exception-record`
- `constraints:reuse-existing-exception-note`
- `canon:keep-existing-exception-record`
- `canon:annotate-existing-exception-record`
- `constraints:carry-forward-exception-note`
- `constraints:annotate-existing-rule-note`
- `timeline:append-post-exception-beat`
- `timeline:rewrite-post-exception-beat`
- `outline:append-post-exception-scene-note`
- `outline:rewrite-post-exception-scene-note`

其中如果默认 merge 输入虽然还是 `create-event-and-scene`，但其 `event_id / scene_id` 已经命中既有正式记录，grouped summary 现在会优先落成：

- `timeline:rewrite-post-exception-beat`
- `outline:rewrite-post-exception-scene-note`

而不是继续写成 `append-post-exception-*`。

同样地，如果 `create-event-and-scene` 这轮连可落地的 `event_id / scene_id` 都没有，
当前 grouped summary 也不会再把它误写成 `append-post-exception-*`。

如果当前 case 不需要继续动 timeline / outline，grouped summary 现在还会继续收紧成：

- `canon:keep-existing-exception-record`
- `canon:annotate-existing-exception-record`
- `constraints:annotate-existing-rule-note`

这时通常也不会再补 `timeline:review-post-exception-beat`、`outline:review-post-exception-scene`
或对应的 `timeline/events.json`、`outline/scene-index.json` target。

对 `prior-exception + local-signal`，如果这轮既没有可落地的 `event_id / scene_id`，
也没有额外 timeline / outline 写入，当前通常会继续收紧成：

- `canon:review-exception-evidence`
- `canon:keep-existing-exception-record`
- `canon:annotate-existing-exception-record`
- `constraints:annotate-existing-rule-note`

此时如果别的主体只出现在目标主体窗口之外，当前 `exception_scope` 仍通常保持：

- `prior-exception-shared-subject-local-signal`

只有当别的主体已经进入目标主体的局部窗口时，才会升级成：

- `prior-exception-mixed-subjects-local-signal`

并进一步带出：

- `constraints:review-subject-scope`

对 `same-chapter exemption` 的 review case，当前也开始补：

- `timeline:review-same-chapter-beat`
- `outline:review-same-chapter-scene`

并与上面同一套 `local-signal` 窗口规则共用：

- 窗口外才出现别的主体：只补 `canon:review-exception-evidence`
- 窗口内已混主体：再额外补 `constraints:review-subject-scope`

对 `prior-exception + claim-match`，如果这轮虽然没有具体 `event_id / scene_id`，
但 draft 仍属于叙事型 kind，例如 `reveal / twist / backstory / event / scene / death`，
当前 grouped summary 通常还会继续保留：

- `constraints:carry-forward-exception-note`

同时不一定补 `timeline:review-post-exception-beat` / `outline:review-post-exception-scene`；
也就是说，`carry-forward` 已经不再等同于“必然有 timeline / outline target”。

但如果这类 `claim-match` 叙事型 case 同时落在 `split-subjects / mixed-subjects`，
当前 grouped summary 会优先退回：

- `constraints:annotate-existing-rule-note`
- `constraints:review-subject-scope`

而不再默认保留 `constraints:carry-forward-exception-note`。

如果一条 idea 同时命中多条已豁免 rule，且这些 rule 共享同一批 review token，
当前 constraints grouped summary 还可能先提一条：

- `shared-exemption-review`

这条共享行通常会集中承载公共的：

- `review_impacts`
- `review_write_shapes`
- `targets`
- `domains`

而每条具体 `rule-xxx: reuse-existing-exception` 行只再保留各自不共享的部分。

如果同一组 exemption 同时混有 `direct` 和 `review`，当前 constraints grouped summary 还可能再提一条：

- `shared-exemption-base`

这条基础共享行通常承载：

- `impacts`
- `targets`
- `domains`

而不会重复承载已经属于 `shared-exemption-review` 的 review 专属 token。

同样地，`shared-exemption-scope` 也只负责 exemption 的 scope 元信息，
不会重复承载已经属于 `shared-exemption-base` / `shared-exemption-review`
的 impact、write-shape 或 target token。

`shared-exemption-rule-tokens` 也遵循同样原则：
它只负责 exemption 的 rule 元信息，不承载 scope、impact 或 write-shape token。

`shared-exemption-links` 也只负责 rule 与 exception id 的映射，
只有在对应 rule 行已经没有其余剩余 token 时才会出现。

如果同一条 idea 同时还有 `world-rule conflict`，当前 constraints grouped summary 还可能再提一条：

- `shared-world-rule-context`

这条 context 行通常只承载：

- `domains`
- `targets`

也就是 conflict 行和 exemption 行共同拥有的公共上下文；各自的 `impacts / write_shapes`
仍会留在对应的 rule 行里。

## `state/idea-log.json`

记录所有已录入想法。

每条 idea 建议字段：

```json
{
  "id": "idea-20260511-001",
  "title": "女主更早知道真相",
  "kind": "reveal",
  "status": "pending",
  "source": "manual",
  "content": "第一卷末尾她已经知道组织首领身份，只是假装不知道。",
  "tags": ["女主", "真相", "反派"],
  "target_files": ["canon/characters.md", "outline/master-outline.md"],
  "created_at": "2026-05-11T00:00:00Z",
  "updated_at": "2026-05-11T00:00:00Z",
  "resolution_note": "",
  "consistency_report_path": "/abs/path/to/state/consistency-checks/idea-20260511-001.json",
  "consistency_gate_status": "clear",
  "merge_gate_override": false,
  "applied_merge_input_id": "timeline-merge-001",
  "applied_merge_input_ids": ["timeline-merge-001", "timeline-merge-002"]
}
```

其中：

- `applied_merge_input_id` 继续用于“只应用了一条 merge input”的简单情况
- `applied_merge_input_ids` 用于记录“一次性消费了一组 merge inputs”的情况

## `state/canon-index.json`

第一版机器可读设定索引。

```json
{
  "novel_name": "示例小说",
  "characters": [
    {
      "id": "char-protagonist",
      "name": "主角名",
      "aliases": [],
      "role": "protagonist",
      "status": "alive",
      "death_event_id": null
    }
  ],
  "relationships": [
    {
      "id": "rel-char-protagonist-char-sulan-allied-ch6",
      "character_ids": ["char-protagonist", "char-sulan"],
      "state": "allied",
      "reading_chapter": 6,
      "event_id": "event-alliance",
      "notes": "两人在第六章正式结盟。"
    }
  ],
  "knowledge_states": [
    {
      "id": "know-char-protagonist-议会和黑潮并非同一阵营-ch3",
      "subject_id": "char-protagonist",
      "subject_name": "主角名",
      "object_key": "议会和黑潮并非同一阵营",
      "object_phrase": "议会和黑潮并非同一阵营",
      "verb": "意识到",
      "reading_chapter": 3,
      "event_id": "event-white-tower-hearing",
      "notes": "主角在第三章正式意识到两者不是一路。"
    }
  ],
  "world_rule_exceptions": [
    {
      "id": "rulex-rule-001-主角-议会和黑潮并非同一阵营-ch3",
      "rule_id": "rule-001",
      "rule_label": "主角在首领身份正式揭露前不知道组织首领身份",
      "subject_id": "char-protagonist",
      "subject_name": "主角名",
      "object_key": "议会和黑潮并非同一阵营",
      "object_phrase": "议会和黑潮并非同一阵营",
      "reading_chapter": 3,
      "event_id": "event-white-tower-hearing",
      "notes": "这条提前知情点作为正式例外保留。"
    }
  ],
  "locations": [],
  "factions": [],
  "items": []
}
```

其中：

- `relationships` 用于承载第一层正式关系事实源
- `knowledge_states` 用于承载正式知情节点
- `world_rule_exceptions` 用于承载正式规则例外说明，供后续 consistency 直接读取

建议字段包括：

- `id`
- `relationships[].character_ids`
- `relationships[].state`
- `knowledge_states[].subject_id`
- `knowledge_states[].object_key`
- `knowledge_states[].reading_chapter`
- `world_rule_exceptions[].rule_id`
- `world_rule_exceptions[].object_key`
- `event_id`
- `notes`

## `timeline/events.json`

记录事件真实时间顺序。

```json
{
  "events": [
    {
      "id": "event-001",
      "label": "主角离开故乡",
      "chronological_index": 1,
      "reading_chapter": 1,
      "participants": ["char-protagonist"],
      "location": "故乡",
      "notes": ""
    }
  ]
}
```

## `outline/scene-index.json`

记录正式场景索引。

```json
{
  "chapters": [
    {
      "chapter": 1,
      "title": "第一章",
      "summary": "主角被迫离家。",
      "scenes": [
        {
          "id": "scene-001",
          "title": "离家前夜",
          "pov": "主角名",
          "status": "planned",
          "characters": ["char-protagonist"],
          "event_ids": ["event-001"],
          "notes": ""
        }
      ]
    }
  ]
}
```

## `constraints/constraints.json`

第一版硬约束文件。

```json
{
  "rules": [
    {
      "id": "rule-001",
      "type": "hard-canon",
      "label": "主角在第一卷前不知道组织首领身份",
      "applies_until_event_id": "event-010",
      "notes": ""
    }
  ]
}
```

第一版脚本只做基础存在性和引用检查，不会完整理解所有规则语义。
但先把规则存储位置固定下来，后续容易扩展。

当前 `world-rule` 的结构化 merge 允许三种常见方向：

- 延后 idea 对应事件到 cutoff 之后
- 把 `applies_until_event_id` 对齐到新事件
- 只记录规则例外说明

其中第三种默认不自动消解 gate，仍要求显式 override。

## `views/*.html`

当前自动生成：

- `views/index.html`
  工作区总览页
- `views/validation-report.html`
  校验结果页
- `views/timeline.html`
- `views/merge-plans/<idea-id>.html`
  时间线页
- `views/intake-drafts/<idea-id>.html`
  intake draft 预览页
- `views/consistency-checks/<idea-id>.html`
  单条 idea 的 consistency 检查页

这些页面来自 JSON 真相源，不应该反向手工编辑。
