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
- 还缺哪些结构化信息
- 对应的 HTML 计划页路径

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
  "resolution_note": ""
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
  "locations": [],
  "factions": [],
  "items": []
}
```

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

## `views/*.html`

当前自动生成：

- `views/index.html`
  工作区总览页
- `views/validation-report.html`
  校验结果页
- `views/timeline.html`
- `views/merge-plans/<idea-id>.html`
  时间线页

这些页面来自 JSON 真相源，不应该反向手工编辑。
