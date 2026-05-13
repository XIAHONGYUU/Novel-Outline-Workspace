# Skill Catalog

这份文档用于固定当前小说大纲工作区的 `skill` 规划，避免后续讨论反复漂移。

目标不是一次性把所有 `skill` 都实现，而是先把：

- 哪些 `skill` 值得做
- 每个 `skill` 的职责边界是什么
- 输入输出大致长什么样
- 它依赖哪些底层数据
- 它和其他 `skill` 的关系是什么

先稳定下来。

## 设计原则

### 1. `skill` 负责工作流，不直接替代数据层

`skill` 是工作流与决策层，不是事实源。

事实源仍应放在：

- `state/*.json`
- `timeline/events.json`
- `outline/scene-index.json`
- `canon/*`

### 2. 能做成 validator / script 的，不急着做成 skill

例如：

- 文件存在性检查
- ID 唯一性检查
- HTML 渲染
- 简单状态刷新

这些更适合留在脚本层。

### 3. 每个 skill 都要有明确边界

避免出现这种情况：

- 一个 skill 又做 merge，又做 consistency，又做 scene expansion，又做伏笔

这会让 skill 失控，难以调度，也难以验证。

### 4. 优先做高频、强耦合、可复用的 skill

优先级判断标准：

- 用户会不会经常用
- 会不会直接影响全工作区稳定性
- 是否能和现有 JSON / HTML 架构形成闭环

## 分层规划

当前建议分三档：

- `P0`
  第一阶段必须做，没有它们就无法形成稳定工作流。
- `P1`
  第二阶段高价值增强，能明显提升工作区质量。
- `P2`
  第三阶段优化型 skill，更偏向深化和可视化。

---

## P0 Skills

### `novel-idea-intake`

#### 作用

把用户随手输入的自然语言想法整理成标准化 idea patch 候选。

#### 当前实现状态

第一版已落地：

- 本地 skill：`novel-idea-intake-skill/`
- 入口脚本：`scripts/ingest_idea.py`
- 自动推断：
  - `kind`
  - `tags`
  - `target_files`
  - `suggested_domains`

本轮已升级到第二层：

- 自动生成 `state/intake-drafts/<idea-id>.json`
- 自动生成 `views/intake-drafts/<idea-id>.html`
- 开始输出 chapter/location/character 级提示

#### 为什么重要

如果入口层太乱，后面所有 merge、校验、人物关系、伏笔分析都会漂。

#### 典型输入

- 一句话剧情想法
- 一段设定补充
- 一个零散 scene 片段

#### 典型输出

- 标准化 idea 记录
- 建议标签
- 建议影响域
- 建议目标文件

#### 主要写入 / 依赖

- `state/idea-log.json`
- `inbox/*.md`

#### 边界

它只负责“收”和“初步整理”，不负责真正合并。

---

### `novel-consistency-check`

#### 作用

检查一条新剧情、新设定或一段补丁是否和现有 `canon / outline / timeline` 冲突。

#### 当前实现状态

MVP 已落地：

- 本地 skill：`novel-consistency-check-skill/`
- 入口脚本：`scripts/check_idea_consistency.py`
- 当前产物：
  - `state/consistency-checks/<idea-id>.json`
  - `views/consistency-checks/<idea-id>.html`

第一版当前覆盖：

- matching event / scene 的 chapter drift
- claim-level `knowledge-state` drift
- matching event 的 location drift
- 显式“初见 / 第一次见面”想法的 first-meeting conflict
- relationship-history conflict
- hard-canon world-rule conflict
- intake draft completeness warnings

本轮已补上：

- 从 idea 中提取 `谁在第几章知道 / 意识到什么` 的结构化 `knowledge_claims`
- report 级 `patch_suggestions`，供后续 merge 直接消费
- relationship-history 的图谱级去重与转移豁免基础版

仍待扩展：

- deeper knowledge-state graph reasoning
- 更细的 relationship-state 豁免边界
- 和 merge plan 的更强联动

#### 为什么重要

这是整个工作区的质检层。没有它，后续 merge 越多，工作区越容易自相矛盾。

#### 典型输入

- 一条新剧情
- 一个设定修订
- 一段结构化 patch

#### 典型输出

- 是否冲突
- 冲突等级
- 冲突类型
- 冲突位置
- 建议处理方式

#### 应重点覆盖的冲突

- `first-meeting conflict`
- `relationship-history conflict`
- `timeline-order conflict`
- `knowledge-state conflict`
- `world-rule conflict`
- `location continuity conflict`

#### 主要写入 / 依赖

- 读取：`state/canon-index.json`
- 读取：`constraints/constraints.json`
- 读取：`timeline/events.json`
- 读取：`outline/scene-index.json`
- 输出：校验报告 JSON / HTML

#### 边界

它只判断“能不能并进去”，不负责真正改大纲。
当前已经接入 pipeline 路由，会在 fresh pending idea 上优先于 merge plan 运行。

---

### `novel-timeline-merge`

#### 作用

把一条新剧情插入时间轴，并联动更新 `timeline / outline / canon`。

#### 当前实现状态

第一层输入已落地：

- `plan_idea_merge` 开始输出 `timeline_merge_inputs`
- `apply_idea_merge` 可按 `merge_input_id` 直接消费
- 当前优先覆盖：
  - 新建 event / scene 输入
  - 基于 `timeline-order / knowledge-state / location` issue 的已有记录更新
  - relationship idea 的 canon relationship 输入
  - 基于 `relationship-history / first-meeting` issue 的 canon relationship 更新

仍待补强：

- 更完整的 canon 联动
- world-rule 类输入
- 更细的 issue-specific strategy
- 更细的 relationship graph 豁免边界

#### 为什么重要

这是故事推进的施工队。很多新想法不只是加一条备注，而是要落到真实事件顺序里。

#### 典型输入

- 一条剧情补丁
- 一个新事件
- 一个场景修订

#### 典型输出

- 时间轴插入位置
- 事件节点更新
- scene 节点更新
- 必要时更新相关人物或设定

#### 主要写入 / 依赖

- `timeline/events.json`
- `outline/scene-index.json`
- `state/canon-index.json`
- `views/timeline.html`

#### 边界

它负责“并入时间与事件结构”，不负责深度人物分析。

---

### `novel-canon-manager`

#### 作用

维护正式设定层，包括人物、阵营、地点、规则、重要物件等。

#### 为什么重要

如果没有清晰的 canon 层，后续所有关系、时间、伏笔都会缺事实锚点。

#### 典型输入

- 新人物
- 新规则
- 新阵营
- 旧设定修订

#### 典型输出

- 更新后的正式设定索引
- 对应的 Markdown patch note
- 需要联动的其他层提示

#### 主要写入 / 依赖

- `state/canon-index.json`
- `canon/characters.md`
- `canon/world-rules.md`

#### 边界

它是正式设定管理员，不负责章节节奏和大纲推进。

---

### `novel-arc-structure-manager`

#### 作用

维护卷、幕、章节、主线、支线和阶段结构。

#### 为什么重要

很多剧情不是“要不要写”，而是“应该放在哪个结构位置”。

#### 典型输入

- 一段大纲修订
- 新阶段设想
- 支线插入

#### 典型输出

- 卷 / 幕 / 章层级调整
- scene 归位建议
- 结构空洞或拥挤提醒

#### 主要写入 / 依赖

- `outline/master-outline.md`
- `outline/scene-index.json`

#### 边界

它负责结构，不负责底层事实校验。

---

### `novel-outline-orchestrator`

#### 作用

作为总控入口，决定现在该先做 merge、先做校验、还是先补结构。

#### 为什么重要

用户不应该每次自己判断：

- 先跑什么脚本
- 先修什么层
- 哪一条 idea 最该先处理

#### 典型输入

- 当前工作区路径
- 可选用户意图

#### 典型输出

- 推荐下一步动作
- 推荐对应 skill
- 执行或只读判断结果

#### 主要写入 / 依赖

- `state/workspace-status.json`
- `views/index.html`
- 其他各 skill 的输出

#### 边界

它做调度，不做重型内容生成。

---

## P1 Skills

### `novel-character-network-manager`

#### 作用

当新增人物时，自动分析他和现有主要人物、阵营、冲突线的关系。

#### 为什么重要

很多人物问题不是“这个人是谁”，而是“这个人进来后，关系网怎么变”。

#### 典型输入

- 一个新人物
- 现有角色表
- 相关剧情上下文

#### 典型输出

- 关系类型
- 关系张力
- 功能位
- 潜在关系演化
- 是否与已有角色功能重叠

#### 应重点处理的关系维度

- 主角关系
- 配角关系
- 阵营归属
- 利益冲突
- 情绪张力
- 功能重复风险

#### 主要写入 / 依赖

- `state/canon-index.json`
- 未来的关系索引 JSON
- `canon/characters.md`

#### 边界

它不是时间线 skill，也不是 scene 扩写 skill。

---

### `novel-location-manager`

#### 作用

维护地点索引，并统计地点在大纲中何时、何地、因为什么被使用。

#### 为什么重要

地点不是背景板。地点本身会承载：

- 氛围
- 阵营控制
- 行程逻辑
- 事件发生地

#### 典型输入

- 新地点
- 现有剧情片段
- 事件与场景中的地点引用

#### 典型输出

- 地点索引
- 地点首次出现
- 地点关联人物
- 地点关联事件
- 地点冲突提示

#### 主要写入 / 依赖

- `state/canon-index.json`
- 未来的地点索引 JSON
- `timeline/events.json`

#### 边界

它先做地点逻辑，不直接等于地图展示。

---

### `novel-foreshadow-and-payoff`

#### 作用

为后续剧情设计前文伏笔，并检查后续是否完成回收和收束。

#### 为什么重要

伏笔不是一个普通“备注问题”，而是跨章节、跨阶段的结构问题。

#### 典型输入

- 一个后续要发生的关键剧情
- 当前已有前文结构

#### 典型输出

- 是否需要伏笔
- 最适合埋在哪几处
- 伏笔类型
- 伏笔强度建议
- 后续回收点建议

#### 常见伏笔类型

- 信息伏笔
- 道具伏笔
- 关系伏笔
- 规则伏笔
- 动机伏笔
- 反转伏笔

#### 主要写入 / 依赖

- `outline/scene-index.json`
- 未来的伏笔索引 JSON
- 相关 HTML 视图

#### 边界

它关注“埋与收”，不负责直接更新时间轴。

---

### `novel-knowledge-state-tracker`

#### 作用

跟踪“谁在什么时候知道了什么”。

#### 为什么重要

用户举的“本来认识、后来又写成不认识”就是这一类问题的典型代表。

#### 典型输入

- 一条认知变化剧情
- 一个揭露节点
- 一段关系修订

#### 典型输出

- 人物认知状态变化
- 认知冲突
- 揭露先后顺序建议

#### 主要写入 / 依赖

- 未来的 knowledge-state 索引 JSON
- `timeline/events.json`
- `outline/scene-index.json`

#### 边界

它和普通关系管理不同，它关注的是“信息状态”，不是“情感关系”。

---

## P2 Skills

### `novel-map-view-builder`

#### 作用

把地点层数据转换成 HTML 地图页、地点关系页或区域总览页。

#### 为什么放在 P2

展示必须建立在地点数据已经稳定之后，否则地图只会很漂亮但不可靠。

#### 典型输入

- 地点索引
- 地点和事件关系
- 地点和人物关系

#### 典型输出

- 地图页
- 地点卡片页
- 地点分布视图

#### 边界

它是 view builder，不是地点真相源。

---

### `novel-timeline-audit`

#### 作用

专门审计时间线，包括 travel time、事件间隔、章节时序和时间跳跃。

#### 为什么放在 P2

它很有用，但依赖前面已经有较成熟的事件层和地点层。

#### 边界

它更像高级 validator，而不是首批必须 skill。

---

### `novel-pacing-balance-check`

#### 作用

检查全书节奏、高光分布、低谷长度和结构换挡是否合理。

#### 为什么放在 P2

这是结构精修层，不是当前工作区能否运转的底层条件。

---

### `novel-ending-payoff-check`

#### 作用

检查前文铺垫是否足以支撑结局，结局是否兑现前面承诺。

#### 为什么放在 P2

它高度依赖前文已经稳定，不适合过早实现。

---

## Skill 关系图

可以把当前 skill 粗略理解成：

```text
novel-idea-intake
  -> novel-consistency-check
  -> novel-timeline-merge
  -> novel-canon-manager
  -> novel-arc-structure-manager
  -> novel-outline-orchestrator

novel-character-network-manager
novel-location-manager
novel-foreshadow-and-payoff
novel-knowledge-state-tracker
  -> 作为 P1 层增强

novel-map-view-builder
novel-timeline-audit
novel-pacing-balance-check
novel-ending-payoff-check
  -> 作为 P2 层深化
```

更准确地说：

- `orchestrator` 是调度层
- `consistency-check` 是质检层
- `timeline-merge` 是施工层
- `canon-manager / arc-structure-manager` 是正式资料维护层
- `character / location / foreshadow / knowledge-state` 是专题增强层
- `map / pacing / ending / timeline-audit` 是深化与展示层

## 当前建议开发顺序

### 第一阶段

1. `novel-idea-intake`
2. `novel-consistency-check`
3. `novel-timeline-merge`
4. `novel-canon-manager`
5. `novel-arc-structure-manager`
6. `novel-outline-orchestrator`

### 第二阶段

1. `novel-character-network-manager`
2. `novel-location-manager`
3. `novel-foreshadow-and-payoff`
4. `novel-knowledge-state-tracker`

### 第三阶段

1. `novel-map-view-builder`
2. `novel-timeline-audit`
3. `novel-pacing-balance-check`
4. `novel-ending-payoff-check`

## 最后结论

当前最重要的不是立刻把所有 skill 都实现，而是先保证：

- skill 之间不互相重叠
- 每个 skill 的输入输出边界清楚
- P0 能尽快形成闭环

这份文档就是为了固定这个边界，方便后续继续实现时不漂。
