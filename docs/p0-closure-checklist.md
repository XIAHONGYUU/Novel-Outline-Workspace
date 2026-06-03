# P0 Closure Checklist

最后更新：2026-06-03

这份清单用于回答一个问题：

`P0 到底什么时候算收口？`

重点不是“规则还能不能继续补”，而是主链路是否已经能在真实 workspace 中稳定闭环。

## 收口标准

### 1. 主链路可跑通

- [x] `ingest`
- [x] `check-consistency`
- [x] `plan-merge`
- [x] `apply-merge`
- [x] `validate`
- [x] `refresh status / render views`

判定标准：

- 至少有一个独立案例工作区能完整跑通
- `apply` 后 `state / timeline / outline / views` 同步更新
- `validate` 返回 `ok=true`

### 2. 工作区状态可解释

- [x] `state/workspace-status.json` 的计数正确
- [x] `recommended_next_step` 与实际状态一致
- [x] pipeline `auto` 推荐动作与工作区现状一致

### 3. merge / apply 可执行

- [x] `plan_idea_merge` 输出的 direct inputs 能被实际消费
- [x] CLI 层能承接主流程需要的关键参数
- [x] 不需要靠手改 JSON 才能完成一次正常 apply

### 4. 样例工作区可继续推进

- [x] `demo-workspace/` 保持清晰 pending path
- [x] `first-workflow-case/` 能证明完整 workflow 至少走通过一轮
- [x] 样例工作区说明文档与真实状态一致

### 5. 规则边界进入“够用”状态

- [x] 当前高频误判不会阻断主链路
- [ ] 边缘句式已知限制可以列出来
- [x] 新规则补丁由真实 workspace 卡点驱动，而不是继续无边界扩张

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

## 中期判断

`P0` 还没有完全收口，但已经从“规则层持续加厚”进入“工作区级验收与 apply 可执行性修补”阶段。

## 第三轮验收记录

### 验收对象

- 临时测试工作区
- 路径：`repair-intake -> check-consistency -> plan-merge -> apply-merge`

### 实际执行链路

1. `python3 scripts/ingest_idea.py ...`
2. `python3 scripts/check_idea_consistency.py ...`
3. `python3 scripts/plan_idea_merge.py ...`
4. `python3 scripts/update_intake_draft.py --chapter-hint 6 --clear-open-questions ...`
5. `python3 scripts/check_idea_consistency.py ...`
6. `python3 scripts/plan_idea_merge.py ...`
7. `python3 scripts/apply_idea_merge.py --merge-input-id ...`

### 结果

- [x] `repair-intake` 现在已有确定性的脚本入口
- [x] intake draft 更新后，旧 consistency report / merge plan 会自动失效
- [x] 修补字段后，pipeline 可以自然回到 `plan-merge`
- [x] `outline-only` 的 direct apply 不再制造悬空 `event_id`
- [x] 这条闭环已有脚本级集成测试覆盖

### 这轮暴露出的真实问题

1. draft 更新不应继续复用旧 merge plan。  
   影响：如果旧 plan 不失效，pipeline 会一直盯着过期的 `missing_fields`。  
   处理：现在更新 intake draft 会显式失效旧 report / plan。

2. `create-event-and-scene` 在非 timeline domain 上不能再偷偷挂未创建的 event。  
   影响：scene 会引用不存在的 `event_id`，直接把 validator 打红。  
   处理：outline-only case 现在不会再自动写入悬空 `scene_event_ids`。

## 第四轮验收记录

### 验收对象

- `demo-workspace/`
- idea: `idea-20260511-006`

### 实际执行链路

1. `python3 scripts/update_intake_draft.py --workspace ./demo-workspace --idea-id idea-20260511-006 --chapter-hint 3 --clear-open-questions --json`
2. `python3 scripts/check_idea_consistency.py --workspace ./demo-workspace --idea-id idea-20260511-006 --json`
3. `python3 scripts/plan_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260511-006 --json`
4. `python3 scripts/apply_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260511-006 --merge-input-id timeline-merge-001 --resolution-note "..."`
5. `python3 scripts/refresh_workspace_status.py --workspace ./demo-workspace --json`
6. `python3 scripts/run_outline_workspace_pipeline.py --workspace ./demo-workspace --json`

### 结果

- [x] `idea-20260511-006` 已从 `pending` 变为 `applied`
- [x] `demo-workspace/` 当前 `pending=0 / applied=4 / rejected=4`
- [x] `outline/scene-index.json` 已新增第 3 章场景 `师徒关系裂缝`
- [x] validator 返回 `ok=true`
- [x] pipeline `auto` 当前建议动作已回到 `validate`

### 这轮暴露出的真实问题

1. 这类 `character` beat 当前最稳的 direct apply 形态，仍主要是 narrative scene 落地。  
   影响：系统现在能稳定把它落成正式剧情场景，但是否一定需要新增结构化 canon 记录，仍要靠人工判断。  
   当前处理：本轮明确选择“只落 outline scene，不强造 canon 结构记录”。  
   结论：这不是 blocker，但它说明 `character` 类 idea 的 canon 联动仍属于后续可继续做厚的方向。

## 第五轮验收记录

### 验收对象

- `demo-workspace/`
- idea: `idea-20260602-001`

### 实际执行链路

1. `python3 scripts/ingest_idea.py --workspace ./demo-workspace --title "林舟确认议会内部泄密" --kind reveal --content "..."`
2. `python3 scripts/check_idea_consistency.py --workspace ./demo-workspace --idea-id idea-20260602-001 --json`
3. `python3 scripts/plan_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260602-001 --json`
4. `python3 scripts/apply_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260602-001 --merge-input-id timeline-merge-001 --merge-input-id timeline-merge-know-001 --resolution-note "..."`
5. `python3 scripts/refresh_workspace_status.py --workspace ./demo-workspace --json`
6. `python3 scripts/run_outline_workspace_pipeline.py --workspace ./demo-workspace --json`

### 结果

- [x] `idea-20260602-001` 已从 `pending` 变为 `applied`
- [x] `demo-workspace/` 当前 `pending=0 / applied=5 / rejected=4`
- [x] `timeline/events.json` 已新增第 4 章事件 `林舟确认议会内部泄密`
- [x] `outline/scene-index.json` 已新增第 4 章场景 `林舟确认议会内部泄密`
- [x] `state/canon-index.json` 已新增 `林舟 -> 议会内部泄密` 的 knowledge-state
- [x] 同一条 idea 已在真实 workspace 里一次性消费两条 `merge_input_id`
- [x] validator 返回 `ok=true`
- [x] pipeline `auto` 当前建议动作仍为 `validate`

### 这轮暴露出的真实问题

1. `multi-input apply` 的真实缺口已经基本补齐。  
   影响：批量消费 `timeline / outline + canon knowledge-state` 不再只是临时测试能力，而已经有真实 workspace 验收。  
   结论：这条缺口可以从 `P0` 主阻塞项降级。

2. 当前剩余更真实的空白，开始转向 `relationship / character` 类 idea 的 canon 联动。  
   影响：`character` beat 目前在真实 workspace 里仍更稳定地落成 narrative scene，而不是结构化关系或角色状态。  
   结论：下一轮更值得做的是 relationship / character 样例，而不是继续补 reveal 类多输入 apply。

## 第五轮后判断

`P0` 主链路已经接近收口。当前剩下的不是“主链路能不能跑通”，而是边缘已知限制是否需要单独收口，以及 `relationship / character` 类真实样例是否还会暴露新的执行层缺口。

下一步最优先不是继续补句式规则，而是：

1. 找一条真实的 `relationship / character` 类 idea，验证它怎样稳定落成 canon 结构记录
2. 继续用真实 workspace 验收 `merge / apply / validate`
3. 把新的真实卡点再反推回脚本层，而不是先回到句式微调

## 第六轮验收记录

### 验收对象

- `demo-workspace/`
- idea: `idea-20260602-002`

### 实际执行链路

1. `python3 scripts/ingest_idea.py --workspace ./demo-workspace --title "林舟和师姐结盟" --kind relationship --content "..."`
2. `python3 scripts/check_idea_consistency.py --workspace ./demo-workspace --idea-id idea-20260602-002 --json`
3. `python3 scripts/plan_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260602-002 --json`
4. `python3 scripts/apply_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260602-002 --merge-input-id timeline-merge-001 --merge-input-id timeline-merge-rel-001 --resolution-note "..."`
5. `python3 scripts/refresh_workspace_status.py --workspace ./demo-workspace --json`
6. `python3 scripts/run_outline_workspace_pipeline.py --workspace ./demo-workspace --json`

### 结果

- [x] `idea-20260602-002` 已从 `pending` 变为 `applied`
- [x] `demo-workspace/` 当前 `pending=0 / applied=6 / rejected=4`
- [x] `outline/scene-index.json` 已新增第 5 章场景 `林舟和师姐结盟`
- [x] `state/canon-index.json` 已新增关系 `rel-char-protagonist-char-shijie-allied-ch5`
- [x] 同一条 idea 已在真实 workspace 里一次性消费 `scene + relationship` 两条 `merge_input_id`
- [x] validator 返回 `ok=true`
- [x] pipeline `auto` 当前建议动作仍为 `validate`

### 这轮暴露出的真实问题

1. `relationship` 类 idea 的首次落库已经有真实 workspace 验收。  
   影响：结构化关系写入不再只是测试能力，而已经被真实样例验证。  
   结论：这条缺口可以从“P0 关键待证项”降级。

2. 当前剩余更真实的空白，已经转向“既有关系记录怎样继续变化”。  
   影响：系统已能创建第一条关系记录，但还需要继续验证 `update-existing-relationship` 在真实 workspace 里的复用、状态转移与冲突收敛。  
   结论：下一轮更值得做的是“已有关系后续变化”样例，而不是继续做首次结盟类样例。

## 当前判断

`P0` 主链路现在已经基本跑通到关系层。接下来更重要的不是证明“关系能不能第一次写入”，而是验证后续关系演化是否也能在真实 workspace 中保持稳定。

下一步最优先不是继续补句式规则，而是：

1. 找一条已有关系继续变化的真实 idea，验证 `update-existing-relationship`
2. 继续用真实 workspace 验收 `merge / apply / validate`
3. 把新暴露出的关系复用问题再反推回脚本层

## 第七轮验收记录

### 验收对象

- `demo-workspace/`
- idea: `idea-20260602-003`

### 实际执行链路

1. `python3 scripts/ingest_idea.py --workspace ./demo-workspace --title "林舟和师姐再次结盟" --kind relationship --content "..."`
2. `python3 scripts/check_idea_consistency.py --workspace ./demo-workspace --idea-id idea-20260602-003 --json`
3. `python3 scripts/plan_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260602-003 --json`

### 结果

- [x] `idea-20260602-003` 已被收敛成真实的 `relationship-history-conflict`
- [x] `workspace-status.json` 当前会明确提示先处理这条关系 consistency 冲突
- [x] planner 已修正：同一条 `update-existing-relationship` 输入不再重复出现
- [x] `canon` action 已重新稳定绑定 `timeline-merge-rel-001`
- [ ] 这条 idea 暂未直接 apply

### 这轮暴露出的真实问题

1. planner 的 relationship reuse 去重与 action 绑定曾存在缺口。  
   影响：同一条关系复用输入会重复出现在 plan 中，`canon` action 还会丢失 `merge_input_id`。  
   当前处理：本轮已修掉 planner 去重与 action 绑定问题，并补了回归测试。

2. `same-state` 重复关系 beat 的落库语义仍未收口。  
   影响：当前 `update-existing-relationship` 虽然已经可以作为 gate-resolving input 暴露出来，但如果直接 apply，会把第 5 章既有关系记录整体改写到第 6 章，语义上还不够稳。  
   结论：下一步更值得先定义这类 case 的落库策略，而不是贸然 apply 当前默认行为。

## 当前判断

`P0` 主链路在 relation 首次落库层面已经站稳，但在“同一状态的重复关系 beat”这一层还没有真正收口。当前更重要的是把这个语义边界定清楚，而不是继续堆更多样例。

下一步最优先不是继续补句式规则，而是：

1. 定义 same-state relationship repeat beat 的落库策略
2. 再让 `demo-workspace/idea-20260602-003` 继续走完闭环
3. 把最终策略再反推回 planner / apply / validator

## 第八轮验收记录

### 验收对象

- `demo-workspace/`
- idea: `idea-20260602-003`

### 实际执行链路

1. `python3 scripts/check_idea_consistency.py --workspace ./demo-workspace --idea-id idea-20260602-003 --json`
2. `python3 scripts/plan_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260602-003 --json`
3. `python3 scripts/apply_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260602-003 --merge-input-id timeline-merge-rel-repeat-001 --resolution-note "..."`
4. `python3 scripts/check_idea_consistency.py --workspace ./demo-workspace --idea-id idea-20260602-003 --json`
5. `python3 scripts/refresh_workspace_status.py --workspace ./demo-workspace --json`
6. `python3 scripts/run_outline_workspace_pipeline.py --workspace ./demo-workspace --action auto --json`

### 结果

- [x] `idea-20260602-003` 已从 `pending` 变为 `applied`
- [x] planner 已默认把 same-state repeat beat 收敛成 `scene-only` 的 gate-resolving input
- [x] `state/canon-index.json` 仍保留第 5 章关系 `rel-char-protagonist-char-shijie-allied-ch5`
- [x] `outline/scene-index.json` 已新增第 6 章场景 `林舟和师姐再次结盟`
- [x] apply 后重新运行 consistency，`relationship-history-conflict` 已清空
- [x] `demo-workspace/` 当前 `pending=0 / applied=7 / rejected=4`
- [x] pipeline `auto` 当前建议动作已回到 `validate`
- [x] validator 返回 `ok=true`

### 这轮暴露出的真实问题

1. same-state repeat beat 已经不再是 `P0` blocker。  
   影响：系统现在已经能稳定区分“首次关系节点”与“后续重复叙事 beat”，不会再用后者覆写前者。  
   结论：这一层缺口可以从 `P0` 主阻塞项降级。

2. 当前更真实的空白继续前移到了“真实状态转移”的落库策略。  
   影响：如果后续是从 `allied -> ruptured`、`ruptured -> reconciled` 这类状态真正变化，系统还需要决定是复用旧节点、追加新节点，还是联动 scene + canon。  
   结论：下一轮应优先找一条已有关系状态真正变化的真实样例。

## 当前判断

`P0` 主链路到 relationship repeat beat 这一层已经收口。接下来更重要的不是继续证明“重复关系 beat 能否处理”，而是验证“关系状态真正变化时，canon history 节点该如何追加”。

下一步最优先不是继续补句式规则，而是：

1. 找一条已有关系状态真正变化的真实 idea
2. 继续用真实 workspace 验收 `merge / apply / validate`
3. 把新的 relationship history 缺口再反推回 planner / apply / validator

## 第九轮验收记录

### 验收对象

- `demo-workspace/`
- idea: `idea-20260602-004`

### 实际执行链路

1. `python3 scripts/ingest_idea.py --workspace ./demo-workspace --title "林舟和师姐决裂" --kind relationship --content "..."`
2. `python3 scripts/check_idea_consistency.py --workspace ./demo-workspace --idea-id idea-20260602-004 --json`
3. `python3 scripts/plan_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260602-004 --json`
4. `python3 scripts/apply_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260602-004 --merge-input-id timeline-merge-001 --merge-input-id timeline-merge-rel-001 --resolution-note "..."`
5. `python3 scripts/check_idea_consistency.py --workspace ./demo-workspace --idea-id idea-20260602-004 --json`
6. `python3 scripts/refresh_workspace_status.py --workspace ./demo-workspace --json`
7. `python3 scripts/run_outline_workspace_pipeline.py --workspace ./demo-workspace --action auto --json`

### 结果

- [x] `idea-20260602-004` 已从 `pending` 变为 `applied`
- [x] planner 已默认把真实 state transition 收敛成 `scene + new canon relationship` 两条 ready input
- [x] `state/canon-index.json` 当前已同时保留 `rel-char-protagonist-char-shijie-allied-ch5` 与 `rel-char-protagonist-char-shijie-ruptured-ch7`
- [x] `outline/scene-index.json` 已新增第 7 章场景 `林舟和师姐决裂`
- [x] apply 后重新运行 consistency，当前无 conflict
- [x] `demo-workspace/` 当前 `pending=0 / applied=8 / rejected=4`
- [x] pipeline `auto` 当前建议动作已回到 `validate`
- [x] validator 返回 `ok=true`

### 这轮暴露出的真实问题

1. relationship state transition 已经不再是 `P0` blocker。  
   影响：系统现在已经能稳定区分“重复旧状态的叙事 beat”和“关系状态真的变化”，并把后者落成新的 `canon relationship` 节点。  
   结论：这一层缺口可以从 `P0` 主阻塞项降级。

2. 当前更真实的空白继续前移到了“多段关系链之后的复归”。  
   影响：系统已经能表达 `allied@5 -> ruptured@7`，但还需要验证未来 `reconciled@9`、`allied-again` 这类后续恢复或再变化，在真实 workspace 里如何继续落库。  
   结论：下一轮应优先找一条关系先决裂、后和解/再结盟的真实样例。

## 当前判断

`P0` 主链路到 relationship state transition 这一层已经收口。接下来更重要的不是继续证明“首次关系节点”或“单次状态转移”能否处理，而是验证多段 relationship history chain 在真实 workspace 里是否仍然稳定。

下一步最优先不是继续补句式规则，而是：

1. 找一条关系先决裂、后和解/再结盟的真实 idea
2. 继续用真实 workspace 验收 `merge / apply / validate`
3. 把多段 relationship history chain 的新缺口再反推回 planner / apply / validator

## 第十轮验收记录

### 验收对象

- `demo-workspace/`
- idea: `idea-20260603-001`

### 实际执行链路

1. `python3 scripts/ingest_idea.py --workspace ./demo-workspace --title "林舟和师姐和解" --kind relationship --content "..."`
2. `python3 scripts/check_idea_consistency.py --workspace ./demo-workspace --idea-id idea-20260603-001 --json`
3. `python3 scripts/plan_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260603-001 --json`
4. `python3 scripts/apply_idea_merge.py --workspace ./demo-workspace --idea-id idea-20260603-001 --merge-input-id timeline-merge-001 --merge-input-id timeline-merge-rel-001 --resolution-note "..."`
5. `python3 scripts/refresh_workspace_status.py --workspace ./demo-workspace --json`
6. `python3 scripts/run_outline_workspace_pipeline.py --workspace ./demo-workspace --action auto --json`

### 结果

- [x] `idea-20260603-001` 已从 `pending` 变为 `applied`
- [x] planner 已默认把 relationship reconciliation 收敛成 `scene + new canon relationship` 两条 ready input
- [x] `state/canon-index.json` 当前已形成 `rel-char-protagonist-char-shijie-allied-ch5 -> rel-char-protagonist-char-shijie-ruptured-ch7 -> rel-char-protagonist-char-shijie-reconciled-ch9`
- [x] `outline/scene-index.json` 已新增第 9 章场景 `林舟和师姐和解`
- [x] `demo-workspace/` 当前 `pending=0 / applied=9 / rejected=4`
- [x] pipeline `auto` 当前建议动作已回到 `validate`
- [x] validator 返回 `ok=true`

### 这轮暴露出的真实问题

1. relationship reconciliation 已经不再是 `P0` blocker。  
   影响：系统现在已经能稳定把多段关系链扩展到 `reconciled`，而不会抹掉中间的 `ruptured` 节点。  
   结论：这一层缺口可以从 `P0` 主阻塞项降级。

2. 当前更真实的空白继续前移到了“reconciled 之后的 repeat beat / 再变化”。  
   影响：系统已经能表达 `allied@5 -> ruptured@7 -> reconciled@9`，但还需要验证未来的 `再次结盟 / 再次和解` 是否仍应只落 scene，或是否需要与既有 `reconciled` 节点发生更细的联动。  
   结论：下一轮应优先找一条已有 `reconciled` 节点后的 repeat beat 样例。

## 当前判断

`P0` 主链路到多段 relationship history chain 这一层已经接近收口。接下来更重要的不是继续证明“和解能不能落库”，而是验证已有 `reconciled` 节点之后的 repeat beat / 再变化在真实 workspace 里是否仍然稳定。

下一步最优先不是继续补句式规则，而是：

1. 找一条已有 `reconciled` 节点后的 repeat beat / 再结盟样例
2. 继续用真实 workspace 验收 `merge / apply / validate`
3. 把新的 relationship history chain 缺口再反推回 planner / apply / validator
