#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from novel_outline_workspace import update_intake_draft


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch a structured intake draft with confirmed fields.")
    parser.add_argument("--workspace", required=True, help="Workspace directory.")
    parser.add_argument("--idea-id", required=True, help="Idea id to patch.")
    parser.add_argument("--chapter-hint", action="append", type=int, default=None, help="Repeatable chapter hint.")
    parser.add_argument("--location-candidate", action="append", default=None, help="Repeatable location candidate.")
    parser.add_argument("--character-mention", action="append", default=None, help="Repeatable character mention.")
    parser.add_argument("--open-question", action="append", default=None, help="Repeatable open question to keep.")
    parser.add_argument("--clear-open-questions", action="store_true", help="Clear existing open questions before writing the patch.")
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    args = parser.parse_args()

    result = update_intake_draft(
        Path(args.workspace),
        idea_id=args.idea_id,
        chapter_hints=args.chapter_hint,
        location_candidates=args.location_candidate,
        character_mentions=args.character_mention,
        open_questions=args.open_question,
        clear_open_questions=args.clear_open_questions,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Updated intake draft: {result['idea_id']}")
        print(f"Draft path: {result['draft_path']}")
        print(f"Recommended next step: {result['status']['recommended_next_step']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
