from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace import check_idea_consistency
from novel_outline_workspace.constraints_review import record_constraints_review_decision, review_constraints
from novel_outline_workspace.merge import (
    _dedupe_merge_inputs,
    _build_issue_driven_timeline_merge_inputs,
    _constraints_group_explainer,
    apply_idea_merge,
    plan_idea_merge,
)
from novel_outline_workspace.orchestrator import run_outline_workspace_pipeline
from novel_outline_workspace.reuse_review import (
    _combined_remaining_review_inputs,
    _remaining_review_input_snapshots,
    record_reuse_review_decision,
    review_reuse,
)
from novel_outline_workspace.workspace import (
    backfill_intake_drafts,
    collect_workspace_status,
    ingest_idea,
    init_workspace,
    read_json,
    update_intake_draft,
    validate_workspace,
    write_json,
)


class WorkspaceTests(unittest.TestCase):
    def test_init_workspace_creates_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            status = init_workspace(workspace, "测试小说", "林舟")
            self.assertEqual(status["novel_name"], "测试小说")
            self.assertTrue((workspace / "state/canon-index.json").exists())
            self.assertTrue((workspace / "outline/scene-index.json").exists())
            self.assertTrue((workspace / "views/index.html").exists())
            self.assertTrue((workspace / "views/timeline.html").exists())

    def test_validator_detects_unknown_scene_character(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            scene_index = {
                "chapters": [
                    {
                        "chapter": 1,
                        "title": "第一章",
                        "summary": "",
                        "scenes": [
                            {
                                "id": "scene-001",
                                "title": "开场",
                                "pov": "林舟",
                                "status": "planned",
                                "characters": ["char-missing"],
                                "event_ids": [],
                                "notes": "",
                            }
                        ],
                    }
                ]
            }
            write_json(workspace / "outline/scene-index.json", scene_index)
            report = validate_workspace(workspace)
            self.assertFalse(report["ok"])
            self.assertTrue(any(issue["code"] == "unknown-scene-character" for issue in report["issues"]))
            self.assertTrue((workspace / "views/validation-report.html").exists())

    def test_validator_detects_unknown_relationship_character(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["relationships"] = [
                {
                    "id": "rel-bad",
                    "character_ids": ["char-protagonist", "char-missing"],
                    "state": "allied",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            report = validate_workspace(workspace)
            self.assertFalse(report["ok"])
            self.assertTrue(any(issue["code"] == "unknown-relationship-character" for issue in report["issues"]))

    def test_validator_detects_invalid_canon_knowledge_and_rule_exception_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["knowledge_states"] = [
                {
                    "id": "know-bad",
                    "subject_id": "char-missing",
                    "subject_name": "陌生人",
                    "object_key": "",
                    "object_phrase": "议会内部有人泄密",
                    "verb": "知道",
                    "reading_chapter": "3",
                    "event_id": "event-missing",
                    "notes": "",
                }
            ]
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-bad",
                    "rule_id": "rule-missing",
                    "rule_label": "师姐在议长遇刺前不能知道议会内部有人泄密",
                    "subject_id": "char-missing",
                    "subject_name": "师姐",
                    "object_key": "议会内部有人泄密",
                    "object_phrase": "议会内部有人泄密",
                    "reading_chapter": "3",
                    "event_id": "event-missing",
                    "notes": "",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)

            report = validate_workspace(workspace)
            codes = {issue["code"] for issue in report["issues"]}
            self.assertIn("unknown-knowledge-state-subject", codes)
            self.assertIn("invalid-knowledge-state-chapter", codes)
            self.assertIn("invalid-knowledge-state-object", codes)
            self.assertIn("unknown-knowledge-state-event", codes)
            self.assertIn("unknown-world-rule-exception-rule", codes)
            self.assertIn("unknown-world-rule-exception-subject", codes)
            self.assertIn("invalid-world-rule-exception-chapter", codes)
            self.assertIn("unknown-world-rule-exception-event", codes)

    def test_status_reflects_pending_idea(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
            idea_log["ideas"].append(
                {
                    "id": "idea-20260511-001",
                    "title": "测试想法",
                    "kind": "scene",
                    "status": "pending",
                    "source": "manual",
                    "content": "内容",
                    "tags": [],
                    "target_files": [],
                    "created_at": "2026-05-11T00:00:00Z",
                    "updated_at": "2026-05-11T00:00:00Z",
                    "resolution_note": "",
                }
            )
            write_json(workspace / "state/idea-log.json", idea_log)
            status = collect_workspace_status(workspace)
            self.assertEqual(status["idea_counts"]["pending"], 1)
            self.assertEqual(status["workspace_mode"], "extend-existing")

    def test_backfill_intake_drafts_repairs_legacy_pending_idea(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
            idea_log["ideas"].append(
                {
                    "id": "idea-20260511-099",
                    "title": "师徒关系裂缝",
                    "kind": "character",
                    "status": "pending",
                    "source": "legacy",
                    "content": "师姐在白塔议事厅确认林舟可能不会继续站在议会一边",
                    "tags": [],
                    "target_files": ["state/canon-index.json"],
                    "suggested_domains": ["canon"],
                    "created_at": "2026-05-11T00:00:00Z",
                    "updated_at": "2026-05-11T00:00:00Z",
                    "resolution_note": "",
                }
            )
            write_json(workspace / "state/idea-log.json", idea_log)

            result = backfill_intake_drafts(workspace)
            self.assertEqual(result["selected_count"], 1)
            self.assertEqual(result["repaired_count"], 1)

            repaired_idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
            repaired_idea = next(item for item in repaired_idea_log["ideas"] if item["id"] == "idea-20260511-099")
            self.assertTrue(repaired_idea["intake_draft_path"].endswith("idea-20260511-099.json"))
            self.assertTrue(repaired_idea["intake_draft_view_path"].endswith("idea-20260511-099.html"))
            draft_path = Path(repaired_idea["intake_draft_path"])
            view_path = Path(repaired_idea["intake_draft_view_path"])
            self.assertTrue(draft_path.exists())
            self.assertTrue(view_path.exists())
            draft = read_json(draft_path, {})
            self.assertIn("白塔议事厅", draft["location_candidates"])
            self.assertIn("林舟", draft["character_mentions"])
            self.assertIn("师姐", draft["character_mentions"])

    def test_backfill_intake_drafts_force_rebuilds_existing_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["chapter_hints"] = [9]
            draft["location_candidates"] = ["旧港口"]
            write_json(draft_path, draft)

            repaired = backfill_intake_drafts(workspace, include_all_pending=True, force_rebuild=True)
            self.assertEqual(repaired["repaired_count"], 1)
            rebuilt_draft = read_json(draft_path, {})
            self.assertEqual(rebuilt_draft["chapter_hints"], [3])
            self.assertIn("白塔议事厅", rebuilt_draft["location_candidates"])

    def test_intake_prefers_compound_location_and_drops_nested_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")

            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft = read_json(workspace / "state" / "intake-drafts" / f"{idea_id}.json", {})
            self.assertEqual(draft["location_candidates"], ["白塔议事厅"])

    def test_intake_can_capture_archive_room_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")

            result = ingest_idea(
                workspace,
                title="发现泄密账册",
                content="林舟在第三章白塔档案室发现密账，由此知道议会内部有人泄密。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft = read_json(workspace / "state" / "intake-drafts" / f"{idea_id}.json", {})
            self.assertEqual(draft["location_candidates"], ["白塔档案室"])

    def test_merge_plan_and_apply_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            ingest_result = ingest_idea(
                workspace,
                title="女主提前知道真相",
                content="她在第七章就知道组织首领身份。",
                kind="reveal",
            )
            idea_id = ingest_result["idea"]["id"]
            consistency = check_idea_consistency(workspace, idea_id)
            self.assertTrue(consistency["ok"])

            plan = plan_idea_merge(workspace, idea_id)
            self.assertIn("canon", plan["suggested_domains"])
            self.assertTrue(plan["consistency_gate"]["can_apply_merge"])
            self.assertTrue(plan["timeline_merge_inputs"])
            self.assertIn("participant_ids", plan["timeline_merge_inputs"][0]["missing_fields"])
            canon_explainer = next(action for action in plan["proposed_actions"] if action["domain"] == "canon")
            self.assertIn("认知变化", canon_explainer["summary"])
            self.assertTrue(canon_explainer["planned_writes"])
            self.assertTrue((workspace / "state/merge-plans" / f"{idea_id}.json").exists())
            self.assertTrue((workspace / "views/merge-plans" / f"{idea_id}.html").exists())

            result = apply_idea_merge(
                workspace,
                idea_id=idea_id,
                resolution_note="并入第七章揭露节点。",
                character_id="char-heroine",
                character_name="女主",
                character_role="deuteragonist",
                event_id="event-secret-reveal",
                event_label="女主提前知道真相",
                chronological_index=7,
                reading_chapter=7,
                participant_ids=["char-heroine"],
                chapter_number=7,
                scene_id="scene-secret-reveal",
                scene_title="假装不知情",
                scene_character_ids=["char-heroine"],
                scene_event_ids=["event-secret-reveal"],
            )
            self.assertEqual(result["idea"]["status"], "applied")
            self.assertIn("timeline/events.json", result["updated_files"])
            self.assertTrue((workspace / "views/validation-report.html").exists())

    def test_apply_merge_can_consume_timeline_merge_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            ingest_result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="reveal",
            )
            idea_id = ingest_result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(report["ok"])

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = plan["timeline_merge_inputs"][0]
            self.assertEqual(merge_input["strategy"], "create-event-and-scene")
            self.assertTrue(merge_input["can_apply_directly"])
            timeline_explainer = next(action for action in plan["proposed_actions"] if action["domain"] == "timeline")
            self.assertEqual(timeline_explainer["merge_input_id"], merge_input["id"])
            self.assertEqual(timeline_explainer["readiness"], "ready")
            self.assertIn("reading_chapter: 3", timeline_explainer["planned_writes"])
            self.assertTrue(any("chapter hint 3" in signal for signal in timeline_explainer["source_signals"]))
            outline_explainer = next(action for action in plan["proposed_actions"] if action["domain"] == "outline")
            self.assertIn("scene: 白塔夜审", outline_explainer["planned_writes"])

            result = apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="按 merge input 并入白塔夜审。",
            )
            self.assertEqual(result["idea"]["applied_merge_input_id"], merge_input["id"])
            scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
            self.assertTrue(any(chapter["chapter"] == 3 for chapter in scene_index["chapters"]))
            events = read_json(workspace / "timeline/events.json", {"events": []})["events"]
            self.assertTrue(any(event["label"] == "白塔夜审" for event in events))

    def test_apply_merge_cli_accepts_knowledge_state_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(report["ok"])
            plan = plan_idea_merge(workspace, idea_id)
            event_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "create-event-and-scene")
            knowledge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "upsert-canon-knowledge-state")

            command = [
                sys.executable,
                "scripts/apply_idea_merge.py",
                "--workspace",
                str(workspace),
                "--idea-id",
                idea_id,
                "--resolution-note",
                "一次性并入 timeline 与 knowledge-state。",
                "--event-id",
                str(event_input["apply_args"]["event_id"]),
                "--event-label",
                str(event_input["apply_args"]["event_label"]),
                "--chronological-index",
                str(event_input["apply_args"]["chronological_index"]),
                "--reading-chapter",
                str(event_input["apply_args"]["reading_chapter"]),
                "--location",
                str(event_input["apply_args"]["location"]),
                "--participant-id",
                "char-protagonist",
                "--chapter-number",
                str(event_input["apply_args"]["chapter_number"]),
                "--scene-id",
                str(event_input["apply_args"]["scene_id"]),
                "--scene-title",
                str(event_input["apply_args"]["scene_title"]),
                "--scene-pov",
                str(event_input["apply_args"]["scene_pov"]),
                "--scene-status",
                str(event_input["apply_args"]["scene_status"]),
                "--scene-character-id",
                "char-protagonist",
                "--scene-event-id",
                str(event_input["apply_args"]["event_id"]),
                "--knowledge-state-id",
                str(knowledge_input["apply_args"]["knowledge_state_id"]),
                "--knowledge-subject-id",
                str(knowledge_input["apply_args"]["knowledge_subject_id"]),
                "--knowledge-subject-name",
                str(knowledge_input["apply_args"]["knowledge_subject_name"]),
                "--knowledge-object-key",
                str(knowledge_input["apply_args"]["knowledge_object_key"]),
                "--knowledge-object-phrase",
                str(knowledge_input["apply_args"]["knowledge_object_phrase"]),
                "--knowledge-verb",
                str(knowledge_input["apply_args"]["knowledge_verb"]),
                "--knowledge-reading-chapter",
                str(knowledge_input["apply_args"]["knowledge_reading_chapter"]),
                "--json",
            ]
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "applied"', completed.stdout)
            canon_index = read_json(workspace / "state/canon-index.json", {})
            self.assertTrue(canon_index["knowledge_states"])

    def test_apply_merge_cli_can_consume_multiple_merge_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(report["ok"])
            plan = plan_idea_merge(workspace, idea_id)
            event_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "create-event-and-scene")
            knowledge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "upsert-canon-knowledge-state")

            command = [
                sys.executable,
                "scripts/apply_idea_merge.py",
                "--workspace",
                str(workspace),
                "--idea-id",
                idea_id,
                "--resolution-note",
                "按两条 merge input 一次性并入。",
                "--merge-input-id",
                str(event_input["id"]),
                "--merge-input-id",
                str(knowledge_input["id"]),
                "--json",
            ]
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "applied"', completed.stdout)
            idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
            idea = next(item for item in idea_log["ideas"] if item["id"] == idea_id)
            self.assertEqual(idea["applied_merge_input_ids"], [event_input["id"], knowledge_input["id"]])
            scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
            self.assertTrue(any(chapter["chapter"] == 3 for chapter in scene_index["chapters"]))
            canon_index = read_json(workspace / "state/canon-index.json", {})
            self.assertTrue(canon_index["knowledge_states"])

    def test_relationship_merge_input_updates_canon_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚结盟",
                content="林舟和苏岚在第六章结盟。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章结盟。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(report["ok"])
            plan = plan_idea_merge(workspace, result["idea"]["id"])
            relationship_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "upsert-canon-relationship")
            self.assertTrue(relationship_input["can_apply_directly"])
            canon_explainer = next(action for action in plan["proposed_actions"] if action["domain"] == "canon")
            self.assertEqual(canon_explainer["merge_input_id"], relationship_input["id"])
            self.assertIn("relationship_id:", " / ".join(canon_explainer["planned_writes"]))
            self.assertEqual(canon_explainer["readiness"], "ready")
            merged = apply_idea_merge(
                workspace,
                idea_id=result["idea"]["id"],
                merge_input_id=relationship_input["id"],
                resolution_note="把结盟关系写入 canon。",
            )
            self.assertEqual(merged["idea"]["applied_merge_input_id"], relationship_input["id"])
            canon_index = read_json(workspace / "state/canon-index.json", {})
            self.assertTrue(canon_index["relationships"])
            self.assertEqual(canon_index["relationships"][0]["state"], "allied")
            self.assertEqual(canon_index["relationships"][0]["character_ids"], ["char-protagonist", "char-sulan"])

    def test_relationship_merge_input_reuses_existing_relationship_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-existing-alliance",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "allied",
                    "reading_chapter": 6,
                    "event_id": None,
                    "notes": "旧记录",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚结盟",
                content="林舟和苏岚在第六章结盟。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章结盟。"
            write_json(draft_path, draft)
            check_idea_consistency(workspace, result["idea"]["id"])
            plan = plan_idea_merge(workspace, result["idea"]["id"])
            relationship_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-relationship")
            self.assertEqual(relationship_input["apply_args"]["relationship_id"], "rel-existing-alliance")

    def test_relationship_repeat_beat_plan_prefers_scene_only_gate_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-existing-alliance",
                    "character_ids": ["char-protagonist", "char-shijie"],
                    "state": "allied",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "旧记录",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和师姐再次结盟",
                content="林舟和师姐在第六章再次结盟。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "师姐"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和师姐在第六章再次结盟。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))
            plan = plan_idea_merge(workspace, result["idea"]["id"])
            relationship_inputs = [
                item
                for item in plan["timeline_merge_inputs"]
                if item["strategy"] == "update-existing-relationship"
            ]
            self.assertEqual(relationship_inputs, [])
            scene_input = next(
                item
                for item in plan["timeline_merge_inputs"]
                if item["strategy"] == "create-event-and-scene"
                and item.get("source_issue_code") == "relationship-history-conflict"
            )
            self.assertTrue(scene_input["can_apply_directly"])
            self.assertTrue(scene_input["resolves_blocked_gate"])
            self.assertEqual(scene_input["target_files"], ["outline/master-outline.md", "outline/scene-index.json"])
            self.assertEqual(scene_input["apply_args"]["chapter_number"], 6)
            self.assertEqual(scene_input["apply_args"]["scene_title"], "林舟和师姐再次结盟")
            self.assertEqual(scene_input["apply_args"]["scene_character_ids"], ["char-protagonist", "char-shijie"])
            outline_explainer = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "outline" and action["merge_input_id"] == scene_input["id"]
            )
            self.assertEqual(outline_explainer["readiness"], "ready")

    def test_apply_repeat_relationship_beat_keeps_existing_canon_relationship_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-existing-alliance",
                    "character_ids": ["char-protagonist", "char-shijie"],
                    "state": "allied",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "旧记录",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和师姐再次结盟",
                content="林舟和师姐在第六章再次结盟，准备一起公开追查议会内部泄密。",
                kind="relationship",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "师姐"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和师姐在第六章再次结盟，准备一起公开追查议会内部泄密。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            scene_input = next(
                item
                for item in plan["timeline_merge_inputs"]
                if item["strategy"] == "create-event-and-scene"
                and item.get("source_issue_code") == "relationship-history-conflict"
            )

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=scene_input["id"],
                resolution_note="保留第5章既有结盟关系，只把第6章再次结盟作为新的场景 beat 写入 outline。",
            )

            updated_canon_index = read_json(workspace / "state/canon-index.json", {})
            relationships = updated_canon_index.get("relationships", [])
            self.assertEqual(len(relationships), 1)
            self.assertEqual(relationships[0]["id"], "rel-existing-alliance")
            self.assertEqual(relationships[0]["reading_chapter"], 5)

            scene_index = read_json(workspace / "outline/scene-index.json", {})
            chapter_six = next(chapter for chapter in scene_index["chapters"] if chapter["chapter"] == 6)
            scene = next(scene for scene in chapter_six["scenes"] if scene["id"] == scene_input["apply_args"]["scene_id"])
            self.assertEqual(scene["title"], "林舟和师姐再次结盟")
            self.assertEqual(scene["characters"], ["char-protagonist", "char-shijie"])

            followup_report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in followup_report["issues"]))

    def test_relationship_state_transition_appends_new_canon_history_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-existing-alliance",
                    "character_ids": ["char-protagonist", "char-shijie"],
                    "state": "allied",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "旧记录",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和师姐决裂",
                content="林舟和师姐在第七章决裂，公开翻脸。",
                kind="relationship",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "师姐"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟和师姐在第七章决裂，公开翻脸。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(report["ok"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            scene_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "create-event-and-scene")
            relationship_input = next(
                item for item in plan["timeline_merge_inputs"] if item["strategy"] == "upsert-canon-relationship"
            )
            self.assertEqual(relationship_input["apply_args"]["relationship_id"], "rel-char-protagonist-char-shijie-ruptured-ch7")
            self.assertEqual(relationship_input["apply_args"]["relationship_state"], "ruptured")
            self.assertEqual(relationship_input["apply_args"]["relationship_reading_chapter"], 7)

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_ids=[scene_input["id"], relationship_input["id"]],
                resolution_note="把第7章决裂同时写入 scene 与新的 canon relationship 历史节点。",
            )

            updated_canon_index = read_json(workspace / "state/canon-index.json", {})
            relationships = updated_canon_index.get("relationships", [])
            self.assertEqual(len(relationships), 2)
            self.assertEqual(relationships[0]["id"], "rel-existing-alliance")
            self.assertEqual(relationships[0]["state"], "allied")
            self.assertEqual(relationships[0]["reading_chapter"], 5)
            self.assertEqual(relationships[1]["id"], "rel-char-protagonist-char-shijie-ruptured-ch7")
            self.assertEqual(relationships[1]["state"], "ruptured")
            self.assertEqual(relationships[1]["reading_chapter"], 7)

            scene_index = read_json(workspace / "outline/scene-index.json", {})
            chapter_seven = next(chapter for chapter in scene_index["chapters"] if chapter["chapter"] == 7)
            scene = next(scene for scene in chapter_seven["scenes"] if scene["id"] == scene_input["apply_args"]["scene_id"])
            self.assertEqual(scene["title"], "林舟和师姐决裂")
            self.assertEqual(scene["characters"], ["char-protagonist", "char-shijie"])

    def test_relationship_history_chain_can_append_reconciled_node_after_rupture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-existing-alliance",
                    "character_ids": ["char-protagonist", "char-shijie"],
                    "state": "allied",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "旧记录",
                },
                {
                    "id": "rel-existing-rupture",
                    "character_ids": ["char-protagonist", "char-shijie"],
                    "state": "ruptured",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "后续决裂",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和师姐和解",
                content="林舟和师姐在第九章和解，再次联手。",
                kind="relationship",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "师姐"]
            draft["chapter_hints"] = [9]
            draft["content"] = "林舟和师姐在第九章和解，再次联手。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(report["ok"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            scene_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "create-event-and-scene")
            relationship_input = next(
                item for item in plan["timeline_merge_inputs"] if item["strategy"] == "upsert-canon-relationship"
            )
            self.assertEqual(relationship_input["apply_args"]["relationship_id"], "rel-char-protagonist-char-shijie-reconciled-ch9")
            self.assertEqual(relationship_input["apply_args"]["relationship_state"], "reconciled")
            self.assertEqual(relationship_input["apply_args"]["relationship_reading_chapter"], 9)

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_ids=[scene_input["id"], relationship_input["id"]],
                resolution_note="把第9章和解同时写入 scene 与新的 canon relationship 历史节点。",
            )

            updated_canon_index = read_json(workspace / "state/canon-index.json", {})
            relationships = updated_canon_index.get("relationships", [])
            self.assertEqual(
                [item["id"] for item in relationships],
                [
                    "rel-existing-alliance",
                    "rel-existing-rupture",
                    "rel-char-protagonist-char-shijie-reconciled-ch9",
                ],
            )
            self.assertEqual(
                [item["state"] for item in relationships],
                ["allied", "ruptured", "reconciled"],
            )

            scene_index = read_json(workspace / "outline/scene-index.json", {})
            chapter_nine = next(chapter for chapter in scene_index["chapters"] if chapter["chapter"] == 9)
            scene = next(scene for scene in chapter_nine["scenes"] if scene["id"] == scene_input["apply_args"]["scene_id"])
            self.assertEqual(scene["title"], "林舟和师姐和解")
            self.assertEqual(scene["characters"], ["char-protagonist", "char-shijie"])

    def test_post_reconciliation_repeat_beat_prefers_scene_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-existing-alliance",
                    "character_ids": ["char-protagonist", "char-shijie"],
                    "state": "allied",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "旧记录",
                },
                {
                    "id": "rel-existing-rupture",
                    "character_ids": ["char-protagonist", "char-shijie"],
                    "state": "ruptured",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "后续决裂",
                },
                {
                    "id": "rel-existing-reconciled",
                    "character_ids": ["char-protagonist", "char-shijie"],
                    "state": "reconciled",
                    "reading_chapter": 9,
                    "event_id": None,
                    "notes": "后续和解",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和师姐再次和解",
                content="林舟和师姐在第十章再次和解，决定继续联手。",
                kind="relationship",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "师姐"]
            draft["chapter_hints"] = [10]
            draft["content"] = "林舟和师姐在第十章再次和解，决定继续联手。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            relationship_inputs = [
                item
                for item in plan["timeline_merge_inputs"]
                if item["strategy"] == "update-existing-relationship"
            ]
            self.assertEqual(relationship_inputs, [])

            scene_input = next(
                item
                for item in plan["timeline_merge_inputs"]
                if item["strategy"] == "create-event-and-scene"
                and item.get("source_issue_code") == "relationship-history-conflict"
            )
            self.assertTrue(scene_input["can_apply_directly"])
            self.assertTrue(scene_input["resolves_blocked_gate"])
            self.assertEqual(scene_input["apply_args"]["chapter_number"], 10)
            self.assertEqual(scene_input["apply_args"]["scene_title"], "林舟和师姐再次和解")

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=scene_input["id"],
                resolution_note="保留第9章既有和解关系，只把第10章再次和解作为新的场景 beat 写入 outline。",
            )

            updated_canon_index = read_json(workspace / "state/canon-index.json", {})
            relationships = updated_canon_index.get("relationships", [])
            self.assertEqual(
                [item["id"] for item in relationships],
                [
                    "rel-existing-alliance",
                    "rel-existing-rupture",
                    "rel-existing-reconciled",
                ],
            )

            scene_index = read_json(workspace / "outline/scene-index.json", {})
            chapter_ten = next(chapter for chapter in scene_index["chapters"] if chapter["chapter"] == 10)
            scene = next(scene for scene in chapter_ten["scenes"] if scene["id"] == scene_input["apply_args"]["scene_id"])
            self.assertEqual(scene["title"], "林舟和师姐再次和解")

            followup_report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in followup_report["issues"]))

    def test_apply_merge_input_can_move_existing_scene_across_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": [],
                                    "notes": "林舟到这里才意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-scene")
            merged = apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="把白塔夜审前移到第三章。",
                override_consistency_gate=True,
            )
            self.assertEqual(merged["idea"]["applied_merge_input_id"], merge_input["id"])
            scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
            scene_locations = [
                chapter["chapter"]
                for chapter in scene_index["chapters"]
                for scene in chapter.get("scenes", [])
                if scene.get("id") == "scene-faction-truth"
            ]
            self.assertEqual(scene_locations, [3])

    def test_scene_title_match_skips_existing_scene_when_inferred_location_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-night-trial-old-harbor",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": [],
                                    "notes": "林舟在旧港口第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(
                any(
                    issue["code"] == "timeline-order-conflict"
                    and issue.get("details", {}).get("record_type") == "scene"
                    for issue in report["issues"]
                )
            )

            plan = plan_idea_merge(workspace, idea_id)
            self.assertFalse(any(item["strategy"] == "update-existing-scene" for item in plan["timeline_merge_inputs"]))
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "create-event-and-scene")
            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="旧港口那条同标题 scene 不复用，白塔议事厅单独新建。",
            )

            scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
            chapter_three = next(chapter for chapter in scene_index["chapters"] if chapter["chapter"] == 3)
            chapter_seven = next(chapter for chapter in scene_index["chapters"] if chapter["chapter"] == 7)
            self.assertTrue(any(scene["id"] == "scene-night-trial-old-harbor" for scene in chapter_seven["scenes"]))
            self.assertTrue(any(scene["id"] == "scene-白塔夜审" for scene in chapter_three["scenes"]))

    def test_scene_title_match_allows_existing_scene_when_location_is_more_specific(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": [],
                                    "notes": "林舟在白塔第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(
                any(
                    issue["code"] == "timeline-order-conflict"
                    and issue.get("details", {}).get("record_type") == "scene"
                    for issue in report["issues"]
                )
            )

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-scene")
            self.assertEqual(merge_input["apply_args"]["scene_id"], "scene-faction-truth")

    def test_apply_merge_input_can_move_existing_event_across_chapters_and_realign_chronology(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟到这里才意识到议会和黑潮并非同一阵营。",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="event",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-event")
            self.assertEqual(merge_input["apply_args"]["reading_chapter"], 3)
            self.assertEqual(merge_input["apply_args"]["chronological_index"], 3)

            merged = apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="把白塔夜审前移到第三章，并同步事件顺序。",
                override_consistency_gate=True,
            )
            self.assertEqual(merged["idea"]["applied_merge_input_id"], merge_input["id"])
            events = read_json(workspace / "timeline/events.json", {"events": []})["events"]
            moved_event = next(item for item in events if item["id"] == "event-faction-truth")
            self.assertEqual(moved_event["reading_chapter"], 3)
            self.assertEqual(moved_event["chronological_index"], 3)

    def test_event_title_match_skips_existing_event_when_location_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-night-trial-old-harbor",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "旧港口",
                            "notes": "林舟在旧港口第一次意识到议会和黑潮并非同一阵营。",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="event",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))
            self.assertFalse(any(issue["code"] == "location-continuity-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            self.assertFalse(any(item["strategy"] == "update-existing-event" for item in plan["timeline_merge_inputs"]))
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "create-event-and-scene")
            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="旧港口那条同标题 event 不复用，白塔议事厅单独新建。",
            )

            events = read_json(workspace / "timeline/events.json", {"events": []})["events"]
            self.assertTrue(any(item["id"] == "event-night-trial-old-harbor" for item in events))
            self.assertTrue(any(item["id"] == "event-白塔夜审" for item in events))

    def test_event_title_match_allows_existing_event_when_location_is_more_specific(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔",
                            "notes": "林舟在白塔第一次意识到议会和黑潮并非同一阵营。",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="event",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-event")
            self.assertEqual(merge_input["apply_args"]["event_id"], "event-faction-truth")

    def test_update_existing_event_syncs_participants_from_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟到这里才意识到议会和黑潮并非同一阵营。",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟和师姐在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="event",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-event")
            self.assertEqual(merge_input["apply_args"]["participant_ids"], ["char-protagonist", "char-shijie"])

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="把白塔夜审前移到第三章，并补全师姐参与。",
                override_consistency_gate=True,
            )
            events = read_json(workspace / "timeline/events.json", {"events": []})["events"]
            moved_event = next(item for item in events if item["id"] == "event-faction-truth")
            self.assertEqual(moved_event["participants"], ["char-protagonist", "char-shijie"])

    def test_update_existing_event_backfills_empty_label_from_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-legacy",
                            "label": "",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "旧 event 缺标题。",
                        }
                    ]
                },
            )
            idea = {
                "id": "idea-001",
                "title": "白塔夜审",
                "content": "林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
            }
            draft = {
                "chapter_hints": [3],
                "location_candidates": ["白塔议事厅"],
                "character_mentions": ["林舟"],
                "timeline_candidates": [{"event_label": "白塔夜审", "participant_candidates": ["林舟"]}],
            }
            report = {
                "issues": [
                    {
                        "code": "timeline-order-conflict",
                        "details": {
                            "record_type": "event",
                            "record_id": "event-legacy",
                            "existing_chapter": 7,
                            "draft_chapter": 3,
                        },
                    }
                ],
                "patch_suggestions": [],
            }
            gate = {"warnings": [], "can_apply_merge": True, "status": "ready"}

            inputs = _build_issue_driven_timeline_merge_inputs(
                workspace,
                idea,
                ["timeline"],
                draft,
                report,
                gate,
            )
            merge_input = next(item for item in inputs if item["strategy"] == "update-existing-event")
            self.assertEqual(merge_input["apply_args"]["event_label"], "白塔夜审")
            self.assertNotIn("event_label", merge_input["missing_fields"])

    def test_update_existing_event_backfills_empty_location_from_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-legacy",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "",
                            "notes": "旧 event 缺地点。",
                        }
                    ]
                },
            )
            idea = {
                "id": "idea-003",
                "title": "白塔夜审",
                "content": "林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
            }
            draft = {
                "chapter_hints": [3],
                "location_candidates": ["白塔议事厅"],
                "character_mentions": ["林舟"],
                "timeline_candidates": [{"event_label": "白塔夜审", "participant_candidates": ["林舟"]}],
            }
            report = {
                "issues": [
                    {
                        "code": "timeline-order-conflict",
                        "details": {
                            "record_type": "event",
                            "record_id": "event-legacy",
                            "existing_chapter": 7,
                            "draft_chapter": 3,
                        },
                    }
                ],
                "patch_suggestions": [],
            }
            gate = {"warnings": [], "can_apply_merge": True, "status": "ready"}

            inputs = _build_issue_driven_timeline_merge_inputs(
                workspace,
                idea,
                ["timeline"],
                draft,
                report,
                gate,
            )
            merge_input = next(item for item in inputs if item["strategy"] == "update-existing-event")
            self.assertEqual(merge_input["apply_args"]["location"], "白塔议事厅")

    def test_update_existing_event_syncs_participants_from_linked_scene_when_draft_has_no_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-shijie"],
                            "location": "白塔议事厅",
                            "notes": "旧 event 残留成了师姐参与。",
                        }
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-faction-truth"],
                                    "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="event",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["chapter_hints"] = [3]
            draft["location_candidates"] = ["白塔议事厅"]
            for candidate in draft.get("timeline_candidates", []):
                candidate["participant_candidates"] = []
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-event")
            self.assertEqual(merge_input["apply_args"]["participant_ids"], ["char-protagonist"])

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="复用旧 event 时，把 participants 向已链接 scene 的 characters 对齐。",
                override_consistency_gate=True,
            )
            events = read_json(workspace / "timeline/events.json", {"events": []})["events"]
            moved_event = next(item for item in events if item["id"] == "event-faction-truth")
            self.assertEqual(moved_event["participants"], ["char-protagonist"])

    def test_update_existing_event_prefers_direct_linked_scene_even_when_old_scene_title_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth",
                            "label": "旧夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-shijie"],
                            "location": "白塔议事厅",
                            "notes": "旧 event 残留成了师姐参与。",
                        }
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "旧夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-faction-truth"],
                                    "notes": "旧 scene 还保留着旧标题，但 event_id 直连是对的。",
                                }
                            ],
                        }
                    ]
                },
            )
            idea = {
                "id": "idea-006",
                "title": "白塔夜审",
                "content": "在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
            }
            draft = {
                "chapter_hints": [3],
                "location_candidates": ["白塔议事厅"],
                "character_mentions": [],
                "timeline_candidates": [{"event_label": "白塔夜审", "participant_candidates": []}],
            }
            report = {
                "issues": [
                    {
                        "code": "timeline-order-conflict",
                        "details": {
                            "record_type": "event",
                            "record_id": "event-faction-truth",
                            "existing_chapter": 7,
                            "draft_chapter": 3,
                        },
                    }
                ],
                "patch_suggestions": [],
            }
            gate = {"warnings": [], "can_apply_merge": True, "status": "ready"}

            inputs = _build_issue_driven_timeline_merge_inputs(
                workspace,
                idea,
                ["timeline"],
                draft,
                report,
                gate,
            )
            merge_input = next(item for item in inputs if item["strategy"] == "update-existing-event")
            self.assertEqual(merge_input["apply_args"]["event_label"], "白塔夜审")
            self.assertEqual(merge_input["apply_args"]["participant_ids"], ["char-protagonist"])

    def test_update_existing_event_marks_participants_missing_when_linked_scenes_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-shijie"],
                            "location": "白塔议事厅",
                            "notes": "旧 event 残留成了师姐参与。",
                        }
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth-a",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-faction-truth"],
                                    "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                                },
                                {
                                    "id": "scene-faction-truth-b",
                                    "title": "白塔夜审",
                                    "pov": "师姐",
                                    "status": "planned",
                                    "characters": ["char-shijie"],
                                    "event_ids": ["event-faction-truth"],
                                    "notes": "师姐在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                                },
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="event",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["chapter_hints"] = [3]
            draft["location_candidates"] = ["白塔议事厅"]
            for candidate in draft.get("timeline_candidates", []):
                candidate["participant_candidates"] = []
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-event")
            self.assertEqual(merge_input["apply_args"]["participant_ids"], [])
            self.assertIn("participant_ids", merge_input["missing_fields"])
            self.assertTrue(any("linked scenes" in warning for warning in merge_input["warnings"]))
            self.assertEqual(merge_input["review_tokens"], ["reuse-ambiguity-linked-scenes"])
            self.assertIn("reuse-ambiguity-linked-scenes", plan["review_tokens"])
            self.assertTrue(any("linked scenes" in question for question in plan["unresolved_questions"]))
            review_action = next(action for action in plan["proposed_actions"] if action["domain"] == "review")
            self.assertEqual(review_action["readiness"], "needs-review")
            self.assertIn("review_token: reuse-ambiguity-linked-scenes", review_action["planned_writes"])

    def test_update_existing_scene_syncs_pov_and_characters_from_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "师姐",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": [],
                                    "notes": "师姐到这里才意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟和师姐在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-scene")
            self.assertEqual(merge_input["apply_args"]["scene_pov"], "林舟")
            self.assertEqual(merge_input["apply_args"]["scene_character_ids"], ["char-protagonist", "char-shijie"])

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="把白塔夜审前移到第三章，并补全 POV / 出场角色。",
                override_consistency_gate=True,
            )
            scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
            updated_scene = next(
                scene
                for chapter in scene_index["chapters"]
                for scene in chapter.get("scenes", [])
                if scene.get("id") == "scene-faction-truth"
            )
            self.assertEqual(updated_scene["pov"], "林舟")
            self.assertEqual(updated_scene["characters"], ["char-protagonist", "char-shijie"])

    def test_update_existing_scene_syncs_event_ids_from_matching_existing_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔",
                            "notes": "林舟在白塔第一次意识到议会和黑潮并非同一阵营。",
                        }
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": [],
                                    "notes": "林舟在白塔第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "knowledge-state-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            scene_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-scene")
            event_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-event")
            self.assertEqual(scene_input["apply_args"]["scene_event_ids"], ["event-faction-truth"])
            self.assertEqual(event_input["apply_args"]["event_id"], "event-faction-truth")

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_ids=[event_input["id"], scene_input["id"]],
                resolution_note="把白塔夜审前移到第三章，并让复用 scene 重新挂回同一条 event。",
                override_consistency_gate=True,
            )
            scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
            updated_scene = next(
                scene
                for chapter in scene_index["chapters"]
                for scene in chapter.get("scenes", [])
                if scene.get("id") == "scene-faction-truth"
            )
            self.assertEqual(updated_scene["event_ids"], ["event-faction-truth"])

    def test_update_existing_scene_drops_stale_event_ids_when_no_compatible_event_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-old-harbor",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "旧港口",
                            "notes": "林舟在旧港口第一次意识到议会和黑潮并非同一阵营。",
                        }
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-old-harbor"],
                                    "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            scene_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-scene")
            self.assertEqual(scene_input["apply_args"]["scene_event_ids"], [])

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=scene_input["id"],
                resolution_note="复用旧 scene，但清掉地点不兼容的旧 event 关联。",
                override_consistency_gate=True,
            )
            scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
            updated_scene = next(
                scene
                for chapter in scene_index["chapters"]
                for scene in chapter.get("scenes", [])
                if scene.get("id") == "scene-faction-truth"
            )
            self.assertEqual(updated_scene["event_ids"], [])

            validation = validate_workspace(workspace)
            self.assertTrue(validation["ok"])

    def test_update_existing_scene_drops_ambiguous_compatible_event_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth-a",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔",
                            "notes": "林舟在白塔第一次意识到议会和黑潮并非同一阵营。",
                        },
                        {
                            "id": "event-faction-truth-b",
                            "label": "白塔夜审",
                            "chronological_index": 8,
                            "reading_chapter": 8,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                        },
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-faction-truth-a", "event-faction-truth-b"],
                                    "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            scene_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-scene")
            self.assertEqual(scene_input["apply_args"]["scene_event_ids"], [])
            self.assertIn("scene_event_ids", scene_input["missing_fields"])
            self.assertTrue(any("多条同样兼容的旧事件" in warning for warning in scene_input["warnings"]))
            self.assertEqual(scene_input["review_tokens"], ["reuse-ambiguity-linked-events"])
            self.assertIn("reuse-ambiguity-linked-events", plan["review_tokens"])
            self.assertTrue(any("多条同样兼容的旧事件" in question for question in plan["unresolved_questions"]))
            review_action = next(action for action in plan["proposed_actions"] if action["domain"] == "review")
            self.assertEqual(review_action["readiness"], "needs-review")
            self.assertIn("review_token: reuse-ambiguity-linked-events", review_action["planned_writes"])

    def test_update_existing_scene_syncs_pov_and_characters_from_linked_event_when_draft_has_no_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                        }
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "师姐",
                                    "status": "planned",
                                    "characters": ["char-shijie"],
                                    "event_ids": [],
                                    "notes": "旧场景残留成了师姐视角。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["chapter_hints"] = [3]
            draft["location_candidates"] = ["白塔议事厅"]
            for candidate in draft.get("timeline_candidates", []):
                candidate["participant_candidates"] = []
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            scene_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-scene")
            self.assertEqual(scene_input["apply_args"]["scene_pov"], "林舟")
            self.assertEqual(scene_input["apply_args"]["scene_character_ids"], ["char-protagonist"])
            self.assertEqual(scene_input["apply_args"]["scene_event_ids"], ["event-faction-truth"])

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=scene_input["id"],
                resolution_note="复用旧 scene 时，把 POV / characters 向已命中的旧 event participants 对齐。",
                override_consistency_gate=True,
            )
            scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
            updated_scene = next(
                scene
                for chapter in scene_index["chapters"]
                for scene in chapter.get("scenes", [])
                if scene.get("id") == "scene-faction-truth"
            )
            self.assertEqual(updated_scene["pov"], "林舟")
            self.assertEqual(updated_scene["characters"], ["char-protagonist"])
            self.assertEqual(updated_scene["event_ids"], ["event-faction-truth"])

    def test_update_existing_scene_backfills_empty_title_from_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-legacy",
                                    "title": "",
                                    "pov": "",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": [],
                                    "notes": "旧 scene 缺标题。",
                                }
                            ],
                        }
                    ]
                },
            )
            idea = {
                "id": "idea-002",
                "title": "白塔夜审",
                "content": "林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
            }
            draft = {
                "chapter_hints": [3],
                "location_candidates": ["白塔议事厅"],
                "character_mentions": ["林舟"],
                "outline_candidates": [{"scene_title": "白塔夜审"}],
            }
            report = {
                "issues": [
                    {
                        "code": "timeline-order-conflict",
                        "details": {
                            "record_type": "scene",
                            "record_id": "scene-legacy",
                            "existing_chapter": 7,
                            "draft_chapter": 3,
                        },
                    }
                ],
                "patch_suggestions": [],
            }
            gate = {"warnings": [], "can_apply_merge": True, "status": "ready"}

            inputs = _build_issue_driven_timeline_merge_inputs(
                workspace,
                idea,
                ["outline"],
                draft,
                report,
                gate,
            )
            merge_input = next(item for item in inputs if item["strategy"] == "update-existing-scene")
            self.assertEqual(merge_input["apply_args"]["scene_title"], "白塔夜审")
            self.assertNotIn("scene_title", merge_input["missing_fields"])

    def test_update_existing_scene_backfills_empty_pov_from_existing_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-legacy",
                                    "title": "白塔夜审",
                                    "pov": "",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": [],
                                    "notes": "旧 scene 缺 POV。",
                                }
                            ],
                        }
                    ]
                },
            )
            idea = {
                "id": "idea-004",
                "title": "白塔夜审",
                "content": "第三章的白塔夜审保持主角视角。",
            }
            draft = {
                "chapter_hints": [3],
                "location_candidates": ["白塔议事厅"],
                "character_mentions": [],
                "timeline_candidates": [{"participant_candidates": []}],
                "outline_candidates": [{"scene_title": "白塔夜审"}],
            }
            report = {
                "issues": [
                    {
                        "code": "timeline-order-conflict",
                        "details": {
                            "record_type": "scene",
                            "record_id": "scene-legacy",
                            "existing_chapter": 7,
                            "draft_chapter": 3,
                        },
                    }
                ],
                "patch_suggestions": [],
            }
            gate = {"warnings": [], "can_apply_merge": True, "status": "ready"}

            inputs = _build_issue_driven_timeline_merge_inputs(
                workspace,
                idea,
                ["outline"],
                draft,
                report,
                gate,
            )
            merge_input = next(item for item in inputs if item["strategy"] == "update-existing-scene")
            self.assertEqual(merge_input["apply_args"]["scene_character_ids"], ["char-protagonist"])
            self.assertEqual(merge_input["apply_args"]["scene_pov"], "林舟")

    def test_update_existing_scene_prefers_draft_title_when_matching_linked_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-new-title",
                            "label": "白塔夜审",
                            "chronological_index": 3,
                            "reading_chapter": 3,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "新标题对应的 event。",
                        }
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-legacy",
                                    "title": "旧夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": [],
                                    "notes": "旧 scene 还保留着旧标题。",
                                }
                            ],
                        }
                    ]
                },
            )
            idea = {
                "id": "idea-005",
                "title": "白塔夜审",
                "content": "第三章白塔议事厅这场戏现在统一叫白塔夜审。",
            }
            draft = {
                "chapter_hints": [3],
                "location_candidates": ["白塔议事厅"],
                "character_mentions": ["林舟"],
                "outline_candidates": [{"scene_title": "白塔夜审"}],
            }
            report = {
                "issues": [
                    {
                        "code": "timeline-order-conflict",
                        "details": {
                            "record_type": "scene",
                            "record_id": "scene-legacy",
                            "existing_chapter": 7,
                            "draft_chapter": 3,
                        },
                    }
                ],
                "patch_suggestions": [],
            }
            gate = {"warnings": [], "can_apply_merge": True, "status": "ready"}

            inputs = _build_issue_driven_timeline_merge_inputs(
                workspace,
                idea,
                ["outline"],
                draft,
                report,
                gate,
            )
            merge_input = next(item for item in inputs if item["strategy"] == "update-existing-scene")
            self.assertEqual(merge_input["apply_args"]["scene_title"], "白塔夜审")
            self.assertEqual(merge_input["apply_args"]["scene_event_ids"], ["event-new-title"])

    def test_update_existing_scene_keeps_direct_event_id_even_when_old_event_label_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-legacy",
                            "label": "旧夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "旧 event 还保留着旧标题。",
                        }
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-legacy",
                                    "title": "旧夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-legacy"],
                                    "notes": "旧 scene / event 直连还在，但标题已过时。",
                                }
                            ],
                        }
                    ]
                },
            )
            idea = {
                "id": "idea-007",
                "title": "白塔夜审",
                "content": "第三章白塔议事厅这场戏现在统一叫白塔夜审。",
            }
            draft = {
                "chapter_hints": [3],
                "location_candidates": ["白塔议事厅"],
                "character_mentions": ["林舟"],
                "outline_candidates": [{"scene_title": "白塔夜审"}],
            }
            report = {
                "issues": [
                    {
                        "code": "timeline-order-conflict",
                        "details": {
                            "record_type": "scene",
                            "record_id": "scene-legacy",
                            "existing_chapter": 7,
                            "draft_chapter": 3,
                        },
                    }
                ],
                "patch_suggestions": [],
            }
            gate = {"warnings": [], "can_apply_merge": True, "status": "ready"}

            inputs = _build_issue_driven_timeline_merge_inputs(
                workspace,
                idea,
                ["outline"],
                draft,
                report,
                gate,
            )
            merge_input = next(item for item in inputs if item["strategy"] == "update-existing-scene")
            self.assertEqual(merge_input["apply_args"]["scene_title"], "白塔夜审")
            self.assertEqual(merge_input["apply_args"]["scene_event_ids"], ["event-legacy"])

    def test_update_existing_event_exposes_notes_sync_in_merge_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "旧事件备注。",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="旧的 event 描述。",
                kind="event",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["content"] = "林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营，并决定回头追查。"
            draft["chapter_hints"] = [3]
            draft["location_candidates"] = ["白塔议事厅"]
            draft["character_mentions"] = ["林舟"]
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-event")
            self.assertEqual(
                merge_input["apply_args"]["event_notes"],
                "林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营，并决定回头追查。",
            )

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="把白塔夜审前移到第三章，并同步事件备注。",
                override_consistency_gate=True,
            )
            events = read_json(workspace / "timeline/events.json", {"events": []})["events"]
            updated_event = next(item for item in events if item["id"] == "event-faction-truth")
            self.assertEqual(
                updated_event["notes"],
                "林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营，并决定回头追查。",
            )

    def test_update_existing_scene_exposes_notes_sync_in_merge_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": [],
                                    "notes": "旧场景备注。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="旧的 scene 描述。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["content"] = "林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营，并决定回头追查。"
            draft["chapter_hints"] = [3]
            draft["location_candidates"] = ["白塔议事厅"]
            draft["character_mentions"] = ["林舟"]
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-scene")
            self.assertEqual(
                merge_input["apply_args"]["scene_notes"],
                "林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营，并决定回头追查。",
            )

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="把白塔夜审前移到第三章，并同步场景备注。",
                override_consistency_gate=True,
            )
            scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
            updated_scene = next(
                scene
                for chapter in scene_index["chapters"]
                for scene in chapter.get("scenes", [])
                if scene.get("id") == "scene-faction-truth"
            )
            self.assertEqual(
                updated_scene["notes"],
                "林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营，并决定回头追查。",
            )

    def test_update_existing_scene_syncs_status_from_default_scene_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "draft",
                                    "characters": ["char-protagonist"],
                                    "event_ids": [],
                                    "notes": "旧场景备注。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营，并决定回头追查。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "update-existing-scene")
            self.assertEqual(merge_input["apply_args"]["scene_status"], "planned")

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="把白塔夜审前移到第三章，并把旧的 draft status 收敛回 planned。",
                override_consistency_gate=True,
            )
            scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
            updated_scene = next(
                scene
                for chapter in scene_index["chapters"]
                for scene in chapter.get("scenes", [])
                if scene.get("id") == "scene-faction-truth"
            )
            self.assertEqual(updated_scene["status"], "planned")

    def test_merge_plan_surfaces_blocked_consistency_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟提前知道组织首领身份",
                content="林舟在第七章就知道组织首领身份。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(report["ok"])
            plan = plan_idea_merge(workspace, idea_id)
            self.assertEqual(plan["consistency_gate"]["status"], "blocked")
            self.assertTrue(plan["consistency_gate"]["blockers"])

    def test_world_rule_merge_input_can_resolve_blocked_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟提前知道组织首领身份",
                content="林舟在第七章就知道组织首领身份。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章就知道组织首领身份。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(report["ok"])
            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "resolve-world-rule-by-updating-cutoff")
            self.assertTrue(merge_input["resolves_blocked_gate"])
            constraints_explainer = next(action for action in plan["proposed_actions"] if action["domain"] == "constraints" and action["merge_input_id"] == merge_input["id"])
            self.assertIn("cutoff", constraints_explainer["summary"])
            self.assertIn("rule_id: rule-001", constraints_explainer["planned_writes"])
            merged = apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="把揭露事件和规则截止点对齐到第七章。",
            )
            self.assertEqual(merged["idea"]["applied_merge_input_id"], merge_input["id"])
            constraints = read_json(workspace / "constraints/constraints.json", {"rules": []})
            rule = next(item for item in constraints["rules"] if item["id"] == "rule-001")
            self.assertEqual(rule["applies_until_event_id"], merge_input["apply_args"]["event_id"])
            events = read_json(workspace / "timeline/events.json", {"events": []})["events"]
            self.assertTrue(any(event["id"] == merge_input["apply_args"]["event_id"] for event in events))

    def test_world_rule_merge_plan_offers_multiple_resolution_strategies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟提前知道组织首领身份",
                content="林舟在第七章就知道组织首领身份。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章就知道组织首领身份。"
            write_json(draft_path, draft)
            check_idea_consistency(workspace, idea_id)
            plan = plan_idea_merge(workspace, idea_id)
            strategies = {item["strategy"] for item in plan["timeline_merge_inputs"]}
            self.assertIn("resolve-world-rule-by-delaying-event", strategies)
            self.assertIn("resolve-world-rule-by-updating-cutoff", strategies)
            self.assertIn("document-world-rule-exception", strategies)

    def test_world_rule_delay_merge_input_can_resolve_blocked_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟提前知道组织首领身份",
                content="林舟在第七章就知道组织首领身份。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章就知道组织首领身份。"
            write_json(draft_path, draft)
            check_idea_consistency(workspace, idea_id)
            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "resolve-world-rule-by-delaying-event")
            merged = apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="把知情事件延后到约束之后。",
            )
            self.assertEqual(merged["idea"]["applied_merge_input_id"], merge_input["id"])
            events = read_json(workspace / "timeline/events.json", {"events": []})["events"]
            delayed_event = next(item for item in events if item["id"] == merge_input["apply_args"]["event_id"])
            self.assertEqual(delayed_event["reading_chapter"], 11)
            scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
            chapters = [
                chapter["chapter"]
                for chapter in scene_index["chapters"]
                for scene in chapter.get("scenes", [])
                if scene.get("id") == merge_input["apply_args"]["scene_id"]
            ]
            self.assertEqual(chapters, [11])

    def test_world_rule_delay_merge_input_prefers_repaired_draft_content_for_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟提前知道组织首领身份",
                content="旧的 idea 描述。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章提前确认了组织首领身份，并决定暂时隐瞒。"
            write_json(draft_path, draft)
            check_idea_consistency(workspace, idea_id)

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "resolve-world-rule-by-delaying-event")
            self.assertEqual(
                merge_input["apply_args"]["event_notes"],
                "林舟在第七章提前确认了组织首领身份，并决定暂时隐瞒。（按硬约束延后到第 11 章。）",
            )
            self.assertEqual(
                merge_input["apply_args"]["scene_notes"],
                "林舟在第七章提前确认了组织首领身份，并决定暂时隐瞒。（按硬约束延后到第 11 章。）",
            )

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="把知情事件延后到约束之后，并沿用修过的 intake 描述。",
            )
            events = read_json(workspace / "timeline/events.json", {"events": []})["events"]
            delayed_event = next(item for item in events if item["id"] == merge_input["apply_args"]["event_id"])
            self.assertEqual(
                delayed_event["notes"],
                "林舟在第七章提前确认了组织首领身份，并决定暂时隐瞒。（按硬约束延后到第 11 章。）",
            )
            scene_index = read_json(workspace / "outline/scene-index.json", {"chapters": []})
            delayed_scene = next(
                scene
                for chapter in scene_index["chapters"]
                for scene in chapter.get("scenes", [])
                if scene.get("id") == merge_input["apply_args"]["scene_id"]
            )
            self.assertEqual(
                delayed_scene["notes"],
                "林舟在第七章提前确认了组织首领身份，并决定暂时隐瞒。（按硬约束延后到第 11 章。）",
            )

    def test_world_rule_note_merge_input_requires_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟提前知道组织首领身份",
                content="林舟在第七章就知道组织首领身份。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章就知道组织首领身份。"
            write_json(draft_path, draft)
            check_idea_consistency(workspace, idea_id)
            plan = plan_idea_merge(workspace, idea_id)
            merge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "document-world-rule-exception")
            self.assertFalse(merge_input["resolves_blocked_gate"])
            with self.assertRaises(ValueError):
                apply_idea_merge(
                    workspace,
                    idea_id=idea_id,
                    merge_input_id=merge_input["id"],
                    resolution_note="先记一条例外说明。",
                )
            merged = apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="先记一条例外说明。",
                override_consistency_gate=True,
            )
            constraints = read_json(workspace / "constraints/constraints.json", {"rules": []})
            rule = next(item for item in constraints["rules"] if item["id"] == "rule-001")
            self.assertIn("例外说明", rule["notes"])
            self.assertEqual(merged["idea"]["applied_merge_input_id"], merge_input["id"])
            canon_index = read_json(workspace / "state/canon-index.json", {})
            self.assertTrue(canon_index["world_rule_exceptions"])
            self.assertEqual(canon_index["world_rule_exceptions"][0]["rule_id"], "rule-001")
            refreshed = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in refreshed["issues"]))

    def test_world_rule_exception_lifecycle_supports_prior_exception_repeat_beat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-012",
                            "label": "黑潮真正目标正式揭露",
                            "chronological_index": 12,
                            "reading_chapter": 12,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在黑潮真正目标正式揭露前不知道黑潮真正目标",
                            "applies_until_event_id": "event-012",
                            "notes": "",
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="林舟提前知道黑潮真正目标",
                content="林舟在第十章白塔议事厅知道黑潮真正目标。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [10]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))
            plan = plan_idea_merge(workspace, idea_id)
            scene_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "create-event-and-scene")
            knowledge_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "upsert-canon-knowledge-state")
            exception_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "document-world-rule-exception")

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_ids=[scene_input["id"], knowledge_input["id"], exception_input["id"]],
                resolution_note="把第10章提前知情同时写入 scene、knowledge-state 和 exception note。",
                override_consistency_gate=True,
            )

            canon_index = read_json(workspace / "state/canon-index.json", {})
            self.assertEqual(len(canon_index["knowledge_states"]), 1)
            self.assertEqual(canon_index["knowledge_states"][0]["reading_chapter"], 10)
            self.assertEqual(len(canon_index["world_rule_exceptions"]), 1)
            self.assertEqual(canon_index["world_rule_exceptions"][0]["reading_chapter"], 10)

            recap = ingest_idea(
                workspace,
                title="林舟再次确认黑潮真正目标",
                content="林舟在第十一章白塔议事厅再次确认黑潮真正目标，决定提前布防。",
                kind="reveal",
            )
            recap_id = recap["idea"]["id"]
            recap_draft_path = workspace / "state" / "intake-drafts" / f"{recap_id}.json"
            recap_draft = read_json(recap_draft_path, {})
            recap_draft["character_mentions"] = ["林舟"]
            recap_draft["chapter_hints"] = [11]
            write_json(recap_draft_path, recap_draft)

            recap_report = check_idea_consistency(workspace, recap_id)
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in recap_report["issues"]))
            self.assertTrue(any(item["code"] == "world-rule-exemption-applied" for item in recap_report["exemptions"]))
            knowledge_issue = next(issue for issue in recap_report["issues"] if issue["code"] == "knowledge-state-conflict")
            self.assertEqual(knowledge_issue["details"]["direction"], "knowledge-repeat-beat")

            recap_plan = plan_idea_merge(workspace, recap_id)
            constraints_action = next(
                action
                for action in recap_plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=prior-exception-shared-subject-claim-match", summary_text)
            recap_scene_input = next(
                item
                for item in recap_plan["timeline_merge_inputs"]
                if item["strategy"] == "create-event-and-scene"
                and item.get("source_issue_code") == "knowledge-state-conflict"
            )

            apply_idea_merge(
                workspace,
                idea_id=recap_id,
                merge_input_id=recap_scene_input["id"],
                resolution_note="保留第10章既有 knowledge-state 与 exception，只把第11章再次确认作为后续 beat 写入 timeline/outline。",
            )

            updated_canon_index = read_json(workspace / "state/canon-index.json", {})
            self.assertEqual(len(updated_canon_index["knowledge_states"]), 1)
            self.assertEqual(updated_canon_index["knowledge_states"][0]["reading_chapter"], 10)
            self.assertEqual(len(updated_canon_index["world_rule_exceptions"]), 1)
            followup = check_idea_consistency(workspace, recap_id)
            self.assertFalse(any(issue["code"] == "knowledge-state-conflict" for issue in followup["issues"]))
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in followup["issues"]))

    def test_world_rule_merge_plan_keeps_claims_separate_for_multiple_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-leader-reveal",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        },
                        {
                            "id": "event-leak-reveal",
                            "label": "议会泄密真相揭露",
                            "chronological_index": 12,
                            "reading_chapter": 12,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        },
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-leader-reveal",
                            "notes": "",
                        },
                        {
                            "id": "rule-002",
                            "type": "hard-canon",
                            "label": "林舟在议会泄密真相揭露前不知道议会内部有人泄密",
                            "applies_until_event_id": "event-leak-reveal",
                            "notes": "",
                        },
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟双重提前知情",
                content="林舟在第七章就知道组织首领是谁，也知道议会内部有人泄密。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章就知道组织首领是谁，也知道议会内部有人泄密。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            world_rule_issues = [issue for issue in report["issues"] if issue["code"] == "world-rule-conflict"]
            self.assertEqual(len(world_rule_issues), 2)
            self.assertEqual(len(report["knowledge_claims"]), 2)

            plan = plan_idea_merge(workspace, idea_id)
            note_inputs = [item for item in plan["timeline_merge_inputs"] if item["strategy"] == "document-world-rule-exception"]
            self.assertEqual(len(note_inputs), 2)
            inputs_by_rule = {item["apply_args"]["rule_id"]: item for item in note_inputs}
            self.assertEqual(inputs_by_rule["rule-001"]["apply_args"]["world_rule_exception_object_key"], "组织首领是谁")
            self.assertEqual(inputs_by_rule["rule-002"]["apply_args"]["world_rule_exception_object_key"], "议会内部有人泄密")
            constraints_summary = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and action.get("merge_input_id") is None
            )
            shared_conflict_overview = next(
                line for line in constraints_summary["planned_writes"] if line.startswith("shared-conflict-overview")
            )
            planned_text = " / ".join(constraints_summary["planned_writes"])
            self.assertEqual(constraints_summary["readiness"], "needs-review")
            self.assertIn("timeline/events.json", constraints_summary["target_files"])
            self.assertIn("constraints/constraints.json", constraints_summary["target_files"])
            self.assertTrue(any(line.startswith("shared-conflict-overview") for line in constraints_summary["planned_writes"]))
            self.assertFalse(any(line.startswith("shared-conflict-summary") for line in constraints_summary["planned_writes"]))
            self.assertFalse(any(line.startswith("shared-conflict-structure |") for line in constraints_summary["planned_writes"]))
            self.assertEqual(planned_text.count("canon/world-rules.md"), 1)
            self.assertEqual(planned_text.count("constraints/constraints.json"), 1)
            self.assertEqual(planned_text.count("outline/master-outline.md"), 1)
            self.assertEqual(planned_text.count("outline/scene-index.json"), 1)
            self.assertEqual(planned_text.count("state/canon-index.json"), 1)
            self.assertEqual(planned_text.count("timeline/events.json"), 1)
            self.assertIn("rules=rule-001, rule-002", shared_conflict_overview)
            self.assertIn("strategies=resolve-world-rule-by-updating-cutoff, document-world-rule-exception", shared_conflict_overview)
            self.assertIn("direct=1", shared_conflict_overview)
            self.assertIn("override=1", shared_conflict_overview)
            self.assertIn("domains=canon, constraints, outline, timeline", shared_conflict_overview)
            self.assertIn("direct_impacts=cutoff-resolution:update-placement", shared_conflict_overview)
            self.assertIn("review_impacts=canon:record-exception, constraints:note-exception", shared_conflict_overview)
            self.assertIn("direct_write_shapes=cutoff-resolution:carry-forward", shared_conflict_overview)
            self.assertIn("review_write_shapes=exception-note:record", shared_conflict_overview)
            self.assertIn("domains=", planned_text)
            self.assertIn("direct_impacts=", planned_text)
            self.assertIn("review_impacts=", planned_text)
            self.assertIn("direct_write_shapes=", planned_text)
            self.assertIn("review_write_shapes=", planned_text)
            self.assertIn("targets=", planned_text)
            self.assertNotIn("rule-001:", planned_text)
            self.assertNotIn("rule-002:", planned_text)
            self.assertIn("constraints:note-exception", " / ".join(constraints_summary["planned_writes"]))
            self.assertTrue(any("world-rule conflict" in signal for signal in constraints_summary["source_signals"]))
            timeline_actions = [action for action in plan["proposed_actions"] if action["domain"] == "timeline"]
            outline_actions = [action for action in plan["proposed_actions"] if action["domain"] == "outline"]
            self.assertEqual(len(timeline_actions), 3)
            self.assertEqual(len(outline_actions), 3)
            merged_timeline_action = next(action for action in timeline_actions if "第 7 章" in action["summary"])
            self.assertEqual(merged_timeline_action["merge_input_id"], "timeline-merge-001")
            rule2_exception = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "canon" and action.get("merge_input_id") == "timeline-merge-rule-note-006"
            )
            self.assertTrue(any("议会内部有人泄密" in signal for signal in rule2_exception["source_signals"]))

    def test_constraints_group_explainer_compresses_partial_shared_conflict_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [],
            }
            draft = {
                "character_mentions": ["林舟"],
            }
            items = [
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-003", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
            ]
            summary = _constraints_group_explainer(workspace, items, report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            partial_shared = next(
                line
                for line in planned
                if line.startswith("shared-conflict-actions") and "rules=rule-001, rule-002" in line
            )
            shared_structure = next(
                line
                for line in planned
                if line.startswith("shared-conflict-structure") and "rules=rule-001, rule-002" in line
            )
            self.assertFalse(
                any(line.startswith("shared-conflict-actions") and "rules=" not in line for line in planned)
            )
            self.assertIn("direct_impacts=cutoff-resolution:update-placement", partial_shared)
            self.assertIn("direct_write_shapes=cutoff-resolution:carry-forward", partial_shared)
            self.assertIn("review_impacts=canon:record-exception, constraints:note-exception", partial_shared)
            self.assertIn("review_write_shapes=exception-note:record", partial_shared)
            self.assertIn("strategies=resolve-world-rule-by-updating-cutoff, document-world-rule-exception", shared_structure)
            self.assertIn("subject_scope=shared-subject", shared_structure)
            rule3_line = next(line for line in planned if line.startswith("rule-003:"))
            self.assertFalse(any(line == "rule-001:" for line in planned))
            self.assertFalse(any(line == "rule-002:" for line in planned))
            self.assertIn("direct_impacts=delay-resolution:update-placement", rule3_line)
            self.assertIn("direct_write_shapes=delay-resolution:rewrite-chapter", rule3_line)
            self.assertNotIn("review_impacts=", rule3_line)

    def test_constraints_group_explainer_compresses_partial_shared_conflict_write_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [],
            }
            draft = {
                "character_mentions": ["林舟", "师姐"],
            }
            items = [
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-003", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-003", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
            ]
            summary = _constraints_group_explainer(workspace, items, report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            shared_cutoff_shapes = next(
                line
                for line in planned
                if line.startswith(("shared-conflict-write-shapes", "shared-conflict-rule-actions"))
                and "rules=rule-001, rule-002" in line
            )
            shared_delay_shapes = next(
                line
                for line in planned
                if line.startswith(("shared-conflict-write-shapes", "shared-conflict-rule-actions"))
                and "rules=rule-002, rule-003" in line
            )
            self.assertIn(
                "direct_write_shapes=cutoff-resolution:carry-forward",
                shared_cutoff_shapes,
            )
            self.assertIn(
                "direct_write_shapes=delay-resolution:rewrite-chapter",
                shared_delay_shapes,
            )
            rule1_line = next(line for line in planned if line.startswith("rule-001:"))
            rule2_line = next(line for line in planned if line.startswith("rule-002:"))
            rule3_line = next(line for line in planned if line.startswith("rule-003:"))
            self.assertNotIn("direct_write_shapes=", rule1_line)
            self.assertNotIn("direct_write_shapes=", rule2_line)
            self.assertNotIn("direct_write_shapes=", rule3_line)

    def test_constraints_group_explainer_omits_duplicate_bucketed_conflict_tokens_from_rule_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [],
            }
            draft = {
                "character_mentions": ["林舟", "师姐"],
            }
            items = [
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-003", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
            ]
            summary = _constraints_group_explainer(workspace, items, report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            rule1_line = next(line for line in planned if line.startswith("rule-001:"))
            rule3_line = next(line for line in planned if line.startswith("rule-003:"))
            self.assertNotIn(" | impacts=", rule1_line)
            self.assertNotIn(" | write_shapes=", rule1_line)
            self.assertIn("direct_impacts=cutoff-resolution:update-placement", rule1_line)
            self.assertIn("review_impacts=canon:record-exception, constraints:note-exception", rule1_line)
            self.assertIn("direct_write_shapes=cutoff-resolution:carry-forward", rule1_line)
            self.assertIn("review_write_shapes=exception-note:record", rule1_line)
            self.assertNotIn(" | impacts=", rule3_line)
            self.assertNotIn(" | write_shapes=", rule3_line)
            self.assertIn("direct_impacts=delay-resolution:update-placement", rule3_line)
            self.assertIn("direct_write_shapes=delay-resolution:rewrite-chapter", rule3_line)

    def test_constraints_group_explainer_omits_duplicate_bucketed_exemption_tokens_from_rule_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-001",
                            "matched_exception_id": "world-rule-exception-001",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "same-chapter-shared-subject-local-signal",
                        },
                    }
                ],
            }
            draft = {
                "kind": "reveal",
                "character_mentions": ["林舟"],
            }
            summary = _constraints_group_explainer(workspace, [], report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            rule1_line = next(line for line in planned if line.startswith("rule-001: reuse-existing-exception"))
            self.assertNotIn(" | impacts=", rule1_line)
            self.assertNotIn(" | write_shapes=", rule1_line)
            self.assertIn(
                "review_impacts=canon:reuse-exception, canon:review-exception-evidence, constraints:reuse-exception",
                rule1_line,
            )
            self.assertIn(
                "review_write_shapes=canon:annotate-existing-exception-record, canon:keep-existing-exception-record, constraints:annotate-existing-rule-note",
                rule1_line,
            )

    def test_constraints_group_explainer_compresses_partial_shared_conflict_structure_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [],
            }
            draft = {
                "character_mentions": ["林舟", "师姐"],
            }
            items = [
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-003", "rule_subject_name": "师姐"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
            ]
            summary = _constraints_group_explainer(workspace, items, report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            shared_structure_tokens = next(
                line
                for line in planned
                if line.startswith("shared-conflict-structure-tokens")
                and "rules=rule-001, rule-002, rule-003" in line
            )
            shared_summary = next(
                line
                for line in planned
                if line.startswith("shared-conflict-rule-summary")
                and "rules=rule-001, rule-002" in line
            )
            self.assertIn("direct=1", shared_structure_tokens)
            self.assertIn("subject_scope=split-subjects", shared_structure_tokens)
            self.assertNotIn("override=1", shared_structure_tokens)
            self.assertIn("override=1", shared_summary)
            self.assertIn("subjects=林舟", shared_summary)
            rule1_line = next((line for line in planned if line.startswith("rule-001:")), "")
            rule2_line = next(line for line in planned if line.startswith("rule-002:"))
            rule3_line = next(line for line in planned if line.startswith("rule-003:"))
            self.assertNotIn("direct=1", rule1_line)
            self.assertNotIn("override=1", rule1_line)
            self.assertNotIn("subject_scope=split-subjects", rule1_line)
            self.assertNotIn("subjects=林舟", rule1_line)
            self.assertNotIn("direct=1", rule2_line)
            self.assertNotIn("override=1", rule2_line)
            self.assertNotIn("subject_scope=split-subjects", rule2_line)
            self.assertNotIn("direct=1", rule3_line)
            self.assertNotIn("override=1", rule3_line)
            self.assertNotIn("subject_scope=split-subjects", rule3_line)
            self.assertNotIn("subjects=林舟", rule2_line)
            self.assertIn("subjects=师姐", rule3_line)

    def test_constraints_group_explainer_compresses_partial_shared_conflict_rule_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [],
            }
            draft = {
                "character_mentions": ["林舟", "师姐"],
            }
            items = [
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-003", "rule_subject_name": "师姐"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
            ]
            summary = _constraints_group_explainer(workspace, items, report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            shared_subjects = next(
                line
                for line in planned
                if line.startswith("shared-conflict-rule-summary")
                and "rules=rule-001, rule-002" in line
            )
            shared_structure = next(
                line
                for line in planned
                if line.startswith("shared-conflict-structure-tokens")
                and "rules=rule-001, rule-002, rule-003" in line
            )
            self.assertIn("subjects=林舟", shared_subjects)
            self.assertIn("override=1", shared_subjects)
            self.assertIn(
                "direct=1",
                shared_structure,
            )
            rule1_line = next((line for line in planned if line.startswith("rule-001:")), "")
            rule2_line = next(line for line in planned if line.startswith("rule-002:"))
            rule3_line = next(line for line in planned if line.startswith("rule-003:"))
            self.assertNotIn("subjects=林舟", rule1_line)
            self.assertNotIn("subjects=林舟", rule2_line)
            self.assertIn(
                "strategies=resolve-world-rule-by-delaying-event, document-world-rule-exception",
                rule2_line,
            )
            self.assertNotIn(
                "strategies=resolve-world-rule-by-updating-cutoff, document-world-rule-exception",
                rule3_line,
            )
            self.assertIn("subjects=师姐", rule3_line)

    def test_constraints_group_explainer_compresses_partial_shared_conflict_rule_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [],
            }
            draft = {
                "character_mentions": ["林舟"],
            }
            items = [
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-003", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
            ]
            summary = _constraints_group_explainer(workspace, items, report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            shared_context = next(
                line
                for line in planned
                if line.startswith("shared-conflict-rule-context")
                and "rules=rule-001, rule-002" in line
            )
            self.assertIn("domains=canon, constraints", shared_context)
            self.assertIn(
                "targets=canon/world-rules.md, constraints/constraints.json, state/canon-index.json",
                shared_context,
            )
            self.assertFalse(any(line.startswith("rule-001:") for line in planned))
            self.assertFalse(any(line.startswith("rule-002:") for line in planned))
            rule3_line = next(line for line in planned if line.startswith("rule-003:"))
            self.assertNotIn("domains=canon, constraints", rule3_line)
            self.assertNotIn("canon/world-rules.md", rule3_line)
            self.assertNotIn("constraints/constraints.json", rule3_line)

    def test_constraints_group_explainer_combines_partial_shared_conflict_rule_tokens_and_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [],
            }
            draft = {
                "character_mentions": ["林舟", "师姐"],
            }
            items = [
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-003", "rule_subject_name": "师姐"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
            ]
            summary = _constraints_group_explainer(workspace, items, report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            shared_details = next(
                line
                for line in planned
                if line.startswith("shared-conflict-rule-details")
                and "rules=rule-001, rule-002" in line
            )
            self.assertIn("subjects=林舟", shared_details)
            self.assertIn(
                "strategies=resolve-world-rule-by-updating-cutoff, document-world-rule-exception",
                shared_details,
            )
            self.assertIn("domains=canon, constraints", shared_details)
            self.assertIn(
                "targets=canon/world-rules.md, constraints/constraints.json, state/canon-index.json",
                shared_details,
            )
            self.assertFalse(
                any(
                    line.startswith("shared-conflict-rule-tokens")
                    and "rules=rule-001, rule-002" in line
                    for line in planned
                )
            )
            self.assertFalse(
                any(
                    line.startswith("shared-conflict-rule-context")
                    and "rules=rule-001, rule-002" in line
                    for line in planned
                )
            )
            rule1_line = next(line for line in planned if line.startswith("rule-001:"))
            rule2_line = next(line for line in planned if line.startswith("rule-002:"))
            rule3_line = next(line for line in planned if line.startswith("rule-003:"))
            self.assertNotIn("subjects=林舟", rule1_line)
            self.assertNotIn("domains=canon, constraints", rule1_line)
            self.assertNotIn("subjects=林舟", rule2_line)
            self.assertNotIn("domains=canon, constraints", rule2_line)
            self.assertIn("direct=0", rule2_line)
            self.assertIn("override=2", rule2_line)
            self.assertNotIn("subjects=林舟", rule3_line)
            self.assertNotIn("domains=canon, constraints", rule3_line)

    def test_constraints_group_explainer_combines_partial_shared_conflict_metadata_and_actions_into_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [],
            }
            draft = {
                "character_mentions": ["林舟", "师姐"],
            }
            items = [
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-003", "rule_subject_name": "师姐"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
            ]
            summary = _constraints_group_explainer(workspace, items, report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            shared_summary = next(
                line
                for line in planned
                if line.startswith("shared-conflict-rule-summary")
                and "rules=rule-001, rule-002" in line
            )
            self.assertIn("override=1", shared_summary)
            self.assertIn("subjects=林舟", shared_summary)
            self.assertIn("domains=canon", shared_summary)
            self.assertIn(
                "targets=canon/world-rules.md, state/canon-index.json",
                shared_summary,
            )
            self.assertIn(
                "review_impacts=canon:record-exception, constraints:note-exception",
                shared_summary,
            )
            self.assertIn(
                "review_write_shapes=exception-note:record",
                shared_summary,
            )
            self.assertFalse(
                any(
                    line.startswith("shared-conflict-structure-tokens | rules=rule-001, rule-002 |")
                    for line in planned
                )
            )
            self.assertFalse(
                any(
                    line.startswith("shared-conflict-rule-details | rules=rule-001, rule-002 |")
                    for line in planned
                )
            )
            self.assertFalse(
                any(
                    line.startswith("shared-conflict-rule-actions | rules=rule-001, rule-002 |")
                    for line in planned
                )
            )
            rule1_line = next(line for line in planned if line.startswith("rule-001:"))
            rule2_line = next(line for line in planned if line.startswith("rule-002:"))
            self.assertNotIn("override=1", rule1_line)
            self.assertNotIn("subjects=林舟", rule1_line)
            self.assertNotIn("domains=canon, constraints", rule1_line)
            self.assertNotIn("review_impacts=canon:record-exception, constraints:note-exception", rule1_line)
            self.assertNotIn("override=1", rule2_line)
            self.assertNotIn("subjects=林舟", rule2_line)
            self.assertNotIn("domains=canon, constraints", rule2_line)
            self.assertNotIn("review_impacts=canon:record-exception, constraints:note-exception", rule2_line)

    def test_constraints_group_explainer_combines_global_conflict_context_and_actions_into_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [],
            }
            draft = {
                "character_mentions": ["林舟"],
            }
            items = [
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
            ]
            summary = _constraints_group_explainer(workspace, items, report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            shared_summary = next(
                line
                for line in planned
                if line.startswith("shared-conflict-summary")
            )
            self.assertFalse(any(line.startswith("shared-conflict-context") for line in planned))
            self.assertFalse(any(line.startswith("shared-conflict-actions") and "rules=" not in line for line in planned))
            self.assertIn("domains=canon, constraints, outline, timeline", shared_summary)
            self.assertIn(
                "targets=canon/world-rules.md, constraints/constraints.json, outline/master-outline.md, outline/scene-index.json, state/canon-index.json, timeline/events.json",
                shared_summary,
            )
            self.assertIn(
                "review_impacts=canon:record-exception, constraints:note-exception",
                shared_summary,
            )
            self.assertIn(
                "review_write_shapes=exception-note:record",
                shared_summary,
            )

    def test_constraints_group_explainer_combines_global_conflict_overview_when_all_rules_share_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [],
            }
            draft = {
                "character_mentions": ["林舟"],
            }
            items = [
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
            ]
            summary = _constraints_group_explainer(workspace, items, report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            shared_overview = next(
                line
                for line in planned
                if line.startswith("shared-conflict-overview")
            )
            self.assertFalse(any(line.startswith("shared-conflict-summary") for line in planned))
            self.assertFalse(any(line.startswith("shared-conflict-structure |") for line in planned))
            self.assertIn("rules=rule-001, rule-002", shared_overview)
            self.assertIn(
                "strategies=resolve-world-rule-by-updating-cutoff, document-world-rule-exception",
                shared_overview,
            )
            self.assertIn("direct=1", shared_overview)
            self.assertIn("override=1", shared_overview)
            self.assertIn("subjects=林舟", shared_overview)
            self.assertIn("subject_scope=shared-subject", shared_overview)
            self.assertIn("domains=canon, constraints, outline, timeline", shared_overview)
            self.assertIn(
                "targets=canon/world-rules.md, constraints/constraints.json, outline/master-outline.md, outline/scene-index.json, state/canon-index.json, timeline/events.json",
                shared_overview,
            )
            self.assertIn(
                "direct_impacts=cutoff-resolution:update-placement",
                shared_overview,
            )
            self.assertIn(
                "review_impacts=canon:record-exception, constraints:note-exception",
                shared_overview,
            )
            self.assertIn(
                "direct_write_shapes=cutoff-resolution:carry-forward",
                shared_overview,
            )
            self.assertIn(
                "review_write_shapes=exception-note:record",
                shared_overview,
            )
            self.assertFalse(any(line.startswith("rule-001:") for line in planned))
            self.assertFalse(any(line.startswith("rule-002:") for line in planned))

    def test_constraints_group_explainer_compresses_partial_shared_conflict_rule_impacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [],
            }
            draft = {
                "character_mentions": ["林舟"],
            }
            items = [
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-003", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-003", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
            ]
            summary = _constraints_group_explainer(workspace, items, report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            shared_impacts = next(
                line
                for line in planned
                if line.startswith(("shared-conflict-rule-impacts", "shared-conflict-rule-actions"))
                and "rules=rule-001, rule-002" in line
            )
            shared_delay_shapes = next(
                line
                for line in planned
                if line.startswith(("shared-conflict-write-shapes", "shared-conflict-rule-actions"))
                and "rules=rule-002, rule-003" in line
            )
            self.assertIn("direct_impacts=cutoff-resolution:update-placement", shared_impacts)
            self.assertIn("direct_write_shapes=delay-resolution:rewrite-chapter", shared_delay_shapes)
            rule1_line = next(line for line in planned if line.startswith("rule-001:"))
            rule2_line = next(line for line in planned if line.startswith("rule-002:"))
            rule3_line = next(line for line in planned if line.startswith("rule-003:"))
            self.assertNotIn("direct_impacts=cutoff-resolution:update-placement", rule1_line)
            self.assertNotIn("direct_impacts=cutoff-resolution:update-placement", rule2_line)
            self.assertNotIn("direct_impacts=cutoff-resolution:update-placement", rule3_line)
            self.assertNotIn("direct_write_shapes=delay-resolution:rewrite-chapter", rule3_line)

    def test_constraints_group_explainer_combines_partial_shared_conflict_impacts_and_write_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [],
            }
            draft = {
                "character_mentions": ["林舟"],
            }
            items = [
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "document-world-rule-exception",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "state/canon-index.json",
                        "constraints/constraints.json",
                        "canon/world-rules.md",
                    ],
                    "apply_args": {"rule_id": "rule-001", "rule_subject_name": "林舟"},
                    "can_apply_directly": False,
                    "requires_override": True,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-updating-cutoff",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                        "constraints/constraints.json",
                    ],
                    "apply_args": {"rule_id": "rule-002", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
                {
                    "strategy": "resolve-world-rule-by-delaying-event",
                    "source_issue_code": "world-rule-conflict",
                    "target_files": [
                        "timeline/events.json",
                        "outline/scene-index.json",
                        "outline/master-outline.md",
                    ],
                    "apply_args": {"rule_id": "rule-003", "rule_subject_name": "林舟"},
                    "can_apply_directly": True,
                    "requires_override": False,
                    "missing_fields": [],
                },
            ]
            summary = _constraints_group_explainer(workspace, items, report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            shared_actions = next(
                line
                for line in planned
                if line.startswith("shared-conflict-rule-actions")
                and "rules=rule-001, rule-002" in line
            )
            self.assertIn("direct_impacts=cutoff-resolution:update-placement", shared_actions)
            self.assertIn("direct_write_shapes=cutoff-resolution:carry-forward", shared_actions)
            self.assertFalse(
                any(
                    line.startswith("shared-conflict-rule-impacts")
                    and "rules=rule-001, rule-002" in line
                    for line in planned
                )
            )
            self.assertFalse(
                any(
                    line.startswith("shared-conflict-write-shapes")
                    and "rules=rule-001, rule-002" in line
                    for line in planned
                )
            )
            rule1_line = next(line for line in planned if line.startswith("rule-001:"))
            rule2_line = next(line for line in planned if line.startswith("rule-002:"))
            self.assertNotIn("direct_impacts=cutoff-resolution:update-placement", rule1_line)
            self.assertNotIn("direct_write_shapes=cutoff-resolution:carry-forward", rule1_line)
            self.assertNotIn("direct_impacts=cutoff-resolution:update-placement", rule2_line)
            self.assertNotIn("direct_write_shapes=cutoff-resolution:carry-forward", rule2_line)
            self.assertIn("review_impacts=canon:record-exception, constraints:note-exception", rule1_line)
            self.assertIn("review_write_shapes=exception-note:record", rule1_line)

    def test_world_rule_merge_plan_marks_split_exception_scope_for_multiple_subjects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-leak-reveal",
                            "label": "议会泄密真相揭露",
                            "chronological_index": 12,
                            "reading_chapter": 12,
                            "participants": ["char-protagonist", "char-shijie"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在议会泄密真相揭露前不知道议会内部有人泄密",
                            "applies_until_event_id": "event-leak-reveal",
                            "notes": "",
                        },
                        {
                            "id": "rule-002",
                            "type": "hard-canon",
                            "label": "师姐在议会泄密真相揭露前不知道议会内部有人泄密",
                            "applies_until_event_id": "event-leak-reveal",
                            "notes": "",
                        },
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟和师姐都提前知道泄密真相",
                content="林舟和师姐在第七章都知道议会内部有人泄密。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "师姐"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟和师姐在第七章都知道议会内部有人泄密。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            world_rule_issues = [issue for issue in report["issues"] if issue["code"] == "world-rule-conflict"]
            self.assertEqual(len(world_rule_issues), 2)
            self.assertEqual(len(report["knowledge_claims"]), 2)
            claim_pairs = {
                (claim["subject_name"], claim["object_key"])
                for claim in report["knowledge_claims"]
            }
            self.assertEqual(claim_pairs, {("林舟", "议会内部有人泄密"), ("师姐", "议会内部有人泄密")})

            plan = plan_idea_merge(workspace, idea_id)
            note_inputs = [item for item in plan["timeline_merge_inputs"] if item["strategy"] == "document-world-rule-exception"]
            self.assertEqual(len(note_inputs), 2)
            subjects_by_rule = {item["apply_args"]["rule_id"]: item["apply_args"]["world_rule_exception_subject_name"] for item in note_inputs}
            self.assertEqual(subjects_by_rule["rule-001"], "林舟")
            self.assertEqual(subjects_by_rule["rule-002"], "师姐")
            constraints_summary = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and action.get("merge_input_id") is None
            )
            summary_text = " / ".join(constraints_summary["planned_writes"])
            self.assertIn("subjects=林舟", summary_text)
            self.assertIn("subjects=师姐", summary_text)
            self.assertIn("subject_scope=split-subjects", summary_text)

    def test_world_rule_merge_plan_keeps_multiple_claims_when_coordinated_subject_uses_alias_without_dou(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": ["阿岚"],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-leak-reveal",
                            "label": "议会泄密真相揭露",
                            "chronological_index": 12,
                            "reading_chapter": 12,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在议会泄密真相揭露前不知道议会内部有人泄密",
                            "applies_until_event_id": "event-leak-reveal",
                            "notes": "",
                        },
                        {
                            "id": "rule-002",
                            "type": "hard-canon",
                            "label": "苏岚在议会泄密真相揭露前不知道议会内部有人泄密",
                            "applies_until_event_id": "event-leak-reveal",
                            "notes": "",
                        },
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟与阿岚提前知道泄密真相",
                content="林舟与阿岚在第七章知道议会内部有人泄密。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟与阿岚在第七章知道议会内部有人泄密。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            world_rule_issues = [issue for issue in report["issues"] if issue["code"] == "world-rule-conflict"]
            self.assertEqual(len(world_rule_issues), 2)
            self.assertEqual(len(report["knowledge_claims"]), 2)
            claim_pairs = {
                (claim["subject_name"], claim["object_key"])
                for claim in report["knowledge_claims"]
            }
            self.assertEqual(claim_pairs, {("林舟", "议会内部有人泄密"), ("苏岚", "议会内部有人泄密")})

            plan = plan_idea_merge(workspace, idea_id)
            note_inputs = [item for item in plan["timeline_merge_inputs"] if item["strategy"] == "document-world-rule-exception"]
            self.assertEqual(len(note_inputs), 2)
            subjects_by_rule = {
                item["apply_args"]["rule_id"]: item["apply_args"]["world_rule_exception_subject_name"]
                for item in note_inputs
            }
            self.assertEqual(subjects_by_rule["rule-001"], "林舟")
            self.assertEqual(subjects_by_rule["rule-002"], "苏岚")

    def test_consistency_check_keeps_mixed_subject_claims_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="双主体双对象",
                content="林舟在第七章知道组织首领是谁，师姐知道议会内部有人泄密。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "师姐"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章知道组织首领是谁，师姐知道议会内部有人泄密。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            claim_pairs = {
                (claim["subject_name"], claim["object_key"])
                for claim in report["knowledge_claims"]
            }
            self.assertEqual(claim_pairs, {("林舟", "组织首领是谁"), ("师姐", "议会内部有人泄密")})

    def test_consistency_check_prefers_more_specific_identity_claim_within_same_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="林舟提前知道首领身份",
                content="林舟在第七章知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章知道组织首领是谁。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(len(report["knowledge_claims"]), 1)
            self.assertEqual(report["knowledge_claims"][0]["object_key"], "组织首领是谁")

    def test_consistency_check_prefers_more_specific_leak_claim_within_same_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="林舟提前知道有人泄密",
                content="林舟在第七章知道议会有内鬼。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章知道议会有内鬼。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(len(report["knowledge_claims"]), 1)
            self.assertEqual(report["knowledge_claims"][0]["object_key"], "议会有内鬼")

    def test_consistency_check_prefers_more_specific_separate_camp_claim_within_same_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="林舟知道他们不是一路人",
                content="林舟在第七章意识到议会和黑潮不是同一阵营。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章意识到议会和黑潮不是同一阵营。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(len(report["knowledge_claims"]), 1)
            self.assertEqual(report["knowledge_claims"][0]["object_key"], "议会和黑潮不是同一阵营")

    def test_consistency_check_prefers_more_specific_same_camp_claim_within_same_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="林舟知道他们是一路人",
                content="林舟在第七章意识到议会和黑潮是同一阵营。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章意识到议会和黑潮是同一阵营。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(len(report["knowledge_claims"]), 1)
            self.assertEqual(report["knowledge_claims"][0]["object_key"], "议会和黑潮是同一阵营")

    def test_consistency_check_keeps_cross_family_claims_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="林舟知道他们是一路人",
                content="林舟在第七章知道议会有内鬼。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章知道议会有内鬼。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            claim_keys = {claim["object_key"] for claim in report["knowledge_claims"]}
            self.assertEqual(claim_keys, {"他们是一路人", "议会有内鬼"})

    def test_consistency_check_prefers_canonical_same_camp_wording_within_same_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="林舟知道议会和黑潮是一伙人",
                content="林舟在第七章意识到议会和黑潮是同一阵营。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章意识到议会和黑潮是同一阵营。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(len(report["knowledge_claims"]), 1)
            self.assertEqual(report["knowledge_claims"][0]["object_key"], "议会和黑潮是同一阵营")

    def test_consistency_check_prefers_canonical_separate_camp_wording_within_same_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="林舟知道议会和黑潮不是一伙人",
                content="林舟在第七章意识到议会和黑潮不是同一阵营。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["content"] = "林舟在第七章意识到议会和黑潮不是同一阵营。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(len(report["knowledge_claims"]), 1)
            self.assertEqual(report["knowledge_claims"][0]["object_key"], "议会和黑潮不是同一阵营")

    def test_apply_merge_requires_consistency_gate_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="测试 pending",
                content="新增一个关键场景。",
                kind="scene",
            )
            with self.assertRaises(ValueError):
                apply_idea_merge(
                    workspace,
                    idea_id=result["idea"]["id"],
                    resolution_note="直接并入。",
                    chapter_number=3,
                    scene_title="关键场景",
                    scene_character_ids=["char-protagonist"],
                )

    def test_apply_merge_can_override_consistency_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟提前知道组织首领身份",
                content="林舟在第七章就知道组织首领身份。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            check_idea_consistency(workspace, idea_id)
            merged = apply_idea_merge(
                workspace,
                idea_id=idea_id,
                resolution_note="人工确认后仍决定并入。",
                override_consistency_gate=True,
                event_id="event-early-reveal",
                event_label="林舟提前知道组织首领身份",
                chronological_index=7,
                reading_chapter=7,
                participant_ids=["char-protagonist"],
            )
            self.assertTrue(merged["idea"]["merge_gate_override"])
            self.assertEqual(merged["idea"]["consistency_gate_status"], "blocked")

    def test_orchestrator_recommends_consistency_check_before_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="测试 pending",
                content="新增一个关键场景。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            result = run_outline_workspace_pipeline(workspace)
            self.assertEqual(result["recommended_action"], "check-consistency")
            self.assertEqual(result["idea_id"], idea_id)

    def test_orchestrator_recommends_merge_after_clean_consistency_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="测试 pending",
                content="新增一个关键场景。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(report["ok"])
            pipeline = run_outline_workspace_pipeline(workspace)
            self.assertEqual(pipeline["recommended_action"], "plan-merge")
            self.assertEqual(pipeline["idea_id"], idea_id)

    def test_status_and_orchestrator_surface_missing_merge_info(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="师徒关系裂缝",
                content="师姐在白塔议事厅确认林舟可能不会继续站在议会一边",
                kind="character",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(report["ok"])

            plan = plan_idea_merge(workspace, idea_id)
            self.assertIn("chapter_number", plan["timeline_merge_inputs"][0]["missing_fields"])

            status = collect_workspace_status(workspace)
            self.assertIn("章节号", status["recommended_next_step"])
            self.assertIn("师徒关系裂缝", status["recommended_next_step"])

            pipeline = run_outline_workspace_pipeline(workspace)
            self.assertEqual(pipeline["recommended_action"], "repair-intake")
            self.assertEqual(pipeline["idea_id"], idea_id)
            self.assertIn("章节号", pipeline["reason"])

            executed = run_outline_workspace_pipeline(workspace, action="repair-intake", execute=True, idea_id=idea_id)
            self.assertTrue(executed["executed"])
            self.assertEqual(executed["consistency_report"]["idea_id"], idea_id)
            self.assertEqual(executed["intake_repair"]["repaired_count"], 1)

    def test_status_and_orchestrator_surface_constraints_review_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "这条更早知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="双人提前知情",
                content="林舟在第七章主城知道组织首领是谁，苏岚在第七章主城知道议会内部有人泄密。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["open_questions"] = []
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(report["ok"])

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and action["readiness"] == "needs-review"
            )
            self.assertIn("主体范围", constraints_action["summary"])

            status = collect_workspace_status(workspace)
            self.assertIn("world-rule / exception 主体范围", status["recommended_next_step"])
            self.assertIn("双人提前知情", status["recommended_next_step"])

            pipeline = run_outline_workspace_pipeline(workspace)
            self.assertEqual(pipeline["recommended_action"], "review-constraints")
            self.assertEqual(pipeline["idea_id"], idea_id)
            self.assertIn("constraints", pipeline["reason"])
            self.assertIn("主体范围", pipeline["reason"])

            executed = run_outline_workspace_pipeline(workspace, action="review-constraints", execute=True, idea_id=idea_id)
            self.assertTrue(executed["executed"])
            self.assertEqual(executed["merge_plan"]["idea_id"], idea_id)
            self.assertEqual(executed["constraints_review"]["idea_id"], idea_id)
            self.assertTrue(Path(executed["constraints_review"]["report_path"]).exists())

    def test_status_and_orchestrator_surface_reuse_review_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth-a",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔",
                            "notes": "林舟在白塔第一次意识到议会和黑潮并非同一阵营。",
                        },
                        {
                            "id": "event-faction-truth-b",
                            "label": "白塔夜审",
                            "chronological_index": 8,
                            "reading_chapter": 8,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                        },
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-faction-truth-a", "event-faction-truth-b"],
                                    "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "timeline-order-conflict" for issue in report["issues"]))

            pipeline = run_outline_workspace_pipeline(workspace)
            self.assertEqual(pipeline["recommended_action"], "plan-merge")
            self.assertEqual(pipeline["idea_id"], idea_id)

            plan = plan_idea_merge(workspace, idea_id)
            self.assertIn("reuse-ambiguity-linked-events", plan["review_tokens"])

            status = collect_workspace_status(workspace)
            self.assertIn("event / scene reuse 歧义", status["recommended_next_step"])
            self.assertIn("白塔夜审", status["recommended_next_step"])
            self.assertIn("仍待确认 reuse 歧义", status["recommended_next_step"])

            pipeline = run_outline_workspace_pipeline(workspace)
            self.assertEqual(pipeline["recommended_action"], "review-reuse")
            self.assertEqual(pipeline["idea_id"], idea_id)
            self.assertIn("reuse", pipeline["reason"])

            executed = run_outline_workspace_pipeline(workspace, action="review-reuse", execute=True, idea_id=idea_id)
            self.assertTrue(executed["executed"])
            self.assertEqual(executed["merge_plan"]["idea_id"], idea_id)
            self.assertEqual(executed["reuse_review"]["idea_id"], idea_id)
            self.assertEqual(executed["reuse_review"]["review_tokens"], ["reuse-ambiguity-linked-events"])
            self.assertTrue(Path(executed["reuse_review"]["report_path"]).exists())

    def test_merge_plan_assigns_unique_story_merge_input_ids_with_issue_and_default_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth-a",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔",
                            "notes": "林舟在白塔第一次意识到议会和黑潮并非同一阵营。",
                        },
                        {
                            "id": "event-faction-truth-b",
                            "label": "白塔夜审",
                            "chronological_index": 8,
                            "reading_chapter": 8,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                        },
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-faction-truth-a", "event-faction-truth-b"],
                                    "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            check_idea_consistency(workspace, idea_id)

            plan = plan_idea_merge(workspace, idea_id)
            story_ids = [
                str(item["id"])
                for item in plan["timeline_merge_inputs"]
                if str(item.get("id") or "").startswith("timeline-merge-")
                and str(item.get("id") or "").removeprefix("timeline-merge-").isdigit()
            ]
            self.assertGreaterEqual(len(story_ids), 2)
            self.assertEqual(len(story_ids), len(set(story_ids)))

    def test_dedupe_merge_inputs_unions_review_tokens_resolve_codes_and_backfills_apply_args(self) -> None:
        merged = _dedupe_merge_inputs(
            [
                {
                    "id": "timeline-merge-001",
                    "kind": "timeline-merge-input",
                    "strategy": "update-existing-event",
                    "summary": "更新事件",
                    "target_files": ["timeline/events.json"],
                    "source_issue_code": "timeline-order-conflict",
                    "source_patch_suggestion_ids": ["patch-a"],
                    "missing_fields": ["participant_ids"],
                    "can_apply_directly": False,
                    "requires_override": True,
                    "resolves_blocked_gate": False,
                    "resolves_issue_codes": [],
                    "warnings": ["needs-participants"],
                    "review_tokens": ["reuse-ambiguity-linked-scenes"],
                    "apply_args": {
                        "event_id": "event-001",
                        "reading_chapter": 3,
                        "participant_ids": [],
                    },
                },
                {
                    "id": "timeline-merge-002",
                    "kind": "timeline-merge-input",
                    "strategy": "update-existing-event",
                    "summary": "更新事件",
                    "target_files": ["outline/scene-index.json"],
                    "source_issue_code": "location-continuity-conflict",
                    "source_patch_suggestion_ids": ["patch-b"],
                    "missing_fields": [],
                    "can_apply_directly": True,
                    "requires_override": False,
                    "resolves_blocked_gate": True,
                    "resolves_issue_codes": ["location-continuity-conflict"],
                    "warnings": [],
                    "review_tokens": [],
                    "apply_args": {
                        "event_id": "event-001",
                        "reading_chapter": 3,
                        "participant_ids": ["char-protagonist"],
                    },
                },
            ]
        )
        self.assertEqual(len(merged), 1)
        item = merged[0]
        self.assertEqual(item["target_files"], ["outline/scene-index.json", "timeline/events.json"])
        self.assertEqual(item["source_patch_suggestion_ids"], ["patch-a", "patch-b"])
        self.assertEqual(item["review_tokens"], ["reuse-ambiguity-linked-scenes"])
        self.assertEqual(item["resolves_issue_codes"], ["location-continuity-conflict"])
        self.assertEqual(item["apply_args"]["participant_ids"], ["char-protagonist"])
        self.assertEqual(item["missing_fields"], [])
        self.assertTrue(item["can_apply_directly"])
        self.assertFalse(item["requires_override"])
        self.assertTrue(item["resolves_blocked_gate"])

    def test_dedupe_merge_inputs_marks_conflicting_scalar_apply_args_in_warnings(self) -> None:
        merged = _dedupe_merge_inputs(
            [
                {
                    "id": "timeline-merge-001",
                    "kind": "timeline-merge-input",
                    "strategy": "update-existing-event",
                    "summary": "更新事件",
                    "target_files": ["timeline/events.json"],
                    "source_issue_code": "timeline-order-conflict",
                    "source_patch_suggestion_ids": [],
                    "missing_fields": [],
                    "can_apply_directly": True,
                    "requires_override": False,
                    "resolves_blocked_gate": True,
                    "resolves_issue_codes": ["timeline-order-conflict"],
                    "warnings": [],
                    "review_tokens": [],
                    "apply_args": {
                        "event_id": "event-001",
                        "reading_chapter": 3,
                        "location": "白塔",
                    },
                },
                {
                    "id": "timeline-merge-002",
                    "kind": "timeline-merge-input",
                    "strategy": "update-existing-event",
                    "summary": "更新事件",
                    "target_files": ["timeline/events.json"],
                    "source_issue_code": "location-continuity-conflict",
                    "source_patch_suggestion_ids": [],
                    "missing_fields": [],
                    "can_apply_directly": True,
                    "requires_override": False,
                    "resolves_blocked_gate": True,
                    "resolves_issue_codes": ["location-continuity-conflict"],
                    "warnings": [],
                    "review_tokens": [],
                    "apply_args": {
                        "event_id": "event-001",
                        "reading_chapter": 3,
                        "location": "白塔议事厅",
                    },
                },
            ]
        )
        self.assertEqual(len(merged), 1)
        self.assertIn("dedupe-apply-args-conflict:location", merged[0]["warnings"])

    def test_reuse_review_missing_fields_remaining_item_reroutes_to_repair_intake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth-a",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔",
                            "notes": "林舟在白塔第一次意识到议会和黑潮并非同一阵营。",
                        },
                        {
                            "id": "event-faction-truth-b",
                            "label": "白塔夜审",
                            "chronological_index": 8,
                            "reading_chapter": 8,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                        },
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-faction-truth-a", "event-faction-truth-b"],
                                    "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            check_idea_consistency(workspace, idea_id)
            review = review_reuse(workspace, idea_id)
            report_path = Path(review["report_path"])
            persisted = read_json(report_path, {})
            persisted["remaining_review_merge_inputs"].append(
                {
                    "id": "timeline-merge-999",
                    "strategy": "create-event-and-scene",
                    "summary": "默认输入仍缺字段",
                    "target_files": ["timeline/events.json"],
                    "can_apply_directly": False,
                    "missing_fields": ["participant_ids"],
                    "warnings": [],
                    "review_tokens": [],
                    "remaining_kind": "missing-fields",
                    "remaining_summary": "仍待补齐字段：participant_ids",
                }
            )
            write_json(report_path, persisted)

            status = collect_workspace_status(workspace)
            self.assertIn("intake / merge 缺口", status["recommended_next_step"])
            self.assertIn("participant_ids", status["recommended_next_step"])

            pipeline = run_outline_workspace_pipeline(workspace)
            self.assertEqual(pipeline["recommended_action"], "repair-intake")
            self.assertEqual(pipeline["idea_id"], idea_id)
            self.assertIn("先补 intake", pipeline["reason"])

    def test_reuse_review_decision_can_advance_review_path_to_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth-a",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔",
                            "notes": "林舟在白塔第一次意识到议会和黑潮并非同一阵营。",
                        },
                        {
                            "id": "event-faction-truth-b",
                            "label": "白塔夜审",
                            "chronological_index": 8,
                            "reading_chapter": 8,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                        },
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-faction-truth-a", "event-faction-truth-b"],
                                    "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            check_idea_consistency(workspace, idea_id)
            review = review_reuse(workspace, idea_id)
            target_ready_input = next(
                item
                for item in review["ready_merge_inputs"]
                if item["strategy"] == "update-existing-event"
                and "event-faction-truth-b" in item["summary"]
            )
            ready_input_ids = [item["id"] for item in review["ready_merge_inputs"]]
            self.assertTrue(ready_input_ids)
            review_input_ids = [item["id"] for item in review["review_merge_inputs"]]
            self.assertEqual(len(review_input_ids), 1)
            self.assertTrue(review_input_ids[0].startswith("timeline-merge-"))
            self.assertEqual(
                [item["id"] for item in review["remaining_review_merge_inputs"]],
                review_input_ids,
            )
            self.assertIn("reuse-ambiguity-linked-events", review["review_tokens"])
            self.assertEqual(
                {item["id"]: item["remaining_kind"] for item in review["remaining_review_merge_inputs"]},
                {review_input_ids[0]: "reuse-ambiguity"},
            )

            decided = record_reuse_review_decision(
                workspace,
                idea_id,
                selected_merge_input_ids=[target_ready_input["id"]],
                resolution_note="复核后先放行 event 更新时间线，scene 的 event 关联歧义后续单独处理。",
            )
            self.assertEqual(decided["decision"]["status"], "approved-ready-merge-inputs")
            self.assertTrue(decided["decision"]["apply_ready"])
            self.assertTrue(decided["decision"]["merge_plan_fingerprint"])
            self.assertEqual(decided["decision"]["selected_merge_input_ids"], [target_ready_input["id"]])
            self.assertEqual(
                decided["decision"]["remaining_review_merge_input_ids"],
                review_input_ids,
            )
            self.assertEqual(
                {item["id"]: item["remaining_kind"] for item in decided["decision"]["remaining_review_merge_inputs"]},
                {review_input_ids[0]: "reuse-ambiguity"},
            )

            report_path = Path(decided["report_path"])
            persisted_review = read_json(report_path, {})
            persisted_review["decision"]["merge_plan_created_at"] = "2000-01-01T00:00:00Z"
            write_json(report_path, persisted_review)

            pipeline = run_outline_workspace_pipeline(workspace)
            self.assertEqual(pipeline["recommended_action"], "apply-merge")
            self.assertEqual(pipeline["idea_id"], idea_id)
            self.assertIn("reuse review", pipeline["reason"])
            status_after_decision = collect_workspace_status(workspace)
            self.assertIn("已确认", status_after_decision["recommended_next_step"])
            self.assertIn("仍待确认 reuse 歧义", status_after_decision["recommended_next_step"])

            applied = run_outline_workspace_pipeline(workspace, action="apply-merge", execute=True, idea_id=idea_id)
            self.assertTrue(applied["executed"])
            self.assertEqual(applied["merge_result"]["idea"]["status"], "applied")
            self.assertEqual(
                applied["merge_result"]["idea"]["applied_merge_input_ids"],
                [target_ready_input["id"]],
            )
            self.assertEqual(
                applied["merge_result"]["idea"]["resolution_note"],
                "复核后先放行 event 更新时间线，scene 的 event 关联歧义后续单独处理。",
            )
            refreshed_decision = applied["reuse_review"]["decision"]
            self.assertTrue(refreshed_decision["applied"])
            self.assertFalse(refreshed_decision["apply_ready"])
            self.assertFalse(applied["reuse_review"]["review_required"])
            self.assertEqual(applied["reuse_review"]["review_state"], "applied")
            self.assertEqual(
                [item["id"] for item in applied["reuse_review"]["remaining_review_merge_inputs"]],
                review_input_ids,
            )
            self.assertEqual(
                {item["id"]: item["remaining_kind"] for item in applied["reuse_review"]["remaining_review_merge_inputs"]},
                {review_input_ids[0]: "reuse-ambiguity"},
            )
            self.assertEqual(applied["reuse_review"]["ready_merge_inputs"], [])
            self.assertEqual(applied["reuse_review"]["blocked_merge_inputs"], [])
            self.assertTrue(applied["reuse_review"]["applied_result"]["validation_ok"])
            self.assertTrue(
                all(
                    str(item.get("readiness") or "").strip() == "applied"
                    for item in applied["reuse_review"]["action_matrix"]
                )
            )
            archived_again = review_reuse(workspace, idea_id)
            self.assertEqual(archived_again["review_state"], "applied")
            self.assertFalse(archived_again["review_required"])

            timeline_after = read_json(workspace / "timeline/events.json", {})
            moved_event = next(item for item in timeline_after["events"] if item["id"] == "event-faction-truth-b")
            self.assertEqual(moved_event["reading_chapter"], 3)
            self.assertEqual(moved_event["chronological_index"], 3)
            report = validate_workspace(workspace)
            self.assertTrue(report["ok"])

    def test_reuse_review_decision_expires_after_merge_plan_fingerprint_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth-a",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔",
                            "notes": "林舟在白塔第一次意识到议会和黑潮并非同一阵营。",
                        },
                        {
                            "id": "event-faction-truth-b",
                            "label": "白塔夜审",
                            "chronological_index": 8,
                            "reading_chapter": 8,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                        },
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-faction-truth-a", "event-faction-truth-b"],
                                    "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            check_idea_consistency(workspace, idea_id)

            review = review_reuse(workspace, idea_id)
            target_ready_input = next(
                item
                for item in review["ready_merge_inputs"]
                if item.get("strategy") == "update-existing-event"
                and "event-faction-truth-b" in str(item.get("summary") or "")
            )

            decided = record_reuse_review_decision(
                workspace,
                idea_id,
                selected_merge_input_ids=[target_ready_input["id"]],
                resolution_note="先消费 ready event 更新。",
            )
            self.assertTrue(decided["decision"]["apply_ready"])
            fingerprint_before = decided["decision"]["merge_plan_fingerprint"]

            updated_scene_index = read_json(workspace / "outline/scene-index.json", {})
            updated_scene_index["chapters"][0]["scenes"][0]["event_ids"] = ["event-faction-truth-b"]
            write_json(workspace / "outline/scene-index.json", updated_scene_index)

            refreshed_review = review_reuse(workspace, idea_id)
            self.assertFalse(refreshed_review["decision"]["apply_ready"])
            self.assertEqual(
                refreshed_review["decision"]["merge_plan_fingerprint"],
                fingerprint_before,
            )
            self.assertEqual(
                refreshed_review["decision"]["selected_merge_input_ids"],
                [target_ready_input["id"]],
            )

    def test_review_reuse_cli_prints_ready_and_remaining_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth-a",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔",
                            "notes": "林舟在白塔第一次意识到议会和黑潮并非同一阵营。",
                        },
                        {
                            "id": "event-faction-truth-b",
                            "label": "白塔夜审",
                            "chronological_index": 8,
                            "reading_chapter": 8,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                        },
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-faction-truth-a", "event-faction-truth-b"],
                                    "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            check_idea_consistency(workspace, idea_id)

            command = [
                sys.executable,
                "scripts/review_reuse.py",
                "--workspace",
                str(workspace),
                "--idea-id",
                idea_id,
            ]
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Ready merge inputs:", completed.stdout)
            self.assertIn("Remaining review inputs:", completed.stdout)
            self.assertIn("更新 `event-faction-truth-b`", completed.stdout)
            self.assertIn("[reuse-ambiguity]", completed.stdout)

    def test_reuse_review_remaining_input_snapshots_classify_ambiguity_and_missing_fields(self) -> None:
        review_inputs = [
            {
                "id": "timeline-merge-004",
                "strategy": "update-existing-scene",
                "summary": "scene reuse 歧义",
                "target_files": ["outline/scene-index.json"],
                "can_apply_directly": False,
                "missing_fields": ["scene_event_ids"],
                "warnings": ["场景需要人工确认旧 event 关联。"],
                "review_tokens": ["reuse-ambiguity-linked-events"],
            }
        ]
        blocked_inputs = [
            {
                "id": "timeline-merge-005",
                "strategy": "create-event-and-scene",
                "summary": "默认 timeline 输入还缺字段",
                "target_files": ["timeline/events.json", "outline/scene-index.json"],
                "can_apply_directly": False,
                "missing_fields": ["participant_ids", "reading_chapter"],
                "warnings": [],
                "review_tokens": [],
            }
        ]

        remaining = _remaining_review_input_snapshots(_combined_remaining_review_inputs(review_inputs, blocked_inputs))
        remaining_by_id = {item["id"]: item for item in remaining}
        self.assertEqual(remaining_by_id["timeline-merge-004"]["remaining_kind"], "reuse-ambiguity")
        self.assertIn("reuse-ambiguity-linked-events", remaining_by_id["timeline-merge-004"]["remaining_summary"])
        self.assertEqual(remaining_by_id["timeline-merge-005"]["remaining_kind"], "missing-fields")
        self.assertIn("participant_ids", remaining_by_id["timeline-merge-005"]["remaining_summary"])
        self.assertIn("reading_chapter", remaining_by_id["timeline-merge-005"]["remaining_summary"])

    def test_reuse_review_decision_can_reject_review_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth-a",
                            "label": "白塔夜审",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔",
                            "notes": "林舟在白塔第一次意识到议会和黑潮并非同一阵营。",
                        },
                        {
                            "id": "event-faction-truth-b",
                            "label": "白塔夜审",
                            "chronological_index": 8,
                            "reading_chapter": 8,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                        },
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-faction-truth",
                                    "title": "白塔夜审",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-faction-truth-a", "event-faction-truth-b"],
                                    "notes": "林舟在白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                                }
                            ],
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="scene",
            )
            idea_id = result["idea"]["id"]
            check_idea_consistency(workspace, idea_id)
            review = review_reuse(workspace, idea_id)
            self.assertTrue(review["review_required"])

            rejected = record_reuse_review_decision(
                workspace,
                idea_id,
                decision="rejected",
                resolution_note="复核后决定这条 reuse 歧义 case 当前不进入 apply，先作为 rejected idea 归档。",
            )
            self.assertEqual(rejected["decision"]["status"], "rejected")
            self.assertTrue(rejected["decision"]["rejected"])
            self.assertEqual(rejected["status"], "rejected")
            self.assertFalse(rejected["review_required"])
            self.assertEqual(rejected["review_state"], "rejected")
            self.assertEqual(rejected["review_merge_inputs"], [])
            self.assertEqual(
                [item["id"] for item in rejected["remaining_review_merge_inputs"]],
                [item["id"] for item in rejected["decision"]["remaining_review_merge_inputs"]],
            )
            self.assertEqual(rejected["ready_merge_inputs"], [])
            self.assertEqual(rejected["blocked_merge_inputs"], [])
            self.assertEqual(rejected["consistency_gate"]["status"], "closed")
            self.assertIn("rejected", rejected["review_status_summary"])
            self.assertEqual(
                [item["readiness"] for item in rejected["action_matrix"]],
                ["applied"],
            )
            self.assertTrue(rejected["rejected_result"]["validation_ok"])

            idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
            idea = next(item for item in idea_log["ideas"] if item["id"] == idea_id)
            self.assertEqual(idea["status"], "rejected")
            self.assertEqual(
                idea["resolution_note"],
                "复核后决定这条 reuse 歧义 case 当前不进入 apply，先作为 rejected idea 归档。",
            )

            status = collect_workspace_status(workspace)
            self.assertEqual(status["idea_counts"]["pending"], 0)
            self.assertEqual(status["idea_counts"]["rejected"], 1)
            pipeline = run_outline_workspace_pipeline(workspace)
            self.assertEqual(pipeline["recommended_action"], "validate")

    def test_review_reuse_backfills_remaining_inputs_for_legacy_applied_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
            idea_log["ideas"].append(
                {
                    "id": "idea-legacy",
                    "title": "档案夜审",
                    "kind": "scene",
                    "status": "applied",
                    "source": "manual",
                    "content": "旧样例。",
                    "tags": [],
                    "target_files": ["timeline/events.json"],
                    "created_at": "2026-07-05T03:36:00Z",
                    "updated_at": "2026-07-05T03:36:16Z",
                    "resolution_note": "先放行旧 event，scene 歧义后续再处理。",
                    "applied_merge_input_ids": ["timeline-merge-003"],
                }
            )
            write_json(workspace / "state/idea-log.json", idea_log)
            write_json(
                workspace / "state/merge-plans/idea-legacy.json",
                {
                    "idea_id": "idea-legacy",
                    "created_at": "2026-07-05T03:36:15Z",
                    "timeline_merge_inputs": [
                        {
                            "id": "timeline-merge-003",
                            "strategy": "update-existing-event",
                            "summary": "更新旧 event。",
                            "target_files": ["timeline/events.json"],
                            "can_apply_directly": False,
                            "missing_fields": [],
                            "warnings": [],
                            "review_tokens": [],
                        },
                        {
                            "id": "timeline-merge-004",
                            "strategy": "update-existing-scene",
                            "summary": "scene reuse 歧义。",
                            "target_files": ["outline/scene-index.json"],
                            "can_apply_directly": False,
                            "missing_fields": ["scene_event_ids"],
                            "warnings": ["场景需要人工确认旧 event 关联。"],
                            "review_tokens": ["reuse-ambiguity-linked-events"],
                        },
                    ],
                },
            )
            write_json(
                workspace / "state/reuse-reviews/idea-legacy.json",
                {
                    "idea_id": "idea-legacy",
                    "title": "档案夜审",
                    "status": "applied",
                    "review_required": False,
                    "review_state": "applied",
                    "review_status_summary": "旧归档。",
                    "review_summary": "当前 merge plan 含有 reuse 歧义，需要先人工确认事件/场景关联对象。",
                    "review_tokens": ["reuse-ambiguity-linked-events"],
                    "review_checklist": [],
                    "review_merge_inputs": [],
                    "ready_merge_inputs": [],
                    "blocked_merge_inputs": [],
                    "action_matrix": [],
                    "consistency_gate": {"status": "consumed"},
                    "merge_plan_path": str((workspace / "state/merge-plans/idea-legacy.json").resolve()),
                    "merge_plan_view_path": str((workspace / "views/merge-plans/idea-legacy.html").resolve()),
                    "created_at": "2026-07-05T03:36:16Z",
                    "decision": {
                        "status": "approved-ready-merge-inputs",
                        "summary": "已确认先消费 ready merge inputs：timeline-merge-003。",
                        "resolution_note": "先放行旧 event，scene 歧义后续再处理。",
                        "selected_merge_input_ids": ["timeline-merge-003"],
                        "selected_merge_inputs": [
                            {
                                "id": "timeline-merge-003",
                                "strategy": "update-existing-event",
                                "summary": "更新旧 event。",
                                "target_files": ["timeline/events.json"],
                                "can_apply_directly": False,
                                "missing_fields": [],
                                "warnings": [],
                                "review_tokens": [],
                            }
                        ],
                        "apply_ready": False,
                        "merge_plan_created_at": "2026-07-05T03:36:15Z",
                        "merge_plan_fingerprint": "legacy-fingerprint",
                        "decided_at": "2026-07-05T03:36:15Z",
                        "applied": True,
                        "applied_at": "2026-07-05T03:36:16Z",
                        "applied_merge_input_ids": ["timeline-merge-003"],
                    },
                    "applied_result": {
                        "status": "applied",
                        "resolution_note": "先放行旧 event，scene 歧义后续再处理。",
                        "applied_merge_input_ids": ["timeline-merge-003"],
                        "updated_files": ["timeline/events.json"],
                        "validation_ok": True,
                        "validation_report_path": "",
                        "validated_at": "2026-07-05T03:36:16Z",
                        "applied_at": "2026-07-05T03:36:16Z",
                    },
                },
            )

            refreshed = review_reuse(workspace, "idea-legacy")
            remaining = refreshed["remaining_review_merge_inputs"]
            self.assertEqual([item["id"] for item in remaining], ["timeline-merge-004"])
            self.assertEqual(remaining[0]["remaining_kind"], "reuse-ambiguity")
            self.assertIn("reuse-ambiguity-linked-events", remaining[0]["remaining_summary"])

    def test_mixed_subject_local_signal_review_path_keeps_participants_from_timeline_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-林舟-黑潮真正目标-ch10",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在黑潮真正目标正式揭露前不知道黑潮真正目标",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "黑潮真正目标",
                    "object_phrase": "黑潮真正目标",
                    "reading_chapter": 10,
                    "event_id": None,
                    "notes": "林舟在第10章的提前知情点是正式 exception。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在黑潮真正目标正式揭露前不知道黑潮真正目标",
                            "applies_until_event_id": "event-012",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-012",
                            "label": "黑潮真正目标正式揭露",
                            "chronological_index": 12,
                            "reading_chapter": 12,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="林舟和师姐都知道黑潮真正目标",
                content="林舟和师姐在第十一章白塔议事厅都知道黑潮真正目标。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["suggested_domains"] = ["canon"]
            draft["chapter_hints"] = [11]
            draft["location_candidates"] = ["白塔议事厅"]
            draft["open_questions"] = []
            draft["content"] = "林舟和师姐在第十一章白塔议事厅都知道黑潮真正目标。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "prior-exception-mixed-subjects-local-signal")
            self.assertEqual(report["knowledge_claims"], [])

            plan = plan_idea_merge(workspace, idea_id)
            scene_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "create-event-and-scene")
            self.assertEqual(scene_input["missing_fields"], [])
            self.assertEqual(
                scene_input["apply_args"]["participant_ids"],
                ["char-protagonist", "char-shijie"],
            )
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            self.assertEqual(constraints_action["readiness"], "needs-review")
            self.assertEqual(
                constraints_action["review_policy"],
                "mixed-subjects-local-signal-review-only",
            )
            self.assertIn(
                "mixed-subjects + local-signal 当前默认只做 review",
                constraints_action["review_policy_summary"],
            )
            self.assertIn(
                "exception_scope=prior-exception-mixed-subjects-local-signal",
                " ".join(constraints_action["planned_writes"]),
            )
            self.assertIn(
                "policy=mixed-subjects-local-signal-review-only",
                " ".join(constraints_action["planned_writes"]),
            )

            status = collect_workspace_status(workspace)
            self.assertIn("world-rule / exception", status["recommended_next_step"])
            self.assertIn("当前默认只做 review", status["recommended_next_step"])
            pipeline = run_outline_workspace_pipeline(workspace)
            self.assertEqual(pipeline["recommended_action"], "review-constraints")
            self.assertEqual(pipeline["idea_id"], idea_id)
            self.assertIn("当前默认只做 review", pipeline["reason"])
            review = review_constraints(workspace, idea_id)
            self.assertTrue(review["review_required"])
            self.assertEqual(review["review_policy"], "mixed-subjects-local-signal-review-only")
            self.assertIn("主体范围未复核前，不新增额外 canon knowledge-state", " / ".join(review["review_checklist"]))
            self.assertEqual(
                [item["id"] for item in review["ready_merge_inputs"]],
                [scene_input["id"]],
            )
            self.assertTrue(Path(review["report_path"]).exists())

    def test_constraints_review_decision_can_advance_review_only_path_to_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-林舟-黑潮真正目标-ch10",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在黑潮真正目标正式揭露前不知道黑潮真正目标",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "黑潮真正目标",
                    "object_phrase": "黑潮真正目标",
                    "reading_chapter": 10,
                    "event_id": None,
                    "notes": "林舟在第10章的提前知情点是正式 exception。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在黑潮真正目标正式揭露前不知道黑潮真正目标",
                            "applies_until_event_id": "event-012",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-012",
                            "label": "黑潮真正目标正式揭露",
                            "chronological_index": 12,
                            "reading_chapter": 12,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="林舟和师姐都知道黑潮真正目标",
                content="林舟和师姐在第十一章白塔议事厅都知道黑潮真正目标。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["suggested_domains"] = ["canon"]
            draft["chapter_hints"] = [11]
            draft["location_candidates"] = ["白塔议事厅"]
            draft["open_questions"] = []
            draft["content"] = "林舟和师姐在第十一章白塔议事厅都知道黑潮真正目标。"
            write_json(draft_path, draft)

            check_idea_consistency(workspace, idea_id)
            review = review_constraints(workspace, idea_id)
            ready_input_ids = [item["id"] for item in review["ready_merge_inputs"]]
            self.assertEqual(ready_input_ids, ["timeline-merge-001"])

            decided = record_constraints_review_decision(
                workspace,
                idea_id,
                resolution_note="复核后仅放行第11章 event/scene，保持既有 exception 主体范围不变。",
            )
            self.assertEqual(decided["decision"]["status"], "approved-ready-merge-inputs")
            self.assertTrue(decided["decision"]["apply_ready"])
            self.assertTrue(decided["decision"]["merge_plan_fingerprint"])
            self.assertEqual(
                decided["decision"]["selected_merge_input_ids"],
                ready_input_ids,
            )
            report_path = Path(decided["report_path"])
            persisted_review = read_json(report_path, {})
            persisted_review["decision"]["merge_plan_created_at"] = "2000-01-01T00:00:00Z"
            write_json(report_path, persisted_review)

            pipeline = run_outline_workspace_pipeline(workspace)
            self.assertEqual(pipeline["recommended_action"], "apply-merge")
            self.assertEqual(pipeline["idea_id"], idea_id)
            self.assertIn("已确认", collect_workspace_status(workspace)["recommended_next_step"])

            applied = run_outline_workspace_pipeline(workspace, action="apply-merge", execute=True, idea_id=idea_id)
            self.assertTrue(applied["executed"])
            self.assertEqual(applied["merge_result"]["idea"]["status"], "applied")
            self.assertEqual(
                applied["merge_result"]["idea"]["applied_merge_input_ids"],
                ready_input_ids,
            )
            self.assertEqual(
                applied["merge_result"]["idea"]["resolution_note"],
                "复核后仅放行第11章 event/scene，保持既有 exception 主体范围不变。",
            )
            refreshed_decision = applied["constraints_review"]["decision"]
            self.assertTrue(refreshed_decision["applied"])
            self.assertFalse(refreshed_decision["apply_ready"])
            self.assertFalse(applied["constraints_review"]["review_required"])
            self.assertEqual(applied["constraints_review"]["review_state"], "applied")
            self.assertIn("已于", applied["constraints_review"]["review_status_summary"])
            self.assertEqual(applied["constraints_review"]["ready_merge_inputs"], [])
            self.assertEqual(applied["constraints_review"]["blocked_merge_inputs"], [])
            self.assertTrue(applied["constraints_review"]["applied_result"]["validation_ok"])
            self.assertTrue(
                all(
                    str(item.get("readiness") or "").strip() == "applied"
                    for item in applied["constraints_review"]["action_matrix"]
                )
            )
            archived_again = review_constraints(workspace, idea_id)
            self.assertEqual(archived_again["review_state"], "applied")
            self.assertFalse(archived_again["review_required"])
            self.assertEqual(archived_again["action_matrix"], applied["constraints_review"]["action_matrix"])

            canon_after = read_json(workspace / "state/canon-index.json", {})
            self.assertEqual(len(canon_after["world_rule_exceptions"]), 1)
            self.assertEqual(canon_after["knowledge_states"], [])
            timeline_after = read_json(workspace / "timeline/events.json", {})
            self.assertTrue(
                any(item["label"] == "林舟和师姐都知道黑潮真正目标" for item in timeline_after["events"])
            )
            report = validate_workspace(workspace)
            self.assertTrue(report["ok"])

    def test_constraints_review_decision_can_reject_review_only_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-林舟-黑潮真正目标-ch10",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在黑潮真正目标正式揭露前不知道黑潮真正目标",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "黑潮真正目标",
                    "object_phrase": "黑潮真正目标",
                    "reading_chapter": 10,
                    "event_id": None,
                    "notes": "林舟在第10章的提前知情点是正式 exception。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在黑潮真正目标正式揭露前不知道黑潮真正目标",
                            "applies_until_event_id": "event-012",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-012",
                            "label": "黑潮真正目标正式揭露",
                            "chronological_index": 12,
                            "reading_chapter": 12,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="林舟和师姐都知道黑潮真正目标",
                content="林舟和师姐在第十一章白塔议事厅都知道黑潮真正目标。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["suggested_domains"] = ["canon"]
            draft["chapter_hints"] = [11]
            draft["location_candidates"] = ["白塔议事厅"]
            draft["open_questions"] = []
            draft["content"] = "林舟和师姐在第十一章白塔议事厅都知道黑潮真正目标。"
            write_json(draft_path, draft)

            check_idea_consistency(workspace, idea_id)
            review = review_constraints(workspace, idea_id)
            self.assertTrue(review["review_required"])

            rejected = record_constraints_review_decision(
                workspace,
                idea_id,
                decision="rejected",
                resolution_note="复核后决定这条 mixed-subject case 当前不进入 apply，先作为 rejected idea 归档。",
            )
            self.assertEqual(rejected["decision"]["status"], "rejected")
            self.assertTrue(rejected["decision"]["rejected"])
            self.assertEqual(rejected["status"], "rejected")
            self.assertFalse(rejected["review_required"])
            self.assertEqual(rejected["review_state"], "rejected")
            self.assertEqual(rejected["ready_merge_inputs"], [])
            self.assertEqual(rejected["blocked_merge_inputs"], [])
            self.assertEqual(rejected["consistency_gate"]["status"], "closed")
            self.assertIn("rejected", rejected["review_status_summary"])
            self.assertEqual(
                [item["readiness"] for item in rejected["action_matrix"]],
                ["applied"],
            )
            self.assertTrue(rejected["rejected_result"]["validation_ok"])

            idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
            idea = next(item for item in idea_log["ideas"] if item["id"] == idea_id)
            self.assertEqual(idea["status"], "rejected")
            self.assertEqual(
                idea["resolution_note"],
                "复核后决定这条 mixed-subject case 当前不进入 apply，先作为 rejected idea 归档。",
            )

            status = collect_workspace_status(workspace)
            self.assertEqual(status["idea_counts"]["pending"], 0)
            self.assertEqual(status["idea_counts"]["rejected"], 1)
            pipeline = run_outline_workspace_pipeline(workspace)
            self.assertEqual(pipeline["recommended_action"], "render")
            archived_again = review_constraints(workspace, idea_id)
            self.assertEqual(archived_again["review_state"], "rejected")
            self.assertFalse(archived_again["review_required"])
            report = validate_workspace(workspace)
            self.assertTrue(report["ok"])

    def test_update_intake_draft_enables_repair_plan_apply_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="师徒关系裂缝",
                content="师姐在白塔议事厅确认林舟可能不会继续站在议会一边",
                kind="character",
            )
            idea_id = result["idea"]["id"]

            initial_report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(initial_report["ok"])
            initial_plan = plan_idea_merge(workspace, idea_id)
            self.assertIn("chapter_number", initial_plan["timeline_merge_inputs"][0]["missing_fields"])
            self.assertEqual(run_outline_workspace_pipeline(workspace)["recommended_action"], "repair-intake")

            patched = update_intake_draft(
                workspace,
                idea_id=idea_id,
                chapter_hints=[6],
                clear_open_questions=True,
            )
            self.assertEqual(patched["draft"]["chapter_hints"], [6])
            self.assertEqual(patched["draft"]["open_questions"], [])
            self.assertFalse((workspace / "state" / "merge-plans" / f"{idea_id}.json").exists())

            refreshed_report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(refreshed_report["ok"])
            self.assertEqual(refreshed_report["warning_count"], 0)

            pipeline = run_outline_workspace_pipeline(workspace)
            self.assertEqual(pipeline["recommended_action"], "plan-merge")

            plan = plan_idea_merge(workspace, idea_id)
            merge_input = plan["timeline_merge_inputs"][0]
            self.assertTrue(merge_input["can_apply_directly"])
            merged = apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=merge_input["id"],
                resolution_note="把师徒关系裂缝并入第六章场景。",
            )
            self.assertEqual(merged["idea"]["status"], "applied")
            self.assertTrue(merged["validation_report"]["ok"])

    def test_update_intake_draft_cli_supports_repair_plan_apply_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="师徒关系裂缝",
                content="师姐在白塔议事厅确认林舟可能不会继续站在议会一边",
                kind="character",
            )
            idea_id = result["idea"]["id"]
            check_idea_consistency(workspace, idea_id)
            plan_idea_merge(workspace, idea_id)

            patch_command = [
                sys.executable,
                "scripts/update_intake_draft.py",
                "--workspace",
                str(workspace),
                "--idea-id",
                idea_id,
                "--chapter-hint",
                "6",
                "--clear-open-questions",
                "--json",
            ]
            patched = subprocess.run(
                patch_command,
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"chapter_hints": [', patched.stdout)

            check_idea_consistency(workspace, idea_id)
            plan = plan_idea_merge(workspace, idea_id)
            merge_input = plan["timeline_merge_inputs"][0]
            apply_command = [
                sys.executable,
                "scripts/apply_idea_merge.py",
                "--workspace",
                str(workspace),
                "--idea-id",
                idea_id,
                "--merge-input-id",
                str(merge_input["id"]),
                "--resolution-note",
                "按修补后的 intake draft 并入。",
                "--json",
            ]
            applied = subprocess.run(
                apply_command,
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn('"status": "applied"', applied.stdout)
            self.assertEqual(run_outline_workspace_pipeline(workspace)["recommended_action"], "render")

    def test_idea_intake_infers_kind_tags_and_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="师姐提前知情",
                content="师姐在第三章白塔议事厅就知道议会内部有人泄密，但先没有告诉林舟。",
                kind="auto",
            )
            idea = result["idea"]
            self.assertEqual(idea["kind"], "reveal")
            self.assertIn("timeline/events.json", idea["target_files"])
            self.assertIn("outline/scene-index.json", idea["target_files"])
            self.assertIn("林舟", idea["tags"])
            self.assertTrue((workspace / "inbox" / f"{idea['id']}-师姐提前知情.md").exists())
            self.assertTrue((workspace / "state" / "intake-drafts" / f"{idea['id']}.json").exists())
            self.assertTrue((workspace / "views" / "intake-drafts" / f"{idea['id']}.html").exists())
            draft = read_json(workspace / "state" / "intake-drafts" / f"{idea['id']}.json", {})
            self.assertIn(3, draft["chapter_hints"])
            self.assertIn("白塔议事厅", draft["location_candidates"])
            self.assertIn("林舟", draft["character_mentions"])

    def test_consistency_check_detects_title_and_location_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-reveal",
                            "label": "苏岚提前知道真相",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-sulan"],
                            "location": "白塔",
                            "notes": "",
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="苏岚提前知道真相",
                content="苏岚在第三章白塔议事厅就知道组织首领身份。",
                kind="auto",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            codes = {issue["code"] for issue in report["issues"]}
            self.assertIn("knowledge-state-conflict", codes)
            self.assertIn("location-continuity-conflict", codes)
            self.assertTrue(any(suggestion["issue_code"] == "knowledge-state-conflict" for suggestion in report["patch_suggestions"]))
            self.assertTrue(any(suggestion["issue_code"] == "location-continuity-conflict" for suggestion in report["patch_suggestions"]))
            self.assertTrue((workspace / "state" / "consistency-checks" / f"{result['idea']['id']}.json").exists())
            self.assertTrue((workspace / "views" / "consistency-checks" / f"{result['idea']['id']}.html").exists())

    def test_consistency_check_detects_title_drift_with_expanded_event_and_scene_titles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-reveal-expanded",
                            "label": "苏岚提前知道真相（白塔议事厅）",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-sulan"],
                            "location": "白塔",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-reveal-expanded",
                                    "title": "苏岚提前知道真相·白塔夜审",
                                    "pov": "苏岚",
                                    "status": "planned",
                                    "characters": ["char-sulan"],
                                    "event_ids": ["event-reveal-expanded"],
                                    "notes": "",
                                }
                            ],
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="苏岚提前知道真相",
                content="苏岚在第三章白塔议事厅就知道组织首领身份。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            knowledge_issues = [issue for issue in report["issues"] if issue["code"] == "knowledge-state-conflict"]
            location_issues = [issue for issue in report["issues"] if issue["code"] == "location-continuity-conflict"]

            self.assertTrue(any(issue["details"]["record_id"] == "event-reveal-expanded" for issue in knowledge_issues))
            self.assertTrue(any(issue["details"]["record_id"] == "scene-reveal-expanded" for issue in knowledge_issues))
            self.assertTrue(any(issue["details"]["record_id"] == "event-reveal-expanded" for issue in location_issues))

    def test_merge_plan_merges_multiple_issues_for_same_event_into_one_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-reveal-expanded",
                            "label": "苏岚提前知道真相（白塔议事厅）",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-sulan"],
                            "location": "白塔",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "title": "第七章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-reveal-expanded",
                                    "title": "苏岚提前知道真相·白塔夜审",
                                    "pov": "苏岚",
                                    "status": "planned",
                                    "characters": ["char-sulan"],
                                    "event_ids": ["event-reveal-expanded"],
                                    "notes": "",
                                }
                            ],
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="苏岚提前知道真相",
                content="苏岚在第三章白塔议事厅就知道组织首领身份。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertIn("knowledge-state-conflict", {issue["code"] for issue in report["issues"]})
            self.assertIn("location-continuity-conflict", {issue["code"] for issue in report["issues"]})

            plan = plan_idea_merge(workspace, idea_id)
            event_inputs = [
                item
                for item in plan["timeline_merge_inputs"]
                if item["strategy"] == "update-existing-event"
                and item.get("apply_args", {}).get("event_id") == "event-reveal-expanded"
            ]
            self.assertEqual(len(event_inputs), 1)
            event_input = event_inputs[0]
            self.assertEqual(event_input["apply_args"]["reading_chapter"], 3)
            self.assertEqual(event_input["apply_args"]["location"], "白塔议事厅")
            suggestion_ids = set(event_input["source_patch_suggestion_ids"])
            self.assertGreaterEqual(len(suggestion_ids), 2)

    def test_consistency_check_detects_knowledge_state_conflict_without_title_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth",
                            "label": "林舟确认议会和黑潮不是同一阵营",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟到这里才彻底明白议会和黑潮不是一路。",
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            knowledge_issue = next(issue for issue in report["issues"] if issue["code"] == "knowledge-state-conflict")
            self.assertEqual(knowledge_issue["details"]["record_id"], "event-faction-truth")
            self.assertEqual(knowledge_issue["details"]["existing_chapter"], 7)
            self.assertTrue(report["knowledge_claims"])
            self.assertEqual(report["knowledge_claims"][0]["subject_id"], "char-protagonist")
            suggestion = next(suggestion for suggestion in report["patch_suggestions"] if suggestion["issue_code"] == "knowledge-state-conflict")
            self.assertIn("timeline/events.json", suggestion["target_files"])

    def test_consistency_check_detects_knowledge_state_conflict_for_synonym_object_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-leak-truth",
                            "label": "林舟确认议会内部有内鬼",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟到这里才知道议会内部有内鬼。",
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次知道议会内部有人泄密。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            knowledge_issue = next(issue for issue in report["issues"] if issue["code"] == "knowledge-state-conflict")
            self.assertEqual(knowledge_issue["details"]["record_id"], "event-leak-truth")

    def test_consistency_check_avoids_false_positive_for_shared_prefix_but_different_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-investigation",
                            "label": "林舟确认议会内部有人调查",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟到这里才知道议会内部有人调查。",
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次知道议会内部有人泄密。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "knowledge-state-conflict" for issue in report["issues"]))

    def test_knowledge_merge_input_updates_canon_and_clears_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth",
                            "label": "林舟确认议会和黑潮不是同一阵营",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟到这里才彻底明白议会和黑潮不是一路。",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "knowledge-state-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            knowledge_input = next(
                item for item in plan["timeline_merge_inputs"] if item["strategy"] in {"upsert-canon-knowledge-state", "update-existing-knowledge-state"}
            )
            self.assertTrue(knowledge_input["can_apply_directly"])

            merged = apply_idea_merge(
                workspace,
                idea_id=idea_id,
                resolution_note="把知情点正式写入 canon。",
                merge_input_id=knowledge_input["id"],
            )
            self.assertEqual(merged["idea"]["applied_merge_input_id"], knowledge_input["id"])
            canon_index = read_json(workspace / "state/canon-index.json", {})
            self.assertTrue(canon_index["knowledge_states"])
            self.assertEqual(canon_index["knowledge_states"][0]["subject_id"], "char-protagonist")
            self.assertEqual(canon_index["knowledge_states"][0]["reading_chapter"], 3)

            refreshed = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "knowledge-state-conflict" for issue in refreshed["issues"]))

    def test_consistency_check_exempts_future_knowledge_recap_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-recap",
                            "label": "林舟再次意识到议会和黑潮不是同一阵营",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟再次意识到议会和黑潮不是一路。",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "knowledge-state-conflict" for issue in report["issues"]))

    def test_consistency_check_exempts_future_knowledge_conflict_when_same_chapter_record_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-faction-truth-early",
                            "label": "林舟意识到议会和黑潮不是同一阵营",
                            "chronological_index": 3,
                            "reading_chapter": 3,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟在这里正式意识到议会和黑潮并非同一阵营。",
                        },
                        {
                            "id": "event-faction-truth-late",
                            "label": "林舟再次确认议会和黑潮不是同一阵营",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟到这里又一次确认议会和黑潮不是一路。",
                        },
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第三章白塔议事厅第一次意识到议会和黑潮并非同一阵营。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "knowledge-state-conflict" for issue in report["issues"]))

    def test_consistency_check_prefers_earlier_knowledge_conflict_over_later_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["knowledge_states"] = [
                {
                    "id": "know-early-faction-truth",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "议会和黑潮并非同一阵营",
                    "object_phrase": "议会和黑潮并非同一阵营",
                    "verb": "意识到",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-late-faction-truth",
                            "label": "林舟确认议会和黑潮不是同一阵营",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "白塔议事厅",
                            "notes": "林舟到这里才彻底确认议会和黑潮不是一路。",
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="白塔夜审",
                content="林舟在第五章第一次意识到议会和黑潮并非同一阵营。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            knowledge_issues = [issue for issue in report["issues"] if issue["code"] == "knowledge-state-conflict"]
            self.assertEqual(len(knowledge_issues), 1)
            self.assertEqual(knowledge_issues[0]["details"]["direction"], "already-known-earlier")
            self.assertEqual(knowledge_issues[0]["details"]["record_id"], "know-early-faction-truth")

    def test_knowledge_repeat_beat_plan_prefers_scene_only_gate_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["knowledge_states"] = [
                {
                    "id": "know-existing-leak-truth",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "议会内部泄密",
                    "object_phrase": "议会内部泄密",
                    "verb": "确认",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "旧记录",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟再次确认议会内部泄密",
                content="林舟在第六章再次确认议会内部有人泄密，决定公开追查。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟在第六章再次确认议会内部有人泄密，决定公开追查。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            knowledge_issue = next(issue for issue in report["issues"] if issue["code"] == "knowledge-state-conflict")
            self.assertEqual(knowledge_issue["details"]["direction"], "knowledge-repeat-beat")

            plan = plan_idea_merge(workspace, idea_id)
            knowledge_inputs = [
                item
                for item in plan["timeline_merge_inputs"]
                if item["strategy"] in {"update-existing-knowledge-state", "upsert-canon-knowledge-state"}
            ]
            self.assertEqual(knowledge_inputs, [])
            scene_input = next(
                item
                for item in plan["timeline_merge_inputs"]
                if item["strategy"] == "create-event-and-scene"
                and item.get("source_issue_code") == "knowledge-state-conflict"
            )
            self.assertTrue(scene_input["can_apply_directly"])
            self.assertTrue(scene_input["resolves_blocked_gate"])
            self.assertCountEqual(
                scene_input["target_files"],
                ["timeline/events.json", "outline/scene-index.json", "outline/master-outline.md"],
            )
            self.assertEqual(scene_input["apply_args"]["reading_chapter"], 6)
            self.assertEqual(scene_input["apply_args"]["scene_title"], "林舟再次确认议会内部泄密")
            self.assertEqual(scene_input["apply_args"]["scene_character_ids"], ["char-protagonist"])

    def test_apply_later_knowledge_repeat_beat_keeps_existing_canon_knowledge_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["knowledge_states"] = [
                {
                    "id": "know-existing-leak-truth",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "议会内部泄密",
                    "object_phrase": "议会内部泄密",
                    "verb": "确认",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "旧记录",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟再次确认议会内部泄密",
                content="林舟在第六章再次确认议会内部有人泄密，决定公开追查。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟在第六章再次确认议会内部有人泄密，决定公开追查。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertTrue(any(issue["code"] == "knowledge-state-conflict" for issue in report["issues"]))
            plan = plan_idea_merge(workspace, idea_id)
            scene_input = next(
                item
                for item in plan["timeline_merge_inputs"]
                if item["strategy"] == "create-event-and-scene"
                and item.get("source_issue_code") == "knowledge-state-conflict"
            )

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_id=scene_input["id"],
                resolution_note="保留第4章既有知情记录，只把第6章再次确认作为新的场景 beat 写入 timeline/outline。",
            )

            updated_canon_index = read_json(workspace / "state/canon-index.json", {})
            knowledge_states = updated_canon_index.get("knowledge_states", [])
            self.assertEqual(len(knowledge_states), 1)
            self.assertEqual(knowledge_states[0]["id"], "know-existing-leak-truth")
            self.assertEqual(knowledge_states[0]["reading_chapter"], 4)

            scene_index = read_json(workspace / "outline/scene-index.json", {})
            chapter_six = next(chapter for chapter in scene_index["chapters"] if chapter["chapter"] == 6)
            scene = next(scene for scene in chapter_six["scenes"] if scene["id"] == scene_input["apply_args"]["scene_id"])
            self.assertEqual(scene["title"], "林舟再次确认议会内部泄密")
            self.assertEqual(scene["characters"], ["char-protagonist"])

            followup_report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "knowledge-state-conflict" for issue in followup_report["issues"]))

    def test_second_subject_can_append_new_knowledge_state_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["knowledge_states"] = [
                {
                    "id": "know-existing-leak-truth",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "议会内部泄密",
                    "object_phrase": "议会内部泄密",
                    "verb": "确认",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "旧记录",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="师姐确认议会内部泄密",
                content="师姐在第八章确认议会内部有人泄密，决定回头协助林舟。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["师姐", "林舟"]
            draft["chapter_hints"] = [8]
            draft["content"] = "师姐在第八章确认议会内部有人泄密，决定回头协助林舟。"
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "knowledge-state-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            scene_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "create-event-and-scene")
            knowledge_input = next(
                item for item in plan["timeline_merge_inputs"] if item["strategy"] == "upsert-canon-knowledge-state"
            )
            self.assertEqual(knowledge_input["apply_args"]["knowledge_subject_id"], "char-shijie")
            self.assertEqual(knowledge_input["apply_args"]["knowledge_reading_chapter"], 8)

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_ids=[scene_input["id"], knowledge_input["id"]],
                resolution_note="把师姐在第8章确认议会内部泄密同时写入 timeline/outline 与新的 canon knowledge-state。",
            )

            updated_canon_index = read_json(workspace / "state/canon-index.json", {})
            knowledge_states = updated_canon_index.get("knowledge_states", [])
            self.assertEqual(len(knowledge_states), 2)
            self.assertEqual(knowledge_states[0]["subject_id"], "char-protagonist")
            self.assertEqual(knowledge_states[0]["reading_chapter"], 4)
            self.assertEqual(knowledge_states[1]["subject_id"], "char-shijie")
            self.assertEqual(knowledge_states[1]["reading_chapter"], 8)

            followup_report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "knowledge-state-conflict" for issue in followup_report["issues"]))

    def test_consistency_check_detects_first_meeting_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 2,
                            "title": "第二章",
                            "summary": "",
                            "scenes": [
                                {
                                    "id": "scene-early-meeting",
                                    "title": "旧案同路",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist", "char-sulan"],
                                    "event_ids": [],
                                    "notes": "",
                                }
                            ],
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="林舟和苏岚初见",
                content="林舟和苏岚在第五章第一次见面。",
                kind="scene",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [5]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "first-meeting-conflict" for issue in report["issues"]))

    def test_consistency_check_detects_relationship_history_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-alliance",
                            "label": "林舟和苏岚结盟",
                            "chronological_index": 2,
                            "reading_chapter": 2,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "白塔",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟和苏岚重新结盟",
                content="林舟和苏岚在第六章结盟。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))
            issue = next(issue for issue in report["issues"] if issue["code"] == "relationship-history-conflict")
            self.assertEqual(issue["details"]["character_ids"], ["char-protagonist", "char-sulan"])

    def test_consistency_check_exempts_relationship_repeat_after_transition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-allied-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "allied",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-ruptured-mid",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚重新结盟",
                content="林舟和苏岚在第六章重新结盟。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章重新结盟。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_exempts_future_relationship_repeat_after_transition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-allied-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "allied",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-ruptured-mid",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-allied-late",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "allied",
                    "reading_chapter": 8,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚重新结盟",
                content="林舟和苏岚在第六章重新结盟。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章重新结盟。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_exempts_future_relationship_repeat_after_transition_for_zaidu_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-allied-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "allied",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-ruptured-mid",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-allied-late",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "allied",
                    "reading_chapter": 8,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚再度结盟",
                content="林舟和苏岚在第六章再度结盟。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章再度结盟。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_exempts_future_relationship_repeat_after_transition_for_chongguiyuhao_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-reconciled-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-ruptured-mid",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-reconciled-late",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 8,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚重归于好",
                content="林舟和苏岚在第六章重归于好。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章重归于好。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_detects_relationship_history_conflict_for_fanmu_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-ruptured-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚反目",
                content="林舟和苏岚在第六章反目。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章反目。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))
            issue = next(issue for issue in report["issues"] if issue["code"] == "relationship-history-conflict")
            self.assertEqual(issue["details"]["relation_token"], "反目")

    def test_consistency_check_exempts_future_relationship_repeat_after_transition_for_bingshiqianxian_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-reconciled-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-ruptured-mid",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-reconciled-late",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 8,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚冰释前嫌",
                content="林舟和苏岚在第六章冰释前嫌。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章冰释前嫌。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_detects_relationship_history_conflict_for_fanlian_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-ruptured-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚翻脸",
                content="林舟和苏岚在第六章翻脸。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章翻脸。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))
            issue = next(issue for issue in report["issues"] if issue["code"] == "relationship-history-conflict")
            self.assertEqual(issue["details"]["relation_token"], "翻脸")

    def test_consistency_check_exempts_future_relationship_repeat_after_transition_for_pojingchongyuan_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-reconciled-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-ruptured-mid",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-reconciled-late",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 8,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚破镜重圆",
                content="林舟和苏岚在第六章破镜重圆。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章破镜重圆。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_detects_relationship_history_conflict_for_naofan_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-ruptured-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚闹翻",
                content="林舟和苏岚在第六章闹翻。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章闹翻。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))
            issue = next(issue for issue in report["issues"] if issue["code"] == "relationship-history-conflict")
            self.assertEqual(issue["details"]["relation_token"], "闹翻")

    def test_consistency_check_exempts_future_relationship_repeat_after_transition_for_yanguiyuhao_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-reconciled-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-ruptured-mid",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-reconciled-late",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 8,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚言归于好",
                content="林舟和苏岚在第六章言归于好。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章言归于好。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_detects_relationship_history_conflict_for_chedifanlian_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-ruptured-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚彻底翻脸",
                content="林舟和苏岚在第六章彻底翻脸。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章彻底翻脸。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))
            issue = next(issue for issue in report["issues"] if issue["code"] == "relationship-history-conflict")
            self.assertEqual(issue["details"]["relation_token"], "彻底翻脸")

    def test_consistency_check_exempts_future_relationship_repeat_after_transition_for_woshouyanhe_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-reconciled-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-ruptured-mid",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-reconciled-late",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 8,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚握手言和",
                content="林舟和苏岚在第六章握手言和。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章握手言和。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_detects_relationship_history_conflict_for_enduanyijue_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-ruptured-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚恩断义绝",
                content="林舟和苏岚在第六章恩断义绝。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章恩断义绝。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))
            issue = next(issue for issue in report["issues"] if issue["code"] == "relationship-history-conflict")
            self.assertEqual(issue["details"]["relation_token"], "恩断义绝")

    def test_consistency_check_exempts_future_relationship_repeat_after_transition_for_zhongxiujiuhao_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-reconciled-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-ruptured-mid",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-reconciled-late",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 8,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚重修旧好",
                content="林舟和苏岚在第六章重修旧好。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章重修旧好。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_detects_relationship_history_conflict_for_sipolian_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-ruptured-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚撕破脸",
                content="林舟和苏岚在第六章撕破脸。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章撕破脸。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))
            issue = next(issue for issue in report["issues"] if issue["code"] == "relationship-history-conflict")
            self.assertEqual(issue["details"]["relation_token"], "撕破脸")

    def test_consistency_check_exempts_future_relationship_repeat_after_transition_for_yixiaominenchou_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-reconciled-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-ruptured-mid",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-reconciled-late",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 8,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚一笑泯恩仇",
                content="林舟和苏岚在第六章一笑泯恩仇。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章一笑泯恩仇。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_detects_relationship_history_conflict_for_fanmuchengchou_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-ruptured-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚反目成仇",
                content="林舟和苏岚在第六章反目成仇。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章反目成仇。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))
            issue = next(issue for issue in report["issues"] if issue["code"] == "relationship-history-conflict")
            self.assertEqual(issue["details"]["relation_token"], "反目成仇")

    def test_consistency_check_exempts_future_relationship_repeat_after_transition_for_huagangeweiyubo_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-reconciled-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-ruptured-mid",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-reconciled-late",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 8,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚化干戈为玉帛",
                content="林舟和苏岚在第六章化干戈为玉帛。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章化干戈为玉帛。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_detects_relationship_history_conflict_for_sipolianpi_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-ruptured-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚撕破脸皮",
                content="林舟和苏岚在第六章撕破脸皮。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章撕破脸皮。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))
            issue = next(issue for issue in report["issues"] if issue["code"] == "relationship-history-conflict")
            self.assertEqual(issue["details"]["relation_token"], "撕破脸皮")

    def test_consistency_check_exempts_future_relationship_repeat_after_transition_for_jinshiqianxian_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-reconciled-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-ruptured-mid",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 4,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-reconciled-late",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "reconciled",
                    "reading_chapter": 8,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚尽释前嫌",
                content="林舟和苏岚在第六章尽释前嫌。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章尽释前嫌。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_detects_relationship_history_conflict_for_fanmuweichou_wording(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-ruptured-early",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "ruptured",
                    "reading_chapter": 2,
                    "event_id": None,
                    "notes": "",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚反目为仇",
                content="林舟和苏岚在第六章反目为仇。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            draft["content"] = "林舟和苏岚在第六章反目为仇。"
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))
            issue = next(issue for issue in report["issues"] if issue["code"] == "relationship-history-conflict")
            self.assertEqual(issue["details"]["relation_token"], "反目为仇")

    def test_consistency_check_exempts_future_relationship_conflict_when_same_chapter_record_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["relationships"] = [
                {
                    "id": "rel-allied-current",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "allied",
                    "reading_chapter": 6,
                    "event_id": None,
                    "notes": "",
                },
                {
                    "id": "rel-allied-future",
                    "character_ids": ["char-protagonist", "char-sulan"],
                    "state": "allied",
                    "reading_chapter": 8,
                    "event_id": None,
                    "notes": "",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟和苏岚结盟",
                content="林舟和苏岚在第六章结盟。",
                kind="relationship",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [6]
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "relationship-history-conflict" for issue in report["issues"]))

    def test_consistency_check_detects_world_rule_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟提前知道组织首领身份",
                content="林舟在第七章就知道组织首领身份。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))

    def test_consistency_check_detects_world_rule_conflict_for_synonym_object_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章就知道组织首领是谁。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertTrue(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))

    def test_consistency_check_exempts_world_rule_exception_for_synonym_object_phrase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章就知道组织首领是谁。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))

    def test_consistency_check_exempts_world_rule_exception_for_synonym_object_phrase_without_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章就知道组织首领是谁。",
                kind="reveal",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["matched_exception_id"], "rulex-rule-001-linzhou-identity-ch7")
            self.assertEqual(exemption["details"]["exception_scope_base"], "same-chapter")
            self.assertEqual(exemption["details"]["exception_subject_scope"], "shared-subject")
            self.assertEqual(exemption["details"]["exception_match_mode"], "local-signal")
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-local-signal")

    def test_consistency_and_merge_plan_prefer_same_chapter_exception_over_prior_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "更早例外。",
                },
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "当前章正式例外。",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            result = ingest_idea(
                workspace,
                title="林舟提前知道组织首领是谁",
                content="林舟在第七章知道组织首领是谁。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["matched_exception_id"], "rulex-rule-001-linzhou-identity-ch7")
            self.assertEqual(exemption["details"]["exception_scope_base"], "same-chapter")
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, result["idea"]["id"])
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exceptions=rulex-rule-001-linzhou-identity-ch7", summary_text)
            self.assertNotIn("rulex-rule-001-linzhou-identity-ch5", summary_text)
            self.assertIn("direct=1", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_consistency_check_does_not_misread_other_subject_object_as_world_rule_hit_without_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "泄密真相正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-002",
                            "type": "hard-canon",
                            "label": "林舟在泄密真相正式揭露前不知道议会内部有人泄密",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="双人对白",
                content="林舟在第七章知道苏岚另有怀疑，苏岚在第七章知道议会内部有人泄密。",
                kind="reveal",
            )
            draft_path = workspace / "state" / "intake-drafts" / f"{result['idea']['id']}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            write_json(draft_path, draft)
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))

    def test_merge_plan_surfaces_existing_world_rule_exception_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="双人对白",
                content="林舟在第七章知道组织首领是谁，苏岚在第七章知道议会内部有人泄密。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, result["idea"]["id"])
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("subject_scope=split-subjects", summary_text)
            self.assertIn("exception_scope=same-chapter-split-subjects-claim-match", summary_text)
            self.assertIn("exception_scope_base=same-chapter", summary_text)
            self.assertIn("exception_subject_scope=split-subjects", summary_text)
            self.assertIn("exception_match_mode=claim-match", summary_text)
            self.assertIn("reuse-existing-exception", summary_text)
            self.assertIn("direct=0", summary_text)
            self.assertIn("review=1", summary_text)
            self.assertIn("constraints:review-subject-scope", summary_text)
            self.assertIn("constraints:annotate-existing-rule-note", summary_text)
            self.assertIn("timeline:review-same-chapter-beat", summary_text)
            self.assertIn("outline:review-same-chapter-scene", summary_text)
            self.assertIn("timeline/events.json", summary_text)
            self.assertIn("outline/scene-index.json", summary_text)
            self.assertNotIn("constraints:carry-forward-exception-note", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_merge_plan_marks_direct_existing_world_rule_exception_for_shared_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟提前知道组织首领是谁",
                content="林舟在第七章知道组织首领是谁。",
                kind="reveal",
            )
            report = check_idea_consistency(workspace, result["idea"]["id"])
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, result["idea"]["id"])
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("reuse-existing-exception", summary_text)
            self.assertIn("subject_scope=shared-subject", summary_text)
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertIn("exception_scope_base=same-chapter", summary_text)
            self.assertIn("exception_subject_scope=shared-subject", summary_text)
            self.assertIn("exception_match_mode=claim-match", summary_text)
            self.assertIn("direct=1", summary_text)
            self.assertIn("review=0", summary_text)
            self.assertIn("canon:reuse-existing-exception-record", summary_text)
            self.assertIn("constraints:reuse-existing-exception-note", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_merge_plan_keeps_same_chapter_claim_match_shared_when_extra_character_mention_has_no_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章知道组织首领是谁，苏岚在旁边听着。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual([claim["subject_name"] for claim in report["knowledge_claims"]], ["林舟"])
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertIn("direct=1", summary_text)
            self.assertIn("review=0", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_merge_plan_ignores_single_char_alias_inside_place_name_before_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": ["岚"],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "岚城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在岚城知道组织首领是谁，苏岚随后赶到。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual([claim["subject_name"] for claim in report["knowledge_claims"]], ["林舟"])
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_merge_plan_ignores_multi_char_alias_inside_place_name_before_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": ["阿岚"],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "阿岚街",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在阿岚街知道组织首领是谁，苏岚随后赶到。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual([claim["subject_name"] for claim in report["knowledge_claims"]], ["林舟"])
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_merge_plan_ignores_multi_char_alias_inside_setting_noun_before_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-bailang",
                    "name": "白狼",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-bailang"],
                            "location": "白狼营",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在白狼营知道组织首领是谁，白狼随后赶到。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "白狼"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual([claim["subject_name"] for claim in report["knowledge_claims"]], ["林舟"])
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_merge_plan_ignores_multi_char_alias_inside_organization_name_before_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-bailang",
                    "name": "白狼",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-bailang"],
                            "location": "白狼帮",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在白狼帮知道组织首领是谁，白狼随后赶到。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "白狼"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual([claim["subject_name"] for claim in report["knowledge_claims"]], ["林舟"])
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_merge_plan_ignores_multi_char_alias_inside_institution_name_before_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-bailang",
                    "name": "白狼",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-bailang"],
                            "location": "白狼会",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在白狼会知道组织首领是谁，白狼随后赶到。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "白狼"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual([claim["subject_name"] for claim in report["knowledge_claims"]], ["林舟"])
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_merge_plan_ignores_multi_char_alias_inside_artifact_name_before_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-bailang",
                    "name": "白狼",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-bailang"],
                            "location": "白狼令",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在白狼令知道组织首领是谁，白狼随后赶到。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "白狼"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual([claim["subject_name"] for claim in report["knowledge_claims"]], ["林舟"])
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_merge_plan_ignores_multi_char_alias_inside_compound_spell_name_before_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-bailang",
                    "name": "白狼",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-bailang"],
                            "location": "白狼封阵术",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在白狼封阵术知道组织首领是谁，白狼随后赶到。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "白狼"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual([claim["subject_name"] for claim in report["knowledge_claims"]], ["林舟"])
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_merge_plan_ignores_multi_char_alias_inside_action_prefixed_spell_name_before_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-bailang",
                    "name": "白狼",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-bailang"],
                            "location": "白狼封阵术",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟持白狼封阵术知道组织首领是谁，白狼随后赶到。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "白狼"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual([claim["subject_name"] for claim in report["knowledge_claims"]], ["林舟"])
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_merge_plan_ignores_multi_char_alias_inside_borrowed_spell_name_before_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-bailang",
                    "name": "白狼",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-bailang"],
                            "location": "白狼封阵术",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟借白狼封阵术知道组织首领是谁，白狼随后赶到。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "白狼"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual([claim["subject_name"] for claim in report["knowledge_claims"]], ["林舟"])
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_merge_plan_ignores_multi_char_alias_inside_controlled_artifact_name_before_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-bailang",
                    "name": "白狼",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-bailang"],
                            "location": "白狼巨舰",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟操控白狼巨舰知道组织首领是谁，白狼随后赶到。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "白狼"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual([claim["subject_name"] for claim in report["knowledge_claims"]], ["林舟"])
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_consistency_check_does_not_turn_nested_other_subject_knowledge_clause_into_rule_subject_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        },
                        {
                            "id": "rule-002",
                            "type": "hard-canon",
                            "label": "苏岚在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        },
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章意识到苏岚知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(
                [(claim["subject_name"], claim["object_key"]) for claim in report["knowledge_claims"]],
                [("苏岚", "组织首领是谁")],
            )
            world_rule_issues = [issue for issue in report["issues"] if issue["code"] == "world-rule-conflict"]
            self.assertEqual(len(world_rule_issues), 1)
            self.assertEqual(world_rule_issues[0]["details"]["rule_id"], "rule-002")

    def test_consistency_check_treats_message_recipient_before_knowledge_verb_as_shared_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "本章正式例外。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章告诉苏岚自己知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(
                [(claim["subject_name"], claim["object_key"]) for claim in report["knowledge_claims"]],
                [("林舟", "组织首领是谁")],
            )
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertIn("direct=1", summary_text)
            self.assertIn("review=0", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_consistency_check_treats_source_subject_before_knowledge_verb_as_shared_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "本章正式例外。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章从苏岚那里知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(
                [(claim["subject_name"], claim["object_key"]) for claim in report["knowledge_claims"]],
                [("林舟", "组织首领是谁")],
            )
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertIn("direct=1", summary_text)
            self.assertIn("review=0", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_consistency_check_treats_hearing_source_before_knowledge_verb_as_shared_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "本章正式例外。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章听苏岚提起后知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(
                [(claim["subject_name"], claim["object_key"]) for claim in report["knowledge_claims"]],
                [("林舟", "组织首领是谁")],
            )
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

    def test_consistency_check_treats_causal_trigger_subject_before_knowledge_verb_as_shared_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "本章正式例外。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章因苏岚一句话才知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(
                [(claim["subject_name"], claim["object_key"]) for claim in report["knowledge_claims"]],
                [("林舟", "组织首领是谁")],
            )
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

    def test_consistency_check_does_not_turn_speculative_other_subject_knowledge_clause_into_direct_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-bailang",
                    "name": "白狼",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-bailang"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        },
                        {
                            "id": "rule-002",
                            "type": "hard-canon",
                            "label": "白狼在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        },
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章怀疑白狼知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "白狼"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(report["knowledge_claims"])
            world_rule_issues = [issue for issue in report["issues"] if issue["code"] == "world-rule-conflict"]
            self.assertFalse(world_rule_issues)

    def test_consistency_check_ignores_demonstrative_between_speculation_and_other_subject_knowledge_clause(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-bailang",
                    "name": "白狼",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-bailang"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        },
                        {
                            "id": "rule-002",
                            "type": "hard-canon",
                            "label": "白狼在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        },
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章怀疑那个白狼知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "白狼"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(report["knowledge_claims"])
            world_rule_issues = [issue for issue in report["issues"] if issue["code"] == "world-rule-conflict"]
            self.assertFalse(world_rule_issues)

    def test_consistency_check_ignores_time_and_demonstrative_between_speculation_and_other_subject_knowledge_clause(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-bailang",
                    "name": "白狼",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-bailang"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        },
                        {
                            "id": "rule-002",
                            "type": "hard-canon",
                            "label": "白狼在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        },
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章怀疑那时那个白狼知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "白狼"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(report["knowledge_claims"])
            world_rule_issues = [issue for issue in report["issues"] if issue["code"] == "world-rule-conflict"]
            self.assertFalse(world_rule_issues)

    def test_consistency_check_ignores_reported_rumor_prefix_before_other_subject_knowledge_clause(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-bailang",
                    "name": "白狼",
                    "aliases": [],
                    "role": "supporting",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-bailang"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        },
                        {
                            "id": "rule-002",
                            "type": "hard-canon",
                            "label": "白狼在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        },
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="据说那时那个白狼知道组织首领是谁，林舟也只记下了这个说法。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "白狼"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(report["knowledge_claims"])
            world_rule_issues = [issue for issue in report["issues"] if issue["code"] == "world-rule-conflict"]
            self.assertFalse(world_rule_issues)

    def test_merge_plan_does_not_infer_other_subject_claim_from_later_rule_subject_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章知道组织首领是谁，提起苏岚时，林舟又知道黑潮藏身处。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "苏岚"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(
                [claim["subject_name"] for claim in report["knowledge_claims"]],
                ["林舟", "林舟"],
            )
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertEqual(constraints_action["readiness"], "ready")

    def test_merge_plan_marks_same_chapter_local_signal_as_evidence_only_without_subject_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章就知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "same-chapter-shared-subject-local-signal")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("canon:review-exception-evidence", summary_text)
            self.assertIn("constraints:annotate-existing-rule-note", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertNotIn("timeline:review-same-chapter-beat", summary_text)
            self.assertNotIn("outline:review-same-chapter-scene", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_merge_plan_marks_prior_exception_review_impacts_by_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "这条更早知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟在第七章再次确认组织首领是谁",
                content="林舟在第七章知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope_base"], "prior-exception")
            self.assertEqual(exemption["details"]["exception_subject_scope"], "shared-subject")
            self.assertEqual(exemption["details"]["exception_match_mode"], "claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=prior-exception-shared-subject-claim-match", summary_text)
            self.assertIn("exception_scope_base=prior-exception", summary_text)
            self.assertIn("exception_subject_scope=shared-subject", summary_text)
            self.assertIn("exception_match_mode=claim-match", summary_text)
            self.assertIn("direct=0", summary_text)
            self.assertIn("review=1", summary_text)
            self.assertIn("canon:review-exception-continuity", summary_text)
            self.assertIn("constraints:review-exception-chain", summary_text)
            self.assertIn("timeline:review-post-exception-beat", summary_text)
            self.assertIn("outline:review-post-exception-scene", summary_text)
            self.assertIn("canon:keep-existing-exception-record", summary_text)
            self.assertIn("constraints:carry-forward-exception-note", summary_text)
            self.assertIn("timeline:append-post-exception-beat", summary_text)
            self.assertIn("outline:append-post-exception-scene-note", summary_text)
            self.assertIn("timeline/events.json", summary_text)
            self.assertIn("outline/scene-index.json", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_merge_plan_marks_prior_exception_rewrite_write_shapes_for_existing_event_and_scene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "这条更早知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        },
                        {
                            "id": "event-identity-recheck",
                            "label": "identity-recheck",
                            "chronological_index": 7,
                            "reading_chapter": 7,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "既有事件记录。",
                        },
                    ]
                },
            )
            write_json(
                workspace / "outline/scene-index.json",
                {
                    "chapters": [
                        {
                            "chapter": 7,
                            "scenes": [
                                {
                                    "id": "scene-identity-recheck",
                                    "title": "identity-recheck",
                                    "pov": "林舟",
                                    "status": "planned",
                                    "characters": ["char-protagonist"],
                                    "event_ids": ["event-identity-recheck"],
                                    "notes": "既有场景记录。",
                                }
                            ],
                        }
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟在第七章再次确认组织首领是谁",
                content="林舟在第七章知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["timeline_candidates"] = [{"event_label": "identity-recheck"}]
            draft["outline_candidates"] = [{"scene_title": "identity-recheck"}]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=prior-exception-shared-subject-claim-match", summary_text)
            self.assertIn("timeline:rewrite-post-exception-beat", summary_text)
            self.assertIn("outline:rewrite-post-exception-scene-note", summary_text)
            self.assertNotIn("timeline:append-post-exception-beat", summary_text)
            self.assertNotIn("outline:append-post-exception-scene-note", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_merge_plan_marks_prior_exception_annotation_only_when_no_timeline_or_outline_write_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "这条更早知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟已经知道组织首领是谁。",
                kind="world",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=prior-exception-shared-subject-claim-match", summary_text)
            self.assertIn("canon:keep-existing-exception-record", summary_text)
            self.assertIn("canon:annotate-existing-exception-record", summary_text)
            self.assertIn("constraints:annotate-existing-rule-note", summary_text)
            self.assertNotIn("constraints:carry-forward-exception-note", summary_text)
            self.assertNotIn("timeline:review-post-exception-beat", summary_text)
            self.assertNotIn("outline:review-post-exception-scene", summary_text)
            self.assertNotIn("timeline/events.json", summary_text)
            self.assertNotIn("outline/scene-index.json", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_merge_plan_marks_prior_exception_evidence_only_for_local_signal_without_chain_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "这条更早知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章就知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope_base"], "prior-exception")
            self.assertEqual(exemption["details"]["exception_match_mode"], "local-signal")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=prior-exception-shared-subject-local-signal", summary_text)
            self.assertIn("canon:annotate-existing-exception-record", summary_text)
            self.assertIn("constraints:annotate-existing-rule-note", summary_text)
            self.assertIn("canon:review-exception-evidence", summary_text)
            self.assertNotIn("constraints:review-exception-chain", summary_text)
            self.assertNotIn("canon:review-exception-continuity", summary_text)
            self.assertNotIn("timeline:review-post-exception-beat", summary_text)
            self.assertNotIn("outline:review-post-exception-scene", summary_text)
            self.assertNotIn("constraints:carry-forward-exception-note", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_merge_plan_keeps_prior_exception_local_signal_as_evidence_only_when_other_subject_is_outside_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "这条更早知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章就知道组织首领是谁。苏岚在旁边看着。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "prior-exception-shared-subject-local-signal")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("canon:review-exception-evidence", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_merge_plan_marks_prior_exception_local_signal_with_mixed_subjects_as_subject_scope_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "这条更早知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟和苏岚在第七章都知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "prior-exception-mixed-subjects-local-signal")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("canon:review-exception-evidence", summary_text)
            self.assertIn("constraints:review-subject-scope", summary_text)
            self.assertNotIn("constraints:review-exception-chain", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_merge_plan_keeps_prior_exception_local_signal_shared_when_rule_subject_is_reintroduced_before_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "这条更早知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟和苏岚对视时，林舟在第七章就知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "prior-exception-shared-subject-local-signal")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("canon:review-exception-evidence", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertNotIn("constraints:review-exception-chain", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_merge_plan_marks_prior_exception_local_signal_mixed_when_other_subject_takes_later_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "这条更早知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章知道组织首领是谁，苏岚也在第七章知道议会内部有人泄密。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "prior-exception-mixed-subjects-local-signal")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("canon:review-exception-evidence", summary_text)
            self.assertIn("constraints:review-subject-scope", summary_text)
            self.assertNotIn("constraints:review-exception-chain", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_merge_plan_keeps_prior_exception_local_signal_shared_when_rule_subject_reappears_before_later_knowledge_verb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "这条更早知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章知道组织首领是谁，苏岚看着他，林舟又知道黑潮藏身处。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = []
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "prior-exception-shared-subject-local-signal")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("canon:review-exception-evidence", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)
            self.assertNotIn("constraints:review-exception-chain", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_merge_plan_marks_prior_exception_claim_match_narrative_note_as_carry_forward_without_event_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "这条更早知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章知道组织首领是谁。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope_base"], "prior-exception")
            self.assertEqual(exemption["details"]["exception_match_mode"], "claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=prior-exception-shared-subject-claim-match", summary_text)
            self.assertIn("constraints:carry-forward-exception-note", summary_text)
            self.assertIn("constraints:review-exception-chain", summary_text)
            self.assertNotIn("timeline:review-post-exception-beat", summary_text)
            self.assertNotIn("outline:review-post-exception-scene", summary_text)
            self.assertNotIn("timeline/events.json", summary_text)
            self.assertNotIn("outline/scene-index.json", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_merge_plan_marks_prior_exception_split_subject_claim_match_as_annotate_without_event_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-sulan",
                    "name": "苏岚",
                    "aliases": [],
                    "role": "deuteragonist",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "这条更早知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-010",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-010",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist", "char-sulan"],
                            "location": "主城",
                            "notes": "",
                        }
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章知道组织首领是谁，苏岚在第七章知道议会内部有人泄密。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope_base"], "prior-exception")
            self.assertEqual(exemption["details"]["exception_subject_scope"], "split-subjects")
            self.assertEqual(exemption["details"]["exception_match_mode"], "claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertIn("exception_scope=prior-exception-split-subjects-claim-match", summary_text)
            self.assertIn("constraints:review-subject-scope", summary_text)
            self.assertIn("constraints:annotate-existing-rule-note", summary_text)
            self.assertNotIn("constraints:carry-forward-exception-note", summary_text)
            self.assertNotIn("timeline:review-post-exception-beat", summary_text)
            self.assertNotIn("outline:review-post-exception-scene", summary_text)
            self.assertEqual(constraints_action["readiness"], "needs-review")

    def test_prior_exception_split_subject_claim_match_with_narrative_targets_reuses_exception_and_writes_other_subject_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["characters"].append(
                {
                    "id": "char-shijie",
                    "name": "师姐",
                    "aliases": [],
                    "role": "mentor",
                    "status": "alive",
                    "death_event_id": None,
                }
            )
            canon_index["knowledge_states"] = [
                # 留空，避免这个最小测试先被旧 knowledge-state gate 挡住；
                # 这里要验证的是 split-subject 直通策略本身。
            ]
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-林舟-黑潮真正目标-ch10",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在黑潮真正目标正式揭露前不知道黑潮真正目标",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "黑潮真正目标",
                    "object_phrase": "黑潮真正目标",
                    "reading_chapter": 10,
                    "event_id": None,
                    "notes": "林舟在第10章的提前知情点是正式 exception。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在黑潮真正目标正式揭露前不知道黑潮真正目标",
                            "applies_until_event_id": "event-013",
                            "notes": "",
                        }
                    ]
                },
            )
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-013",
                            "label": "黑潮真正目标正式揭露",
                            "chronological_index": 13,
                            "reading_chapter": 13,
                            "participants": ["char-protagonist", "char-shijie"],
                            "location": "白塔议事厅",
                            "notes": "",
                        }
                    ]
                },
            )

            result = ingest_idea(
                workspace,
                title="双人同章知道黑潮目标",
                content="林舟在第十一章白塔议事厅知道黑潮真正目标，师姐在第十一章白塔议事厅知道黑潮真正目标。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟", "师姐"]
            draft["chapter_hints"] = [11]
            draft["location_candidates"] = ["白塔议事厅"]
            draft["suggested_domains"] = ["outline", "timeline"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            exemption = next(item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied")
            self.assertEqual(exemption["details"]["exception_scope"], "prior-exception-split-subjects-claim-match")

            plan = plan_idea_merge(workspace, idea_id)
            constraints_action = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            summary_text = " ".join(constraints_action["planned_writes"])
            self.assertEqual(constraints_action["readiness"], "ready")
            self.assertIn("exception_scope=prior-exception-split-subjects-claim-match", summary_text)
            self.assertIn("direct=1", summary_text)
            self.assertIn("review=0", summary_text)
            self.assertIn("canon:reuse-existing-exception-record", summary_text)
            self.assertIn("constraints:reuse-existing-exception-note", summary_text)
            self.assertNotIn("constraints:review-subject-scope", summary_text)

            scene_input = next(item for item in plan["timeline_merge_inputs"] if item["strategy"] == "create-event-and-scene")
            knowledge_inputs = [
                item
                for item in plan["timeline_merge_inputs"]
                if item["strategy"] in {"upsert-canon-knowledge-state", "update-existing-knowledge-state"}
            ]
            self.assertEqual(len(knowledge_inputs), 1)
            self.assertEqual(knowledge_inputs[0]["apply_args"]["knowledge_subject_id"], "char-shijie")
            self.assertEqual(knowledge_inputs[0]["apply_args"]["knowledge_reading_chapter"], 11)

            apply_idea_merge(
                workspace,
                idea_id=idea_id,
                merge_input_ids=[scene_input["id"], knowledge_inputs[0]["id"]],
                resolution_note="沿用林舟既有 exception，只把师姐在第11章得知黑潮真正目标写入新的 knowledge-state。",
            )

            updated_canon_index = read_json(workspace / "state/canon-index.json", {})
            knowledge_states = updated_canon_index.get("knowledge_states", [])
            self.assertEqual(len(knowledge_states), 1)
            self.assertEqual(knowledge_states[0]["subject_id"], "char-shijie")
            self.assertEqual(knowledge_states[0]["reading_chapter"], 11)
            self.assertEqual(len(updated_canon_index.get("world_rule_exceptions", [])), 1)
            self.assertEqual(
                updated_canon_index["world_rule_exceptions"][0]["id"],
                "rulex-rule-001-林舟-黑潮真正目标-ch10",
            )

            refreshed = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in refreshed["issues"]))
            self.assertFalse(any(issue["code"] == "knowledge-state-conflict" for issue in refreshed["issues"]))

    def test_merge_plan_combines_world_rule_conflicts_and_exemptions_into_one_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "这条提前知情点作为正式例外保留。",
                }
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-leader-reveal",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        },
                        {
                            "id": "event-leak-reveal",
                            "label": "议会泄密真相揭露",
                            "chronological_index": 11,
                            "reading_chapter": 11,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        },
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-leader-reveal",
                            "notes": "",
                        },
                        {
                            "id": "rule-002",
                            "type": "hard-canon",
                            "label": "林舟在议会泄密真相揭露前不知道议会内部有人泄密",
                            "applies_until_event_id": "event-leak-reveal",
                            "notes": "",
                        },
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="林舟双重提前知情",
                content="林舟在第七章知道组织首领是谁，也知道议会内部有人泄密。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertEqual(len([issue for issue in report["issues"] if issue["code"] == "world-rule-conflict"]), 1)
            self.assertEqual(len([item for item in report["exemptions"] if item["code"] == "world-rule-exemption-applied"]), 1)

            plan = plan_idea_merge(workspace, idea_id)
            constraints_summaries = [
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and action.get("merge_input_id") is None
            ]
            self.assertEqual(len(constraints_summaries), 1)
            summary = constraints_summaries[0]
            planned = summary["planned_writes"]
            summary_text = " ".join(summary["planned_writes"])
            self.assertIn("其中 1 条仍需处理，1 条已有正式 exception 覆盖", summary["summary"])
            self.assertTrue(any(line.startswith("shared-world-rule-context") for line in planned))
            self.assertEqual(summary_text.count("canon/world-rules.md"), 1)
            self.assertEqual(summary_text.count("constraints/constraints.json"), 1)
            self.assertEqual(summary_text.count("state/canon-index.json"), 1)
            self.assertIn("rule-001: reuse-existing-exception", summary_text)
            self.assertIn("rule-002:", summary_text)
            self.assertTrue(any("world-rule conflict x1" in signal for signal in summary["source_signals"]))
            self.assertTrue(any("world-rule exemptions x1" in signal for signal in summary["source_signals"]))

    def test_merge_plan_compresses_shared_review_tokens_for_multiple_exemptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch5",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "更早知情例外。",
                },
                {
                    "id": "rulex-rule-002-linzhou-leak-ch5",
                    "rule_id": "rule-002",
                    "rule_label": "林舟在泄密真相正式揭露前不知道议会内部有人泄密",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "议会内部有人泄密",
                    "object_phrase": "议会内部有人泄密",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "更早知情例外。",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-leader-reveal",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        },
                        {
                            "id": "event-leak-reveal",
                            "label": "泄密真相正式揭露",
                            "chronological_index": 11,
                            "reading_chapter": 11,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        },
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-leader-reveal",
                            "notes": "",
                        },
                        {
                            "id": "rule-002",
                            "type": "hard-canon",
                            "label": "林舟在泄密真相正式揭露前不知道议会内部有人泄密",
                            "applies_until_event_id": "event-leak-reveal",
                            "notes": "",
                        },
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章知道组织首领是谁，也知道议会内部有人泄密。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            summary = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            planned = summary["planned_writes"]
            summary_text = " ".join(planned)
            self.assertTrue(any(line.startswith("shared-exemption-review") for line in planned))
            self.assertEqual(summary_text.count("constraints:review-exception-chain"), 1)
            self.assertEqual(summary_text.count("constraints:carry-forward-exception-note"), 1)
            self.assertIn("rule-001: reuse-existing-exception", summary_text)
            self.assertIn("rule-002: reuse-existing-exception", summary_text)

    def test_merge_plan_compresses_shared_base_tokens_for_mixed_direct_and_review_exemptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            canon_index = read_json(workspace / "state/canon-index.json", {})
            canon_index["world_rule_exceptions"] = [
                {
                    "id": "rulex-rule-001-linzhou-identity-ch7",
                    "rule_id": "rule-001",
                    "rule_label": "林舟在首领身份正式揭露前不知道组织首领身份",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "组织首领身份",
                    "object_phrase": "组织首领身份",
                    "reading_chapter": 7,
                    "event_id": None,
                    "notes": "本章正式例外。",
                },
                {
                    "id": "rulex-rule-002-linzhou-leak-ch5",
                    "rule_id": "rule-002",
                    "rule_label": "林舟在泄密真相正式揭露前不知道议会内部有人泄密",
                    "subject_id": "char-protagonist",
                    "subject_name": "林舟",
                    "object_key": "议会内部有人泄密",
                    "object_phrase": "议会内部有人泄密",
                    "reading_chapter": 5,
                    "event_id": None,
                    "notes": "更早知情例外。",
                },
            ]
            write_json(workspace / "state/canon-index.json", canon_index)
            write_json(
                workspace / "timeline/events.json",
                {
                    "events": [
                        {
                            "id": "event-leader-reveal",
                            "label": "首领身份正式揭露",
                            "chronological_index": 10,
                            "reading_chapter": 10,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        },
                        {
                            "id": "event-leak-reveal",
                            "label": "泄密真相正式揭露",
                            "chronological_index": 11,
                            "reading_chapter": 11,
                            "participants": ["char-protagonist"],
                            "location": "主城",
                            "notes": "",
                        },
                    ]
                },
            )
            write_json(
                workspace / "constraints/constraints.json",
                {
                    "rules": [
                        {
                            "id": "rule-001",
                            "type": "hard-canon",
                            "label": "林舟在首领身份正式揭露前不知道组织首领身份",
                            "applies_until_event_id": "event-leader-reveal",
                            "notes": "",
                        },
                        {
                            "id": "rule-002",
                            "type": "hard-canon",
                            "label": "林舟在泄密真相正式揭露前不知道议会内部有人泄密",
                            "applies_until_event_id": "event-leak-reveal",
                            "notes": "",
                        },
                    ]
                },
            )
            result = ingest_idea(
                workspace,
                title="",
                content="林舟在第七章知道组织首领是谁，也知道议会内部有人泄密。",
                kind="reveal",
            )
            idea_id = result["idea"]["id"]
            draft_path = workspace / "state" / "intake-drafts" / f"{idea_id}.json"
            draft = read_json(draft_path, {})
            draft["character_mentions"] = ["林舟"]
            draft["chapter_hints"] = [7]
            draft["suggested_domains"] = ["canon"]
            write_json(draft_path, draft)

            report = check_idea_consistency(workspace, idea_id)
            self.assertFalse(any(issue["code"] == "world-rule-conflict" for issue in report["issues"]))

            plan = plan_idea_merge(workspace, idea_id)
            summary = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "constraints" and "已有正式 exception" in action["summary"]
            )
            planned = summary["planned_writes"]
            summary_text = " ".join(planned)
            self.assertTrue(any(line.startswith("shared-exemption-base") for line in planned))
            self.assertFalse(any(line.startswith("shared-exemption-review") for line in planned))
            self.assertEqual(summary_text.count("canon:reuse-exception"), 1)
            self.assertEqual(summary_text.count("constraints:reuse-exception"), 1)
            self.assertIn("rule-001: reuse-existing-exception", summary_text)
            self.assertIn("rule-002: reuse-existing-exception", summary_text)

    def test_constraints_group_explainer_does_not_repeat_shared_base_tokens_in_shared_exemption_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-001",
                            "matched_exception_id": "rulex-001",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "same-chapter-shared-subject-claim-match",
                        },
                    },
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-002",
                            "matched_exception_id": "rulex-002",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "prior-exception-shared-subject-claim-match",
                        },
                    },
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-003",
                            "matched_exception_id": "rulex-003",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "prior-exception-shared-subject-claim-match",
                        },
                    },
                ],
            }
            draft = {
                "kind": "reveal",
                "character_mentions": ["林舟"],
                "suggested_domains": ["canon"],
            }
            summary = _constraints_group_explainer(workspace, [], report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            base_line = next(line for line in planned if line.startswith("shared-exemption-base"))
            review_line = next(line for line in planned if line.startswith("shared-exemption-review"))
            self.assertIn("domains=canon, constraints", base_line)
            self.assertIn(
                "impacts=canon:reuse-exception, constraints:reuse-exception",
                base_line,
            )
            self.assertNotIn("domains=canon, constraints", review_line)
            self.assertNotIn("targets=canon/world-rules.md, constraints/constraints.json, state/canon-index.json", review_line)
            self.assertNotIn("canon:reuse-exception", review_line)
            self.assertNotIn("constraints:reuse-exception", review_line)
            self.assertIn(
                "review_impacts=canon:review-exception-continuity, constraints:review-exception-chain",
                review_line,
            )
            self.assertIn(
                "review_write_shapes=canon:keep-existing-exception-record, constraints:carry-forward-exception-note",
                review_line,
            )

    def test_constraints_group_explainer_compresses_shared_exemption_scope_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-001",
                            "matched_exception_id": "rulex-001",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "same-chapter-shared-subject-claim-match",
                        },
                    },
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-002",
                            "matched_exception_id": "rulex-002",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "prior-exception-shared-subject-claim-match",
                        },
                    },
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-003",
                            "matched_exception_id": "rulex-003",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "prior-exception-shared-subject-claim-match",
                        },
                    },
                ],
            }
            draft = {
                "kind": "reveal",
                "character_mentions": ["林舟"],
                "suggested_domains": ["canon"],
            }
            summary = _constraints_group_explainer(workspace, [], report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            all_scope_line = next(
                line
                for line in planned
                if line.startswith("shared-exemption-scope")
                and "rules=rule-001, rule-002, rule-003" in line
            )
            partial_scope_line = next(
                line
                for line in planned
                if line.startswith("shared-exemption-scope")
                and "rules=rule-002, rule-003" in line
            )
            self.assertIn("subject_scope=shared-subject", all_scope_line)
            self.assertIn("exception_subject_scope=shared-subject", all_scope_line)
            self.assertIn("exception_match_mode=claim-match", all_scope_line)
            self.assertIn("exception_scope=prior-exception-shared-subject-claim-match", partial_scope_line)
            self.assertIn("exception_scope_base=prior-exception", partial_scope_line)
            shared_links_line = next(line for line in planned if line.startswith("shared-exemption-links"))
            self.assertIn("rule-002:rulex-002", shared_links_line)
            self.assertIn("rule-003:rulex-003", shared_links_line)
            rule1_line = next(line for line in planned if line.startswith("rule-001: reuse-existing-exception"))
            self.assertIn("exception_scope=same-chapter-shared-subject-claim-match", rule1_line)
            self.assertIn("exception_scope_base=same-chapter", rule1_line)
            self.assertNotIn("subject_scope=shared-subject", rule1_line)
            self.assertNotIn("exception_subject_scope=shared-subject", rule1_line)
            self.assertNotIn("exception_match_mode=claim-match", rule1_line)
            self.assertFalse(any(line.startswith("rule-002: reuse-existing-exception") for line in planned))
            self.assertFalse(any(line.startswith("rule-003: reuse-existing-exception") for line in planned))

    def test_constraints_group_explainer_compresses_shared_exemption_rule_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-001",
                            "matched_exception_id": "rulex-001",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "same-chapter-shared-subject-claim-match",
                        },
                    },
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-002",
                            "matched_exception_id": "rulex-002",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "prior-exception-shared-subject-claim-match",
                        },
                    },
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-003",
                            "matched_exception_id": "rulex-003",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "prior-exception-shared-subject-claim-match",
                        },
                    },
                ],
            }
            draft = {
                "kind": "reveal",
                "character_mentions": ["林舟"],
                "suggested_domains": ["canon"],
            }
            summary = _constraints_group_explainer(workspace, [], report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            shared_subjects = next(
                line
                for line in planned
                if line.startswith("shared-exemption-rule-tokens")
                and "rules=rule-001, rule-002, rule-003" in line
            )
            shared_review_state = next(
                line
                for line in planned
                if line.startswith("shared-exemption-rule-tokens")
                and "rules=rule-002, rule-003" in line
            )
            shared_links_line = next(line for line in planned if line.startswith("shared-exemption-links"))
            self.assertIn("subjects=林舟", shared_subjects)
            self.assertIn("direct=0", shared_review_state)
            self.assertIn("review=1", shared_review_state)
            self.assertIn("rule-002:rulex-002", shared_links_line)
            self.assertIn("rule-003:rulex-003", shared_links_line)
            rule1_line = next(line for line in planned if line.startswith("rule-001: reuse-existing-exception"))
            self.assertIn("direct=1", rule1_line)
            self.assertIn("review=0", rule1_line)
            self.assertNotIn("subjects=林舟", rule1_line)
            self.assertFalse(any(line.startswith("rule-002: reuse-existing-exception") for line in planned))
            self.assertFalse(any(line.startswith("rule-003: reuse-existing-exception") for line in planned))

    def test_constraints_group_explainer_collapses_exception_id_only_exemption_rows_into_shared_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            report = {
                "issues": [],
                "exemptions": [
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-001",
                            "matched_exception_id": "rulex-001",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "same-chapter-shared-subject-claim-match",
                        },
                    },
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-002",
                            "matched_exception_id": "rulex-002",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "prior-exception-shared-subject-claim-match",
                        },
                    },
                    {
                        "code": "world-rule-exemption-applied",
                        "details": {
                            "rule_id": "rule-003",
                            "matched_exception_id": "rulex-003",
                            "matched_exception_subject_name": "林舟",
                            "exception_scope": "prior-exception-shared-subject-claim-match",
                        },
                    },
                ],
            }
            draft = {
                "kind": "reveal",
                "character_mentions": ["林舟"],
                "suggested_domains": ["canon"],
            }
            summary = _constraints_group_explainer(workspace, [], report, draft)
            self.assertIsNotNone(summary)
            planned = summary["planned_writes"]
            shared_links_line = next(line for line in planned if line.startswith("shared-exemption-links"))
            self.assertIn("rule-002:rulex-002", shared_links_line)
            self.assertIn("rule-003:rulex-003", shared_links_line)
            self.assertIn("rule-001: reuse-existing-exception", " ".join(planned))
            self.assertFalse(any(line.startswith("rule-002: reuse-existing-exception") for line in planned))
            self.assertFalse(any(line.startswith("rule-003: reuse-existing-exception") for line in planned))

    def test_pipeline_can_execute_consistency_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            result = ingest_idea(
                workspace,
                title="测试 pending",
                content="新增一个关键场景。",
                kind="scene",
            )
            pipeline = run_outline_workspace_pipeline(workspace, action="check-consistency", execute=True, idea_id=result["idea"]["id"])
            self.assertTrue(pipeline["executed"])
            self.assertIn("consistency_report", pipeline)


if __name__ == "__main__":
    unittest.main()
