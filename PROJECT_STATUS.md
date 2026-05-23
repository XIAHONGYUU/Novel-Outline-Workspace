# Project Status

最后更新：2026-05-23

## 项目定位

这个仓库在构建一个“小说大纲工作区”系统。

目标不是一次性生成大纲，而是把：

- `canon`
- `outline`
- `timeline`
- `inbox`
- `views`

放进一个可持续维护、可校验、可回滚的工作区流程里。

## 当前阶段

当前处于 `P0 主链路加固期`。

已经完成的方向：

- 工作区模板与初始化
- idea inbox 录入
- workspace 状态刷新
- 基础校验
- 基础 HTML 视图渲染
- merge plan / apply merge 基础流
- orchestrator 入口
- idea intake 第二层草案推断
- idea-level consistency check 可用版
- gate-aware merge
- world-rule 多策略 merge input
- graph-aware consistency 豁免
- formal intake backfill / repair 入口
- domain-specific merge plan explainers

## 已完成能力

### 1. 工作区骨架

- `scripts/init_workspace.py`
- `workspace-template/`
- `src/novel_outline_workspace/workspace.py`

### 2. idea 录入主流程

- `scripts/ingest_idea.py`
- 写入 `state/idea-log.json`
- 写入 `inbox/*.md`

### 3. idea intake 推断

已支持自动推断：

- `kind`
- `tags`
- `target_files`
- `suggested_domains`
- `chapter_hints`
- `location_candidates`
- `character_mentions`

并自动生成：

- `state/intake-drafts/<idea-id>.json`
- `views/intake-drafts/<idea-id>.html`

### 4. 基础校验与渲染

- `scripts/validate_workspace.py`
- `scripts/check_idea_consistency.py`
- `scripts/render_workspace_views.py`
- `scripts/refresh_workspace_status.py`

### 5. merge 基础流

- `scripts/plan_idea_merge.py`
- `scripts/apply_idea_merge.py`
- `scripts/run_outline_workspace_pipeline.py`
- merge 默认受 consistency gate 约束
- `plan_idea_merge` 的 `proposed_actions` 已升级为更接近执行层的 domain explainers

### 6. consistency-check 增强

已支持：

- claim-level `knowledge-state` 提取
- `knowledge-state conflict` 的非同标题匹配
- 当同一知情事实同时存在更早与更晚记录时，优先只报告更早冲突，避免重复告警
- `title-based drift` 对带括注 / 副标题的扩写事件名和场景名开始支持安全的部分匹配
- `knowledge object` 开始支持有限的同义归一与对象家族匹配，并压缩公共前缀导致的误报
- `world-rule conflict` / `world_rule_exception` 开始复用结构化 `knowledge_claims` 做 subject/object 协同匹配
- 单条 idea 中的多条 `knowledge_claims` 开始能稳定抽出，并按 rule 精确回流到 world-rule merge input
- 多条 `world-rule` 同时命中时，`proposed_actions` 开始先给出 constraints 级分组摘要，再保留每条 rule 的具体输入
- constraints 分组摘要开始直接列出每条 rule 的策略、direct/override 状态、目标文件，以及按 direct / review 拆开的跨 domain impacts
- constraints 分组摘要开始区分 `shared-subject` 与 `split-subjects`，避免多主体 world-rule 被误看成可共用同一条 exception 解释
- 同一主体下如果标题 object 和正文 object 同时落成 claim，且前者只是同一家族的泛化说法，claim 层开始优先保留更具体那条
- 多主体句子里如果前后主体分别对应不同 object，claim 提取开始按主体窗口截断，避免把后一个主体的 object 串回前一个主体
- `identity` family 里的近义 object 开始按更具体 claim 收敛，例如“首领身份 / 组织首领是谁”会优先保留后者
- `leak / same-camp / separate-camp` family 里的近义 object 也开始按更具体 claim 收敛，例如“有人泄密 / 议会有内鬼”“他们是一路人 / 议会和黑潮是同一阵营”“他们不是一路人 / 议会和黑潮不是同一阵营”会优先保留后者
- 在 `same-camp / separate-camp` family 内，如果只是“同一阵营 / 一伙人 / 一路人”这类 wording 差异，claim 层也开始优先保留更标准表达
- cross-family claim 当前会继续保持分离，避免把同一主体在同章知道的两类不同事实误收敛到一条
- 如果同章已经有正式 event / scene / canon `knowledge-state` 记录，future duplicate 不再把当前 idea 误报成知情点前移
- `world-rule` 在缺少 `knowledge_claims` 时，也开始按主体局部窗口抽取 knowledge signal；同章 exception 的同义 object 不再只靠整句字面命中，mixed-subject 句子里别人的 object 也不会误触发当前 rule
- consistency report 开始显式输出 `world-rule-exemption-applied`，merge plan 在 clean gate 下也会补一条 exemption explainer，说明这是“已落地豁免”而不是“没有命中规则”
- 对已落地的 world-rule exception，grouped summary 开始区分 `direct` 沿用和仍需 `review` 的主体范围；如果同一 idea 同时存在冲突 rule 和已豁免 rule，也会收敛进同一条 constraints 摘要
- `exception_scope` 开始细分成 `exception_scope_base / exception_subject_scope / exception_match_mode`，并把 `review-subject-scope / review-exception-chain / review-exception-evidence` 这类 impact token 稳定写出
- world-rule 相关的 canon explainer 开始引用各自命中的 claim，而不是回退到第一条 claim
- 多条 rule 共享同一事件/场景写入时，重复的 timeline / outline explainers 开始做去重收敛
- report 级结构化 `patch_suggestions`
- 对后文“再次意识到 / 已经知道”类复述记录的豁免
- relationship-history 对未来重复状态的图谱级豁免
- 如果同章已经有正式 relationship beat，future same-state 记录不再把当前 idea 误报成关系漂移

### 7. timeline merge 输入层

已支持：

- `plan_idea_merge` 输出结构化 `timeline_merge_inputs`
- `apply_idea_merge` 通过 `merge_input_id` 直接消费 merge plan 输入
- 对已有 scene 做跨章节移动时避免重复 scene id
- event / scene note 已可由 merge input 显式携带
- plan explainers 已可输出 `readiness / merge_input_id / planned_writes / source_signals`

### 8. canon relationship 联动

已支持：

- `state/canon-index.json` 新增 `relationships`
- relationship idea 可生成 `upsert-canon-relationship` merge input
- relationship / first-meeting 相关 issue 开始能驱动 canon 关系写入
- relationship-history 重复状态去重
- 关系在存在中间状态转移时的豁免规则
- 对“重新结盟 / 再次和解”且未来已有同状态记录的 case 开始按图谱路径豁免

### 9. world-rule 闭环

已支持：

- `world-rule conflict` 生成结构化 merge input
- merge input 可按不同策略更新事件/场景、`constraints` cutoff 或规则说明
- `resolve-world-rule-by-delaying-event` 可把 idea 事件延后到 cutoff 之后
- `resolve-world-rule-by-updating-cutoff` 可把 rule cutoff 对齐到新事件
- `document-world-rule-exception` 可只记录规则说明，并显式要求 override

### 10. demo / case workspace 整理

已支持：

- 对 legacy duplicate idea 进行收敛
- 为缺 intake draft 的历史 idea 补回最小 draft
- 让 demo workspace 回到“有一条可继续 plan-merge 的 pending idea”状态
- 新增 `first-workflow-case/` 作为首个独立 workflow 案例工作区，并停在 `clear gate + ready merge plan` 状态

### 11. intake backfill / repair

已支持：

- `scripts/backfill_intake_drafts.py`
- 对缺 draft / 缺 view / 缺 path 元数据的 pending idea 做正式 backfill
- 按 `--all-pending` 或 `--all-ideas` 批量修复
- 按 `--force-rebuild` 重建已有 draft

## 当前状态判断

项目已经从“蓝图阶段”进入“主链路闭环可跑”的阶段。

现在最缺的不是更多零散脚本，而是把以下链路继续做厚：

- merge plan 的影响面表达
- intake 对 legacy / 模糊 idea 的修复能力
- 更稳定的 timeline / outline / canon 联动
- 更明确的 skill 与 script 边界
- 更完整的 demo / case workspace / 文档闭环

## 最近完成

- 为 intake 增加结构化 draft 层
- 新增 intake draft 的 JSON 与 HTML 产物
- 修复地点短语推断，使 `白塔议事厅` 这类地点可被正确提取
- 补齐对应测试并确认通过
- 落地 `novel-consistency-check` 的可用版，并接入 pipeline / 首页入口
- 新增 `relationship-history` 与 `world-rule` 两类冲突检查
- 让 merge plan 与 apply merge 显式读取 consistency gate
- 让 orchestrator 在 pending idea 上优先跑 consistency gate
- 扩展 claim-level `knowledge-state` 检查
- 让 consistency report 输出结构化 `patch_suggestions`
- 让 merge plan 输出 `timeline_merge_inputs`
- 让 apply merge 能直接消费 `merge_input_id`
- 让 canon relationship 进入机器真相源并接入 merge
- 让 relationship merge input 优先复用已有关系节点
- 为 relationship-history 增加图谱级去重和转移豁免
- 让 world-rule conflict 接入 plan/apply 闭环
- 把 world-rule 的单一路径扩成多策略输入
- 为 world-rule 增加“延后事件 / 只记规则说明”两条分支
- 为 knowledge-state 增加后文复述型豁免
- 为 relationship-history 增加未来重复状态的图谱级豁免
- 清理 demo workspace 的 legacy duplicate idea，并补回代表样本的 intake draft / plan
- 落地正式的 intake backfill / repair 脚本入口
- 为 legacy idea backfill 增加测试覆盖
- 把 merge plan 的影响面说明升级成 domain-specific explainers
- 为 timeline / outline / canon / constraints explainers 增加测试覆盖
- 为 `state/canon-index.json` 增加 `knowledge_states` / `world_rule_exceptions`
- 新增 `upsert-canon-knowledge-state` / `update-existing-knowledge-state`
- `document-world-rule-exception` 开始同步写入 canon 机器事实源
- consistency-check 开始读取 canon knowledge / world-rule exception 回流结果
- validator 开始校验 knowledge-state / world-rule exception 的引用完整性
- 收紧 `knowledge-state conflict` 边界：当更早 canon / timeline 记录已足够解释冲突时，不再同时报未来重复记录
- 收紧 `title-based drift` 边界：正式事件 / 场景标题即使带有地点括注或副标题，也能继续命中同一 idea
- 收紧 `knowledge object` 边界：`内鬼 / 泄密`、`身份 / 是谁`、`不是一路 / 不是同一阵营` 这类常见表达开始做保守归一，同时不再把“有人调查”误判成“有人泄密”
- 收紧 `world-rule exception` 边界：规则检测与例外豁免开始共用 `knowledge_claims`，`组织首领身份 / 组织首领是谁` 这类同义 object 不再依赖原句字面命中
- 收紧多 claim / 多 rule 闭环：`plan_idea_merge` 现在能把不同 rule 绑定回各自命中的 claim，而不再把第一条 subject claim 错绑到所有 rule
- 收紧 constraints explainer 边界：多条 world-rule 冲突时，plan 已开始先按 rule 分组摘要，减少人工在多条输入间来回对照
- 细化 constraints 影响面说明：grouped summary 已开始把每条 rule 的目标文件、direct/override 信息，以及 `timeline / outline / canon / constraints` 的 direct / review impact 类型直接摊开
- 细化 canon 影响面说明：多条 world-rule exception 的 canon explainer 已开始按各自命中的 claim 输出 source signal
- 收敛 explainers 噪音：同一事件/场景的重复 timeline / outline 说明开始优先保留一条更高可执行性的版本
- 收紧同章锚点边界：如果当前 chapter 已经有正式的 knowledge-state / relationship 记录，future duplicate 不再反向把 idea 报成前移或漂移
- 收紧无 claim 的 world-rule 边界：exception fallback 与规则命中都开始按主体局部窗口判断，不再把另一主体的 object 误算进来
- 增加 exemption 可见性：同章 / 既有 world-rule exception 不再只在底层放行，report 与 plan 都开始显式标记
- 收敛 world-rule 说明噪音：已豁免 rule 不再单独挂一条 summary，而是开始和冲突 rule 共享一条 grouped constraints 说明
- 但 `exception_scope` 仍只覆盖第一层 token，后续还可以继续细化到更明确的 domain impact 组合

## 当前风险

- 语义级 merge 仍然偏弱
- consistency-check 已能输出 claim-level knowledge-state，但还不是完整知识图谱推理
- timeline merge 已接上第一层 canon knowledge / exception 联动，但还不是完整知识图谱推理
- relationship 目前已入 canon，但仍缺更丰富的状态图谱和更细的豁免边界
- world-rule exception 已能处理 claim 级 subject/object 对齐，但 chapter-scoped exception 和 mixed-subject 展示边界还可继续收紧
- world-rule 已有多策略输入，但“只改说明”的策略仍依赖人工 override
- world-rule 现在已处理单 idea 下的多 claim / 多 rule 基本分流，并补上第一层 rule 级 direct / review impact 摘要、`shared-subject / split-subjects` 边界、标题/正文泛化 claim 收敛、mixed-subject claim 串绑收紧，以及 `identity / leak / same-camp / separate-camp` family 的更具体与更标准 wording 收敛；但更多 object family 仍偏薄
- intake backfill 目前仍以启发式推断为主，手工增强字段在 force rebuild 下会被重建
- canon 侧 explainers 仍有一部分 fallback case，尤其是更复杂的知识图谱与关系状态转移
- skill 规划已写出，但执行优先级还需要持续收敛

## 近期目标

1. 继续扩展 timeline-order / knowledge-state 规则
2. 继续收紧 relationship / world-rule exception 的边界说明
3. 继续增强 repair / merge explainers 的边界说明
4. 继续收敛 skill 与 script 的边界
