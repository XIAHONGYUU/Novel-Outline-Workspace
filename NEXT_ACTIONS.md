# Next Actions

最后更新：2026-06-03

## 现在优先做什么

### P0

1. 定义并锁定 `P0` 收口标准  
   目标：明确“什么时候主链路算稳定可用”，不再用无限补规则代替阶段完成。  
   至少应包含：
   - `ingest -> check-consistency -> plan-merge -> apply-merge -> validate` 能在样例工作区稳定跑通
   - 哪些 consistency 误判还必须修
   - 哪些边缘句式先接受为已知限制
   - 哪些产物必须同步更新：`state / reports / views`
   当前跟踪文档：
   - `docs/p0-closure-checklist.md`
   - `docs/workspace-acceptance-framework.md`

2. 把重心转到 `merge / apply` 的可执行性  
   目标：让系统不只是更会解释问题，而是更会把问题落成稳定写入。  
   重点检查：
   - `plan_idea_merge` 是否足够短、足够可执行
   - `apply_idea_merge` 是否能稳定写入 `canon / timeline / outline`
   - `warning-only / needs-info` case 是否总能被明确收敛到 `repair-intake`
   - 多 merge inputs 的组合 apply 是否已覆盖主要真实 case
   - repair / merge explainers 是否能直接指导人工决策

3. 用真实 workspace 做工作区级验收  
   目标：不再主要靠句式级单测判断阶段成熟度，而是看真实工作区能否闭环推进。  
   当前验收对象：
   - `demo-workspace/`
   - `first-workflow-case/`
   重点看：
   - 是否都能保持清晰的 pending path
   - 是否能稳定产出 merge plan
   - apply 后的状态、视图、校验是否一致
   当前进展：
   - `first-workflow-case/` 已完成首轮完整闭环
   - `demo-workspace/` 已把 `needs-info` 路径收紧成显式 `repair-intake`
   - `demo-workspace/` 的 `idea-20260511-006` 已完成真实闭环，当前 pending=0
   - `demo-workspace/` 的 `idea-20260602-001` 已完成真实 multi-input apply，`timeline / outline + canon knowledge-state` 已在真实 workspace 一次性落地
   - `demo-workspace/` 的 `idea-20260602-002` 已完成真实 relationship 闭环，`outline scene + canon relationship` 已在真实 workspace 一次性落地
   - `demo-workspace/` 的 `idea-20260602-003` 已完成真实 same-state repeat beat 闭环：保留第 5 章既有 `canon relationship`，只把第 6 章“再次结盟”落成 scene
   - `demo-workspace/` 的 `idea-20260602-004` 已完成真实 relationship state transition 闭环：第 7 章 `决裂` 已作为新的 `canon relationship` 历史节点落库
   - `demo-workspace/` 的 `idea-20260603-001` 已完成真实 relationship reconciliation 闭环：第 9 章 `和解` 已作为新的 `canon relationship` 历史节点落库
   - `repair-intake -> plan-merge -> apply-merge` 已有脚本级集成闭环，也已有真实 workspace 验收

### P1

4. 补工作区级验收测试  
   目标：继续增加覆盖主流程成功路径的集成型测试，而不是继续主要堆规则微测例。  
   当前进展：
   - 已覆盖 `repair-intake -> plan-merge -> apply-merge` 的脚本级闭环

5. 真正做厚 `timeline merge`  
  目标：把 `timeline_merge_inputs` 从“解释层输入”继续推进成更稳定的执行层。

6. 收敛 skill 与 script 边界  
   目标：把确定性 `repair / merge / render` 动作继续沉到底层脚本，减少高层流程的模糊行为。

## 建议执行顺序

1. 先写清楚 `P0` 收口 checklist
2. 再用 `first-workflow-case/` 跑一次完整闭环并记录卡点
3. 然后回头修最影响 `merge / apply` 稳定性的缺口
4. 先验证“已有 `reconciled` 节点之后的 repeat beat / 再结盟”时，该如何与既有 history chain 对齐
5. 再在真实 workspace 里补齐“关系复用 / 状态转移 / 冲突收敛”，而不是回到临时测试工作区
6. 最后再决定哪些 consistency 细节值得继续追

## 顶层原则

接下来默认先补 framework，再补细节：

- 先看 `acceptance track` 有没有完整
- 再看是哪一个真实 workspace case 最适合补这条 track
- 不再默认因为某个微规则还能补，就把它提到顶层优先级

## 下一次开工时的最小切入点

如果只做一个任务，优先做这个：

`优先找一条“先和解、后再次结盟/再次和解”的真实 idea，验证已有 reconciled 节点之后的 repeat beat 在真实 workspace 里如何收口。`

## 这次方向调整的含义

- `subject-scope / claim-level` 的局部规则已经补到“受词 / 来源 / 转述来源 / 触发短语”这一层
- 继续深挖句式边界的收益正在下降
- 接下来默认不再优先补新的中文句式微规则
- 只有当真实 workspace 闭环被明确卡住时，才回头修对应规则
- `first-workflow-case/` 已完成首轮完整闭环；`demo-workspace/` 也已补齐真实 multi-input apply
- `demo-workspace/` 现已补齐 `relationship` 首次落库样例
- `demo-workspace/` 现已补齐 same-state relationship repeat beat 的真实闭环样例
- `demo-workspace/` 现已补齐 relationship state transition 的真实闭环样例
- `demo-workspace/` 现已补齐 `allied -> ruptured -> reconciled` 的多段 relationship history chain 样例
- 当前最真实的缺口已经继续前移到“已有 reconciled 节点之后，repeat beat / 再变化怎样继续与 history chain 对齐”，而不是“relationship 能不能第一次落库”本身

## 暂时不要优先做

- 高交互前端
- 全自动语义重写章节摘要
- 复杂地图式展示
- 一次性扩太多 skill
