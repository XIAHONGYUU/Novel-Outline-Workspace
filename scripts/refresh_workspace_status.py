#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace import collect_workspace_status, render_workspace_views
from novel_outline_workspace.workspace import write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh workspace-status.json.")
    parser.add_argument("--workspace", required=True, help="Workspace directory to inspect.")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout.")
    parser.add_argument("--no-write", action="store_true", help="Do not persist state/workspace-status.json.")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    status = collect_workspace_status(workspace)
    if not args.no_write:
        write_json(workspace / "state/workspace-status.json", status)
        render_workspace_views(workspace, status=status)
    if args.json or args.no_write:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        print(f"Workspace: {status['workspace_path']}")
        print(f"Mode: {status['workspace_mode']}")
        print(f"Recommended next step: {status['recommended_next_step']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
