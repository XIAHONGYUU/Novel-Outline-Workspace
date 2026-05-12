#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace.merge import apply_idea_merge


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a semi-automatic merge for one idea.")
    parser.add_argument("--workspace", required=True, help="Workspace directory.")
    parser.add_argument("--idea-id", required=True, help="Idea id to apply.")
    parser.add_argument("--resolution-note", required=True, help="How this idea was resolved.")
    parser.add_argument("--character-id", help="Character id to add or update.")
    parser.add_argument("--character-name", help="Character name to add or update.")
    parser.add_argument("--character-role", default="support", help="Character role.")
    parser.add_argument("--character-status", default="alive", help="Character status.")
    parser.add_argument("--death-event-id", help="Linked death event id.")
    parser.add_argument("--event-id", help="Event id to add or update.")
    parser.add_argument("--event-label", help="Event label.")
    parser.add_argument("--chronological-index", type=int, help="Chronological order index.")
    parser.add_argument("--reading-chapter", type=int, help="Reading chapter number.")
    parser.add_argument("--location", help="Event location.")
    parser.add_argument("--participant-id", action="append", default=[], help="Repeatable participant character id.")
    parser.add_argument("--chapter-number", type=int, help="Chapter number to place the scene in.")
    parser.add_argument("--scene-id", help="Scene id to add or update.")
    parser.add_argument("--scene-title", help="Scene title.")
    parser.add_argument("--scene-pov", help="Scene POV.")
    parser.add_argument("--scene-status", default="planned", help="Scene status.")
    parser.add_argument("--scene-character-id", action="append", default=[], help="Repeatable scene character id.")
    parser.add_argument("--scene-event-id", action="append", default=[], help="Repeatable scene event id.")
    parser.add_argument("--canon-note", help="Extra canon note written into markdown.")
    parser.add_argument("--outline-note", help="Extra outline note written into markdown.")
    parser.add_argument("--override-consistency-gate", action="store_true", help="Apply merge even if consistency gate is blocked.")
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    args = parser.parse_args()

    result = apply_idea_merge(
        Path(args.workspace),
        idea_id=args.idea_id,
        resolution_note=args.resolution_note,
        override_consistency_gate=args.override_consistency_gate,
        character_id=args.character_id,
        character_name=args.character_name,
        character_role=args.character_role,
        character_status=args.character_status,
        death_event_id=args.death_event_id,
        event_id=args.event_id,
        event_label=args.event_label,
        chronological_index=args.chronological_index,
        reading_chapter=args.reading_chapter,
        location=args.location,
        participant_ids=args.participant_id,
        chapter_number=args.chapter_number,
        scene_id=args.scene_id,
        scene_title=args.scene_title,
        scene_pov=args.scene_pov,
        scene_status=args.scene_status,
        scene_character_ids=args.scene_character_id,
        scene_event_ids=args.scene_event_id,
        canon_note=args.canon_note,
        outline_note=args.outline_note,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Applied idea: {result['idea']['id']}")
        print(f"Updated files: {', '.join(result['updated_files']) if result['updated_files'] else '无'}")
        print(f"Validation report: {result['validation_report']['report_path']}")
    return 0 if result["validation_report"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
