#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace.merge import plan_idea_merge


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan a semi-automatic merge for one pending idea.")
    parser.add_argument("--workspace", required=True, help="Workspace directory.")
    parser.add_argument("--idea-id", required=True, help="Idea id to plan.")
    parser.add_argument("--json", action="store_true", help="Print JSON plan.")
    args = parser.parse_args()

    plan = plan_idea_merge(Path(args.workspace), args.idea_id)
    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(f"Planned merge: {plan['idea_id']}")
        print(f"Plan JSON: {plan['plan_path']}")
        print(f"Plan View: {plan['view_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
