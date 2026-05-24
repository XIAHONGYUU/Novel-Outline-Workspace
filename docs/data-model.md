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
- `missing_fields`
- `can_apply_directly`
- `resolves_blocked_gate`
- `requires_override`
- `resolution_note_suggestion`
- `apply_args`

其中：

- `resolves_blocked_gate` 用于标记这条 merge input 是否能在不手动 override 的前提下结构化消解原有 gate blocker
- `apply_args` 现在既可承载 timeline / outline / relationship，也可承载 constraint rule 更新参数

`proposed_actions` 现在不再只是泛化 domain 提示，而是更接近执行层的 explainer。

建议字段包括：

- `domain`
- `action`
- `summary`
- `target_files`
- `merge_input_id`
- `readiness`
- `planned_writes`
- `source_signals`
- `missing_fields`

其中：

- `merge_input_id` 用于把 domain explainer 指回某条具体 merge input
- `readiness` 用于表示当前是 `ready / needs-info / needs-review / blocked-by-gate / planned`
- `planned_writes` 用于把这一层准备写什么字段直接列出来
- `source_signals` 用于说明这条 explainer 是由哪些 intake / consistency 信号驱动的

当前常见策略包括：

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

如果 mixed conflict 子组里 `strategies / subjects` 也还有局部重复，
当前 constraints grouped summary 还可能再提一条：

- `shared-conflict-rule-tokens`

这条共享行通常承载：

- `rules=...`
- `strategies=...`
- `subjects=...`

也就是只把重复的 rule 标签字段单独上提，而把各自仍不同的部分继续留在
对应的 `rule-xxx:` 行里。

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
  "applied_merge_input_id": "timeline-merge-001"
}
```

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
