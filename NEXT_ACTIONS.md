# Next Actions

最后更新：2026-06-01

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

### P1

4. 补工作区级验收测试  
   目标：增加覆盖主流程成功路径的集成型测试，而不是继续主要堆规则微测例。

5. 真正做厚 `timeline merge`  
   目标：把 `timeline_merge_inputs` 从“解释层输入”继续推进成更稳定的执行层。

6. 收敛 skill 与 script 边界  
   目标：把确定性 `repair / merge / render` 动作继续沉到底层脚本，减少高层流程的模糊行为。

## 建议执行顺序

1. 先写清楚 `P0` 收口 checklist
2. 再用 `first-workflow-case/` 跑一次完整闭环并记录卡点
3. 然后回头修最影响 `merge / apply` 稳定性的缺口
4. 再补一条覆盖 `repair-intake` 分支的工作区级集成测试
5. 再用真实 workspace 覆盖一次“多 merge inputs 一次性 apply”
6. 最后再决定哪些 consistency 细节值得继续追

## 下一次开工时的最小切入点

如果只做一个任务，优先做这个：

`优先补一条工作区级集成测试，覆盖 repair-intake -> plan-merge -> apply-merge，并用真实 workspace 再走一轮多 merge inputs 一次性 apply。`

## 这次方向调整的含义

- `subject-scope / claim-level` 的局部规则已经补到“受词 / 来源 / 转述来源 / 触发短语”这一层
- 继续深挖句式边界的收益正在下降
- 接下来默认不再优先补新的中文句式微规则
- 只有当真实 workspace 闭环被明确卡住时，才回头修对应规则
- `first-workflow-case/` 已完成首轮完整闭环；当前最真实的缺口已经从句式误判转成 `merge / apply` 的执行入口与批量消费能力

## 暂时不要优先做

- 高交互前端
- 全自动语义重写章节摘要
- 复杂地图式展示
- 一次性扩太多 skill
