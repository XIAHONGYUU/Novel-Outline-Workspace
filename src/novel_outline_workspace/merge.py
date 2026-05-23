from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .consistency import consistency_report_needs_refresh, load_consistency_report
from .workspace import (
    _html_page,
    _safe,
    collect_workspace_status,
    default_canon_index,
    now_iso,
    read_json,
    render_workspace_views,
    slugify,
    validate_workspace,
    write_json,
    write_text,
)

DOMAIN_TARGET_FILES = {
    "canon": ["state/canon-index.json", "canon/characters.md"],
    "outline": ["outline/scene-index.json", "outline/master-outline.md"],
    "constraints": ["constraints/constraints.json"],
    "timeline": ["timeline/events.json"],
}

KIND_DOMAIN_MAP = {
    "character": ["canon", "outline"],
    "relationship": ["canon", "outline"],
    "world": ["canon"],
    "reveal": ["canon", "outline", "timeline"],
    "twist": ["outline", "timeline"],
    "scene": ["outline"],
    "event": ["timeline", "outline"],
    "death": ["canon", "timeline", "outline"],
    "backstory": ["canon", "timeline"],
    "misc": ["outline"],
}

TIMELINE_RELEVANT_ISSUES = {
    "knowledge-state-conflict",
    "timeline-order-conflict",
    "location-continuity-conflict",
}
KNOWLEDGE_RELEVANT_ISSUES = {
    "knowledge-state-conflict",
}
RELATIONSHIP_RELEVANT_ISSUES = {
    "relationship-history-conflict",
    "first-meeting-conflict",
}
WORLD_RULE_RELEVANT_ISSUES = {
    "world-rule-conflict",
}
RELATIONSHIP_STATE_MAP = {
    "结盟": "allied",
    "和解": "reconciled",
    "决裂": "ruptured",
    "背叛": "betrayed",
    "认识": "acquainted",
    "初见": "met",
    "不认识": "strangers",
}
RELATIONSHIP_STATE_LABELS = {
    "allied": "结盟",
    "reconciled": "和解",
    "ruptured": "决裂",
    "betrayed": "背叛",
    "acquainted": "认识",
    "met": "初见",
    "strangers": "互不认识",
}


def _load_idea_log(workspace: Path) -> dict[str, Any]:
    return read_json(workspace / "state/idea-log.json", {"ideas": []})


def _find_idea(workspace: Path, idea_id: str) -> tuple[dict[str, Any], dict[str, Any], int]:
    idea_log = _load_idea_log(workspace)
    for index, idea in enumerate(idea_log.get("ideas", [])):
        if idea.get("id") == idea_id:
            return idea_log, idea, index
    raise ValueError(f"idea not found: {idea_id}")


def pending_ideas(workspace: Path) -> list[dict[str, Any]]:
    idea_log = _load_idea_log(workspace)
    return [idea for idea in idea_log.get("ideas", []) if idea.get("status") == "pending"]


def _infer_domains(idea: dict[str, Any], protagonist_name: str | None) -> list[str]:
    domains: set[str] = set(KIND_DOMAIN_MAP.get(str(idea.get("kind", "misc")).lower(), ["outline"]))
    haystack = " ".join(
        [str(idea.get("title", "")), str(idea.get("content", "")), " ".join(idea.get("tags", []))]
    )

    if protagonist_name and protagonist_name in haystack:
        domains.update({"canon", "outline"})
    if any(token in haystack for token in ["身份", "真相", "秘密", "揭露", "知道", "背叛"]):
        domains.update({"canon", "outline"})
    if any(token in haystack for token in ["死亡", "死", "牺牲", "杀"]):
        domains.update({"canon", "timeline", "outline"})
    if any(token in haystack for token in ["第一章", "第二章", "第三章", "卷", "幕", "chapter", "scene", "场景"]):
        domains.update({"outline", "timeline"})
    if any(token in haystack for token in ["地点", "路程", "离开", "抵达", "出发"]):
        domains.update({"timeline"})

    return sorted(domains)


def _unresolved_questions(domains: list[str]) -> list[str]:
    questions: list[str] = []
    if "canon" in domains:
        questions.append("是否需要新增或更新某个正式角色 / 设定条目？")
    if "outline" in domains:
        questions.append("这条想法具体落在哪一章或哪一个 scene？")
    if "timeline" in domains:
        questions.append("这条想法对应的真实时间序号、阅读章节和参与者是什么？")
    return questions


def _target_file_domains(target_files: list[str]) -> list[str]:
    domains: list[str] = []
    for path in target_files:
        if path.startswith("timeline/"):
            domains.append("timeline")
        elif path.startswith("outline/"):
            domains.append("outline")
        elif path.startswith("constraints/"):
            domains.append("constraints")
        elif path.startswith("canon/") or path.startswith("state/canon"):
            domains.append("canon")
    return sorted(set(domains))


def _readiness_for_input(item: dict[str, Any], gate: dict[str, Any]) -> str:
    if item.get("can_apply_directly"):
        return "ready"
    if item.get("missing_fields"):
        return "needs-info"
    if item.get("requires_override") or (gate.get("status") == "blocked" and not item.get("resolves_blocked_gate")):
        return "blocked-by-gate"
    if gate.get("status") == "warning":
        return "needs-review"
    return "planned"


def _source_signals_for_input(domain: str, item: dict[str, Any], draft: dict[str, Any], report: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    apply_args = item.get("apply_args", {}) if isinstance(item.get("apply_args"), dict) else {}
    if domain in {"timeline", "outline"}:
        chapter = apply_args.get("reading_chapter") if domain == "timeline" else apply_args.get("chapter_number")
        if isinstance(chapter, int):
            signals.append(f"intake: chapter hint {chapter}")
        location = apply_args.get("location")
        if domain == "timeline" and isinstance(location, str) and location.strip():
            signals.append(f"intake: location {location}")
    mentions = draft.get("character_mentions", [])
    if mentions:
        signals.append(f"intake: characters {', '.join(str(item) for item in mentions[:3])}")
    if item.get("source_issue_code"):
        signals.append(f"consistency: {item.get('source_issue_code')}")
    if domain == "canon":
        if apply_args.get("world_rule_exception_object_phrase") or apply_args.get("world_rule_exception_object_key"):
            subject_name = apply_args.get("world_rule_exception_subject_name") or apply_args.get("world_rule_exception_subject_id") or "角色"
            chapter = apply_args.get("world_rule_exception_reading_chapter")
            object_phrase = apply_args.get("world_rule_exception_object_phrase") or apply_args.get("world_rule_exception_object_key")
            signals.append(f"claim: {subject_name} 第{chapter if isinstance(chapter, int) else '?'}章 知道{object_phrase}")
        elif apply_args.get("knowledge_object_phrase") or apply_args.get("knowledge_object_key"):
            subject_name = apply_args.get("knowledge_subject_name") or apply_args.get("knowledge_subject_id") or "角色"
            chapter = apply_args.get("knowledge_reading_chapter")
            object_phrase = apply_args.get("knowledge_object_phrase") or apply_args.get("knowledge_object_key")
            signals.append(f"claim: {subject_name} 第{chapter if isinstance(chapter, int) else '?'}章 知道{object_phrase}")
        elif report.get("knowledge_claims"):
            claim = report["knowledge_claims"][0]
            signals.append(f"claim: {claim.get('subject_name')} 第{claim.get('chapter')}章 {claim.get('verb')}{claim.get('object_phrase')}")
    if domain == "constraints" and item.get("source_issue_code") == "world-rule-conflict":
        signals.append("consistency: world-rule conflict")
    return signals


def _timeline_summary_from_input(item: dict[str, Any]) -> tuple[str, list[str]]:
    apply_args = item.get("apply_args", {}) if isinstance(item.get("apply_args"), dict) else {}
    strategy = str(item.get("strategy") or "")
    event_label = str(apply_args.get("event_label") or apply_args.get("event_id") or "事件")
    chapter = apply_args.get("reading_chapter")
    location = str(apply_args.get("location") or "").strip()
    participants = [str(participant) for participant in apply_args.get("participant_ids", []) if str(participant).strip()]
    writes: list[str] = [f"event: {event_label}"]
    if isinstance(chapter, int):
        writes.append(f"reading_chapter: {chapter}")
    if location:
        writes.append(f"location: {location}")
    if participants:
        writes.append(f"participants: {', '.join(participants)}")
    if strategy == "update-existing-event":
        summary = f"更新事件 `{apply_args.get('event_id')}` 的时间线挂载，并同步章节 / 地点 / 参与者字段。"
    elif strategy == "resolve-world-rule-by-delaying-event":
        summary = f"把事件 `{event_label}` 延后到第 {chapter} 章，保持原有 rule cutoff 不变。"
    else:
        summary = f"在 `timeline/events.json` 新增或更新事件 `{event_label}`，并挂到第 {chapter or '?'} 章。"
    return summary, writes


def _outline_summary_from_input(item: dict[str, Any]) -> tuple[str, list[str]]:
    apply_args = item.get("apply_args", {}) if isinstance(item.get("apply_args"), dict) else {}
    strategy = str(item.get("strategy") or "")
    scene_title = str(apply_args.get("scene_title") or apply_args.get("scene_id") or "场景")
    chapter = apply_args.get("chapter_number")
    pov = str(apply_args.get("scene_pov") or "").strip()
    event_ids = [str(event_id) for event_id in apply_args.get("scene_event_ids", []) if str(event_id).strip()]
    writes: list[str] = [f"scene: {scene_title}"]
    if isinstance(chapter, int):
        writes.append(f"chapter: {chapter}")
    if pov:
        writes.append(f"pov: {pov}")
    if event_ids:
        writes.append(f"event_ids: {', '.join(event_ids)}")
    if strategy == "update-existing-scene":
        summary = f"更新场景 `{apply_args.get('scene_id')}` 的章节挂载，并同步 POV / 事件关联。"
    else:
        summary = f"在 `outline/scene-index.json` 新增或更新第 {chapter or '?'} 章场景 `{scene_title}`。"
    return summary, writes


def _canon_summary_from_input(item: dict[str, Any], report: dict[str, Any], draft: dict[str, Any]) -> tuple[str, list[str]]:
    apply_args = item.get("apply_args", {}) if isinstance(item.get("apply_args"), dict) else {}
    strategy = str(item.get("strategy") or "")
    if strategy in {"upsert-canon-relationship", "update-existing-relationship"}:
        relationship_id = str(apply_args.get("relationship_id") or "relationship")
        state = str(apply_args.get("relationship_state") or "")
        character_ids = [str(item) for item in apply_args.get("relationship_character_ids", []) if str(item).strip()]
        chapter = apply_args.get("relationship_reading_chapter")
        writes = [
            f"relationship_id: {relationship_id}",
            f"state: {state}",
            f"characters: {', '.join(character_ids)}",
        ]
        if isinstance(chapter, int):
            writes.append(f"reading_chapter: {chapter}")
        summary = f"把关系 `{relationship_id}` 写入 `state/canon-index.json`，同步 pair / state / chapter。"
        return summary, writes
    if strategy in {"upsert-canon-knowledge-state", "update-existing-knowledge-state"}:
        knowledge_state_id = str(apply_args.get("knowledge_state_id") or "knowledge-state")
        subject_name = str(apply_args.get("knowledge_subject_name") or apply_args.get("knowledge_subject_id") or "角色")
        chapter = apply_args.get("knowledge_reading_chapter")
        writes = [
            f"knowledge_state_id: {knowledge_state_id}",
            f"subject: {subject_name}",
            f"object: {apply_args.get('knowledge_object_phrase') or apply_args.get('knowledge_object_key')}",
        ]
        if isinstance(chapter, int):
            writes.append(f"reading_chapter: {chapter}")
        summary = f"把 `{subject_name}` 的知情变化写入 `state/canon-index.json`，作为正式 knowledge-state 事实源。"
        return summary, writes
    if strategy == "document-world-rule-exception" and apply_args.get("world_rule_exception_id"):
        exception_id = str(apply_args.get("world_rule_exception_id") or "world-rule-exception")
        subject_name = str(apply_args.get("world_rule_exception_subject_name") or apply_args.get("world_rule_exception_subject_id") or "角色")
        chapter = apply_args.get("world_rule_exception_reading_chapter")
        writes = [
            f"world_rule_exception_id: {exception_id}",
            f"rule_id: {apply_args.get('rule_id')}",
            f"subject: {subject_name}",
        ]
        if isinstance(chapter, int):
            writes.append(f"reading_chapter: {chapter}")
        summary = f"把规则例外 `{exception_id}` 写入 `state/canon-index.json`，让后续 consistency 直接识别这条正式豁免。"
        return summary, writes

    claims = report.get("knowledge_claims", [])
    if claims:
        claim = claims[0]
        writes = [
            f"knowledge_subject: {claim.get('subject_name')}",
            f"knowledge_chapter: {claim.get('chapter')}",
            f"knowledge_object: {claim.get('object_phrase')}",
        ]
        summary = f"当前没有直接 canon merge input；建议把 `{claim.get('subject_name')}` 的知情变化补进角色或设定说明。"
        return summary, writes

    mentions = [str(item) for item in draft.get("character_mentions", []) if str(item).strip()]
    writes = [f"review_characters: {', '.join(mentions)}"] if mentions else []
    summary = "当前 canon 侧还缺直接结构化写入，建议先确认是否需要新增角色条目、关系节点或正式设定说明。"
    return summary, writes


def _constraints_summary_from_input(item: dict[str, Any]) -> tuple[str, list[str]]:
    apply_args = item.get("apply_args", {}) if isinstance(item.get("apply_args"), dict) else {}
    strategy = str(item.get("strategy") or "")
    rule_id = str(apply_args.get("rule_id") or "rule")
    writes = [f"rule_id: {rule_id}"]
    if apply_args.get("rule_applies_until_event_id"):
        writes.append(f"cutoff_event: {apply_args.get('rule_applies_until_event_id')}")
    if strategy == "resolve-world-rule-by-updating-cutoff":
        summary = f"把约束 `{rule_id}` 的 cutoff 对齐到新事件，直接修改 `constraints/constraints.json`。"
    elif strategy == "document-world-rule-exception":
        summary = f"为约束 `{rule_id}` 追加例外说明，保留原 cutoff 不变。"
    else:
        summary = f"更新约束 `{rule_id}` 的规则字段。"
    return summary, writes


def _world_rule_impacts_for_item(item: dict[str, Any]) -> list[str]:
    strategy = str(item.get("strategy") or "").strip()
    impact_map = {
        "resolve-world-rule-by-delaying-event": [
            "timeline:update-event",
            "outline:update-scene",
        ],
        "resolve-world-rule-by-updating-cutoff": [
            "timeline:update-event",
            "outline:update-scene",
            "constraints:update-cutoff",
        ],
        "document-world-rule-exception": [
            "constraints:note-exception",
            "canon:record-exception",
        ],
    }
    impacts = impact_map.get(strategy)
    if impacts:
        return impacts

    return [
        f"{domain}:review"
        for domain in _target_file_domains([str(path) for path in item.get("target_files", []) if str(path).strip()])
    ]


def _impact_bucket_for_item(item: dict[str, Any]) -> str:
    if item.get("can_apply_directly") and not item.get("requires_override") and not item.get("missing_fields"):
        return "direct"
    return "review"


def _world_rule_subjects_for_item(item: dict[str, Any]) -> list[str]:
    apply_args = item.get("apply_args", {}) if isinstance(item.get("apply_args"), dict) else {}
    primary_subject = (
        apply_args.get("world_rule_exception_subject_name")
        or apply_args.get("rule_subject_name")
        or apply_args.get("world_rule_exception_subject_id")
        or apply_args.get("rule_subject_id")
    )
    text = str(primary_subject or "").strip()
    return [text] if text else []


def _world_rule_subject_scope(rule_subjects: set[str], all_subjects: set[str]) -> str:
    normalized_rule_subjects = {str(subject).strip() for subject in rule_subjects if str(subject).strip()}
    normalized_all_subjects = {str(subject).strip() for subject in all_subjects if str(subject).strip()}
    if not normalized_rule_subjects:
        return "review-subject"
    if len(normalized_rule_subjects) > 1:
        return "mixed-subjects"
    if len(normalized_all_subjects) <= 1:
        return "shared-subject"
    return "split-subjects"


def _split_world_rule_exemption_scope(scope: str) -> tuple[str, str, str]:
    parts = [part.strip() for part in str(scope or "").split("-") if part.strip()]
    if len(parts) >= 5:
        return "-".join(parts[:2]), "-".join(parts[2:4]), "-".join(parts[4:])
    if len(parts) >= 3:
        return parts[0], parts[1], "-".join(parts[2:])
    return str(scope or "").strip(), "", ""


def _world_rule_exemption_bucket(exception_scopes: set[str]) -> str:
    normalized_scopes = {str(scope).strip() for scope in exception_scopes if str(scope).strip()}
    if normalized_scopes and all(
        _split_world_rule_exemption_scope(scope) == ("same-chapter", "shared-subject", "claim-match")
        for scope in normalized_scopes
    ):
        return "direct"
    return "review"


def _draft_domains_for_exemption_review(draft: dict[str, Any]) -> set[str]:
    domains = {
        str(item).strip()
        for item in draft.get("suggested_domains", [])
        if str(item).strip()
    }
    if not domains:
        kind = str(draft.get("kind") or "").strip().lower()
        domains.update(KIND_DOMAIN_MAP.get(kind, []))
    return domains


def _constraints_group_explainer(items: list[dict[str, Any]], report: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any] | None:
    world_rule_items = [
        item
        for item in items
        if str(item.get("source_issue_code") or "") == "world-rule-conflict"
    ]
    strategies_by_rule: dict[str, list[str]] = {}
    targets_by_rule: dict[str, set[str]] = {}
    domains_by_rule: dict[str, set[str]] = {}
    impacts_by_rule: dict[str, set[str]] = {}
    direct_impacts_by_rule: dict[str, set[str]] = {}
    review_impacts_by_rule: dict[str, set[str]] = {}
    subjects_by_rule: dict[str, set[str]] = {}
    direct_by_rule: dict[str, int] = {}
    override_by_rule: dict[str, int] = {}
    all_targets: set[str] = set()
    for item in world_rule_items:
        apply_args = item.get("apply_args", {}) if isinstance(item.get("apply_args"), dict) else {}
        rule_id = str(apply_args.get("rule_id") or "").strip()
        strategy = str(item.get("strategy") or "").strip()
        if not rule_id or not strategy:
            continue
        strategies_by_rule.setdefault(rule_id, [])
        if strategy not in strategies_by_rule[rule_id]:
            strategies_by_rule[rule_id].append(strategy)
        targets = {str(path) for path in item.get("target_files", []) if str(path).strip()}
        all_targets.update(targets)
        targets_by_rule.setdefault(rule_id, set()).update(targets)
        domains_by_rule.setdefault(rule_id, set()).update(_target_file_domains(item.get("target_files", [])))
        impacts = _world_rule_impacts_for_item(item)
        impacts_by_rule.setdefault(rule_id, set()).update(impacts)
        subjects_by_rule.setdefault(rule_id, set()).update(_world_rule_subjects_for_item(item))
        if _impact_bucket_for_item(item) == "direct":
            direct_impacts_by_rule.setdefault(rule_id, set()).update(impacts)
        else:
            review_impacts_by_rule.setdefault(rule_id, set()).update(impacts)
        if item.get("can_apply_directly"):
            direct_by_rule[rule_id] = direct_by_rule.get(rule_id, 0) + 1
        if item.get("requires_override"):
            override_by_rule[rule_id] = override_by_rule.get(rule_id, 0) + 1

    exemptions = [
        item
        for item in report.get("exemptions", [])
        if str(item.get("code") or "") == "world-rule-exemption-applied"
    ]
    exception_ids_by_rule: dict[str, set[str]] = {}
    exception_scopes_by_rule: dict[str, set[str]] = {}
    exemption_direct_by_rule: dict[str, int] = {}
    exemption_review_by_rule: dict[str, int] = {}
    for item in exemptions:
        details = item.get("details", {}) if isinstance(item.get("details"), dict) else {}
        rule_id = str(details.get("rule_id") or "").strip()
        if not rule_id:
            continue
        subject = str(details.get("matched_exception_subject_name") or details.get("rule_subject") or "").strip()
        if subject:
            subjects_by_rule.setdefault(rule_id, set()).add(subject)
        scope = str(details.get("exception_scope") or "").strip()
        if scope:
            exception_scopes_by_rule.setdefault(rule_id, set()).add(scope)
        exception_id = str(details.get("matched_exception_id") or "").strip()
        if exception_id:
            exception_ids_by_rule.setdefault(rule_id, set()).add(exception_id)
        targets_by_rule.setdefault(rule_id, set()).update({"state/canon-index.json", "constraints/constraints.json", "canon/world-rules.md"})
        domains_by_rule.setdefault(rule_id, set()).update({"canon", "constraints"})
        impacts_by_rule.setdefault(rule_id, set()).update({"canon:reuse-exception", "constraints:reuse-exception"})

    all_subjects = {
        subject
        for subjects in subjects_by_rule.values()
        for subject in subjects
        if str(subject).strip()
    }
    all_subjects.update(
        str(item).strip()
        for item in draft.get("character_mentions", [])
        if str(item).strip()
    )
    conflict_rule_ids = sorted(strategies_by_rule.keys())
    exemption_rule_ids = sorted(exception_ids_by_rule.keys() | exception_scopes_by_rule.keys())
    rule_ids = sorted(set(conflict_rule_ids) | set(exemption_rule_ids))
    if not rule_ids:
        return None
    if len(conflict_rule_ids) < 2 and not exemption_rule_ids:
        return None

    all_targets: set[str] = set()
    planned_writes: list[str] = []
    overall_readiness = "ready"
    for rule_id in rule_ids:
        all_targets.update(targets_by_rule.get(rule_id, set()))
        subject_scope = _world_rule_subject_scope(subjects_by_rule.get(rule_id, set()), all_subjects)
        if rule_id in conflict_rule_ids:
            line = (
                f"{rule_id}: "
                f"{', '.join(strategies_by_rule.get(rule_id, [])) or 'review'}"
                f" | direct={direct_by_rule.get(rule_id, 0)}"
                f" | override={override_by_rule.get(rule_id, 0)}"
                f" | subjects={', '.join(sorted(subjects_by_rule.get(rule_id, set())))}"
                f" | subject_scope={subject_scope}"
                f" | domains={', '.join(sorted(domains_by_rule.get(rule_id, set())))}"
                f" | impacts={', '.join(sorted(impacts_by_rule.get(rule_id, set())))}"
                f" | direct_impacts={', '.join(sorted(direct_impacts_by_rule.get(rule_id, set())))}"
                f" | review_impacts={', '.join(sorted(review_impacts_by_rule.get(rule_id, set())))}"
                f" | targets={', '.join(sorted(targets_by_rule.get(rule_id, set())))}"
            )
            planned_writes.append(line)
            overall_readiness = "needs-review"
            continue

        exception_scopes = exception_scopes_by_rule.get(rule_id, set())
        reuse_bucket = _world_rule_exemption_bucket(exception_scopes)
        exception_scope_bases = {
            base_scope
            for base_scope, _, _ in (_split_world_rule_exemption_scope(scope) for scope in exception_scopes)
            if base_scope
        }
        exception_subject_scopes = {
            token_subject_scope
            for _, token_subject_scope, _ in (_split_world_rule_exemption_scope(scope) for scope in exception_scopes)
            if token_subject_scope
        }
        exception_match_modes = {
            match_mode
            for _, _, match_mode in (_split_world_rule_exemption_scope(scope) for scope in exception_scopes)
            if match_mode
        }
        if reuse_bucket == "direct":
            exemption_direct_by_rule[rule_id] = 1
            direct_impacts_by_rule.setdefault(rule_id, set()).update({"canon:reuse-exception", "constraints:reuse-exception"})
        else:
            exemption_review_by_rule[rule_id] = 1
            review_impacts = {"canon:reuse-exception", "constraints:reuse-exception"}
            if "prior-exception" in exception_scope_bases:
                review_impacts.update(
                    {
                        "canon:review-exception-continuity",
                        "constraints:review-exception-chain",
                        "timeline:review-post-exception-beat",
                        "outline:review-post-exception-scene",
                    }
                )
                targets_by_rule.setdefault(rule_id, set()).update({"timeline/events.json", "outline/scene-index.json"})
                exemption_review_domains = _draft_domains_for_exemption_review(draft)
                domains_by_rule.setdefault(rule_id, set()).update({"timeline", "outline"} & exemption_review_domains or {"timeline", "outline"})
            if any(scope in {"split-subjects", "mixed-subjects", "review-subject"} for scope in exception_subject_scopes):
                review_impacts.add("constraints:review-subject-scope")
            if "local-signal" in exception_match_modes:
                review_impacts.add("canon:review-exception-evidence")
            review_impacts_by_rule.setdefault(rule_id, set()).update(review_impacts)
            overall_readiness = "needs-review"
        line = (
            f"{rule_id}: "
            f"reuse-existing-exception"
            f" | direct={exemption_direct_by_rule.get(rule_id, 0)}"
            f" | review={exemption_review_by_rule.get(rule_id, 0)}"
            f" | exceptions={', '.join(sorted(exception_ids_by_rule.get(rule_id, set()))) or 'existing'}"
            f" | subjects={', '.join(sorted(subjects_by_rule.get(rule_id, set())))}"
            f" | subject_scope={subject_scope}"
            f" | exception_scope={', '.join(sorted(exception_scopes))}"
            f" | exception_scope_base={', '.join(sorted(exception_scope_bases))}"
            f" | exception_subject_scope={', '.join(sorted(exception_subject_scopes))}"
            f" | exception_match_mode={', '.join(sorted(exception_match_modes))}"
            f" | domains={', '.join(sorted(domains_by_rule.get(rule_id, set())))}"
            f" | impacts={', '.join(sorted(impacts_by_rule.get(rule_id, set())))}"
            f" | direct_impacts={', '.join(sorted(direct_impacts_by_rule.get(rule_id, set())))}"
            f" | review_impacts={', '.join(sorted(review_impacts_by_rule.get(rule_id, set())))}"
            f" | targets={', '.join(sorted(targets_by_rule.get(rule_id, set())))}"
        )
        planned_writes.append(line)

    if conflict_rule_ids and exemption_rule_ids:
        summary = f"当前这条 idea 涉及 {len(rule_ids)} 条 world-rule；其中 {len(conflict_rule_ids)} 条仍需处理，{len(exemption_rule_ids)} 条已有正式 exception 覆盖。"
        action = "先按 rule 分组复核 constraints 层的冲突与豁免状态。"
    elif conflict_rule_ids:
        summary = f"当前这条 idea 同时触发了 {len(rule_ids)} 条 world-rule；先按 rule 分组复核各自的 cutoff / exception 处理策略。"
        action = "先按 rule 分组复核 constraints 层的冲突与处理方向。"
    else:
        summary = f"这条 idea 命中的 {len(rule_ids)} 条 world-rule 已有正式 exception 覆盖；优先沿用既有解释链，并只复核需要人工确认的主体范围。"
        action = "复核已落地的 world-rule exception。"

    source_signals: list[str] = []
    if conflict_rule_ids:
        source_signals.append(f"consistency: world-rule conflict x{len(conflict_rule_ids)}")
    if exemption_rule_ids:
        source_signals.append(f"consistency: world-rule exemptions x{len(exemption_rule_ids)}")
    return {
        "domain": "constraints",
        "action": action,
        "summary": summary,
        "target_files": sorted(all_targets),
        "reason": summary,
        "confidence": "high",
        "merge_input_id": None,
        "readiness": overall_readiness,
        "planned_writes": planned_writes,
        "source_signals": source_signals,
    }


def _readiness_rank(value: Any) -> int:
    order = {
        "ready": 4,
        "needs-review": 3,
        "planned": 2,
        "needs-info": 1,
        "blocked-by-gate": 0,
    }
    return order.get(str(value or ""), -1)


def _dedupe_domain_explainers(explainers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    index_by_key: dict[tuple[str, str, tuple[str, ...]], int] = {}

    for explainer in explainers:
        explainer = {**explainer, "_duplicate_count": int(explainer.get("_duplicate_count") or 1)}
        key = (
            str(explainer.get("domain") or ""),
            str(explainer.get("summary") or ""),
            tuple(str(item) for item in explainer.get("planned_writes", [])),
        )
        existing_index = index_by_key.get(key)
        if existing_index is None:
            index_by_key[key] = len(deduped)
            deduped.append(explainer)
            continue

        current = deduped[existing_index]
        preferred, secondary = (
            (explainer, current)
            if _readiness_rank(explainer.get("readiness")) > _readiness_rank(current.get("readiness"))
            else (current, explainer)
        )
        merged = dict(preferred)
        merged["target_files"] = sorted(
            {
                str(item)
                for item in [*current.get("target_files", []), *explainer.get("target_files", [])]
                if str(item).strip()
            }
        )
        merged["source_signals"] = list(
            dict.fromkeys(
                str(item)
                for item in [*current.get("source_signals", []), *explainer.get("source_signals", [])]
                if str(item).strip()
            )
        )
        merged["missing_fields"] = sorted(
            {
                str(item)
                for item in [*current.get("missing_fields", []), *explainer.get("missing_fields", [])]
                if str(item).strip()
            }
        )
        merged["_duplicate_count"] = int(current.get("_duplicate_count") or 1) + int(explainer.get("_duplicate_count") or 1)
        merge_input_ids = {
            str(item.get("merge_input_id"))
            for item in (current, explainer)
            if item.get("merge_input_id") is not None
        }
        merged["merge_input_id"] = next(iter(merge_input_ids)) if merged["_duplicate_count"] == 1 and len(merge_input_ids) == 1 else None
        merged["confidence"] = preferred.get("confidence") or secondary.get("confidence")
        deduped[existing_index] = merged

    return [{key: value for key, value in item.items() if key != "_duplicate_count"} for item in deduped]


def _fallback_domain_summary(domain: str, idea: dict[str, Any], draft: dict[str, Any], report: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    kind = str(idea.get("kind", "misc"))
    if domain == "canon":
        mentions = [str(item) for item in draft.get("character_mentions", []) if str(item).strip()]
        if kind in {"reveal", "twist", "backstory"}:
            summary = f"复核这条 `{kind}` 想法带来的人物认知变化，决定是否补进正式设定层。"
        else:
            summary = f"复核这条 `{kind}` 想法是否需要写入正式设定层，而不是只停留在 timeline / outline。"
        if mentions:
            writes = [f"character_mentions: {', '.join(mentions)}"]
        elif kind in {"reveal", "twist", "backstory"}:
            writes = [f"review_knowledge_shift: {str(idea.get('title') or idea.get('content') or 'idea').strip()}"]
        else:
            writes = []
        signals = [f"intake: characters {', '.join(mentions[:3])}"] if mentions else []
        return summary, writes, signals
    if domain == "outline":
        chapters = [str(item) for item in draft.get("chapter_hints", [])]
        summary = f"确认这条 `{kind}` 想法具体落到哪一章、哪个 scene，再决定是否写入 `outline/scene-index.json`。"
        writes = [f"chapter_hints: {', '.join(chapters)}"] if chapters else []
        signals = [f"intake: chapter hints {', '.join(chapters)}"] if chapters else []
        return summary, writes, signals
    summary = f"把这条 `{kind}` 想法落成正式事件，再补章节、地点和参与者。"
    writes = []
    signals = []
    return summary, writes, signals


def _domain_explainers(
    workspace: Path,
    idea: dict[str, Any],
    domains: list[str],
    gate: dict[str, Any],
    draft: dict[str, Any],
    report: dict[str, Any],
    timeline_merge_inputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    explainers: list[dict[str, Any]] = []
    if gate["status"] in {"missing", "stale"}:
        explainers.append(
            {
                "domain": "gate",
                "action": "先运行或重跑 consistency check。",
                "summary": gate["summary"],
                "target_files": ["state/consistency-checks", "views/consistency-checks"],
                "reason": gate["summary"],
                "confidence": "high",
                "merge_input_id": None,
                "readiness": "blocked-by-gate",
                "planned_writes": [],
                "source_signals": [],
            }
        )
    elif gate["status"] == "blocked":
        explainers.append(
            {
                "domain": "gate",
                "action": "先处理 consistency blockers，再决定如何 merge。",
                "summary": gate["summary"],
                "target_files": ["state/consistency-checks", "views/consistency-checks"],
                "reason": gate["summary"],
                "confidence": "high",
                "merge_input_id": None,
                "readiness": "blocked-by-gate",
                "planned_writes": [],
                "source_signals": [f"blockers: {len(gate.get('blockers', []))}"],
            }
        )

    constraints_group_explainer = _constraints_group_explainer(timeline_merge_inputs, report, draft)
    if constraints_group_explainer is not None:
        explainers.append(constraints_group_explainer)

    covered_domains: set[str] = set()
    for item in timeline_merge_inputs:
        for domain in _target_file_domains(item.get("target_files", [])):
            covered_domains.add(domain)
            if domain == "timeline":
                summary, planned_writes = _timeline_summary_from_input(item)
            elif domain == "outline":
                summary, planned_writes = _outline_summary_from_input(item)
            elif domain == "canon":
                summary, planned_writes = _canon_summary_from_input(item, report, draft)
            else:
                summary, planned_writes = _constraints_summary_from_input(item)
            explainers.append(
                {
                    "domain": domain,
                    "action": f"处理 {domain} 层的具体写入。",
                    "summary": summary,
                    "target_files": item.get("target_files", []),
                    "reason": summary,
                    "confidence": "medium" if item.get("missing_fields") else "high",
                    "merge_input_id": item.get("id"),
                    "readiness": _readiness_for_input(item, gate),
                    "planned_writes": planned_writes,
                    "source_signals": _source_signals_for_input(domain, item, draft, report),
                    "missing_fields": item.get("missing_fields", []),
                }
            )

    for domain in sorted(set(domains) - covered_domains):
        summary, planned_writes, source_signals = _fallback_domain_summary(domain, idea, draft, report)
        explainers.append(
            {
                "domain": domain,
                "action": f"复核 {domain} 层的补写需求。",
                "summary": summary,
                "target_files": DOMAIN_TARGET_FILES[domain],
                "reason": summary,
                "confidence": "medium",
                "merge_input_id": None,
                "readiness": "planned" if gate.get("can_plan_merge") else "blocked-by-gate",
                "planned_writes": planned_writes,
                "source_signals": source_signals,
            }
        )
    return _dedupe_domain_explainers(explainers)


def _consistency_gate(workspace: Path, idea: dict[str, Any]) -> dict[str, Any]:
    report = load_consistency_report(workspace, str(idea.get("id")))
    if report is None:
        return {
            "status": "missing",
            "can_plan_merge": False,
            "can_apply_merge": False,
            "summary": "这条 idea 还没有 consistency report。",
            "report_path": None,
            "view_path": None,
            "blockers": ["先运行 idea-level consistency check，再决定 merge。"],
            "warnings": [],
        }
    if consistency_report_needs_refresh(workspace, idea):
        return {
            "status": "stale",
            "can_plan_merge": False,
            "can_apply_merge": False,
            "summary": "已有 consistency report，但它落后于当前 idea 内容，需要重跑。",
            "report_path": report.get("report_path"),
            "view_path": report.get("view_path"),
            "blockers": ["当前 consistency report 已过期，需要重跑后再做 merge。"],
            "warnings": [],
        }

    blockers = [
        issue.get("message")
        for issue in report.get("issues", [])
        if issue.get("level") == "error" or str(issue.get("code", "")).endswith("-conflict")
    ]
    warnings = [
        issue.get("message")
        for issue in report.get("issues", [])
        if issue.get("level") == "warning" and not str(issue.get("code", "")).endswith("-conflict")
    ]
    if blockers:
        return {
            "status": "blocked",
            "can_plan_merge": True,
            "can_apply_merge": False,
            "summary": "consistency report 已生成，但仍有 conflicts / errors，当前不应直接 apply merge。",
            "report_path": report.get("report_path"),
            "view_path": report.get("view_path"),
            "blockers": blockers,
            "warnings": warnings,
        }
    if warnings:
        return {
            "status": "warning",
            "can_plan_merge": True,
            "can_apply_merge": True,
            "summary": "consistency report 没有硬 conflicts，但仍有 warning，merge 前需要人工确认。",
            "report_path": report.get("report_path"),
            "view_path": report.get("view_path"),
            "blockers": [],
            "warnings": warnings,
        }
    return {
        "status": "clear",
        "can_plan_merge": True,
        "can_apply_merge": True,
        "summary": "consistency gate 已通过，可以进入 merge planning / apply。",
        "report_path": report.get("report_path"),
        "view_path": report.get("view_path"),
        "blockers": [],
        "warnings": [],
    }


def _load_intake_draft(workspace: Path, idea_id: str) -> dict[str, Any]:
    draft = read_json(workspace / "state/intake-drafts" / f"{idea_id}.json", {})
    return draft if isinstance(draft, dict) else {}


def _load_intake_draft_summary(workspace: Path, idea_id: str) -> dict[str, Any]:
    draft = _load_intake_draft(workspace, idea_id)
    return {
        "chapter_hints": draft.get("chapter_hints", []),
        "location_candidates": draft.get("location_candidates", []),
        "character_mentions": draft.get("character_mentions", []),
        "suggested_domains": draft.get("suggested_domains", []),
        "confidence": draft.get("confidence"),
    }


def _normalize_token(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    normalized = re.sub(r"\s+", "", normalized)
    return normalized


def _first_int(items: list[Any]) -> int | None:
    return next((item for item in items if isinstance(item, int)), None)


def _first_text(items: list[Any]) -> str | None:
    return next((str(item).strip() for item in items if str(item).strip()), None)


def _character_lookup(canon_index: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    token_to_id: dict[str, str] = {}
    id_to_name: dict[str, str] = {}
    for item in canon_index.get("characters", []):
        char_id = str(item.get("id") or "").strip()
        if not char_id:
            continue
        display_name = str(item.get("name") or char_id)
        id_to_name[char_id] = display_name
        for token in [char_id, display_name, *item.get("aliases", [])]:
            normalized = _normalize_token(token)
            if normalized:
                token_to_id[normalized] = char_id
    return token_to_id, id_to_name


def _resolve_participant_ids(draft: dict[str, Any], canon_index: dict[str, Any]) -> list[str]:
    token_to_id, _ = _character_lookup(canon_index)
    output: list[str] = []
    for mention in draft.get("character_mentions", []):
        char_id = token_to_id.get(_normalize_token(mention))
        if char_id and char_id not in output:
            output.append(char_id)
    return output


def _event_records(workspace: Path) -> list[dict[str, Any]]:
    data = read_json(workspace / "timeline/events.json", {"events": []})
    return data.get("events", []) if isinstance(data, dict) else []


def _scene_records(workspace: Path) -> list[dict[str, Any]]:
    scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
    output: list[dict[str, Any]] = []
    for chapter in scene_index.get("chapters", []):
        chapter_number = chapter.get("chapter")
        for scene in chapter.get("scenes", []):
            output.append({"chapter": chapter_number, "scene": scene})
    return output


def _event_by_id(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(event.get("id")): event for event in events if event.get("id")}


def _scene_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for record in records:
        scene = record.get("scene", {})
        scene_id = scene.get("id")
        if scene_id:
            output[str(scene_id)] = record
    return output


def _suggest_chronological_index(events: list[dict[str, Any]], preferred: int | None) -> int:
    used = {
        item.get("chronological_index")
        for item in events
        if isinstance(item.get("chronological_index"), int)
    }
    if isinstance(preferred, int):
        candidate = preferred
    else:
        candidate = (max(used) if used else 0) + 1
    while candidate in used:
        candidate += 1
    return candidate


def _relationship_state_from_text(text: str) -> str | None:
    for token, state in RELATIONSHIP_STATE_MAP.items():
        if token in str(text or ""):
            return state
    return None


def _relationship_state_label(state: str | None) -> str:
    return RELATIONSHIP_STATE_LABELS.get(str(state or ""), str(state or "关系"))


def _relationship_record_id(character_ids: list[str], relationship_state: str, reading_chapter: int | None) -> str:
    pair = "-".join(sorted(character_ids))
    chapter_suffix = f"-ch{reading_chapter}" if isinstance(reading_chapter, int) else ""
    return f"rel-{pair}-{relationship_state}{chapter_suffix}"


def _relationship_records(canon_index: dict[str, Any], character_ids: list[str]) -> list[dict[str, Any]]:
    target = sorted(character_ids)
    records = [
        item
        for item in canon_index.get("relationships", [])
        if sorted(str(value) for value in item.get("character_ids", [])) == target
    ]
    records.sort(
        key=lambda item: (
            item.get("reading_chapter") if isinstance(item.get("reading_chapter"), int) else 10**9,
            str(item.get("id", "")),
        )
    )
    return records


def _has_intervening_relationship_state(
    records: list[dict[str, Any]],
    *,
    from_chapter: int,
    to_chapter: int,
    relationship_state: str,
) -> bool:
    return any(
        from_chapter < int(item.get("reading_chapter")) < to_chapter and str(item.get("state")) != relationship_state
        for item in records
        if isinstance(item.get("reading_chapter"), int)
    )


def _existing_relationship_match(
    canon_index: dict[str, Any],
    character_ids: list[str],
    relationship_state: str,
    reading_chapter: int | None,
) -> dict[str, Any] | None:
    records = _relationship_records(canon_index, character_ids)
    if not records:
        return None
    exact = next(
        (
            item
            for item in records
            if str(item.get("state")) == relationship_state and item.get("reading_chapter") == reading_chapter
        ),
        None,
    )
    if exact is not None:
        return exact
    if not isinstance(reading_chapter, int):
        return None
    prior_same = [
        item
        for item in records
        if str(item.get("state")) == relationship_state and isinstance(item.get("reading_chapter"), int) and int(item.get("reading_chapter")) < reading_chapter
    ]
    if prior_same:
        latest_prior = prior_same[-1]
        latest_chapter = int(latest_prior.get("reading_chapter"))
        if not _has_intervening_relationship_state(records, from_chapter=latest_chapter, to_chapter=reading_chapter, relationship_state=relationship_state):
            return latest_prior
    future_same = [
        item
        for item in records
        if str(item.get("state")) == relationship_state and isinstance(item.get("reading_chapter"), int) and int(item.get("reading_chapter")) > reading_chapter
    ]
    if future_same:
        return future_same[0]
    return None


def _knowledge_state_record_id(subject_id: str, object_key: str, reading_chapter: int | None) -> str:
    chapter_suffix = f"-ch{reading_chapter}" if isinstance(reading_chapter, int) else ""
    return f"know-{subject_id}-{slugify(object_key)}{chapter_suffix}"


def _knowledge_state_records(canon_index: dict[str, Any], subject_id: str) -> list[dict[str, Any]]:
    records = [
        item
        for item in canon_index.get("knowledge_states", [])
        if str(item.get("subject_id") or "").strip() == subject_id
    ]
    records.sort(
        key=lambda item: (
            item.get("reading_chapter") if isinstance(item.get("reading_chapter"), int) else 10**9,
            str(item.get("id", "")),
        )
    )
    return records


def _existing_knowledge_state_match(canon_index: dict[str, Any], subject_id: str, object_key: str) -> dict[str, Any] | None:
    for item in _knowledge_state_records(canon_index, subject_id):
        if str(item.get("object_key") or "").strip() == object_key:
            return item
    return None


def _world_rule_exception_record_id(rule_id: str, subject_key: str, object_key: str, reading_chapter: int | None) -> str:
    chapter_suffix = f"-ch{reading_chapter}" if isinstance(reading_chapter, int) else ""
    return f"rulex-{slugify(rule_id)}-{slugify(subject_key or 'subject')}-{slugify(object_key or 'exception')}{chapter_suffix}"


def _default_timeline_apply_args(
    workspace: Path,
    idea: dict[str, Any],
    draft: dict[str, Any],
    domains: list[str],
) -> tuple[dict[str, Any], list[str], list[str]]:
    canon_index = read_json(workspace / "state/canon-index.json", default_canon_index(workspace.name))
    events = _event_records(workspace)
    participant_ids = _resolve_participant_ids(draft, canon_index)
    _, id_to_name = _character_lookup(canon_index)

    chapter_hint = _first_int(draft.get("chapter_hints", []))
    location = _first_text(draft.get("location_candidates", []))
    timeline_candidate = next((item for item in draft.get("timeline_candidates", []) if isinstance(item, dict)), {})
    outline_candidate = next((item for item in draft.get("outline_candidates", []) if isinstance(item, dict)), {})
    event_label = str(timeline_candidate.get("event_label") or idea.get("title") or "").strip()
    scene_title = str(outline_candidate.get("scene_title") or idea.get("title") or "").strip()
    event_id = f"event-{slugify(event_label)}" if event_label else None
    scene_id = f"scene-{slugify(scene_title)}" if scene_title else None
    scene_pov = id_to_name.get(participant_ids[0]) if participant_ids else _first_text(draft.get("character_mentions", []))

    apply_args: dict[str, Any] = {}
    target_files: list[str] = []
    missing_fields: list[str] = []

    if "timeline" in domains:
        if not event_label:
            missing_fields.append("event_label")
        apply_args.update(
            {
                "event_id": event_id,
                "event_label": event_label,
                "chronological_index": _suggest_chronological_index(events, chapter_hint),
                "reading_chapter": chapter_hint,
                "location": location,
                "participant_ids": participant_ids,
                "event_notes": idea.get("content", ""),
            }
        )
        target_files.append("timeline/events.json")
        if chapter_hint is None:
            missing_fields.append("reading_chapter")
        if not participant_ids:
            missing_fields.append("participant_ids")

    if "outline" in domains and scene_title:
        apply_args.update(
            {
                "chapter_number": chapter_hint,
                "scene_id": scene_id,
                "scene_title": scene_title,
                "scene_pov": scene_pov,
                "scene_status": "planned",
                "scene_character_ids": participant_ids,
                "scene_event_ids": [event_id] if event_id else [],
                "scene_notes": idea.get("content", ""),
            }
        )
        target_files.extend(["outline/scene-index.json", "outline/master-outline.md"])
        if chapter_hint is None:
            missing_fields.append("chapter_number")

    seen_targets: set[str] = set()
    deduped_targets: list[str] = []
    for path in target_files:
        if path not in seen_targets:
            seen_targets.add(path)
            deduped_targets.append(path)
    return apply_args, deduped_targets, sorted(set(missing_fields))


def _build_default_timeline_merge_input(
    workspace: Path,
    idea: dict[str, Any],
    draft: dict[str, Any],
    domains: list[str],
    gate: dict[str, Any],
) -> dict[str, Any] | None:
    if "timeline" not in domains and "outline" not in domains:
        return None
    apply_args, target_files, missing_fields = _default_timeline_apply_args(workspace, idea, draft, domains)
    chapter_hint = _first_int(draft.get("chapter_hints", []))
    summary = f"为 idea `{idea.get('title')}` 生成默认 timeline merge 输入。"
    if chapter_hint is not None:
        summary = f"建议把 `{idea.get('title')}` 作为第 {chapter_hint} 章的事件/场景并入。"
    return {
        "id": "timeline-merge-001",
        "kind": "timeline-merge-input",
        "strategy": "create-event-and-scene",
        "summary": summary,
        "target_files": target_files,
        "source_issue_code": None,
        "source_patch_suggestion_ids": [],
        "missing_fields": missing_fields,
        "can_apply_directly": gate.get("can_apply_merge", False) and not missing_fields,
        "requires_override": False,
        "warnings": list(gate.get("warnings", [])),
        "resolution_note_suggestion": f"把 `{idea.get('title')}` 并入 timeline / outline，并同步视图。",
        "apply_args": apply_args,
    }


def _build_default_relationship_merge_input(
    workspace: Path,
    idea: dict[str, Any],
    draft: dict[str, Any],
    gate: dict[str, Any],
) -> dict[str, Any] | None:
    canon_index = read_json(workspace / "state/canon-index.json", default_canon_index(workspace.name))
    participant_ids = _resolve_participant_ids(draft, canon_index)
    relationship_state = _relationship_state_from_text(f"{idea.get('title', '')}\n{draft.get('content', '')}")
    reading_chapter = _first_int(draft.get("chapter_hints", []))
    if idea.get("kind") != "relationship" and relationship_state is None:
        return None
    relationship_state = relationship_state or "acquainted"
    existing_relationship = (
        _existing_relationship_match(canon_index, participant_ids, relationship_state, reading_chapter)
        if len(participant_ids) >= 2
        else None
    )
    relationship_id = (
        str(existing_relationship.get("id"))
        if existing_relationship and existing_relationship.get("id")
        else _relationship_record_id(participant_ids, relationship_state, reading_chapter)
        if len(participant_ids) >= 2
        else None
    )
    missing_fields: list[str] = []
    if len(participant_ids) < 2:
        missing_fields.append("relationship_character_ids")
    if reading_chapter is None:
        missing_fields.append("relationship_reading_chapter")
    apply_args = {
        "relationship_id": relationship_id,
        "relationship_character_ids": participant_ids,
        "relationship_state": relationship_state,
        "relationship_reading_chapter": reading_chapter,
        "relationship_event_id": None,
        "relationship_notes": idea.get("content", ""),
    }
    return {
        "id": "timeline-merge-rel-001",
        "kind": "timeline-merge-input",
        "strategy": "update-existing-relationship" if existing_relationship else "upsert-canon-relationship",
        "summary": (
            f"更新现有关系 `{relationship_id}`，把 `{idea.get('title')}` 的状态 `{_relationship_state_label(relationship_state)}` 同步到 canon。"
            if existing_relationship
            else f"把 `{idea.get('title')}` 的关系状态 `{_relationship_state_label(relationship_state)}` 写入 canon。"
        ),
        "target_files": ["state/canon-index.json", "canon/characters.md"],
        "source_issue_code": None,
        "source_patch_suggestion_ids": [],
        "missing_fields": missing_fields,
        "can_apply_directly": gate.get("can_apply_merge", False) and not missing_fields,
        "requires_override": False,
        "warnings": list(gate.get("warnings", [])),
        "resolution_note_suggestion": f"把 `{idea.get('title')}` 的关系状态写入 canon。",
        "apply_args": apply_args,
    }


def _build_default_knowledge_merge_input(
    workspace: Path,
    idea: dict[str, Any],
    report: dict[str, Any],
    gate: dict[str, Any],
) -> dict[str, Any] | None:
    if any(str(issue.get("code") or "") == "knowledge-state-conflict" for issue in report.get("issues", [])):
        return None
    claims = report.get("knowledge_claims", [])
    if not claims or idea.get("kind") not in {"reveal", "twist", "backstory"}:
        return None
    claim = next((item for item in claims if item.get("subject_id") and item.get("object_key")), None)
    if claim is None:
        return None
    canon_index = read_json(workspace / "state/canon-index.json", default_canon_index(workspace.name))
    subject_id = str(claim.get("subject_id") or "").strip()
    object_key = str(claim.get("object_key") or "").strip()
    existing_state = _existing_knowledge_state_match(canon_index, subject_id, object_key)
    chapter = claim.get("chapter")
    knowledge_state_id = (
        str(existing_state.get("id"))
        if existing_state and existing_state.get("id")
        else _knowledge_state_record_id(subject_id, object_key, chapter if isinstance(chapter, int) else None)
    )
    missing_fields: list[str] = []
    if not isinstance(chapter, int):
        missing_fields.append("knowledge_reading_chapter")
    return {
        "id": "timeline-merge-know-001",
        "kind": "timeline-merge-input",
        "strategy": "update-existing-knowledge-state" if existing_state else "upsert-canon-knowledge-state",
        "summary": f"把 `{claim.get('subject_name')}` 关于 `{claim.get('object_phrase')}` 的知情变化补进 canon 机器真相源。",
        "target_files": ["state/canon-index.json", "canon/characters.md"],
        "source_issue_code": None,
        "source_patch_suggestion_ids": [],
        "missing_fields": missing_fields,
        "can_apply_directly": gate.get("can_apply_merge", False) and not missing_fields,
        "requires_override": False,
        "warnings": list(gate.get("warnings", [])),
        "resolution_note_suggestion": f"把 `{claim.get('subject_name')}` 的知情变化写入 canon。",
        "apply_args": {
            "knowledge_state_id": knowledge_state_id,
            "knowledge_subject_id": subject_id,
            "knowledge_subject_name": claim.get("subject_name"),
            "knowledge_object_key": object_key,
            "knowledge_object_phrase": claim.get("object_phrase"),
            "knowledge_verb": claim.get("verb"),
            "knowledge_reading_chapter": chapter if isinstance(chapter, int) else None,
            "knowledge_event_id": None,
            "knowledge_notes": idea.get("content", ""),
        },
    }


def _summary_for_issue_input(issue: dict[str, Any], issue_code: str, record_id: str | None) -> str:
    details = issue.get("details", {}) if isinstance(issue.get("details"), dict) else {}
    if issue_code == "knowledge-state-conflict":
        return (
            f"更新 `{record_id}` 的知情节点章节到第 {details.get('draft_chapter')} 章，"
            f"并同步相关 timeline / outline 记录。"
        )
    if issue_code == "timeline-order-conflict":
        return f"更新 `{record_id}` 的章节挂载，从第 {details.get('existing_chapter')} 章调整到第 {details.get('draft_chapter')} 章。"
    if issue_code == "location-continuity-conflict":
        return f"更新 `{record_id}` 的地点字段，统一为 `{details.get('draft_location')}`。"
    return str(issue.get("message") or "复核这条 merge 输入。")


def _patch_suggestion_ids(report: dict[str, Any], issue_code: str) -> list[str]:
    ids = [
        suggestion.get("id")
        for suggestion in report.get("patch_suggestions", [])
        if suggestion.get("issue_code") == issue_code and suggestion.get("id")
    ]
    return [str(item) for item in ids]


def _build_issue_driven_timeline_merge_inputs(
    workspace: Path,
    report: dict[str, Any],
    gate: dict[str, Any],
) -> list[dict[str, Any]]:
    events = _event_records(workspace)
    scenes = _scene_records(workspace)
    event_map = _event_by_id(events)
    scene_map = _scene_by_id(scenes)
    inputs: list[dict[str, Any]] = []
    seen_records: set[tuple[str, str, str]] = set()

    for issue in report.get("issues", []):
        issue_code = str(issue.get("code") or "")
        if issue_code not in TIMELINE_RELEVANT_ISSUES:
            continue
        details = issue.get("details", {}) if isinstance(issue.get("details"), dict) else {}
        record_type = str(details.get("record_type") or "")
        record_id = str(details.get("record_id") or "")
        if not record_type or not record_id:
            continue
        issue_key = (issue_code, record_type, record_id)
        if issue_key in seen_records:
            continue
        seen_records.add(issue_key)

        apply_args: dict[str, Any] = {}
        target_files: list[str] = []
        missing_fields: list[str] = []

        if record_type == "event":
            event = event_map.get(record_id)
            if not event:
                continue
            reading_chapter = details.get("draft_chapter") if isinstance(details.get("draft_chapter"), int) else event.get("reading_chapter")
            location = details.get("draft_location")
            if not isinstance(location, str) or not location.strip():
                location = str(event.get("location") or "").strip() or None
            chronological_index = event.get("chronological_index")
            if not isinstance(chronological_index, int):
                chronological_index = _suggest_chronological_index(events, reading_chapter if isinstance(reading_chapter, int) else None)
            apply_args = {
                "event_id": record_id,
                "event_label": event.get("label"),
                "chronological_index": chronological_index,
                "reading_chapter": reading_chapter,
                "location": location,
                "participant_ids": list(event.get("participants", [])),
            }
            target_files = ["timeline/events.json"]
            if not event.get("label"):
                missing_fields.append("event_label")
            if not isinstance(reading_chapter, int):
                missing_fields.append("reading_chapter")
            if not apply_args["participant_ids"]:
                missing_fields.append("participant_ids")
            strategy = "update-existing-event"
        elif record_type == "scene":
            record = scene_map.get(record_id)
            if not record:
                continue
            scene = record.get("scene", {})
            chapter_number = details.get("draft_chapter") if isinstance(details.get("draft_chapter"), int) else record.get("chapter")
            apply_args = {
                "chapter_number": chapter_number,
                "scene_id": record_id,
                "scene_title": scene.get("title"),
                "scene_pov": scene.get("pov"),
                "scene_status": scene.get("status") or "planned",
                "scene_character_ids": list(scene.get("characters", [])),
                "scene_event_ids": list(scene.get("event_ids", [])),
            }
            target_files = ["outline/scene-index.json", "outline/master-outline.md"]
            if not scene.get("title"):
                missing_fields.append("scene_title")
            if not isinstance(chapter_number, int):
                missing_fields.append("chapter_number")
            strategy = "update-existing-scene"
        else:
            continue

        inputs.append(
            {
                "id": f"timeline-merge-{len(inputs) + 1:03d}",
                "kind": "timeline-merge-input",
                "strategy": strategy,
                "summary": _summary_for_issue_input(issue, issue_code, record_id),
                "target_files": target_files,
                "source_issue_code": issue_code,
                "source_patch_suggestion_ids": _patch_suggestion_ids(report, issue_code),
                "missing_fields": missing_fields,
                "can_apply_directly": gate.get("can_apply_merge", False) and not missing_fields,
                "requires_override": gate.get("status") == "blocked",
                "warnings": list(gate.get("warnings", [])),
                "resolution_note_suggestion": str(issue.get("message") or ""),
                "apply_args": apply_args,
            }
        )
    return inputs


def _build_issue_driven_knowledge_merge_inputs(
    workspace: Path,
    report: dict[str, Any],
    gate: dict[str, Any],
) -> list[dict[str, Any]]:
    canon_index = read_json(workspace / "state/canon-index.json", default_canon_index(workspace.name))
    claims = report.get("knowledge_claims", [])
    claim_map = {
        (str(item.get("subject_id") or ""), str(item.get("object_key") or "")): item
        for item in claims
        if item.get("subject_id") and item.get("object_key")
    }
    inputs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for issue in report.get("issues", []):
        issue_code = str(issue.get("code") or "")
        if issue_code not in KNOWLEDGE_RELEVANT_ISSUES:
            continue
        details = issue.get("details", {}) if isinstance(issue.get("details"), dict) else {}
        if str(details.get("direction") or "") != "knowledge-advance":
            continue
        subject_id = str(details.get("subject_id") or "").strip()
        if not subject_id:
            continue
        claim = None
        detail_object = str(details.get("knowledge_object") or "").strip()
        for item in claims:
            if str(item.get("subject_id") or "").strip() != subject_id:
                continue
            if detail_object and str(item.get("object_phrase") or "").strip() != detail_object:
                continue
            claim = item
            break
        if claim is None and len(claim_map) == 1:
            claim = next(iter(claim_map.values()))
        if claim is None:
            continue
        object_key = str(claim.get("object_key") or "").strip()
        if not object_key:
            continue
        existing_state = _existing_knowledge_state_match(canon_index, subject_id, object_key)
        knowledge_state_id = (
            str(existing_state.get("id"))
            if existing_state and existing_state.get("id")
            else _knowledge_state_record_id(subject_id, object_key, claim.get("chapter") if isinstance(claim.get("chapter"), int) else None)
        )
        issue_key = (issue_code, knowledge_state_id)
        if issue_key in seen:
            continue
        seen.add(issue_key)

        missing_fields: list[str] = []
        chapter = claim.get("chapter")
        if not isinstance(chapter, int):
            missing_fields.append("knowledge_reading_chapter")
        apply_args = {
            "knowledge_state_id": knowledge_state_id,
            "knowledge_subject_id": subject_id,
            "knowledge_subject_name": claim.get("subject_name"),
            "knowledge_object_key": object_key,
            "knowledge_object_phrase": claim.get("object_phrase"),
            "knowledge_verb": claim.get("verb"),
            "knowledge_reading_chapter": chapter if isinstance(chapter, int) else None,
            "knowledge_event_id": details.get("record_id") if details.get("record_type") == "event" else None,
            "knowledge_notes": issue.get("message"),
        }
        inputs.append(
            {
                "id": f"timeline-merge-know-{len(inputs) + 1:03d}",
                "kind": "timeline-merge-input",
                "strategy": "update-existing-knowledge-state" if existing_state else "upsert-canon-knowledge-state",
                "summary": (
                    f"更新现有知情记录 `{knowledge_state_id}`，把 `{claim.get('subject_name')}` 的知情点前移到第 {chapter} 章。"
                    if existing_state
                    else f"把 `{claim.get('subject_name')}` 关于 `{claim.get('object_phrase')}` 的知情点写入 canon。"
                ),
                "target_files": ["state/canon-index.json", "canon/characters.md"],
                "source_issue_code": issue_code,
                "source_patch_suggestion_ids": _patch_suggestion_ids(report, issue_code),
                "missing_fields": missing_fields,
                "can_apply_directly": not missing_fields,
                "requires_override": False,
                "resolves_blocked_gate": True,
                "resolves_issue_codes": [issue_code],
                "warnings": list(gate.get("warnings", [])),
                "resolution_note_suggestion": str(issue.get("message") or ""),
                "apply_args": apply_args,
            }
        )
    return inputs


def _build_issue_driven_relationship_merge_inputs(
    workspace: Path,
    report: dict[str, Any],
    gate: dict[str, Any],
) -> list[dict[str, Any]]:
    canon_index = read_json(workspace / "state/canon-index.json", default_canon_index(workspace.name))
    inputs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for issue in report.get("issues", []):
        issue_code = str(issue.get("code") or "")
        if issue_code not in RELATIONSHIP_RELEVANT_ISSUES:
            continue
        details = issue.get("details", {}) if isinstance(issue.get("details"), dict) else {}
        character_ids = [str(item) for item in details.get("character_ids", []) if str(item).strip()]
        relation_token = str(details.get("relation_token") or ("初见" if issue_code == "first-meeting-conflict" else "")).strip()
        relationship_state = RELATIONSHIP_STATE_MAP.get(relation_token)
        draft_chapter = details.get("draft_chapter")
        if len(character_ids) < 2 or relationship_state is None:
            continue
        existing_relationship = _existing_relationship_match(
            canon_index,
            character_ids,
            relationship_state,
            draft_chapter if isinstance(draft_chapter, int) else None,
        )
        relationship_id = (
            str(existing_relationship.get("id"))
            if existing_relationship and existing_relationship.get("id")
            else _relationship_record_id(character_ids, relationship_state, draft_chapter if isinstance(draft_chapter, int) else None)
        )
        issue_key = (issue_code, relationship_id)
        if issue_key in seen:
            continue
        seen.add(issue_key)

        missing_fields: list[str] = []
        if not isinstance(draft_chapter, int):
            missing_fields.append("relationship_reading_chapter")
        record_type = str(details.get("record_type") or "")
        resolves_from_canon = record_type == "canon-relationship"
        apply_args = {
            "relationship_id": relationship_id,
            "relationship_character_ids": character_ids,
            "relationship_state": relationship_state,
            "relationship_reading_chapter": draft_chapter if isinstance(draft_chapter, int) else None,
            "relationship_event_id": details.get("record_id") if details.get("record_type") == "event" else None,
            "relationship_notes": issue.get("message"),
        }
        inputs.append(
            {
                "id": f"timeline-merge-rel-{len(inputs) + 1:03d}",
                "kind": "timeline-merge-input",
                "strategy": "update-existing-relationship" if existing_relationship else "upsert-canon-relationship",
                "summary": (
                    f"更新现有关系 `{relationship_id}`，把 `{details.get('pair')}` 的状态 `{_relationship_state_label(relationship_state)}` 同步到 canon。"
                    if existing_relationship
                    else f"把关系 `{details.get('pair')}` 的状态 `{_relationship_state_label(relationship_state)}` 同步到 canon。"
                ),
                "target_files": ["state/canon-index.json", "canon/characters.md"],
                "source_issue_code": issue_code,
                "source_patch_suggestion_ids": _patch_suggestion_ids(report, issue_code),
                "missing_fields": missing_fields,
                "can_apply_directly": (gate.get("can_apply_merge", False) or resolves_from_canon) and not missing_fields,
                "requires_override": gate.get("status") == "blocked" and not resolves_from_canon,
                "resolves_blocked_gate": resolves_from_canon,
                "resolves_issue_codes": [issue_code] if resolves_from_canon else [],
                "warnings": list(gate.get("warnings", [])),
                "resolution_note_suggestion": str(issue.get("message") or ""),
                "apply_args": apply_args,
            }
        )
    return inputs


def _build_issue_driven_world_rule_merge_inputs(
    workspace: Path,
    idea: dict[str, Any],
    draft: dict[str, Any],
    domains: list[str],
    report: dict[str, Any],
    gate: dict[str, Any],
) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    events = _event_records(workspace)
    constraints = read_json(workspace / "constraints/constraints.json", {"rules": []})
    rule_map = {str(item.get("id")): item for item in constraints.get("rules", []) if item.get("id")}
    default_apply_args, default_targets, default_missing_fields = _default_timeline_apply_args(workspace, idea, draft, domains)
    if not default_apply_args.get("event_id"):
        return inputs

    for issue in report.get("issues", []):
        issue_code = str(issue.get("code") or "")
        if issue_code not in WORLD_RULE_RELEVANT_ISSUES:
            continue
        details = issue.get("details", {}) if isinstance(issue.get("details"), dict) else {}
        rule_id = str(details.get("rule_id") or "").strip()
        if not rule_id:
            continue
        rule = rule_map.get(rule_id, {})
        event_id = str(default_apply_args.get("event_id") or "")
        event_label = str(default_apply_args.get("event_label") or idea.get("title") or "")
        cutoff_chapter = details.get("cutoff_chapter")
        delayed_chapter = details.get("suggested_delay_chapter")
        if not isinstance(delayed_chapter, int):
            delayed_chapter = (cutoff_chapter + 1) if isinstance(cutoff_chapter, int) else None

        delay_apply_args = {
            **default_apply_args,
            "rule_subject_id": details.get("matched_claim_subject_id"),
            "rule_subject_name": details.get("matched_claim_subject_name") or details.get("rule_subject"),
            "chronological_index": _suggest_chronological_index(events, delayed_chapter if isinstance(delayed_chapter, int) else None),
            "reading_chapter": delayed_chapter,
            "chapter_number": delayed_chapter,
            "event_notes": f"{idea.get('content', '')}（按硬约束延后到第 {delayed_chapter} 章。）" if isinstance(delayed_chapter, int) else idea.get("content", ""),
            "scene_notes": f"{idea.get('content', '')}（按硬约束延后到第 {delayed_chapter} 章。）" if isinstance(delayed_chapter, int) else idea.get("content", ""),
        }
        delay_missing_fields = [field for field in default_missing_fields if field not in {"reading_chapter", "chapter_number"}]
        if not isinstance(delayed_chapter, int):
            delay_missing_fields.extend(["reading_chapter", "chapter_number"])
        inputs.append(
            {
                "id": f"timeline-merge-rule-delay-{len(inputs) + 1:03d}",
                "kind": "timeline-merge-input",
                "strategy": "resolve-world-rule-by-delaying-event",
                "summary": f"把 `{event_label}` 延后到第 {delayed_chapter} 章，并保持原有约束 cutoff 不变。",
                "target_files": list(default_targets),
                "source_issue_code": issue_code,
                "source_patch_suggestion_ids": _patch_suggestion_ids(report, issue_code),
                "missing_fields": sorted(set(delay_missing_fields)),
                "can_apply_directly": not delay_missing_fields,
                "requires_override": False,
                "resolves_blocked_gate": True,
                "resolves_issue_codes": [issue_code],
                "warnings": list(gate.get("warnings", [])),
                "resolution_note_suggestion": f"把 `{event_label}` 延后到约束 `{rule_id}` 的 cutoff 之后。",
                "apply_args": delay_apply_args,
            }
        )

        apply_args = {
            **default_apply_args,
            "rule_id": rule_id,
            "rule_type": "hard-canon",
            "rule_label": details.get("rule_label"),
            "rule_subject_id": details.get("matched_claim_subject_id"),
            "rule_subject_name": details.get("matched_claim_subject_name") or details.get("rule_subject"),
            "rule_applies_until_event_id": event_id,
            "rule_notes": f"把 `{details.get('rule_label')}` 的截止点对齐到 `{event_label}`。",
        }
        missing_fields = list(default_missing_fields)
        if not event_id:
            missing_fields.append("rule_applies_until_event_id")
        targets = list(default_targets)
        if "constraints/constraints.json" not in targets:
            targets.append("constraints/constraints.json")
        inputs.append(
            {
                "id": f"timeline-merge-rule-cutoff-{len(inputs) + 1:03d}",
                "kind": "timeline-merge-input",
                "strategy": "resolve-world-rule-by-updating-cutoff",
                "summary": f"创建/更新 `{event_label}`，并把约束 `{rule_id}` 的截止点对齐到该事件。",
                "target_files": targets,
                "source_issue_code": issue_code,
                "source_patch_suggestion_ids": _patch_suggestion_ids(report, issue_code),
                "missing_fields": sorted(set(missing_fields)),
                "can_apply_directly": not missing_fields,
                "requires_override": False,
                "resolves_blocked_gate": True,
                "resolves_issue_codes": [issue_code],
                "warnings": list(gate.get("warnings", [])),
                "resolution_note_suggestion": str(issue.get("message") or ""),
                "apply_args": apply_args,
            }
        )

        current_rule_notes = str(rule.get("notes") or "").strip()
        note_lines = [current_rule_notes] if current_rule_notes else []
        note_lines.append(
            f"例外说明：`{idea.get('title')}` 当前作为第 {details.get('draft_chapter')} 章的提前知情点，需人工确认该约束的解释边界。"
        )
        matching_claim = {
            "subject_id": details.get("matched_claim_subject_id"),
            "subject_name": details.get("matched_claim_subject_name"),
            "object_key": details.get("matched_claim_object_key"),
            "object_phrase": details.get("matched_claim_object_phrase"),
        }
        if not any(matching_claim.values()):
            matching_claim = next(
                (
                    claim
                    for claim in report.get("knowledge_claims", [])
                    if str(claim.get("subject_name") or "").strip() == str(details.get("rule_subject") or "").strip()
                ),
                {},
            )
        exception_object_key = str(matching_claim.get("object_key") or details.get("rule_object") or "").strip()
        exception_object_phrase = str(matching_claim.get("object_phrase") or details.get("rule_object") or "").strip()
        exception_subject_name = str(matching_claim.get("subject_name") or details.get("rule_subject") or "").strip()
        exception_subject_id = matching_claim.get("subject_id")
        exception_chapter = details.get("draft_chapter") if isinstance(details.get("draft_chapter"), int) else None
        exception_id = _world_rule_exception_record_id(rule_id, exception_subject_name, exception_object_key, exception_chapter)
        inputs.append(
            {
                "id": f"timeline-merge-rule-note-{len(inputs) + 1:03d}",
                "kind": "timeline-merge-input",
                "strategy": "document-world-rule-exception",
                "summary": f"保留 `{rule_id}` 的 cutoff，仅补一条规则说明，记录 `{idea.get('title')}` 的人工解释边界。",
                "target_files": ["state/canon-index.json", "constraints/constraints.json", "canon/world-rules.md"],
                "source_issue_code": issue_code,
                "source_patch_suggestion_ids": _patch_suggestion_ids(report, issue_code),
                "missing_fields": [],
                "can_apply_directly": gate.get("can_apply_merge", False),
                "requires_override": gate.get("status") == "blocked",
                "resolves_blocked_gate": False,
                "warnings": list(gate.get("warnings", [])),
                "resolution_note_suggestion": "先把这条 world-rule 例外说明记入 constraints，再决定是否真正放行。",
                "apply_args": {
                    "rule_id": rule_id,
                    "rule_type": str(rule.get("type") or "hard-canon"),
                    "rule_label": details.get("rule_label"),
                    "rule_subject_id": exception_subject_id,
                    "rule_subject_name": exception_subject_name,
                    "rule_applies_until_event_id": details.get("cutoff_event_id"),
                    "rule_notes": "\n".join(note_lines),
                    "world_rule_exception_id": exception_id,
                    "world_rule_exception_subject_id": exception_subject_id,
                    "world_rule_exception_subject_name": exception_subject_name,
                    "world_rule_exception_object_key": exception_object_key,
                    "world_rule_exception_object_phrase": exception_object_phrase,
                    "world_rule_exception_reading_chapter": exception_chapter,
                    "world_rule_exception_event_id": event_id or None,
                    "world_rule_exception_notes": str(issue.get("message") or ""),
                },
            }
        )
    return inputs


def _build_timeline_merge_inputs(
    workspace: Path,
    idea: dict[str, Any],
    domains: list[str],
    gate: dict[str, Any],
) -> list[dict[str, Any]]:
    draft = _load_intake_draft(workspace, str(idea.get("id")))
    report = load_consistency_report(workspace, str(idea.get("id"))) or {}
    inputs: list[dict[str, Any]] = []
    inputs.extend(_build_issue_driven_timeline_merge_inputs(workspace, report, gate))
    inputs.extend(_build_issue_driven_knowledge_merge_inputs(workspace, report, gate))
    inputs.extend(_build_issue_driven_relationship_merge_inputs(workspace, report, gate))
    inputs.extend(_build_issue_driven_world_rule_merge_inputs(workspace, idea, draft, domains, report, gate))

    default_timeline_input = _build_default_timeline_merge_input(workspace, idea, draft, domains, gate)
    if default_timeline_input is not None:
        inputs.append(default_timeline_input)

    default_relationship_input = _build_default_relationship_merge_input(workspace, idea, draft, gate)
    if default_relationship_input is not None:
        inputs.append(default_relationship_input)
    default_knowledge_input = _build_default_knowledge_merge_input(workspace, idea, report, gate)
    if default_knowledge_input is not None:
        inputs.append(default_knowledge_input)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in inputs:
        key = (str(item.get("strategy") or ""), str(item.get("summary") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _render_merge_plan_html(plan: dict[str, Any]) -> str:
    action_rows = "\n".join(
        "<tr>"
        f"<td><code>{_safe(action.get('domain'))}</code></td>"
        f"<td>{_safe(action.get('summary') or action.get('action'))}</td>"
        f"<td><code>{_safe(action.get('readiness') or '-')}</code></td>"
        f"<td>{_safe(', '.join(action.get('target_files', [])))}</td>"
        f"<td>{_safe(' / '.join(action.get('planned_writes', [])) or '-')}</td>"
        "</tr>"
        for action in plan.get("proposed_actions", [])
    )
    merge_input_rows = "\n".join(
        "<tr>"
        f"<td><code>{_safe(item.get('id'))}</code></td>"
        f"<td><code>{_safe(item.get('strategy'))}</code></td>"
        f"<td><code>{_safe(item.get('can_apply_directly'))}</code></td>"
        f"<td><code>{_safe(', '.join(item.get('target_files', [])))}</code></td>"
        f"<td>{_safe(item.get('summary'))}</td>"
        "</tr>"
        for item in plan.get("timeline_merge_inputs", [])
    )
    merge_input_markup = (
        "<table><thead><tr><th>ID</th><th>Strategy</th><th>Ready</th><th>Targets</th><th>Summary</th></tr></thead>"
        f"<tbody>{merge_input_rows}</tbody></table>"
        if merge_input_rows
        else '<div class="empty">当前没有可生成的 timeline merge 输入。</div>'
    )
    question_items = "\n".join(f"<li>{_safe(question)}</li>" for question in plan.get("unresolved_questions", []))
    blocker_items = "\n".join(f"<li>{_safe(item)}</li>" for item in plan.get("consistency_gate", {}).get("blockers", []))
    warning_items = "\n".join(f"<li>{_safe(item)}</li>" for item in plan.get("consistency_gate", {}).get("warnings", []))
    intake = plan.get("intake_summary", {})
    body = f"""
    <header class="hero">
      <div class="eyebrow">Merge Plan</div>
      <h1>{_safe(plan.get('title'))}</h1>
      <p>idea id: <code>{_safe(plan.get('idea_id'))}</code> · kind: <code>{_safe(plan.get('kind'))}</code></p>
      <nav>
        <a href="../index.html">总览</a>
        <a href="../validation-report.html">校验报告</a>
        <a href="../timeline.html">时间线</a>
      </nav>
    </header>
    <section class="panel" style="margin-top: 24px;">
      <h2>原始想法</h2>
      <p>{_safe(plan.get('content'))}</p>
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Consistency Gate</h2>
      <p>status: <code>{_safe(plan.get('consistency_gate', {}).get('status'))}</code></p>
      <p>{_safe(plan.get('consistency_gate', {}).get('summary'))}</p>
      <p>can apply merge: <code>{_safe(plan.get('consistency_gate', {}).get('can_apply_merge'))}</code></p>
      <h3>Blockers</h3>
      <ul class="clean">{blocker_items or '<li>无</li>'}</ul>
      <h3>Warnings</h3>
      <ul class="clean">{warning_items or '<li>无</li>'}</ul>
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Intake Hints</h2>
      <p>chapter hints: <code>{_safe(', '.join(str(item) for item in intake.get('chapter_hints', [])) or '无')}</code></p>
      <p>location candidates: <code>{_safe(', '.join(intake.get('location_candidates', [])) or '无')}</code></p>
      <p>character mentions: <code>{_safe(', '.join(intake.get('character_mentions', [])) or '无')}</code></p>
      <p>confidence: <code>{_safe(intake.get('confidence') or 'unknown')}</code></p>
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Proposed Actions</h2>
      <table>
        <thead><tr><th>Domain</th><th>Summary</th><th>Readiness</th><th>Targets</th><th>Planned Writes</th></tr></thead>
        <tbody>{action_rows}</tbody>
      </table>
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Timeline Merge Inputs</h2>
      {merge_input_markup}
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Unresolved Questions</h2>
      <ul class="clean">{question_items or '<li>无</li>'}</ul>
    </section>
    """
    return _html_page(f"{plan.get('title')} · Merge Plan", body)


def plan_idea_merge(workspace: Path, idea_id: str) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    status = collect_workspace_status(workspace)
    _, idea, _ = _find_idea(workspace, idea_id)
    domains = _infer_domains(idea, status.get("protagonist_name"))
    gate = _consistency_gate(workspace, idea)
    draft = _load_intake_draft(workspace, idea_id)
    report = load_consistency_report(workspace, idea_id) or {}
    intake_summary = _load_intake_draft_summary(workspace, idea_id)
    timeline_merge_inputs = _build_timeline_merge_inputs(workspace, idea, domains, gate)
    plan = {
        "idea_id": idea_id,
        "title": idea.get("title"),
        "kind": idea.get("kind"),
        "status": idea.get("status"),
        "content": idea.get("content"),
        "suggested_domains": domains,
        "consistency_gate": gate,
        "intake_summary": intake_summary,
        "timeline_merge_inputs": timeline_merge_inputs,
        "proposed_actions": _domain_explainers(workspace, idea, domains, gate, draft, report, timeline_merge_inputs),
        "unresolved_questions": _unresolved_questions(domains) + gate["blockers"] + gate["warnings"],
        "created_at": now_iso(),
    }
    plan_path = workspace / "state/merge-plans" / f"{idea_id}.json"
    write_json(plan_path, plan)
    view_path = workspace / "views/merge-plans" / f"{idea_id}.html"
    write_text(view_path, _render_merge_plan_html(plan))
    plan["plan_path"] = str(plan_path.resolve())
    plan["view_path"] = str(view_path.resolve())
    return plan


def _append_markdown_block(path: Path, section_title: str, block_title: str, lines: list[str]) -> None:
    if path.exists():
        text = path.read_text(encoding="utf-8").rstrip() + "\n"
    else:
        text = ""
    header = f"## {section_title}"
    if header not in text:
        if text.strip():
            text += "\n"
        text += f"{header}\n\n"
    text += f"### {block_title}\n\n"
    for line in lines:
        text += f"- {line}\n"
    text += "\n"
    write_text(path, text)


def _upsert_character(
    workspace: Path,
    *,
    character_id: str,
    character_name: str,
    character_role: str,
    character_status: str,
    death_event_id: str | None,
) -> str:
    canon_index_path = workspace / "state/canon-index.json"
    canon_index = read_json(canon_index_path, default_canon_index(workspace.name))
    character = None
    for item in canon_index.get("characters", []):
        if item.get("id") == character_id:
            character = item
            break
    if character is None:
        character = {
            "id": character_id,
            "name": character_name,
            "aliases": [],
            "role": character_role,
            "status": character_status,
            "death_event_id": death_event_id,
        }
        canon_index.setdefault("characters", []).append(character)
    else:
        character["name"] = character_name
        character["role"] = character_role
        character["status"] = character_status
        character["death_event_id"] = death_event_id
    write_json(canon_index_path, canon_index)
    return "state/canon-index.json"


def _upsert_relationship(
    workspace: Path,
    *,
    relationship_id: str,
    relationship_character_ids: list[str],
    relationship_state: str,
    relationship_reading_chapter: int | None,
    relationship_event_id: str | None,
    relationship_notes: str,
) -> str:
    canon_index_path = workspace / "state/canon-index.json"
    canon_index = read_json(canon_index_path, default_canon_index(workspace.name))
    relationship = None
    for item in canon_index.setdefault("relationships", []):
        if item.get("id") == relationship_id:
            relationship = item
            break
    if relationship is None:
        relationship = {"id": relationship_id}
        canon_index.setdefault("relationships", []).append(relationship)
    relationship["character_ids"] = sorted(relationship_character_ids)
    relationship["state"] = relationship_state
    relationship["reading_chapter"] = relationship_reading_chapter
    relationship["event_id"] = relationship_event_id
    relationship["notes"] = relationship_notes
    canon_index["relationships"] = sorted(
        canon_index.get("relationships", []),
        key=lambda item: (
            item.get("reading_chapter") if isinstance(item.get("reading_chapter"), int) else 10**9,
            str(item.get("id", "")),
        ),
    )
    write_json(canon_index_path, canon_index)
    return "state/canon-index.json"


def _upsert_knowledge_state(
    workspace: Path,
    *,
    knowledge_state_id: str,
    knowledge_subject_id: str,
    knowledge_subject_name: str | None,
    knowledge_object_key: str,
    knowledge_object_phrase: str,
    knowledge_verb: str,
    knowledge_reading_chapter: int | None,
    knowledge_event_id: str | None,
    knowledge_notes: str,
) -> str:
    canon_index_path = workspace / "state/canon-index.json"
    canon_index = read_json(canon_index_path, default_canon_index(workspace.name))
    knowledge_state = None
    for item in canon_index.setdefault("knowledge_states", []):
        if item.get("id") == knowledge_state_id:
            knowledge_state = item
            break
    if knowledge_state is None:
        knowledge_state = {"id": knowledge_state_id}
        canon_index.setdefault("knowledge_states", []).append(knowledge_state)
    knowledge_state["subject_id"] = knowledge_subject_id
    knowledge_state["subject_name"] = knowledge_subject_name
    knowledge_state["object_key"] = knowledge_object_key
    knowledge_state["object_phrase"] = knowledge_object_phrase
    knowledge_state["verb"] = knowledge_verb
    knowledge_state["reading_chapter"] = knowledge_reading_chapter
    knowledge_state["event_id"] = knowledge_event_id
    knowledge_state["notes"] = knowledge_notes
    canon_index["knowledge_states"] = sorted(
        canon_index.get("knowledge_states", []),
        key=lambda item: (
            item.get("reading_chapter") if isinstance(item.get("reading_chapter"), int) else 10**9,
            str(item.get("id", "")),
        ),
    )
    write_json(canon_index_path, canon_index)
    return "state/canon-index.json"


def _upsert_world_rule_exception(
    workspace: Path,
    *,
    world_rule_exception_id: str,
    world_rule_exception_rule_id: str,
    world_rule_exception_rule_label: str | None,
    world_rule_exception_subject_id: str | None,
    world_rule_exception_subject_name: str | None,
    world_rule_exception_object_key: str,
    world_rule_exception_object_phrase: str,
    world_rule_exception_reading_chapter: int | None,
    world_rule_exception_event_id: str | None,
    world_rule_exception_notes: str,
) -> str:
    canon_index_path = workspace / "state/canon-index.json"
    canon_index = read_json(canon_index_path, default_canon_index(workspace.name))
    exception = None
    for item in canon_index.setdefault("world_rule_exceptions", []):
        if item.get("id") == world_rule_exception_id:
            exception = item
            break
    if exception is None:
        exception = {"id": world_rule_exception_id}
        canon_index.setdefault("world_rule_exceptions", []).append(exception)
    exception["rule_id"] = world_rule_exception_rule_id
    exception["rule_label"] = world_rule_exception_rule_label
    exception["subject_id"] = world_rule_exception_subject_id
    exception["subject_name"] = world_rule_exception_subject_name
    exception["object_key"] = world_rule_exception_object_key
    exception["object_phrase"] = world_rule_exception_object_phrase
    exception["reading_chapter"] = world_rule_exception_reading_chapter
    exception["event_id"] = world_rule_exception_event_id
    exception["notes"] = world_rule_exception_notes
    canon_index["world_rule_exceptions"] = sorted(
        canon_index.get("world_rule_exceptions", []),
        key=lambda item: (
            item.get("reading_chapter") if isinstance(item.get("reading_chapter"), int) else 10**9,
            str(item.get("id", "")),
        ),
    )
    write_json(canon_index_path, canon_index)
    return "state/canon-index.json"


def _upsert_event(
    workspace: Path,
    *,
    event_id: str,
    event_label: str,
    chronological_index: int,
    reading_chapter: int | None,
    location: str | None,
    participant_ids: list[str],
    notes: str,
) -> str:
    events_path = workspace / "timeline/events.json"
    events_data = read_json(events_path, {"events": []})
    event = None
    for item in events_data.get("events", []):
        if item.get("id") == event_id:
            event = item
            break
    if event is None:
        event = {"id": event_id}
        events_data.setdefault("events", []).append(event)
    event["label"] = event_label
    event["chronological_index"] = chronological_index
    event["reading_chapter"] = reading_chapter
    event["participants"] = participant_ids
    event["location"] = location or ""
    event["notes"] = notes
    events_data["events"] = sorted(
        events_data.get("events", []),
        key=lambda item: (
            item.get("chronological_index") if isinstance(item.get("chronological_index"), int) else 10**9,
            str(item.get("id", "")),
        ),
    )
    write_json(events_path, events_data)
    return "timeline/events.json"


def _upsert_constraint_rule(
    workspace: Path,
    *,
    rule_id: str,
    rule_type: str,
    rule_label: str,
    rule_applies_until_event_id: str | None,
    rule_notes: str,
) -> str:
    constraints_path = workspace / "constraints/constraints.json"
    constraints = read_json(constraints_path, {"rules": []})
    rule = None
    for item in constraints.setdefault("rules", []):
        if item.get("id") == rule_id:
            rule = item
            break
    if rule is None:
        rule = {"id": rule_id}
        constraints.setdefault("rules", []).append(rule)
    rule["type"] = rule_type
    rule["label"] = rule_label
    rule["applies_until_event_id"] = rule_applies_until_event_id
    rule["notes"] = rule_notes
    write_json(constraints_path, constraints)
    return "constraints/constraints.json"


def _upsert_scene(
    workspace: Path,
    *,
    chapter_number: int,
    scene_id: str,
    scene_title: str,
    scene_pov: str | None,
    scene_status: str,
    scene_character_ids: list[str],
    scene_event_ids: list[str],
    notes: str,
) -> str:
    scene_index_path = workspace / "outline/scene-index.json"
    scene_index = read_json(scene_index_path, {"chapters": []})
    chapters = scene_index.setdefault("chapters", [])
    chapter_entry = None
    existing_scene = None
    existing_owner = None

    for item in chapters:
        if item.get("chapter") == chapter_number:
            chapter_entry = item
        for scene in item.setdefault("scenes", []):
            if scene.get("id") == scene_id:
                existing_scene = scene
                existing_owner = item

    if chapter_entry is None:
        chapter_entry = {"chapter": chapter_number, "title": f"第{chapter_number}章", "summary": "", "scenes": []}
        chapters.append(chapter_entry)
        chapters.sort(key=lambda item: item.get("chapter", 10**9))

    if existing_scene is not None and existing_owner is not chapter_entry:
        existing_owner["scenes"] = [scene for scene in existing_owner.get("scenes", []) if scene.get("id") != scene_id]
        chapter_entry.setdefault("scenes", []).append(existing_scene)

    scene = existing_scene
    if scene is None:
        scene = {"id": scene_id}
        chapter_entry.setdefault("scenes", []).append(scene)

    scene["title"] = scene_title
    scene["pov"] = scene_pov or ""
    scene["status"] = scene_status
    scene["characters"] = scene_character_ids
    scene["event_ids"] = scene_event_ids
    scene["notes"] = notes
    write_json(scene_index_path, scene_index)
    return "outline/scene-index.json"


def _load_merge_input_from_plan(workspace: Path, idea_id: str, merge_input_id: str) -> dict[str, Any]:
    plan_path = workspace / "state/merge-plans" / f"{idea_id}.json"
    plan = read_json(plan_path, {})
    for item in plan.get("timeline_merge_inputs", []):
        if item.get("id") == merge_input_id:
            return item
    raise ValueError(f"merge input not found for `{idea_id}`: {merge_input_id}")


def _coalesce_scalar(explicit: Any, fallback: Any, default_values: tuple[Any, ...] = ()) -> Any:
    if explicit is None:
        return fallback
    if explicit in default_values and fallback is not None:
        return fallback
    return explicit


def _coalesce_list(explicit: list[Any] | None, fallback: list[Any] | None) -> list[Any] | None:
    if explicit:
        return explicit
    return fallback


def _can_merge_input_resolve_blocked_gate(workspace: Path, idea_id: str, merge_input: dict[str, Any]) -> bool:
    if not merge_input or not merge_input.get("resolves_blocked_gate"):
        return False
    report = load_consistency_report(workspace, idea_id) or {}
    issues = report.get("issues", [])
    if not issues:
        return False
    blocking_codes = {
        str(issue.get("code") or "")
        for issue in issues
        if issue.get("level") == "error" or str(issue.get("code", "")).endswith("-conflict")
    }
    resolvable_codes = {
        str(code)
        for code in merge_input.get("resolves_issue_codes", [])
        if str(code).strip()
    }
    if not resolvable_codes and merge_input.get("source_issue_code"):
        resolvable_codes.add(str(merge_input.get("source_issue_code")))
    return bool(blocking_codes) and blocking_codes.issubset(resolvable_codes)


def apply_idea_merge(
    workspace: Path,
    *,
    idea_id: str,
    resolution_note: str,
    merge_input_id: str | None = None,
    override_consistency_gate: bool = False,
    rule_id: str | None = None,
    rule_type: str = "hard-canon",
    rule_label: str | None = None,
    rule_applies_until_event_id: str | None = None,
    rule_notes: str | None = None,
    relationship_id: str | None = None,
    relationship_character_ids: list[str] | None = None,
    relationship_state: str | None = None,
    relationship_reading_chapter: int | None = None,
    relationship_event_id: str | None = None,
    relationship_notes: str | None = None,
    knowledge_state_id: str | None = None,
    knowledge_subject_id: str | None = None,
    knowledge_subject_name: str | None = None,
    knowledge_object_key: str | None = None,
    knowledge_object_phrase: str | None = None,
    knowledge_verb: str | None = None,
    knowledge_reading_chapter: int | None = None,
    knowledge_event_id: str | None = None,
    knowledge_notes: str | None = None,
    world_rule_exception_id: str | None = None,
    world_rule_exception_subject_id: str | None = None,
    world_rule_exception_subject_name: str | None = None,
    world_rule_exception_object_key: str | None = None,
    world_rule_exception_object_phrase: str | None = None,
    world_rule_exception_reading_chapter: int | None = None,
    world_rule_exception_event_id: str | None = None,
    world_rule_exception_notes: str | None = None,
    character_id: str | None = None,
    character_name: str | None = None,
    character_role: str = "support",
    character_status: str = "alive",
    death_event_id: str | None = None,
    event_id: str | None = None,
    event_label: str | None = None,
    chronological_index: int | None = None,
    reading_chapter: int | None = None,
    location: str | None = None,
    participant_ids: list[str] | None = None,
    event_notes: str | None = None,
    chapter_number: int | None = None,
    scene_id: str | None = None,
    scene_title: str | None = None,
    scene_pov: str | None = None,
    scene_status: str = "planned",
    scene_character_ids: list[str] | None = None,
    scene_event_ids: list[str] | None = None,
    scene_notes: str | None = None,
    canon_note: str | None = None,
    outline_note: str | None = None,
) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    idea_log, idea, idea_index = _find_idea(workspace, idea_id)
    gate = _consistency_gate(workspace, idea)
    merge_input = _load_merge_input_from_plan(workspace, idea_id, merge_input_id) if merge_input_id else {}
    if not gate["can_apply_merge"] and not override_consistency_gate and not _can_merge_input_resolve_blocked_gate(workspace, idea_id, merge_input):
        raise ValueError(f"consistency gate blocked for `{idea_id}`: {gate['summary']}")
    merge_apply_args = merge_input.get("apply_args", {}) if isinstance(merge_input, dict) else {}

    rule_id = _coalesce_scalar(rule_id, merge_apply_args.get("rule_id"))
    rule_type = _coalesce_scalar(rule_type, merge_apply_args.get("rule_type"), ("hard-canon",))
    rule_label = _coalesce_scalar(rule_label, merge_apply_args.get("rule_label"))
    rule_applies_until_event_id = _coalesce_scalar(rule_applies_until_event_id, merge_apply_args.get("rule_applies_until_event_id"))
    rule_notes = _coalesce_scalar(rule_notes, merge_apply_args.get("rule_notes"))
    relationship_id = _coalesce_scalar(relationship_id, merge_apply_args.get("relationship_id"))
    relationship_character_ids = _coalesce_list(relationship_character_ids, merge_apply_args.get("relationship_character_ids"))
    relationship_state = _coalesce_scalar(relationship_state, merge_apply_args.get("relationship_state"))
    relationship_reading_chapter = _coalesce_scalar(relationship_reading_chapter, merge_apply_args.get("relationship_reading_chapter"))
    relationship_event_id = _coalesce_scalar(relationship_event_id, merge_apply_args.get("relationship_event_id"))
    relationship_notes = _coalesce_scalar(relationship_notes, merge_apply_args.get("relationship_notes"))
    knowledge_state_id = _coalesce_scalar(knowledge_state_id, merge_apply_args.get("knowledge_state_id"))
    knowledge_subject_id = _coalesce_scalar(knowledge_subject_id, merge_apply_args.get("knowledge_subject_id"))
    knowledge_subject_name = _coalesce_scalar(knowledge_subject_name, merge_apply_args.get("knowledge_subject_name"))
    knowledge_object_key = _coalesce_scalar(knowledge_object_key, merge_apply_args.get("knowledge_object_key"))
    knowledge_object_phrase = _coalesce_scalar(knowledge_object_phrase, merge_apply_args.get("knowledge_object_phrase"))
    knowledge_verb = _coalesce_scalar(knowledge_verb, merge_apply_args.get("knowledge_verb"))
    knowledge_reading_chapter = _coalesce_scalar(knowledge_reading_chapter, merge_apply_args.get("knowledge_reading_chapter"))
    knowledge_event_id = _coalesce_scalar(knowledge_event_id, merge_apply_args.get("knowledge_event_id"))
    knowledge_notes = _coalesce_scalar(knowledge_notes, merge_apply_args.get("knowledge_notes"))
    world_rule_exception_id = _coalesce_scalar(world_rule_exception_id, merge_apply_args.get("world_rule_exception_id"))
    world_rule_exception_subject_id = _coalesce_scalar(world_rule_exception_subject_id, merge_apply_args.get("world_rule_exception_subject_id"))
    world_rule_exception_subject_name = _coalesce_scalar(world_rule_exception_subject_name, merge_apply_args.get("world_rule_exception_subject_name"))
    world_rule_exception_object_key = _coalesce_scalar(world_rule_exception_object_key, merge_apply_args.get("world_rule_exception_object_key"))
    world_rule_exception_object_phrase = _coalesce_scalar(world_rule_exception_object_phrase, merge_apply_args.get("world_rule_exception_object_phrase"))
    world_rule_exception_reading_chapter = _coalesce_scalar(world_rule_exception_reading_chapter, merge_apply_args.get("world_rule_exception_reading_chapter"))
    world_rule_exception_event_id = _coalesce_scalar(world_rule_exception_event_id, merge_apply_args.get("world_rule_exception_event_id"))
    world_rule_exception_notes = _coalesce_scalar(world_rule_exception_notes, merge_apply_args.get("world_rule_exception_notes"))
    character_id = _coalesce_scalar(character_id, merge_apply_args.get("character_id"))
    character_name = _coalesce_scalar(character_name, merge_apply_args.get("character_name"))
    character_role = _coalesce_scalar(character_role, merge_apply_args.get("character_role"), ("support",))
    character_status = _coalesce_scalar(character_status, merge_apply_args.get("character_status"), ("alive",))
    death_event_id = _coalesce_scalar(death_event_id, merge_apply_args.get("death_event_id"))
    event_id = _coalesce_scalar(event_id, merge_apply_args.get("event_id"))
    event_label = _coalesce_scalar(event_label, merge_apply_args.get("event_label"))
    chronological_index = _coalesce_scalar(chronological_index, merge_apply_args.get("chronological_index"))
    reading_chapter = _coalesce_scalar(reading_chapter, merge_apply_args.get("reading_chapter"))
    location = _coalesce_scalar(location, merge_apply_args.get("location"))
    participant_ids = _coalesce_list(participant_ids, merge_apply_args.get("participant_ids"))
    event_notes = _coalesce_scalar(event_notes, merge_apply_args.get("event_notes"))
    chapter_number = _coalesce_scalar(chapter_number, merge_apply_args.get("chapter_number"))
    scene_id = _coalesce_scalar(scene_id, merge_apply_args.get("scene_id"))
    scene_title = _coalesce_scalar(scene_title, merge_apply_args.get("scene_title"))
    scene_pov = _coalesce_scalar(scene_pov, merge_apply_args.get("scene_pov"))
    scene_status = _coalesce_scalar(scene_status, merge_apply_args.get("scene_status"), ("planned",))
    scene_character_ids = _coalesce_list(scene_character_ids, merge_apply_args.get("scene_character_ids"))
    scene_event_ids = _coalesce_list(scene_event_ids, merge_apply_args.get("scene_event_ids"))
    scene_notes = _coalesce_scalar(scene_notes, merge_apply_args.get("scene_notes"))
    canon_note = _coalesce_scalar(canon_note, merge_input.get("resolution_note_suggestion"))
    outline_note = _coalesce_scalar(outline_note, merge_input.get("resolution_note_suggestion"))

    updated_files: set[str] = set()

    if relationship_character_ids and relationship_state:
        actual_relationship_id = relationship_id or _relationship_record_id(
            relationship_character_ids,
            relationship_state,
            relationship_reading_chapter if isinstance(relationship_reading_chapter, int) else None,
        )
        updated_files.add(
            _upsert_relationship(
                workspace,
                relationship_id=actual_relationship_id,
                relationship_character_ids=relationship_character_ids,
                relationship_state=relationship_state,
                relationship_reading_chapter=relationship_reading_chapter,
                relationship_event_id=relationship_event_id,
                relationship_notes=relationship_notes or idea.get("content", ""),
            )
        )
        updated_files.add("canon/characters.md")
        _append_markdown_block(
            workspace / "canon/characters.md",
            "Relationship Log",
            f"{idea_id} · {idea.get('title')}",
            [
                f"relationship_id: {actual_relationship_id}",
                f"characters: {', '.join(relationship_character_ids)}",
                f"state: {relationship_state}",
                f"chapter: {relationship_reading_chapter if relationship_reading_chapter is not None else 'unknown'}",
                relationship_notes or resolution_note,
            ],
        )

    if knowledge_subject_id and knowledge_object_key:
        actual_knowledge_state_id = knowledge_state_id or _knowledge_state_record_id(
            knowledge_subject_id,
            knowledge_object_key,
            knowledge_reading_chapter if isinstance(knowledge_reading_chapter, int) else None,
        )
        updated_files.add(
            _upsert_knowledge_state(
                workspace,
                knowledge_state_id=actual_knowledge_state_id,
                knowledge_subject_id=knowledge_subject_id,
                knowledge_subject_name=knowledge_subject_name,
                knowledge_object_key=knowledge_object_key,
                knowledge_object_phrase=knowledge_object_phrase or knowledge_object_key,
                knowledge_verb=knowledge_verb or "知道",
                knowledge_reading_chapter=knowledge_reading_chapter,
                knowledge_event_id=knowledge_event_id,
                knowledge_notes=knowledge_notes or idea.get("content", ""),
            )
        )
        updated_files.add("canon/characters.md")
        _append_markdown_block(
            workspace / "canon/characters.md",
            "Knowledge Log",
            f"{idea_id} · {idea.get('title')}",
            [
                f"knowledge_state_id: {actual_knowledge_state_id}",
                f"subject: {knowledge_subject_name or knowledge_subject_id}",
                f"verb: {knowledge_verb or '知道'}",
                f"object: {knowledge_object_phrase or knowledge_object_key}",
                f"chapter: {knowledge_reading_chapter if knowledge_reading_chapter is not None else 'unknown'}",
                knowledge_notes or resolution_note,
            ],
        )

    if world_rule_exception_object_key and rule_id:
        actual_world_rule_exception_id = world_rule_exception_id or _world_rule_exception_record_id(
            rule_id,
            world_rule_exception_subject_name or world_rule_exception_subject_id or "subject",
            world_rule_exception_object_key,
            world_rule_exception_reading_chapter if isinstance(world_rule_exception_reading_chapter, int) else None,
        )
        updated_files.add(
            _upsert_world_rule_exception(
                workspace,
                world_rule_exception_id=actual_world_rule_exception_id,
                world_rule_exception_rule_id=rule_id,
                world_rule_exception_rule_label=rule_label,
                world_rule_exception_subject_id=world_rule_exception_subject_id,
                world_rule_exception_subject_name=world_rule_exception_subject_name,
                world_rule_exception_object_key=world_rule_exception_object_key,
                world_rule_exception_object_phrase=world_rule_exception_object_phrase or world_rule_exception_object_key,
                world_rule_exception_reading_chapter=world_rule_exception_reading_chapter,
                world_rule_exception_event_id=world_rule_exception_event_id,
                world_rule_exception_notes=world_rule_exception_notes or resolution_note,
            )
        )
        updated_files.add("canon/world-rules.md")
        _append_markdown_block(
            workspace / "canon/world-rules.md",
            "Exception Log",
            f"{idea_id} · {idea.get('title')}",
            [
                f"world_rule_exception_id: {actual_world_rule_exception_id}",
                f"rule_id: {rule_id}",
                f"subject: {world_rule_exception_subject_name or world_rule_exception_subject_id or 'unknown'}",
                f"object: {world_rule_exception_object_phrase or world_rule_exception_object_key}",
                f"chapter: {world_rule_exception_reading_chapter if world_rule_exception_reading_chapter is not None else 'unknown'}",
                world_rule_exception_notes or resolution_note,
            ],
        )

    if rule_id and rule_label:
        updated_files.add(
            _upsert_constraint_rule(
                workspace,
                rule_id=rule_id,
                rule_type=rule_type,
                rule_label=rule_label,
                rule_applies_until_event_id=rule_applies_until_event_id,
                rule_notes=rule_notes or resolution_note,
            )
        )

    if character_name:
        actual_character_id = character_id or f"char-{slugify(character_name)}"
        updated_files.add(
            _upsert_character(
                workspace,
                character_id=actual_character_id,
                character_name=character_name,
                character_role=character_role,
                character_status=character_status,
                death_event_id=death_event_id,
            )
        )
        updated_files.add("canon/characters.md")
        _append_markdown_block(
            workspace / "canon/characters.md",
            "Merge Notes",
            f"{idea_id} · {idea.get('title')}",
            [
                f"角色更新：{character_name} ({actual_character_id})",
                f"role: {character_role}",
                f"status: {character_status}",
                canon_note or resolution_note,
            ],
        )

    actual_event_id = event_id
    if event_label and chronological_index is not None:
        actual_event_id = event_id or f"event-{slugify(event_label)}"
        updated_files.add(
            _upsert_event(
                workspace,
                event_id=actual_event_id,
                event_label=event_label,
                chronological_index=chronological_index,
                reading_chapter=reading_chapter,
                location=location,
                participant_ids=participant_ids or [],
                notes=event_notes or idea.get("content", ""),
            )
        )

    if scene_title and chapter_number is not None:
        actual_scene_id = scene_id or f"scene-{slugify(scene_title)}"
        resolved_event_ids = scene_event_ids or ([actual_event_id] if actual_event_id else [])
        updated_files.add(
            _upsert_scene(
                workspace,
                chapter_number=chapter_number,
                scene_id=actual_scene_id,
                scene_title=scene_title,
                scene_pov=scene_pov,
                scene_status=scene_status,
                scene_character_ids=scene_character_ids or [],
                scene_event_ids=resolved_event_ids,
                notes=scene_notes or idea.get("content", ""),
            )
        )
        updated_files.add("outline/master-outline.md")
        _append_markdown_block(
            workspace / "outline/master-outline.md",
            "Patch Log",
            f"{idea_id} · {idea.get('title')}",
            [
                f"chapter: {chapter_number}",
                f"scene: {scene_title}",
                outline_note or resolution_note,
            ],
        )

    if not updated_files:
        raise ValueError("apply_idea_merge requires at least one concrete canon / outline / timeline update.")

    idea["status"] = "applied"
    idea["target_files"] = sorted(updated_files)
    idea["resolution_note"] = resolution_note
    idea["updated_at"] = now_iso()
    idea["planned_merge_path"] = str((workspace / "state/merge-plans" / f"{idea_id}.json").resolve())
    idea["consistency_report_path"] = gate.get("report_path")
    idea["consistency_gate_status"] = gate.get("status")
    idea["merge_gate_override"] = bool(override_consistency_gate)
    if merge_input_id:
        idea["applied_merge_input_id"] = merge_input_id
    idea_log["ideas"][idea_index] = idea
    write_json(workspace / "state/idea-log.json", idea_log)

    report = validate_workspace(workspace)
    status = collect_workspace_status(workspace)
    render_workspace_views(workspace, status=status, validation_report=report)
    return {
        "idea": idea,
        "updated_files": sorted(updated_files),
        "validation_report": report,
    }
