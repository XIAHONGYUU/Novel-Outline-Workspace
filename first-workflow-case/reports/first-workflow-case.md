# 第一个 Workflow 案例

最后更新：2026-06-01

## 案例目标

这个工作区用于记录“第一次按标准 workflow 跑一个新想法”的完整样本。

当前案例已经完成首轮完整闭环：

`ingest -> check-consistency -> plan-merge -> apply-merge -> validate`

也就是：

- 新想法已经进入 `inbox`
- intake draft / consistency report / merge plan / HTML views 已生成
- timeline / outline / canon knowledge-state 已正式写入
- validator 当前为 `ok=true`

## 本次使用的想法

- idea id: `idea-20260522-001`
- title: `林舟在白塔档案室发现泄密账册`
- content:

> 林舟在第三章的白塔档案室发现密账，由此知道议会内部有人泄密。

## 本次实际执行步骤

1. 初始化工作区：

```bash
python3 scripts/init_workspace.py \
  --workspace ./first-workflow-case \
  --novel-name "白塔疑案" \
  --protagonist-name "林舟"
```

2. 录入想法：

```bash
python3 scripts/ingest_idea.py \
  --workspace ./first-workflow-case \
  --title "林舟在白塔档案室发现泄密账册" \
  --kind reveal \
  --content "林舟在第三章的白塔档案室发现密账，由此知道议会内部有人泄密。"
```

3. 跑 consistency：

```bash
python3 scripts/check_idea_consistency.py \
  --workspace ./first-workflow-case \
  --idea-id idea-20260522-001 \
  --json
```

4. 生成 merge plan：

```bash
python3 scripts/plan_idea_merge.py \
  --workspace ./first-workflow-case \
  --idea-id idea-20260522-001 \
  --json
```

5. 执行 apply：

```bash
python3 scripts/apply_idea_merge.py \
  --workspace ./first-workflow-case \
  --idea-id idea-20260522-001 \
  --merge-input-id timeline-merge-001 \
  --merge-input-id timeline-merge-knowledge-001 \
  --resolution-note "把林舟在第三章白塔档案室发现密账并入 timeline、outline 与 canon knowledge-state，并将地点人工确认为白塔档案室。" \
  --location "白塔档案室" \
  --json
```

6. 校验并刷新状态：

```bash
python3 scripts/validate_workspace.py --workspace ./first-workflow-case --json
python3 scripts/refresh_workspace_status.py --workspace ./first-workflow-case --json
```

## 当前结果

- `state/idea-log.json` 中已有 1 条 `applied` idea
- consistency gate: `clear`
- `timeline/events.json` 中已有 1 条正式事件
- `outline/scene-index.json` 中已有 1 个正式场景
- `state/canon-index.json` 中已有 1 条正式 knowledge-state
- validator 当前为 `ok=true`，warning 已清零

## 关键文件

- inbox idea: `inbox/idea-20260522-001-林舟在白塔档案室发现泄密账册.md`
- intake draft: `state/intake-drafts/idea-20260522-001.json`
- consistency report: `state/consistency-checks/idea-20260522-001.json`
- merge plan: `state/merge-plans/idea-20260522-001.json`
- workspace status: `state/workspace-status.json`
- intake HTML: `views/intake-drafts/idea-20260522-001.html`
- consistency HTML: `views/consistency-checks/idea-20260522-001.html`
- merge plan HTML: `views/merge-plans/idea-20260522-001.html`

## 当前观察

- 这条案例现在已经证明：主链路可以在一个全新工作区里完整跑通到 `apply-merge`
- `plan_idea_merge` 已能同时给出：
  - timeline / outline 的事件与场景并入输入
  - canon knowledge-state 的并入输入
- 这轮也暴露了两个更关键的真实问题：
  - `apply_idea_merge.py` 原先没有暴露 knowledge-state CLI 参数，现已补齐；同时也已支持一次性消费多条 `merge_input_id`
  - `location_candidates` 仍会抽出 `的白塔` 这种弱值，apply 时仍需要人工确认

## 当前结论

这个案例不再是“可继续并入”的 pending 样本，而是“已完成首轮闭环”的基准样本。  
后续如果再拿它做验收，重点应从 `plan-merge` 前移到：

- `apply` 的可执行性
- 状态文件是否一致
- view / validator / pipeline 推荐动作是否跟正式状态一致
