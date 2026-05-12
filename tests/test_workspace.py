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
from novel_outline_workspace.workspace import collect_workspace_status, ingest_idea, init_workspace, read_json, validate_workspace, write_json


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
            self.assertTrue((workspace / "state" / "consistency-checks" / f"{result['idea']['id']}.json").exists())
            self.assertTrue((workspace / "views" / "consistency-checks" / f"{result['idea']['id']}.html").exists())

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
