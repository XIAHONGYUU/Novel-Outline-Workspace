from __future__ import annotations

from pathlib import Path
from typing import Any

from .workspace import (
    _html_page,
    _safe,
    collect_workspace_status,
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


def _domain_reason(domain: str, idea: dict[str, Any]) -> str:
    kind = str(idea.get("kind", "misc"))
    if domain == "canon":
        return f"这条 `{kind}` 想法会影响正式设定或人物认知。"
    if domain == "outline":
        return f"这条 `{kind}` 想法会影响章节推进或场景安排。"
    return f"这条 `{kind}` 想法需要落到事件顺序或时间节点。"


def _unresolved_questions(domains: list[str]) -> list[str]:
    questions: list[str] = []
    if "canon" in domains:
        questions.append("是否需要新增或更新某个正式角色 / 设定条目？")
    if "outline" in domains:
        questions.append("这条想法具体落在哪一章或哪一个 scene？")
    if "timeline" in domains:
        questions.append("这条想法对应的真实时间序号、阅读章节和参与者是什么？")
    return questions


def _render_merge_plan_html(plan: dict[str, Any]) -> str:
    action_rows = "\n".join(
        "<tr>"
        f"<td><code>{_safe(action.get('domain'))}</code></td>"
        f"<td>{_safe(action.get('action'))}</td>"
        f"<td>{_safe(', '.join(action.get('target_files', [])))}</td>"
        f"<td>{_safe(action.get('reason'))}</td>"
        "</tr>"
        for action in plan.get("proposed_actions", [])
    )
    question_items = "\n".join(f"<li>{_safe(question)}</li>" for question in plan.get("unresolved_questions", []))
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
      <h2>Proposed Actions</h2>
      <table>
        <thead><tr><th>Domain</th><th>Action</th><th>Targets</th><th>Reason</th></tr></thead>
        <tbody>{action_rows}</tbody>
      </table>
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
    plan = {
        "idea_id": idea_id,
        "title": idea.get("title"),
        "kind": idea.get("kind"),
        "status": idea.get("status"),
        "content": idea.get("content"),
        "suggested_domains": domains,
        "proposed_actions": [
            {
                "domain": domain,
                "action": f"把该想法并入 {domain} 层。",
                "target_files": DOMAIN_TARGET_FILES[domain],
                "reason": _domain_reason(domain, idea),
                "confidence": "medium",
            }
            for domain in domains
        ],
        "unresolved_questions": _unresolved_questions(domains),
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
    canon_index = read_json(canon_index_path, {"novel_name": workspace.name, "characters": [], "locations": [], "factions": [], "items": []})
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
    for item in chapters:
        if item.get("chapter") == chapter_number:
            chapter_entry = item
            break
    if chapter_entry is None:
        chapter_entry = {"chapter": chapter_number, "title": f"第{chapter_number}章", "summary": "", "scenes": []}
        chapters.append(chapter_entry)
        chapters.sort(key=lambda item: item.get("chapter", 10**9))
    scene = None
    for item in chapter_entry.setdefault("scenes", []):
        if item.get("id") == scene_id:
            scene = item
            break
    if scene is None:
        scene = {"id": scene_id}
        chapter_entry["scenes"].append(scene)
    scene["title"] = scene_title
    scene["pov"] = scene_pov or ""
    scene["status"] = scene_status
    scene["characters"] = scene_character_ids
    scene["event_ids"] = scene_event_ids
    scene["notes"] = notes
    write_json(scene_index_path, scene_index)
    return "outline/scene-index.json"


def apply_idea_merge(
    workspace: Path,
    *,
    idea_id: str,
    resolution_note: str,
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
    chapter_number: int | None = None,
    scene_id: str | None = None,
    scene_title: str | None = None,
    scene_pov: str | None = None,
    scene_status: str = "planned",
    scene_character_ids: list[str] | None = None,
    scene_event_ids: list[str] | None = None,
    canon_note: str | None = None,
    outline_note: str | None = None,
) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    idea_log, idea, idea_index = _find_idea(workspace, idea_id)
    updated_files: set[str] = set()

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
                notes=idea.get("content", ""),
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
                notes=idea.get("content", ""),
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
