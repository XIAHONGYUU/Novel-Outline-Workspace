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
