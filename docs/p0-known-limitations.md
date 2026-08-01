# P0 Known Limitations

最后更新：2026-08-01

这份文档回答的是：

`哪些限制在 P0 阶段可以正式接受，而不再继续当作当前主阻塞项？`

原则：

- 只记录已经被真实 workspace 验证过、且当前不会阻断主链路闭环的限制
- 不把“以后也许想做得更好”的方向混进来
- 如果某条限制开始反复阻断真实 workspace，就应从这里移除，重新回到主优先级

## 一、已接受的 review-only 路径

### 1. `prior-exception + mixed-subjects + local-signal`

当前策略：

- 默认停在 `review-constraints`
- 当前正式策略 token：
  - `mixed-subjects-local-signal-review-only`

当前为什么可接受：

- 这条路径已经有真实 workspace 样例：`demo-workspace/idea-20260605-003`
- `check-consistency -> plan-merge -> review-constraints` 已稳定闭环
- `review_constraints.py` 已能输出正式结构化报告，说明：
  - 为什么停在 review
  - 哪些 merge inputs 仍然 ready
  - 复核时应看什么

当前不做什么：

- 不自动扩写既有 `world_rule_exception` 的主体范围
- 不自动为额外主体补新的 `canon knowledge-state`

## 二、已接受的人工确认点

### 2. intake 仍可能缺少关键结构字段

典型表现：

- 缺 `chapter_number`
- 缺 `reading_chapter`
- 缺 `participant_ids`

当前为什么可接受：

- 这类 case 已被显式收敛到 `repair-intake`
- 系统现在已经知道“下一步该补什么”，不再是流程迷路

### 3. 地点推断仍可能给出弱值

典型表现：

- `的白塔`
- 过于泛化或不够正式的地点表达

当前为什么可接受：

- 这类问题目前属于质量问题，不是流程问题
- 真实 workspace 已证明：人工确认后，主链路仍可自然继续

当前默认处理：

- 允许人工在 apply 前确认 location
- 不把这类质量波动视为当前阶段 blocker

## 三、已接受的结构表达边界

### 4. 部分 `character` beat 仍主要落成 narrative scene

当前表现：

- 某些 `character` 类 idea 更稳的 direct apply 形态仍是 `outline scene`
- 不强行制造新的结构化 canon 记录

当前为什么可接受：

- 真实 workspace 已证明这种落法能稳定闭环
- 这属于“canon 联动可以更厚”，不是“主链路现在不能用”

### 5. review-only path 仍保留人工确认点

当前已有：

- `review-constraints -> resolve-constraints-review -> apply-merge`
- `review-reuse -> resolve-reuse-review -> apply-merge`
- `approved-ready-merge-inputs / rejected` 两种正式 decision
- 按 `merge_plan_fingerprint` 校验 freshness
- apply / reject 后的 archive 语义
- archived report 中保留 `remaining_review_merge_inputs`

当前仍不自动做什么：

- 不绕过人工确认直接消费带 `review_tokens / missing_fields / apply_arg_conflicts / apply_arg_review_holds` 的输入
- 不把未批准的 reuse 歧义或 constraints 剩余项静默并入
- 不把 archived review 重新伪装成 live pending review

当前为什么可接受：

- `P0` 已收口；constraints / reuse 两条 review-only 主路径都已经有确定性写回与真实 workspace 验收样例
- 当前剩余问题是 P1 表达与执行层厚化，不是 P0 主链路 blocker
- 保留人工确认点可以避免把复用歧义、主体范围歧义或缺字段输入误当作直接可执行输入

## 四、哪些还不算已接受限制

以下情况如果出现，仍应重新上提优先级，而不是留在本清单：

- `review-constraints` 反复出现，但系统说不清为什么 review
- `review-reuse` 反复出现，但 archived report 说不清剩余项是 `reuse-ambiguity`、`missing-fields` 还是其他原因
- ready merge inputs 被错误地打回 `repair-intake`
- 同一类 world-rule case 在真实 workspace 中反复出现不一致策略
- 已知限制开始直接阻断 `ingest -> check-consistency -> plan-merge -> apply-merge -> validate`

## 当前结论

到当前阶段，`P0` 已经可以正式接受这些限制：

- `mixed-subjects-local-signal-review-only` 这类 review-only path
- `repair-intake` 仍需人工补关键字段
- location 推断仍可能出现弱值
- 部分 `character` beat 先只落 scene
- review-only path 仍保留人工确认点，但 constraints / reuse writeback 已落地

这意味着下一步默认不该继续围绕这些点横向补细节，而应把注意力放在：

- 是否还有新的真实 blocker 会把这些限制重新升级
- 如果没有，`P1` 应优先继续厚化 `timeline merge` 执行层，并维护 archived / reuse 剩余项表达
