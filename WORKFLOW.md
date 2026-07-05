# 工作流

这个项目采用“想法补丁”而不是“一次性重写大纲”的模式。

## 主循环

```text
新想法
  -> inbox
  -> 结构化登记
  -> 冲突校验
  -> merge plan
  -> 人工确认 / override
  -> 更新 canon / outline / timeline
  -> validate
  -> 写回状态与 HTML 视图
```

当 `constraints` explainer 明确进入 `needs-review` 时，当前推荐子路径是：

```text
plan-merge
  -> review-constraints
  -> resolve-constraints-review
  -> apply-merge
  -> validate
```

当 `review` explainer 明确进入 `needs-review` 时，当前推荐子路径是：

```text
check-consistency
  -> plan-merge
  -> review-reuse
  -> resolve-reuse-review
  -> apply-merge
  -> validate
```

## 当前默认推进框架

从 `P0` 当前阶段开始，默认不再按“哪里像是还能补规则”来推进，而是按一组固定的 `acceptance tracks` 推进：

1. 先识别当前缺的是哪一条工作区闭环
2. 再选一个最小但真实的 workspace case 去跑
3. 只有真实闭环被卡住时，才回头修规则或 planner

详见：

- `docs/workspace-acceptance-framework.md`

## 各层职责

### `inbox`

用于收集未经整理的原始想法。

允许：

- 碎片化
- 口语化
- 只有一个设定点

不要求：

- 立即成为正式 canon
- 立即改完整个大纲

### `canon`

当前正式设定层。

适合放：

- 角色身份
- 关系网
- 世界规则
- 阵营结构
- 不可违背的硬设定

### `outline`

当前正式大纲层。

适合放：

- 卷级结构
- 幕级结构
- 章节摘要
- scene beats

### `timeline`

事件时间层。

适合放：

- 关键事件
- 事件先后
- 事件参与者
- 已知死亡点
- 已知揭露点

### `reports`

保留补充说明和非结构化诊断。

适合放：

- 待确认冲突
- 需要补写的影响面

### `views`

主要生成产物层。

适合放：

- `index.html`
- `validation-report.html`
- `timeline.html`
- 后续的角色页、关系页、地图页

### `state`

机器共享状态层。

适合放：

- `workspace-status.json`
- `idea-log.json`
- `canon-index.json`

## 第一版模式

### `fresh`

还没有工作区，先创建骨架。

### `extend-existing`

已有工作区，新增设定或补充一段大纲。

### `repair-existing`

已有正式文件，但发现明显冲突或引用失效，需要修复。

### `validate-only`

只检查，不修改内容。

## 第一版边界

当前版本先处理：

- 工作区模板
- idea inbox 录入
- 状态刷新
- 基础结构校验
- 第一批硬冲突检查
- 基础 HTML 页面生成
- idea merge plan
- 结构化 apply merge
- orchestrator 路由入口

当前版本暂不自动完成：

- 高质量语义合并
- 全自动重写章节摘要
- 自动解决所有冲突
- 高交互地图式前端
