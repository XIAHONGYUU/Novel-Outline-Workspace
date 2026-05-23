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
- `knowledge_states[].subject_id` 是否都指向已存在角色
- `knowledge_states[].event_id` 如果存在，是否都指向已存在事件
- `world_rule_exceptions[].rule_id` 是否都指向已存在约束
- `world_rule_exceptions[].subject_id` / `event_id` 如果存在，是否指向合法对象

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

### 9. knowledge-state / world-rule exception 基本合法

如果 `canon-index.json` 中存在 `knowledge_states[]` 或 `world_rule_exceptions[]`，则：

- `knowledge_states[].id` 不能重复
- `knowledge_states[].reading_chapter` 必须是整数
- `knowledge_states[].object_key` 不能为空
- `world_rule_exceptions[].id` 不能重复
- `world_rule_exceptions[].reading_chapter` 必须是整数
- `world_rule_exceptions[].rule_id` 必须引用已存在约束

## 与 consistency-check 的边界

`validate_workspace` 负责整库硬检查。

`novel-consistency-check` 负责单条 idea 在 merge 前的独立冲突检查。

两者不是替代关系：

- validator 更偏“正式数据是否已经坏掉”
- consistency-check 更偏“这条新 idea 现在能不能安全并入”
- consistency-check 现已开始输出 claim-level `knowledge-state` 冲突和结构化 `patch_suggestions`
- consistency-check 现已开始回读 `knowledge_states[]` 与 `world_rule_exceptions[]`
- consistency-check 当前还带有一批确定性豁免：
  对后文“再次 / 已经”类知情复述，以及有明确状态转移后的未来重复关系状态，会尽量不误报
- 对同一 `knowledge-state` 同时命中更早与更晚记录的 case，会优先只保留更早冲突，避免重复告警
- 如果同章已经有正式的 event / scene / canon `knowledge-state` 记录，future duplicate 不会再把当前 idea 误报成知情点前移
- 对带地点括注或副标题的正式事件名 / 场景名，title-based drift 会尝试做保守的部分匹配
- 对少量高频 `knowledge object`，consistency-check 会做保守同义归一，并尽量避免把共享前缀但实际不同的事实误判为同一 object
- 对 `world-rule conflict` 与 `world_rule_exception`，consistency-check 现已开始优先复用结构化 `knowledge_claims` 做 subject / object 匹配
- 如果一条 draft 没有成功抽出 `knowledge_claims`，`world-rule` 也会退回到主体局部窗口做 signal 匹配，而不是直接用整句字面串；这样 mixed-subject 句子里别人的 object 不会再误触发当前 rule
- 如果某条 `world-rule` 已被正式 exception 放行，consistency report 现在会在 `exemptions[]` 中显式记一条 `world-rule-exemption-applied`，而不是只返回“无冲突”
- merge plan 的 grouped constraints 说明也会继续把这类 rule 带出来，并区分哪些可直接沿用、哪些仍需人工 review
- 对已豁免 rule，当前还会进一步写出 `exception_scope_base / exception_subject_scope / exception_match_mode`，并据此产出第一层 review impact token
- 如果同一主体同时抽到标题里的泛化 object 和正文里的更具体 object，`knowledge_claims` 会优先收敛到更具体那条
- 如果多主体句子里不同主体分别对应不同 object，`knowledge_claims` 会优先按主体窗口拆开，避免跨主体串绑
- 如果同一主体在同一 object family 里同时抽到更短概括表达和更长具体表达，`knowledge_claims` 会优先保留更具体那条；当前已覆盖 `identity / leak / same-camp / separate-camp`
- 在 `same-camp / separate-camp` family 内，如果只是 wording 不同，`knowledge_claims` 会优先保留更标准表达
- 不同 object family 的 claim 当前保持分离，避免把同章不同事实误收敛成一条
- 当单条 idea 同时命中多条 `world-rule` 时，issue 细节会开始带回各自命中的 claim，供后续 merge plan 精确消费
- merge plan 在多条 world-rule 场景下，现已开始先给 constraints 域分组摘要，再展开具体输入；摘要会带出每条 rule 的策略、targets、direct/override、按 direct / review 拆开的 impacts，以及 `shared-subject / split-subjects` exception scope
- 如果同章已经有正式 relationship beat，future same-state 记录也不会再把当前 idea 误报成关系漂移

## 当前未实现

- 完整的 knowledge-state 图谱与多跳推理
- 伏笔是否回收
- 动机链是否自洽
- 阵营关系是否逻辑闭环
- 更复杂的平行叙事自动豁免

这些仍应放到第二阶段继续增强。

## 输出形式

validator 会写两种结果：

- `views/validation-report.html`
- `state/workspace-status.json` 中的最新校验摘要
