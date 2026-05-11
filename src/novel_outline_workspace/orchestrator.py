from __future__ import annotations

from pathlib import Path
from typing import Any

from .merge import pending_ideas, plan_idea_merge
from .workspace import collect_workspace_status, render_workspace_views, validate_workspace


def choose_next_action(workspace: Path) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    status = collect_workspace_status(workspace)
    pending = pending_ideas(workspace)

    if status.get("last_validation", {}).get("error_count", 0) > 0:
        return {
            "workspace": str(workspace),
            "recommended_action": "validate",
            "reason": "当前存在硬冲突，优先重跑校验并修复。",
            "idea_id": None,
            "status": status,
        }
    if pending:
        return {
            "workspace": str(workspace),
            "recommended_action": "plan-merge",
            "reason": "当前存在 pending idea，优先为最早一条想法生成 merge plan。",
            "idea_id": pending[0].get("id"),
            "status": status,
        }
    if status.get("entity_counts", {}).get("events", 0) == 0 or status.get("entity_counts", {}).get("scenes", 0) == 0:
        return {
            "workspace": str(workspace),
            "recommended_action": "render",
            "reason": "工作区还缺正式事件或场景，先保持视图同步，然后补基础结构。",
            "idea_id": None,
            "status": status,
        }
    return {
        "workspace": str(workspace),
        "recommended_action": "validate",
        "reason": "当前没有 pending idea，默认做一次状态校验。",
        "idea_id": None,
        "status": status,
    }


def run_outline_workspace_pipeline(
    workspace: Path,
    *,
    action: str = "auto",
    execute: bool = False,
    idea_id: str | None = None,
) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    decision = choose_next_action(workspace)

    selected_action = decision["recommended_action"] if action == "auto" else action
    target_idea_id = idea_id or decision.get("idea_id")
    result: dict[str, Any] = {
        "workspace": str(workspace),
        "recommended_action": decision["recommended_action"],
        "selected_action": selected_action,
        "reason": decision["reason"],
        "idea_id": target_idea_id,
        "executed": False,
        "status": decision["status"],
    }

    if not execute:
        return result

    if selected_action == "validate":
        report = validate_workspace(workspace)
        result["executed"] = True
        result["validation_report"] = report
        return result

    if selected_action == "render":
        outputs = render_workspace_views(workspace, status=collect_workspace_status(workspace))
        result["executed"] = True
        result["rendered_views"] = outputs
        return result

    if selected_action == "plan-merge":
        if not target_idea_id:
            raise ValueError("plan-merge requires a pending idea.")
        plan = plan_idea_merge(workspace, target_idea_id)
        result["executed"] = True
        result["merge_plan"] = plan
        return result

    raise ValueError(f"unsupported action: {selected_action}")
