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

### 6. consistency-check 增强

已支持：

- claim-level `knowledge-state` 提取
- `knowledge-state conflict` 的非同标题匹配
- report 级结构化 `patch_suggestions`

### 7. timeline merge 输入层

已支持：

- `plan_idea_merge` 输出结构化 `timeline_merge_inputs`
- `apply_idea_merge` 通过 `merge_input_id` 直接消费 merge plan 输入
- 对已有 scene 做跨章节移动时避免重复 scene id

### 8. canon relationship 联动

已支持：

- `state/canon-index.json` 新增 `relationships`
- relationship idea 可生成 `upsert-canon-relationship` merge input
- relationship / first-meeting 相关 issue 开始能驱动 canon 关系写入
- relationship-history 重复状态去重
- 关系在存在中间状态转移时的豁免规则

### 9. world-rule 闭环

已支持：

- `world-rule conflict` 生成结构化 merge input
- merge input 可同时更新事件/场景与 `constraints` 的 cutoff rule
- 在仅有 `world-rule conflict` 的情况下允许通过结构化 resolution input 直接 apply

## 当前状态判断

项目已经从“蓝图阶段”进入“主链路闭环可跑”的阶段。

现在最缺的不是更多零散脚本，而是把以下链路补完整：

- consistency 结果到 timeline merge 的稳定落地
- 把 `patch_suggestions` 真正接到更完整的 merge 执行策略
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
- 扩展 claim-level `knowledge-state` 检查
- 让 consistency report 输出结构化 `patch_suggestions`
- 让 merge plan 输出 `timeline_merge_inputs`
- 让 apply merge 能直接消费 `merge_input_id`
- 让 canon relationship 进入机器真相源并接入 merge
- 让 relationship merge input 优先复用已有关系节点
- 为 relationship-history 增加图谱级去重和转移豁免
- 让 world-rule conflict 接入 plan/apply 闭环

## 当前风险

- 语义级 merge 仍然偏弱
- consistency-check 已能输出 claim-level knowledge-state，但还不是完整图谱推理
- timeline merge 目前先打通了 timeline / outline 输入层，canon 联动仍偏弱
- relationship 目前已入 canon，但还缺更丰富的状态图谱和更细的豁免边界
- world-rule 已有一条结构化 resolution path，但策略还不够丰富
- skill 规划已写出，但执行优先级还需要持续收敛

## 近期目标

1. 扩展 `timeline_merge_inputs` 到更多 `world-rule` 策略与 canon 输入
2. 继续补 relationship 图谱里的更细豁免边界
3. 提高 timeline / canon / outline 的联动质量
4. 继续收敛 skill 与 script 的边界
