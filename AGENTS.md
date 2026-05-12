# AGENTS

这个文件给 AI 编程工具使用，说明这个仓库的固定协作规则。

## 目标

本仓库用于构建“小说大纲工作区”系统。

重点不是一次性生成小说大纲，而是维护一个可持续演化的 workspace，包括：

- `canon`
- `outline`
- `timeline`
- `state`
- `inbox`
- `views`

## 先读什么

开始工作前，优先读取：

1. `README.md`
2. `WORKFLOW.md`
3. `PROJECT_STATUS.md`
4. `NEXT_ACTIONS.md`
5. `DECISIONS.md`
6. `docs/repository-map.md`
7. `docs/data-model.md`

## 事实源规则

- `state/*.json`、`timeline/events.json`、`outline/scene-index.json` 是机器事实源。
- Markdown 主要用于人工输入、说明和正式文本承载。
- `views/*.html` 是生成产物，不应作为反向编辑入口。

## 工作原则

1. 优先维护工作区闭环，而不是新增零散功能。
2. 优先补强 `intake -> validate -> merge -> render` 主链路。
3. 能做成脚本或测试的能力，不要先做成模糊 agent 行为。
4. 不要绕开现有数据模型随意写新结构。
5. 新增字段时同步更新文档和测试。

## 修改规则

如果修改了以下内容，必须同步检查相关文件：

- 修改数据结构：更新 `docs/data-model.md`
- 修改目录结构：更新 `docs/repository-map.md`
- 修改阶段目标：更新 `PROJECT_STATUS.md` 和 `NEXT_ACTIONS.md`
- 修改关键方向：更新 `DECISIONS.md`
- 新增或调整 skill：更新 `docs/skill-catalog.md`

## 开发优先级

当前优先顺序：

1. `novel-consistency-check`
2. `novel-timeline-merge`
3. merge 影响面表达增强
4. intake 推断质量提升

当前默认工作流：

`ingest -> check-consistency -> plan-merge -> apply-merge -> validate`

不要优先投入：

- 高交互 UI
- 全自动长文重写
- 复杂可视化
- 过早拆太多 skill

## 测试要求

- 改动脚本或核心逻辑时，优先补或改 `tests/test_workspace.py`
- 至少覆盖主流程成功路径
- 新增推断规则时，补一个能说明预期行为的测试

推荐验证命令：

```bash
python3 -m unittest discover -s tests -v
```

## 文档维护要求

每次完成一个可感知的阶段推进时：

- 更新 `PROJECT_STATUS.md`
- 调整 `NEXT_ACTIONS.md`
- 如果涉及方向或边界变化，补记 `DECISIONS.md`

## 禁止事项

- 不要把生成 HTML 当作手工编辑源
- 不要跳过 `state` 层直接制造隐式状态
- 不要把多个职责完全不同的能力混成一个 skill
- 不要为了快而破坏 `canon / outline / timeline` 分层
