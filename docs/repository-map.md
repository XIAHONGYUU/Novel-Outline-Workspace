# Repository Map

## 顶层结构

```text
.
├── README.md
├── WORKFLOW.md
├── docs/
├── novel-outline-orchestrator-skill/
├── scripts/
├── src/novel_outline_workspace/
└── workspace-template/
```

## 目录说明

### `docs/`

项目设计说明：

- 仓库结构
- 数据模型
- 校验规则

### `scripts/`

可直接运行的命令行入口：

- `init_workspace.py`
- `refresh_workspace_status.py`
- `ingest_idea.py`
- `validate_workspace.py`
- `plan_idea_merge.py`
- `apply_idea_merge.py`
- `run_outline_workspace_pipeline.py`

### `src/novel_outline_workspace/`

共享 Python 逻辑：

- 工作区初始化
- JSON 读写
- 状态汇总
- idea log 更新
- merge planning
- merge application
- orchestration routing
- 校验逻辑
- Markdown 报告输出

### `novel-outline-orchestrator-skill/`

本地 skill 包装层：

- 给 Codex 一个统一入口
- 约束默认流程
- 引导使用 merge / validate / render 命令

### `workspace-template/`

未来每本小说的新工作区模板。

## 模板工作区

```text
workspace-template/
├── README.md
├── canon/
│   ├── characters.md
│   ├── story-premise.md
│   └── world-rules.md
├── constraints/
│   ├── constraints.json
│   └── README.md
├── inbox/
│   └── README.md
├── outline/
│   ├── arc-map.md
│   ├── master-outline.md
│   └── scene-index.json
├── reports/
│   └── README.md
├── state/
│   ├── canon-index.json
│   ├── consistency-checks/
│   ├── idea-log.json
│   ├── intake-drafts/
│   ├── merge-plans/
│   └── workspace-status.json
├── timeline/
│   └── events.json
└── views/
    ├── README.md
    ├── consistency-checks/
    ├── intake-drafts/
    └── merge-plans/
```
