# Next Actions

最后更新：2026-05-13

## 现在优先做什么

### P0

1. 扩展 `novel-consistency-check`
   目标：在现有可用版上补更强的 `knowledge-state` 和 patch 建议。

2. 开始实现 `novel-timeline-merge`
   目标：消费 intake draft、consistency gate 和 merge plan，稳定地更新 timeline / outline / canon。

3. 给 merge plan 产出更可执行的结构化 merge inputs
   目标：减少从“报告”到“真正写入”的人工跳跃。

### P1

4. 扩展 intake 推断规则
   目标：提高角色、地点、章节、关系提示的稳定性，减少误报和漏报。

5. 为 merge plan 增加更明确的影响面说明
   目标：让 `timeline / outline / canon` 的改动建议更可执行。

6. 把更多验收逻辑补进测试
   目标：覆盖 intake draft、merge、validator、pipeline 的关键路径。

## 建议执行顺序

1. 先扩展 `novel-consistency-check`
2. 再做 `novel-timeline-merge`
3. 然后把 merge plan 变成更接近执行输入的产物

## 下一次开工时的最小切入点

如果只做一个任务，优先做这个：

`先把 consistency gate 产物和 merge plan 摘要转成更可执行的 timeline merge 输入。`

下一批优先补的冲突：

- `knowledge-state conflict`
- 更细的 `timeline-order conflict`
- 结构化 patch 建议
- rule-specific explainers

## 暂时不要优先做

- 高交互前端
- 全自动语义重写章节摘要
- 复杂地图式展示
- 一次性扩太多 skill
