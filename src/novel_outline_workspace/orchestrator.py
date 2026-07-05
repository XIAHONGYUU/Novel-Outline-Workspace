from __future__ import annotations

from pathlib import Path
from typing import Any

from .consistency import check_idea_consistency, consistency_report_needs_refresh, load_consistency_report
from .constraints_review import apply_approved_constraints_review, review_constraints
from .merge import pending_ideas, plan_idea_merge
from .reuse_review import apply_approved_reuse_review, review_reuse
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


def _constraints_review_reason(idea: dict[str, Any], progress: dict[str, Any]) -> str:
    title = str(idea.get("title") or progress.get("idea_id") or "pending idea")
    summary = str(progress.get("constraints_review_summary") or "").strip()
    policy_summary = str(progress.get("constraints_review_policy_summary") or "").strip()
    if summary:
        if policy_summary:
            return f"当前最早一条 pending idea `{title}` 已有 merge plan，但 constraints 仍需人工复核主体范围。{policy_summary}{summary}"
        return f"当前最早一条 pending idea `{title}` 已有 merge plan，但 constraints 仍需人工复核主体范围。{summary}"
    return f"当前最早一条 pending idea `{title}` 已有 merge plan，但 constraints 仍需人工复核主体范围。"


def _reuse_review_reason(idea: dict[str, Any], progress: dict[str, Any]) -> str:
    title = str(idea.get("title") or progress.get("idea_id") or "pending idea")
    summary = str(progress.get("reuse_review_summary") or "").strip()
    if summary:
        return f"当前最早一条 pending idea `{title}` 已有 merge plan，但 event / scene reuse 仍需人工复核。{summary}"
    return f"当前最早一条 pending idea `{title}` 已有 merge plan，但 event / scene reuse 仍需人工复核。"


def _reuse_apply_ready_reason(idea: dict[str, Any], progress: dict[str, Any]) -> str:
    title = str(idea.get("title") or progress.get("idea_id") or "pending idea")
    summary = str(progress.get("reuse_review_decision_summary") or "").strip()
    if summary:
        return f"当前最早一条 pending idea `{title}` 的 reuse review 已确认，可以直接消费已批准的 ready merge inputs。{summary}"
    return f"当前最早一条 pending idea `{title}` 的 reuse review 已确认，可以直接消费已批准的 ready merge inputs。"


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
        if report.get("error_count", 0) > 0:
            return {
                "workspace": str(workspace),
                "recommended_action": "check-consistency",
                "reason": "当前最早的 pending idea 存在 consistency 硬错误，应该先处理这条 idea 的报告。",
                "idea_id": target_idea.get("id"),
                "status": status,
            }
        progress = inspect_pending_idea_progress(workspace, target_idea)
        if progress.get("plan_status") in {"missing", "stale"}:
            return {
                "workspace": str(workspace),
                "recommended_action": "plan-merge",
                "reason": f"当前最早一条 pending idea `{target_idea.get('title')}` 已有最新 consistency，但 merge plan 还没跟上，先重跑 plan。",
                "idea_id": target_idea.get("id"),
                "status": status,
            }
        if progress.get("constraints_review_apply_ready"):
            return {
                "workspace": str(workspace),
                "recommended_action": "apply-merge",
                "reason": (
                    f"当前最早一条 pending idea `{target_idea.get('title')}` 的 constraints review 已确认，"
                    "可以直接消费已批准的 ready merge inputs。"
                ),
                "idea_id": target_idea.get("id"),
                "status": status,
            }
        if progress.get("reuse_review_apply_ready"):
            return {
                "workspace": str(workspace),
                "recommended_action": "apply-merge",
                "reason": _reuse_apply_ready_reason(target_idea, progress),
                "idea_id": target_idea.get("id"),
                "status": status,
            }
        if progress.get("needs_constraints_review"):
            return {
                "workspace": str(workspace),
                "recommended_action": "review-constraints",
                "reason": _constraints_review_reason(target_idea, progress),
                "idea_id": target_idea.get("id"),
                "status": status,
            }
        if progress.get("needs_reuse_review"):
            return {
                "workspace": str(workspace),
                "recommended_action": "review-reuse",
                "reason": _reuse_review_reason(target_idea, progress),
                "idea_id": target_idea.get("id"),
                "status": status,
            }
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

    if selected_action == "review-constraints":
        if not target_idea_id:
            raise ValueError("review-constraints requires a pending idea.")
        review = review_constraints(workspace, target_idea_id)
        result["executed"] = True
        result["constraints_review"] = review
        result["merge_plan"] = review.get("merge_plan")
        return result

    if selected_action == "review-reuse":
        if not target_idea_id:
            raise ValueError("review-reuse requires a pending idea.")
        review = review_reuse(workspace, target_idea_id)
        result["executed"] = True
        result["reuse_review"] = review
        result["merge_plan"] = review.get("merge_plan")
        return result

    if selected_action == "apply-merge":
        if not target_idea_id:
            raise ValueError("apply-merge requires a pending idea.")
        progress = inspect_pending_idea_progress(workspace, {"id": target_idea_id})
        if progress.get("constraints_review_apply_ready"):
            applied = apply_approved_constraints_review(workspace, target_idea_id)
            result["executed"] = True
            result["constraints_review"] = applied["constraints_review"]
            result["merge_result"] = applied["merge_result"]
            return result
        if progress.get("reuse_review_apply_ready"):
            applied = apply_approved_reuse_review(workspace, target_idea_id)
            result["executed"] = True
            result["reuse_review"] = applied["reuse_review"]
            result["merge_result"] = applied["merge_result"]
            return result
        applied = apply_approved_constraints_review(workspace, target_idea_id)
        result["executed"] = True
        result["constraints_review"] = applied["constraints_review"]
        result["merge_result"] = applied["merge_result"]
        return result

    raise ValueError(f"unsupported action: {selected_action}")
