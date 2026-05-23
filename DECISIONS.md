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
