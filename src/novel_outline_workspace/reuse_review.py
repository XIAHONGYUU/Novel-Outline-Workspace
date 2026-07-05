from __future__ import annotations

from pathlib import Path
from typing import Any

from .merge import apply_idea_merge, plan_idea_merge
from .workspace import (
    collect_workspace_status,
    compute_review_plan_fingerprint,
    now_iso,
    read_json,
    render_workspace_views,
    validate_workspace,
    write_json,
)


def _reuse_review_path(workspace: Path, idea_id: str) -> Path:
    return workspace / "state/reuse-reviews" / f"{idea_id}.json"


def _load_existing_report(workspace: Path, idea_id: str) -> dict[str, Any]:
    report = read_json(_reuse_review_path(workspace, idea_id), {})
    return report if isinstance(report, dict) else {}


def _load_idea_snapshot(workspace: Path, idea_id: str) -> dict[str, Any]:
    idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
    for idea in idea_log.get("ideas", []):
        if str(idea.get("id") or "").strip() == idea_id:
            return idea if isinstance(idea, dict) else {}
    return {}


def _load_workspace_status_snapshot(workspace: Path) -> dict[str, Any]:
    status = read_json(workspace / "state/workspace-status.json", {})
    return status if isinstance(status, dict) else {}


def _action_snapshot(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain": str(action.get("domain") or "").strip(),
        "action": str(action.get("action") or "").strip(),
        "summary": str(action.get("summary") or "").strip(),
        "readiness": str(action.get("readiness") or "").strip(),
        "merge_input_id": action.get("merge_input_id"),
        "target_files": [str(item).strip() for item in action.get("target_files", []) if str(item).strip()],
        "planned_writes": [str(item).strip() for item in action.get("planned_writes", []) if str(item).strip()],
        "source_signals": [str(item).strip() for item in action.get("source_signals", []) if str(item).strip()],
        "warnings": [str(item).strip() for item in action.get("warnings", []) if str(item).strip()],
        "review_tokens": [str(item).strip() for item in action.get("review_tokens", []) if str(item).strip()],
    }


def _merge_input_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or "").strip(),
        "strategy": str(item.get("strategy") or "").strip(),
        "summary": str(item.get("summary") or "").strip(),
        "target_files": [str(path).strip() for path in item.get("target_files", []) if str(path).strip()],
        "can_apply_directly": bool(item.get("can_apply_directly")),
        "missing_fields": [str(field).strip() for field in item.get("missing_fields", []) if str(field).strip()],
        "warnings": [str(field).strip() for field in item.get("warnings", []) if str(field).strip()],
        "review_tokens": [str(field).strip() for field in item.get("review_tokens", []) if str(field).strip()],
    }


def _review_checklist(review_tokens: list[str], review_inputs: list[dict[str, Any]]) -> list[str]:
    checklist: list[str] = []
    if "reuse-ambiguity-linked-scenes" in review_tokens:
        checklist.append("确认当前 event 应该向哪一条 linked scene 对齐参与者，而不是继续沿用旧 event 残留 participants。")
    if "reuse-ambiguity-linked-events" in review_tokens:
        checklist.append("确认当前 scene 应该挂到哪一条旧 event，而不是继续保留多条兼容候选。")
    if review_inputs:
        checklist.append("复核通过后，可只消费已确认无歧义的 ready merge inputs，歧义输入继续留给后续修正。")
    return checklist


def _normalize_selected_merge_input_ids(
    ready_inputs: list[dict[str, Any]],
    selected_merge_input_ids: list[str] | None,
) -> list[str]:
    ready_ids = [str(item.get("id") or "").strip() for item in ready_inputs if str(item.get("id") or "").strip()]
    if not ready_ids:
        return []
    normalized = [str(item or "").strip() for item in (selected_merge_input_ids or []) if str(item or "").strip()]
    if not normalized:
        return ready_ids
    unknown = [item for item in normalized if item not in ready_ids]
    if unknown:
        raise ValueError(f"selected merge_input_id(s) are not ready for apply: {', '.join(unknown)}")
    deduped: list[str] = []
    for item in normalized:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _selected_merge_input_snapshots(
    ready_inputs: list[dict[str, Any]],
    selected_merge_input_ids: list[str],
) -> list[dict[str, Any]]:
    selected = set(selected_merge_input_ids)
    return [item for item in ready_inputs if str(item.get("id") or "").strip() in selected]


def _remaining_review_input_snapshots(review_inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in review_inputs
        if str(item.get("id") or "").strip()
    ]


def _is_apply_ready_decision(
    decision: dict[str, Any],
    *,
    ready_inputs: list[dict[str, Any]],
    merge_plan_fingerprint: str,
) -> bool:
    if str(decision.get("status") or "").strip() != "approved-ready-merge-inputs":
        return False
    if not str(decision.get("resolution_note") or "").strip():
        return False
    if str(decision.get("merge_plan_fingerprint") or "").strip() != merge_plan_fingerprint:
        return False
    ready_ids = {str(item.get("id") or "").strip() for item in ready_inputs if str(item.get("id") or "").strip()}
    selected_ids = {
        str(item).strip()
        for item in decision.get("selected_merge_input_ids", [])
        if str(item).strip()
    }
    return bool(selected_ids) and selected_ids.issubset(ready_ids)


def _decision_summary(status: str, selected_merge_input_ids: list[str], review_tokens: list[str]) -> str:
    if status == "approved-ready-merge-inputs":
        merge_input_preview = "、".join(selected_merge_input_ids)
        token_preview = "、".join(review_tokens)
        if token_preview:
            return f"已确认先消费 ready merge inputs：{merge_input_preview}；reuse 歧义 `{token_preview}` 暂保留待后续修正。"
        return f"已确认先消费 ready merge inputs：{merge_input_preview}。"
    if status == "rejected":
        return "已确认当前 reuse-review case 不进入 apply，保留为人工处理。"
    return "已记录本轮 reuse review 决策。"


def _review_state(review_required: bool, decision: dict[str, Any]) -> str:
    if str(decision.get("status") or "").strip() == "rejected" or bool(decision.get("rejected")):
        return "rejected"
    if bool(decision.get("applied")):
        return "applied"
    if bool(decision.get("apply_ready")):
        return "approved-ready-merge-inputs"
    if review_required:
        return "needs-review"
    return "review-not-required"


def _review_status_summary(
    review_required: bool,
    decision: dict[str, Any],
    review_summary: str,
) -> str:
    if str(decision.get("status") or "").strip() == "rejected" or bool(decision.get("rejected")):
        rejected_at = str(decision.get("rejected_at") or decision.get("decided_at") or "").strip()
        if rejected_at:
            return f"这条 reuse review 已于 {rejected_at} 确认不进入 apply，并已把 idea 标记为 rejected。"
        return "这条 reuse review 已确认不进入 apply，并已把 idea 标记为 rejected。"
    if bool(decision.get("applied")):
        applied_at = str(decision.get("applied_at") or "").strip()
        if applied_at:
            return f"这条 reuse review 决策已于 {applied_at} 被消费，并已把批准的 merge inputs 写回 workspace。"
        return "这条 reuse review 决策已被消费，并已把批准的 merge inputs 写回 workspace。"
    if bool(decision.get("apply_ready")):
        return str(decision.get("summary") or "").strip()
    if review_required:
        return review_summary
    return "当前无需额外 reuse review。"


def _archived_review_action(report: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain": "review",
        "action": "保留已确认的 reuse review 决策。",
        "summary": _review_status_summary(
            False,
            decision,
            str(report.get("review_summary") or "").strip(),
        ),
        "readiness": "applied",
        "merge_input_id": None,
        "target_files": [
            str(item).strip()
            for item in next(
                (
                    action.get("target_files", [])
                    for action in report.get("action_matrix", [])
                    if str(action.get("domain") or "").strip() == "review"
                ),
                [],
            )
            if str(item).strip()
        ],
        "planned_writes": [
            f"decision: {str(decision.get('status') or '').strip()}",
            (
                f"applied_merge_inputs: {', '.join(str(item).strip() for item in decision.get('applied_merge_input_ids', []) if str(item).strip()) or ', '.join(str(item).strip() for item in decision.get('selected_merge_input_ids', []) if str(item).strip())}"
                if str(decision.get("status") or "").strip() != "rejected"
                else "idea_status: rejected"
            ),
        ],
        "source_signals": ["reuse-review: terminal decision"],
        "warnings": [],
        "review_tokens": [
            str(item).strip()
            for item in report.get("review_tokens", [])
            if str(item).strip()
        ],
    }


def _archived_apply_rows(decision: dict[str, Any], idea: dict[str, Any]) -> list[dict[str, Any]]:
    selected_inputs = decision.get("selected_merge_inputs", [])
    updated_files = [str(item).strip() for item in idea.get("target_files", []) if str(item).strip()]
    rows: list[dict[str, Any]] = []
    for item in selected_inputs:
        target_files = [str(path).strip() for path in item.get("target_files", []) if str(path).strip()]
        domains: set[str] = set()
        for path in target_files:
            if path.startswith("timeline/"):
                domains.add("timeline")
            if path.startswith("outline/"):
                domains.add("outline")
            if path.startswith("canon/") or path.startswith("state/canon-index.json"):
                domains.add("canon")
        for domain in sorted(domains):
            rows.append(
                {
                    "domain": domain,
                    "action": "已消费已批准的 merge input。",
                    "summary": f"已根据 `{str(item.get('id') or '').strip()}` 把对应写入落到 {domain} 层。",
                    "readiness": "applied",
                    "merge_input_id": str(item.get("id") or "").strip() or None,
                    "target_files": target_files,
                    "planned_writes": updated_files,
                    "source_signals": ["reuse-review: approved merge input applied"],
                    "warnings": [],
                    "review_tokens": [],
                }
            )
    return rows


def _archive_consistency_gate(decision: dict[str, Any]) -> dict[str, Any]:
    status = str(decision.get("status") or "").strip()
    if status == "rejected":
        return {
            "status": "closed",
            "can_plan_merge": False,
            "can_apply_merge": False,
            "summary": "这条 reuse review 已确认不进入 apply，并已关闭当前 idea。",
            "report_path": None,
            "view_path": None,
            "blockers": [],
            "warnings": [],
        }
    return {
        "status": "consumed",
        "can_plan_merge": False,
        "can_apply_merge": False,
        "summary": "这条 reuse review 已完成，并已消费批准的 merge inputs。",
        "report_path": None,
        "view_path": None,
        "blockers": [],
        "warnings": [],
    }


def _build_applied_reuse_review(
    workspace: Path,
    report: dict[str, Any],
    decision: dict[str, Any],
    idea: dict[str, Any],
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    archived = dict(report)
    archived["status"] = str(idea.get("status") or archived.get("status") or "").strip()
    archived["review_required"] = False
    archived["review_state"] = _review_state(False, decision)
    archived["review_status_summary"] = _review_status_summary(
        False,
        decision,
        str(archived.get("review_summary") or "").strip(),
    )
    archived["review_checklist"] = []
    archived["review_merge_inputs"] = []
    archived["remaining_review_merge_inputs"] = [
        item
        for item in decision.get("remaining_review_merge_inputs", report.get("remaining_review_merge_inputs", []))
        if isinstance(item, dict)
    ]
    archived["ready_merge_inputs"] = []
    archived["blocked_merge_inputs"] = []
    archived["consistency_gate"] = _archive_consistency_gate(decision)
    archived["action_matrix"] = [_archived_review_action(archived, decision)]
    if str(decision.get("status") or "").strip() != "rejected":
        archived["action_matrix"].extend(_archived_apply_rows(decision, idea))
    archived["decision"] = decision
    archived["updated_at"] = now_iso()
    decision_status = str(decision.get("status") or "").strip()
    if result is not None:
        merge_result = result.get("merge_result", result)
        validation_report = merge_result.get("validation_report", {})
        result_snapshot = {
            "status": str(idea.get("status") or "").strip(),
            "resolution_note": str(idea.get("resolution_note") or "").strip(),
            "applied_merge_input_ids": [
                str(item).strip()
                for item in idea.get("applied_merge_input_ids", [])
                if str(item).strip()
            ],
            "updated_files": [str(item).strip() for item in merge_result.get("updated_files", []) if str(item).strip()],
            "validation_ok": bool(validation_report.get("ok")),
            "validation_report_path": str(validation_report.get("report_path") or "").strip(),
            "validated_at": str(validation_report.get("validated_at") or "").strip(),
            "applied_at": str(decision.get("applied_at") or decision.get("rejected_at") or "").strip(),
        }
        if decision_status == "rejected":
            archived.pop("applied_result", None)
            archived["rejected_result"] = result_snapshot
        else:
            archived.pop("rejected_result", None)
            archived["applied_result"] = result_snapshot
    else:
        workspace_status = _load_workspace_status_snapshot(workspace)
        last_validation = workspace_status.get("last_validation", {})
        result_snapshot = {
            "status": str(idea.get("status") or "").strip(),
            "resolution_note": str(idea.get("resolution_note") or "").strip(),
            "applied_merge_input_ids": [
                str(item).strip()
                for item in idea.get("applied_merge_input_ids", [])
                if str(item).strip()
            ],
            "updated_files": [str(item).strip() for item in idea.get("target_files", []) if str(item).strip()],
            "validation_ok": bool(last_validation.get("ok")),
            "validation_report_path": str(last_validation.get("report_path") or "").strip(),
            "validated_at": str(last_validation.get("validated_at") or "").strip(),
            "applied_at": str(decision.get("applied_at") or decision.get("rejected_at") or "").strip(),
        }
        if decision_status == "rejected":
            archived.pop("applied_result", None)
            archived["rejected_result"] = result_snapshot
        else:
            archived.pop("rejected_result", None)
            archived["applied_result"] = result_snapshot
    return archived


def _mark_idea_rejected(workspace: Path, idea_id: str, resolution_note: str) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
    for index, idea in enumerate(idea_log.get("ideas", [])):
        if str(idea.get("id") or "").strip() != idea_id:
            continue
        idea["status"] = "rejected"
        idea["resolution_note"] = resolution_note
        idea["updated_at"] = now_iso()
        idea_log["ideas"][index] = idea
        write_json(workspace / "state/idea-log.json", idea_log)
        validation_report = validate_workspace(workspace)
        status = collect_workspace_status(workspace)
        render_workspace_views(workspace, status=status, validation_report=validation_report)
        return {
            "idea": idea,
            "validation_report": validation_report,
        }
    raise ValueError(f"unknown idea id: {idea_id}")


def review_reuse(workspace: Path, idea_id: str) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    existing_report = _load_existing_report(workspace, idea_id)
    existing_decision = existing_report.get("decision", {}) if isinstance(existing_report.get("decision", {}), dict) else {}
    idea = _load_idea_snapshot(workspace, idea_id)
    if (
        bool(existing_decision.get("applied"))
        and str(idea.get("status") or "").strip() == "applied"
    ) or (
        str(existing_decision.get("status") or "").strip() == "rejected"
        and str(idea.get("status") or "").strip() == "rejected"
    ):
        report = _build_applied_reuse_review(workspace, existing_report, existing_decision, idea)
        report_path = _reuse_review_path(workspace, idea_id)
        write_json(report_path, report)
        report["report_path"] = str(report_path.resolve())
        return report

    plan = plan_idea_merge(workspace, idea_id)
    review_actions = [
        action
        for action in plan.get("proposed_actions", [])
        if str(action.get("domain") or "").strip() == "review"
    ]
    review_action = next(
        (
            action
            for action in review_actions
            if str(action.get("readiness") or "").strip() == "needs-review"
        ),
        review_actions[0] if review_actions else {},
    )
    review_tokens = [
        str(token).strip()
        for token in plan.get("review_tokens", [])
        if str(token).strip().startswith("reuse-ambiguity-")
    ]
    review_input_ids = {
        str(item.get("id") or "").strip()
        for item in plan.get("timeline_merge_inputs", [])
        if any(str(token).strip().startswith("reuse-ambiguity-") for token in item.get("review_tokens", []))
    }
    review_inputs = [
        _merge_input_snapshot(item)
        for item in plan.get("timeline_merge_inputs", [])
        if str(item.get("id") or "").strip() in review_input_ids
    ]
    ready_merge_inputs = [
        _merge_input_snapshot(item)
        for item in plan.get("timeline_merge_inputs", [])
        if not item.get("missing_fields")
        and str(item.get("id") or "").strip() not in review_input_ids
    ]
    blocked_merge_inputs = [
        _merge_input_snapshot(item)
        for item in plan.get("timeline_merge_inputs", [])
        if str(item.get("id") or "").strip() not in {str(row.get("id") or "").strip() for row in ready_merge_inputs}
        and str(item.get("id") or "").strip() not in review_input_ids
    ]
    review_required = str(review_action.get("readiness") or "").strip() == "needs-review" and bool(review_tokens)
    report = {
        "idea_id": idea_id,
        "title": plan.get("title"),
        "status": plan.get("status"),
        "review_required": review_required,
        "review_state": _review_state(review_required, existing_decision),
        "review_status_summary": _review_status_summary(
            review_required,
            existing_decision,
            str(review_action.get("summary") or "").strip(),
        ),
        "review_summary": str(review_action.get("summary") or "").strip(),
        "review_tokens": review_tokens,
        "review_checklist": _review_checklist(review_tokens, review_inputs),
        "review_merge_inputs": review_inputs,
        "remaining_review_merge_inputs": review_inputs,
        "ready_merge_inputs": ready_merge_inputs,
        "blocked_merge_inputs": blocked_merge_inputs,
        "action_matrix": [_action_snapshot(action) for action in plan.get("proposed_actions", [])],
        "consistency_gate": plan.get("consistency_gate", {}),
        "merge_plan_path": str(plan.get("plan_path") or ""),
        "merge_plan_view_path": str(plan.get("view_path") or ""),
        "created_at": now_iso(),
    }
    if existing_decision:
        report["decision"] = existing_decision
    report_path = _reuse_review_path(workspace, idea_id)
    write_json(report_path, report)
    report["report_path"] = str(report_path.resolve())
    report["merge_plan"] = plan
    return report


def record_reuse_review_decision(
    workspace: Path,
    idea_id: str,
    *,
    decision: str = "approved-ready-merge-inputs",
    selected_merge_input_ids: list[str] | None = None,
    resolution_note: str | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    report = review_reuse(workspace, idea_id)
    ready_inputs = report.get("ready_merge_inputs", [])
    if decision == "approved-ready-merge-inputs":
        if not report.get("review_required"):
            raise ValueError(f"`{idea_id}` does not currently require reuse review.")
        selected_ids = _normalize_selected_merge_input_ids(ready_inputs, selected_merge_input_ids)
        if not selected_ids:
            raise ValueError(f"`{idea_id}` has no ready merge inputs to approve.")
        note = str(resolution_note or "").strip()
        if not note:
            raise ValueError("approved-ready-merge-inputs requires a resolution note.")
    elif decision == "rejected":
        if not report.get("review_required"):
            raise ValueError(f"`{idea_id}` does not currently require reuse review.")
        selected_ids = []
        note = str(resolution_note or "").strip()
        if not note:
            raise ValueError("rejected requires a resolution note.")
    else:
        raise ValueError(f"unsupported reuse review decision: {decision}")

    merge_plan = report.get("merge_plan", {})
    review_inputs = report.get("review_merge_inputs", [])
    decision_record = {
        "status": decision,
        "summary": _decision_summary(
            decision,
            selected_ids,
            [str(item).strip() for item in report.get("review_tokens", []) if str(item).strip()],
        ),
        "resolution_note": note,
        "reviewer": str(reviewer or "").strip(),
        "selected_merge_input_ids": selected_ids,
        "selected_merge_inputs": _selected_merge_input_snapshots(ready_inputs, selected_ids),
        "remaining_review_merge_input_ids": [
            str(item.get("id") or "").strip()
            for item in review_inputs
            if str(item.get("id") or "").strip()
        ],
        "remaining_review_merge_inputs": _remaining_review_input_snapshots(review_inputs),
        "apply_ready": _is_apply_ready_decision(
            {
                "status": decision,
                "resolution_note": note,
                "selected_merge_input_ids": selected_ids,
                "merge_plan_fingerprint": compute_review_plan_fingerprint(merge_plan),
            },
            ready_inputs=ready_inputs,
            merge_plan_fingerprint=compute_review_plan_fingerprint(merge_plan),
        ),
        "merge_plan_created_at": str(merge_plan.get("created_at") or "").strip(),
        "merge_plan_fingerprint": compute_review_plan_fingerprint(merge_plan),
        "decided_at": now_iso(),
    }
    if decision == "rejected":
        decision_record["rejected"] = True
        decision_record["rejected_at"] = decision_record["decided_at"]

    if decision == "rejected":
        rejected_result = _mark_idea_rejected(workspace, idea_id, note)
        terminal_report = _build_applied_reuse_review(
            workspace,
            report,
            decision_record,
            rejected_result["idea"],
            rejected_result,
        )
        report_path = Path(str(report.get("report_path") or _reuse_review_path(workspace, idea_id))).expanduser().resolve()
        persisted_report = {key: value for key, value in terminal_report.items() if key not in {"report_path", "merge_plan"}}
        write_json(report_path, persisted_report)
        terminal_report["report_path"] = str(report_path)
        return terminal_report

    report["decision"] = decision_record
    report_path = Path(str(report.get("report_path") or _reuse_review_path(workspace, idea_id))).expanduser().resolve()
    persisted_report = {key: value for key, value in report.items() if key not in {"report_path", "merge_plan"}}
    write_json(report_path, persisted_report)
    report["report_path"] = str(report_path)
    return report


def apply_approved_reuse_review(workspace: Path, idea_id: str) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    report = review_reuse(workspace, idea_id)
    decision = report.get("decision", {})
    merge_plan = report.get("merge_plan", {})
    merge_plan_fingerprint = compute_review_plan_fingerprint(merge_plan)
    if not isinstance(decision, dict) or not _is_apply_ready_decision(
        decision,
        ready_inputs=report.get("ready_merge_inputs", []),
        merge_plan_fingerprint=merge_plan_fingerprint,
    ):
        raise ValueError(f"`{idea_id}` does not have an apply-ready reuse review decision.")

    result = apply_idea_merge(
        workspace,
        idea_id=idea_id,
        merge_input_ids=[
            str(item).strip()
            for item in decision.get("selected_merge_input_ids", [])
            if str(item).strip()
        ],
        resolution_note=str(decision.get("resolution_note") or "").strip(),
        override_consistency_gate=True,
    )
    refreshed_decision = dict(decision)
    refreshed_decision["apply_ready"] = False
    refreshed_decision["applied"] = True
    refreshed_decision["applied_at"] = now_iso()
    refreshed_decision["applied_merge_input_ids"] = list(result["idea"].get("applied_merge_input_ids", []))
    refreshed_report = _build_applied_reuse_review(workspace, report, refreshed_decision, result["idea"], result)
    report_path = Path(str(report.get("report_path") or _reuse_review_path(workspace, idea_id))).expanduser().resolve()
    persisted_report = {key: value for key, value in refreshed_report.items() if key not in {"report_path", "merge_plan"}}
    write_json(report_path, persisted_report)
    refreshed_report["report_path"] = str(report_path)
    return {
        "reuse_review": refreshed_report,
        "merge_result": result,
    }
