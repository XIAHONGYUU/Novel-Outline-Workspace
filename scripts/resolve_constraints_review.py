#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace.constraints_review import record_constraints_review_decision


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a deterministic constraints-review decision for one idea.")
    parser.add_argument("--workspace", required=True, help="Workspace directory.")
    parser.add_argument("--idea-id", required=True, help="Idea id to resolve.")
    parser.add_argument(
        "--decision",
        choices=["approved-ready-merge-inputs", "rejected"],
        default="approved-ready-merge-inputs",
        help="Decision to record.",
    )
    parser.add_argument(
        "--merge-input-id",
        action="append",
        default=[],
        help="Optional ready merge input ids to approve. Defaults to all ready merge inputs.",
    )
    parser.add_argument(
        "--resolution-note",
        required=True,
        help="Resolution note that will be reused if the approved merge inputs are later applied.",
    )
    parser.add_argument("--reviewer", help="Optional reviewer name.")
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    args = parser.parse_args()

    report = record_constraints_review_decision(
        Path(args.workspace),
        args.idea_id,
        decision=args.decision,
        selected_merge_input_ids=args.merge_input_id,
        resolution_note=args.resolution_note,
        reviewer=args.reviewer,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        decision = report.get("decision", {})
        print(f"Idea: {report['idea_id']}")
        print(f"Decision: {decision.get('status', '')}")
        print(f"Apply ready: {decision.get('apply_ready', False)}")
        if decision.get("summary"):
            print(f"Summary: {decision['summary']}")
        print(f"Report: {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
