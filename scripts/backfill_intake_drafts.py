#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace import backfill_intake_drafts


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill or repair intake drafts for legacy workspace ideas.")
    parser.add_argument("--workspace", required=True, help="Workspace directory.")
    parser.add_argument("--idea-id", action="append", default=[], help="Repeatable idea id to repair explicitly.")
    parser.add_argument("--all-pending", action="store_true", help="Repair every pending idea, not only missing drafts.")
    parser.add_argument("--all-ideas", action="store_true", help="Repair every idea in the workspace.")
    parser.add_argument("--force-rebuild", action="store_true", help="Rebuild draft JSON from inference even if a draft already exists.")
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    args = parser.parse_args()

    result = backfill_intake_drafts(
        Path(args.workspace),
        idea_ids=args.idea_id,
        include_all_pending=args.all_pending,
        include_all_ideas=args.all_ideas,
        force_rebuild=args.force_rebuild,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Workspace: {result['workspace_path']}")
        print(f"Selected ideas: {result['selected_count']}")
        print(f"Repaired: {result['repaired_count']}")
        print(f"Skipped: {result['skipped_count']}")
        print(f"Recommended next step: {result['status']['recommended_next_step']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
