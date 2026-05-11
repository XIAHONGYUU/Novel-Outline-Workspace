from __future__ import annotations

import html
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import CORE_JSON_FILES, TEMPLATE_ROOT


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def slugify(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"\s+", "-", lowered)
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff\-_]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    return lowered or "idea"


def _safe(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _replace_placeholders(text: str, novel_name: str, protagonist_name: str) -> str:
    return text.replace("{{NOVEL_NAME}}", novel_name).replace("{{PROTAGONIST_NAME}}", protagonist_name)


def _default_status(workspace: Path) -> dict[str, Any]:
    return {
        "workspace_path": str(workspace),
        "novel_name": workspace.name,
        "protagonist_name": None,
        "workspace_mode": "fresh",
        "idea_counts": {"total": 0, "pending": 0, "applied": 0, "rejected": 0},
        "entity_counts": {"characters": 0, "events": 0, "scenes": 0},
        "core_files": {path: False for path in CORE_JSON_FILES},
        "view_files": {
            "index": "views/index.html",
            "validation_report": "views/validation-report.html",
            "timeline": "views/timeline.html",
        },
        "last_validation": {
            "ok": False,
            "error_count": 0,
            "warning_count": 0,
            "report_path": None,
            "validated_at": None,
        },
        "recommended_next_step": "先初始化工作区。",
        "updated_at": now_iso(),
    }


def _load_scene_records(workspace: Path) -> list[dict[str, Any]]:
    scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
    records: list[dict[str, Any]] = []
    for chapter in scene_index.get("chapters", []):
        chapter_no = chapter.get("chapter")
        for scene in chapter.get("scenes", []):
            records.append({"chapter": chapter_no, "scene": scene})
    return records


def collect_workspace_status(workspace: Path) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    status = _default_status(workspace)
    stored_status = read_json(workspace / "state/workspace-status.json", {})
    idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
    canon_index = read_json(workspace / "state/canon-index.json", {"characters": []})
    events = read_json(workspace / "timeline/events.json", {"events": []})
    scenes = _load_scene_records(workspace)

    idea_counts = {"total": 0, "pending": 0, "applied": 0, "rejected": 0}
    for idea in idea_log.get("ideas", []):
        idea_counts["total"] += 1
        bucket = idea.get("status", "pending")
        if bucket in idea_counts:
            idea_counts[bucket] += 1

    protagonist_name = stored_status.get("protagonist_name")
    if not protagonist_name and canon_index.get("characters"):
        protagonist_name = canon_index["characters"][0].get("name")

    status["novel_name"] = stored_status.get("novel_name") or canon_index.get("novel_name") or workspace.name
    status["protagonist_name"] = protagonist_name
    status["idea_counts"] = idea_counts
    status["entity_counts"] = {
        "characters": len(canon_index.get("characters", [])),
        "events": len(events.get("events", [])),
        "scenes": len(scenes),
    }
    status["core_files"] = {path: (workspace / path).exists() for path in CORE_JSON_FILES}
    status["view_files"] = stored_status.get("view_files", status["view_files"])
    status["last_validation"] = stored_status.get("last_validation", status["last_validation"])

    if status["last_validation"].get("error_count", 0) > 0:
        status["workspace_mode"] = "repair-existing"
        status["recommended_next_step"] = "先处理 views/validation-report.html 里的错误，再继续补大纲。"
    elif idea_counts["pending"] > 0:
        status["workspace_mode"] = "extend-existing"
        status["recommended_next_step"] = "优先处理 pending ideas，并把确认内容并入 canon / outline / timeline。"
    elif status["entity_counts"]["scenes"] == 0:
        status["workspace_mode"] = "fresh"
        status["recommended_next_step"] = "补第一批正式 scenes 和 timeline events。"
    else:
        status["workspace_mode"] = "extend-existing"
        status["recommended_next_step"] = "继续扩充正式大纲，并在每轮改动后运行 validator。"

    status["updated_at"] = now_iso()
    return status


def _html_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_safe(title)}</title>
  <style>
    :root {{
      --bg: #f5efe5;
      --panel: rgba(255,255,255,0.82);
      --ink: #1d1a17;
      --muted: #5c544c;
      --line: rgba(62, 40, 24, 0.14);
      --accent: #9a3412;
      --accent-soft: #fdba74;
      --error: #b91c1c;
      --warn: #b45309;
      --ok: #166534;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(251, 191, 36, 0.28), transparent 28rem),
        radial-gradient(circle at bottom right, rgba(217, 119, 6, 0.18), transparent 24rem),
        linear-gradient(180deg, #fbf7f0 0%, #efe6d8 100%);
      font-family: "Iowan Old Style", "Palatino Linotype", "Noto Serif SC", serif;
    }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 64px; }}
    header.hero {{
      padding: 24px 28px;
      border: 1px solid var(--line);
      background: linear-gradient(135deg, rgba(255,255,255,0.88), rgba(255,244,230,0.78));
      border-radius: 24px;
      box-shadow: 0 18px 50px rgba(82, 54, 31, 0.10);
    }}
    nav {{
      margin-top: 16px;
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }}
    nav a {{
      color: var(--ink);
      text-decoration: none;
      border: 1px solid var(--line);
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.6);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-top: 24px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 20px;
      background: var(--panel);
      backdrop-filter: blur(12px);
      padding: 18px 20px;
      box-shadow: 0 12px 30px rgba(82, 54, 31, 0.08);
    }}
    .eyebrow {{
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }}
    h1, h2, h3, p {{ margin-top: 0; }}
    h1 {{ font-size: clamp(2rem, 5vw, 3.5rem); margin-bottom: 8px; }}
    h2 {{ font-size: 1.25rem; margin-bottom: 12px; }}
    .metric {{
      font-size: 2rem;
      font-weight: 700;
      margin: 8px 0 0;
    }}
    .badge {{
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 0.88rem;
      background: rgba(154, 52, 18, 0.10);
      color: var(--accent);
    }}
    .badge.error {{ background: rgba(185, 28, 28, 0.12); color: var(--error); }}
    .badge.warning {{ background: rgba(180, 83, 9, 0.12); color: var(--warn); }}
    .badge.ok {{ background: rgba(22, 101, 52, 0.12); color: var(--ok); }}
    ul.clean {{ list-style: none; padding: 0; margin: 0; }}
    ul.clean li {{ padding: 10px 0; border-top: 1px solid var(--line); }}
    ul.clean li:first-child {{ border-top: none; padding-top: 0; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.95rem;
    }}
    th, td {{
      padding: 12px 10px;
      text-align: left;
      border-top: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-weight: 600; }}
    .empty {{
      padding: 18px;
      border: 1px dashed var(--line);
      border-radius: 16px;
      color: var(--muted);
      background: rgba(255,255,255,0.45);
    }}
    .timeline {{
      position: relative;
      margin-top: 24px;
      padding-left: 20px;
    }}
    .timeline::before {{
      content: "";
      position: absolute;
      left: 6px;
      top: 4px;
      bottom: 4px;
      width: 2px;
      background: linear-gradient(180deg, var(--accent-soft), rgba(154, 52, 18, 0.2));
    }}
    .timeline-item {{
      position: relative;
      margin: 0 0 16px;
      padding: 14px 16px 14px 22px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.78);
    }}
    .timeline-item::before {{
      content: "";
      position: absolute;
      left: -18px;
      top: 18px;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 0 4px rgba(251, 191, 36, 0.22);
    }}
    code {{
      background: rgba(62, 40, 24, 0.08);
      padding: 2px 6px;
      border-radius: 6px;
      font-size: 0.92em;
    }}
  </style>
</head>
<body>
  <main>
    {body}
  </main>
</body>
</html>
"""


def _status_badge(status: dict[str, Any]) -> str:
    last_validation = status.get("last_validation", {})
    if last_validation.get("error_count", 0) > 0:
        return '<span class="badge error">Repair Existing</span>'
    if status.get("idea_counts", {}).get("pending", 0) > 0:
        return '<span class="badge warning">Pending Ideas</span>'
    if status.get("entity_counts", {}).get("scenes", 0) > 0:
        return '<span class="badge ok">Stable Working State</span>'
    return '<span class="badge">Fresh Workspace</span>'


def _render_status_html(workspace: Path, status: dict[str, Any]) -> str:
    idea_counts = status.get("idea_counts", {})
    entity_counts = status.get("entity_counts", {})
    last_validation = status.get("last_validation", {})
    core_file_items = "\n".join(
        f"<li><strong>{_safe(path)}</strong> <span class=\"badge {'ok' if exists else 'warning'}\">{'ready' if exists else 'missing'}</span></li>"
        for path, exists in status.get("core_files", {}).items()
    )
    ideas = read_json(workspace / "state/idea-log.json", {"ideas": []}).get("ideas", [])
    recent_ideas = list(reversed(ideas[-5:]))
    recent_idea_items = "\n".join(
        f"<li><strong>{_safe(idea.get('title'))}</strong> <span class=\"badge {'warning' if idea.get('status') == 'pending' else 'ok'}\">{_safe(idea.get('status'))}</span><br><span>{_safe(idea.get('content', ''))}</span></li>"
        for idea in recent_ideas
    )
    if not recent_idea_items:
        recent_idea_items = '<div class="empty">还没有 idea 记录。</div>'

    body = f"""
    <header class="hero">
      <div class="eyebrow">Novel Outline Workspace</div>
      <h1>{_safe(status.get('novel_name'))}</h1>
      <p>主角：{_safe(status.get('protagonist_name') or '未设置')} · 模式：<code>{_safe(status.get('workspace_mode'))}</code></p>
      {_status_badge(status)}
      <nav>
        <a href="index.html">总览</a>
        <a href="validation-report.html">校验报告</a>
        <a href="timeline.html">时间线</a>
      </nav>
    </header>
    <section class="grid">
      <article class="panel"><div class="eyebrow">Ideas</div><div class="metric">{idea_counts.get('total', 0)}</div><p>pending: {idea_counts.get('pending', 0)} / applied: {idea_counts.get('applied', 0)}</p></article>
      <article class="panel"><div class="eyebrow">Characters</div><div class="metric">{entity_counts.get('characters', 0)}</div><p>正式角色索引条目</p></article>
      <article class="panel"><div class="eyebrow">Events</div><div class="metric">{entity_counts.get('events', 0)}</div><p>时间线事件节点</p></article>
      <article class="panel"><div class="eyebrow">Scenes</div><div class="metric">{entity_counts.get('scenes', 0)}</div><p>正式场景节点</p></article>
    </section>
    <section class="grid">
      <article class="panel">
        <h2>下一步</h2>
        <p>{_safe(status.get('recommended_next_step'))}</p>
        <p class="eyebrow">updated at {_safe(status.get('updated_at'))}</p>
      </article>
      <article class="panel">
        <h2>最近校验</h2>
        <p>ok: <code>{_safe(last_validation.get('ok'))}</code></p>
        <p>errors: <code>{_safe(last_validation.get('error_count'))}</code> · warnings: <code>{_safe(last_validation.get('warning_count'))}</code></p>
        <p>validated_at: <code>{_safe(last_validation.get('validated_at') or '未运行')}</code></p>
      </article>
    </section>
    <section class="grid">
      <article class="panel">
        <h2>核心文件</h2>
        <ul class="clean">{core_file_items}</ul>
      </article>
      <article class="panel">
        <h2>最近想法</h2>
        <ul class="clean">{recent_idea_items}</ul>
      </article>
    </section>
    """
    return _html_page(f"{status.get('novel_name')} · 工作区总览", body)


def _render_validation_html(report: dict[str, Any], status: dict[str, Any]) -> str:
    issue_rows = "\n".join(
        "<tr>"
        f"<td><span class=\"badge {'error' if issue.get('level') == 'error' else 'warning'}\">{_safe(issue.get('level'))}</span></td>"
        f"<td><code>{_safe(issue.get('code'))}</code></td>"
        f"<td>{_safe(issue.get('message'))}</td>"
        f"<td><code>{_safe(issue.get('path') or '-')}</code></td>"
        "</tr>"
        for issue in report.get("issues", [])
    )
    if issue_rows:
        issue_markup = f"<table><thead><tr><th>Level</th><th>Code</th><th>Message</th><th>Path</th></tr></thead><tbody>{issue_rows}</tbody></table>"
    else:
        issue_markup = '<div class="empty">当前没有硬冲突。</div>'
    status_class = "ok" if report.get("ok") else "error"
    body = f"""
    <header class="hero">
      <div class="eyebrow">Validation View</div>
      <h1>{_safe(status.get('novel_name'))} 校验报告</h1>
      <p><span class="badge {status_class}">{'OK' if report.get('ok') else 'Needs Repair'}</span></p>
      <nav>
        <a href="index.html">总览</a>
        <a href="validation-report.html">校验报告</a>
        <a href="timeline.html">时间线</a>
      </nav>
    </header>
    <section class="grid">
      <article class="panel"><div class="eyebrow">Errors</div><div class="metric">{report.get('error_count', 0)}</div></article>
      <article class="panel"><div class="eyebrow">Warnings</div><div class="metric">{report.get('warning_count', 0)}</div></article>
      <article class="panel"><div class="eyebrow">Validated At</div><p>{_safe(report.get('validated_at') or '未运行')}</p></article>
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Issues</h2>
      {issue_markup}
    </section>
    """
    return _html_page(f"{status.get('novel_name')} · 校验报告", body)


def _render_timeline_html(workspace: Path, status: dict[str, Any]) -> str:
    canon_index = read_json(workspace / "state/canon-index.json", {"characters": []})
    events = read_json(workspace / "timeline/events.json", {"events": []}).get("events", [])
    characters = {
        item.get("id"): item.get("name", item.get("id"))
        for item in canon_index.get("characters", [])
        if item.get("id")
    }
    sorted_events = sorted(
        events,
        key=lambda item: (
            item.get("chronological_index") if isinstance(item.get("chronological_index"), int) else 10**9,
            str(item.get("id", "")),
        ),
    )
    timeline_markup = []
    for event in sorted_events:
        participant_names = [characters.get(char_id, char_id) for char_id in event.get("participants", [])]
        timeline_markup.append(
            f"""
            <article class="timeline-item">
              <div class="eyebrow">chronological #{_safe(event.get('chronological_index', '?'))}</div>
              <h2>{_safe(event.get('label', event.get('id')))}</h2>
              <p><code>{_safe(event.get('id'))}</code></p>
              <p>reading chapter: <code>{_safe(event.get('reading_chapter', '-'))}</code> · location: <code>{_safe(event.get('location', '-'))}</code></p>
              <p>participants: {_safe(', '.join(participant_names) if participant_names else '无')}</p>
              <p>{_safe(event.get('notes', ''))}</p>
            </article>
            """
        )
    timeline_body = "\n".join(timeline_markup) if timeline_markup else '<div class="empty">当前还没有正式事件。先补 `timeline/events.json`。</div>'
    body = f"""
    <header class="hero">
      <div class="eyebrow">Timeline View</div>
      <h1>{_safe(status.get('novel_name'))} 时间线</h1>
      <p>按真实时间顺序展示事件，适合作为时间与地域信息的基础面板。</p>
      <nav>
        <a href="index.html">总览</a>
        <a href="validation-report.html">校验报告</a>
        <a href="timeline.html">时间线</a>
      </nav>
    </header>
    <section class="panel" style="margin-top: 24px;">
      <h2>Chronological View</h2>
      <div class="timeline">{timeline_body}</div>
    </section>
    """
    return _html_page(f"{status.get('novel_name')} · 时间线", body)


def render_workspace_views(
    workspace: Path,
    status: dict[str, Any] | None = None,
    validation_report: dict[str, Any] | None = None,
) -> dict[str, str]:
    workspace = workspace.expanduser().resolve()
    status = status or collect_workspace_status(workspace)
    validation_report = validation_report or {
        "workspace_path": str(workspace),
        "validated_at": status.get("last_validation", {}).get("validated_at"),
        "ok": status.get("last_validation", {}).get("ok", False),
        "error_count": status.get("last_validation", {}).get("error_count", 0),
        "warning_count": status.get("last_validation", {}).get("warning_count", 0),
        "issues": [],
    }

    index_path = workspace / "views/index.html"
    validation_path = workspace / "views/validation-report.html"
    timeline_path = workspace / "views/timeline.html"

    write_text(index_path, _render_status_html(workspace, status))
    write_text(validation_path, _render_validation_html(validation_report, status))
    write_text(timeline_path, _render_timeline_html(workspace, status))
    return {
        "index": str(index_path.resolve()),
        "validation_report": str(validation_path.resolve()),
        "timeline": str(timeline_path.resolve()),
    }


def init_workspace(workspace: Path, novel_name: str, protagonist_name: str, force: bool = False) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    if workspace.exists() and any(workspace.iterdir()) and not force:
        raise FileExistsError(f"workspace is not empty: {workspace}")

    workspace.mkdir(parents=True, exist_ok=True)
    for source in sorted(TEMPLATE_ROOT.rglob("*")):
        target = workspace / source.relative_to(TEMPLATE_ROOT)
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        content = source.read_text(encoding="utf-8")
        content = _replace_placeholders(content, novel_name, protagonist_name)
        write_text(target, content)

    status = collect_workspace_status(workspace)
    write_json(workspace / "state/workspace-status.json", status)
    render_workspace_views(workspace, status=status)
    return status


def _next_idea_id(existing: list[dict[str, Any]]) -> str:
    prefix = datetime.now(timezone.utc).strftime("idea-%Y%m%d-")
    max_seq = 0
    for item in existing:
        idea_id = str(item.get("id", ""))
        if not idea_id.startswith(prefix):
            continue
        suffix = idea_id.removeprefix(prefix)
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:03d}"


def ingest_idea(
    workspace: Path,
    title: str,
    content: str,
    kind: str,
    tags: list[str] | None = None,
    target_files: list[str] | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    idea_log_path = workspace / "state/idea-log.json"
    idea_log = read_json(idea_log_path, {"ideas": []})
    tags = tags or []
    target_files = target_files or []

    idea_id = _next_idea_id(idea_log.get("ideas", []))
    created_at = now_iso()
    idea = {
        "id": idea_id,
        "title": title,
        "kind": kind,
        "status": "pending",
        "source": source,
        "content": content,
        "tags": tags,
        "target_files": target_files,
        "created_at": created_at,
        "updated_at": created_at,
        "resolution_note": "",
    }
    idea_log.setdefault("ideas", []).append(idea)
    write_json(idea_log_path, idea_log)

    markdown = "\n".join(
        [
            f"# {title}",
            "",
            f"- id: `{idea_id}`",
            f"- kind: `{kind}`",
            "- status: `pending`",
            f"- source: `{source}`",
            f"- created_at: `{created_at}`",
            f"- tags: {', '.join(tags) if tags else '无'}",
            f"- target_files: {', '.join(target_files) if target_files else '待判断'}",
            "",
            "## 原始想法",
            "",
            content.strip(),
            "",
            "## 初步影响面",
            "",
            "- 待分析",
            "",
            "## 处理备注",
            "",
            "- 待补充",
            "",
        ]
    )
    inbox_name = f"{idea_id}-{slugify(title)}.md"
    write_text(workspace / "inbox" / inbox_name, markdown)

    status = collect_workspace_status(workspace)
    write_json(workspace / "state/workspace-status.json", status)
    render_workspace_views(workspace, status=status)
    return {"idea": idea, "inbox_file": str((workspace / 'inbox' / inbox_name).resolve()), "status": status}


def _duplicate_values(items: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return sorted(duplicates)


def _append_issue(issues: list[dict[str, Any]], level: str, code: str, message: str, path: str | None = None) -> None:
    issues.append({"level": level, "code": code, "message": message, "path": path})


def validate_workspace(workspace: Path) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    issues: list[dict[str, Any]] = []

    for rel_path in CORE_JSON_FILES:
        if not (workspace / rel_path).exists():
            _append_issue(issues, "error", "missing-core-file", f"缺少核心文件 `{rel_path}`。", rel_path)

    canon_index = read_json(workspace / "state/canon-index.json", {"characters": []})
    idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
    events_data = read_json(workspace / "timeline/events.json", {"events": []})
    scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})

    characters = canon_index.get("characters", [])
    events = events_data.get("events", [])
    chapters = scene_index.get("chapters", [])
    scene_records = _load_scene_records(workspace)

    character_ids = [str(item.get("id")) for item in characters if item.get("id")]
    event_ids = [str(item.get("id")) for item in events if item.get("id")]
    scene_ids = [str(record["scene"].get("id")) for record in scene_records if record["scene"].get("id")]

    for duplicate in _duplicate_values(character_ids):
        _append_issue(issues, "error", "duplicate-character-id", f"角色 ID 重复：`{duplicate}`。", "state/canon-index.json")
    for duplicate in _duplicate_values(event_ids):
        _append_issue(issues, "error", "duplicate-event-id", f"事件 ID 重复：`{duplicate}`。", "timeline/events.json")
    for duplicate in _duplicate_values(scene_ids):
        _append_issue(issues, "error", "duplicate-scene-id", f"场景 ID 重复：`{duplicate}`。", "outline/scene-index.json")

    character_map = {item["id"]: item for item in characters if item.get("id")}
    event_map = {item["id"]: item for item in events if item.get("id")}
    event_order_map = {
        item["id"]: item.get("chronological_index")
        for item in events
        if item.get("id") and isinstance(item.get("chronological_index"), int)
    }

    chrono_values = [item.get("chronological_index") for item in events if isinstance(item.get("chronological_index"), int)]
    for duplicate in _duplicate_values([str(value) for value in chrono_values]):
        _append_issue(issues, "error", "duplicate-chronological-index", f"事件真实时间序号重复：`{duplicate}`。", "timeline/events.json")

    chapter_numbers = [chapter.get("chapter") for chapter in chapters]
    if chapter_numbers:
        cleaned = [number for number in chapter_numbers if isinstance(number, int)]
        if len(cleaned) != len(chapter_numbers) or cleaned != sorted(cleaned) or len(set(cleaned)) != len(cleaned):
            _append_issue(issues, "error", "invalid-chapter-order", "章节编号必须是严格递增且不重复的整数。", "outline/scene-index.json")

    for event in events:
        event_id = event.get("id")
        for participant in event.get("participants", []):
            if participant not in character_map:
                _append_issue(issues, "error", "unknown-event-participant", f"事件 `{event_id}` 引用了不存在的角色 `{participant}`。", "timeline/events.json")

    for record in scene_records:
        scene = record["scene"]
        scene_id = scene.get("id")
        for character_id in scene.get("characters", []):
            if character_id not in character_map:
                _append_issue(issues, "error", "unknown-scene-character", f"场景 `{scene_id}` 引用了不存在的角色 `{character_id}`。", "outline/scene-index.json")
        for event_id in scene.get("event_ids", []):
            if event_id not in event_map:
                _append_issue(issues, "error", "unknown-scene-event", f"场景 `{scene_id}` 引用了不存在的事件 `{event_id}`。", "outline/scene-index.json")

    for character in characters:
        death_event_id = character.get("death_event_id")
        if not death_event_id:
            continue
        if death_event_id not in event_order_map:
            _append_issue(issues, "warning", "unknown-death-event", f"角色 `{character.get('id')}` 的 death_event_id `{death_event_id}` 不存在。", "state/canon-index.json")
            continue
        death_index = event_order_map[death_event_id]
        char_id = character.get("id")
        for event in events:
            if char_id in event.get("participants", []) and isinstance(event.get("chronological_index"), int):
                if event["chronological_index"] > death_index:
                    _append_issue(issues, "error", "post-death-event-appearance", f"角色 `{char_id}` 在死亡事件之后仍参与事件 `{event.get('id')}`。", "timeline/events.json")
        for record in scene_records:
            scene = record["scene"]
            if char_id not in scene.get("characters", []):
                continue
            scene_event_indexes = [event_order_map[event_id] for event_id in scene.get("event_ids", []) if event_id in event_order_map]
            if any(index > death_index for index in scene_event_indexes):
                _append_issue(issues, "error", "post-death-scene-appearance", f"角色 `{char_id}` 在死亡事件之后仍出现在场景 `{scene.get('id')}`。", "outline/scene-index.json")

    for idea in idea_log.get("ideas", []):
        if idea.get("status") != "applied":
            continue
        if not idea.get("target_files"):
            _append_issue(issues, "error", "applied-idea-missing-target-files", f"已应用想法 `{idea.get('id')}` 缺少 target_files。", "state/idea-log.json")
        if not str(idea.get("resolution_note", "")).strip():
            _append_issue(issues, "error", "applied-idea-missing-resolution-note", f"已应用想法 `{idea.get('id')}` 缺少 resolution_note。", "state/idea-log.json")

    if not characters:
        _append_issue(issues, "warning", "no-characters", "当前还没有正式角色索引。", "state/canon-index.json")
    if not events:
        _append_issue(issues, "warning", "no-events", "当前还没有 timeline events。", "timeline/events.json")
    if not scene_records:
        _append_issue(issues, "warning", "no-scenes", "当前还没有正式 scenes。", "outline/scene-index.json")

    error_count = sum(1 for issue in issues if issue["level"] == "error")
    warning_count = sum(1 for issue in issues if issue["level"] == "warning")
    report = {
        "workspace_path": str(workspace),
        "validated_at": now_iso(),
        "ok": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
    }

    status = collect_workspace_status(workspace)
    status["last_validation"] = {
        "ok": report["ok"],
        "error_count": error_count,
        "warning_count": warning_count,
        "report_path": str((workspace / "views/validation-report.html").resolve()),
        "validated_at": report["validated_at"],
    }
    if error_count > 0:
        status["workspace_mode"] = "repair-existing"
        status["recommended_next_step"] = "先修复 validator 报出的硬冲突，再继续并入新想法。"
    write_json(workspace / "state/workspace-status.json", status)
    outputs = render_workspace_views(workspace, status=status, validation_report=report)
    report["report_path"] = outputs["validation_report"]
    return report
