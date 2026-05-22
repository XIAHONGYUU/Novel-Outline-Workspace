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


def default_canon_index(novel_name: str) -> dict[str, Any]:
    return {
        "novel_name": novel_name,
        "characters": [],
        "relationships": [],
        "knowledge_states": [],
        "world_rule_exceptions": [],
        "locations": [],
        "factions": [],
        "items": [],
    }


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


IDEA_KIND_KEYWORDS: dict[str, tuple[str, ...]] = {
    "reveal": ("真相", "身份", "秘密", "泄密", "揭露", "知道", "知情", "暴露", "发现", "意识到"),
    "scene": ("场景", "夜谈", "对话", "相遇", "初见", " confrontation", "谈判"),
    "event": ("发生", "爆发", "到达", "出发", "来袭", "遇袭", "转折"),
    "character": ("新角色", "角色", "师姐", "导师", "反派", " rival", " mentor"),
    "death": ("死", "死亡", "牺牲", "殒命"),
    "relationship": ("认识", "结盟", "背叛", "误会", "和解", "决裂"),
    "world": ("规则", "世界观", "法则", "系统", "设定"),
    "twist": ("反转", "其实", "原来", "真正", "假装"),
}

KIND_DEFAULT_TARGETS: dict[str, tuple[str, ...]] = {
    "reveal": ("outline/master-outline.md", "outline/scene-index.json", "timeline/events.json"),
    "scene": ("outline/master-outline.md", "outline/scene-index.json"),
    "event": ("timeline/events.json", "outline/scene-index.json"),
    "character": ("state/canon-index.json", "canon/characters.md"),
    "relationship": ("state/canon-index.json", "canon/characters.md", "outline/master-outline.md"),
    "world": ("state/canon-index.json", "canon/world-rules.md"),
    "death": ("state/canon-index.json", "timeline/events.json", "outline/scene-index.json"),
    "twist": ("outline/master-outline.md", "timeline/events.json"),
    "misc": ("outline/master-outline.md",),
}

STOP_TAGS = {
    "一个",
    "一些",
    "这个",
    "那个",
    "我们",
    "他们",
    "她们",
    "你们",
    "自己",
    "现在",
    "然后",
    "但是",
    "因为",
    "如果",
    "需要",
    "应该",
    "可以",
    "关于",
    "剧情",
    "大纲",
    "角色",
    "确认",
    "继续",
    "可能",
    "不会",
    "一边",
    "提前",
    "内部",
    "有人",
    "没有",
    "告诉",
}

NOISY_TAG_FRAGMENTS = (
    "在",
    "可能",
    "继续",
    "不会",
    "确认",
    "站在",
    "一边",
    "有人",
    "没有",
    "提前",
)

CN_NUM_MAP = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


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
            "consistency_index": "views/consistency-checks/index.html",
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
    canon_index = read_json(workspace / "state/canon-index.json", default_canon_index(workspace.name))
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
      --bg: #f4ecdf;
      --panel: rgba(255, 252, 247, 0.82);
      --panel-strong: rgba(255, 250, 242, 0.94);
      --ink: #1f1a17;
      --muted: #62584f;
      --line: rgba(73, 49, 29, 0.14);
      --accent: #9f3c17;
      --accent-2: #c76a19;
      --accent-soft: #f8c98d;
      --error: #b42318;
      --warn: #b45309;
      --ok: #166534;
      --shadow: 0 18px 50px rgba(79, 54, 34, 0.09);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(248, 201, 141, 0.34), transparent 28rem),
        radial-gradient(circle at top right, rgba(193, 104, 35, 0.16), transparent 20rem),
        radial-gradient(circle at bottom right, rgba(198, 126, 48, 0.16), transparent 24rem),
        linear-gradient(180deg, #fbf6ee 0%, #ede2d0 100%);
      font-family: "Iowan Old Style", "Palatino Linotype", "Baskerville", "Noto Serif SC", serif;
    }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 28px 20px 64px; }}
    header.hero {{
      position: relative;
      overflow: hidden;
      padding: 28px 30px 30px;
      border: 1px solid var(--line);
      background:
        radial-gradient(circle at 85% 20%, rgba(248, 201, 141, 0.42), transparent 13rem),
        linear-gradient(135deg, rgba(255,255,255,0.88), rgba(255,244,230,0.84));
      border-radius: 28px;
      box-shadow: var(--shadow);
    }}
    header.hero::after {{
      content: "";
      position: absolute;
      right: -40px;
      top: -40px;
      width: 180px;
      height: 180px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(159, 60, 23, 0.10), transparent 70%);
      pointer-events: none;
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
      padding: 9px 13px;
      border-radius: 999px;
      background: rgba(255,255,255,0.64);
      transition: transform 160ms ease, background 160ms ease;
    }}
    nav a:hover {{
      transform: translateY(-1px);
      background: rgba(255,255,255,0.9);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-top: 24px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.95fr);
      gap: 18px;
      margin-top: 24px;
      align-items: start;
    }}
    .stack {{
      display: grid;
      gap: 18px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 22px;
      background: var(--panel);
      backdrop-filter: blur(12px);
      padding: 18px 20px;
      box-shadow: 0 12px 30px rgba(82, 54, 31, 0.08);
    }}
    .panel.strong {{
      background: var(--panel-strong);
    }}
    .eyebrow {{
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }}
    h1, h2, h3, p {{ margin-top: 0; }}
    h1 {{ font-size: clamp(2rem, 5vw, 3.5rem); margin-bottom: 8px; }}
    h2 {{ font-size: 1.22rem; margin-bottom: 12px; }}
    h3 {{ font-size: 1rem; margin-bottom: 8px; }}
    .metric {{
      font-size: 2.15rem;
      font-weight: 700;
      margin: 8px 0 0;
    }}
    .submetric {{
      color: var(--muted);
      font-size: 0.95rem;
      margin: 6px 0 0;
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
    .badge.soft {{ background: rgba(99, 92, 84, 0.10); color: var(--muted); }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
    }}
    .hero-copy {{
      max-width: 760px;
      position: relative;
      z-index: 1;
    }}
    .hero-copy p {{
      color: var(--muted);
      font-size: 1.02rem;
      line-height: 1.6;
      margin-bottom: 0;
    }}
    .hero-rail {{
      min-width: 220px;
      display: grid;
      gap: 10px;
      position: relative;
      z-index: 1;
    }}
    .rail-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px;
      background: rgba(255,255,255,0.66);
    }}
    .rail-card strong {{
      display: block;
      font-size: 1.05rem;
      margin-bottom: 4px;
    }}
    .story-stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-top: 24px;
      position: relative;
      z-index: 1;
    }}
    .stat-card {{
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 16px 18px;
      background: rgba(255,255,255,0.66);
    }}
    .stat-card .eyebrow {{
      margin-bottom: 4px;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      margin-bottom: 14px;
    }}
    .section-head p {{
      color: var(--muted);
      font-size: 0.95rem;
      margin-bottom: 0;
    }}
    .action-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .action-card {{
      display: block;
      text-decoration: none;
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      background: rgba(255,255,255,0.62);
      transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
    }}
    .action-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 14px 28px rgba(82, 54, 31, 0.10);
      border-color: rgba(159, 60, 23, 0.24);
    }}
    .action-card strong {{
      display: block;
      margin-bottom: 6px;
      font-size: 1rem;
    }}
    .action-card span {{
      color: var(--muted);
      font-size: 0.94rem;
      line-height: 1.45;
    }}
    ul.clean {{ list-style: none; padding: 0; margin: 0; }}
    ul.clean li {{ padding: 10px 0; border-top: 1px solid var(--line); }}
    ul.clean li:first-child {{ border-top: none; padding-top: 0; }}
    .list-card {{
      display: grid;
      gap: 10px;
    }}
    .list-row {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 15px;
      background: rgba(255,255,255,0.58);
    }}
    .list-row strong {{
      display: block;
      margin-bottom: 6px;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }}
    .meta code {{
      background: rgba(62, 40, 24, 0.07);
    }}
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
    .progress-wrap {{
      display: grid;
      gap: 10px;
    }}
    .progress-row {{
      display: grid;
      gap: 7px;
    }}
    .progress-label {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      font-size: 0.95rem;
    }}
    .progress-bar {{
      height: 10px;
      border-radius: 999px;
      background: rgba(98, 88, 79, 0.12);
      overflow: hidden;
    }}
    .progress-fill {{
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--accent), var(--accent-2));
    }}
    .workspace-map {{
      display: grid;
      gap: 12px;
    }}
    .map-item {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 14px;
      background: rgba(255,255,255,0.56);
    }}
    .chapter-strip {{
      display: grid;
      gap: 10px;
    }}
    .chapter-card {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 15px;
      background: rgba(255,255,255,0.56);
    }}
    .chapter-card p {{
      color: var(--muted);
      margin-bottom: 0;
      line-height: 1.5;
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
    @media (max-width: 980px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .story-stats {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 760px) {{
      main {{
        padding: 20px 14px 44px;
      }}
      header.hero {{
        padding: 22px 18px 22px;
      }}
      .hero-top {{
        flex-direction: column;
      }}
      .hero-rail {{
        width: 100%;
        min-width: 0;
      }}
      .story-stats {{
        grid-template-columns: 1fr;
      }}
      .action-grid {{
        grid-template-columns: 1fr;
      }}
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
    ideas = read_json(workspace / "state/idea-log.json", {"ideas": []}).get("ideas", [])
    pending_ideas = [idea for idea in ideas if idea.get("status") == "pending"]
    applied_ideas = [idea for idea in ideas if idea.get("status") == "applied"]
    merge_plan_dir = workspace / "state/merge-plans"
    merge_plan_files = sorted(merge_plan_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True) if merge_plan_dir.exists() else []
    latest_merge_plans = [read_json(path, {}) for path in merge_plan_files[:4]]
    consistency_dir = workspace / "state/consistency-checks"
    consistency_files = sorted(consistency_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True) if consistency_dir.exists() else []
    latest_consistency_reports = [read_json(path, {}) for path in consistency_files[:4]]
    events = read_json(workspace / "timeline/events.json", {"events": []}).get("events", [])
    recent_events = sorted(
        events,
        key=lambda item: (
            item.get("chronological_index") if isinstance(item.get("chronological_index"), int) else 10**9,
            str(item.get("id", "")),
        ),
    )[:4]
    scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
    chapters = sorted(scene_index.get("chapters", []), key=lambda item: item.get("chapter", 10**9))
    recent_chapters = chapters[:4]

    core_ready = sum(1 for exists in status.get("core_files", {}).values() if exists)
    core_total = max(len(status.get("core_files", {})), 1)
    core_ratio = int((core_ready / core_total) * 100)
    structure_target = 12
    structure_progress = min(100, int(((entity_counts.get("events", 0) + entity_counts.get("scenes", 0)) / structure_target) * 100))
    merge_health = 100 if idea_counts.get("total", 0) == 0 else max(0, int((1 - (idea_counts.get("pending", 0) / max(idea_counts.get("total", 1), 1))) * 100))

    if last_validation.get("error_count", 0) > 0:
        state_sentence = "工作区当前处于修复期，应该先清理硬冲突，再继续推进剧情和设定。"
    elif pending_ideas:
        state_sentence = "当前最重要的是处理 merge 队列，把零散 idea 尽快转成正式 canon、timeline 和 scene。"
    elif entity_counts.get("events", 0) == 0 or entity_counts.get("scenes", 0) == 0:
        state_sentence = "故事骨架还在搭建期，建议先补关键事件和核心 scene，让时间线真正立起来。"
    else:
        state_sentence = "工作区已经进入稳定推进状态，适合继续扩写章节、补场景和做更细的冲突校验。"

    core_file_items = "\n".join(
        f"""
        <div class="map-item">
          <div>
            <strong>{_safe(path)}</strong>
            <div class="submetric">核心状态文件</div>
          </div>
          <span class="badge {'ok' if exists else 'warning'}">{'ready' if exists else 'missing'}</span>
        </div>
        """
        for path, exists in status.get("core_files", {}).items()
    ) or '<div class="empty">当前还没有核心状态文件。</div>'

    pending_idea_markup = "\n".join(
        f"""
        <div class="list-row">
          <strong>{_safe(idea.get('title'))}</strong>
          <div>{_safe(idea.get('content', ''))}</div>
          <div class="meta">
            <span class="badge warning">{_safe(idea.get('kind'))}</span>
            <code>{_safe(idea.get('id'))}</code>
          </div>
        </div>
        """
        for idea in pending_ideas[:4]
    ) or '<div class="empty">当前没有 pending ideas，merge 队列是空的。</div>'

    merge_plan_markup = "\n".join(
        f"""
        <div class="list-row">
          <strong>{_safe(plan.get('title') or plan.get('idea_id'))}</strong>
          <div>{_safe(' / '.join(plan.get('suggested_domains', [])) or '未分类')}</div>
          <div class="meta">
            <code>{_safe(plan.get('idea_id'))}</code>
            <span class="badge soft">{_safe(plan.get('created_at') or 'unknown')}</span>
          </div>
        </div>
        """
        for plan in latest_merge_plans
    ) or '<div class="empty">当前还没有 merge plans。先为 pending idea 生成计划。</div>'

    consistency_markup = "\n".join(
        f"""
        <div class="list-row">
          <strong>{_safe(report.get('title') or report.get('idea_id'))}</strong>
          <div>{_safe('conflicts ' + str(report.get('conflict_count', 0)) + ' / warnings ' + str(report.get('warning_count', 0)))}</div>
          <div class="meta">
            <code>{_safe(report.get('idea_id'))}</code>
            <span class="badge {'warning' if report.get('conflict_count', 0) > 0 or report.get('error_count', 0) > 0 else 'ok'}">{'needs review' if report.get('conflict_count', 0) > 0 or report.get('error_count', 0) > 0 else 'clear'}</span>
          </div>
        </div>
        """
        for report in latest_consistency_reports
    ) or '<div class="empty">当前还没有 idea-level consistency reports。</div>'

    event_markup = "\n".join(
        f"""
        <div class="list-row">
          <strong>{_safe(event.get('label', event.get('id')))}</strong>
          <div class="meta">
            <span class="badge soft">chronological #{_safe(event.get('chronological_index', '?'))}</span>
            <span class="badge soft">chapter {_safe(event.get('reading_chapter', '-'))}</span>
            <code>{_safe(event.get('location') or 'location unset')}</code>
          </div>
        </div>
        """
        for event in recent_events
    ) or '<div class="empty">还没有正式事件。时间线页目前会保持空白。</div>'

    chapter_markup = "\n".join(
        f"""
        <div class="chapter-card">
          <strong>第 {_safe(chapter.get('chapter'))} 章</strong>
          <div class="meta">
            <span class="badge soft">{len(chapter.get('scenes', []))} scenes</span>
            <span class="badge soft">{_safe(chapter.get('title') or '未命名章节')}</span>
          </div>
          <p>{_safe(chapter.get('summary') or '当前还没有章节摘要。')}</p>
        </div>
        """
        for chapter in recent_chapters
    ) or '<div class="empty">还没有章节卡片。先补 `outline/scene-index.json`。</div>'

    body = f"""
    <header class="hero">
      <div class="hero-top">
        <div class="hero-copy">
          <div class="eyebrow">Novel Outline Workspace</div>
          <h1>{_safe(status.get('novel_name'))}</h1>
          <p>{_safe(state_sentence)}</p>
          <nav>
            <a href="index.html">总览</a>
            <a href="validation-report.html">校验报告</a>
            <a href="timeline.html">时间线</a>
            <a href="merge-plans/">Merge Plans</a>
          </nav>
        </div>
        <div class="hero-rail">
          <div class="rail-card">
            <div class="eyebrow">Workspace Mode</div>
            <strong>{_safe(status.get('workspace_mode'))}</strong>
            {_status_badge(status)}
          </div>
          <div class="rail-card">
            <div class="eyebrow">Protagonist</div>
            <strong>{_safe(status.get('protagonist_name') or '未设置')}</strong>
            <span class="submetric">updated at {_safe(status.get('updated_at'))}</span>
          </div>
        </div>
      </div>
      <div class="story-stats">
        <article class="stat-card"><div class="eyebrow">Idea Pool</div><div class="metric">{idea_counts.get('total', 0)}</div><div class="submetric">pending {idea_counts.get('pending', 0)} / applied {idea_counts.get('applied', 0)}</div></article>
        <article class="stat-card"><div class="eyebrow">Characters</div><div class="metric">{entity_counts.get('characters', 0)}</div><div class="submetric">正式角色索引</div></article>
        <article class="stat-card"><div class="eyebrow">Events</div><div class="metric">{entity_counts.get('events', 0)}</div><div class="submetric">真实时间线节点</div></article>
        <article class="stat-card"><div class="eyebrow">Scenes</div><div class="metric">{entity_counts.get('scenes', 0)}</div><div class="submetric">正式场景节点</div></article>
      </div>
    </header>
    <section class="layout">
      <div class="stack">
        <article class="panel strong">
          <div class="section-head">
            <div>
              <div class="eyebrow">Command Desk</div>
              <h2>下一步应该做什么</h2>
            </div>
            <span class="badge {'error' if last_validation.get('error_count', 0) > 0 else 'warning' if pending_ideas else 'ok'}">{_safe(status.get('workspace_mode'))}</span>
          </div>
          <div class="action-grid">
            <a class="action-card" href="validation-report.html">
              <strong>检查冲突与校验</strong>
              <span>先看当前有没有硬错误、引用失效或结构缺口。</span>
            </a>
            <a class="action-card" href="timeline.html">
              <strong>推进时间线</strong>
              <span>把关键事件和阅读章节挂起来，避免剧情发展失焦。</span>
            </a>
            <a class="action-card" href="merge-plans/">
              <strong>处理 Merge 队列</strong>
              <span>把 pending idea 变成正式的 merge plan 和可执行补丁。</span>
            </a>
            <a class="action-card" href="consistency-checks/index.html">
              <strong>先看 Consistency</strong>
              <span>在并入之前先检查单条 idea 是否和现有 canon、timeline、scene 冲突。</span>
            </a>
            <a class="action-card" href="../state/workspace-status.json">
              <strong>检查状态源</strong>
              <span>直接回到 JSON 真相源确认 mode、counts 和最新校验时间。</span>
            </a>
          </div>
          <p class="submetric" style="margin-top: 16px;">{_safe(status.get('recommended_next_step'))}</p>
        </article>
        <article class="panel">
          <div class="section-head">
            <div>
              <div class="eyebrow">Merge Desk</div>
              <h2>Pending Ideas</h2>
            </div>
            <span class="badge {'warning' if pending_ideas else 'ok'}">{len(pending_ideas)} waiting</span>
          </div>
          <div class="list-card">{pending_idea_markup}</div>
        </article>
        <article class="panel">
          <div class="section-head">
            <div>
              <div class="eyebrow">Story Surface</div>
              <h2>最近事件与章节</h2>
            </div>
            <p>首页优先呈现当前最关键的剧情骨架。</p>
          </div>
          <div class="grid" style="margin-top: 0;">
            <div class="panel strong">
              <h3>Recent Events</h3>
              <div class="list-card">{event_markup}</div>
            </div>
            <div class="panel strong">
              <h3>Chapter Snapshot</h3>
              <div class="chapter-strip">{chapter_markup}</div>
            </div>
          </div>
        </article>
      </div>
      <div class="stack">
        <article class="panel">
          <div class="section-head">
            <div>
              <div class="eyebrow">Health</div>
              <h2>工作区健康度</h2>
            </div>
            <span class="badge {'error' if last_validation.get('error_count', 0) > 0 else 'ok'}">{'repair needed' if last_validation.get('error_count', 0) > 0 else 'stable'}</span>
          </div>
          <div class="progress-wrap">
            <div class="progress-row">
              <div class="progress-label"><span>Core Files</span><span>{core_ratio}%</span></div>
              <div class="progress-bar"><div class="progress-fill" style="width: {core_ratio}%;"></div></div>
            </div>
            <div class="progress-row">
              <div class="progress-label"><span>Structure Coverage</span><span>{structure_progress}%</span></div>
              <div class="progress-bar"><div class="progress-fill" style="width: {structure_progress}%;"></div></div>
            </div>
            <div class="progress-row">
              <div class="progress-label"><span>Merge Queue Health</span><span>{merge_health}%</span></div>
              <div class="progress-bar"><div class="progress-fill" style="width: {merge_health}%;"></div></div>
            </div>
          </div>
          <div class="meta" style="margin-top: 14px;">
            <span class="badge {'error' if last_validation.get('error_count', 0) > 0 else 'ok'}">errors {last_validation.get('error_count', 0)}</span>
            <span class="badge {'warning' if last_validation.get('warning_count', 0) > 0 else 'ok'}">warnings {last_validation.get('warning_count', 0)}</span>
            <span class="badge soft">applied {len(applied_ideas)}</span>
          </div>
        </article>
        <article class="panel">
          <div class="section-head">
            <div>
              <div class="eyebrow">Consistency Gate</div>
              <h2>Recent Consistency Checks</h2>
            </div>
            <span class="badge soft">{len(latest_consistency_reports)} visible</span>
          </div>
          <div class="list-card">{consistency_markup}</div>
        </article>
        <article class="panel">
          <div class="section-head">
            <div>
              <div class="eyebrow">Latest Plans</div>
              <h2>Merge Plans</h2>
            </div>
            <span class="badge soft">{len(latest_merge_plans)} visible</span>
          </div>
          <div class="list-card">{merge_plan_markup}</div>
        </article>
        <article class="panel">
          <div class="section-head">
            <div>
              <div class="eyebrow">Workspace Map</div>
              <h2>核心文件状态</h2>
            </div>
            <p>确保工作台始终有可用的状态源。</p>
          </div>
          <div class="workspace-map">{core_file_items}</div>
        </article>
        <article class="panel">
          <div class="section-head">
            <div>
              <div class="eyebrow">Latest Validation</div>
              <h2>校验摘要</h2>
            </div>
          </div>
          <p>validated_at: <code>{_safe(last_validation.get('validated_at') or '未运行')}</code></p>
          <p>report_path: <code>{_safe(last_validation.get('report_path') or '未生成')}</code></p>
          <p class="submetric">{_safe(status.get('recommended_next_step'))}</p>
        </article>
      </div>
    </section>
    <section class="grid">
      <article class="panel">
        <div class="section-head">
          <div>
            <div class="eyebrow">Reality Check</div>
            <h2>工作区事实面</h2>
          </div>
          <span class="badge soft">source of truth</span>
        </div>
        <p>当前事实层以 `state/*.json`、`timeline/events.json`、`outline/scene-index.json` 为准。HTML 负责展示，不反向作为编辑真相源。</p>
      </article>
      <article class="panel">
        <div class="section-head">
          <div>
            <div class="eyebrow">Operating Note</div>
            <h2>操作节奏</h2>
          </div>
        </div>
        <p>推荐节奏：先收 idea，再做 merge plan，再结构化 apply，最后跑 validator 和 HTML 重渲染。</p>
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
    canon_index = read_json(workspace / "state/canon-index.json", default_canon_index(workspace.name))
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


def _render_consistency_index_html(workspace: Path, status: dict[str, Any]) -> str:
    consistency_dir = workspace / "state/consistency-checks"
    report_files = sorted(consistency_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True) if consistency_dir.exists() else []
    reports = [read_json(path, {}) for path in report_files]
    rows = "\n".join(
        f"""
        <tr>
          <td><code>{_safe(report.get('idea_id'))}</code></td>
          <td>{_safe(report.get('title'))}</td>
          <td>{_safe(report.get('conflict_count', 0))}</td>
          <td>{_safe(report.get('warning_count', 0))}</td>
          <td><span class="badge {'warning' if report.get('conflict_count', 0) > 0 or report.get('error_count', 0) > 0 else 'ok'}">{'needs review' if report.get('conflict_count', 0) > 0 or report.get('error_count', 0) > 0 else 'clear'}</span></td>
          <td><a href="{_safe(Path(report.get('view_path', '')).name or '')}">详情</a></td>
        </tr>
        """
        for report in reports
    )
    body = f"""
    <header class="hero">
      <div class="eyebrow">Consistency Gate</div>
      <h1>{_safe(status.get('novel_name'))} Consistency Checks</h1>
      <p>这里汇总每条 idea 在 merge 前做的独立 consistency 检查。</p>
      <nav>
        <a href="../index.html">总览</a>
        <a href="../validation-report.html">校验报告</a>
        <a href="../timeline.html">时间线</a>
      </nav>
    </header>
    <section class="panel" style="margin-top: 24px;">
      <h2>Reports</h2>
      {f'<table><thead><tr><th>Idea</th><th>Title</th><th>Conflicts</th><th>Warnings</th><th>Status</th><th>View</th></tr></thead><tbody>{rows}</tbody></table>' if rows else '<div class="empty">当前还没有 consistency reports。</div>'}
    </section>
    """
    return _html_page(f"{status.get('novel_name')} · Consistency Checks", body)


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
    consistency_index_path = workspace / "views/consistency-checks/index.html"

    write_text(index_path, _render_status_html(workspace, status))
    write_text(validation_path, _render_validation_html(validation_report, status))
    write_text(timeline_path, _render_timeline_html(workspace, status))
    write_text(consistency_index_path, _render_consistency_index_html(workspace, status))
    return {
        "consistency_index": str(consistency_index_path.resolve()),
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


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def infer_idea_kind(title: str, content: str, explicit_kind: str | None = None) -> str:
    if explicit_kind and explicit_kind != "auto":
        return explicit_kind

    haystack = f"{title}\n{content}".lower()
    best_kind = "misc"
    best_score = 0
    for kind, keywords in IDEA_KIND_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in haystack)
        if score > best_score:
            best_kind = kind
            best_score = score
    return best_kind


def infer_idea_tags(
    title: str,
    content: str,
    existing_tags: list[str] | None = None,
    protagonist_name: str | None = None,
) -> list[str]:
    tags = list(existing_tags or [])
    text = f"{title} {content}"
    if protagonist_name and protagonist_name in text:
        tags.append(protagonist_name)

    if 2 <= len(title.strip()) <= 12:
        tags.append(title.strip())

    location_like = re.findall(r"[\u4e00-\u9fff]{2,8}(?:港口|议会|议事厅|白塔|皇城|主城|学宫|宫|府|城|镇|村|山|海|岛|厅|院)", text)
    role_like = re.findall(r"(?:师姐|师兄|师父|导师|议会|主角|反派|林舟)", text)
    relation_like = re.findall(r"(?:背叛|结盟|决裂|和解|知情|真相|黑潮|泄密)", text)

    for chunk in location_like + role_like + relation_like:
        if chunk in STOP_TAGS:
            continue
        if any(fragment in chunk for fragment in NOISY_TAG_FRAGMENTS):
            continue
        tags.append(chunk)

    for kind, keywords in IDEA_KIND_KEYWORDS.items():
        if any(keyword.lower() in text.lower() for keyword in keywords):
            tags.append(kind)

    return _dedupe_keep_order(tags[:8])


def infer_target_files(kind: str, title: str, content: str, explicit_targets: list[str] | None = None) -> list[str]:
    targets = list(explicit_targets or [])
    targets.extend(KIND_DEFAULT_TARGETS.get(kind, KIND_DEFAULT_TARGETS["misc"]))
    text = f"{title} {content}"
    if any(token in text for token in ["地点", "港口", "城", "塔", "山", "海"]):
        targets.append("timeline/events.json")
    if any(token in text for token in ["规则", "法则", "系统", "设定"]):
        targets.append("canon/world-rules.md")
    return _dedupe_keep_order(targets)


def infer_suggested_domains(kind: str, target_files: list[str]) -> list[str]:
    domains: list[str] = []
    for target in target_files:
        if target.startswith("timeline/"):
            domains.append("timeline")
        elif target.startswith("outline/"):
            domains.append("outline")
        elif target.startswith("canon/") or target.startswith("state/canon"):
            domains.append("canon")
    if kind == "relationship":
        domains.extend(["canon", "outline"])
    return _dedupe_keep_order(domains)


def _parse_chinese_number(text: str) -> int | None:
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if "十" in text:
        parts = text.split("十", 1)
        left = CN_NUM_MAP.get(parts[0], 1 if parts[0] == "" else None)
        right = CN_NUM_MAP.get(parts[1], 0 if parts[1] == "" else None)
        if left is None or right is None:
            return None
        return left * 10 + right
    total = 0
    for char in text:
        value = CN_NUM_MAP.get(char)
        if value is None:
            return None
        total = total * 10 + value
    return total or None


def infer_chapter_hints(title: str, content: str) -> list[int]:
    hints: list[int] = []
    for match in re.findall(r"第\s*([0-9]{1,4}|[零一二两三四五六七八九十]{1,3})\s*章", f"{title} {content}"):
        parsed = _parse_chinese_number(match)
        if parsed is not None:
            hints.append(parsed)
    deduped = _dedupe_keep_order([str(item) for item in hints])
    return [int(item) for item in deduped]


def infer_location_candidates(title: str, content: str) -> list[str]:
    text = f"{title} {content}"
    suffixes = ("港口", "议事厅", "白塔", "皇城", "主城", "学宫", "宫", "府", "城", "镇", "村", "山", "海", "岛", "厅", "院")
    suffix_group = "|".join(sorted((re.escape(suffix) for suffix in suffixes), key=len, reverse=True))
    location_core = rf"[\u4e00-\u9fff]{{0,6}}(?:{suffix_group})"
    patterns = (
        rf"第\s*[0-9零一二两三四五六七八九十]+\s*章\s*({location_core})",
        rf"(?:在|到|从|向|往|于)\s*({location_core})",
        rf"({location_core})",
    )
    candidates: list[str] = []
    for pattern in patterns:
        for chunk in re.findall(pattern, text):
            chunk = re.sub(r"^第[零一二两三四五六七八九十0-9]+章", "", chunk)
            chunk = re.sub(r"^(在|到|从|向|往|于)", "", chunk)
            if len(chunk) < 2:
                continue
            if any(fragment in chunk for fragment in NOISY_TAG_FRAGMENTS + ("意识到", "第一次", "知道", "确认")):
                continue
            candidates.append(chunk)
    return _dedupe_keep_order(candidates[:5])


def infer_character_mentions(title: str, content: str, protagonist_name: str | None = None) -> list[str]:
    text = f"{title} {content}"
    candidates: list[str] = []
    if protagonist_name and protagonist_name in text:
        candidates.append(protagonist_name)
    candidates.extend(re.findall(r"(师姐|师兄|师父|导师|主角|反派|议长|议会)", text))
    return _dedupe_keep_order(candidates[:6])


def build_intake_draft(
    *,
    idea_id: str,
    title: str,
    content: str,
    kind: str,
    tags: list[str],
    target_files: list[str],
    suggested_domains: list[str],
    protagonist_name: str | None,
) -> dict[str, Any]:
    chapter_hints = infer_chapter_hints(title, content)
    location_candidates = infer_location_candidates(title, content)
    character_mentions = infer_character_mentions(title, content, protagonist_name)
    candidate_scene_title = title if kind in {"scene", "reveal", "event", "twist"} else None
    candidate_event_label = title if kind in {"event", "reveal", "death", "twist"} else None

    canon_updates: list[dict[str, Any]] = []
    if kind in {"character", "relationship"}:
        for name in character_mentions:
            canon_updates.append(
                {
                    "type": "character-link",
                    "label": name,
                    "suggested_file": "state/canon-index.json",
                }
            )
    if kind == "world":
        canon_updates.append(
            {
                "type": "world-rule-note",
                "label": title,
                "suggested_file": "canon/world-rules.md",
            }
        )

    timeline_candidates: list[dict[str, Any]] = []
    if "timeline" in suggested_domains:
        timeline_candidates.append(
            {
                "event_label": candidate_event_label or title,
                "reading_chapter_hint": chapter_hints[0] if chapter_hints else None,
                "location_candidates": location_candidates,
                "participant_candidates": character_mentions,
            }
        )

    outline_candidates: list[dict[str, Any]] = []
    if "outline" in suggested_domains:
        outline_candidates.append(
            {
                "scene_title": candidate_scene_title or title,
                "chapter_hints": chapter_hints,
                "pov_candidates": character_mentions[:2],
                "target_outline_files": [path for path in target_files if path.startswith("outline/")],
            }
        )

    open_questions: list[str] = []
    if "timeline" in suggested_domains and not chapter_hints:
        open_questions.append("这条想法落在哪一章或哪一个时间节点？")
    if "timeline" in suggested_domains and not location_candidates:
        open_questions.append("这条想法发生在什么地点？")
    if "timeline" in suggested_domains and not character_mentions:
        open_questions.append("这条想法涉及哪些角色参与？")
    if "canon" in suggested_domains and kind in {"character", "relationship"} and not character_mentions:
        open_questions.append("新人物或关系具体关联到哪些主要角色？")

    confidence = "medium"
    if chapter_hints or location_candidates or character_mentions:
        confidence = "medium-high"
    if len(open_questions) >= 3:
        confidence = "low-medium"

    return {
        "idea_id": idea_id,
        "title": title,
        "kind": kind,
        "tags": tags,
        "target_files": target_files,
        "suggested_domains": suggested_domains,
        "chapter_hints": chapter_hints,
        "location_candidates": location_candidates,
        "character_mentions": character_mentions,
        "canon_update_candidates": canon_updates,
        "timeline_candidates": timeline_candidates,
        "outline_candidates": outline_candidates,
        "open_questions": open_questions,
        "confidence": confidence,
        "created_at": now_iso(),
    }


def _render_intake_draft_html(draft: dict[str, Any]) -> str:
    questions = "\n".join(f"<li>{_safe(question)}</li>" for question in draft.get("open_questions", [])) or "<li>无</li>"
    body = f"""
    <header class="hero">
      <div class="eyebrow">Idea Intake Draft</div>
      <h1>{_safe(draft.get('title'))}</h1>
      <p>idea id: <code>{_safe(draft.get('idea_id'))}</code> · inferred kind: <code>{_safe(draft.get('kind'))}</code></p>
      <nav>
        <a href="../index.html">总览</a>
        <a href="../validation-report.html">校验报告</a>
        <a href="../timeline.html">时间线</a>
      </nav>
    </header>
    <section class="grid">
      <article class="panel"><div class="eyebrow">Confidence</div><div class="metric">{_safe(draft.get('confidence'))}</div></article>
      <article class="panel"><div class="eyebrow">Chapter Hints</div><div class="metric">{len(draft.get('chapter_hints', []))}</div><div class="submetric">{_safe(', '.join(str(item) for item in draft.get('chapter_hints', [])) or '无')}</div></article>
      <article class="panel"><div class="eyebrow">Locations</div><div class="metric">{len(draft.get('location_candidates', []))}</div><div class="submetric">{_safe(', '.join(draft.get('location_candidates', [])) or '无')}</div></article>
      <article class="panel"><div class="eyebrow">Characters</div><div class="metric">{len(draft.get('character_mentions', []))}</div><div class="submetric">{_safe(', '.join(draft.get('character_mentions', [])) or '无')}</div></article>
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Suggested Domains</h2>
      <p>{_safe(', '.join(draft.get('suggested_domains', [])) or '无')}</p>
      <h2>Target Files</h2>
      <p>{_safe(', '.join(draft.get('target_files', [])) or '无')}</p>
    </section>
    <section class="panel" style="margin-top: 24px;">
      <h2>Open Questions</h2>
      <ul class="clean">{questions}</ul>
    </section>
    """
    return _html_page(f"{draft.get('title')} · Intake Draft", body)


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
    status = collect_workspace_status(workspace)
    normalized_kind = infer_idea_kind(title, content, kind)
    tags = infer_idea_tags(title, content, tags, status.get("protagonist_name"))
    target_files = infer_target_files(normalized_kind, title, content, target_files)
    suggested_domains = infer_suggested_domains(normalized_kind, target_files)

    idea_id = _next_idea_id(idea_log.get("ideas", []))
    created_at = now_iso()
    intake_draft = build_intake_draft(
        idea_id=idea_id,
        title=title,
        content=content,
        kind=normalized_kind,
        tags=tags,
        target_files=target_files,
        suggested_domains=suggested_domains,
        protagonist_name=status.get("protagonist_name"),
    )
    intake_draft_path = workspace / "state/intake-drafts" / f"{idea_id}.json"
    intake_draft_view_path = workspace / "views/intake-drafts" / f"{idea_id}.html"
    write_json(intake_draft_path, intake_draft)
    write_text(intake_draft_view_path, _render_intake_draft_html(intake_draft))
    idea = {
        "id": idea_id,
        "title": title,
        "kind": normalized_kind,
        "status": "pending",
        "source": source,
        "content": content,
        "tags": tags,
        "target_files": target_files,
        "suggested_domains": suggested_domains,
        "intake_draft_path": str(intake_draft_path.resolve()),
        "intake_draft_view_path": str(intake_draft_view_path.resolve()),
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
            f"- kind: `{normalized_kind}`",
            "- status: `pending`",
            f"- source: `{source}`",
            f"- created_at: `{created_at}`",
            f"- tags: {', '.join(tags) if tags else '无'}",
            f"- target_files: {', '.join(target_files) if target_files else '待判断'}",
            f"- suggested_domains: {', '.join(suggested_domains) if suggested_domains else '待判断'}",
            f"- intake_draft: `{intake_draft_path}`",
            f"- intake_draft_view: `{intake_draft_view_path}`",
            "",
            "## 原始想法",
            "",
            content.strip(),
            "",
            "## Intake 结果",
            "",
            f"- inferred kind: `{normalized_kind}`",
            f"- inferred tags: {', '.join(tags) if tags else '无'}",
            f"- inferred target files: {', '.join(target_files) if target_files else '无'}",
            f"- inferred domains: {', '.join(suggested_domains) if suggested_domains else '无'}",
            f"- chapter hints: {', '.join(str(item) for item in intake_draft.get('chapter_hints', [])) if intake_draft.get('chapter_hints') else '无'}",
            f"- location candidates: {', '.join(intake_draft.get('location_candidates', [])) if intake_draft.get('location_candidates') else '无'}",
            f"- character mentions: {', '.join(intake_draft.get('character_mentions', [])) if intake_draft.get('character_mentions') else '无'}",
            f"- confidence: `{intake_draft.get('confidence')}`",
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


def _resolve_intake_paths(workspace: Path, idea: dict[str, Any]) -> tuple[Path, Path]:
    idea_id = str(idea.get("id") or "").strip()
    configured_draft = idea.get("intake_draft_path")
    configured_view = idea.get("intake_draft_view_path")

    draft_path = Path(configured_draft).expanduser() if configured_draft else workspace / "state/intake-drafts" / f"{idea_id}.json"
    if not draft_path.is_absolute():
        draft_path = (workspace / draft_path).resolve()

    view_path = Path(configured_view).expanduser() if configured_view else workspace / "views/intake-drafts" / f"{idea_id}.html"
    if not view_path.is_absolute():
        view_path = (workspace / view_path).resolve()

    return draft_path, view_path


def _idea_needs_intake_repair(workspace: Path, idea: dict[str, Any]) -> bool:
    draft_path, view_path = _resolve_intake_paths(workspace, idea)
    if not str(idea.get("intake_draft_path") or "").strip():
        return True
    if not str(idea.get("intake_draft_view_path") or "").strip():
        return True
    return not draft_path.exists() or not view_path.exists()


def _merge_intake_draft(existing: dict[str, Any], inferred: dict[str, Any]) -> dict[str, Any]:
    merged = dict(inferred)
    for key in ["title", "kind", "tags", "target_files", "suggested_domains"]:
        if existing.get(key):
            merged[key] = existing[key]
    for key in [
        "chapter_hints",
        "location_candidates",
        "character_mentions",
        "canon_update_candidates",
        "timeline_candidates",
        "outline_candidates",
        "open_questions",
    ]:
        if existing.get(key):
            merged[key] = existing[key]
    if existing.get("confidence"):
        merged["confidence"] = existing["confidence"]
    if existing.get("created_at"):
        merged["created_at"] = existing["created_at"]
    if existing.get("content"):
        merged["content"] = existing["content"]
    return merged


def backfill_intake_drafts(
    workspace: Path,
    *,
    idea_ids: list[str] | None = None,
    include_all_pending: bool = False,
    include_all_ideas: bool = False,
    force_rebuild: bool = False,
) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    idea_log_path = workspace / "state/idea-log.json"
    idea_log = read_json(idea_log_path, {"ideas": []})
    ideas = idea_log.get("ideas", [])
    status = collect_workspace_status(workspace)
    protagonist_name = status.get("protagonist_name")

    explicit_ids = [str(item).strip() for item in idea_ids or [] if str(item).strip()]
    if explicit_ids:
        selected: list[tuple[int, dict[str, Any]]] = []
        for requested_id in explicit_ids:
            match_index = next((index for index, item in enumerate(ideas) if item.get("id") == requested_id), None)
            if match_index is None:
                raise ValueError(f"unknown idea id: {requested_id}")
            selected.append((match_index, ideas[match_index]))
    elif include_all_ideas:
        selected = list(enumerate(ideas))
    elif include_all_pending:
        selected = [(index, item) for index, item in enumerate(ideas) if item.get("status") == "pending"]
    else:
        selected = [
            (index, item)
            for index, item in enumerate(ideas)
            if item.get("status") == "pending" and _idea_needs_intake_repair(workspace, item)
        ]

    repaired: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    changed = False
    repair_selected_even_if_present = bool(explicit_ids or include_all_pending or include_all_ideas or force_rebuild)

    for index, idea in selected:
        draft_path, view_path = _resolve_intake_paths(workspace, idea)
        existing_draft = read_json(draft_path, {}) if draft_path.exists() else {}
        if existing_draft and not force_rebuild and not repair_selected_even_if_present and not _idea_needs_intake_repair(workspace, idea):
            skipped.append({"idea_id": idea.get("id"), "reason": "draft and view already exist"})
            continue

        title = str(idea.get("title") or "").strip()
        content = str(idea.get("content") or "").strip()
        normalized_kind = infer_idea_kind(title, content, str(idea.get("kind") or "auto"))
        tags = infer_idea_tags(title, content, idea.get("tags"), protagonist_name)
        target_files = infer_target_files(normalized_kind, title, content, idea.get("target_files"))
        suggested_domains = infer_suggested_domains(normalized_kind, target_files)
        inferred_draft = build_intake_draft(
            idea_id=str(idea.get("id")),
            title=title,
            content=content,
            kind=normalized_kind,
            tags=tags,
            target_files=target_files,
            suggested_domains=suggested_domains,
            protagonist_name=protagonist_name,
        )
        draft = inferred_draft if force_rebuild or not existing_draft else _merge_intake_draft(existing_draft, inferred_draft)
        if not draft.get("content"):
            draft["content"] = content

        draft_path.parent.mkdir(parents=True, exist_ok=True)
        view_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(draft_path, draft)
        write_text(view_path, _render_intake_draft_html(draft))

        updated_idea = dict(idea)
        updated_idea["kind"] = normalized_kind
        updated_idea["tags"] = tags
        updated_idea["target_files"] = target_files
        updated_idea["suggested_domains"] = suggested_domains
        updated_idea["intake_draft_path"] = str(draft_path.resolve())
        updated_idea["intake_draft_view_path"] = str(view_path.resolve())
        updated_idea["updated_at"] = now_iso()
        ideas[index] = updated_idea
        changed = True
        repaired.append(
            {
                "idea_id": updated_idea["id"],
                "draft_path": str(draft_path.resolve()),
                "view_path": str(view_path.resolve()),
                "kind": normalized_kind,
                "force_rebuilt": bool(force_rebuild and existing_draft),
            }
        )

    if changed:
        write_json(idea_log_path, idea_log)

    refreshed_status = collect_workspace_status(workspace)
    write_json(workspace / "state/workspace-status.json", refreshed_status)
    render_workspace_views(workspace, status=refreshed_status)
    return {
        "workspace_path": str(workspace),
        "selected_count": len(selected),
        "repaired_count": len(repaired),
        "skipped_count": len(skipped),
        "repaired": repaired,
        "skipped": skipped,
        "status": refreshed_status,
    }


def _duplicate_values(items: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if item in seen:
            duplicates.add(item)
        seen.add(item)
    return sorted(duplicates)


def _append_issue(
    issues: list[dict[str, Any]],
    level: str,
    code: str,
    message: str,
    path: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    issue = {"level": level, "code": code, "message": message, "path": path}
    if details:
        issue["details"] = details
    issues.append(issue)


def validate_workspace(workspace: Path) -> dict[str, Any]:
    workspace = workspace.expanduser().resolve()
    issues: list[dict[str, Any]] = []

    for rel_path in CORE_JSON_FILES:
        if not (workspace / rel_path).exists():
            _append_issue(issues, "error", "missing-core-file", f"缺少核心文件 `{rel_path}`。", rel_path)

    canon_index = read_json(workspace / "state/canon-index.json", default_canon_index(workspace.name))
    idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
    events_data = read_json(workspace / "timeline/events.json", {"events": []})
    scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
    constraints = read_json(workspace / "constraints/constraints.json", {"rules": []})

    characters = canon_index.get("characters", [])
    relationships = canon_index.get("relationships", [])
    knowledge_states = canon_index.get("knowledge_states", [])
    world_rule_exceptions = canon_index.get("world_rule_exceptions", [])
    events = events_data.get("events", [])
    chapters = scene_index.get("chapters", [])
    scene_records = _load_scene_records(workspace)

    character_ids = [str(item.get("id")) for item in characters if item.get("id")]
    relationship_ids = [str(item.get("id")) for item in relationships if item.get("id")]
    knowledge_state_ids = [str(item.get("id")) for item in knowledge_states if item.get("id")]
    world_rule_exception_ids = [str(item.get("id")) for item in world_rule_exceptions if item.get("id")]
    event_ids = [str(item.get("id")) for item in events if item.get("id")]
    scene_ids = [str(record["scene"].get("id")) for record in scene_records if record["scene"].get("id")]
    rule_ids = {str(item.get("id")) for item in constraints.get("rules", []) if item.get("id")}

    for duplicate in _duplicate_values(character_ids):
        _append_issue(issues, "error", "duplicate-character-id", f"角色 ID 重复：`{duplicate}`。", "state/canon-index.json")
    for duplicate in _duplicate_values(relationship_ids):
        _append_issue(issues, "error", "duplicate-relationship-id", f"关系 ID 重复：`{duplicate}`。", "state/canon-index.json")
    for duplicate in _duplicate_values(knowledge_state_ids):
        _append_issue(issues, "error", "duplicate-knowledge-state-id", f"知情记录 ID 重复：`{duplicate}`。", "state/canon-index.json")
    for duplicate in _duplicate_values(world_rule_exception_ids):
        _append_issue(issues, "error", "duplicate-world-rule-exception-id", f"规则例外 ID 重复：`{duplicate}`。", "state/canon-index.json")
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

    for relationship in relationships:
        relationship_id = relationship.get("id")
        relation_character_ids = relationship.get("character_ids", [])
        if len(relation_character_ids) < 2:
            _append_issue(issues, "error", "invalid-relationship-characters", f"关系 `{relationship_id}` 至少需要两个角色。", "state/canon-index.json")
        for character_id in relation_character_ids:
            if character_id not in character_map:
                _append_issue(issues, "error", "unknown-relationship-character", f"关系 `{relationship_id}` 引用了不存在的角色 `{character_id}`。", "state/canon-index.json")
        relationship_event_id = relationship.get("event_id")
        if relationship_event_id and relationship_event_id not in event_map:
            _append_issue(issues, "error", "unknown-relationship-event", f"关系 `{relationship_id}` 引用了不存在的事件 `{relationship_event_id}`。", "state/canon-index.json")

    for knowledge_state in knowledge_states:
        knowledge_state_id = knowledge_state.get("id")
        subject_id = str(knowledge_state.get("subject_id") or "").strip()
        if not subject_id or subject_id not in character_map:
            _append_issue(
                issues,
                "error",
                "unknown-knowledge-state-subject",
                f"知情记录 `{knowledge_state_id}` 引用了不存在的角色 `{subject_id or 'unknown'}`。",
                "state/canon-index.json",
            )
        if not isinstance(knowledge_state.get("reading_chapter"), int):
            _append_issue(
                issues,
                "error",
                "invalid-knowledge-state-chapter",
                f"知情记录 `{knowledge_state_id}` 缺少合法的 `reading_chapter`。",
                "state/canon-index.json",
            )
        if not str(knowledge_state.get("object_key") or "").strip():
            _append_issue(
                issues,
                "error",
                "invalid-knowledge-state-object",
                f"知情记录 `{knowledge_state_id}` 缺少 `object_key`。",
                "state/canon-index.json",
            )
        knowledge_event_id = knowledge_state.get("event_id")
        if knowledge_event_id and knowledge_event_id not in event_map:
            _append_issue(
                issues,
                "error",
                "unknown-knowledge-state-event",
                f"知情记录 `{knowledge_state_id}` 引用了不存在的事件 `{knowledge_event_id}`。",
                "state/canon-index.json",
            )

    for exception in world_rule_exceptions:
        exception_id = exception.get("id")
        rule_id = str(exception.get("rule_id") or "").strip()
        if not rule_id or rule_id not in rule_ids:
            _append_issue(
                issues,
                "error",
                "unknown-world-rule-exception-rule",
                f"规则例外 `{exception_id}` 引用了不存在的约束 `{rule_id or 'unknown'}`。",
                "state/canon-index.json",
            )
        subject_id = str(exception.get("subject_id") or "").strip()
        if subject_id and subject_id not in character_map:
            _append_issue(
                issues,
                "error",
                "unknown-world-rule-exception-subject",
                f"规则例外 `{exception_id}` 引用了不存在的角色 `{subject_id}`。",
                "state/canon-index.json",
            )
        if not isinstance(exception.get("reading_chapter"), int):
            _append_issue(
                issues,
                "error",
                "invalid-world-rule-exception-chapter",
                f"规则例外 `{exception_id}` 缺少合法的 `reading_chapter`。",
                "state/canon-index.json",
            )
        exception_event_id = exception.get("event_id")
        if exception_event_id and exception_event_id not in event_map:
            _append_issue(
                issues,
                "error",
                "unknown-world-rule-exception-event",
                f"规则例外 `{exception_id}` 引用了不存在的事件 `{exception_event_id}`。",
                "state/canon-index.json",
            )

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
