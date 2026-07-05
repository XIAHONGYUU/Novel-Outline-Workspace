#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace.constraints_review import review_constraints


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a structured constraints-review report for one idea.")
    parser.add_argument("--workspace", required=True, help="Workspace directory.")
    parser.add_argument("--idea-id", required=True, help="Idea id to review.")
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    args = parser.parse_args()

    report = review_constraints(Path(args.workspace), args.idea_id)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Idea: {report['idea_id']}")
        print(f"Review required: {report['review_required']}")
        if report.get("review_policy"):
            print(f"Policy: {report['review_policy']}")
        if report.get("review_policy_summary"):
            print(f"Summary: {report['review_policy_summary']}")
        print(f"Report: {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
