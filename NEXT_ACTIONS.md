# Next Actions

最后更新：2026-05-13

## 现在优先做什么

### P0

1. 扩展 `novel-timeline-merge`
   目标：在已落地的 `timeline_merge_inputs` 基础上，补更多 issue-specific 执行策略，优先扩展 `world-rule` 的多策略分支。

2. 扩展 `timeline_merge_inputs`
   目标：覆盖 `world-rule` 的“延后事件 / 对齐 cutoff / 修改规则说明”等更多 resolution path。

3. 继续扩展 `novel-consistency-check`
   目标：把当前 claim-based `knowledge-state` 和 relationship-history 推进到更稳定的图谱推理与豁免边界。

### P1

4. 扩展 intake 推断规则
   目标：提高角色、地点、章节、关系提示的稳定性，减少误报和漏报。

5. 为 merge plan 增加更明确的影响面说明
   目标：让 `timeline / outline / canon` 的改动建议更可执行。

6. 把更多验收逻辑补进测试
   目标：覆盖 intake draft、merge、validator、pipeline 的关键路径。

## 建议执行顺序

1. 先扩展 `novel-timeline-merge`
2. 再继续补 relationship / knowledge-state 图谱边界
3. 然后继续覆盖 world-rule / canon merge 输入

## 下一次开工时的最小切入点

如果只做一个任务，优先做这个：

`先把 world-rule 的单一路径 resolution input 扩成多策略输入。`

下一批优先补的冲突：

- 更细的 `timeline-order conflict`
- knowledge-state 的图谱级豁免和去重
- relationship-history 的图谱级豁免和重复状态去重
- world-rule conflict 的结构化执行建议
- world-rule 的多策略 resolution 选择
- rule-specific explainers

## 暂时不要优先做

- 高交互前端
- 全自动语义重写章节摘要
- 复杂地图式展示
- 一次性扩太多 skill
