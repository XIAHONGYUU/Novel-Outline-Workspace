# Next Actions

最后更新：2026-05-22

## 现在优先做什么

### P0

1. 继续扩展 timeline-order / knowledge-state 规则
   目标：继续补 chapter drift 与知识状态边界；“更早记录优先、避免未来重复双报”“扩写标题的安全部分匹配”“knowledge object 的保守同义归一”“world-rule 与 knowledge_claims 的 subject/object 协同”“多 claim / 多 rule 的基本分流”“constraints 分组摘要 explainer”“rule 级 direct/override/targets 影响面说明”“canon 侧 claim 级 source signal 对齐”“重复 explainer 去重收敛”“rule 级 impacts 跨 domain 摘要”“direct / review impacts 拆分”“shared-subject / split-subjects exception scope”“标题/正文泛化 claim 收敛”“mixed-subject claim 串绑收紧”“identity family 更具体 claim 收敛”已完成，下一步转向更多 object family。

2. 收紧 relationship / world-rule exception 边界
   目标：明确哪些关系冲突能靠 canon 记录直接解 gate，哪些 world-rule 例外在 mixed-subject / 多 rule 场景下仍需要更细的边界与展示。

3. 增强 repair / merge explainers
   目标：让 intake backfill 与 merge plan 都能更明确地区分“推断补回”与“可直接执行”的写入。

### P1

4. 补更多验收逻辑
   目标：覆盖 canon explainers、constraints explainers、repair explainers 的边界路径。

5. 收敛 skill 与 script 边界
   目标：把可确定执行的 repair / merge / render 动作继续沉到底层脚本。

6. 继续清理 demo / docs 闭环
   目标：让示例工作区和顶层说明始终指向同一条可继续推进的 pending path。

## 建议执行顺序

1. 先继续补 timeline-order / knowledge-state 规则
2. 再收紧 relationship / world-rule exception 边界
3. 然后增强 repair / merge explainers

## 下一次开工时的最小切入点

如果只做一个任务，优先做这个：

`先继续补 timeline-order / knowledge-state 的判定边界，尤其是 title-based drift 和 canon knowledge-state 的协同。`

刚完成的一步：

- `knowledge-state conflict` 在同时命中更早与更晚记录时，现已优先只保留更早冲突
- `title-based drift` 对带括注 / 副标题的正式事件名与场景名，现已支持安全的部分匹配
- `knowledge object` 现已支持一批保守同义匹配，并压掉“共享前缀但不是同一事实”的误报
- `world-rule conflict` 与 `world_rule_exception` 现已开始复用 `knowledge_claims` 做 subject/object 匹配，不再只靠原句字面串
- `plan_idea_merge` 现已能把单 idea 下不同 rule 分别绑定到各自命中的 claim，避免多 rule 共用同一 exception object
- 多条 `world-rule` 同时命中时，`proposed_actions` 现已先输出 constraints 分组摘要，方便先按 rule 级别决策
- constraints 分组摘要现已直接带出每条 rule 的策略、目标文件、direct/override 信息，以及按 direct / review 拆开的 impacts
- 多主体命中的 world-rule 现已在 grouped summary 里显式标记 `shared-subject / split-subjects`，避免误把不同主体的 exception 当成一条解释链
- 同一主体如果同时命中标题泛化 object 和正文更具体 object，`knowledge_claims` 现已优先收敛到更具体那条
- 多主体句子里如果不同主体分别对应不同 object，`knowledge_claims` 现已开始按主体窗口拆开，避免 object 串绑
- `identity` family 里的近义 object，`knowledge_claims` 现已开始优先保留更具体那条
- world-rule 相关的 canon explainer 现已对齐到各自命中的 claim，不再误指第一条 claim
- 多条 rule 共享同一事件/场景写入时，重复的 timeline / outline explainer 现已开始自动收敛

下一批优先补的冲突：

- 更细的 `timeline-order conflict`
- 更细的 `knowledge-state conflict`
- relationship / world-rule exception 的匹配边界
- mixed-subject / 多 rule 的 world-rule exception 边界
- 更多 `knowledge object` family 去重
- grouped summary 与逐条 explainer 的进一步压缩
- intake repair 的 explainers 与批量回写摘要
- rule-specific explainers

## 暂时不要优先做

- 高交互前端
- 全自动语义重写章节摘要
- 复杂地图式展示
- 一次性扩太多 skill
