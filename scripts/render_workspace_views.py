#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace import collect_workspace_status, render_workspace_views


def main() -> int:
    parser = argparse.ArgumentParser(description="Render HTML workspace views from JSON source files.")
    parser.add_argument("--workspace", required=True, help="Workspace directory.")
    args = parser.parse_args()

    workspace = Path(args.workspace)
    status = collect_workspace_status(workspace)
    outputs = render_workspace_views(workspace, status=status)
    print(f"Rendered: {outputs['index']}")
    print(f"Rendered: {outputs['validation_report']}")
    print(f"Rendered: {outputs['timeline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
