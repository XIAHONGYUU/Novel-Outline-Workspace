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

到 `2026-05-13` 为止，主链路已经推进到：

`ingest -> check-consistency -> plan-merge -> apply-merge -> validate`

当前已具备：

- `novel-idea-intake`
  能生成 intake draft 和 HTML 预览
- `novel-consistency-check`
  能生成 idea-level consistency report，并已接入 pipeline
- gate-aware merge
  `plan_idea_merge` 和 `apply_idea_merge` 都会显式读取 consistency gate

下一步重点不再是补“有没有入口”，而是增强：

- `knowledge-state` 检查
- `novel-timeline-merge`
- timeline / outline / canon 的联动质量

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
