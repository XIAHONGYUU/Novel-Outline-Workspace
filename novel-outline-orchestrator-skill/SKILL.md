---
name: novel-outline-orchestrator
description: Coordinate a novel outline workspace that captures ideas, plans merges, applies structured updates to canon/outline/timeline, and reruns validation plus HTML view generation.
---

# Novel Outline Orchestrator

Use this skill when the user wants one entry point for the novel outline workspace instead of manually choosing scripts.

This skill is not the data layer.

Its job is to:

- inspect the workspace first
- decide whether to validate, render, or plan a merge
- prefer the pending-idea queue when new ideas exist
- keep JSON as the source of truth
- regenerate HTML views after state changes

## Default Workflow

1. Read `state/workspace-status.json` first.
2. If there are validator errors, fix those before planning more merges.
3. If there are pending ideas, run the pipeline router or `plan_idea_merge.py`.
4. If the user has enough structured details, run `apply_idea_merge.py`.
5. After any change, rerun validation and refresh views.

## Primary Commands

Inspect and route:

```bash
python3 scripts/run_outline_workspace_pipeline.py --workspace <workspace> --json
```

Execute the recommended action:

```bash
python3 scripts/run_outline_workspace_pipeline.py --workspace <workspace> --execute
```

Plan one pending idea:

```bash
python3 scripts/plan_idea_merge.py --workspace <workspace> --idea-id <idea-id> --json
```

Apply one structured merge:

```bash
python3 scripts/apply_idea_merge.py --workspace <workspace> --idea-id <idea-id> --resolution-note "<note>" ...
```

## When To Read More

- For merge CLI fields and common patterns, read [references/merge-commands.md](references/merge-commands.md).
- For repository structure, read `README.md` and `WORKFLOW.md`.

## Guardrails

- Do not treat HTML as the source of truth.
- Do not mark an idea `applied` unless actual target files were updated.
- Prefer updating JSON first, then append short Markdown patch notes.
- Always leave the workspace with refreshed HTML views.
