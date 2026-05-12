from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .workspace import (
    _append_issue,
    _html_page,
    _load_scene_records,
    _safe,
    now_iso,
    read_json,
    write_json,
    write_text,
)

GENERIC_CHARACTER_MENTIONS = {"主角", "反派", "导师", "师姐", "师兄", "师父", "议长", "议会"}
FIRST_MEETING_TOKENS = ("初见", "初次见面", "首次见面", "第一次见", "第一次认识", "第一次相遇", "第一次碰面")
UNFAMILIAR_RELATION_TOKENS = ("不认识", "并不认识", "素不相识", "互不认识")
RELATIONSHIP_STATE_TOKENS = ("结盟", "和解", "决裂", "背叛", "认识")


def _report_path_for(workspace: Path, idea_id: str) -> Path:
    return workspace / "state/consistency-checks" / f"{idea_id}.json"


def load_consistency_report(workspace: Path, idea_id: str) -> dict[str, Any] | None:
    path = _report_path_for(workspace, idea_id)
    if not path.exists():
        return None
    return read_json(path, {})


def _normalize_text(text: Any) -> str:
    lowered = str(text or "").lower().strip()
    lowered = re.sub(r"\s+", "", lowered)
    lowered = re.sub(r"[^\w\u4e00-\u9fff]+", "", lowered)
    return lowered


def _find_idea(workspace: Path, idea_id: str) -> dict[str, Any]:
    idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
    for idea in idea_log.get("ideas", []):
        if idea.get("id") == idea_id:
            return idea
    raise ValueError(f"unknown idea id: {idea_id}")


def _iso_to_sortable(value: Any) -> str:
    return str(value or "").strip()


def consistency_report_needs_refresh(workspace: Path, idea: dict[str, Any]) -> bool:
    report = load_consistency_report(workspace, str(idea.get("id")))
    if not report:
        return True
    return _iso_to_sortable(report.get("checked_at")) < _iso_to_sortable(idea.get("updated_at"))


def _load_intake_draft(workspace: Path, idea: dict[str, Any]) -> tuple[Path, dict[str, Any] | None]:
    configured = idea.get("intake_draft_path")
    draft_path = Path(configured).expanduser() if configured else workspace / "state/intake-drafts" / f"{idea.get('id')}.json"
    if not draft_path.is_absolute():
        draft_path = (workspace / draft_path).resolve()
    if not draft_path.exists():
        return draft_path, None
    return draft_path, read_json(draft_path, {})


def _character_lookup(canon_index: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    name_to_id: dict[str, str] = {}
    id_to_name: dict[str, str] = {}
    for item in canon_index.get("characters", []):
        char_id = str(item.get("id") or "").strip()
        if not char_id:
            continue
        display_name = str(item.get("name") or char_id)
        id_to_name[char_id] = display_name
        for token in [char_id, display_name, *item.get("aliases", [])]:
            normalized = _normalize_text(token)
            if normalized:
                name_to_id[normalized] = char_id
    return name_to_id, id_to_name


def _resolve_character_mentions(draft: dict[str, Any], canon_index: dict[str, Any], issues: list[dict[str, Any]]) -> list[str]:
    name_to_id, _ = _character_lookup(canon_index)
    resolved: list[str] = []
    for mention in draft.get("character_mentions", []):
        normalized = _normalize_text(mention)
        if not normalized:
            continue
        char_id = name_to_id.get(normalized)
        if char_id:
            if char_id not in resolved:
                resolved.append(char_id)
            continue
        if mention not in GENERIC_CHARACTER_MENTIONS:
            _append_issue(issues, "warning", "unknown-character-mention", f"intake draft 提到了角色 `{mention}`，但当前 canon 中还找不到对应角色。", "state/canon-index.json")
    return resolved


def _append_intake_warnings(draft: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    for question in draft.get("open_questions", []):
        _append_issue(issues, "warning", "intake-open-question", f"intake draft 仍有待确认问题：{question}", "state/intake-drafts")
    if not draft.get("chapter_hints") and "timeline" in draft.get("suggested_domains", []):
        _append_issue(issues, "warning", "missing-chapter-hint", "这条 idea 缺少 chapter hint，时间线相关冲突只能做弱检查。", "state/intake-drafts")
    if not draft.get("location_candidates") and "timeline" in draft.get("suggested_domains", []):
        _append_issue(issues, "warning", "missing-location-candidate", "这条 idea 缺少 location candidate，地点连续性检查会偏弱。", "state/intake-drafts")


def _title_candidates(draft: dict[str, Any]) -> list[str]:
    candidates = [draft.get("title", "")]
    for item in draft.get("timeline_candidates", []):
        candidates.append(item.get("event_label", ""))
    for item in draft.get("outline_candidates", []):
        candidates.append(item.get("scene_title", ""))
    output: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = _normalize_text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


def _check_title_based_conflicts(
    draft: dict[str, Any],
    events: list[dict[str, Any]],
    scene_records: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    title_keys = set(_title_candidates(draft))
    if not title_keys:
        return

    draft_kind = str(draft.get("kind") or "misc")
    draft_chapter = next((item for item in draft.get("chapter_hints", []) if isinstance(item, int)), None)
    draft_location = next((str(item).strip() for item in draft.get("location_candidates", []) if str(item).strip()), None)
    chapter_conflict_code = "knowledge-state-conflict" if draft_kind in {"reveal", "twist"} else "timeline-order-conflict"

    for event in events:
        event_label = _normalize_text(event.get("label") or event.get("id"))
        if event_label not in title_keys:
            continue
        existing_chapter = event.get("reading_chapter")
        if draft_chapter is not None and isinstance(existing_chapter, int) and existing_chapter != draft_chapter:
            _append_issue(
                issues,
                "warning",
                chapter_conflict_code,
                f"idea `{draft.get('idea_id')}` 推断在第 {draft_chapter} 章，但正式事件 `{event.get('id')}` 当前挂在第 {existing_chapter} 章，需确认知识点或事件顺序是否前移。",
                "timeline/events.json",
            )
        existing_location = str(event.get("location") or "").strip()
        if draft_location and existing_location and existing_location != draft_location:
            _append_issue(
                issues,
                "warning",
                "location-continuity-conflict",
                f"idea `{draft.get('idea_id')}` 推断地点为 `{draft_location}`，但正式事件 `{event.get('id')}` 当前地点是 `{existing_location}`。",
                "timeline/events.json",
            )

    for record in scene_records:
        scene = record["scene"]
        scene_title = _normalize_text(scene.get("title") or scene.get("id"))
        if scene_title not in title_keys:
            continue
        existing_chapter = record.get("chapter")
        if draft_chapter is not None and isinstance(existing_chapter, int) and existing_chapter != draft_chapter:
            _append_issue(
                issues,
                "warning",
                chapter_conflict_code,
                f"idea `{draft.get('idea_id')}` 推断在第 {draft_chapter} 章，但正式场景 `{scene.get('id')}` 当前挂在第 {existing_chapter} 章。",
                "outline/scene-index.json",
            )


def _check_first_meeting_conflicts(
    draft: dict[str, Any],
    resolved_character_ids: list[str],
    id_to_name: dict[str, str],
    events: list[dict[str, Any]],
    scene_records: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    haystack = f"{draft.get('title', '')}\n{draft.get('content', '')}"
    if not any(token in haystack for token in FIRST_MEETING_TOKENS):
        return
    draft_chapter = next((item for item in draft.get("chapter_hints", []) if isinstance(item, int)), None)
    if draft_chapter is None or len(resolved_character_ids) < 2:
        return

    pair_label = " / ".join(id_to_name.get(char_id, char_id) for char_id in resolved_character_ids)
    target_set = set(resolved_character_ids)
    for event in events:
        participants = set(event.get("participants", []))
        existing_chapter = event.get("reading_chapter")
        if target_set.issubset(participants) and isinstance(existing_chapter, int) and existing_chapter < draft_chapter:
            _append_issue(
                issues,
                "warning",
                "first-meeting-conflict",
                f"`{pair_label}` 在事件 `{event.get('id')}` 第 {existing_chapter} 章已经共同出场；如果这条 idea 是首次见面，需要确认前文记录是否应改写。",
                "timeline/events.json",
            )
            break
    for record in scene_records:
        scene = record["scene"]
        characters = set(scene.get("characters", []))
        existing_chapter = record.get("chapter")
        if target_set.issubset(characters) and isinstance(existing_chapter, int) and existing_chapter < draft_chapter:
            _append_issue(
                issues,
                "warning",
                "first-meeting-conflict",
                f"`{pair_label}` 在场景 `{scene.get('id')}` 第 {existing_chapter} 章已经共同出场；如果这条 idea 是首次见面，需要确认前文 scene 是否应改写。",
                "outline/scene-index.json",
            )
            break


def _relation_token_in_text(text: str) -> str | None:
    for token in RELATIONSHIP_STATE_TOKENS:
        if token in text:
            return token
    return None


def _check_relationship_history_conflicts(
    draft: dict[str, Any],
    resolved_character_ids: list[str],
    id_to_name: dict[str, str],
    events: list[dict[str, Any]],
    scene_records: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    if len(resolved_character_ids) < 2:
        return

    haystack = f"{draft.get('title', '')}\n{draft.get('content', '')}"
    draft_chapter = next((item for item in draft.get("chapter_hints", []) if isinstance(item, int)), None)
    target_set = set(resolved_character_ids)
    pair_label = " / ".join(id_to_name.get(char_id, char_id) for char_id in resolved_character_ids)

    if draft_chapter is not None and any(token in haystack for token in UNFAMILIAR_RELATION_TOKENS):
        for event in events:
            participants = set(event.get("participants", []))
            existing_chapter = event.get("reading_chapter")
            if target_set.issubset(participants) and isinstance(existing_chapter, int) and existing_chapter < draft_chapter:
                _append_issue(
                    issues,
                    "warning",
                    "relationship-history-conflict",
                    f"`{pair_label}` 在事件 `{event.get('id')}` 第 {existing_chapter} 章已经共同出场；如果此处仍写成互不认识，需要确认关系史是否冲突。",
                    "timeline/events.json",
                )
                break
        for record in scene_records:
            scene = record["scene"]
            characters = set(scene.get("characters", []))
            existing_chapter = record.get("chapter")
            if target_set.issubset(characters) and isinstance(existing_chapter, int) and existing_chapter < draft_chapter:
                _append_issue(
                    issues,
                    "warning",
                    "relationship-history-conflict",
                    f"`{pair_label}` 在场景 `{scene.get('id')}` 第 {existing_chapter} 章已经共同出场；如果此处仍写成互不认识，需要确认关系史是否冲突。",
                    "outline/scene-index.json",
                )
                break

    relation_token = _relation_token_in_text(haystack)
    if not relation_token or draft_chapter is None:
        return

    for event in events:
        participants = set(event.get("participants", []))
        existing_chapter = event.get("reading_chapter")
        relation_text = f"{event.get('label', '')}\n{event.get('notes', '')}"
        if target_set.issubset(participants) and relation_token in relation_text and isinstance(existing_chapter, int) and existing_chapter != draft_chapter:
            _append_issue(
                issues,
                "warning",
                "relationship-history-conflict",
                f"`{pair_label}` 的 `{relation_token}` 关系在事件 `{event.get('id')}` 第 {existing_chapter} 章已有记录，和这条 idea 的第 {draft_chapter} 章存在漂移。",
                "timeline/events.json",
            )
            break

    for record in scene_records:
        scene = record["scene"]
        characters = set(scene.get("characters", []))
        existing_chapter = record.get("chapter")
        relation_text = f"{scene.get('title', '')}\n{scene.get('notes', '')}"
        if target_set.issubset(characters) and relation_token in relation_text and isinstance(existing_chapter, int) and existing_chapter != draft_chapter:
            _append_issue(
                issues,
                "warning",
                "relationship-history-conflict",
                f"`{pair_label}` 的 `{relation_token}` 关系在场景 `{scene.get('id')}` 第 {existing_chapter} 章已有记录，和这条 idea 的第 {draft_chapter} 章存在漂移。",
                "outline/scene-index.json",
            )
            break


def _rule_subject_candidates(canon_index: dict[str, Any]) -> list[str]:
    output: list[str] = []
    for item in canon_index.get("characters", []):
        for token in [item.get("name"), *item.get("aliases", [])]:
            value = str(token or "").strip()
            if value and value not in output:
                output.append(value)
    return output


def _extract_rule_requirement(rule_label: str, canon_index: dict[str, Any]) -> tuple[str, str, str] | None:
    for negation, positive_token in (("不知道", "知道"), ("不能", ""), ("不得", "")):
        if negation not in rule_label:
            continue
        object_part = rule_label.split(negation, 1)[1].strip(" ，。；：,.")
        if not object_part:
            continue
        for subject in _rule_subject_candidates(canon_index):
            if subject in rule_label:
                return subject, positive_token, object_part
    return None


def _check_world_rule_conflicts(
    draft: dict[str, Any],
    workspace: Path,
    canon_index: dict[str, Any],
    events: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    draft_chapter = next((item for item in draft.get("chapter_hints", []) if isinstance(item, int)), None)
    if draft_chapter is None:
        return

    constraints = read_json(workspace / "constraints/constraints.json", {"rules": []})
    event_map = {item.get("id"): item for item in events if item.get("id")}
    haystack = f"{draft.get('title', '')}\n{draft.get('content', '')}"
    normalized_haystack = _normalize_text(haystack)
    for rule in constraints.get("rules", []):
        if rule.get("type") != "hard-canon":
            continue
        keyword_info = _extract_rule_requirement(str(rule.get("label", "")), canon_index)
        cutoff_event = event_map.get(rule.get("applies_until_event_id"))
        cutoff_chapter = cutoff_event.get("reading_chapter") if isinstance(cutoff_event, dict) else None
        if not keyword_info or not isinstance(cutoff_chapter, int):
            continue
        subject_key, positive_token, object_key = keyword_info
        subject_hit = _normalize_text(subject_key) in normalized_haystack
        object_hit = _normalize_text(object_key) in normalized_haystack
        positive_hit = (not positive_token) or (_normalize_text(positive_token) in normalized_haystack)
        if subject_hit and object_hit and positive_hit and draft_chapter <= cutoff_chapter:
            _append_issue(
                issues,
                "warning",
                "world-rule-conflict",
                f"这条 idea 在第 {draft_chapter} 章触发了约束 `{rule.get('label')}`，但该硬约束要求至少到事件 `{rule.get('applies_until_event_id')}` 之后才允许变化。",
                "constraints/constraints.json",
            )


def _render_consistency_html(report: dict[str, Any]) -> str:
    issue_rows = "\n".join(
        "<tr>"
        f"<td><span class=\"badge {'error' if issue.get('level') == 'error' else 'warning'}\">{_safe(issue.get('level'))}</span></td>"
        f"<td><code>{_safe(issue.get('code'))}</code></td>"
        f"<td>{_safe(issue.get('message'))}</td>"
        f"<td><code>{_safe(issue.get('path') or '-')}</code></td>"
        "</tr>"
        for issue in report.get("issues", [])
    )
    issue_markup = (
        f"<table><thead><tr><th>Level</th><th>Code</th><th>Message</th><th>Path</th></tr></thead><tbody>{issue_rows}</tbody></table>"
        if issue_rows
        else '<div class="empty">当前没有发现 idea-level consistency 冲突。</div>'
    )
    draft = report.get("draft", {})
    body = f"""
    <header class="hero">
      <div class="eyebrow">Consistency Check</div>
      <h1>{_safe(report.get('title'))}</h1>
      <p>idea id: <code>{_safe(report.get('idea_id'))}</code> · kind: <code>{_safe(draft.get('kind'))}</code></p>
      <nav>
        <a href="../index.html">总览</a>
        <a href="../validation-report.html">校验报告</a>
        <a href="../timeline.html">时间线</a>
      </nav>
    </header>
    <section class="grid">
      <article class="panel"><div class="eyebrow">Conflicts</div><div class="metric">{report.get('conflict_count', 0)}</div></article>
      <article class="panel"><div class="eyebrow">Errors</div><div class="metric">{report.get('error_count', 0)}</div></article>
      <article class="panel"><div class="eyebrow">Warnings</div><div class="metric">{report.get('warning_count', 0)}</div></article>
      <article class="panel"><div class="eyebrow">Checked At</div><p>{_safe(report.get('checked_at'))}</p></article>
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Draft Snapshot</h2>
      <p>chapter hints: <code>{_safe(', '.join(str(item) for item in draft.get('chapter_hints', [])) or '无')}</code></p>
      <p>location candidates: <code>{_safe(', '.join(draft.get('location_candidates', [])) or '无')}</code></p>
      <p>character mentions: <code>{_safe(', '.join(draft.get('character_mentions', [])) or '无')}</code></p>
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Issues</h2>
      {issue_markup}
    </section>
    """
    return _html_page(f"{report.get('title')} · Consistency Check", body)


def check_idea_consistency(workspace: Path, idea_id: str) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    idea = _find_idea(workspace, idea_id)
    issues: list[dict[str, Any]] = []
    draft_path, draft = _load_intake_draft(workspace, idea)

    if draft is None:
        _append_issue(issues, "error", "missing-intake-draft", f"找不到 idea `{idea_id}` 对应的 intake draft。", str(draft_path))
        draft = {
            "idea_id": idea_id,
            "title": idea.get("title"),
            "kind": idea.get("kind"),
            "chapter_hints": [],
            "location_candidates": [],
            "character_mentions": [],
            "suggested_domains": idea.get("suggested_domains", []),
            "open_questions": [],
        }

    canon_index = read_json(workspace / "state/canon-index.json", {"characters": [], "locations": []})
    events = read_json(workspace / "timeline/events.json", {"events": []}).get("events", [])
    scene_records = _load_scene_records(workspace)
    _, id_to_name = _character_lookup(canon_index)

    _append_intake_warnings(draft, issues)
    resolved_character_ids = _resolve_character_mentions(draft, canon_index, issues)
    _check_title_based_conflicts(draft, events, scene_records, issues)
    _check_first_meeting_conflicts(draft, resolved_character_ids, id_to_name, events, scene_records, issues)
    _check_relationship_history_conflicts(draft, resolved_character_ids, id_to_name, events, scene_records, issues)
    _check_world_rule_conflicts(draft, workspace, canon_index, events, issues)

    error_count = sum(1 for issue in issues if issue.get("level") == "error")
    warning_count = sum(1 for issue in issues if issue.get("level") == "warning")
    conflict_count = sum(1 for issue in issues if str(issue.get("code", "")).endswith("-conflict"))

    report = {
        "workspace_path": str(workspace),
        "idea_id": idea_id,
        "title": idea.get("title"),
        "checked_at": now_iso(),
        "ok": error_count == 0 and conflict_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "conflict_count": conflict_count,
        "issues": issues,
        "draft_path": str(draft_path),
        "draft": draft,
    }

    report_path = _report_path_for(workspace, idea_id)
    view_path = workspace / "views/consistency-checks" / f"{idea_id}.html"
    write_json(report_path, report)
    write_text(view_path, _render_consistency_html(report))
    report["report_path"] = str(report_path.resolve())
    report["view_path"] = str(view_path.resolve())
    return report
