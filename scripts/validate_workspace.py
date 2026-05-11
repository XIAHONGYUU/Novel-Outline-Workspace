#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace import validate_workspace


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the first-pass hard validator for a workspace.")
    parser.add_argument("--workspace", required=True, help="Workspace directory.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    args = parser.parse_args()

    report = validate_workspace(Path(args.workspace))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Validation ok: {report['ok']}")
        print(f"Errors: {report['error_count']}")
        print(f"Warnings: {report['warning_count']}")
        print(f"Report: {report['report_path']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
