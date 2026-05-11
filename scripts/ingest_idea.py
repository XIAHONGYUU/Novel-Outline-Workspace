#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace import ingest_idea


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a pending idea in the workspace inbox and idea log.")
    parser.add_argument("--workspace", required=True, help="Workspace directory.")
    parser.add_argument("--title", required=True, help="Idea title.")
    parser.add_argument("--content", required=True, help="Raw idea content.")
    parser.add_argument("--kind", default="misc", help="Idea kind, e.g. reveal / character / twist / scene.")
    parser.add_argument("--tag", action="append", default=[], help="Repeatable tag.")
    parser.add_argument("--target-file", action="append", default=[], help="Likely affected file path.")
    parser.add_argument("--source", default="manual", help="Idea source.")
    args = parser.parse_args()

    result = ingest_idea(
        workspace=Path(args.workspace),
        title=args.title,
        content=args.content,
        kind=args.kind,
        tags=args.tag,
        target_files=args.target_file,
        source=args.source,
    )
    print(f"Created idea: {result['idea']['id']}")
    print(f"Inbox file: {result['inbox_file']}")
    print(f"Recommended next step: {result['status']['recommended_next_step']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
