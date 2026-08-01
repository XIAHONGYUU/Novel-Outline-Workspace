#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace.reuse_review import review_reuse


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a structured reuse-review report for one idea.")
    parser.add_argument("--workspace", required=True, help="Workspace directory.")
    parser.add_argument("--idea-id", required=True, help="Idea id to review.")
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    args = parser.parse_args()

    report = review_reuse(Path(args.workspace), args.idea_id)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Idea: {report['idea_id']}")
        print(f"Review required: {report['review_required']}")
        if report.get("review_tokens"):
            print(f"Tokens: {', '.join(report['review_tokens'])}")
        if report.get("review_summary"):
            print(f"Summary: {report['review_summary']}")
        ready_inputs = report.get("ready_merge_inputs", [])
        if ready_inputs:
            print("Ready merge inputs:")
            for item in ready_inputs:
                merge_input_id = str(item.get("id") or "").strip()
                summary = str(item.get("summary") or "").strip()
                print(f"- {merge_input_id}: {summary}")
        remaining_inputs = report.get("remaining_review_merge_inputs", [])
        if remaining_inputs:
            print("Remaining review inputs:")
            for item in remaining_inputs:
                merge_input_id = str(item.get("id") or "").strip()
                remaining_kind = str(item.get("remaining_kind") or "").strip() or "pending"
                remaining_summary = str(item.get("remaining_summary") or item.get("summary") or "").strip()
                print(f"- {merge_input_id} [{remaining_kind}]: {remaining_summary}")
                source_issue_codes = [str(code).strip() for code in item.get("source_issue_codes", []) if str(code).strip()]
                if source_issue_codes:
                    print(f"  source issues: {', '.join(source_issue_codes)}")
                for hold in item.get("apply_arg_review_holds", []):
                    if not isinstance(hold, dict):
                        continue
                    field = str(hold.get("field") or "").strip()
                    tokens = [str(token).strip() for token in hold.get("review_tokens", []) if str(token).strip()]
                    details = f"review hold on {field}" if field else "review hold"
                    if tokens:
                        details += f": {', '.join(tokens)}"
                    print(f"  {details}")
                for conflict in item.get("apply_arg_conflicts", []):
                    if not isinstance(conflict, dict):
                        continue
                    key = str(conflict.get("key") or "").strip() or "apply_args"
                    value_kind = str(conflict.get("value_kind") or "").strip() or "value"
                    print(f"  apply_arg_conflict {key} ({value_kind})")
        print(f"Report: {report['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
