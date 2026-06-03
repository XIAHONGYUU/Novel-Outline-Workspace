# Project Status

最后更新：2026-06-03

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

当前处于 `P0 主链路收口与工作区级验收期`。

## 当前战略判断

项目的主要矛盾已经变了。

前一阶段的重点是把：

- consistency-check
- merge plan
- exception / grouped summary
- claim / subject-scope

这些底层能力做厚，避免主链路还没站稳时就过早进入工作区验收。

但到当前这一轮，继续深挖中文句式级边界的收益已经开始下降。  
接下来更重要的不是“还能再补多少误判规则”，而是：

- `ingest -> check-consistency -> plan-merge -> apply-merge -> validate` 能不能在真实 workspace 里稳定闭环
- `plan_idea_merge / apply_idea_merge` 是否已经足够可执行
- `demo-workspace/` 与 `first-workflow-case/` 是否始终维持清晰的 pending path

因此当前阶段的默认工作重点调整为：

1. 先定义 `P0` 收口标准
2. 再做工作区级验收
3. 只有在真实闭环被卡住时，才回头修对应规则
4. 顶层上按固定 `acceptance tracks` 推进，而不再按零散样例堆进度

当前这条判断已经有了第一轮实证支撑：

- `docs/p0-closure-checklist.md` 已建立
- `first-workflow-case/` 已完成首轮完整闭环
- 这轮验收暴露出的核心问题，不再是新的句式误判，而是 `apply_idea_merge.py` 的 CLI 能力缺口与“多 merge inputs 如何顺滑消费”的执行层问题

第二轮工作区级验收也已经补上：

- `demo-workspace/` 已完成一轮 `pending -> consistency -> plan` 验收
- 暴露出的核心问题不是新的 consistency 规则缺口，而是 `warning-only / needs-info` case 的工作流提示不够具体
- `workspace-status.json` 与 pipeline `auto` 现在已经开始把这类 case 明确收敛到 `repair-intake` 路径，而不再泛化成继续 `plan-merge`
- `apply_idea_merge.py` 现已支持一次性消费多条 `merge_input_id`，`timeline / outline / canon` 的组合写入不再需要手工拼参数
- `update_intake_draft.py` 已补上“人类确认字段如何写回 intake draft”的确定性入口，`repair-intake -> plan-merge -> apply-merge` 现在已有脚本级闭环测试

第三轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260511-006` 已从 `repair-intake` 真正走到 `apply`
- 这轮验证表明：`repair-intake -> check-consistency -> plan-merge -> apply-merge -> validate` 已不只是临时测试工作区能跑通，真实样例工作区也能闭环
- 验收过程还顺手确认了一点：对这类 `character` beat，当前最稳的 direct apply 形态是落成 outline 场景，而不是勉强制造新的 canon 结构记录

第四轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260602-001` 已从 `ingest` 真正走到一次性 multi-input `apply`
- 这轮验证表明：重复传入 `--merge-input-id` 不只是 CLI 能力已经补齐，真实 workspace 里也能一口气把 `timeline / outline + canon knowledge-state` 落地
- 当前更真实的剩余缺口，已经开始从“多 input 能不能一起 apply”转向“`relationship / character` 类 idea 怎样更稳定地产生 canon 结构联动”

第五轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260602-002` 已从 `ingest` 真正走到一次性 `outline scene + canon relationship` 的 apply
- 这轮验证表明：`relationship` 类 idea 不只是能在测试里写入 `state/canon-index.json`，真实 workspace 里也能稳定生成结构化关系记录
- 当前更真实的剩余缺口，已经继续前移到“已有关系记录的后续状态转移、复用与冲突收敛”这一层，而不再是“关系能不能第一次落库”

第六轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260602-003` 已把“已有关系继续变化”收敛成真实的 `relationship-history-conflict`
- 这轮先暴露并修掉了一个 planner 缺口：同一条 relationship reuse input 不再重复出现在 plan 里，`canon` action 现在也会稳定带上对应 `merge_input_id`
- 但这轮也把更深一层的真实空白暴露出来了：对“第 6 章再次结盟”这类 same-state repeat beat，当前 `update-existing-relationship` 会倾向于把既有关系记录整体改写到新章节，这在语义上还不够稳

第七轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260602-003` 已从 `relationship-history-conflict` 真正走到 `apply`
- 这轮验证表明：对“第 6 章再次结盟”这类 same-state repeat beat，planner 现在会优先产出 `scene-only` 的 gate-resolving input，而不是直接改写第 5 章既有 `canon relationship`
- apply 后 `state/canon-index.json` 仍保留第 5 章的首次结盟记录，第 6 章则新增 narrative scene，随后 consistency 已清空，`demo-workspace/` 当前回到 `pending=0 / applied=7 / rejected=4`
- 当前更真实的剩余缺口已经继续前移到：什么情况下应当把“既有关系后续变化”落成新的 `canon relationship` 历史节点，而不只是 scene 或覆写旧节点

第八轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260602-004` 已从 `ingest` 真正走到一次性 `scene + new canon relationship history node` 的 `apply`
- 这轮验证表明：对“第 7 章决裂”这类真实状态转移，planner 现在会稳定追加新的 `canon relationship` 历史节点，而不是复用或覆写第 5 章旧的 `allied` 节点
- apply 后 `state/canon-index.json` 当前已形成 `allied@5 -> ruptured@7` 的正式关系链，`outline/scene-index.json` 也同步新增了第 7 章 scene，consistency / validator 均保持 `ok=true`
- 当前更真实的剩余缺口已经继续前移到：多段 relationship history chain 之后，后续 `reconciled / allied again` 这类再变化在真实 workspace 中应如何继续落库

第九轮真实 workspace 验收也已经推进：

- `demo-workspace/` 的 `idea-20260603-001` 已从 `ingest` 真正走到一次性 `scene + new canon relationship history node` 的 `apply`
- 这轮验证表明：在已有 `allied@5 -> ruptured@7` 的关系链上，后续 `reconciled@9` 也能稳定追加成新的正式 history 节点，而不会打断既有链条
- apply 后 `state/canon-index.json` 当前已形成 `allied@5 -> ruptured@7 -> reconciled@9` 的三段关系链，`outline/scene-index.json` 也同步新增了第 9 章 scene，consistency / validator 均保持 `ok=true`
- 当前更真实的剩余缺口已经继续前移到：在已有 `reconciled` 节点之后，未来的 `再次结盟 / 再次和解` 这类 repeat beat，是否仍应只落 scene，以及怎样避免与已有 history chain 冲突

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
- confirmed intake patch 入口
- domain-specific merge plan explainers
- `needs-info` pending path 显式化：当 merge plan 缺少 `chapter_number` 等关键字段时，状态层与 orchestrator 已会优先提示 `repair-intake`
- multi-input apply 入口：CLI 与底层 `apply_idea_merge` 已支持一条 idea 一次性消费一组 merge inputs
- `demo-workspace/` 已补齐真实 multi-input apply 样例，当前 pending 已清空，pipeline `auto` 已回到 `validate`
- `demo-workspace/` 已补齐真实 relationship 样例，`state/canon-index.json` 中已有正式 `relationships` 记录
- relationship reuse planner 已去重并修正 action 绑定；same-state repeat beat 现已稳定落成 `scene-only` 闭环
- 真实 relationship state transition 现已能稳定追加新的 `canon relationship` 历史节点
- 多段 relationship history chain 现已能在真实 workspace 中稳定扩展到 `reconciled`
- 当前更真实的剩余问题是：已有 `reconciled` 节点之后，未来 repeat beat / 再变化如何继续与整条 history chain 保持一致
- 这条推进路线现已在 `docs/workspace-acceptance-framework.md` 里收敛成显式 framework，避免顶层继续被零散 case 主导

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
- 如果多条 `world-rule conflict` 之间共享同一批 context，grouped summary 现在会先提一条 `shared-conflict-context`，把公共 `domains / targets` 上提
- 如果多条 `world-rule conflict` 连动作层也完全相同，grouped summary 现在还会再提一条 `shared-conflict-actions`，把公共 `direct/review impacts` 与 `write_shapes` 上提
- 如果只有一部分 conflict rule 共享同一套动作签名，grouped summary 现在也会按 `rules=...` 再提 subset 级 `shared-conflict-actions`
- 如果同一批 conflict 连策略、direct/override 和主体范围也完全一致，grouped summary 现在还会再提一条 `shared-conflict-structure`
- 如果策略或主体不同、但 `direct / override / subject_scope` 仍重复，grouped summary 现在也会按 `rules=...` 再提一条 `shared-conflict-structure-tokens`
- 如果同一批 mixed conflict 子组同时共享结构 token 和 `strategies/subjects + domains/targets`，grouped summary 现在也会把这两层局部描述合成一条 `shared-conflict-rule-metadata`
- 如果同一批 mixed conflict 子组同时共享 `shared-conflict-rule-metadata` 和 action fields，grouped summary 现在也会再合成一条 `shared-conflict-rule-summary`
- 如果当前批次的全局 conflict context 和全局 conflict actions 同时存在，grouped summary 现在也会把 `shared-conflict-context + shared-conflict-actions` 合成一条顶层 `shared-conflict-summary`
- 如果这条顶层 conflict summary 对应的全部 rule 结构也完全一致，grouped summary 现在还会继续把 `shared-conflict-summary + shared-conflict-structure` 合成一条 `shared-conflict-overview`
- 如果 mixed conflict 子组里 `strategies=` 或 `subjects=` 仍重复，grouped summary 现在也会按 `rules=...` 再提一条 `shared-conflict-rule-tokens`
- 如果同一批 mixed conflict 子组同时共享 `strategies/subjects` 和 `domains/targets`，grouped summary 现在也会把这两条局部描述行合成一条 `shared-conflict-rule-details`
- 如果 mixed conflict 子组里 `domains=` 或 `targets=` 仍重复，grouped summary 现在也会按 `rules=...` 再提一条 `shared-conflict-rule-context`
- 如果 mixed conflict 子组里 `direct_impacts=` 或 `review_impacts=` 仍重复，grouped summary 现在也会按 `rules=...` 再提一条 `shared-conflict-rule-impacts`
- 如果不同 conflict 子组虽然整体签名不同，但还共享同一批 `write_shapes`，grouped summary 现在也会按 `rules=...` 再提一条 `shared-conflict-write-shapes`
- 如果同一批 mixed conflict 子组同时共享 `impacts` 和 `write_shapes`，grouped summary 现在也会把这两条局部 action 行合成一条 `shared-conflict-rule-actions`
- 如果某条 conflict / exemption rule 行里的 `impacts=` 或 `write_shapes=` 只是 `direct_/review_` 桶的并集，grouped summary 现在也会直接省掉这层泛化字段，避免同一 token 在明细行里重复两次
- 如果 `shared-exemption-base` 已经承载了公共 `domains / targets / reuse-exception impacts`，`shared-exemption-review` 现在也会自动扣掉这部分 base token，只保留 review 专属补充
- 如果多条 exemption 共享同一批 `subject_scope / exception_scope_*` 元信息，grouped summary 现在也会按 `rules=...` 再提一条 `shared-exemption-scope`
- 如果多条 exemption 共享同一批 `direct / review / subjects` 元信息，grouped summary 现在也会按 `rules=...` 再提一条 `shared-exemption-rule-tokens`
- 如果某批 exemption 行在扣掉共享 token 后只剩 exception id，grouped summary 现在也会再提一条 `shared-exemption-links`，把这些壳行收成一条映射
- 如果同一 rule 同时命中更早的 prior exception 和当前章 same-chapter exception，consistency / merge 现在也会优先选当前章那条，避免把本可 direct 的 case 误降成 review
- relationship repeat hint 现在也开始覆盖 `再度` 这类常见重启关系 wording，减少“再度结盟 / 再度和解”被误报成 future drift
- relationship state / repeat 词表现在也开始覆盖 `重归于好`、`反目` 这类常见关系表达，减少 reconciliation / rupture 场景的漏判与误报
- relationship state / repeat 词表现在也开始覆盖 `冰释前嫌`、`翻脸` 这类常见关系表达，进一步补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现在也开始覆盖 `破镜重圆`、`闹翻` 这类常见关系表达，继续补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现在也开始覆盖 `言归于好`、`彻底翻脸` 这类常见关系表达，继续补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现在也开始覆盖 `握手言和`、`恩断义绝` 这类常见关系表达，继续补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现在也开始覆盖 `重修旧好`、`撕破脸` 这类常见关系表达，继续补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现在也开始覆盖 `一笑泯恩仇`、`反目成仇` 这类常见关系表达，并处理 `反目` 前缀长短词的命中顺序
- relationship state / repeat 词表现在也开始覆盖 `化干戈为玉帛`、`撕破脸皮` 这类常见关系表达，并处理 `撕破脸` 前缀长短词的命中顺序
- relationship state / repeat 词表现在也开始覆盖 `尽释前嫌`、`反目为仇` 这类常见关系表达，并继续补齐 `反目*` 前缀长短词的命中顺序
- conflict 侧成对出现的 `timeline / outline` 章节改写说明，现已开始收敛成跨域 `story-beat:*` token，减少不同子组之间重复的 scene/event 文案
- conflict 侧 `constraints:rewrite-cutoff + story-beat:carry-forward`，现已开始收敛成跨域 `cutoff-resolution:carry-forward`
- conflict 侧 `timeline / outline` 章节改写直写路径，现已开始收敛成跨域 `delay-resolution:rewrite-chapter`
- conflict 侧成对出现的 exception note 写入说明，现已开始收敛成跨域 `exception-note:record`，减少重复的 canon / constraints review write-shape 文案
- conflict 侧 `resolve-world-rule-by-updating-cutoff / resolve-world-rule-by-delaying-event` 的 impact，现已开始收敛成跨域 `cutoff-resolution:update-placement / delay-resolution:update-placement`
- 如果某条 conflict rule 已被这些共享行完整覆盖，grouped summary 现在也不会再留空的 `rule-xxx:` 占位行
- `exception_scope` 开始细分成 `exception_scope_base / exception_subject_scope / exception_match_mode`，并把 `review-subject-scope / review-exception-chain / review-exception-evidence` 这类 impact token 稳定写出
- 对 `prior-exception`，review impacts 开始细分到 `canon:review-exception-continuity`、`constraints:review-exception-chain`、`timeline:review-post-exception-beat`、`outline:review-post-exception-scene`
- 对 `prior-exception`，grouped summary 现在还会继续细分 `write_shapes`，直接区分 `keep-existing-exception-record / carry-forward-exception-note / append-post-exception-beat / append-post-exception-scene-note` 这类更接近执行层的复核动作
- 如果 `prior-exception` 下的默认 merge 输入实际命中既有 `event_id / scene_id`，对应 `write_shapes` 现在也会自动从 `append-post-exception-*` 收紧成 `rewrite-post-exception-*`
- 如果 `prior-exception` 当前不需要继续动 timeline / outline，grouped summary 现在会继续收紧成 `annotate-existing-exception-record / annotate-existing-rule-note`，明确这轮只补 canon / constraints 注释
- 对 `prior-exception + local-signal`，如果这轮没有可落地的 `event_id / scene_id`，grouped summary 现在会优先收敛到 `review-exception-evidence`，不再误带 `review-exception-chain`
- 对 `prior-exception + local-signal`，如果别的主体只出现在主体窗口外，grouped summary 现在仍保持 `review-exception-evidence`；只有主体窗口内已经混进别的主体时，才会额外升级到 `review-subject-scope`
- 对 `prior-exception + local-signal`，如果句子先提到别的主体、但在知识谓词前又重新落回规则主体，consistency 现在会继续保持 `shared-subject`，不再误升成 `mixed-subjects`
- 对 `prior-exception + local-signal`，如果别的主体出现在知识谓词后、并自己带第二个 knowledge verb，consistency 现在也会稳定升级成 `mixed-subjects`
- 对 `prior-exception + local-signal`，如果别的主体出现在知识谓词后、但后续 knowledge verb 前又重新落回规则主体，consistency 现在也会继续保持 `shared-subject`
- 对 `claim-match`，如果另一个角色只是旁观出场、但自己附近没有 knowledge signal，exception scope 现在也会继续保持 `shared-subject`，不再仅凭 `character_mentions` 误升成 `split-subjects`
- 对 `claim-match`，如果中间只是提到别的角色、后面又回到规则主体的第二个 knowledge verb，draft claim 抽取现在也不会再凭空造出那名角色的假 claim
- 对 draft claim 抽取，像“林舟和苏岚都知道...”这类并列主体共用一个 knowledge verb 的句式，仍会继续稳定拆成多主体 claim，不会被窗口收紧误截断
- 对 draft claim 抽取，像“林舟与阿岚知道...”这种别名参与的并列主体共享 knowledge verb，现也会继续稳定拆成 `林舟 / 苏岚` 两条 claim
- 对 draft claim 抽取与 subject-scope 扫描，如果第二主体只是落在“告诉 / 告知 / 提醒 / 通知”后的受词位置，后面的 knowledge verb 现在也会继续归给规则主体，不会再把“林舟告诉苏岚自己知道...”误抽成苏岚知情，或误升成 `mixed-subjects`
- 对 draft claim 抽取与 subject-scope 扫描，如果第二主体只是落在“从 / 由 / 经 + 某人 + 那里 / 这边 / 口中 / 处”这类来源短语里，后面的 knowledge verb 现在也会继续归给规则主体，不会再把“林舟从苏岚那里知道...”误抽成来源角色知情，或误升成 `mixed-subjects`
- 对 draft claim 抽取与 subject-scope 扫描，如果第二主体只是落在“听某人提起 / 说起 / 讲起”这类转述来源短语里，后面的 knowledge verb 现在也会继续归给规则主体，不会再把“林舟听苏岚提起后知道...”误抽成来源角色知情
- 对 draft claim 抽取与 subject-scope 扫描，如果第二主体只是落在“因 / 因为某人一句话 / 提醒 / 提点”这类触发短语里，后面的 knowledge verb 现在也会继续归给规则主体，不会再把“林舟因苏岚一句话才知道...”误抽成触发角色知情
- 对 draft claim 抽取与 subject-scope 扫描，如果另一角色只有短 alias 或称谓，且这枚 token 只是嵌在“岚城 / 阿岚街 / 白狼营 / 白狼帮 / 白狼会 / 白狼令 / 白狼封阵术 / 持白狼封阵术 / 借白狼封阵术 / 操控白狼巨舰”这类地名、设定名词、组织名、机构名或物件/术式名里，consistency 现在也不会再把它误当主体命中，更不会因此截断规则主体窗口或凭空造出假 claim
- 对 draft claim 抽取，如果规则主体只是“意识到 / 知道 / 发现”另一个角色已经知情，后面的嵌套 knowledge 子句现在也不会再反向污染规则主体本人，不会再把“林舟意识到苏岚知道...”误抽成林舟直接知道该事实
- 对 draft claim 抽取，如果外层只是“怀疑 / 猜测 / 听说 / 觉得 / 担心”另一个角色已经知情，内层 knowledge 子句现在也不会再被当成该角色已被正式证实的 direct claim，不会再把“林舟怀疑白狼知道...”误报成白狼真的知道
- 对 draft claim 抽取，如果 speculative 外层和内层主体之间只插了“那个 / 这名 / 那位”这类指代修饰，内层 knowledge 子句现在也仍会继续被视为未证实，不会再把“林舟怀疑那个白狼知道...”误报成白狼真的知道
- 对 draft claim 抽取，如果 speculative 外层和内层主体之间再夹着“那时 / 当时 / 第七章 / 在”这类时间或章节 filler，内层 knowledge 子句现在也仍会继续被视为未证实，不会再把“林舟怀疑那时那个白狼知道...”误报成白狼真的知道
- 对 draft claim 抽取，如果外层只是“据说 / 传闻 / 听闻”这类更弱的传闻前缀，内层 knowledge 子句现在也仍会继续被视为未证实，不会再把“据说那时那个白狼知道...”误报成白狼真的知道
- `same-chapter exemption` 的 review case 现在也开始补 `timeline:review-same-chapter-beat` / `outline:review-same-chapter-scene`，并和 `evidence-only / review-subject-scope` 规则保持一致
- 如果同一条 idea 同时还有 `world-rule conflict`，grouped summary 现在会先提一条 `shared-world-rule-context`，把 conflict 行和 exemption 行共同拥有的 `domains / targets` 上提
- 多条 exemption rule 共享同一批 review token 时，grouped summary 现在会先提一条 `shared-exemption-review`，把公共 `review_impacts / review_write_shapes / targets` 上提，减少逐条重复
- 如果同一组 exemption 同时混有 `direct` 和 `review`，grouped summary 现在还会再提一条 `shared-exemption-base`，把公共 `impacts / targets / domains` 再上提一层
- 对 `prior-exception + claim-match` 的叙事型 idea，如果这轮还没落到具体 event / scene，但已经是明确剧情 beat，grouped summary 现在仍会保留 `carry-forward-exception-note`
- 如果这类 `claim-match` 叙事型 case 同时落在 `split-subjects / mixed-subjects`，grouped summary 现在会退回 `annotate-existing-rule-note + review-subject-scope`，不再默认共用 exception chain
- world-rule 相关的 canon explainer 开始引用各自命中的 claim，而不是回退到第一条 claim
- 多条 rule 共享同一事件/场景写入时，重复的 timeline / outline explainers 开始做去重收敛
- conflict / exemption 的逐条 rule 行开始省掉和 `direct_/review_` 完全重合的 `impacts=` / `write_shapes=`，减少 grouped summary 明细噪音
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

当前最值得继续推进的，不再是继续堆顶层 grouped summary 压缩，而是：

- 更细的 `knowledge-state / world-rule` claim 提取边界
- 更少误报的 `subject-scope / mixed-subject` 判定
- 以及把这些边界稳定沉到可测试的脚本规则里

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
- 细化 `prior-exception` 写入组合：grouped summary 已开始把“沿用旧 exception 但还需复核什么”继续拆成更接近执行的 `write_shapes`
- 收紧 `prior-exception` 写入形态：如果默认 merge 输入实际命中既有 event / scene，grouped summary 已开始把 `append` 自动改判成 `rewrite`
- 收紧 `prior-exception` 注释边界：如果当前 case 不需要 timeline / outline 写入，grouped summary 已开始把 review 收敛到纯 `annotate` 组合
- 收紧 `local-signal` 证据边界：如果这轮没有可落地的 event / scene 标识，grouped summary 已开始只提示 evidence note，而不再误判成 chain 更新
- 细化 `local-signal` 多主体边界：如果别的主体只出现在窗口外，grouped summary 继续只做 evidence review；只有窗口内混主体时才升级 subject-scope review
- 收敛 `same-chapter` 说明层：同章 exemption 的 grouped summary 已开始和 `prior-exception` 共用同一套 evidence / subject-scope / timeline-outline review 规则
- 收敛 grouped summary 噪音：多条 exemption 的公共 review token 已开始集中上提，不再在每条 rule 行里重复展开
- 收敛 rule-line 噪音：如果 `impacts=` / `write_shapes=` 只是 `direct_/review_` 的并集，明细行现在直接省掉泛化字段，避免同一 token 同行重复
- 收敛 exemption shared-line 噪音：`shared-exemption-review` 现在不再重复 `shared-exemption-base` 已经承载的 `domains / targets / reuse-exception` 公共项
- 收敛 exemption scope 噪音：多条 `reuse-existing-exception` 行里重复的 `subject_scope / exception_scope_*` 现在会先上提到 `shared-exemption-scope`
- 收敛 exemption rule-token 噪音：多条 `reuse-existing-exception` 行里重复的 `direct / review / subjects` 现在会先上提到 `shared-exemption-rule-tokens`
- 收敛 exemption 壳行噪音：如果若干 exemption 行只剩 exception id，grouped summary 现在会改成一条 `shared-exemption-links`
- 收紧 exception 选取边界：同一 rule 命中多条 exception 时，现在会优先选最贴近当前 draft chapter 的匹配记录，不再按存储顺序误选更早链路
- 收紧 relationship repeat 词表边界：`再度` 现在也会触发 future repeat after transition 的豁免，不再只识别 `重新 / 再次 / 又`
- 收紧 relationship 语义词表边界：`重归于好` 现在会同时触发 `reconciled` 状态与 repeat hint，`反目` 现在会映射到 `ruptured`
- 收紧 relationship 语义词表边界：`冰释前嫌` 现在也会同时触发 `reconciled` 状态与 repeat hint，`翻脸` 现在会映射到 `ruptured`
- 收紧 relationship 语义词表边界：`破镜重圆` 现在也会同时触发 `reconciled` 状态与 repeat hint，`闹翻` 现在会映射到 `ruptured`
- 收紧 relationship 语义词表边界：`言归于好` 现在也会同时触发 `reconciled` 状态与 repeat hint，`彻底翻脸` 现在会映射到 `ruptured`
- 收紧 relationship 语义词表边界：`握手言和` 现在也会同时触发 `reconciled` 状态与 repeat hint，`恩断义绝` 现在会映射到 `ruptured`
- 细化 `claim-match` 注释边界：叙事型 idea 在无 event / scene targets 时，grouped summary 已开始保留 `carry-forward`，而纯设定型则继续只走 `annotate`
- 收紧多主体 `claim-match` 边界：叙事型 idea 在 `split-subjects / mixed-subjects` 下，grouped summary 已开始从 `carry-forward` 退回 `annotate + review-subject-scope`
- 收紧同章锚点边界：如果当前 chapter 已经有正式的 knowledge-state / relationship 记录，future duplicate 不再反向把 idea 报成前移或漂移
- 收紧无 claim 的 world-rule 边界：exception fallback 与规则命中都开始按主体局部窗口判断，不再把另一主体的 object 误算进来
- 增加 exemption 可见性：同章 / 既有 world-rule exception 不再只在底层放行，report 与 plan 都开始显式标记
- 收敛 world-rule 说明噪音：已豁免 rule 不再单独挂一条 summary，而是开始和冲突 rule 共享一条 grouped constraints 说明
- 但 `prior-exception` 的 domain impact 仍是第一层保守拆分，后续还可以继续细化到更明确的写入组合

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
