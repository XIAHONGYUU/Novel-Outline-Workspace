# Decisions

这个文件记录会影响项目方向、实现边界和协作方式的关键决策。

## 2026-06-03

### 决策：P0 顶层推进改为“acceptance tracks framework”，而不是继续按零散样例推进

当前状态：

- relationship history 这条线已经连续跑通了 `first node / repeat beat / transition / reconciliation`
- 如果继续只按单个样例记进展，顶层计划会越来越像流水账
- 这会让后续协作重新回到“看起来哪里还能补，就先补哪里”的模式

因此这一轮开始：

- 顶层默认用 `docs/workspace-acceptance-framework.md` 追踪当前阶段
- 每次推进先判断是在补哪一条 `acceptance track`
- 只有当某条 track 被真实 workspace 卡住时，才回头补脚本、planner 或 consistency 细节

原因：

- 当前最重要的已经不是多一个例子，而是把“哪些闭环已经收口、下一个缺口在哪”说清楚
- 这样更容易避免重新陷进细节型推进
- 也更适合后续把零散 case 收束成稳定阶段框架

影响：

- 顶层计划将不再默认围绕单个样例书写
- `NEXT_ACTIONS.md` 和 `PROJECT_STATUS.md` 会更强调 track，而不是只强调 case
- 下一步默认优先补 `Track 8: Post-Reconciliation Repeat Beat`

### 决策：relationship reconciliation 继续沿用“追加新 history 节点”而不是回写旧节点

当前状态：

- `demo-workspace/idea-20260603-001` 在已有 `allied@5 -> ruptured@7` 关系链后，又新增了第 9 章 `和解`
- 这类 case 本质上不是 repeat beat，而是关系状态在历史链上的再次变化
- 如果把它回写到旧节点，关系链就会失去中间阶段

因此这一轮确认：

- 对 `reconciled` 这类后续复归型状态，默认继续产出新的 `upsert-canon-relationship`
- apply 时保留旧的 `allied / ruptured` 节点，同时追加新的 chapter-scoped `reconciled` 节点
- `outline scene + canon relationship` 继续作为这类复归型 case 的默认真实闭环形态

原因：

- 关系的恢复本身也是正式 canon 事实，不应只停留在 scene 层
- 追加新节点能保住完整关系链，而不是把“关系曾经破裂”抹掉
- 这样后续遇到 `再次结盟 / 再次和解` 时，planner 才有稳定的 history basis 可用

影响：

- `demo-workspace` 当前已形成 `allied@5 -> ruptured@7 -> reconciled@9` 的三段 relationship history chain
- 关系层的真实验收已经不止覆盖单次状态转移，而是开始覆盖连续 history
- 下一阶段的重点继续前移到：已有 `reconciled` 节点之后，repeat beat / 再变化怎样与整条 history chain 对齐

## 2026-06-02

### 决策：真实 relationship state transition 默认追加新的 `canon relationship` history 节点

当前状态：

- `demo-workspace/idea-20260602-004` 暴露出另一类真实 case：第 5 章已经有正式 `allied` 关系记录，第 7 章又出现 `决裂`
- 这类 case 和 same-state repeat beat 不同，它不是“再次确认旧状态”，而是关系状态真的发生了变化
- 如果继续复用旧节点或只写 scene，`canon` 层就无法稳定表达关系史

因此这一轮开始：

- 对明确的 relationship state transition，planner 默认继续产出新的 `upsert-canon-relationship`
- apply 时保留旧关系节点，同时追加新的 chapter-scoped relationship history 节点
- `outline scene + canon relationship` 继续作为这类 case 的默认真实闭环形态

原因：

- 关系状态变化本身就是正式 canon 事实，不应只停留在 narrative scene
- 追加新节点比覆写旧节点更能保住关系链
- 这让真实 workspace 能稳定形成 `allied@5 -> ruptured@7` 这类历史序列，为后续 reconciliation / repeat beat 提供确定性基础

影响：

- `demo-workspace/idea-20260602-004` 已能真实闭环到 `apply`
- `state/canon-index.json` 的 relationship layer 不再只承载单点关系，而开始承载有序 history
- 下一阶段的重点继续前移到：多段 relationship history chain 之后，后续 `和解 / 再结盟` 等复归型 beat 应怎样继续落库

## 2026-06-02

### 决策：same-state relationship repeat beat 默认保留旧 `canon relationship`，只新增 scene

当前状态：

- `demo-workspace/idea-20260602-003` 暴露出一个真实 case：第 5 章已经有正式 `结盟` 关系记录，第 6 章又出现“再次结盟”
- 旧版 planner 会把这类 case 收敛成 `update-existing-relationship`
- 如果直接 apply，既有 `canon relationship` 会被整体改写到更晚章节，语义上等于抹掉“首次结盟发生在第 5 章”这件事

因此这一轮开始：

- 对 same-state repeat beat，如果已有同状态 `canon relationship` 且 wording 明确是“再次/重新/再度”等重复关系 beat，planner 默认不再直接改写旧关系节点
- planner 改为优先产出一个 `scene-only` 的 gate-resolving input
- apply 后保留旧 `canon relationship` 章节，只把新的重复关系 beat 落成后续 scene

原因：

- same-state repeat beat 本质上更像“关系再次被叙事确认”，不是“首次关系发生时间被改写”
- 先保住已有 `canon relationship` 的首次发生章节，语义更稳
- 这能让 consistency / plan / apply 在真实 workspace 里顺利闭环，而不需要先发明新的 relationship history 数据结构

影响：

- `demo-workspace/idea-20260602-003` 已能真实闭环到 `apply`
- `state/canon-index.json` 的关系首次节点不会因重复 beat 被误覆写
- 下一阶段的重点前移到：当关系状态真的发生变化时，何时该追加新的 `canon relationship` history 节点

## 2026-06-01

### 决策：`apply_idea_merge` 继续沿用单入口，但要支持一条 idea 一次性消费多条 `merge_input_id`

当前状态：

- `plan_idea_merge` 已能为同一条 idea 产出多条可 direct apply 的结构化输入
- 真实案例里最常见的组合已经不只是单条 timeline 输入，而是 `timeline / outline / canon` 联动写入
- 如果 CLI 只能吃一条 `merge_input_id`，就会迫使使用者手工拼多套参数，或者逐条 apply 并覆盖 idea 元数据

因此这一轮不新增第二套 apply 脚本，而是在现有 `apply_idea_merge` 上继续扩：

- `scripts/apply_idea_merge.py` 支持重复传入 `--merge-input-id`
- 底层 `apply_idea_merge` 支持一次性合并一组 `merge_input_id`
- `state/idea-log.json` 开始记录 `applied_merge_input_ids`

原因：

- 这比新造一套“batch apply”入口更稳，也更符合现有 `plan -> apply` 主链路
- 用户仍只需要记住一个 apply 命令，心智成本更低
- 这能直接覆盖 `first-workflow-case` 里最典型的 `timeline + knowledge-state` 组合写入

影响：

- `merge / apply` 的可执行性问题从“必须手工补参数”收敛成“默认直接消费 plan 输入”
- 后续工作区级验收可以更真实地测试一条 idea 的多层联动写入
- 下一阶段优先级进一步转向工作区级集成测试，而不是继续扩单条规则补丁

### 决策：`warning-only` 但仍缺关键字段的 pending idea，工作流默认进入 `repair-intake`

当前状态：

- `demo-workspace/` 暴露出一种真实 case：consistency 没有硬冲突，但 merge plan 仍缺 `chapter_number`
- 旧版 pipeline `auto` 会把这种 case 泛化成继续 `plan-merge`
- 这会让“没有 blocker”被误读成“已经可以 apply”

因此这一轮开始：

- `workspace-status.json` 的 `recommended_next_step` 要直接指出缺什么字段
- orchestrator 默认把这类 case 收敛到 `repair-intake`
- `repair-intake` 成为显式流程动作，而不是隐含在人工判断里

原因：

- 真实工作区更需要“下一步做什么”足够具体，而不是继续给泛化状态
- 这类问题属于执行链路缺口，不是新的 consistency 规则缺口
- 先把 pending path 解释清楚，比继续补句式规则更值钱

影响：

- `demo-workspace/` 这类 `needs-info` case 现在能明确停在 intake 修补层
- `P0` 验收开始真正区分 `blocked / needs-info / ready`
- 顶层计划默认继续向 `repair -> plan -> apply` 的集成闭环推进

### 决策：为 `repair-intake` 补一个确定性的字段修补脚本，而不是继续依赖手改 JSON

当前状态：

- `backfill_intake_drafts.py` 只擅长“从现有文本重新推断 draft”
- 真实卡点往往不是“缺 draft”，而是“缺人类确认后的章节号、地点或待确认问题收口”
- 如果没有显式写回入口，`repair-intake` 只能停留在状态提示层，无法稳定闭环

因此这一轮补了：

- `scripts/update_intake_draft.py`
- workspace 层对应的确定性 patch 入口
- 更新 draft 后自动失效旧 consistency report / merge plan 的规则

原因：

- 人类确认字段本来就是主链路的一部分，不该继续依赖手工改 JSON
- draft 一旦改了，旧 report / plan 就不再可靠，应该显式失效
- 这能把 `repair-intake -> check-consistency -> plan-merge -> apply-merge` 真正连成脚本级闭环

影响：

- `repair-intake` 从“提示动作”升级成了“可脚本执行动作”
- pipeline 不会再继续盯着过期 merge plan 的 `missing_fields`
- 下一阶段可以更自然地把这条路径推进到真实 workspace 验收

### 决策：从规则微调优先，切到 `P0` 收口与工作区级验收优先

当前状态：

- `consistency -> merge` 主链路的底层规则已经补到较细粒度
- `subject-scope / claim-level` 的局部误判已经覆盖到受词、来源、转述来源、触发短语等一层
- 继续深挖中文句式级边界，边际收益已经下降

因此从这一轮开始，默认优先级调整为：

- 先定义 `P0` 收口标准
- 再用 `demo-workspace/` 与 `first-workflow-case/` 做工作区级验收
- 优先修会阻断真实闭环的 `merge / apply / validate` 问题
- 只有当真实 workspace 被明确卡住时，才回头补对应规则

原因：

- 项目当前更缺的是“可稳定交付的一轮闭环”，不是继续堆更多规则微优化
- 如果没有工作区级验收，规则层再细，也无法证明主链路真的可用
- 先锁定阶段收口线，后续 `timeline merge` 的推进才有稳定起点

影响：

- `NEXT_ACTIONS.md` 不再默认把句式级规则细化放在第一优先级
- 后续任务拆分会更偏向 checklist、workspace walkthrough、apply 稳定性和集成测试
- 规则补丁仍然允许继续做，但默认要由真实 workspace 卡点来驱动

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

---

## 2026-05-21

### 决策：`world-rule conflict` 改为多策略 merge input，而不是只保留 cutoff 对齐

当前状态：

- `world-rule conflict` 已能稳定产出 issue 和 `patch_suggestions`
- 单一路径的 cutoff 对齐已经不够覆盖真实 merge 选择

因此本轮把结构化输入扩成三类：

- `resolve-world-rule-by-delaying-event`
- `resolve-world-rule-by-updating-cutoff`
- `document-world-rule-exception`

其中：

- 前两类允许在仅有 `world-rule conflict` 时直接结构化解 gate
- 只记录规则说明的路径明确保留 `override` 要求

原因：

- 同一类冲突至少存在“改事件”与“改规则”两种方向
- 不是所有规则说明修改都应被系统装作已经自动消解 gate
- 先把策略层显式化，后续再继续丰富 explainers 和选择逻辑

---

## 2026-05-22

### 决策：首个独立 workflow 案例工作区先保留在 `plan-merge` 前状态

当前状态：

- 仓库里已经有一个持续演化中的 `demo-workspace/`
- 但还缺一个“从零初始化后，最短路径跑到 ready merge”的独立案例

因此本轮新增一个单独工作区：

- `first-workflow-case/`

并刻意把它停在：

- 想法已录入
- consistency gate 已通过
- merge plan 已生成
- 尚未 apply

原因：

- 这样最适合作为“第一次用这条 workflow 应该看到什么”的样本
- 它既能展示 intake / consistency / plan 的完整产物
- 又不会把后续 apply 结果混进第一次案例，便于继续复盘

---

## 2026-05-22

### 决策：多条 `world-rule` 冲突时，`proposed_actions` 先给 constraints 分组摘要

当前状态：

- 单条 idea 下的多 claim / 多 rule 绑定已经打通
- 但如果 plan 直接只列一串具体输入，人工仍要自己先把它们按 rule 分组再理解

因此本轮先在 explainer 层加一层摘要：

- 当同一 idea 同时命中两条及以上 world-rule
- `proposed_actions` 先输出一条 constraints 域的 grouped summary
- 再保留每条 rule 对应的 delay / cutoff / exception 具体输入
- grouped summary 里直接列出每条 rule 的策略、目标文件、direct/override 和跨 domain impact 类型，并继续细分哪些 impact 可直接 apply、哪些只能 review
- grouped summary 里还要带出按主体链划分的 exception scope，至少区分 `shared-subject` 和 `split-subjects`
- 如果同一主体在标题和正文里同时触发泛化 object 与更具体 object，claim 层优先保留更具体的匹配，减少 world-rule 下游重复绑定
- 如果多主体句子里前后主体分别对应不同 object，claim 层要按主体窗口拆开，避免后一个主体的 object 被前一个主体误吸收
- 如果同一主体在同一 object family 里出现更短的概括表达和更长的具体表达，claim 层优先保留更具体的那条；当前已覆盖 `identity / leak / same-camp / separate-camp`
- 在 `same-camp / separate-camp` family 内，如果只是标准表达和口语表达差异，claim 层优先保留更标准的 wording
- 不同 object family 的 claim 当前保持分离，避免把同章出现的不同事实错误收敛
- grouped summary 里直接列出每条 rule 的策略、目标文件和 direct/override 信息

原因：

- 先按 rule 聚合，人工更容易判断本次是“一条规则多策略”，还是“多条规则并行冲突”
- 这能减少在 merge plan 里来回对照多条 input 的成本
- 先把摘要层补上，后续再继续细化更完整的 impact explainer

---

## 2026-05-23

### 决策：`knowledge-state / relationship-history` 先把“同章已落地”视为稳定锚点

当前状态：

- `knowledge-state` 已能处理“更早记录优先”和 future recap 豁免
- `relationship-history` 已能处理未来重复状态与中间状态转移豁免
- 但如果同章已经存在正式的 event / scene / canon beat，后面更晚的重复记录仍可能把当前 idea 误报成前移或漂移

因此本轮先补一个更保守的 chapter-scoped 边界：

- 如果同章已经有正式的 `knowledge-state` 记录，无论来源是 event / scene / canon，优先视为当前 idea 已落地
- 如果同章已经有正式的 relationship beat，优先视为当前关系状态已经落地
- 在这两种情况下，future duplicate 不再反向把当前 idea 报成前移或关系漂移

原因：

- 这更符合 `plan-merge -> apply-merge -> recheck` 的闭环预期
- apply 之后重新跑 consistency，不应再被更晚的重复记录继续阻塞
- 先把 chapter-scoped 锚点收紧，后面再继续补 world-rule exception 的同章 / mixed-subject 边界会更稳

---

## 2026-05-23

### 决策：无 `knowledge_claims` 时，`world-rule` 先按主体局部窗口判断命中与 exception

当前状态：

- `world-rule conflict` 和 `world_rule_exception` 在有 `knowledge_claims` 时已经能做 subject/object 对齐
- 但如果 draft 没抽出 claim，之前会退回“整句里是否同时出现 subject / object”的粗匹配
- 这会让 mixed-subject 句子里另一主体的 object 被误算到当前 rule subject 身上，也会让同章 exception 的同义 object 只靠字面串命中

因此本轮先补一层 subject-local fallback：

- 没有 `knowledge_claims` 时，沿用主体窗口切分逻辑
- 只在当前 rule subject 附近抽取 knowledge signal
- `world-rule conflict` 与 `world_rule_exception` fallback 都改走这套局部信号，而不再直接扫整句

原因：

- 这样能把 mixed-subject 误报压掉
- 也能让同章 exception 在“身份 / 是谁”这类同义 object 上继续稳定生效
- 先把无 claim fallback 收紧，再继续做 chapter-scoped exception 的 explainer 展示会更稳

---

## 2026-05-23

### 决策：`world-rule` 的已落地 exception 不再只静默放行，report / plan 需要显式标记

当前状态：

- 同章或既有 `world_rule_exception` 已经可以在 consistency-check 中直接放行
- 但如果只是在底层返回“无冲突”，人工很难分辨这是“没命中规则”还是“命中了但已有正式豁免”

因此本轮补一层显式可见性：

- consistency report 新增 `exemptions`
- 对已命中的正式规则豁免，写出 `world-rule-exemption-applied`
- merge plan 在 clean gate 下也补一条 constraints explainer，直接标记对应 rule 的 `subject_scope / exception_scope`

原因：

- 这样 chapter-scoped exception 不再是隐式状态
- mixed-subject / split-subjects 边界可以在 clean gate 下继续被看见和复核
- 后续再细化 direct / review exemption summary 时，不需要重新设计 report 结构

---

## 2026-05-23

### 决策：已豁免 `world-rule` 与仍冲突 `world-rule` 尽量共享一条 grouped constraints 说明

当前状态：

- plan 已经能单独解释“多条冲突 rule”
- 也已经能单独解释“已有正式 exception 的 rule”
- 但两者分成两条 summary 时，噪音偏大，而且人工仍要自己拼出“哪些 rule 需要处理、哪些其实可以直接沿用”

因此本轮把 grouped summary 再收一层：

- 冲突 rule 继续保留原有策略 / impacts / targets 摘要
- 已豁免 rule 改成 `reuse-existing-exception`
- 对已豁免 rule 直接区分 `direct` 沿用和 `review` 复核
- 如果同一 idea 同时存在冲突 rule 和已豁免 rule，优先合并成同一条 constraints summary

原因：

- 这样人工在一个摘要里就能看完“哪些还要处理，哪些只需沿用”
- `shared-subject / split-subjects / mixed-subjects` 会直接影响 direct/review 判定，更适合放在同一条 grouped 说明里
- 后面继续细化 `exception_scope` 和 impact 类型时，也不需要再拆第二套 summary

---

## 2026-05-23

### 决策：`exception_scope` 先固定成三层 token，再往 impact 组合扩

当前状态：

- `same-chapter / prior-exception` 这种单层 scope 已经不够解释为什么某条 exception 只能 review
- 真正影响 direct / review 的至少还有主体范围和匹配来源

因此本轮先把 `exception_scope` 稳定成三层：

- `exception_scope_base`
- `exception_subject_scope`
- `exception_match_mode`

并据此派生第一层 review impact token：

- `constraints:review-subject-scope`
- `constraints:review-exception-chain`
- `canon:review-exception-evidence`

原因：

- 先把 token 层固定，后面细化 domain impact 组合不会再反复改字段名
- direct / review 判定也会更可解释，不再只靠 summary 文案
- 这能继续压缩后续 explainer 的自由文本噪音

---

## 2026-05-23

### 决策：不同 conflict 子组之间共享的 `write_shapes` 也单独上提

当前状态：

- `shared-conflict-actions` 已能处理“动作签名完全一致”的全体共享或子集共享
- 但如果两个 conflict 子组只共享一部分 `write_shapes`，整体动作签名不同，这部分 scene/event 写入说明仍会在逐条 rule 行里重复

因此这轮再补一条更细的 shape 共享行：

- 当不同 conflict 子组共享同一批 `direct/review write_shapes` 时，先提一条 `shared-conflict-write-shapes`
- 这条行按 `rules=...` 标记它覆盖的 conflict 子集
- 对应 rule 行再扣掉这些共享 shape token

原因：

- 先把“动作签名整体一致”和“只是写入形态局部一致”拆开
- 不改变 impacts 或策略判断，只继续压 scene/event 写入说明的重复
- 后续如果要把这些 shape 再映射到更自然的 explainer 文案，也有稳定的共享层可复用

### 决策：冲突侧直写路径的 timeline/outline 写入形态收敛成跨域 token

当前状态：

- `shared-conflict-write-shapes` 已能把不同 conflict 子组里完全相同的 `write_shapes` 上提
- 但 updating-cutoff / delaying-event 这两条直写路径的 scene/event 写入，仍会在不同子组之间重复出现

因此这轮补一层更稳定的跨域 token：

- 把 updating-cutoff 的直写组合收敛成 `cutoff-resolution:carry-forward`
- 把 delaying-event 的直写组合收敛成 `delay-resolution:rewrite-chapter`
- `exception-note:record` 这类别的跨域写入 token 继续单独处理

原因：

- 直接压掉冲突子组之间重复的 scene/event 文案，而不是继续堆叠新说明行
- 保留 `targets / domains / impacts` 提供的 timeline 与 outline 影响面，不需要在 `write_shapes` 再重复两次
- 给下一步继续压冲突直写路径的 impact 留出一致的 token 方向

### 决策：冲突侧成对的 exception note 写入形态收敛成 `exception-note:record`

当前状态：

- `story-beat:*` 已能压掉冲突子组之间重复的 scene/event 写入文案
- 但 `canon:record-exception-entry + constraints:append-exception-note` 这对 review write-shape 仍经常一起出现

因此这轮继续补一层跨域 token：

- 把这对 exception note 写入收敛成 `exception-note:record`
- `targets / domains` 继续负责保留 canon 与 constraints 的影响面

原因：

- 继续压掉冲突子组之间重复的 review write-shape 文案
- 让冲突侧跨域 write-shape token 不只覆盖 story beat，也覆盖 exception note
- 不改变 exemption 侧已有的更细 write-shape 语义

### 决策：冲突侧 `constraints:rewrite-cutoff + story-beat:carry-forward` 收敛成 `cutoff-resolution:carry-forward`

当前状态：

- `story-beat:*` 已能压掉冲突子组之间重复的 scene/event 写入文案
- 但 `resolve-world-rule-by-updating-cutoff` 这条直写路径仍会稳定带出 `constraints:rewrite-cutoff + story-beat:carry-forward`

因此这轮继续补一层跨域 token：

- 把这组直写组合收敛成 `cutoff-resolution:carry-forward`
- `impacts` 继续通过 `cutoff-resolution:update-placement` 保留执行语义

原因：

- 继续压掉冲突子组之间重复的 direct write-shape 文案
- 让冲突侧跨域 write-shape token 同时覆盖 cutoff resolution、story beat 和 exception note
- 不改变现有 impact 层的分组与判定

### 决策：冲突侧直写路径 impacts 收敛成 `delay-resolution:update-placement / cutoff-resolution:update-placement`

当前状态：

- `cutoff-resolution:carry-forward / delay-resolution:rewrite-chapter` 已能压掉不同 conflict 子组之间重复的 scene/event 写入文案
- 但 `shared-conflict-actions` 里仍会重复出现 updating-cutoff / delaying-event 的 impact 说明

因此这轮继续补一层 impact 收敛：

- 把 updating-cutoff 的 impact 收敛成 `cutoff-resolution:update-placement`
- 把 delaying-event 的 impact 收敛成 `delay-resolution:update-placement`
- `canon:record-exception` 这类非直写 impact 继续保留原样

原因：

- 让 `impacts` 和 `write_shapes` 的跨域 resolution 语义保持一致
- 继续压掉 conflict 子组之间重复的 scene/event impact 文案
- 仍保留 `targets / domains` 作为 timeline 与 outline 影响面的事实来源

### 决策：mixed conflict 子组里重复的结构字段上提成 `shared-conflict-structure-tokens`

当前状态：

- `shared-conflict-structure` 已能处理“策略、主体、direct/override、subject_scope 全都一致”的整组共享
- 但在 mixed direct/review conflict 子组里，经常只有 `direct / override / subject_scope` 重复，而 `strategies / subjects` 不同

因此这轮再补一条更细的结构共享行：

- 当不同 conflict 子组共享同一批 `direct / override / subject_scope` 时，先提一条 `shared-conflict-structure-tokens`
- 这条行按 `rules=...` 标记它覆盖的冲突子集
- 各自的 `rule-xxx:` 行继续只保留不同的 `strategies / subjects`

原因：

- 不破坏现有 `shared-conflict-structure` 代表“完整结构签名一致”的语义
- 继续压掉 mixed 子组里重复的结构字段
- 给下一步继续收 `subjects / strategies` 文案留下独立层次

### 决策：mixed conflict 子组里重复的 `subjects / strategies` 上提成 `shared-conflict-rule-tokens`

当前状态：

- `shared-conflict-structure-tokens` 已能把 mixed 子组里重复的 `direct / override / subject_scope` 上提
- 但 `rule-xxx:` 行里仍经常重复出现同一批 `strategies=` 或 `subjects=`

因此这轮再补一条更细的 rule 标签共享行：

- 当不同 conflict 子组共享同一批 `strategies=` 或 `subjects=` 时，先提一条 `shared-conflict-rule-tokens`
- 这条行按 `rules=...` 标记它覆盖的冲突子集
- 各自的 `rule-xxx:` 行再扣掉这些已共享的标签字段

原因：

- 继续压掉 mixed 子组里逐条重复的 rule 标签文案
- 不改变现有 `shared-conflict-structure` 和 `shared-conflict-structure-tokens` 的职责边界
- 给下一步继续压 rule 级 `domains / targets` 留出更干净的逐条行

### 决策：mixed conflict 子组里重复的 `domains / targets` 上提成 `shared-conflict-rule-context`

当前状态：

- `shared-conflict-rule-tokens` 已能把 mixed 子组里重复的 `subjects / strategies` 上提
- 但逐条 `rule-xxx:` 行里仍可能重复出现同一批 `domains=` 或 `targets=`

因此这轮再补一条更细的 context 共享行：

- 当不同 conflict 子组共享同一批 `domains=` 或 `targets=` 时，先提一条 `shared-conflict-rule-context`
- 这条行按 `rules=...` 标记它覆盖的冲突子集
- 各自的 `rule-xxx:` 行再扣掉这些已共享的 context 字段

原因：

- 继续压掉 mixed 子组里逐条重复的 rule 级 context 文案
- 不改变全局 `shared-conflict-context` 代表“所有 conflict 都共享”的语义
- 给下一步继续收 rule 级 `direct/review shape` 组合留下更干净的逐条行

### 决策：mixed conflict 子组里重复的 `direct/review impacts` 上提成 `shared-conflict-rule-impacts`

当前状态：

- `shared-conflict-rule-context` 已能把 mixed 子组里重复的 `domains / targets` 上提
- 但逐条 `rule-xxx:` 行里仍可能重复出现同一批 `direct_impacts=` 或 `review_impacts=`

因此这轮再补一条更细的 impact 共享行：

- 当不同 conflict 子组共享同一批 `direct_impacts=` 或 `review_impacts=` 时，先提一条 `shared-conflict-rule-impacts`
- 这条行按 `rules=...` 标记它覆盖的冲突子集
- 各自的 `rule-xxx:` 行再扣掉这些已共享的 impact 字段

原因：

- 继续压掉 mixed 子组里逐条重复的 rule 级 impact 文案
- 不改变更上层 `shared-conflict-actions` 代表“整组动作签名共享”的语义
- 给下一步继续收 rule 级 `direct/review write-shape` 组合留下更干净的逐条行

---

## 2026-05-23

### 决策：被共享行完全覆盖的 conflict rule 不再保留空占位

当前状态：

- `shared-conflict-context / actions / structure` 已经能把大量重复信息上提
- 但当某条 conflict rule 的所有字段都被共享行吃掉之后，逐条列表里还会剩一个空的 `rule-xxx:`

因此这轮把这类空占位直接拿掉：

- 如果 conflict rule 在扣掉共享 context、actions、structure 后没有任何剩余字段，就不再输出单独的 `rule-xxx:` 行
- 仍由对应的共享行承担可读性和定位作用

原因：

- 空占位不会提供额外信息，只会增加扫描噪音
- 用户仍能通过 `shared-conflict-structure rules=...` 定位哪些 rule 被一起收敛
- 这样后续继续处理剩余 write-shape 差异时，列表会更干净

---

## 2026-05-23

### 决策：冲突元信息也单独上提成 `shared-conflict-structure`

当前状态：

- `shared-conflict-actions` 已经能压掉冲突动作层的全体共享和子集共享
- 但在很多多冲突 case 里，逐条 rule 行里还会重复同一套策略、`direct / override` 计数和主体范围

因此这轮再补一条更轻的结构共享行：

- 当一批 conflict 连策略列表、`direct / override` 计数、`subjects / subject_scope` 都一致时，先提一条 `shared-conflict-structure`
- 对应 rule 行只再保留自己的差异字段
- 如果某条 rule 在 context、actions、structure 三层都被上提干净，逐条行就只剩 `rule-xxx:`

原因：

- 先把“做什么”“怎么做”和“这条 rule 自己还剩什么差异”彻底拆开
- 不改变任何 merge 语义，只减少多冲突场景里的横向对照成本
- 后续再细化剩余 write-shape 文案时，也不会再被这些固定元信息干扰

---

## 2026-05-23

### 决策：冲突动作共享不只看“全体一致”，同签名子集也单独上提

当前状态：

- `shared-conflict-actions` 已经能压掉“所有 conflict 都完全相同”的动作 token
- 但如果是 3 条以上 conflict，只有其中一个子集动作签名一致，剩余 rule 不同，这些局部共享动作还会留在逐条 rule 行里重复

因此这轮把共享动作再放宽一层：

- 继续保留“全体共享”的 `shared-conflict-actions`
- 如果某个 conflict 子集在扣掉全体共享值后，剩余 `direct/review impacts` 与 `write_shapes` 仍完全一致，就再提一条带 `rules=...` 的 subset 级 `shared-conflict-actions`
- 对应 rule 行再扣掉这条 subset 共享动作

原因：

- 先把“全体共享”和“局部共享”拆开
- 不要求所有 conflict 都同形，部分重复也能继续压缩
- 这样后续如果再细化到 write-shape 层的部分共享，也可以复用同一套签名分组逻辑

---

## 2026-05-23

### 决策：多条 `world-rule conflict` 动作层完全相同时，再上提 `shared-conflict-actions`

当前状态：

- `shared-conflict-context` 已经能压掉多条 conflict 行之间重复的 `domains / targets`
- 但当多条 conflict 连 `direct/review impacts` 和 `write_shapes` 也完全相同时，这些动作 token 仍会在每条 rule 行里重复

因此这轮再补一条冲突动作共享行：

- 当多条 conflict 共享同一批 `direct/review impacts` 与 `write_shapes` 时，先提一条 `shared-conflict-actions`
- 这条行只承载动作层共享 token
- 每条 conflict 行再扣掉这些共享动作，只保留策略、主体范围和差异字段

原因：

- 先把冲突动作层里完全相同的 token 再上提一层
- 不会改变冲突分流和 readiness，只继续压缩 summary 噪音
- 后续如果再遇到“部分相同、部分不同”的冲突动作，也可以继续沿用同一套共享值裁剪逻辑

---

## 2026-05-23

### 决策：多条 `world-rule conflict` 共享同一批 context 时，先上提 `shared-conflict-context`

当前状态：

- `shared-world-rule-context` 已经能压掉 conflict 行和 exemption 行之间共同拥有的 `domains / targets`
- 但在纯多冲突场景里，冲突行之间的 `domains / targets` 仍会整条重复

因此这轮先补一条 conflict 专用的共享行：

- 当至少两条 conflict rule 共享同一批 `domains / targets` 时，先提一条 `shared-conflict-context`
- 这条行只承载 conflict 行之间公共的 context
- 每条 conflict 行再扣掉这些共享字段，只保留自己的策略、impact、write-shape

原因：

- 先把冲突行内部的公共上下文提出来
- 不改变冲突策略和 readiness，只压缩说明层噪音
- 后续如果继续压冲突行之间共享的 `impacts / write_shapes`，可以继续沿用这套分层

---

## 2026-05-23

### 决策：`world-rule conflict` 与 exemption 共存时，先上提 `shared-world-rule-context`

当前状态：

- `shared-exemption-base` 和 `shared-exemption-review` 已经能压掉 exemption 行内部的重复
- 但如果同一条 idea 同时还有 `world-rule conflict`，冲突行和 exemption 行仍会一起重复 `canon / constraints` 这类公共 `domains / targets`

因此这轮先补一条更外层的 context 行：

- 当 conflict 与 exemption 共存时，先提一条 `shared-world-rule-context`
- 这条行只承载所有 rule 共用的 `domains / targets`
- conflict 行和 exemption 行各自再扣掉这些公共 context，只保留自己的策略、impact、write-shape

原因：

- 先把“公共上下文”与“各自处理动作”拆开
- 不会把 conflict 的动作 token 和 exemption 的复用 token 混成一层
- 后续如果继续压 conflict 行之间的重复，也可以复用同一层 context 思路

---

## 2026-05-23

### 决策：`direct / review` 混合 exemption 先再提一条 `shared-exemption-base`

当前状态：

- 多条 review exemption 已经会把公共 review token 上提到 `shared-exemption-review`
- 但如果同一组 exemption 里同时混有 `direct` 和 `review`，公共的 `impacts / targets / domains` 仍会在各自 rule 行里重复展开

因此这轮再补一层更基础的共享行：

- 对所有 exemption 共用的基础 token，先提一条 `shared-exemption-base`
- 这层只承载公共 `impacts / targets / domains`，不碰 review 专属 token
- `shared-exemption-review` 仍只负责多条 review exemption 的共享 review token

原因：

- 先把混合 `direct / review` 场景里的公共噪音压下去
- 避免 `shared-exemption-base` 和 `shared-exemption-review` 写同一批 review token
- 后续如果继续压 conflict rule 与 exemption line 共存时的重复，也可以直接复用这套分层

---

## 2026-05-23

### 决策：多条 exemption 共用同一批 review token 时，先上提 `shared-exemption-review`

当前状态：

- `same-chapter` 和 `prior-exception` 的 review 说明层已经基本对齐
- 但当一条 idea 同时命中多条已豁免 rule，而且这些 rule 共享同一批 `review_impacts / review_write_shapes / targets` 时，grouped summary 仍会在每条 rule 行里重复展开

因此这轮先做一层 summary 压缩：

- 对共享的 review token，先提一条 `shared-exemption-review`
- 每条 rule 继续保留自己的 `reuse-existing-exception` 行
- 但公共 `review_impacts / review_write_shapes / targets` 从逐条行里扣掉，只在共享行里写一次

原因：

- 先减少多条 exemption review 的重复噪音
- 不改变 apply / review 语义，只收紧说明层呈现
- 后续如果继续做 `direct / review` 混合压缩，也可以复用同一套“共享值上提”规则

---

## 2026-05-23

### 决策：`prior-exception` 先拆成跨 `canon / constraints / timeline / outline` 的 review impacts

当前状态：

- `prior-exception` 已经能被识别
- 但如果 review impacts 只写成抽象 token，人工仍不知道应优先复核哪一层

因此本轮先做一层保守拆分：

- `canon:review-exception-continuity`
- `constraints:review-exception-chain`
- `timeline:review-post-exception-beat`
- `outline:review-post-exception-scene`

原因：

- 这样“沿用旧 exception 但还要复核什么”会直接落到 domain 级别
- 后面即使继续细化到更具体的写入动作，也可以复用这层 domain token
- 这比继续堆自由文本 summary 更稳定

影响：

- grouped summary 里不再只写抽象 review，而会直接带出 `review-exception-continuity / review-exception-chain / review-post-exception-beat / review-post-exception-scene`
- 后续如果继续细化到“追加 beat / 改写既有 beat / 只补注释”，可以直接在这些 token 之上继续分层

---

## 2026-05-22

### 决策：`world-rule` 的 merge plan 开始按命中的 claim 精确绑定多条 rule

当前状态：

- consistency-check 已经能在单条 idea 上产出多条 `world-rule conflict`
- 但 merge plan 之前仍会按 subject 取第一条 claim，导致多条 rule 可能共用同一个 exception object

因此本轮把 world-rule 的下游绑定再收紧一层：

- 单条 idea 中如果抽出多条 `knowledge_claims`
- 每条 world-rule issue 都要把自己命中的 claim 写进 `issues[].details`
- `plan_idea_merge` 的 exception 输入直接消费这组命中结果，而不是在 merge 层重新猜 claim

原因：

- 否则多 rule 场景下会把错误 object 写进 `world_rule_exceptions`
- 先让 issue 层把“这条 rule 命中了哪条 claim”说清楚，下游 plan/apply 才能稳定
- 这为后续做多 rule explainers 分组提供了结构化锚点

---

## 2026-05-22

### 决策：`world-rule` 检测与例外豁免开始复用 `knowledge_claims` 做 subject/object 协同

当前状态：

- `knowledge object` 已有保守同义归一
- 但 `world-rule conflict` 和 `world_rule_exception` 之前仍主要依赖原句字面命中
- 这会让 `组织首领身份 / 组织首领是谁` 这类 object 在 world-rule 层出现漏报或豁免失效

因此本轮固定一个新的输入边界：

- world-rule 检测优先读取 draft 中已抽出的 `knowledge_claims`
- rule 的 subject / object 命中，先走结构化 claim，再退回原句字面
- exception 的 subject / object 匹配，也改为优先复用同一套 claim / object matcher

原因：

- 这样可以让 knowledge-state 和 world-rule 共用同一套 object 解释层
- 能最短路径减少 world-rule 的同义表达漏报
- 先把单 claim、单 subject、单 rule 的闭环收紧，后续再继续补多 claim / 多 rule 的边界

---

## 2026-05-21

### 决策：`knowledge object` 先采用“保守同义归一 + 对象家族匹配”

当前状态：

- 原先的 `knowledge-state` object matching 主要依赖包含关系和少量字符重叠
- 这会让“不是一路 / 不是同一阵营”“身份 / 是谁”“内鬼 / 泄密”这类常见同义表达有时能撞上，但也会把“有人调查”误判成“有人泄密”

因此本轮先固定一个保守边界：

- 只为少量高频 object 家族做归一：
  `身份 / 是谁`、`内鬼 / 泄密`、`不是一路 / 不是同一阵营`
- 对可识别的对象改用家族签名匹配，而不是继续放任低门槛字符重叠
- 对剩余兜底匹配收紧条件，优先压掉共享前缀带来的误报

原因：

- 这批 object family 已经反复出现在当前 demo 和测试样本里
- 它们足够高频，值得先用确定性规则收进来
- 先把最明显的漏报 / 误报都压住，再考虑更宽的 object graph 推理

---

## 2026-05-21

### 决策：`title-based drift` 先允许“安全的扩写标题部分匹配”

当前状态：

- consistency-check 已有基于 title 的 chapter drift 检查
- 但之前只接受规范化后的完全相等
- 真实工作区里，同一事件 / 场景标题经常会被补上地点括注、卷内副标题或短说明

因此本轮固定一个保守边界：

- 对规范化后长度足够的标题，允许双向包含式匹配
- 先覆盖“主标题 + 括注 / 副标题”这类常见扩写
- 暂不引入更宽的模糊相似度匹配

原因：

- 这能直接补上 title-based drift 的一批漏报
- 双向包含比通用模糊匹配更可解释，也更容易控制误报
- 先把最常见的扩写标题收进来，后续再继续细化 object matching 和更复杂的 drift case

---

## 2026-05-20

### 决策：`knowledge-state conflict` 命中更早与更晚记录时，优先只保留更早冲突

当前状态：

- consistency-check 已能同时读取 timeline / outline / canon 的知情记录
- 同一知情事实如果既有更早记录、又有更晚记录，之前会在一条 idea 上同时产出两条 `knowledge-state conflict`

因此本轮固定一个优先级边界：

- 只要更早记录已经足够说明“这不是首次 / 关键知情点”，就不再额外报告未来同事实的重复漂移

原因：

- 对 merge gate 来说，更早记录已经构成充分 blocker
- 再叠加未来重复记录，只会放大噪音，不会提供新的决策信息
- 先把冲突优先级收紧，后续再继续细化 title-based drift 和 object matching

---

## 2026-05-20

### 决策：`knowledge-state` 和 `relationship-history` 先补“后文复述 / 未来重复状态”豁免

当前状态：

- claim-level `knowledge-state` 检查已经可用
- relationship-history 已有“中间状态转移豁免”
- 但未来章节里的复述型记录仍会产生噪音

因此本轮先固定两条边界：

- 如果未来知识记录明显带有“再次 / 重新 / 已经”类复述信号，则不把它当作新的首次知情冲突
- 如果关系图谱已经出现“同状态 -> 不同状态 -> 同状态”的路径，且 draft 本身带有“重新 / 再次”信号，则允许豁免未来重复同状态记录

原因：

- 这两类误报在实际大纲里很常见
- 它们可以用确定性规则压掉，不需要先上完整图谱推理
- 先减少噪音，后续 merge plan 的结构化输入才更稳定

---

## 2026-05-23

### 决策：`prior-exception` 先继续拆成稳定的 `write_shapes`

当前状态：

- `prior-exception` 已经能稳定识别
- grouped summary 已经能写出 `canon / constraints / timeline / outline` 四层 review impacts
- 但这些 token 仍偏“影响面”，还不够接近实际写入动作

因此这轮先不改 apply 逻辑，而是在 summary 层继续细分一层稳定 token：

- direct reuse 先写成 `reuse-existing-exception-record / reuse-existing-exception-note`
- prior review 先写成 `keep-existing-exception-record / carry-forward-exception-note`
- 如果当前 draft 仍需要 timeline / outline 落地，再补 `append-post-exception-beat / append-post-exception-scene-note`
- 如果后续命中已有 event / scene 更新，再允许扩到 `rewrite-post-exception-*`

原因：

- 先把“要复核什么”从 domain 提示推进到更接近执行的动作组合
- 这样 grouped summary 不用立刻引入更多结构，也能更稳定地指导人工决策
- 保持 token 级表达，后续如果继续做 apply / review 分流，还能直接复用这层信号

---

## 2026-05-23

### 决策：`create-event-and-scene` 命中既有记录时，`write_shapes` 先按 `rewrite` 解释

当前状态：

- `prior-exception` 的 grouped summary 已经能写出 `append-post-exception-*`
- 但默认 merge 输入的 strategy 还是统一写成 `create-event-and-scene`
- 这会把“其实只是重写已有 event / scene”的 case 误说成 append

因此这轮先只在 summary 判定层补一层保守识别：

- 如果默认输入里的 `event_id` 已存在，timeline 侧改写为 `rewrite-post-exception-beat`
- 如果默认输入里的 `scene_id` 已存在，outline 侧改写为 `rewrite-post-exception-scene-note`
- apply 层暂不改 strategy，先保持兼容

原因：

- 先让 explainer 对齐真实写入形态，减少 review 噪音
- 不必为了说明层收紧，马上改动 merge apply 入口
- 这层判定后续还能继续扩到 `annotate / carry-forward`

---

## 2026-05-23

### 决策：没有 timeline / outline 写入时，`prior-exception` 的 review 先收敛到纯 `annotate`

当前状态：

- `prior-exception` 已能分出 `append` 和 `rewrite`
- 但还有一类 case，实际上不需要继续动 event / scene
- 这类 case 如果继续写成 `carry-forward`，会误导成还有后续时间线改动

因此这轮先把这类 review 说明收紧成：

- `canon:keep-existing-exception-record`
- `canon:annotate-existing-exception-record`
- `constraints:annotate-existing-rule-note`

同时不再补：

- `timeline:review-post-exception-beat`
- `outline:review-post-exception-scene`
- `timeline/events.json`
- `outline/scene-index.json`

原因：

- 先把“只是补注释”与“还要带后续 beat / scene”拆开
- 这样 grouped summary 更接近真实执行成本
- 后续再继续决定 `annotate` 和 `carry-forward` 的更细切换条件

---

## 2026-05-23

### 决策：`prior-exception + local-signal` 且无可落地 event/scene 时，先只提示 evidence

当前状态：

- `local-signal` 已经能命中正式 exception
- 但如果没有可落地的 `event_id / scene_id`，这轮其实很难稳定判断后续 chain 要不要变
- 继续默认写成 `carry-forward`，会把“证据复核”误说成“链路重写”

因此这轮先收紧成更保守的说明：

- 保留 `canon:review-exception-evidence`
- 保留 `annotate-existing-exception-record / annotate-existing-rule-note`
- 不再默认补 `constraints:review-exception-chain`
- `create-event-and-scene` 也只有在带着可落地 `event_id / scene_id` 时，才会落成 `append-post-exception-*`

原因：

- 先把“只有证据需要复核”和“确实要改 chain”拆开
- 这样 local-signal case 的 grouped summary 噪音更低
- 后续可以继续把 claim-match 路径的切换条件做细，而不用回头再拆这层混淆

---

## 2026-05-23

### 决策：`claim-match` 的叙事型 idea 即使没有 event/scene target，也先保留 `carry-forward`

当前状态：

- 纯设定型 `claim-match` 已经能收敛成 `annotate`
- 但 `reveal / twist / backstory` 这类叙事型 idea，即使这轮没落成具体 event / scene，也往往仍然代表一段需要延续的 exception chain

因此这轮先按 kind 做一层保守分流：

- `world` 这类设定型 case 继续走 `annotate-existing-rule-note`
- `reveal / twist / backstory / event / scene / death` 这类叙事型 case，在 `prior-exception + claim-match` 下仍保留 `carry-forward-exception-note`
- 但如果没有 timeline / outline write-shape，仍不补 `timeline:review-*` / `outline:review-*`

原因：

- 先把“只是补说明”和“剧情链仍要续接”拆开
- 不要求现在就精确落到 event / scene，先把 constraints 层的说明语义拉直
- 下一步再继续收紧 mixed-subject / split-subjects 上的切换条件

---

## 2026-05-23

### 决策：`claim-match` 的叙事型 idea 只有在 `shared-subject` 下才默认 `carry-forward`

当前状态：

- 叙事型 `claim-match` 已经能在无 event / scene target 时保留 `carry-forward`
- 但一旦落到 `split-subjects / mixed-subjects`，这条 exception chain 就不再明显属于同一主体链

因此这轮再收紧一步：

- `shared-subject + claim-match + narrative kind` 仍可保留 `carry-forward-exception-note`
- `split-subjects / mixed-subjects + claim-match` 即使是 narrative kind，也先退回 `annotate-existing-rule-note`
- 同时继续补 `constraints:review-subject-scope`

原因：

- 先把“剧情链仍要续接”和“主体范围已经拆开”分成两层判断
- 避免多主体 case 误看成可以沿用同一条 exception chain
- 后续只需要继续收紧 `mixed-subjects + local-signal`，不必回头重拆 shared-subject 路径

---

## 2026-05-23

### 决策：`local-signal` 的多主体边界按“窗口内是否混主体”来判

当前状态：

- `local-signal` 已经能和 `claim-match` 分开
- 但多主体时，并不是所有 case 都该直接升级到 `review-subject-scope`
- 如果别的主体只出现在目标主体窗口之外，这轮其实仍然更接近“证据不足”，而不是“主体链混乱”

因此这轮把 `local-signal` 再拆一层：

- 若别的主体没有进入 rule subject 的局部窗口，继续保留 `shared-subject-local-signal`
- 若局部窗口内已经混进别的主体，升级成 `mixed-subjects-local-signal`
- merge summary 只在后者额外补 `constraints:review-subject-scope`

原因：

- 先把“证据不够”与“主体范围不清”拆开
- 这样 local-signal 场景不会因为文本里出现第二个人名就过度升级
- 后续同一套窗口判断还能继续复用到 same-chapter exemption 的说明收敛

---

## 2026-05-23

### 决策：把 `same-chapter exemption` 的 review 说明层对齐到 `prior-exception`

当前状态：

- `prior-exception` 已经能稳定分出 `evidence-only / review-subject-scope / timeline-outline review`
- `same-chapter exemption` 之前虽然能 direct/review，但 review 侧的说明粒度还不够一致

因此这轮把 review 侧说明统一到同一套分层：

- 若涉及 timeline / outline 写入，补 `timeline:review-same-chapter-beat / outline:review-same-chapter-scene`
- 若是 `local-signal` 且窗口外才出现别的主体，只保留 `review-exception-evidence`
- 若窗口内已混主体，再额外补 `review-subject-scope`

原因：

- 先把 `same-chapter` 和 `prior-exception` 的 explainers 拉到同一语义层
- 这样下一步只需要继续做 grouped summary 去重，不必再维护两套不同的 review 规则
- 同时能减少“同一类 review，在不同 scope 下说法不一致”的噪音

---

## 2026-05-20

### 决策：为 legacy workspace 增加正式的 intake backfill / repair 脚本入口

当前状态：

- demo workspace 已经暴露出“idea 还在，但 intake draft / view / path 元数据丢失”的历史问题
- 继续靠手工 patch JSON 不能算正式工作流能力

因此本轮补一个正式入口：

- `scripts/backfill_intake_drafts.py`
- 默认只修需要修的 pending idea
- 可按 `--all-pending` / `--all-ideas` 批量回写
- 可按 `--force-rebuild` 重建已有 draft

原因：

- 让 legacy workspace repair 进入可重复执行的脚本层
- 让后续 consistency / merge 不再依赖手工补 state 文件
- 先把 repair 路径固定，后续再继续增加 explainers 和批量策略

---

## 2026-05-20

### 决策：`plan_idea_merge` 的 `proposed_actions` 改为 domain-specific explainers

当前状态：

- 原先的 `proposed_actions` 只会说“并入某个 domain”
- `timeline_merge_inputs` 已经足够接近执行层，但 plan 展示还没有把这些信息真正解释出来

因此本轮不新开平行字段，而是直接升级现有 `proposed_actions`：

- 保留列表结构和兼容字段
- 补充 `summary`
- 补充 `merge_input_id`
- 补充 `readiness`
- 补充 `planned_writes`
- 补充 `source_signals`

原因：

- 这样能最短路径把 plan 从“领域提示”推进到“执行说明”
- 不需要强制上游或 HTML 重新适配另一套字段名
- 后续如果继续细化 explainers，也仍可沿着同一数据结构扩展

---

## 2026-05-20

### 决策：把 `knowledge-state` 与 `world-rule exception` 正式收进 `state/canon-index.json`

当前状态：

- `relationships[]` 已经进入 `state/canon-index.json`
- `knowledge-state conflict` 已能稳定产出 claim 和 issue
- `document-world-rule-exception` 之前只会改 `constraints/constraints.json`

因此本轮把 canon 机器真相源再往前推进一层：

- `state/canon-index.json -> knowledge_states[]`
- `state/canon-index.json -> world_rule_exceptions[]`
- `plan_idea_merge` 新增 `upsert-canon-knowledge-state / update-existing-knowledge-state`
- `document-world-rule-exception` 同步把例外说明写入 canon
- consistency-check 开始读取这两类 canon 记录，作为后续 merge / check 的正式输入

原因：

- 让 `knowledge-state` 不再只依赖 timeline / outline 的文本命中
- 让 world-rule 例外不再只是 constraints 里的备注，而是可回流的机器事实
- 先把 canon 真相源固定，再继续细化图谱推理和例外边界

---

## 2026-05-24

### 决策：逐条 world-rule explainer 不再重复输出泛化 `impacts=` / `write_shapes=`

当前状态：

- `shared-conflict-actions` 这一层已经会把和 `direct_/review_` 桶完全重合的 `impacts=` / `write_shapes=` 扣掉
- 但逐条 `rule-xxx:` 明细行，以及 exemption 的 `reuse-existing-exception` 明细行，之前仍可能同时输出：
  `impacts=...` + `direct_impacts=...` / `review_impacts=...`
- `write_shapes=` 也有同样问题，导致同一个 token 在同一行里重复两次

因此这轮把同样的去重规则下沉到 rule 行本身：

- 如果某条 rule 行里的 `impacts=` 只是 `direct_impacts` 与 `review_impacts` 的并集，就不再输出这层泛化字段
- 如果某条 rule 行里的 `write_shapes=` 只是 `direct_write_shapes` 与 `review_write_shapes` 的并集，也不再输出这层泛化字段
- 这个规则同时应用到 conflict rule 行和 exemption rule 行

原因：

- grouped summary 的目标是压缩噪音，不应该在明细层把同一 token 再写一遍
- 这样生成出来的 plan diff 会更稳定，人工扫 `rule-xxx:` 时也更容易直接看到“哪些是 direct、哪些是 review”
- 不改数据模型，只继续收紧现有 explainer 的表达层

---

## 2026-05-24

### 决策：`shared-exemption-review` 不再重复 `shared-exemption-base` 已覆盖的公共 token

当前状态：

- `shared-exemption-base` 已经负责 direct / review 混排 exemption 里的公共 `domains / impacts / targets`
- `shared-exemption-review` 负责多条 review exemption 共享的 review token
- 但在“1 条 direct + 多条 review”混排时，`shared-exemption-review` 之前仍会把
  `canon:reuse-exception / constraints:reuse-exception` 以及同一批 `domains / targets`
  再写一遍

因此这轮把 review 共享行也对齐到“先扣 base、再输出 review 专属”的规则：

- `shared-exemption-review` 输出前，先减掉 `shared-exemption-base` 已经覆盖的
  `domains / targets / impacts / write_shapes`
- 只保留 review 专属补充，例如
  `canon:review-exception-continuity / constraints:review-exception-chain`

原因：

- 这样 `shared-exemption-base` 和 `shared-exemption-review` 的职责边界才真正稳定
- 混排 case 的 grouped summary 不会再把同一批公共 token 写两次
- 仍然不改数据结构，只收紧 explainers 的去重逻辑

---

## 2026-05-24

### 决策：多条 exemption 共用同一批 scope 元信息时，先上提 `shared-exemption-scope`

当前状态：

- `shared-exemption-base` 已经负责公共 `domains / targets / reuse-exception impacts`
- `shared-exemption-review` 已经负责公共 `review_impacts / review_write_shapes`
- 但多条 `reuse-existing-exception` 行里，`subject_scope / exception_scope / exception_scope_base / exception_subject_scope / exception_match_mode`
  这批 scope 元信息之前仍会逐条重复

因此这轮再补一条更窄的 scope 共享行：

- 当多条 exemption 共享同一批 scope 元信息时，先提一条 `shared-exemption-scope`
- 这条行按 `rules=...` 标记它覆盖的 exemption 子集
- 对应的 `rule-xxx: reuse-existing-exception` 行再扣掉这些已共享的 scope token

原因：

- 这样 exemption 侧的“base / review / scope”三层职责会更清楚
- mixed-subject / prior-exception / same-chapter 混排时，规则行能更快暴露真正不同的部分
- 仍然不改数据结构，只继续压缩 grouped summary 的重复元信息

---

## 2026-05-24

### 决策：多条 exemption 共用同一批 rule 元信息时，先上提 `shared-exemption-rule-tokens`

当前状态：

- `shared-exemption-scope` 已经能把重复的 `subject_scope / exception_scope_*` 上提
- 但多条 `reuse-existing-exception` 行里，`direct / review / subjects` 这批 rule 元信息仍可能逐条重复

因此这轮再补一条更轻的 rule-token 共享行：

- 当多条 exemption 共享同一批 `direct / review / subjects` 时，先提一条 `shared-exemption-rule-tokens`
- 这条行按 `rules=...` 标记它覆盖的 exemption 子集
- 对应的 `rule-xxx: reuse-existing-exception` 行再扣掉这些已共享的 rule token

原因：

- 让 exemption 侧的规则行更快收敛到“exception id + 真正差异字段”
- 不和 `shared-exemption-scope`、`shared-exemption-base`、`shared-exemption-review` 混职责
- 仍然不改数据结构，只继续压缩 grouped summary 的重复 rule 元信息

---

## 2026-05-24

### 决策：只剩 exception id 的 exemption 壳行收成 `shared-exemption-links`

当前状态：

- `shared-exemption-scope` 和 `shared-exemption-rule-tokens` 已经能把大部分重复元信息上提
- 某些 mixed exemption case 下，部分 `rule-xxx: reuse-existing-exception` 行扣掉这些共享 token 后，只会剩 `exceptions=...`
- 继续保留这类行，信息增量已经很低，只是在逐条重复 `rule-xxx:` 壳子

因此这轮再补一条更窄的映射行：

- 当至少两条 exemption 行在扣掉共享 token 后只剩 `exceptions=...`，且当前同组里仍有别的 richer exemption 行需要单独保留时，
  先提一条 `shared-exemption-links`
- 这条行承载 `rule_id -> exception_id` 的映射
- 对应的壳行不再单独输出

原因：

- 这样仍保留 rule 和 matched exception 的对应关系
- 但能去掉多条只差 exception id 的空壳行
- 继续维持“shared 行负责公共结构，rule 行负责剩余差异”的输出原则

---

## 2026-05-24

### 决策：多条匹配 exception 并存时，优先选最贴近当前 chapter 的那条

当前状态：

- `world_rule_exceptions[]` 允许同一 rule 在不同 chapter 留下多条正式 exception
- 之前 `_matching_world_rule_exception()` 只要命中就按存储顺序返回第一条
- 这会让“更早的 prior exception 写在前面、当前章 same-chapter exception 写在后面”的 case
  被误选成 prior exception，进而把本来可 direct 的 merge plan 降成 review

因此这轮把 exception 选择策略收紧成“更贴近当前 draft chapter 的优先”：

- 在多个 exception 都匹配同一 rule / subject / object 时，先优先当前章 same-chapter
- 否则再退回更早的 prior exception
- 如果都是 earlier match，则优先 chapter 更接近当前 draft 的那条

原因：

- 这更符合 exception chain 的语义：当前章已有正式例外时，不应再回退到更早的链路节点
- consistency report 和 merge plan 的 direct/review 判定会更稳定
- 这是规则边界修正，不改数据结构

---

## 2026-05-24

### 决策：relationship repeat hint 补充 `再度`

当前状态：

- future relationship repeat after transition 的豁免目前依赖重复提示词
- 现有词表已经覆盖 `重新 / 再次 / 又`
- 但中文大纲里也常见 `再度结盟 / 再度和解` 这类表达，之前不会命中 repeat hint

因此这轮先补一个保守词表扩展：

- 把 `再度` 加进 `RELATIONSHIP_REPEAT_TOKENS`

原因：

- 这类 wording 和 `再次` 的语义足够接近，适合直接走同一确定性规则
- 能减少 relationship-history 在“有中间状态转移、且未来同状态已落地”场景下的误报
- 这是边界扩展，不改数据结构，也不改变原有 repeat-hint 机制

---

## 2026-05-24

### 决策：relationship 词表补充 `重归于好 / 反目`

当前状态：

- relationship-history 目前主要靠少量稳定 token 映射关系状态
- `和解 / 决裂` 已能工作
- 但中文大纲里也很常见 `重归于好`、`反目` 这类表达，之前不会命中对应状态

因此这轮补一个保守的同义词扩展：

- `重归于好 -> reconciled`
- `反目 -> ruptured`
- 同时把 `重归于好` 也纳入 relationship repeat hint，因为它天然带有“重新恢复关系”的语义

原因：

- 这两类表达在角色关系 beat 里足够高频
- 它们能直接复用现有 `relationship-history` 状态机，不需要引入更复杂的 NLP
- 这是词表边界扩展，不改数据结构

---

## 2026-05-24

### 决策：relationship 词表继续补充 `冰释前嫌 / 翻脸`

当前状态：

- `重归于好 / 反目` 已经接入 relationship 状态词表
- 但中文大纲里也很常见 `冰释前嫌`、`翻脸` 这类表达
- 其中 `冰释前嫌` 和 `重归于好` 一样，除了是 `reconciled` 状态，本身也带有 repeat/restart 的语义

因此这轮继续做一层保守扩展：

- `冰释前嫌 -> reconciled`
- `翻脸 -> ruptured`
- 同时把 `冰释前嫌` 纳入 relationship repeat hint

原因：

- 这是对现有 reconciled / ruptured 词表的直接补全
- 能继续减少 relationship-history 在常见中文写法上的漏判与误报
- 仍然只是词表边界扩展，不改数据结构

---

## 2026-05-24

### 决策：relationship 词表继续补充 `破镜重圆 / 闹翻`

当前状态：

- `冰释前嫌 / 翻脸` 已经接入 relationship 词表
- 但中文大纲里同样高频的还有 `破镜重圆`、`闹翻`
- `破镜重圆` 与 `重归于好 / 冰释前嫌` 一样，也自带“关系重新修复”的语义

因此这轮继续做一层保守扩展：

- `破镜重圆 -> reconciled`
- `闹翻 -> ruptured`
- 同时把 `破镜重圆` 纳入 relationship repeat hint

原因：

- 继续沿现有 reconciled / ruptured 状态机补齐高频中文写法
- 能再压掉一批 relationship-history 的漏判与误报
- 仍然只是词表边界扩展，不改数据结构

---

## 2026-05-27

### 决策：speculative 外层和内层主体之间夹着指代修饰时，仍不能把内层 `知道...` 提升成 direct claim

当前状态：

- 前一轮已经拦掉了 `怀疑 / 猜测 / 听说 / 觉得 / 担心` 直接包住另一主体的 case
- 但中文大纲里也很常见“怀疑那个白狼知道…”、“觉得这位议长已经知情”这类写法
- 如果只按主体前紧邻文本判断，`那个 / 这名 / 那位` 会把 speculative 前缀隔开，重新让系统把内层 `知道...` 当成已证实 claim

因此这轮继续做一层保守收紧：

- speculative subject 检查现在会剥掉 `那个 / 这个 / 那名 / 这名 / 那位 / 这位` 这类短指代修饰
- 这样“林舟怀疑那个白狼知道组织首领是谁”仍会保持为未证实，不会再生成白狼已知情的 direct claim

原因：

- 这类指代修饰只是在描述口气上补一个限定，不会改变外层仍是怀疑/传闻的事实
- 如果不拦，machine fact 会把未证实猜测升级成已证实知识，污染 `knowledge_claims` 和后续 world-rule conflict
- 仍然只是 claim 抽取边界收紧，不改数据结构

### 决策：speculative 外层和内层主体之间夹着时间/章节 filler 时，仍不能把内层 `知道...` 提升成 direct claim

当前状态：

- 上一轮已经拦掉了 speculative 前缀和主体之间只夹着“那个 / 这名 / 那位”这类指代修饰的 case
- 但中文大纲里也常见“怀疑那时那个白狼知道…”、“听说在第七章白狼已经知情”这类写法
- 如果 helper 只剥指代词，这些时间/章节 filler 会把 speculative 前缀再次隔开，重新让系统把内层 `知道...` 当成已证实 claim

因此这轮继续做一层保守收紧：

- speculative subject 检查现在会继续剥掉 `那时 / 这时 / 当时 / 当天 / 那晚 / 此刻` 这类短时间 filler
- 如果主体前是 `在第七章 / 于第十章` 这类章节提示，也会先剥掉章节 token，再清掉残留的 `在 / 于`
- 这样“林舟怀疑那时那个白狼知道组织首领是谁”仍会保持为未证实，不会再生成白狼已知情的 direct claim

原因：

- 这类时间/章节 filler 只是在补语境，不会改变外层仍是怀疑/传闻的事实性质
- 如果不拦，claim 抽取会再次把未证实的传闻升级成 machine fact，污染 `knowledge_claims` 和 world-rule conflict
- 仍然只是 claim 抽取边界收紧，不改数据结构

### 决策：`据说 / 传闻 / 听闻` 这类更弱传闻前缀，也不能把内层 `知道...` 提升成 direct claim

当前状态：

- 前几轮已经拦掉了 `怀疑 / 猜测 / 听说 / 觉得 / 担心` 这批更显式的主观判断或传闻前缀
- 但中文大纲里也常出现更弱的“据说那时那个白狼知道…”、“传闻白狼已经知情”、“林舟听闻白狼知道内情”
- 如果词表只覆盖前一批显式前缀，这些更弱 rumor prefix 仍会让系统把内层 `知道...` 当成已证实 claim

因此这轮继续做一层保守扩展：

- speculative prefix 词表现在补进 `据说 / 传闻 / 听闻`
- 这样“据说那时那个白狼知道组织首领是谁”也会继续保持为未证实，不会再生成白狼已知情的 direct claim

原因：

- 这类前缀表达的仍然是传闻、转述或非证实信息，而不是可直接落入 machine fact 的事实陈述
- 如果不拦，`knowledge_claims` 会把 rumor 升级成 direct knowledge，后续 world-rule conflict 也会被污染
- 仍然只是 claim 抽取边界收紧，不改数据结构

---

## 2026-05-25

### 决策：`prior-exception + local-signal` 只有在别的主体真正占到知识谓词时才升 `mixed-subjects`

当前状态：

- `prior-exception + local-signal` 已经会按主体窗口区分 `shared-subject` 和 `mixed-subjects`
- 但像“林舟和苏岚对视时，林舟知道组织首领是谁”这种句式
- 别的主体虽然先出现在同一句里，知识谓词前却又重新落回规则主体

因此这轮把 local-signal 的 mixed-subject 判定再收紧一层：

- 如果别的主体只是在前置铺垫里出现
- 但知识谓词前又重新出现了规则主体
- 那这条 exception 继续按 `shared-subject` 处理，而不是升级成 `mixed-subjects`
- 如果别的主体出现在知识谓词后，并且自己又带出第二个 knowledge verb
- 那这条 exception 仍按 `mixed-subjects` 处理，不会被前面的单主体谓词误降回 `shared-subject`
- 如果别的主体出现在知识谓词后，但后续 knowledge verb 前又重新出现了规则主体
- 那这条 exception 继续按 `shared-subject` 处理，不会因为窗口放宽而被误升成 `mixed-subjects`
- 对 `claim-match`，如果另一个角色只是旁观出场、但自己附近没有 knowledge signal
- 那这条 exception 也继续按 `shared-subject` 处理，不再仅凭 `character_mentions` 就升成 `split-subjects`
- 如果中间只是提到别的角色，但后面重新回到规则主体并带出第二个 knowledge verb
- 那 draft claim 抽取也不能把后面的规则主体谓词错误归到这个中间角色头上
- 但像“林舟和苏岚都知道...”这种并列主体共用一个 knowledge verb 的句式
- 仍要继续允许两个主体共同吃到这条 knowledge 谓词，不能因为窗口收紧把前一个主体截断掉
- 这也包括别名参与的并列主语，例如“林舟与阿岚知道...”
- 抽取结果仍应稳定回到 canonical subject `林舟 / 苏岚`

原因：

- 这类句子表达的是“同场出现”，不是“多主体共享同一条知情变化”
- 继续保守地把它打成 mixed 会平白引入 `review-subject-scope`
- 这条收紧只影响 local-signal 边界，不改 claim-match；同时保留真正多主体 knowledge 谓词 case 的 mixed review

---

## 2026-05-25

### 决策：一字 alias 只有在像主体出现时，才能参与 knowledge claim / subject-scope 命中

当前状态：

- draft claim 抽取已经能处理“林舟与阿岚知道...”这类别名参与的并列主语
- 但如果另一角色还带一字 alias，例如 `苏岚 -> 岚`
- 那么“林舟在岚城知道组织首领是谁，苏岚随后赶到”这类句子里
- `岚城` 里的 `岚` 会被误当成主体命中

因此这轮把 subject term 命中再收紧一层：

- 对多字姓名 / 别名，继续沿用当前宽松匹配
- 对一字 alias，只有当前后文看起来像主体出现时，才允许把它当成有效 subject hit
- 像 `岚城`、`岚桥` 这类地名 / 名词里的嵌入命中，不再参与主体窗口截断
- 这样既不会截断规则主体自己的 knowledge verb 窗口
- 也不会给一字 alias 所属角色凭空造出假的 knowledge claim
- 同一层收紧也复用于 `local-signal / claim-match` 的 subject-scope 扫描

原因：

- 一字 alias 在中文地名、物名里非常容易发生子串误命中
- 这类误命中同时会污染 claim 抽取和 mixed-subject 判定，影响面比单条 wording 漏判更大
- 先把一字 alias 收紧成“像主体时才算主体”，收益高且不需要改数据结构

---

## 2026-05-25

### 决策：短 alias / 称谓如果只是嵌在地名、设定名词、组织名或机构名里，也不能算主体命中

当前状态：

- 上一轮已经把一字 alias 收紧成“像主体时才算主体”
- 但更长一点的 alias / 称谓，例如 `阿岚`、`白狼`、`师姐`
- 仍可能在 `阿岚街 / 白狼谷 / 师姐峰 / 白狼营 / 白狼帮 / 白狼会` 这类地名、设定名词、组织名或机构名里误命中

因此这轮再补一层轻量过滤：

- 如果 alias / 称谓后面直接连的是典型地名、设定名词、组织名或机构名后缀
- 那这次命中不再参与 subject hit
- 它既不能截断规则主体自己的 knowledge 窗口
- 也不能给对应角色凭空造出 claim
- 这层过滤继续复用到 `claim-match / local-signal` 的 subject-scope 扫描

原因：

- 多字 alias 的误命中模式和一字 alias 本质相同，只是前一轮规则还没覆盖到
- 这类后缀过滤比给所有多字姓名都上重语法判断更稳，风险更低
- 先挡住地名/设定名词/组织名/机构名嵌入命中，已经能覆盖一批高频中文写法

---

## 2026-05-27

### 决策：嵌套 knowledge 子句不能反向污染规则主体的 direct claim

当前状态：

- 前一轮已经把短 alias / 称谓嵌在复合名词里的假主体命中压下来了
- 但像“林舟意识到苏岚知道组织首领是谁”这种句式里
- 规则主体后面虽然跟着 knowledge verb
- 真正持有核心事实的却是后面的第二主体

因此这轮继续收紧一层：

- 如果第二主体后面直接带出自己的 knowledge 子句
- 那这条嵌套 knowledge 不再回流成前一个主体的 direct claim
- 也就是说“林舟意识到苏岚知道...”只保留苏岚那条 claim
- 不再把林舟误判成也直接知道该世界规则对象

原因：

- 这类句子表达的是“知道别人已经知情”，不是“自己直接掌握该事实”
- 如果不收紧，会在 world-rule 上平白制造错误 conflict / exemption
- 这属于 claim 提取边界本身的问题，优先级高于继续压说明文案

---

## 2026-05-27

### 决策：speculative 外层认知不能把内层 `知道...` 提升成已证实 direct claim

当前状态：

- 上一轮已经处理了“林舟意识到苏岚知道...”这类嵌套 knowledge 子句
- 但像“林舟怀疑白狼知道组织首领是谁”“林舟听说白狼知道组织首领是谁”
- 这类外层只是猜测、传闻或主观判断的句式
- 仍会把内层主体误抽成已被证实知情

因此这轮继续收紧一层：

- 如果某个主体只是出现在 `怀疑 / 猜测 / 担心 / 听说 / 觉得 / 以为` 这类 speculative 外层动词之后
- 那它后面的 `知道...` 子句不再自动落成 direct knowledge claim
- 这样不会再平白制造该主体的 `world-rule conflict`
- 也不会把“传闻中的知情”误升成正式 exception / conflict 输入

原因：

- 这类句子表达的是不确定判断，不是机器事实源可以直接采信的正式知情变化
- 如果继续放行，会把 `knowledge-state / world-rule` 的误报拉高，而且难靠后续 merge 再修正
- 先在 claim 抽取层挡住，收益高且副作用小

---

## 2026-05-27

### 决策：短 alias / 称谓如果只是嵌在物件或术式名里，也不能算主体命中

当前状态：

- 前一轮已经把地名、设定名词、组织名、机构名里的嵌入命中压掉
- 但像 `白狼令 / 白狼阵 / 白狼符 / 白狼舰 / 白狼封阵术`
- 这类世界观物件、法器、阵法或术式名里
- 角色 token 仍会被误当成主体
- 进一步看，像 `持白狼封阵术 / 催动白狼大阵 / 施展白狼七杀号`
- 这类动作前缀带出的复合术式名，也会绕过只看介词前缀的过滤
- 再往下看，像 `借白狼封阵术 / 引动白狼封阵术 / 唤起白狼巨舰`
- 这类更短或不同构式的动作前缀，也会落在同一个漏网点上
- 另外像 `操控白狼巨舰 / 驾驭白狼大阵 / 运转白狼封阵术`
- 这类更抽象的使用/操控前缀，也会把人物 token 错吸成主体

因此这轮继续沿同一层过滤扩一格：

- 如果 alias / 称谓后面直接连的是典型物件或术式后缀
- 这次命中也不再参与 subject hit
- 如果 alias / 称谓后面还有一小段修饰词，但整体仍落在介词引导的复合术式名里
- 这次命中也继续按嵌入名词处理，不再等到紧邻字符就是后缀才拦
- 如果 alias / 称谓前面是 `持 / 催动 / 施展 / 唤出 / 祭出` 这类动作前缀
- 且后面仍连着复合物件 / 术式尾巴
- 这次命中也继续按嵌入名词处理
- 这也包括 `借 / 引动 / 唤起` 这类前缀，以及 `催动起 / 施展开` 这类动作词后再带一个轻补语字的变体
- 也包括 `操控 / 驾驭 / 运转` 这类抽象操控前缀
- 它不能截断规则主体自己的 knowledge 窗口
- 也不能给对应角色凭空造出 claim
- 这层过滤同样继续复用到 `claim-match / local-signal` 的 subject-scope 扫描

原因：

- 在偏玄幻、仙侠、奇幻设定里，人物 token 经常出现在令牌、阵法、兵器、法门名称里
- 这类误命中和组织名误命中的机制相同，继续放着只会把 claim 级边界越拉越噪
- 仍然只是扩大后缀过滤词表，不改数据结构

---

## 2026-05-25

### 决策：当全部 conflict rule 共享同一结构签名时，把顶层 `shared-conflict-summary + shared-conflict-structure` 合成 `shared-conflict-overview`

当前状态：

- constraints grouped summary 顶层已经能把 `shared-conflict-context + shared-conflict-actions` 合成 `shared-conflict-summary`
- 但当全部 conflict rule 还共享同一套 `strategies / direct / override / subjects / subject_scope`
- 输出里仍会再紧跟一条覆盖全部 rule 的 `shared-conflict-structure`

因此这轮继续做一层保守压缩：

- 只在一条 `shared-conflict-structure` 覆盖全部 conflict rule 时
- 再把这条结构行和顶层 `shared-conflict-summary` 合成一条 `shared-conflict-overview`
- 同时省掉那条独立的全局 structure 行

原因：

- 这时 summary 和 structure 描述的是同一批全局 conflict，只是被拆成了两条相邻行
- 约束条件很窄，不会影响 `rules=...` 的 subset 级 structure 行
- 能继续减少顶层 explainer 的切换成本，让 overview 更接近“读一行就知道整体影响面”

---

## 2026-05-25

### 决策：把顶层 `shared-conflict-context + shared-conflict-actions` 合成 `shared-conflict-summary`

当前状态：

- constraints grouped summary 顶层原本会分别输出 `shared-conflict-context` 和 `shared-conflict-actions`
- 当当前批次的 conflict rule 共享同一批全局 `domains / targets`
- 并且也共享同一批全局 `impacts / write_shapes` 时，这两条顶层行会紧挨着重复同一层范围

因此这轮继续做一层保守压缩：

- 只在全局 conflict context 和全局 conflict actions 同时存在时
- 把原本拆开的 `shared-conflict-context + shared-conflict-actions` 合成一条 `shared-conflict-summary`
- 这条 summary 同时承载 `domains / targets / impacts / write_shapes`

原因：

- 这时两条顶层行描述的是同一批全局 conflict 影响面，拆开只是在重复读者视线切换
- 约束条件仍然很窄，不会影响 `rules=...` 子组级的局部 summary
- 能继续减少 grouped summary 里的顶层噪音行数

---

## 2026-05-24

### 决策：relationship 词表继续补充 `化干戈为玉帛 / 撕破脸皮`

当前状态：

- `一笑泯恩仇 / 反目成仇` 已经接入 relationship 词表
- 但中文大纲里也很常见 `化干戈为玉帛`、`撕破脸皮`
- `撕破脸皮` 和既有 `撕破脸` 共享前缀，如果不显式补长词并调整命中顺序，解释层会退化成较短 token

因此这轮继续做一层保守扩展：

- `化干戈为玉帛 -> reconciled`
- `撕破脸皮 -> ruptured`
- 同时把 `化干戈为玉帛` 纳入 relationship repeat hint

原因：

- 继续沿现有 reconciled / ruptured 状态机补齐高频中文写法
- 顺手补齐长短词共享前缀时的 token 命中边界
- 仍然只是词表边界扩展，不改数据结构

---

## 2026-05-24

### 决策：relationship 词表继续补充 `尽释前嫌 / 反目为仇`

当前状态：

- `化干戈为玉帛 / 撕破脸皮` 已经接入 relationship 词表
- 但中文大纲里也很常见 `尽释前嫌`、`反目为仇`
- `反目为仇` 和既有 `反目 / 反目成仇` 共享前缀，如果不显式补长词并调整命中顺序，解释层会退化成较短 token

因此这轮继续做一层保守扩展：

- `尽释前嫌 -> reconciled`
- `反目为仇 -> ruptured`
- 同时把 `尽释前嫌` 纳入 relationship repeat hint

原因：

- 继续沿现有 reconciled / ruptured 状态机补齐高频中文写法
- 继续补齐长短词共享前缀时的 token 命中边界
- 仍然只是词表边界扩展，不改数据结构

---

## 2026-05-24

### 决策：把同 support 的 conflict `rule-impacts + write-shapes` 合成 `shared-conflict-rule-actions`

当前状态：

- mixed conflict 子组已经能分别上提 `shared-conflict-rule-impacts` 和 `shared-conflict-write-shapes`
- 但如果两者刚好命中同一批 `rules=...`，输出里会连续重复同一组 rule id
- 这类重复并不提供新结构信息，只是在把同一组局部 action 拆成两行

因此这轮继续做一层保守压缩：

- 当同一批 conflict rule 同时共享 `direct/review impacts` 和 `direct/review write_shapes` 时
- 不再分开输出两条局部共享行
- 而是合成一条 `shared-conflict-rule-actions`

原因：

- 继续压缩 grouped summary 的局部重复 token
- 不改变 merge 判定逻辑，只收紧 explainers 的表达层
- 保留 `rules -> action fields` 的映射可读性，同时减少重复的 `rules=...`

---

## 2026-05-24

### 决策：把同 support 的 conflict `rule-tokens + rule-context` 合成 `shared-conflict-rule-details`

当前状态：

- mixed conflict 子组已经能分别上提 `shared-conflict-rule-tokens` 和 `shared-conflict-rule-context`
- 但如果两者刚好命中同一批 `rules=...`，输出里仍会连续重复同一组 rule id
- 这类重复也不提供新的结构信息，只是在把同一组局部描述拆成两行

因此这轮继续做一层保守压缩：

- 当同一批 conflict rule 同时共享 `strategies/subjects` 和 `domains/targets` 时
- 不再分开输出两条局部描述行
- 而是合成一条 `shared-conflict-rule-details`

原因：

- 继续压缩 grouped summary 的局部重复 token
- 不改变 merge 判定逻辑，只收紧 explainers 的表达层
- 保留 `rules -> descriptor fields` 的映射可读性，同时减少重复的 `rules=...`

---

## 2026-05-25

### 决策：把同 support 的 conflict `rule-metadata + rule-actions` 合成 `shared-conflict-rule-summary`

当前状态：

- mixed conflict 子组已经能分别上提 `shared-conflict-rule-metadata` 和 `shared-conflict-rule-actions`
- 但如果两者刚好命中同一批 `rules=...`，输出里还是会重复同一组 rule id
- 这类重复也不再提供新的结构信息，只是在把同一组局部 summary 拆成两行

因此这轮继续做一层保守压缩：

- 当同一批 conflict rule 同时共享 `shared-conflict-rule-metadata`
- 且也共享 `direct/review impacts + direct/review write_shapes` 时
- 不再分开输出两条局部 summary 行
- 而是合成一条 `shared-conflict-rule-summary`

原因：

- 继续压缩 grouped summary 的局部重复 token
- 不改变 merge 判定逻辑，只收紧 explainers 的表达层
- 保留 `rules -> summary fields` 的映射可读性，同时减少重复的 `rules=...`

---

## 2026-05-25

### 决策：把同 support 的 conflict `structure-tokens + rule-details` 合成 `shared-conflict-rule-metadata`

当前状态：

- mixed conflict 子组已经能分别上提 `shared-conflict-structure-tokens` 和 `shared-conflict-rule-details`
- 但如果两者刚好命中同一批 `rules=...`，输出里仍会连续重复同一组 rule id
- 这类重复同样不提供新的结构信息，只是在把同一组局部 descriptor 拆成两行

因此这轮继续做一层保守压缩：

- 当同一批 conflict rule 同时共享 `direct/override/subject_scope`
- 且也共享 `strategies/subjects + domains/targets` 时
- 不再分开输出两条局部 descriptor 行
- 而是合成一条 `shared-conflict-rule-metadata`

原因：

- 继续压缩 grouped summary 的局部重复 token
- 不改变 merge 判定逻辑，只收紧 explainers 的表达层
- 保留 `rules -> descriptor fields` 的映射可读性，同时减少重复的 `rules=...`

---

## 2026-05-24

### 决策：relationship 词表继续补充 `一笑泯恩仇 / 反目成仇`

当前状态：

- `重修旧好 / 撕破脸` 已经接入 relationship 词表
- 但中文大纲里也很常见 `一笑泯恩仇`、`反目成仇`
- `反目成仇` 和既有 `反目` 共享前缀，如果不显式补长词并调整命中顺序，解释层会退化成较短 token

因此这轮继续做一层保守扩展：

- `一笑泯恩仇 -> reconciled`
- `反目成仇 -> ruptured`
- 同时把 `一笑泯恩仇` 纳入 relationship repeat hint

原因：

- 继续沿现有 reconciled / ruptured 状态机补齐高频中文写法
- 顺手补齐长短词共享前缀时的 token 命中边界
- 仍然只是词表边界扩展，不改数据结构

---

## 2026-05-24

### 决策：relationship 词表继续补充 `重修旧好 / 撕破脸`

当前状态：

- `握手言和 / 恩断义绝` 已经接入 relationship 词表
- 但中文大纲里也很常见 `重修旧好`、`撕破脸`
- `重修旧好` 和 `握手言和 / 言归于好 / 破镜重圆` 一样，也带有关系重新修复的语义

因此这轮继续做一层保守扩展：

- `重修旧好 -> reconciled`
- `撕破脸 -> ruptured`
- 同时把 `重修旧好` 纳入 relationship repeat hint

原因：

- 继续沿现有 reconciled / ruptured 状态机补齐高频中文写法
- 能再压掉一批 relationship-history 的漏判与误报
- 仍然只是词表边界扩展，不改数据结构

---

## 2026-05-24

### 决策：relationship 词表继续补充 `言归于好 / 彻底翻脸`

当前状态：

- `破镜重圆 / 闹翻` 已经接入 relationship 词表
- 但中文大纲里也很常见 `言归于好`、`彻底翻脸`
- `言归于好` 和 `重归于好 / 冰释前嫌 / 破镜重圆` 一样，也带有关系重新修复的语义

因此这轮继续做一层保守扩展：

- `言归于好 -> reconciled`
- `彻底翻脸 -> ruptured`
- 同时把 `言归于好` 纳入 relationship repeat hint

原因：

- 继续沿现有 reconciled / ruptured 状态机补齐高频中文写法
- 能再压掉一批 relationship-history 的漏判与误报
- 仍然只是词表边界扩展，不改数据结构

---

## 2026-05-24

### 决策：relationship 词表继续补充 `握手言和 / 恩断义绝`

当前状态：

- `言归于好 / 彻底翻脸` 已经接入 relationship 词表
- 但中文大纲里也很常见 `握手言和`、`恩断义绝`
- `握手言和` 和 `言归于好 / 冰释前嫌 / 破镜重圆` 一样，也带有关系重新修复的语义

因此这轮继续做一层保守扩展：

- `握手言和 -> reconciled`
- `恩断义绝 -> ruptured`
- 同时把 `握手言和` 纳入 relationship repeat hint

原因：

- 继续沿现有 reconciled / ruptured 状态机补齐高频中文写法
- 能再压掉一批 relationship-history 的漏判与误报
- 仍然只是词表边界扩展，不改数据结构
