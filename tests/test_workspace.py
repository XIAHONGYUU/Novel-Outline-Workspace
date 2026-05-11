from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace.merge import apply_idea_merge, plan_idea_merge
from novel_outline_workspace.orchestrator import run_outline_workspace_pipeline
from novel_outline_workspace.workspace import collect_workspace_status, init_workspace, read_json, validate_workspace, write_json


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
            idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
            idea_log["ideas"].append(
                {
                    "id": "idea-20260511-001",
                    "title": "女主提前知道真相",
                    "kind": "reveal",
                    "status": "pending",
                    "source": "manual",
                    "content": "她在第七章就知道组织首领身份。",
                    "tags": ["女主", "真相"],
                    "target_files": [],
                    "created_at": "2026-05-11T00:00:00Z",
                    "updated_at": "2026-05-11T00:00:00Z",
                    "resolution_note": "",
                }
            )
            write_json(workspace / "state/idea-log.json", idea_log)

            plan = plan_idea_merge(workspace, "idea-20260511-001")
            self.assertIn("canon", plan["suggested_domains"])
            self.assertTrue((workspace / "state/merge-plans/idea-20260511-001.json").exists())
            self.assertTrue((workspace / "views/merge-plans/idea-20260511-001.html").exists())

            result = apply_idea_merge(
                workspace,
                idea_id="idea-20260511-001",
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

    def test_orchestrator_recommends_pending_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "demo"
            init_workspace(workspace, "测试小说", "林舟")
            idea_log = read_json(workspace / "state/idea-log.json", {"ideas": []})
            idea_log["ideas"].append(
                {
                    "id": "idea-20260511-002",
                    "title": "测试 pending",
                    "kind": "scene",
                    "status": "pending",
                    "source": "manual",
                    "content": "新增一个关键场景。",
                    "tags": [],
                    "target_files": [],
                    "created_at": "2026-05-11T00:00:00Z",
                    "updated_at": "2026-05-11T00:00:00Z",
                    "resolution_note": "",
                }
            )
            write_json(workspace / "state/idea-log.json", idea_log)
            result = run_outline_workspace_pipeline(workspace)
            self.assertEqual(result["recommended_action"], "plan-merge")
            self.assertEqual(result["idea_id"], "idea-20260511-002")


if __name__ == "__main__":
    unittest.main()
