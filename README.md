# Novel Outline Workspace

一个面向原创小说策划的大纲工作区系统。

目标不是一次性“生成一份大纲”，而是把小说的 `canon / outline / timeline / idea inbox / html views`
放进一个可持续维护、可校验、可回滚的 Git 工作区里。

## 设计目标

- 随手记下新想法，不要求一开始就写成正式大纲
- 把新想法先放进 `inbox`，再并入正式设定和大纲
- 让 `canon`、`outline`、`timeline` 成为清晰的事实来源
- 用结构化数据做第一批硬校验，减少明显冲突
- 用 `HTML` 作为主要生成产物，承载时间线、关系和状态展示
- 每次处理完都能写回状态、报告和下一步建议

## 这一版先做什么

当前仓库先提供第一版蓝图：

- 工作区模板
- 核心数据模型
- 想法录入脚本
- 状态刷新脚本
- 第一批硬冲突校验脚本
- 基础 HTML 视图渲染
- 半自动 merge 计划与应用脚本
- orchestrator skill 与 pipeline 入口

这还不是“自动把所有想法无损融合进全文”的终版代理。
它是一个可靠的基础层。

## 当前状态

到 `2026-05-23` 为止，主链路已经推进到：

`ingest -> check-consistency -> plan-merge -> apply-merge -> validate`

当前已具备：

- `novel-idea-intake`
  能生成 intake draft 和 HTML 预览
- `novel-consistency-check`
  能生成 idea-level consistency report，并已接入 pipeline
- gate-aware merge
  `plan_idea_merge` 和 `apply_idea_merge` 都会显式读取 consistency gate
- timeline merge input layer
  `plan_idea_merge` 已开始输出结构化 `timeline_merge_inputs`，`apply_idea_merge` 可直接按 `merge_input_id` 消费
- domain-specific plan explainers
  `plan_idea_merge` 的 `proposed_actions` 已开始输出更接近执行层的 domain explainers，而不只是泛化的 domain 提示
- canon relationship layer
  `state/canon-index.json` 已开始承载结构化 `relationships`，关系类 merge input 可直接写入
- canon knowledge / exception layer
  `state/canon-index.json` 已开始承载 `knowledge_states` 与 `world_rule_exceptions`；
  `knowledge-state` merge input 可直接写入并反向参与 consistency，
  `world-rule exception` 记录也会进入正式机器事实源
- world-rule resolution layer
  `plan_idea_merge` 已可为 `world-rule conflict` 生成多策略输入：
  延后事件、对齐 cutoff、记录规则例外说明
- multi-claim / multi-rule world-rule binding
  `check_idea_consistency` 已开始在 `world-rule conflict` 中写回命中的 claim，
  `plan_idea_merge` 可按各自命中的 claim 为不同 rule 生成独立 exception 输入
- grouped world-rule explainers
  当一条 idea 同时命中多条 world-rule 时，
  `plan_idea_merge` 会先给出 constraints 级摘要，再展开每条 rule 的具体处理输入；
  摘要中会直接列出每条 rule 的策略、目标文件、direct/override 信息，以及按 direct / review 拆开的跨 domain impacts，
  并开始区分哪些 rule 仍在同一主体链上、哪些 exception 需要按 `split-subjects` 分开解释，
  同一主体下若标题和正文同时抽到泛化 object 与更具体 object，claim 层会优先收敛到更具体那条，
  多主体句子里如果前后主体对应不同 object，claim 层也会优先按主体窗口拆开，避免把后一个主体的 object 串回前一个主体，
  `identity / leak / same-camp / separate-camp` family 里更短概括表达与更长具体表达并存时，claim 层也开始优先保留更具体那条，
  同一 family 内如果只是“标准表达 / 口语表达”差异，也会优先保留更标准的 wording，
  而 cross-family 的 claim 目前仍会保持分离，避免把不同事实误合并，
  `world-rule` 在缺少 `knowledge_claims` 时也开始按主体局部窗口抽取 knowledge signal，
  因此同章 exception 的同义 object 不再只靠全句字面串命中，mixed-subject 句子里别人的 object 也不会再误算到当前 rule subject 身上，
  对已落地的 exception，constraints explainer 现在也开始区分哪些可 `direct` 沿用、哪些仍需 `review`，
  并把“仍有冲突的 rule”和“已有豁免的 rule”收敛进同一组 grouped summary，
  `exception_scope` 本身也开始细分成 `chapter scope / subject scope / match mode` 三层稳定 token，
  canon 侧 exception explainer 也会对齐到各自命中的 claim，
  重复的 timeline / outline 说明会优先收敛成一条更高可执行性的版本
- graph-aware consistency exemptions
  `knowledge-state` 已开始豁免后文复述型知情记录，
  如果同章已经有正式 event / scene / canon 知情记录，也不会再被更晚重复记录误报成前移；
  `relationship-history` 已开始豁免有显式状态转移后的未来重复状态，
  如果同章已经有正式关系 beat，也不会再被未来同状态记录误报成漂移；
  对 `world-rule`，consistency report 现在也开始显式写出已命中的正式 exemption，而不再只静默放行

仓库内当前也附带两个可直接查看的样本工作区：

- `demo-workspace/`
  作为持续演化的综合示例
- `first-workflow-case/`
  作为第一个独立 workflow 案例，当前停在 `clear consistency gate + ready merge plan`

下一步重点不再是补“有没有入口”，而是增强：

- `novel-timeline-merge`
- 更细的 timeline-order / knowledge-state 规则
- 更细的 relationship / world-rule exception 边界
- 继续扩到更多 object family 的 claim 收敛
- grouped summary 与逐条 explainer 的进一步压缩
- repair / merge explainers 的进一步收敛

## 核心结构

```text
repo/
├── docs/
├── scripts/
├── src/novel_outline_workspace/
└── workspace-template/
```

未来每一本小说会是一个独立 workspace，推荐结构如下：

```text
your-novel/
├── canon/
├── constraints/
├── inbox/
├── outline/
├── reports/
├── state/
├── timeline/
└── views/
```

## 使用方式

初始化一个小说工作区：

```bash
python3 scripts/init_workspace.py \
  --workspace ./demo-workspace \
  --novel-name "你的小说" \
  --protagonist-name "主角名"
```

刷新工作区状态：

```bash
python3 scripts/refresh_workspace_status.py --workspace ./demo-workspace --json
```

录入一条新想法：

```bash
python3 scripts/ingest_idea.py \
  --workspace ./demo-workspace \
  --title "女主其实更早知道真相" \
  --kind reveal \
  --content "第一卷末尾她已经知道组织首领身份，只是假装不知道。"
```

运行第一批校验：

```bash
python3 scripts/validate_workspace.py --workspace ./demo-workspace --json
```

对单条 idea 运行 consistency check：

```bash
python3 scripts/check_idea_consistency.py \
  --workspace ./demo-workspace \
  --idea-id idea-20260511-001 \
  --json
```

为 legacy idea 补回或修复 intake draft：

```bash
python3 scripts/backfill_intake_drafts.py \
  --workspace ./demo-workspace \
  --all-pending \
  --json
```

重建 HTML 展示页：

```bash
python3 scripts/render_workspace_views.py --workspace ./demo-workspace
```

为一条 idea 生成 merge plan：

```bash
python3 scripts/plan_idea_merge.py \
  --workspace ./demo-workspace \
  --idea-id idea-20260511-001 \
  --json
```

如果 plan 里已经有可直接执行的 `timeline_merge_inputs`，可以按输入 id 应用：

```bash
python3 scripts/apply_idea_merge.py \
  --workspace ./demo-workspace \
  --idea-id idea-20260511-001 \
  --merge-input-id timeline-merge-001 \
  --resolution-note "按 merge input 并入第七章揭露节点。"
```

对于 `world-rule conflict`，plan 现在可能生成多种结构化输入。

对齐 cutoff：

```bash
python3 scripts/apply_idea_merge.py \
  --workspace ./demo-workspace \
  --idea-id idea-20260511-001 \
  --merge-input-id timeline-merge-rule-cutoff-002 \
  --resolution-note "把揭露事件与硬约束截止点对齐。"
```

延后事件到 cutoff 之后：

```bash
python3 scripts/apply_idea_merge.py \
  --workspace ./demo-workspace \
  --idea-id idea-20260511-001 \
  --merge-input-id timeline-merge-rule-delay-001 \
  --resolution-note "把揭露事件延后到硬约束之后。"
```

只记录规则例外说明：

```bash
python3 scripts/apply_idea_merge.py \
  --workspace ./demo-workspace \
  --idea-id idea-20260511-001 \
  --merge-input-id timeline-merge-rule-note-003 \
  --resolution-note "先把这条例外写入 constraints 说明。" \
  --override-consistency-gate
```

应用一条结构化 merge：

```bash
python3 scripts/apply_idea_merge.py \
  --workspace ./demo-workspace \
  --idea-id idea-20260511-001 \
  --resolution-note "把揭露点前移到第七章，并同步更新时间线与场景。"
```

默认情况下，`apply_idea_merge.py` 会要求这条 idea 先通过或至少完成最新的 `consistency check`。
如果你已经人工确认要强行并入，可以显式加：

```bash
python3 scripts/apply_idea_merge.py \
  --workspace ./demo-workspace \
  --idea-id idea-20260511-001 \
  --resolution-note "人工确认后仍决定并入。" \
  --override-consistency-gate
```

让 orchestrator 判断下一步：

```bash
python3 scripts/run_outline_workspace_pipeline.py --workspace ./demo-workspace --json
```

直接执行 orchestrator 推荐动作：

```bash
python3 scripts/run_outline_workspace_pipeline.py \
  --workspace ./demo-workspace \
  --execute \
  --json
```

## 当前原则

- JSON 是机器真相源
- Markdown 主要保留给人工输入和源码说明
- HTML 是主要生成产物和展示层
- `inbox` 允许混乱，`canon / outline / timeline` 不允许混乱
- 先做硬校验，再逐步加语义级 merge
- 推荐主流程：`ingest -> check-consistency -> plan-merge -> apply-merge -> validate`

## 文档

- [WORKFLOW.md](/home/zuoky/project2/WORKFLOW.md:1)
- [PROJECT_STATUS.md](/home/zuoky/project2/PROJECT_STATUS.md:1)
- [NEXT_ACTIONS.md](/home/zuoky/project2/NEXT_ACTIONS.md:1)
- [DECISIONS.md](/home/zuoky/project2/DECISIONS.md:1)
- [AGENTS.md](/home/zuoky/project2/AGENTS.md:1)
- [docs/repository-map.md](/home/zuoky/project2/docs/repository-map.md:1)
- [docs/data-model.md](/home/zuoky/project2/docs/data-model.md:1)
- [docs/validator-rules.md](/home/zuoky/project2/docs/validator-rules.md:1)
- [docs/skill-catalog.md](/home/zuoky/project2/docs/skill-catalog.md:1)
- [novel-idea-intake-skill/SKILL.md](/home/zuoky/project2/novel-idea-intake-skill/SKILL.md:1)
- [novel-consistency-check-skill/SKILL.md](/home/zuoky/project2/novel-consistency-check-skill/SKILL.md:1)
- [novel-outline-orchestrator-skill/SKILL.md](/home/zuoky/project2/novel-outline-orchestrator-skill/SKILL.md:1)
