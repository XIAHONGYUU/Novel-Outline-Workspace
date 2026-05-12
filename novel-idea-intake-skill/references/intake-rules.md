# Intake Rules

## Likely kind inference

Typical default mapping:

- `reveal`
  Keywords like: 真相, 身份, 秘密, 泄密, 揭露, 知道
- `scene`
  Keywords like: 场景, 夜谈, 对话, 初见, confrontation
- `event`
  Keywords like: 发生, 爆发, 遇袭, 到达, 出发
- `character`
  Keywords like: 新角色, 师姐, 反派, mentor, rival
- `death`
  Keywords like: 死, 死亡, 牺牲
- `relationship`
  Keywords like: 认识, 误会, 结盟, 背叛
- `world`
  Keywords like: 规则, 世界观, 法则, 系统
- `twist`
  Keywords like: 反转, 其实, 原来

If no signal is strong enough, fall back to `misc`.

## Likely target inference

- `reveal`
  Usually impacts:
  - `outline/master-outline.md`
  - `outline/scene-index.json`
  - `timeline/events.json`
- `character`
  Usually impacts:
  - `state/canon-index.json`
  - `canon/characters.md`
- `world`
  Usually impacts:
  - `state/canon-index.json`
  - `canon/world-rules.md`
- `scene`
  Usually impacts:
  - `outline/master-outline.md`
  - `outline/scene-index.json`

## Tag inference

Good tags should be short and reusable:

- 人名
- 地点名
- 剧情功能词
- 主题词

Avoid turning the whole idea sentence into a tag.
