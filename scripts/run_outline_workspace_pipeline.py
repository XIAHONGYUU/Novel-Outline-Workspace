#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace.orchestrator import run_outline_workspace_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the workspace and route the next workflow action.")
    parser.add_argument("--workspace", required=True, help="Workspace directory.")
    parser.add_argument(
        "--action",
        choices=["auto", "validate", "render", "check-consistency", "plan-merge"],
        default="auto",
        help="Action to recommend or execute.",
    )
    parser.add_argument("--idea-id", help="Idea id for check-consistency or plan-merge.")
    parser.add_argument("--execute", action="store_true", help="Execute the selected action.")
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    args = parser.parse_args()

    result = run_outline_workspace_pipeline(
        Path(args.workspace),
        action=args.action,
        execute=args.execute,
        idea_id=args.idea_id,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Recommended: {result['recommended_action']}")
        print(f"Selected: {result['selected_action']}")
        print(f"Reason: {result['reason']}")
        if result.get("idea_id"):
            print(f"Idea: {result['idea_id']}")
        print(f"Executed: {result['executed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
