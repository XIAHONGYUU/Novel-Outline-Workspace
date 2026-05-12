# Project Status

最后更新：2026-05-13

## 项目定位

这个仓库在构建一个“小说大纲工作区”系统。

目标不是一次性生成大纲，而是把：

- `canon`
- `outline`
- `timeline`
- `inbox`
- `views`

放进一个可持续维护、可校验、可回滚的工作区流程里。

## 当前阶段

当前处于 `P0 基础工作流搭建期`。

已经完成的方向：

- 工作区模板与初始化
- idea inbox 录入
- workspace 状态刷新
- 基础校验
- 基础 HTML 视图渲染
- merge plan / apply merge 基础流
- orchestrator 入口
- idea intake 第二层草案推断
- idea-level consistency check 可用版
- gate-aware merge

## 已完成能力

### 1. 工作区骨架

- `scripts/init_workspace.py`
- `workspace-template/`
- `src/novel_outline_workspace/workspace.py`

### 2. idea 录入主流程

- `scripts/ingest_idea.py`
- 写入 `state/idea-log.json`
- 写入 `inbox/*.md`

### 3. idea intake 推断

已支持自动推断：

- `kind`
- `tags`
- `target_files`
- `suggested_domains`
- `chapter_hints`
- `location_candidates`
- `character_mentions`

并自动生成：

- `state/intake-drafts/<idea-id>.json`
- `views/intake-drafts/<idea-id>.html`

### 4. 基础校验与渲染

- `scripts/validate_workspace.py`
- `scripts/check_idea_consistency.py`
- `scripts/render_workspace_views.py`
- `scripts/refresh_workspace_status.py`

### 5. merge 基础流

- `scripts/plan_idea_merge.py`
- `scripts/apply_idea_merge.py`
- `scripts/run_outline_workspace_pipeline.py`
- merge 默认受 consistency gate 约束

## 当前状态判断

项目已经从“蓝图阶段”进入“主链路闭环可跑”的阶段。

现在最缺的不是更多零散脚本，而是把以下链路补完整：

- consistency 结果到 timeline merge 的稳定落地
- 更强的 `knowledge-state` 与 patch 建议
- 更稳定的 timeline / outline / canon 联动
- 更明确的 skill 与 script 边界
- 更固定的项目协作文档

## 最近完成

- 为 intake 增加结构化 draft 层
- 新增 intake draft 的 JSON 与 HTML 产物
- 修复地点短语推断，使 `白塔议事厅` 这类地点可被正确提取
- 补齐对应测试并确认通过
- 落地 `novel-consistency-check` 的可用版，并接入 pipeline / 首页入口
- 新增 `relationship-history` 与 `world-rule` 两类冲突检查
- 让 merge plan 与 apply merge 显式读取 consistency gate
- 让 orchestrator 在 pending idea 上优先跑 consistency gate

## 当前风险

- 语义级 merge 仍然偏弱
- consistency-check 已可用，但 `knowledge-state` 仍主要靠弱语义推断
- skill 规划已写出，但执行优先级还需要持续收敛

## 近期目标

1. 扩展 `novel-consistency-check` 的 `knowledge-state` 与更细的 patch 建议
2. 基于 gate-aware merge 继续做 `novel-timeline-merge`
3. 提高 timeline / canon / outline 的联动质量
4. 继续收敛 skill 与 script 的边界
