# P0 Closure Checklist

最后更新：2026-06-01

这份清单用于回答一个问题：

`P0 到底什么时候算收口？`

重点不是“规则还能不能继续补”，而是主链路是否已经能在真实 workspace 中稳定闭环。

## 收口标准

### 1. 主链路可跑通

- [ ] `ingest`
- [ ] `check-consistency`
- [ ] `plan-merge`
- [ ] `apply-merge`
- [ ] `validate`
- [ ] `refresh status / render views`

判定标准：

- 至少有一个独立案例工作区能完整跑通
- `apply` 后 `state / timeline / outline / views` 同步更新
- `validate` 返回 `ok=true`

### 2. 工作区状态可解释

- [ ] `state/workspace-status.json` 的计数正确
- [ ] `recommended_next_step` 与实际状态一致
- [ ] pipeline `auto` 推荐动作与工作区现状一致

### 3. merge / apply 可执行

- [ ] `plan_idea_merge` 输出的 direct inputs 能被实际消费
- [ ] CLI 层能承接主流程需要的关键参数
- [ ] 不需要靠手改 JSON 才能完成一次正常 apply

### 4. 样例工作区可继续推进

- [ ] `demo-workspace/` 保持清晰 pending path
- [ ] `first-workflow-case/` 能证明完整 workflow 至少走通过一轮
- [ ] 样例工作区说明文档与真实状态一致

### 5. 规则边界进入“够用”状态

- [ ] 当前高频误判不会阻断主链路
- [ ] 边缘句式已知限制可以列出来
- [ ] 新规则补丁由真实 workspace 卡点驱动，而不是继续无边界扩张

## 首轮验收记录

### 验收对象

- `first-workflow-case/`
- idea: `idea-20260522-001`

### 实际执行链路

1. `python3 scripts/check_idea_consistency.py --workspace ./first-workflow-case --idea-id idea-20260522-001 --json`
2. `python3 scripts/plan_idea_merge.py --workspace ./first-workflow-case --idea-id idea-20260522-001 --json`
3. `python3 scripts/apply_idea_merge.py ...`
4. `python3 scripts/refresh_workspace_status.py --workspace ./first-workflow-case --json`
5. `python3 scripts/run_outline_workspace_pipeline.py --workspace ./first-workflow-case --action auto --json`

### 结果

- [x] 主链路跑通
- [x] `idea-20260522-001` 已从 `pending` 变为 `applied`
- [x] `timeline/events.json` 已写入事件
- [x] `outline/scene-index.json` 已写入场景
- [x] `state/canon-index.json` 已写入 knowledge-state
- [x] `validate` 返回 `ok=true`
- [x] `workspace-status.json` 计数已更新为 `pending=0 / applied=1`
- [x] pipeline `auto` 当前建议动作为 `validate`

### 这轮暴露出的真实问题

1. `apply_idea_merge.py` 的 CLI 原先没有暴露 knowledge-state 参数。  
   影响：merge plan 虽然能产出 canon knowledge input，但命令行层无法一次性消费。  
   处理：本轮已补齐 CLI 参数，并新增脚本级回归测试。

2. intake / plan 的 location 推断仍会给出弱值，例如 `的白塔`。  
   影响：如果不做人类确认，正式 timeline 事实源会被写入低质量地点。  
   当前处理：本轮 apply 时人工确认为 `白塔档案室`。  
   结论：这属于仍需保留的 `P0` 已知限制，但不再默认优先于闭环验收。

3. 一个 idea 可能同时对应多个 direct merge inputs，但 CLI 默认没有“批量消费整组 plan inputs”的概念。  
   影响：如果直接逐条 apply，idea 元数据会被后一次 apply 覆盖，工作流表达不够顺。  
   当前处理：仓库现已支持重复传入 `--merge-input-id`，一次性消费整组 merge inputs。  
   结论：这个缺口已从 `P0` 主阻塞项降为“已补齐能力，待继续用真实 workspace 覆盖更多组合”。

## 第二轮验收记录

### 验收对象

- `demo-workspace/`
- idea: `idea-20260511-006`

### 实际执行链路

1. `python3 scripts/refresh_workspace_status.py --workspace ./demo-workspace --json`
2. `python3 scripts/check_idea_consistency.py --workspace ./demo-workspace --idea-id idea-20260511-006 --json`
3. `python3 scripts/plan_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260511-006 --json`
4. `python3 scripts/run_outline_workspace_pipeline.py --workspace ./demo-workspace --json`

### 结果

- [x] `demo-workspace/` 仍保持清晰的 pending path
- [x] consistency report 已明确指出这是 `warning-only` case，而不是硬冲突
- [x] merge plan 已明确指出当前缺的是 `chapter_number`
- [x] `workspace-status.json` 和 pipeline `auto` 现在都会直接提示先补 intake 信息，而不再泛化成“继续处理 pending ideas”
- [ ] 这条 idea 仍不能 direct apply

### 这轮暴露出的真实问题

1. `warning-only` 并不等于“已经 ready for apply”。  
   影响：如果只看旧版 `recommended_next_step` 或 pipeline `auto`，会误以为当前应该继续跑 `plan-merge`。  
   处理：本轮已把这类 case 上提成显式 `repair-intake` 路径，并把推荐语收紧到缺失字段层。

2. intake 信息不足仍是当前工作区真实阻塞点。  
   影响：`师徒关系裂缝` 这条 idea 缺 `chapter_number`，因此即使 consistency clean，也不能落成 timeline / outline 的 direct write。  
   当前处理：系统现在会明确要求先补章节 / 时间节点。  
   结论：这属于 `P0` 仍需保留的真实人工确认点，但已经不再是“系统不知道下一步是什么”。

## 当前判断

`P0` 还没有完全收口，但已经从“规则层持续加厚”进入“工作区级验收与 apply 可执行性修补”阶段。

下一步最优先不是继续补句式规则，而是：

1. 补一条工作区级集成测试，覆盖“pending idea 进入 repair-intake 分支”的成功路径
2. 用真实 workspace 继续覆盖“多 merge inputs 一次性 apply”的更多组合
3. 把真实闭环里暴露出的缺口，反推回 `merge / apply / validate`
