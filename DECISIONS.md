# Decisions

这个文件记录会影响项目方向、实现边界和协作方式的关键决策。

## 2026-05-12

### 决策：采用固定的根目录协作文档

新增并长期维护以下文件：

- `PROJECT_STATUS.md`
- `NEXT_ACTIONS.md`
- `DECISIONS.md`
- `AGENTS.md`

原因：

- 降低跨天继续开发时的上下文损耗
- 让 AI 编程工具有稳定入口
- 把“现在做到哪了、接下来做什么、为什么这样做”分开记录

---

## 2026-05-12

### 决策：项目采用 workspace-first，而不是一次性生成大纲

事实源分层固定为：

- `canon`
- `outline`
- `timeline`
- `state`
- `inbox`
- `views`

原因：

- 小说策划是持续演化，不是一次性产出
- 后续需要回滚、校验、合并和复查
- 把状态放进工作区比把结果留在聊天记录里更稳定

---

## 2026-05-12

### 决策：JSON 是机器真相源，Markdown 主要用于输入与说明，HTML 是主要展示产物

原因：

- JSON 便于脚本处理和校验
- Markdown 适合人工录入和阅读
- HTML 更适合作为最终浏览界面

影响：

- 不鼓励反向手改生成视图
- 校验、渲染、merge 都应优先围绕 JSON 设计

---

## 2026-05-12

### 决策：idea 采用 patch 模式，而不是直接改整份大纲

基本路径：

`raw idea -> intake -> merge plan -> validate -> apply merge`

原因：

- 原始想法通常是不完整、口语化、局部的
- 先收集再结构化，能减少大纲层的反复重写
- 更容易做局部回滚和冲突分析

---

## 2026-05-12

### 决策：新增 intake draft 作为独立中间层

新增产物：

- `state/intake-drafts/<idea-id>.json`
- `views/intake-drafts/<idea-id>.html`

原因：

- raw idea 和正式 merge plan 中间需要过渡层
- 便于记录推断出的 `kind / tags / target_files / chapter / location / character`
- 后续 consistency-check 和 merge 可以直接消费 draft

---

## 2026-05-12

### 决策：skill 负责工作流，script 负责确定性执行

原因：

- skill 适合调度、判断下一步、组织流程
- script 更适合稳定的数据写入、校验和渲染

影响：

- 不把所有能力都堆成一个大 skill
- 能在脚本层完成的事，优先保持在脚本层

---

## 2026-05-12

### 决策：`novel-consistency-check` 的 MVP 先做确定性弱语义检查

第一版先支持：

- matching title 的 chapter drift
- matching event 的 location drift
- 显式 first-meeting conflict
- intake completeness warnings

原因：

- 当前 JSON 模型还不够支撑完整语义推理
- 先做可解释、可测试、可复用的检查，比过早做模糊推理更稳
- 后续可以在不推翻接口的前提下继续补强冲突类型

---

## 2026-05-12

### 决策：merge 默认受 consistency gate 约束

当前规则：

- `plan_idea_merge` 必须显式读取 consistency report
- `apply_idea_merge` 默认不允许跳过 missing / stale / blocked gate
- 只有显式传入 override 时，才允许人工强制并入

原因：

- 否则 consistency-check 会退化成“看了也可以不理”的旁路能力
- merge 计划和最终写入必须共享同一个 gate，工作流才闭环

---

## 2026-05-13

### 决策：下一阶段优先做 `novel-timeline-merge`，但前提是保留 gate-aware merge

当前状态：

- intake 已能输出结构化 draft
- consistency-check 已能输出独立 report
- merge plan / apply merge 已接入 consistency gate

因此下一阶段不应绕开现有 gate 直接做更复杂的大纲写入，而应该让：

- intake draft
- consistency report
- merge plan

共同成为 `novel-timeline-merge` 的输入层。

原因：

- 否则后续 timeline merge 会重新发明一套并行输入
- 已有 gate-aware merge 是后续 skill 的稳定前提
- 先把输入层收敛，后续 `canon-manager` 和 `arc-structure-manager` 更容易接入

---

## 2026-05-13

### 决策：consistency report 开始输出结构化 `knowledge_claims` 和 `patch_suggestions`

当前状态：

- idea-level consistency check 已能识别一部分 `knowledge-state conflict`
- 下一阶段需要让 `novel-timeline-merge` 直接消费 consistency 结果

因此不再只输出面向人看的 issue 文本，还要在 report 里补：

- `knowledge_claims`
- `patch_suggestions`
- `issues[].details`

原因：

- 否则后续 merge 仍要从长句描述里反向猜结构化输入
- 先把 consistency 输出层机器化，timeline merge 更容易落地
- 这能保持 `check-consistency -> plan-merge -> apply-merge` 的闭环连续性

---

## 2026-05-13

### 决策：`plan_idea_merge` 先输出 `timeline_merge_inputs`，`apply_idea_merge` 直接按 `merge_input_id` 消费

当前状态：

- consistency report 已能输出 `knowledge_claims` 和 `patch_suggestions`
- merge plan 之前仍偏“报告”，不够接近执行层

因此先不急着拆独立脚本，而是在现有 `plan/apply` 之间加一层结构化输入：

- `state/merge-plans/<idea-id>.json` 增加 `timeline_merge_inputs`
- `apply_idea_merge` 支持 `merge_input_id`

原因：

- 这能最短路径打通从 report 到执行的闭环
- 不会绕开现有 gate-aware merge
- 等输入层稳定后，再拆更完整的 `novel-timeline-merge` 会更稳

---

## 2026-05-13

### 决策：relationship 进入 `state/canon-index.json` 的正式机器源

当前状态：

- relationship-history / first-meeting 已经能在 consistency-check 中稳定产出 issue
- 如果关系只写 Markdown note，后续 merge 和 validator 都无法稳定消费

因此本轮增加最小关系结构：

- `state/canon-index.json -> relationships[]`

第一层只固定：

- `id`
- `character_ids`
- `state`
- `reading_chapter`
- `event_id`
- `notes`

原因：

- 先把关系事实从纯文本提到机器真相源
- 让 relationship merge input 有稳定落点
- 后续再扩 richer graph，不必推翻当前接口

---

## 2026-05-13

### 决策：relationship-history 先采用“重复状态去重 + 中间状态转移豁免”

当前状态：

- `relationships[]` 已进入 `state/canon-index.json`
- relationship merge input 已能写入 canon

如果没有去重与豁免，常见的“先结盟、后决裂、再结盟”会被错误地持续判成重复冲突。

因此本轮规则固定为：

- 同一 pair 在没有中间状态转移的前提下，重复同状态视为冲突
- 如果两次同状态之间存在明确不同状态，则后一次同状态允许豁免
- merge input 在命中已有关系节点时优先复用旧节点 id，而不是盲目追加

原因：

- 先把最常见的关系图谱噪音压下去
- 保持 merge 输入尽量更新已有节点，减少重复关系记录
- 后续再补更细的豁免边界时，不需要推翻当前模型

---

## 2026-05-13

### 决策：`world-rule conflict` 先提供一条“事件 + cutoff 对齐”的结构化 resolution path

当前状态：

- `world-rule conflict` 已能稳定产出 issue 和 `patch_suggestions`
- 如果只保留人工 override，gate-aware merge 会在这类 case 上断开

因此当前先固定一条可执行策略：

- 创建或更新 idea 对应事件 / 场景
- 同时把 `constraints` 中对应 rule 的 `applies_until_event_id` 对齐到该事件

原因：

- 这条路径能最短闭环接上现有 `plan/apply`
- 相比直接 override，更接近结构化修复
- 后续可以在不推翻接口的前提下继续增加“延后事件”或“改单条 rule 说明”等分支
