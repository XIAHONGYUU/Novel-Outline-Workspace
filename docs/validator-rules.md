# Validator Rules

第一版 validator 只做“硬检查”，不装作能理解整本小说。

## 当前已实现

### 1. 必要文件存在

检查这些文件是否存在：

- `state/canon-index.json`
- `state/idea-log.json`
- `state/workspace-status.json`
- `timeline/events.json`
- `outline/scene-index.json`

### 2. 角色 / 事件 / 场景 ID 唯一

检查：

- `characters[].id`
- `events[].id`
- `scenes[].id`

是否重复。

### 3. 引用完整

检查：

- `events[].participants` 是否都指向已存在角色
- `scenes[].characters` 是否都指向已存在角色
- `scenes[].event_ids` 是否都指向已存在事件
- `relationships[].character_ids` 是否都指向已存在角色
- `relationships[].event_id` 如果存在，是否都指向已存在事件

### 4. 章节顺序正确

检查 `scene-index.json` 里的 `chapter` 是否严格递增。

### 5. 事件真实时间顺序正确

检查 `events[].chronological_index` 是否唯一，且能形成稳定顺序。

### 6. 角色死亡后仍出场

如果角色在 `canon-index.json` 中定义了 `death_event_id`，则：

- 不能出现在更晚的事件参与者里
- 不能出现在关联更晚事件的 scene 里

这条是第一版最直接的硬冲突检测。

### 7. 已应用 idea 缺少落地信息

如果 `idea-log.json` 中某条 idea 的状态是 `applied`，则必须有：

- `target_files`
- `resolution_note`

否则视为工作流不完整。

### 8. 关系记录基本合法

如果 `canon-index.json` 中存在 `relationships[]`，则：

- `relationships[].id` 不能重复
- 每条关系至少需要两个角色 id
- 关系引用不能指向不存在的角色或事件

## 与 consistency-check 的边界

`validate_workspace` 负责整库硬检查。

`novel-consistency-check` 负责单条 idea 在 merge 前的独立冲突检查。

两者不是替代关系：

- validator 更偏“正式数据是否已经坏掉”
- consistency-check 更偏“这条新 idea 现在能不能安全并入”
- consistency-check 现已开始输出 claim-level `knowledge-state` 冲突和结构化 `patch_suggestions`

## 当前未实现

- 完整的 knowledge-state 图谱与多跳推理
- 伏笔是否回收
- 动机链是否自洽
- 阵营关系是否逻辑闭环
- 平行叙事的自动豁免

这些仍应放到第二阶段继续增强。

## 输出形式

validator 会写两种结果：

- `views/validation-report.html`
- `state/workspace-status.json` 中的最新校验摘要
