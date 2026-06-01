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
    parser.add_argument(
        "--merge-input-id",
        action="append",
        default=[],
        help="Repeatable structured merge input id from state/merge-plans/<idea-id>.json.",
    )
    parser.add_argument("--rule-id", help="Constraint rule id to add or update.")
    parser.add_argument("--rule-type", default="hard-canon", help="Constraint rule type.")
    parser.add_argument("--rule-label", help="Constraint rule label.")
    parser.add_argument("--rule-applies-until-event-id", help="Constraint cutoff event id.")
    parser.add_argument("--rule-notes", help="Constraint rule notes.")
    parser.add_argument("--relationship-id", help="Relationship id to add or update.")
    parser.add_argument("--relationship-character-id", action="append", default=[], help="Repeatable relationship character id.")
    parser.add_argument("--relationship-state", help="Relationship state key such as allied / met / acquainted.")
    parser.add_argument("--relationship-reading-chapter", type=int, help="Relationship beat chapter number.")
    parser.add_argument("--relationship-event-id", help="Linked event id for the relationship beat.")
    parser.add_argument("--relationship-notes", help="Extra relationship note stored in canon index.")
    parser.add_argument("--knowledge-state-id", help="Knowledge-state id to add or update.")
    parser.add_argument("--knowledge-subject-id", help="Knowledge-state subject character id.")
    parser.add_argument("--knowledge-subject-name", help="Knowledge-state subject display name.")
    parser.add_argument("--knowledge-object-key", help="Canonical knowledge object key.")
    parser.add_argument("--knowledge-object-phrase", help="Original knowledge object phrase.")
    parser.add_argument("--knowledge-verb", help="Knowledge verb such as 知道 / 发现.")
    parser.add_argument("--knowledge-reading-chapter", type=int, help="Knowledge-state chapter number.")
    parser.add_argument("--knowledge-event-id", help="Linked event id for the knowledge-state beat.")
    parser.add_argument("--knowledge-notes", help="Extra knowledge-state note stored in canon index.")
    parser.add_argument("--world-rule-exception-id", help="World-rule exception id to add or update.")
    parser.add_argument("--world-rule-exception-subject-id", help="World-rule exception subject character id.")
    parser.add_argument("--world-rule-exception-subject-name", help="World-rule exception subject display name.")
    parser.add_argument("--world-rule-exception-object-key", help="Canonical world-rule exception object key.")
    parser.add_argument("--world-rule-exception-object-phrase", help="Original world-rule exception object phrase.")
    parser.add_argument("--world-rule-exception-reading-chapter", type=int, help="World-rule exception chapter number.")
    parser.add_argument("--world-rule-exception-event-id", help="Linked event id for the world-rule exception beat.")
    parser.add_argument("--world-rule-exception-notes", help="Extra world-rule exception note stored in canon index.")
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
        merge_input_ids=args.merge_input_id,
        override_consistency_gate=args.override_consistency_gate,
        rule_id=args.rule_id,
        rule_type=args.rule_type,
        rule_label=args.rule_label,
        rule_applies_until_event_id=args.rule_applies_until_event_id,
        rule_notes=args.rule_notes,
        relationship_id=args.relationship_id,
        relationship_character_ids=args.relationship_character_id,
        relationship_state=args.relationship_state,
        relationship_reading_chapter=args.relationship_reading_chapter,
        relationship_event_id=args.relationship_event_id,
        relationship_notes=args.relationship_notes,
        knowledge_state_id=args.knowledge_state_id,
        knowledge_subject_id=args.knowledge_subject_id,
        knowledge_subject_name=args.knowledge_subject_name,
        knowledge_object_key=args.knowledge_object_key,
        knowledge_object_phrase=args.knowledge_object_phrase,
        knowledge_verb=args.knowledge_verb,
        knowledge_reading_chapter=args.knowledge_reading_chapter,
        knowledge_event_id=args.knowledge_event_id,
        knowledge_notes=args.knowledge_notes,
        world_rule_exception_id=args.world_rule_exception_id,
        world_rule_exception_subject_id=args.world_rule_exception_subject_id,
        world_rule_exception_subject_name=args.world_rule_exception_subject_name,
        world_rule_exception_object_key=args.world_rule_exception_object_key,
        world_rule_exception_object_phrase=args.world_rule_exception_object_phrase,
        world_rule_exception_reading_chapter=args.world_rule_exception_reading_chapter,
        world_rule_exception_event_id=args.world_rule_exception_event_id,
        world_rule_exception_notes=args.world_rule_exception_notes,
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
