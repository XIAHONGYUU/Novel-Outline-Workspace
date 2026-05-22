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
- `knowledge_claims`
- `patch_suggestions`
- `draft_path`
- `checked_at`

其中：

- `issues[].details` 可携带具体 `record_id / existing_chapter / draft_chapter / rule_id` 等机器可消费上下文
- `knowledge_claims` 用于记录从这条 idea 中提取出的“谁在何章知道了什么”的结构化信号
- `patch_suggestions` 用于记录后续 merge 可直接消费的结构化修补建议

对于 `world-rule conflict`，`issues[].details` 现在通常还会包含：

- `rule_subject`
- `rule_positive_token`
- `rule_object`
- `suggested_delay_chapter`

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
