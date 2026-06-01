from __future__ import annotations

from pathlib import Path
from typing import Any

from .consistency import check_idea_consistency, consistency_report_needs_refresh, load_consistency_report
from .merge import pending_ideas, plan_idea_merge
from .workspace import (
    _format_missing_field_labels,
    backfill_intake_drafts,
    collect_workspace_status,
    inspect_pending_idea_progress,
    render_workspace_views,
    validate_workspace,
)


def _repair_intake_reason(idea: dict[str, Any], progress: dict[str, Any]) -> str:
    title = str(idea.get("title") or progress.get("idea_id") or "pending idea")
    missing_fields = progress.get("missing_fields", [])
    if missing_fields:
        preview = _format_missing_field_labels(missing_fields)
        return f"当前最早一条 pending idea `{title}` 的 merge plan 还缺 {preview}，先补 intake 信息再继续 merge。"
    if progress.get("open_questions"):
        return f"当前最早一条 pending idea `{title}` 仍有待确认问题，先补 intake 信息再继续 merge。"
    return f"当前最早一条 pending idea `{title}` 还缺可执行信息，先修 intake draft 再继续 merge。"


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
        target_idea = pending[0]
        if consistency_report_needs_refresh(workspace, target_idea):
            return {
                "workspace": str(workspace),
                "recommended_action": "check-consistency",
                "reason": "当前存在 pending idea，且还没有最新的 consistency check，先跑 idea-level 冲突检查。",
                "idea_id": target_idea.get("id"),
                "status": status,
            }
        report = load_consistency_report(workspace, str(target_idea.get("id"))) or {}
        if report.get("error_count", 0) > 0 or report.get("conflict_count", 0) > 0:
            return {
                "workspace": str(workspace),
                "recommended_action": "check-consistency",
                "reason": "当前最早的 pending idea 存在 consistency 冲突，应该先处理这条 idea 的报告。",
                "idea_id": target_idea.get("id"),
                "status": status,
            }
        progress = inspect_pending_idea_progress(workspace, target_idea)
        if progress.get("needs_intake_repair"):
            return {
                "workspace": str(workspace),
                "recommended_action": "repair-intake",
                "reason": _repair_intake_reason(target_idea, progress),
                "idea_id": target_idea.get("id"),
                "status": status,
            }
        return {
            "workspace": str(workspace),
            "recommended_action": "plan-merge",
            "reason": "当前最早一条 pending idea 已通过基础 consistency gate，可以继续生成 merge plan。",
            "idea_id": target_idea.get("id"),
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

    if selected_action == "check-consistency":
        if not target_idea_id:
            raise ValueError("check-consistency requires a pending idea.")
        report = check_idea_consistency(workspace, target_idea_id)
        result["executed"] = True
        result["consistency_report"] = report
        return result

    if selected_action == "repair-intake":
        if not target_idea_id:
            raise ValueError("repair-intake requires a pending idea.")
        repair = backfill_intake_drafts(workspace, idea_ids=[target_idea_id])
        report = check_idea_consistency(workspace, target_idea_id)
        result["executed"] = True
        result["intake_repair"] = repair
        result["consistency_report"] = report
        return result

    if selected_action == "plan-merge":
        if not target_idea_id:
            raise ValueError("plan-merge requires a pending idea.")
        plan = plan_idea_merge(workspace, target_idea_id)
        result["executed"] = True
        result["merge_plan"] = plan
        return result

    raise ValueError(f"unsupported action: {selected_action}")
