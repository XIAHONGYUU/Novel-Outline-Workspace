from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .workspace import (
    _append_issue,
    _html_page,
    _load_scene_records,
    _safe,
    default_canon_index,
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
KNOWLEDGE_RECAP_TOKENS = ("再次", "重新", "又", "已经", "早已", "早就")
RELATIONSHIP_REPEAT_TOKENS = ("重新", "再次", "又")
KNOWLEDGE_OBJECT_GENERIC_SUFFIXES = ("真相", "秘密", "消息", "一事", "这件事", "这回事")
KNOWLEDGE_OBJECT_CANONICAL_REPLACEMENTS = (
    ("并不是", "不是"),
    ("并非", "不是"),
    ("不是一路人", "不是同阵营"),
    ("不是一路", "不是同阵营"),
    ("不是一伙人", "不是同阵营"),
    ("不是一伙", "不是同阵营"),
    ("不是同一阵营", "不是同阵营"),
    ("同一阵营", "同阵营"),
    ("一路人", "同阵营"),
    ("一路", "同阵营"),
    ("一伙人", "同阵营"),
    ("一伙", "同阵营"),
    ("同伙", "同阵营"),
    ("真正身份", "身份"),
    ("真实身份", "身份"),
    ("真身", "身份"),
    ("是谁", "身份"),
    ("有内鬼", "泄密"),
    ("内鬼", "泄密"),
)


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


def _title_keys_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    return min(len(left), len(right)) >= 4 and (left in right or right in left)


def _canonicalize_knowledge_match_text(text: str) -> str:
    normalized = _normalize_text(text)
    for source, target in KNOWLEDGE_OBJECT_CANONICAL_REPLACEMENTS:
        normalized = normalized.replace(_normalize_text(source), _normalize_text(target))
    return normalized


def _knowledge_object_signature(text: str) -> tuple[str, tuple[str, ...]] | None:
    normalized = _canonicalize_knowledge_match_text(text)
    if not normalized:
        return None

    for relation_token, family in (("不是同阵营", "separate-camp"), ("同阵营", "same-camp")):
        if relation_token not in normalized:
            continue
        prefix = normalized.split(relation_token, 1)[0]
        parts = [part.strip("的") for part in re.split(r"[和与跟及]", prefix) if part.strip("的")]
        if len(parts) >= 2:
            return family, tuple(sorted(parts))

    if normalized.endswith("身份"):
        subject = normalized[: -len("身份")].rstrip("的")
        if len(subject) >= 2:
            return "identity", (subject,)

    if normalized.endswith("泄密"):
        subject = re.sub(r"(?:有人|有)$", "", normalized[: -len("泄密")]).rstrip("的")
        if len(subject) >= 2:
            return "leak", (subject,)

    return None


def _knowledge_object_tail_family(text: str) -> str | None:
    normalized = _canonicalize_knowledge_match_text(text)
    if not normalized:
        return None
    if normalized.endswith("不是同阵营"):
        return "separate-camp"
    if normalized.endswith("同阵营"):
        return "same-camp"
    if normalized.endswith("身份"):
        return "identity"
    if normalized.endswith("泄密"):
        return "leak"
    return None


def _knowledge_object_family_core(text: str) -> str:
    normalized = _canonicalize_knowledge_match_text(text)
    if not normalized:
        return ""
    updated = normalized
    changed = True
    while changed:
        changed = False
        for suffix in KNOWLEDGE_OBJECT_GENERIC_SUFFIXES:
            normalized_suffix = _normalize_text(suffix)
            if updated.endswith(normalized_suffix) and len(updated) > len(normalized_suffix) + 1:
                updated = updated[: -len(normalized_suffix)]
                changed = True
                break
    return updated


def _normalize_knowledge_object_claim_family_base(family: str, base: str) -> str:
    normalized = str(base or "").strip("的")
    if family == "leak":
        normalized = re.sub(r"(?:内部)?有人$", "", normalized)
        normalized = re.sub(r"有$", "", normalized)
    if family == "same-camp":
        normalized = re.sub(r"是$", "", normalized)
    if family in {"same-camp", "separate-camp"} and normalized in {"他们", "二者", "双方", "两边", "两方", "两者"}:
        return ""
    return normalized.strip("的")


def _knowledge_object_claim_family_signature(text: str) -> tuple[str, str] | None:
    core = _knowledge_object_family_core(text)
    family = _knowledge_object_tail_family(core)
    if not family or not core:
        return None
    family_suffix = {
        "identity": "身份",
        "leak": "泄密",
        "same-camp": "同阵营",
        "separate-camp": "不是同阵营",
    }.get(family, "")
    base = core[: -len(family_suffix)] if family_suffix and core.endswith(family_suffix) else core
    return family, _normalize_knowledge_object_claim_family_base(family, base)


def _is_generic_knowledge_object_for_claim_dedupe(text: str) -> bool:
    signature = _knowledge_object_claim_family_signature(text)
    if signature and not signature[1]:
        return True
    core = _knowledge_object_family_core(text)
    family = _knowledge_object_tail_family(core)
    return bool(family and core in {"身份", "泄密", "同阵营", "不是同阵营"})


def _knowledge_object_claim_wording_rank(text: str) -> int:
    raw = str(text or "")
    signature = _knowledge_object_claim_family_signature(text)
    family = signature[0] if signature else None
    if family == "identity":
        if "是谁" in raw:
            return 3
        if any(token in raw for token in ("真实身份", "真正身份", "身份")):
            return 2
        if "真身" in raw:
            return 1
    if family == "leak":
        if "内部有人泄密" in raw:
            return 3
        if "有人泄密" in raw or "泄密" in raw:
            return 2
        if "内鬼" in raw:
            return 1
    if family == "same-camp":
        if "同一阵营" in raw or "同阵营" in raw:
            return 3
        if "一路人" in raw or "一路" in raw:
            return 2
        if "一伙人" in raw or "一伙" in raw or "同伙" in raw:
            return 1
    if family == "separate-camp":
        if "不是同一阵营" in raw or "并非同一阵营" in raw or "不是同阵营" in raw:
            return 3
        if "不是一路人" in raw or "不是一路" in raw:
            return 2
        if "不是一伙人" in raw or "不是一伙" in raw:
            return 1
    return 0


def _knowledge_object_claim_specificity(text: str) -> tuple[int, int]:
    signature = _knowledge_object_claim_family_signature(text)
    family_base = signature[1] if signature else ""
    normalized = _canonicalize_knowledge_match_text(text)
    return (len(family_base), _knowledge_object_claim_wording_rank(text), len(normalized))


def _dedupe_subject_knowledge_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    for claim in claims:
        candidate_key = str(claim.get("object_key") or claim.get("object_phrase") or "")
        merged = False
        for index, existing in enumerate(deduped):
            if str(existing.get("subject_id") or "") != str(claim.get("subject_id") or ""):
                continue
            existing_key = str(existing.get("object_key") or existing.get("object_phrase") or "")
            if _knowledge_objects_match(existing_key, candidate_key):
                if _knowledge_object_claim_specificity(candidate_key) > _knowledge_object_claim_specificity(existing_key):
                    deduped[index] = claim
                merged = True
                break

            existing_signature = _knowledge_object_claim_family_signature(existing_key)
            candidate_signature = _knowledge_object_claim_family_signature(candidate_key)
            if not existing_signature or existing_signature[0] != (candidate_signature or ("", ""))[0]:
                continue
            existing_core = _knowledge_object_family_core(existing_key)
            candidate_core = _knowledge_object_family_core(candidate_key)
            existing_family = existing_signature[0]
            candidate_family = candidate_signature[0]
            if _is_generic_knowledge_object_for_claim_dedupe(existing_key) and candidate_core != existing_core:
                deduped[index] = claim
                merged = True
                break
            if _is_generic_knowledge_object_for_claim_dedupe(candidate_key) and existing_core != candidate_core:
                merged = True
                break
            existing_base = existing_signature[1]
            candidate_base = candidate_signature[1]
            if existing_base and candidate_base and (
                existing_base in candidate_base or candidate_base in existing_base
            ):
                if _knowledge_object_claim_specificity(candidate_key) > _knowledge_object_claim_specificity(existing_key):
                    deduped[index] = claim
                merged = True
                break
        if not merged:
            deduped.append(claim)
    return deduped


def _shared_knowledge_object_residuals(left: str, right: str) -> tuple[str, str]:
    prefix_length = 0
    while prefix_length < min(len(left), len(right)) and left[prefix_length] == right[prefix_length]:
        prefix_length += 1

    suffix_length = 0
    left_limit = len(left) - prefix_length
    right_limit = len(right) - prefix_length
    while suffix_length < min(left_limit, right_limit) and left[-(suffix_length + 1)] == right[-(suffix_length + 1)]:
        suffix_length += 1

    left_end = len(left) - suffix_length if suffix_length else len(left)
    right_end = len(right) - suffix_length if suffix_length else len(right)
    left_residual = left[prefix_length:left_end].strip("的")
    right_residual = right[prefix_length:right_end].strip("的")
    return left_residual, right_residual


def _knowledge_objects_match(left: str, right: str) -> bool:
    left_normalized = _canonicalize_knowledge_match_text(left)
    right_normalized = _canonicalize_knowledge_match_text(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True

    left_signature = _knowledge_object_signature(left_normalized)
    right_signature = _knowledge_object_signature(right_normalized)
    if left_signature or right_signature:
        return left_signature is not None and left_signature == right_signature

    if min(len(left_normalized), len(right_normalized)) >= 4 and (
        left_normalized in right_normalized or right_normalized in left_normalized
    ):
        return True

    left_residual, right_residual = _shared_knowledge_object_residuals(left_normalized, right_normalized)
    if left_residual or right_residual:
        if not left_residual or not right_residual:
            return True
        if left_residual == right_residual:
            return True
        left_family = _knowledge_object_tail_family(left_residual)
        right_family = _knowledge_object_tail_family(right_residual)
        if left_family and left_family == right_family:
            return True
        return False

    overlap = len(_knowledge_shingles(left_normalized) & _knowledge_shingles(right_normalized))
    min_shingles = min(len(_knowledge_shingles(left_normalized)), len(_knowledge_shingles(right_normalized)))
    return min_shingles >= 4 and overlap >= min_shingles - 1


def _knowledge_record_priority(record_type: str) -> int:
    if record_type == "canon-knowledge-state":
        return 2
    if record_type == "event":
        return 1
    return 0


def _matching_knowledge_signal_for_record(
    record: dict[str, Any],
    *,
    claim_object_key: str,
    removable_terms: list[str],
) -> dict[str, Any] | None:
    if record.get("record_type") == "canon-knowledge-state":
        signal = record.get("signal", {})
        return signal if _knowledge_objects_match(claim_object_key, str(signal.get("object_key") or "")) else None

    signals = _extract_knowledge_signals(str(record.get("text") or ""), removable_terms)
    return next((signal for signal in signals if _knowledge_objects_match(claim_object_key, signal["object_key"])), None)


def _knowledge_signals_near_subject(
    text: str,
    *,
    subject_terms: list[str],
    all_subject_terms: list[str],
) -> list[dict[str, Any]]:
    haystack = str(text or "")
    normalized_subject_terms = [str(term).strip() for term in subject_terms if str(term).strip()]
    normalized_all_subject_terms = [str(term).strip() for term in all_subject_terms if str(term).strip()]
    signals: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for term in normalized_subject_terms:
        start = 0
        while True:
            subject_index = haystack.find(term, start)
            if subject_index < 0:
                break
            window_end = _subject_window_end(haystack, subject_index, len(term), normalized_all_subject_terms)
            window = haystack[subject_index:window_end]
            for signal in _extract_knowledge_signals(window, normalized_subject_terms):
                key = (str(signal.get("verb") or ""), str(signal.get("object_key") or ""))
                if key in seen:
                    continue
                seen.add(key)
                signals.append(signal)
            start = subject_index + len(term)
    return signals


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
            prefix_window = source[max(0, index - 4) : index]
            key = (verb, object_key)
            if object_key and key not in seen:
                seen.add(key)
                signals.append(
                    {
                        "verb": verb,
                        "object_phrase": object_phrase,
                        "object_key": object_key,
                        "is_recap": any(token in prefix_window for token in KNOWLEDGE_RECAP_TOKENS),
                    }
                )
            start = index + len(verb)
    return signals


def _subject_window_end(
    haystack: str,
    subject_index: int,
    subject_length: int,
    all_subject_terms: list[str],
) -> int:
    default_end = min(len(haystack), subject_index + 96)
    search_start = subject_index + max(subject_length, 1)
    next_subject_indexes = sorted(
        {
            haystack.find(term, search_start)
            for term in all_subject_terms
            if term and haystack.find(term, search_start) >= 0
        }
    )
    if not next_subject_indexes:
        return default_end
    first_verb_indexes = [
        haystack.find(verb, search_start, default_end)
        for verb in KNOWLEDGE_STATE_TOKENS
        if haystack.find(verb, search_start, default_end) >= 0
    ]
    if not first_verb_indexes:
        return min(default_end, next_subject_indexes[0])
    first_verb_index = min(first_verb_indexes)
    first_next_subject_index = next_subject_indexes[0]
    if first_next_subject_index < first_verb_index:
        return default_end
    return min(default_end, first_next_subject_index)


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
    all_subject_terms = [
        term
        for char_id in resolved_character_ids
        for term in (character_terms_by_id.get(char_id) or [id_to_name.get(char_id, char_id)])
        if str(term).strip()
    ]
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
                window_end = _subject_window_end(haystack, subject_index, len(term), all_subject_terms)
                window = haystack[subject_index:window_end]
                for verb in KNOWLEDGE_STATE_TOKENS:
                    verb_start = len(term)
                    while True:
                        verb_index = window.find(verb, verb_start)
                        if verb_index < 0:
                            break
                        if verb_index - len(term) > 24 and matched:
                            break
                        if verb_index - len(term) > 24:
                            verb_start = verb_index + len(verb)
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
                        verb_start = verb_index + len(verb)
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
    return _dedupe_subject_knowledge_claims(claims)


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
        if not any(_title_keys_match(title_key, event_label) for title_key in title_keys):
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
        if not any(_title_keys_match(title_key, scene_title) for title_key in title_keys):
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
    canon_index: dict[str, Any],
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
    for knowledge_state in canon_index.get("knowledge_states", []):
        subject_id = str(knowledge_state.get("subject_id") or "").strip()
        object_key = str(knowledge_state.get("object_key") or "").strip()
        if not subject_id or not object_key:
            continue
        records.append(
            {
                "record_type": "canon-knowledge-state",
                "record_id": knowledge_state.get("id"),
                "chapter": knowledge_state.get("reading_chapter"),
                "participants": {subject_id},
                "path": "state/canon-index.json",
                "text": "",
                "signal": {
                    "verb": str(knowledge_state.get("verb") or "知道"),
                    "object_phrase": str(knowledge_state.get("object_phrase") or object_key),
                    "object_key": object_key,
                    "is_recap": False,
                },
            }
        )

    for claim in knowledge_claims:
        subject_id = claim["subject_id"]
        subject_name = claim["subject_name"]
        terms = character_terms_by_id.get(subject_id) or [subject_name]
        same_chapter_matches: list[dict[str, Any]] = []
        prior_matches: list[dict[str, Any]] = []
        future_matches: list[dict[str, Any]] = []
        for record in records:
            record_chapter = record.get("chapter")
            if subject_id not in record["participants"] or not isinstance(record_chapter, int):
                continue
            matched_signal = _matching_knowledge_signal_for_record(
                record,
                claim_object_key=str(claim.get("object_key") or ""),
                removable_terms=terms,
            )
            if matched_signal is None:
                continue
            candidate = {"record": record, "signal": matched_signal}
            if record_chapter == claim["chapter"]:
                same_chapter_matches.append(candidate)
                continue
            if record_chapter < claim["chapter"]:
                prior_matches.append(candidate)
            else:
                future_matches.append(candidate)

        if same_chapter_matches:
            continue

        if prior_matches:
            prior_match = max(
                prior_matches,
                key=lambda item: (
                    int(item["record"]["chapter"]),
                    _knowledge_record_priority(str(item["record"]["record_type"])),
                    str(item["record"]["record_id"]),
                ),
            )
            record = prior_match["record"]
            matched_signal = prior_match["signal"]
            record_chapter = int(record["chapter"])
            qualifier = "首次" if claim["first_claim"] else "关键"
            message = (
                f"角色 `{subject_name}` 在 {record['record_type']} `{record['record_id']}` 第 {record_chapter} 章已经出现 "
                f"`{matched_signal['object_phrase']}` 的知情记录；这条 idea 又把{qualifier}知情点放到第 {claim['chapter']} 章。"
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
                    "direction": "already-known-earlier",
                    "claim_verb": claim["verb"],
                    "record_verb": matched_signal["verb"],
                },
            )
            continue

        non_recap_future_matches = [item for item in future_matches if not item["signal"].get("is_recap")]
        if not non_recap_future_matches:
            continue
        future_match = min(
            non_recap_future_matches,
            key=lambda item: (
                int(item["record"]["chapter"]),
                -_knowledge_record_priority(str(item["record"]["record_type"])),
                str(item["record"]["record_id"]),
            ),
        )
        record = future_match["record"]
        matched_signal = future_match["signal"]
        record_chapter = int(record["chapter"])
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
                "direction": "knowledge-advance",
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


def _has_relationship_repeat_hint(text: str) -> bool:
    haystack = str(text or "")
    return any(token in haystack for token in RELATIONSHIP_REPEAT_TOKENS)


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
    repeat_hint = _has_relationship_repeat_hint(haystack)

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
    if any(
        str(beat.get("state")) == relationship_state and beat.get("chapter") == draft_chapter
        for beat in relationship_history
    ):
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
        if latest_prior_same is not None and repeat_hint and _has_intervening_relationship_transition(
            relationship_history,
            from_chapter=int(latest_prior_same["chapter"]),
            to_chapter=int(earliest_future_same["chapter"]),
            relationship_state=relationship_state,
        ):
            return
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


def _rule_subject_id(rule_subject: str, canon_index: dict[str, Any]) -> str | None:
    token_to_id, _ = _character_lookup(canon_index)
    return token_to_id.get(_normalize_text(rule_subject))


def _rule_subject_terms(rule_subject: str, rule_subject_id: str | None, canon_index: dict[str, Any]) -> list[str]:
    if rule_subject_id:
        terms = _character_terms_by_id(canon_index).get(rule_subject_id, [])
        if terms:
            return terms
    value = str(rule_subject or "").strip()
    return [value] if value else []


def _subject_matches_rule(
    *,
    subject_id: Any,
    subject_name: Any,
    rule_subject: str,
    rule_subject_id: str | None,
) -> bool:
    normalized_rule_subject = _normalize_text(rule_subject)
    if rule_subject_id and str(subject_id or "").strip() == rule_subject_id:
        return True
    return _normalize_text(subject_name) == normalized_rule_subject


def _world_rule_context_subject_scope(
    draft: dict[str, Any],
    knowledge_claims: list[dict[str, Any]],
    *,
    rule_subject: str,
) -> str:
    context_subjects = {
        str(claim.get("subject_name") or "").strip()
        for claim in knowledge_claims
        if str(claim.get("subject_name") or "").strip()
    }
    context_subjects.update(
        str(item).strip()
        for item in draft.get("character_mentions", [])
        if str(item).strip()
    )
    normalized_rule_subject = str(rule_subject or "").strip()
    if normalized_rule_subject:
        context_subjects.add(normalized_rule_subject)
    if len(context_subjects) <= 1:
        return "shared-subject"
    return "split-subjects"


def _local_signal_subject_scope(
    haystack: str,
    *,
    rule_subject_terms: list[str],
    all_subject_terms: list[str],
) -> str:
    normalized_subject_terms = {str(term).strip() for term in rule_subject_terms if str(term).strip()}
    other_subject_terms = [
        str(term).strip()
        for term in all_subject_terms
        if str(term).strip() and str(term).strip() not in normalized_subject_terms
    ]
    if not normalized_subject_terms or not other_subject_terms:
        return "shared-subject"

    for term in normalized_subject_terms:
        start = 0
        while True:
            subject_index = haystack.find(term, start)
            if subject_index < 0:
                break
            window_end = _subject_window_end(haystack, subject_index, len(term), list(normalized_subject_terms | set(other_subject_terms)))
            window = haystack[subject_index:window_end]
            if any(other_term in window for other_term in other_subject_terms):
                return "mixed-subjects"
            start = subject_index + len(term)
    return "shared-subject"


def _world_rule_exemption_scope_token(
    *,
    base_scope: str,
    subject_scope: str,
    match_mode: str,
) -> str:
    return f"{base_scope}-{subject_scope}-{match_mode}"


def _claim_matches_world_rule(
    claim: dict[str, Any],
    *,
    rule_subject: str,
    rule_subject_id: str | None,
    rule_object: str,
) -> bool:
    return _subject_matches_rule(
        subject_id=claim.get("subject_id"),
        subject_name=claim.get("subject_name"),
        rule_subject=rule_subject,
        rule_subject_id=rule_subject_id,
    ) and _knowledge_objects_match(
        str(claim.get("object_key") or claim.get("object_phrase") or ""),
        rule_object,
    )


def _matching_world_rule_exception(
    canon_index: dict[str, Any],
    *,
    rule_id: str,
    draft_chapter: int,
    haystack: str,
    knowledge_claims: list[dict[str, Any]],
    rule_subject: str,
    rule_object: str,
) -> dict[str, Any] | None:
    rule_subject_id = _rule_subject_id(rule_subject, canon_index)
    rule_subject_terms = _rule_subject_terms(rule_subject, rule_subject_id, canon_index)
    all_subject_terms = _rule_subject_candidates(canon_index)
    for exception in canon_index.get("world_rule_exceptions", []):
        if str(exception.get("rule_id") or "").strip() != rule_id:
            continue
        exception_chapter = exception.get("reading_chapter")
        if isinstance(exception_chapter, int) and draft_chapter < exception_chapter:
            continue
        exception_subject_matches_rule = _subject_matches_rule(
            subject_id=exception.get("subject_id"),
            subject_name=exception.get("subject_name"),
            rule_subject=rule_subject,
            rule_subject_id=rule_subject_id,
        )
        if not exception_subject_matches_rule:
            continue
        exception_object = str(exception.get("object_key") or exception.get("object_phrase") or "")
        if knowledge_claims:
            if any(
                _claim_matches_world_rule(
                    claim,
                    rule_subject=rule_subject,
                    rule_subject_id=rule_subject_id,
                    rule_object=exception_object,
                )
                for claim in knowledge_claims
            ):
                return dict(exception)
            continue
        local_signals = _knowledge_signals_near_subject(
            haystack,
            subject_terms=rule_subject_terms,
            all_subject_terms=all_subject_terms,
        )
        if any(_knowledge_objects_match(exception_object, str(signal.get("object_key") or "")) for signal in local_signals):
            return dict(exception)
    return None


def _check_world_rule_conflicts(
    draft: dict[str, Any],
    workspace: Path,
    canon_index: dict[str, Any],
    events: list[dict[str, Any]],
    knowledge_claims: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    exemptions: list[dict[str, Any]],
) -> None:
    draft_chapter = _primary_chapter_hint(draft)
    if draft_chapter is None:
        return

    constraints = read_json(workspace / "constraints/constraints.json", {"rules": []})
    event_map = {item.get("id"): item for item in events if item.get("id")}
    haystack = f"{draft.get('title', '')}\n{draft.get('content', '')}"
    for rule in constraints.get("rules", []):
        if rule.get("type") != "hard-canon":
            continue
        keyword_info = _extract_rule_requirement(str(rule.get("label", "")), canon_index)
        cutoff_event = event_map.get(rule.get("applies_until_event_id"))
        cutoff_chapter = cutoff_event.get("reading_chapter") if isinstance(cutoff_event, dict) else None
        if not keyword_info or not isinstance(cutoff_chapter, int):
            continue
        subject_key, positive_token, object_key = keyword_info
        rule_subject_id = _rule_subject_id(subject_key, canon_index)
        matching_claims = [
            claim
            for claim in knowledge_claims
            if _claim_matches_world_rule(
                claim,
                rule_subject=subject_key,
                rule_subject_id=rule_subject_id,
                rule_object=object_key,
            )
        ]
        matched_claim = matching_claims[0] if matching_claims else {}
        local_signals = _knowledge_signals_near_subject(
            haystack,
            subject_terms=_rule_subject_terms(subject_key, rule_subject_id, canon_index),
            all_subject_terms=_rule_subject_candidates(canon_index),
        )
        subject_hit = bool(matching_claims) or bool(local_signals)
        object_hit = bool(matching_claims) or any(
            _knowledge_objects_match(object_key, str(signal.get("object_key") or ""))
            for signal in local_signals
        )
        positive_hit = bool(matching_claims) or any(str(signal.get("verb") or "").strip() for signal in local_signals) or not positive_token
        matched_exception = _matching_world_rule_exception(
            canon_index,
            rule_id=str(rule.get("id") or ""),
            draft_chapter=draft_chapter,
            haystack=haystack,
            knowledge_claims=matching_claims,
            rule_subject=subject_key,
            rule_object=object_key,
        )
        if matched_exception is not None:
            exception_chapter = matched_exception.get("reading_chapter")
            exception_scope_base = (
                "same-chapter"
                if isinstance(exception_chapter, int) and exception_chapter == draft_chapter
                else "prior-exception"
            )
            exception_match_mode = "claim-match" if matching_claims else "local-signal"
            if exception_match_mode == "claim-match":
                exception_subject_scope = _world_rule_context_subject_scope(
                    draft,
                    knowledge_claims,
                    rule_subject=subject_key,
                )
            else:
                exception_subject_scope = _local_signal_subject_scope(
                    haystack,
                    rule_subject_terms=_rule_subject_terms(subject_key, rule_subject_id, canon_index),
                    all_subject_terms=_rule_subject_candidates(canon_index),
                )
            exemptions.append(
                {
                    "level": "info",
                    "code": "world-rule-exemption-applied",
                    "message": (
                        f"这条 idea 命中了约束 `{rule.get('label')}`，但已有正式 exception "
                        f"`{matched_exception.get('id')}` 放行当前 chapter 的知情变化。"
                    ),
                    "path": "state/canon-index.json",
                    "details": {
                        "rule_id": rule.get("id"),
                        "rule_label": rule.get("label"),
                        "rule_subject": subject_key,
                        "rule_object": object_key,
                        "draft_chapter": draft_chapter,
                        "matched_exception_id": matched_exception.get("id"),
                        "matched_exception_subject_id": matched_exception.get("subject_id"),
                        "matched_exception_subject_name": matched_exception.get("subject_name"),
                        "matched_exception_object_key": matched_exception.get("object_key"),
                        "matched_exception_object_phrase": matched_exception.get("object_phrase"),
                        "matched_exception_chapter": exception_chapter,
                        "exception_scope_base": exception_scope_base,
                        "exception_subject_scope": exception_subject_scope,
                        "exception_match_mode": exception_match_mode,
                        "exception_scope": _world_rule_exemption_scope_token(
                            base_scope=exception_scope_base,
                            subject_scope=exception_subject_scope,
                            match_mode=exception_match_mode,
                        ),
                    },
                }
            )
            continue
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
                    "rule_subject": subject_key,
                    "rule_positive_token": positive_token,
                    "rule_object": object_key,
                    "cutoff_event_id": rule.get("applies_until_event_id"),
                    "cutoff_chapter": cutoff_chapter,
                    "draft_chapter": draft_chapter,
                    "suggested_delay_chapter": cutoff_chapter + 1,
                    "matched_claim_subject_id": matched_claim.get("subject_id"),
                    "matched_claim_subject_name": matched_claim.get("subject_name"),
                    "matched_claim_object_key": matched_claim.get("object_key"),
                    "matched_claim_object_phrase": matched_claim.get("object_phrase"),
                },
            )


def _issue_target_files(issue: dict[str, Any]) -> list[str]:
    code = str(issue.get("code") or "")
    if code == "location-continuity-conflict":
        return ["timeline/events.json"]
    if code == "world-rule-conflict":
        return ["state/canon-index.json", "constraints/constraints.json", "timeline/events.json", "outline/scene-index.json"]
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
            f"这条 idea 早于硬约束 `{details.get('rule_id')}` 的截止点；可以延后事件到第 {details.get('suggested_delay_chapter')} 章，"
            "对齐 cutoff，或补一条显式规则说明。"
        )
        actions = [
            {
                "type": "delay-event-past-cutoff",
                "path": issue.get("path"),
                "rule_id": details.get("rule_id"),
                "cutoff_event_id": details.get("cutoff_event_id"),
                "cutoff_chapter": details.get("cutoff_chapter"),
                "draft_chapter": details.get("draft_chapter"),
                "target_chapter": details.get("suggested_delay_chapter"),
            },
            {
                "type": "align-rule-cutoff-to-draft-event",
                "path": issue.get("path"),
                "rule_id": details.get("rule_id"),
                "cutoff_event_id": details.get("cutoff_event_id"),
                "draft_chapter": details.get("draft_chapter"),
            },
            {
                "type": "document-rule-exception",
                "path": issue.get("path"),
                "rule_id": details.get("rule_id"),
                "rule_subject": details.get("rule_subject"),
                "rule_object": details.get("rule_object"),
                "draft_chapter": details.get("draft_chapter"),
            },
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
    exemption_rows = "\n".join(
        "<tr>"
        f"<td><code>{_safe(item.get('code'))}</code></td>"
        f"<td>{_safe(item.get('message'))}</td>"
        f"<td><code>{_safe((item.get('details', {}) or {}).get('exception_scope') or '-')}</code></td>"
        f"<td><code>{_safe((item.get('details', {}) or {}).get('matched_exception_id') or '-')}</code></td>"
        "</tr>"
        for item in report.get("exemptions", [])
    )
    exemption_markup = (
        f"<table><thead><tr><th>Code</th><th>Message</th><th>Scope</th><th>Exception</th></tr></thead><tbody>{exemption_rows}</tbody></table>"
        if exemption_rows
        else '<div class="empty">当前没有命中的正式豁免记录。</div>'
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
      <h2>Exemptions</h2>
      {exemption_markup}
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
    exemptions: list[dict[str, Any]] = []
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

    canon_index = read_json(workspace / "state/canon-index.json", default_canon_index(workspace.name))
    events = read_json(workspace / "timeline/events.json", {"events": []}).get("events", [])
    scene_records = _load_scene_records(workspace)
    _, id_to_name = _character_lookup(canon_index)
    character_terms_by_id = _character_terms_by_id(canon_index)

    _append_intake_warnings(draft, issues)
    resolved_character_ids = _resolve_character_mentions(draft, canon_index, issues)
    knowledge_claims = _extract_draft_knowledge_claims(draft, resolved_character_ids, character_terms_by_id, id_to_name)
    _check_title_based_conflicts(draft, events, scene_records, issues)
    _check_knowledge_state_conflicts(knowledge_claims, canon_index, character_terms_by_id, events, scene_records, issues)
    _check_first_meeting_conflicts(draft, resolved_character_ids, id_to_name, events, scene_records, issues)
    _check_relationship_history_conflicts(draft, canon_index, resolved_character_ids, id_to_name, events, scene_records, issues)
    _check_world_rule_conflicts(draft, workspace, canon_index, events, knowledge_claims, issues, exemptions)

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
        "exemptions": exemptions,
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
