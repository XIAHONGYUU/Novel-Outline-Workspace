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
RELATIONSHIP_TOKEN_TO_STATE = {
    "结盟": "allied",
    "和解": "reconciled",
    "决裂": "ruptured",
    "背叛": "betrayed",
    "认识": "acquainted",
    "初见": "met",
    "不认识": "strangers",
}
KNOWLEDGE_STATE_TOKENS = ("知道", "知情", "意识到", "发现", "察觉", "确认", "识破", "看出", "明白")
FIRST_KNOWLEDGE_TOKENS = (
    "第一次知道",
    "第一次意识到",
    "第一次发现",
    "第一次察觉",
    "第一次确认",
    "第一次识破",
    "第一次看出",
    "第一次明白",
    "才知道",
    "才意识到",
    "才发现",
)
KNOWLEDGE_PREFIX_TOKENS = ("原来", "其实", "已经", "也", "还", "就", "才", "终于", "开始", "逐渐")


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


def _character_terms_by_id(canon_index: dict[str, Any]) -> dict[str, list[str]]:
    terms_by_id: dict[str, list[str]] = {}
    for item in canon_index.get("characters", []):
        char_id = str(item.get("id") or "").strip()
        if not char_id:
            continue
        raw_terms = [str(item.get("name") or "").strip(), *(str(alias).strip() for alias in item.get("aliases", []))]
        seen: set[str] = set()
        terms: list[str] = []
        for token in raw_terms:
            if token and token not in seen:
                seen.add(token)
                terms.append(token)
        if terms:
            terms_by_id[char_id] = sorted(terms, key=len, reverse=True)
    return terms_by_id


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


def _primary_chapter_hint(draft: dict[str, Any]) -> int | None:
    return next((item for item in draft.get("chapter_hints", []) if isinstance(item, int)), None)


def _primary_location_candidate(draft: dict[str, Any]) -> str | None:
    return next((str(item).strip() for item in draft.get("location_candidates", []) if str(item).strip()), None)


def _trim_knowledge_object(text: str, removable_terms: list[str] | None = None) -> str:
    snippet = re.split(r"[，。；：！？\n]", str(text or ""), maxsplit=1)[0]
    snippet = snippet.strip()
    for token in KNOWLEDGE_PREFIX_TOKENS:
        if snippet.startswith(token):
            snippet = snippet.removeprefix(token).strip()
    snippet = re.sub(r"^了+", "", snippet).strip()
    snippet = re.sub(r"^在第[一二三四五六七八九十百两0-9]+章", "", snippet).strip()
    for term in removable_terms or []:
        if term:
            snippet = snippet.replace(term, "")
    return snippet.strip(" ，。；：,.!?")


def _normalize_knowledge_object(text: str, removable_terms: list[str] | None = None) -> str:
    normalized = _normalize_text(_trim_knowledge_object(text, removable_terms))
    for token in [*KNOWLEDGE_STATE_TOKENS, *KNOWLEDGE_PREFIX_TOKENS, "第一次", "首次", "得知"]:
        normalized = normalized.replace(_normalize_text(token), "")
    normalized = re.sub(r"第[一二三四五六七八九十百两0-9]+章", "", normalized)
    return normalized


def _knowledge_shingles(text: str, size: int = 2) -> set[str]:
    if len(text) < size:
        return set()
    return {text[index : index + size] for index in range(len(text) - size + 1)}


def _knowledge_objects_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    if min(len(left), len(right)) >= 4 and (left in right or right in left):
        return True
    return len(_knowledge_shingles(left) & _knowledge_shingles(right)) >= 2


def _extract_knowledge_signals(text: str, removable_terms: list[str] | None = None) -> list[dict[str, Any]]:
    source = str(text or "")
    signals: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for verb in KNOWLEDGE_STATE_TOKENS:
        start = 0
        while True:
            index = source.find(verb, start)
            if index < 0:
                break
            object_phrase = _trim_knowledge_object(source[index + len(verb) :], removable_terms)
            object_key = _normalize_knowledge_object(object_phrase, removable_terms)
            key = (verb, object_key)
            if object_key and key not in seen:
                seen.add(key)
                signals.append(
                    {
                        "verb": verb,
                        "object_phrase": object_phrase,
                        "object_key": object_key,
                    }
                )
            start = index + len(verb)
    return signals


def _extract_draft_knowledge_claims(
    draft: dict[str, Any],
    resolved_character_ids: list[str],
    character_terms_by_id: dict[str, list[str]],
    id_to_name: dict[str, str],
) -> list[dict[str, Any]]:
    draft_chapter = _primary_chapter_hint(draft)
    if draft_chapter is None or not resolved_character_ids:
        return []

    haystack = f"{draft.get('title', '')}\n{draft.get('content', '')}"
    claims: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    first_claim = any(token in haystack for token in FIRST_KNOWLEDGE_TOKENS)

    for char_id in resolved_character_ids:
        terms = character_terms_by_id.get(char_id) or [id_to_name.get(char_id, char_id)]
        matched = False
        for term in terms:
            start = 0
            while True:
                subject_index = haystack.find(term, start)
                if subject_index < 0:
                    break
                window = haystack[subject_index : subject_index + 96]
                for verb in KNOWLEDGE_STATE_TOKENS:
                    verb_index = window.find(verb, len(term))
                    if verb_index < 0 or verb_index - len(term) > 24:
                        continue
                    object_phrase = _trim_knowledge_object(window[verb_index + len(verb) :], terms)
                    object_key = _normalize_knowledge_object(object_phrase, terms)
                    key = (char_id, object_key)
                    if object_key and key not in seen:
                        seen.add(key)
                        claims.append(
                            {
                                "subject_id": char_id,
                                "subject_name": id_to_name.get(char_id, char_id),
                                "verb": verb,
                                "object_phrase": object_phrase,
                                "object_key": object_key,
                                "chapter": draft_chapter,
                                "first_claim": first_claim,
                            }
                        )
                        matched = True
                start = subject_index + len(term)
        if matched:
            continue
        fallback_signals = _extract_knowledge_signals(haystack, terms)
        if len(resolved_character_ids) == 1:
            for signal in fallback_signals:
                key = (char_id, signal["object_key"])
                if signal["object_key"] and key not in seen:
                    seen.add(key)
                    claims.append(
                        {
                            "subject_id": char_id,
                            "subject_name": id_to_name.get(char_id, char_id),
                            "verb": signal["verb"],
                            "object_phrase": signal["object_phrase"],
                            "object_key": signal["object_key"],
                            "chapter": draft_chapter,
                            "first_claim": first_claim,
                        }
                    )
    return claims


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
    draft_chapter = _primary_chapter_hint(draft)
    draft_location = _primary_location_candidate(draft)
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
                {
                    "record_type": "event",
                    "record_id": event.get("id"),
                    "draft_chapter": draft_chapter,
                    "existing_chapter": existing_chapter,
                    "direction": "chapter-drift",
                },
            )
        existing_location = str(event.get("location") or "").strip()
        if draft_location and existing_location and existing_location != draft_location:
            _append_issue(
                issues,
                "warning",
                "location-continuity-conflict",
                f"idea `{draft.get('idea_id')}` 推断地点为 `{draft_location}`，但正式事件 `{event.get('id')}` 当前地点是 `{existing_location}`。",
                "timeline/events.json",
                {
                    "record_type": "event",
                    "record_id": event.get("id"),
                    "draft_location": draft_location,
                    "existing_location": existing_location,
                },
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
                {
                    "record_type": "scene",
                    "record_id": scene.get("id"),
                    "draft_chapter": draft_chapter,
                    "existing_chapter": existing_chapter,
                    "direction": "chapter-drift",
                },
            )


def _check_knowledge_state_conflicts(
    knowledge_claims: list[dict[str, Any]],
    character_terms_by_id: dict[str, list[str]],
    events: list[dict[str, Any]],
    scene_records: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    if not knowledge_claims:
        return

    records: list[dict[str, Any]] = []
    for event in events:
        records.append(
            {
                "record_type": "event",
                "record_id": event.get("id"),
                "chapter": event.get("reading_chapter"),
                "participants": set(event.get("participants", [])),
                "path": "timeline/events.json",
                "text": f"{event.get('label', '')}\n{event.get('notes', '')}",
            }
        )
    for record in scene_records:
        scene = record["scene"]
        records.append(
            {
                "record_type": "scene",
                "record_id": scene.get("id"),
                "chapter": record.get("chapter"),
                "participants": set(scene.get("characters", [])),
                "path": "outline/scene-index.json",
                "text": f"{scene.get('title', '')}\n{scene.get('notes', '')}",
            }
        )

    seen: set[tuple[str, str, str, str, str]] = set()
    for claim in knowledge_claims:
        subject_id = claim["subject_id"]
        subject_name = claim["subject_name"]
        terms = character_terms_by_id.get(subject_id) or [subject_name]
        for record in records:
            record_chapter = record.get("chapter")
            if subject_id not in record["participants"] or not isinstance(record_chapter, int):
                continue
            if record_chapter == claim["chapter"]:
                continue
            signals = _extract_knowledge_signals(str(record.get("text") or ""), terms)
            matched_signal = next(
                (signal for signal in signals if _knowledge_objects_match(claim["object_key"], signal["object_key"])),
                None,
            )
            if matched_signal is None:
                continue
            direction = "already-known-earlier" if record_chapter < claim["chapter"] else "knowledge-advance"
            issue_key = (subject_id, claim["object_key"], str(record["record_type"]), str(record["record_id"]), direction)
            if issue_key in seen:
                continue
            seen.add(issue_key)
            if direction == "already-known-earlier":
                qualifier = "首次" if claim["first_claim"] else "关键"
                message = (
                    f"角色 `{subject_name}` 在 {record['record_type']} `{record['record_id']}` 第 {record_chapter} 章已经出现 "
                    f"`{matched_signal['object_phrase']}` 的知情记录；这条 idea 又把{qualifier}知情点放到第 {claim['chapter']} 章。"
                )
            else:
                message = (
                    f"角色 `{subject_name}` 关于 `{matched_signal['object_phrase']}` 的正式知情记录目前在 "
                    f"{record['record_type']} `{record['record_id']}` 第 {record_chapter} 章，这条 idea 试图前移到第 {claim['chapter']} 章。"
                )
            _append_issue(
                issues,
                "warning",
                "knowledge-state-conflict",
                message,
                str(record["path"]),
                {
                    "subject_id": subject_id,
                    "subject_name": subject_name,
                    "record_type": record["record_type"],
                    "record_id": record["record_id"],
                    "draft_chapter": claim["chapter"],
                    "existing_chapter": record_chapter,
                    "knowledge_object": matched_signal["object_phrase"],
                    "direction": direction,
                    "claim_verb": claim["verb"],
                    "record_verb": matched_signal["verb"],
                },
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
    draft_chapter = _primary_chapter_hint(draft)
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
                {
                    "pair": pair_label,
                    "character_ids": list(resolved_character_ids),
                    "record_type": "event",
                    "record_id": event.get("id"),
                    "draft_chapter": draft_chapter,
                    "existing_chapter": existing_chapter,
                },
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
                {
                    "pair": pair_label,
                    "character_ids": list(resolved_character_ids),
                    "record_type": "scene",
                    "record_id": scene.get("id"),
                    "draft_chapter": draft_chapter,
                    "existing_chapter": existing_chapter,
                },
            )
            break


def _relation_token_in_text(text: str) -> str | None:
    for token in RELATIONSHIP_STATE_TOKENS:
        if token in text:
            return token
    return None


def _relationship_state_from_token(token: str | None) -> str | None:
    if not token:
        return None
    return RELATIONSHIP_TOKEN_TO_STATE.get(token)


def _relationship_history(
    canon_index: dict[str, Any],
    target_set: set[str],
    events: list[dict[str, Any]],
    scene_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    beats: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str, str]] = set()

    for relationship in canon_index.get("relationships", []):
        character_ids = {str(item) for item in relationship.get("character_ids", []) if str(item).strip()}
        chapter = relationship.get("reading_chapter")
        state = str(relationship.get("state") or "").strip()
        if character_ids != target_set or not isinstance(chapter, int) or not state:
            continue
        beat = {
            "chapter": chapter,
            "state": state,
            "source": "canon-relationship",
            "record_id": relationship.get("id"),
            "path": "state/canon-index.json",
        }
        key = (beat["source"], beat["chapter"], beat["state"], str(beat["record_id"]))
        if key not in seen:
            seen.add(key)
            beats.append(beat)

    for event in events:
        participants = {str(item) for item in event.get("participants", []) if str(item).strip()}
        chapter = event.get("reading_chapter")
        token = _relation_token_in_text(f"{event.get('label', '')}\n{event.get('notes', '')}")
        state = _relationship_state_from_token(token)
        if participants == target_set and isinstance(chapter, int) and state:
            beat = {
                "chapter": chapter,
                "state": state,
                "source": "event",
                "record_id": event.get("id"),
                "path": "timeline/events.json",
            }
            key = (beat["source"], beat["chapter"], beat["state"], str(beat["record_id"]))
            if key not in seen:
                seen.add(key)
                beats.append(beat)

    for record in scene_records:
        scene = record["scene"]
        characters = {str(item) for item in scene.get("characters", []) if str(item).strip()}
        chapter = record.get("chapter")
        token = _relation_token_in_text(f"{scene.get('title', '')}\n{scene.get('notes', '')}")
        state = _relationship_state_from_token(token)
        if characters == target_set and isinstance(chapter, int) and state:
            beat = {
                "chapter": chapter,
                "state": state,
                "source": "scene",
                "record_id": scene.get("id"),
                "path": "outline/scene-index.json",
            }
            key = (beat["source"], beat["chapter"], beat["state"], str(beat["record_id"]))
            if key not in seen:
                seen.add(key)
                beats.append(beat)

    beats.sort(key=lambda item: (item["chapter"], str(item["record_id"])))
    return beats


def _has_intervening_relationship_transition(
    history: list[dict[str, Any]],
    *,
    from_chapter: int,
    to_chapter: int,
    relationship_state: str,
) -> bool:
    return any(
        from_chapter < int(item.get("chapter")) < to_chapter and str(item.get("state")) != relationship_state
        for item in history
        if isinstance(item.get("chapter"), int)
    )


def _check_relationship_history_conflicts(
    draft: dict[str, Any],
    canon_index: dict[str, Any],
    resolved_character_ids: list[str],
    id_to_name: dict[str, str],
    events: list[dict[str, Any]],
    scene_records: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    if len(resolved_character_ids) < 2:
        return

    haystack = f"{draft.get('title', '')}\n{draft.get('content', '')}"
    draft_chapter = _primary_chapter_hint(draft)
    target_set = set(resolved_character_ids)
    pair_label = " / ".join(id_to_name.get(char_id, char_id) for char_id in resolved_character_ids)
    relationship_history = _relationship_history(canon_index, target_set, events, scene_records)

    if draft_chapter is not None and any(token in haystack for token in UNFAMILIAR_RELATION_TOKENS):
        for beat in relationship_history:
            existing_chapter = beat.get("chapter")
            if isinstance(existing_chapter, int) and existing_chapter < draft_chapter and str(beat.get("state")) != "strangers":
                _append_issue(
                    issues,
                    "warning",
                    "relationship-history-conflict",
                    f"`{pair_label}` 在 `{beat.get('record_id')}` 第 {existing_chapter} 章已经有关系记录；如果此处仍写成互不认识，需要确认关系史是否冲突。",
                    str(beat.get("path")),
                    {
                        "pair": pair_label,
                        "character_ids": list(resolved_character_ids),
                        "relation_token": "不认识",
                        "record_type": beat.get("source"),
                        "record_id": beat.get("record_id"),
                        "draft_chapter": draft_chapter,
                        "existing_chapter": existing_chapter,
                        "direction": "unfamiliar-after-prior-contact",
                    },
                )
                break

    relation_token = _relation_token_in_text(haystack)
    if not relation_token or draft_chapter is None:
        return
    relationship_state = _relationship_state_from_token(relation_token)
    if relationship_state is None:
        return
    latest_prior_same = None
    earliest_future_same = None
    for beat in relationship_history:
        if str(beat.get("state")) != relationship_state:
            continue
        chapter = beat.get("chapter")
        if not isinstance(chapter, int) or chapter == draft_chapter:
            continue
        if chapter < draft_chapter and (latest_prior_same is None or chapter > latest_prior_same["chapter"]):
            latest_prior_same = beat
        if chapter > draft_chapter and (earliest_future_same is None or chapter < earliest_future_same["chapter"]):
            earliest_future_same = beat

    if latest_prior_same is not None:
        intervening_transition = _has_intervening_relationship_transition(
            relationship_history,
            from_chapter=int(latest_prior_same["chapter"]),
            to_chapter=draft_chapter,
            relationship_state=relationship_state,
        )
        if not intervening_transition:
            _append_issue(
                issues,
                "warning",
                "relationship-history-conflict",
                f"`{pair_label}` 的 `{relation_token}` 关系在 `{latest_prior_same.get('record_id')}` 第 {latest_prior_same['chapter']} 章已有记录，和这条 idea 的第 {draft_chapter} 章存在漂移。",
                str(latest_prior_same.get("path")),
                {
                    "pair": pair_label,
                    "character_ids": list(resolved_character_ids),
                    "relation_token": relation_token,
                    "record_type": latest_prior_same.get("source"),
                    "record_id": latest_prior_same.get("record_id"),
                    "draft_chapter": draft_chapter,
                    "existing_chapter": latest_prior_same["chapter"],
                    "direction": "relationship-drift",
                    "transition_exemptible": intervening_transition,
                },
            )
            return

    if earliest_future_same is not None:
        _append_issue(
            issues,
            "warning",
            "relationship-history-conflict",
            f"`{pair_label}` 的 `{relation_token}` 关系在 `{earliest_future_same.get('record_id')}` 第 {earliest_future_same['chapter']} 章已有记录，和这条 idea 的第 {draft_chapter} 章存在漂移。",
            str(earliest_future_same.get("path")),
            {
                "pair": pair_label,
                "character_ids": list(resolved_character_ids),
                "relation_token": relation_token,
                "record_type": earliest_future_same.get("source"),
                "record_id": earliest_future_same.get("record_id"),
                "draft_chapter": draft_chapter,
                "existing_chapter": earliest_future_same["chapter"],
                "direction": "relationship-drift",
            },
        )


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
    draft_chapter = _primary_chapter_hint(draft)
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
                {
                    "rule_id": rule.get("id"),
                    "rule_label": rule.get("label"),
                    "cutoff_event_id": rule.get("applies_until_event_id"),
                    "cutoff_chapter": cutoff_chapter,
                    "draft_chapter": draft_chapter,
                },
            )


def _issue_target_files(issue: dict[str, Any]) -> list[str]:
    code = str(issue.get("code") or "")
    if code == "location-continuity-conflict":
        return ["timeline/events.json"]
    if code == "world-rule-conflict":
        return ["constraints/constraints.json", "timeline/events.json", "outline/scene-index.json"]
    if code in {"knowledge-state-conflict", "timeline-order-conflict"}:
        return ["timeline/events.json", "outline/scene-index.json"]
    if code in {"first-meeting-conflict", "relationship-history-conflict"}:
        return ["state/canon-index.json", "canon/characters.md", "timeline/events.json", "outline/scene-index.json"]
    if issue.get("path"):
        return [str(issue.get("path"))]
    return ["state/consistency-checks"]


def _build_patch_suggestion(issue: dict[str, Any]) -> dict[str, Any]:
    code = str(issue.get("code") or "")
    details = issue.get("details", {}) if isinstance(issue.get("details"), dict) else {}
    target_files = _issue_target_files(issue)

    if code == "knowledge-state-conflict":
        summary = (
            f"确认 `{details.get('subject_name') or '角色'}` 的知情点是否应改到第 {details.get('draft_chapter')} 章，"
            f"或保留 `{details.get('record_id')}` 当前第 {details.get('existing_chapter')} 章记录。"
        )
        actions = [
            {
                "type": "review-knowledge-beat",
                "path": issue.get("path"),
                "record_id": details.get("record_id"),
                "record_type": details.get("record_type"),
                "current_chapter": details.get("existing_chapter"),
                "suggested_chapter": details.get("draft_chapter"),
                "knowledge_object": details.get("knowledge_object"),
            },
            {
                "type": "sync-knowledge-beat",
                "path": "outline/scene-index.json" if issue.get("path") == "timeline/events.json" else "timeline/events.json",
                "subject_id": details.get("subject_id"),
                "knowledge_object": details.get("knowledge_object"),
            },
        ]
        priority = "high"
    elif code == "location-continuity-conflict":
        summary = f"统一事件 `{details.get('record_id')}` 的地点记录，决定采用 `{details.get('draft_location')}` 还是 `{details.get('existing_location')}`。"
        actions = [
            {
                "type": "review-location",
                "path": issue.get("path"),
                "record_id": details.get("record_id"),
                "draft_location": details.get("draft_location"),
                "existing_location": details.get("existing_location"),
            }
        ]
        priority = "medium"
    elif code == "world-rule-conflict":
        summary = (
            f"这条 idea 早于硬约束 `{details.get('rule_id')}` 的截止点；要么把知识点延后到第 {details.get('cutoff_chapter')} 章之后，"
            "要么明确修改约束。"
        )
        actions = [
            {
                "type": "delay-or-amend-rule",
                "path": issue.get("path"),
                "rule_id": details.get("rule_id"),
                "cutoff_event_id": details.get("cutoff_event_id"),
                "cutoff_chapter": details.get("cutoff_chapter"),
                "draft_chapter": details.get("draft_chapter"),
            }
        ]
        priority = "high"
    elif code == "first-meeting-conflict":
        summary = f"确认 `{details.get('pair')}` 是否真的在第 {details.get('draft_chapter')} 章首次见面，否则需要改写更早记录或调整这条 idea。"
        actions = [
            {
                "type": "review-first-meeting",
                "path": issue.get("path"),
                "record_id": details.get("record_id"),
                "record_type": details.get("record_type"),
                "existing_chapter": details.get("existing_chapter"),
                "draft_chapter": details.get("draft_chapter"),
            }
        ]
        priority = "high"
    elif code == "relationship-history-conflict":
        summary = f"确认 `{details.get('pair')}` 的关系状态是否应改到第 {details.get('draft_chapter')} 章，避免和既有记录重复或漂移。"
        actions = [
            {
                "type": "review-relationship-beat",
                "path": issue.get("path"),
                "record_id": details.get("record_id"),
                "record_type": details.get("record_type"),
                "existing_chapter": details.get("existing_chapter"),
                "draft_chapter": details.get("draft_chapter"),
                "relation_token": details.get("relation_token"),
            }
        ]
        priority = "medium"
    elif code == "timeline-order-conflict":
        summary = f"确认 `{details.get('record_id')}` 的章节挂载是否应从第 {details.get('existing_chapter')} 章调整到第 {details.get('draft_chapter')} 章。"
        actions = [
            {
                "type": "review-timeline-order",
                "path": issue.get("path"),
                "record_id": details.get("record_id"),
                "record_type": details.get("record_type"),
                "existing_chapter": details.get("existing_chapter"),
                "draft_chapter": details.get("draft_chapter"),
            }
        ]
        priority = "medium"
    else:
        summary = issue.get("message") or "复核这条 consistency issue。"
        actions = [{"type": "review-issue", "path": issue.get("path"), "code": code}]
        priority = "medium"

    return {
        "issue_code": code,
        "summary": summary,
        "target_files": target_files,
        "actions": actions,
        "priority": priority,
        "confidence": "medium",
    }


def _build_patch_suggestions(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for issue in issues:
        code = str(issue.get("code") or "")
        if not (code.endswith("-conflict") or code == "world-rule-conflict"):
            continue
        details = issue.get("details", {}) if isinstance(issue.get("details"), dict) else {}
        issue_key = (code, str(issue.get("path") or ""), str(details.get("record_id") or details.get("rule_id") or issue.get("message")))
        if issue_key in seen:
            continue
        seen.add(issue_key)
        suggestion = _build_patch_suggestion(issue)
        suggestion["id"] = f"patch-{len(suggestions) + 1:03d}"
        suggestions.append(suggestion)
    return suggestions


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
    suggestion_rows = "\n".join(
        "<tr>"
        f"<td><code>{_safe(suggestion.get('id'))}</code></td>"
        f"<td>{_safe(suggestion.get('summary'))}</td>"
        f"<td><code>{_safe(', '.join(suggestion.get('target_files', [])))}</code></td>"
        f"<td><code>{_safe(suggestion.get('priority'))}</code></td>"
        "</tr>"
        for suggestion in report.get("patch_suggestions", [])
    )
    suggestion_markup = (
        f"<table><thead><tr><th>ID</th><th>Summary</th><th>Target Files</th><th>Priority</th></tr></thead><tbody>{suggestion_rows}</tbody></table>"
        if suggestion_rows
        else '<div class="empty">当前没有额外 patch 建议。</div>'
    )
    draft = report.get("draft", {})
    knowledge_claims = report.get("knowledge_claims", [])
    knowledge_claim_markup = "\n".join(
        f"<li><code>{_safe(claim.get('subject_name'))}</code> · <code>{_safe(claim.get('verb'))}</code> · {_safe(claim.get('object_phrase'))} · 第 {_safe(claim.get('chapter'))} 章</li>"
        for claim in knowledge_claims
    ) or "<li>无</li>"
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
      <article class="panel"><div class="eyebrow">Patch Suggestions</div><div class="metric">{len(report.get('patch_suggestions', []))}</div></article>
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Draft Snapshot</h2>
      <p>chapter hints: <code>{_safe(', '.join(str(item) for item in draft.get('chapter_hints', [])) or '无')}</code></p>
      <p>location candidates: <code>{_safe(', '.join(draft.get('location_candidates', [])) or '无')}</code></p>
      <p>character mentions: <code>{_safe(', '.join(draft.get('character_mentions', [])) or '无')}</code></p>
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Knowledge Claims</h2>
      <ul class="clean">{knowledge_claim_markup}</ul>
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Issues</h2>
      {issue_markup}
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Patch Suggestions</h2>
      {suggestion_markup}
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
    draft.setdefault("title", idea.get("title"))
    draft.setdefault("kind", idea.get("kind"))
    draft.setdefault("content", idea.get("content"))

    canon_index = read_json(workspace / "state/canon-index.json", {"characters": [], "locations": []})
    events = read_json(workspace / "timeline/events.json", {"events": []}).get("events", [])
    scene_records = _load_scene_records(workspace)
    _, id_to_name = _character_lookup(canon_index)
    character_terms_by_id = _character_terms_by_id(canon_index)

    _append_intake_warnings(draft, issues)
    resolved_character_ids = _resolve_character_mentions(draft, canon_index, issues)
    knowledge_claims = _extract_draft_knowledge_claims(draft, resolved_character_ids, character_terms_by_id, id_to_name)
    _check_title_based_conflicts(draft, events, scene_records, issues)
    _check_knowledge_state_conflicts(knowledge_claims, character_terms_by_id, events, scene_records, issues)
    _check_first_meeting_conflicts(draft, resolved_character_ids, id_to_name, events, scene_records, issues)
    _check_relationship_history_conflicts(draft, canon_index, resolved_character_ids, id_to_name, events, scene_records, issues)
    _check_world_rule_conflicts(draft, workspace, canon_index, events, issues)

    error_count = sum(1 for issue in issues if issue.get("level") == "error")
    warning_count = sum(1 for issue in issues if issue.get("level") == "warning")
    conflict_count = sum(1 for issue in issues if str(issue.get("code", "")).endswith("-conflict"))
    patch_suggestions = _build_patch_suggestions(issues)

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
        "knowledge_claims": knowledge_claims,
        "patch_suggestions": patch_suggestions,
    }

    report_path = _report_path_for(workspace, idea_id)
    view_path = workspace / "views/consistency-checks" / f"{idea_id}.html"
    write_json(report_path, report)
    write_text(view_path, _render_consistency_html(report))
    report["report_path"] = str(report_path.resolve())
    report["view_path"] = str(view_path.resolve())
    return report
