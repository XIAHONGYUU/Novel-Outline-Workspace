from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = REPO_ROOT / "workspace-template"
CORE_JSON_FILES = (
    "state/canon-index.json",
    "state/idea-log.json",
    "state/workspace-status.json",
    "timeline/events.json",
    "outline/scene-index.json",
)
