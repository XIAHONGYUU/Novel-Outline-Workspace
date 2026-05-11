#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace import init_workspace


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a new novel outline workspace.")
    parser.add_argument("--workspace", required=True, help="Workspace directory to create.")
    parser.add_argument("--novel-name", required=True, help="Novel name written into the template.")
    parser.add_argument("--protagonist-name", default="未命名主角", help="Initial protagonist name.")
    parser.add_argument("--force", action="store_true", help="Allow writing into an existing non-empty directory.")
    args = parser.parse_args()

    status = init_workspace(
        workspace=Path(args.workspace),
        novel_name=args.novel_name,
        protagonist_name=args.protagonist_name,
        force=args.force,
    )
    print(f"Initialized workspace: {args.workspace}")
    print(f"Novel: {status['novel_name']}")
    print(f"Recommended next step: {status['recommended_next_step']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
