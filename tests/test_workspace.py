from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace import check_idea_consistency
from novel_outline_workspace.merge import apply_idea_merge, plan_idea_merge
from novel_outline_workspace.orchestrator import run_outline_workspace_pipeline
from novel_outline_workspace.workspace import backfill_intake_drafts, collect_workspace_status, ingest_idea, init_workspace, read_json, validate_workspace, write_json


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
            self.assertEqual(constraints_summary["readiness"], "needs-review")
            self.assertIn("timeline/events.json", constraints_summary["target_files"])
            self.assertIn("constraints/constraints.json", constraints_summary["target_files"])
            self.assertIn("rule-001", " / ".join(constraints_summary["planned_writes"]))
            self.assertIn("direct=", " / ".join(constraints_summary["planned_writes"]))
            self.assertIn("domains=", " / ".join(constraints_summary["planned_writes"]))
            self.assertIn("impacts=", " / ".join(constraints_summary["planned_writes"]))
            self.assertIn("direct_impacts=", " / ".join(constraints_summary["planned_writes"]))
            self.assertIn("review_impacts=", " / ".join(constraints_summary["planned_writes"]))
            self.assertIn("targets=", " / ".join(constraints_summary["planned_writes"]))
            self.assertIn("rule-002", " / ".join(constraints_summary["planned_writes"]))
            self.assertIn("timeline:update-event", " / ".join(constraints_summary["planned_writes"]))
            self.assertIn("canon:record-exception", " / ".join(constraints_summary["planned_writes"]))
            self.assertIn("constraints:update-cutoff", " / ".join(constraints_summary["planned_writes"]))
            self.assertIn("constraints:note-exception", " / ".join(constraints_summary["planned_writes"]))
            self.assertTrue(any("world-rule conflict" in signal for signal in constraints_summary["source_signals"]))
            timeline_actions = [action for action in plan["proposed_actions"] if action["domain"] == "timeline"]
            outline_actions = [action for action in plan["proposed_actions"] if action["domain"] == "outline"]
            self.assertEqual(len(timeline_actions), 3)
            self.assertEqual(len(outline_actions), 3)
            merged_timeline_action = next(action for action in timeline_actions if "第 7 章" in action["summary"])
            self.assertIsNone(merged_timeline_action["merge_input_id"])
            rule2_exception = next(
                action
                for action in plan["proposed_actions"]
                if action["domain"] == "canon" and action.get("merge_input_id") == "timeline-merge-rule-note-006"
            )
            self.assertTrue(any("议会内部有人泄密" in signal for signal in rule2_exception["source_signals"]))

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
                            "location": "黑港",
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
                            "location": "黑港",
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
                title="林舟提前知道组织首领是谁",
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
                title="林舟提前知道组织首领是谁",
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
                title="林舟提前知道组织首领是谁",
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
            self.assertEqual(constraints_action["readiness"], "ready")

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
            summary_text = " ".join(summary["planned_writes"])
            self.assertIn("其中 1 条仍需处理，1 条已有正式 exception 覆盖", summary["summary"])
            self.assertIn("rule-001: reuse-existing-exception", summary_text)
            self.assertIn("rule-002:", summary_text)
            self.assertTrue(any("world-rule conflict x1" in signal for signal in summary["source_signals"]))
            self.assertTrue(any("world-rule exemptions x1" in signal for signal in summary["source_signals"]))

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
