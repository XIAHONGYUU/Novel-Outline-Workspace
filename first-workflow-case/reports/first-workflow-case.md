# 第一个 Workflow 案例

最后更新：2026-05-22

## 案例目标

这个工作区用于记录“第一次按标准 workflow 跑一个新想法”的完整样本。

当前案例刻意停在：

`ingest -> check-consistency -> plan-merge -> validate`

也就是：

- 新想法已经进入 `inbox`
- intake draft / consistency report / merge plan / HTML views 都已生成
- 还没有执行 `apply-merge`

这样后续打开这个工作区时，能直接看到一个“可继续并入”的 pending path。

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

5. 校验并刷新状态：

```bash
python3 scripts/validate_workspace.py --workspace ./first-workflow-case --json
python3 scripts/refresh_workspace_status.py --workspace ./first-workflow-case --json
```

## 当前结果

- `state/idea-log.json` 中已有 1 条 `pending` idea
- consistency gate: `clear`
- 当前已有 2 条可直接执行的 merge input：
  - `timeline-merge-001`
  - `timeline-merge-know-001`
- validator 当前为 `ok=true`，但仍有 2 条预期内 warning：
  - `no-events`
  - `no-scenes`

这是因为本案例故意停在 `plan-merge` 前，不主动 apply。

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

- 这条案例已经证明主链路可以在一个全新工作区里跑通到 `plan-merge`
- `plan_idea_merge` 已能同时给出：
  - timeline / outline 的事件与场景并入输入
  - canon knowledge-state 的并入输入
- 这条案例也保留了一个后续可继续优化的样本：
  - `location_candidates` 目前抽成了 `的白塔` 与 `白塔`
  - `knowledge_claims` 当前同时抽到了 `泄密账册`、`议会内部有人泄密`、`密账`

## 如果继续推进这条案例

下一步可直接执行：

```bash
python3 scripts/apply_idea_merge.py \
  --workspace ./first-workflow-case \
  --idea-id idea-20260522-001 \
  --merge-input-id timeline-merge-001 \
  --resolution-note "把白塔档案室发现密账并入第三章 timeline / outline。"
```

然后再补 canon 侧的 `timeline-merge-know-001`，最后重新跑 `validate`。
