# Next Actions

最后更新：2026-05-28

## 现在优先做什么

### P0

1. 继续扩展 timeline-order / knowledge-state 规则
   目标：在已完成的 object family 收敛与 subject-window 收紧基础上，继续补更细的 claim / subject-scope 边界，优先处理“真实多主体 claim”与“嵌入名词假主体命中”之外剩余的 chapter-scoped 误判。

2. 收紧 relationship / world-rule exception 边界
   目标：明确哪些关系冲突能靠 canon 记录直接解 gate，哪些同章 relationship beat 应直接视为已落地，哪些 world-rule 例外在 mixed-subject / 多 rule / chapter-scoped 场景下仍需要更细的边界与展示。

3. 增强 repair / merge explainers
   目标：让 intake backfill 与 merge plan 都能更明确地区分“推断补回”与“可直接执行”的写入。

### P1

4. 补更多验收逻辑
   目标：覆盖 canon explainers、constraints explainers、repair explainers 的边界路径。

5. 收敛 skill 与 script 边界
   目标：把可确定执行的 repair / merge / render 动作继续沉到底层脚本。

6. 继续清理 demo / docs 闭环
   目标：让 `demo-workspace/`、`first-workflow-case/` 和顶层说明始终指向清晰可继续的 pending path。

## 建议执行顺序

1. 先继续补 timeline-order / knowledge-state 规则
2. 再收紧 relationship / world-rule exception 边界
3. 然后增强 repair / merge explainers

## 下一次开工时的最小切入点

如果只做一个任务，优先做这个：

`先继续补 claim-level subject-scope 的正反边界，优先“同句内存在第二主体，但它只是动作接受者 / 被提及对象 / 旁观者，不应升级成 mixed-subjects”的 case。`

刚完成的一步：

- `knowledge-state conflict` 在同时命中更早与更晚记录时，现已优先只保留更早冲突
- `title-based drift` 对带括注 / 副标题的正式事件名与场景名，现已支持安全的部分匹配
- `knowledge object` 现已支持一批保守同义匹配，并压掉“共享前缀但不是同一事实”的误报
- `world-rule conflict` 与 `world_rule_exception` 现已开始复用 `knowledge_claims` 做 subject/object 匹配，不再只靠原句字面串
- `plan_idea_merge` 现已能把单 idea 下不同 rule 分别绑定到各自命中的 claim，避免多 rule 共用同一 exception object
- 多条 `world-rule` 同时命中时，`proposed_actions` 现已先输出 constraints 分组摘要，方便先按 rule 级别决策
- constraints 分组摘要现已直接带出每条 rule 的策略、目标文件、direct/override 信息，以及按 direct / review 拆开的 impacts
- 如果多条 `world-rule conflict` 之间共享同一批 context，grouped summary 现已会先提一条 `shared-conflict-context`，把公共 `domains / targets` 上提
- 如果多条 `world-rule conflict` 连动作层也完全相同，grouped summary 现已还会再提一条 `shared-conflict-actions`，把公共 `direct/review impacts` 与 `write_shapes` 上提
- 如果只有部分 conflict rule 共享同一套动作签名，grouped summary 现已也会按 `rules=...` 再提 subset 级 `shared-conflict-actions`
- 如果同一批 conflict 连策略、direct/override 和主体范围也完全一致，grouped summary 现已还会再提一条 `shared-conflict-structure`
- 如果策略或主体不同、但 `direct / override / subject_scope` 仍重复，grouped summary 现已也会按 `rules=...` 再提一条 `shared-conflict-structure-tokens`
- 如果同一批 mixed conflict 子组同时共享结构 token 和 `strategies/subjects + domains/targets`，grouped summary 现已也会把这两层局部描述合成一条 `shared-conflict-rule-metadata`
- 如果同一批 mixed conflict 子组同时共享 `shared-conflict-rule-metadata` 和 action fields，grouped summary 现已也会再合成一条 `shared-conflict-rule-summary`
- 如果当前批次的全局 conflict context 和全局 conflict actions 同时存在，grouped summary 现已也会把 `shared-conflict-context + shared-conflict-actions` 合成一条顶层 `shared-conflict-summary`
- 如果这条顶层 conflict summary 对应的全部 rule 结构也完全一致，grouped summary 现已还会继续把 `shared-conflict-summary + shared-conflict-structure` 合成一条 `shared-conflict-overview`
- 如果 mixed conflict 子组里 `strategies=` 或 `subjects=` 仍重复，grouped summary 现已也会按 `rules=...` 再提一条 `shared-conflict-rule-tokens`
- 如果同一批 mixed conflict 子组同时共享 `strategies/subjects` 和 `domains/targets`，grouped summary 现已也会把这两条局部描述行合成一条 `shared-conflict-rule-details`
- 如果 mixed conflict 子组里 `domains=` 或 `targets=` 仍重复，grouped summary 现已也会按 `rules=...` 再提一条 `shared-conflict-rule-context`
- 如果 mixed conflict 子组里 `direct_impacts=` 或 `review_impacts=` 仍重复，grouped summary 现已也会按 `rules=...` 再提一条 `shared-conflict-rule-impacts`
- 如果不同 conflict 子组虽然整体签名不同，但还共享同一批 `write_shapes`，grouped summary 现已也会按 `rules=...` 再提一条 `shared-conflict-write-shapes`
- 如果同一批 mixed conflict 子组同时共享 `impacts` 和 `write_shapes`，grouped summary 现已也会把这两条局部 action 行合成一条 `shared-conflict-rule-actions`
- 如果某条 conflict / exemption rule 行里的 `impacts=` 或 `write_shapes=` 只是 `direct_/review_` 桶的并集，grouped summary 现已也会直接省掉这层泛化字段，避免同一 token 在明细行里重复两次
- 如果 `shared-exemption-base` 已经承载了公共 `domains / targets / reuse-exception impacts`，`shared-exemption-review` 现已也会自动扣掉这部分 base token，只保留 review 专属补充
- 如果多条 exemption 共享同一批 `subject_scope / exception_scope_*` 元信息，grouped summary 现已也会按 `rules=...` 再提一条 `shared-exemption-scope`
- 如果多条 exemption 共享同一批 `direct / review / subjects` 元信息，grouped summary 现已也会按 `rules=...` 再提一条 `shared-exemption-rule-tokens`
- 如果某批 exemption 行在扣掉共享 token 后只剩 exception id，grouped summary 现已也会再提一条 `shared-exemption-links`，把这些壳行收成一条映射
- 如果同一 rule 同时命中更早的 prior exception 和当前章 same-chapter exception，consistency / merge 现已也会优先选当前章那条，避免把本可 direct 的 case 误降成 review
- relationship repeat hint 现已也开始覆盖 `再度` 这类常见重启关系 wording，减少“再度结盟 / 再度和解”被误报成 future drift
- relationship state / repeat 词表现已也开始覆盖 `重归于好`、`反目` 这类常见关系表达，减少 reconciliation / rupture 场景的漏判与误报
- relationship state / repeat 词表现已也开始覆盖 `冰释前嫌`、`翻脸` 这类常见关系表达，进一步补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现已也开始覆盖 `破镜重圆`、`闹翻` 这类常见关系表达，继续补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现已也开始覆盖 `言归于好`、`彻底翻脸` 这类常见关系表达，继续补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现已也开始覆盖 `握手言和`、`恩断义绝` 这类常见关系表达，继续补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现已也开始覆盖 `重修旧好`、`撕破脸` 这类常见关系表达，继续补齐 reconciled / ruptured 的常见中文写法
- relationship state / repeat 词表现已也开始覆盖 `一笑泯恩仇`、`反目成仇` 这类常见关系表达，并处理 `反目` 前缀长短词的命中顺序
- relationship state / repeat 词表现已也开始覆盖 `化干戈为玉帛`、`撕破脸皮` 这类常见关系表达，并处理 `撕破脸` 前缀长短词的命中顺序
- relationship state / repeat 词表现已也开始覆盖 `尽释前嫌`、`反目为仇` 这类常见关系表达，并继续补齐 `反目*` 前缀长短词的命中顺序
- conflict 侧直写路径的写入说明，现已开始收敛成跨域 `delay-resolution:rewrite-chapter / cutoff-resolution:carry-forward`
- conflict 侧成对出现的 exception note 写入说明，现已开始收敛成跨域 `exception-note:record`
- conflict 侧直写路径的 impact，现已开始收敛成跨域 `delay-resolution:update-placement / cutoff-resolution:update-placement`
- 如果某条 conflict rule 已被这些共享行完整覆盖，grouped summary 现已也不会再留空的 `rule-xxx:` 占位行
- 多主体命中的 world-rule 现已在 grouped summary 里显式标记 `shared-subject / split-subjects`，避免误把不同主体的 exception 当成一条解释链
- 同一主体如果同时命中标题泛化 object 和正文更具体 object，`knowledge_claims` 现已优先收敛到更具体那条
- 多主体句子里如果不同主体分别对应不同 object，`knowledge_claims` 现已开始按主体窗口拆开，避免 object 串绑
- `identity / leak / same-camp / separate-camp` family 里的近义 object，`knowledge_claims` 现已开始优先保留更具体那条
- `same-camp / separate-camp` family 里如果只是 wording 不同，`knowledge_claims` 现已开始优先保留更标准表达
- cross-family claim 当前仍保持分离，避免把不同事实误合并
- 如果同章已经有正式 event / scene / canon `knowledge-state` 记录，future duplicate 现已不再把当前 idea 误报成知情点前移
- 如果同章已经有正式 relationship beat，future same-state 记录现已不再把当前 idea 误报成关系漂移
- `world-rule` 在缺少 `knowledge_claims` 时，现已开始按主体局部窗口抽取 knowledge signal；同章 exception 的同义 object 不再只靠全句字面串命中，mixed-subject 句子里别人的 object 也不会误触发当前 rule
- consistency report 现已开始显式输出 `world-rule-exemption-applied`，merge plan 在 clean gate 下也会补一条 exemption explainer，说明这是“已落地豁免”而不是“没命中规则”
- 对已落地的 exception，grouped summary 现已开始区分 `direct` 沿用和仍需 `review` 的主体范围；如果同一 idea 同时存在冲突 rule 和已豁免 rule，也会收敛进同一条 constraints summary
- `exception_scope` 现已开始拆成 `exception_scope_base / exception_subject_scope / exception_match_mode`，并稳定产出 `constraints:review-subject-scope`、`constraints:review-exception-chain`、`canon:review-exception-evidence` 这类 review impact token
- `prior-exception` 的 review impacts 现已开始拆到 `canon / constraints / timeline / outline` 四层
- `prior-exception` 的 grouped summary 现已直接带出 `review-exception-continuity / review-exception-chain / review-post-exception-beat / review-post-exception-scene`
- `prior-exception` 的 grouped summary 现已继续细分 `write_shapes`，开始明确写出 `keep-existing-exception-record / carry-forward-exception-note / append-post-exception-beat / append-post-exception-scene-note`
- 如果默认 merge 输入实际命中既有 `event_id / scene_id`，`prior-exception` 的 grouped summary 现已会把 `append-post-exception-*` 自动收紧成 `rewrite-post-exception-*`
- 如果当前 case 不需要 timeline / outline 写入，`prior-exception` 的 grouped summary 现已会继续收紧成 `annotate-existing-exception-record / annotate-existing-rule-note`
- 对 `prior-exception + local-signal`，如果这轮没有可落地的 `event_id / scene_id`，grouped summary 现已会继续收紧成纯 `review-exception-evidence`
- 对 `prior-exception + claim-match` 的叙事型 idea，如果这轮虽然还没落到 event / scene target，grouped summary 现已仍会保留 `carry-forward-exception-note`
- 如果这类 `claim-match` 叙事型 case 同时落在 `split-subjects / mixed-subjects`，grouped summary 现已会退回 `annotate-existing-rule-note + review-subject-scope`
- 对 `prior-exception + local-signal`，如果别的主体只出现在窗口外，grouped summary 现已继续只做 `review-exception-evidence`；只有窗口内混主体时才升级 `review-subject-scope`
- 对 `prior-exception + local-signal`，如果句子先提到别的主体、但在知识谓词前又重新落回规则主体，consistency 现已继续保持 `shared-subject`，不再误升成 `mixed-subjects`
- 对 `prior-exception + local-signal`，如果别的主体出现在知识谓词后、并自己带第二个 knowledge verb，consistency 现已也会稳定升级成 `mixed-subjects`
- 对 `prior-exception + local-signal`，如果别的主体出现在知识谓词后、但后续 knowledge verb 前又重新落回规则主体，consistency 现已也会继续保持 `shared-subject`
- 对 `claim-match`，如果另一个角色只是旁观出场、但自己附近没有 knowledge signal，exception scope 现已也会继续保持 `shared-subject`，不再仅凭 `character_mentions` 误升成 `split-subjects`
- 对 `claim-match`，如果中间只是提到别的角色、后面又回到规则主体的第二个 knowledge verb，draft claim 抽取现已也不会再凭空造出那名角色的假 claim
- 对 draft claim 抽取，像“林舟和苏岚都知道...”这类并列主体共用一个 knowledge verb 的句式，现已也会继续稳定拆成多主体 claim，不会被窗口收紧误截断
- 对 draft claim 抽取，像“林舟与阿岚知道...”这种别名参与的并列主体共享 knowledge verb，现已也会继续稳定拆成 `林舟 / 苏岚` 两条 claim
- 对 draft claim 抽取与 subject-scope 扫描，如果另一角色只有短 alias 或称谓，且这枚 token 只是嵌在“岚城 / 阿岚街 / 白狼营 / 白狼帮 / 白狼会 / 白狼令 / 白狼封阵术 / 持白狼封阵术 / 借白狼封阵术 / 操控白狼巨舰”这类地名、设定名词、组织名、机构名或物件/术式名里，consistency 现已也不会再把它误当主体命中，更不会因此截断规则主体窗口或凭空造出假 claim
- 对 draft claim 抽取，如果规则主体只是意识到/发现另一个角色已经知情，嵌套 knowledge 子句现已也不会再反向污染规则主体本人，不会再把“林舟意识到苏岚知道...”误抽成林舟直接知道该事实
- 对 draft claim 抽取，如果外层只是怀疑/猜测/听说/觉得/担心另一个角色已经知情，内层 knowledge 子句现已也不会再被当成该角色已被正式证实的 direct claim，不会再把“林舟怀疑白狼知道...”误报成白狼真的知道
- 对 draft claim 抽取，如果 speculative 外层和内层主体之间只插了“那个 / 这名 / 那位”这类指代修饰，内层 knowledge 子句现已也仍会继续被视为未证实，不会再把“林舟怀疑那个白狼知道...”误报成白狼真的知道
- 对 draft claim 抽取，如果 speculative 外层和内层主体之间再夹着“那时 / 当时 / 第七章 / 在”这类时间或章节 filler，内层 knowledge 子句现已也仍会继续被视为未证实，不会再把“林舟怀疑那时那个白狼知道...”误报成白狼真的知道
- 对 draft claim 抽取，如果外层只是“据说 / 传闻 / 听闻”这类更弱的传闻前缀，内层 knowledge 子句现已也仍会继续被视为未证实，不会再把“据说那时那个白狼知道...”误报成白狼真的知道
- `same-chapter exemption` 的 review case 现已开始补 `review-same-chapter-beat / review-same-chapter-scene`，并复用同一套 `evidence-only / review-subject-scope` 规则
- 如果同一条 idea 同时还有 `world-rule conflict`，grouped summary 现已会先提一条 `shared-world-rule-context`，把 conflict 行和 exemption 行共同拥有的 `domains / targets` 上提
- 多条 exemption rule 如果共享同一批 `review_impacts / review_write_shapes / targets`，grouped summary 现已会先提一条 `shared-exemption-review`，把公共 review token 上提，减少逐条重复
- 如果同一组 exemption 同时混有 `direct` 和 `review`，grouped summary 现已还会再提一条 `shared-exemption-base`，把公共 `impacts / targets / domains` 再上提一层
- 新增 `first-workflow-case/` 作为首个独立案例工作区，当前停在 `check-consistency` 已过、`plan-merge` 已生成、尚未 `apply`
- world-rule 相关的 canon explainer 现已对齐到各自命中的 claim，不再误指第一条 claim
- 多条 rule 共享同一事件/场景写入时，重复的 timeline / outline explainer 现已开始自动收敛

下一批优先补的冲突：

- 更细的 `timeline-order conflict`
- 更细的 `knowledge-state conflict`
- relationship / world-rule exception 的匹配边界
- mixed-subject / 多 rule 的 world-rule exception 边界
- 更多 `knowledge object` family 去重，以及更细的 chapter-scoped exception / relationship gate 边界
- 不同 conflict 子组之间剩余的 scene/event 写入文案与差异字段继续细化
- grouped summary 与逐条 explainer 的进一步压缩
- intake repair 的 explainers 与批量回写摘要
- rule-specific explainers

## 暂时不要优先做

- 高交互前端
- 全自动语义重写章节摘要
- 复杂地图式展示
- 一次性扩太多 skill
