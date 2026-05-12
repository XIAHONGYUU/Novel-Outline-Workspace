---
name: novel-consistency-check
description: Check whether a pending idea or intake draft conflicts with the current canon, outline, and timeline before merge.
---

# Novel Consistency Check

Use this skill after `novel-idea-intake` and before merge.

This skill is the idea-level quality gate.

Its job is to:

- read one pending idea
- load its intake draft
- compare the draft against current `canon / outline / timeline`
- report likely conflicts
- leave a reusable JSON and HTML report for later merge decisions

## MVP Scope

Current first version focuses on deterministic checks that can be supported by the existing JSON model.

It currently checks:

- chapter placement drift for matching event / scene titles
- location continuity drift for matching events
- first-meeting conflicts when an idea explicitly claims a first meeting but earlier shared appearances already exist
- relationship-history drift for repeated alliance / acquaintance states
- hard-canon world-rule conflicts from `constraints/constraints.json`
- intake draft completeness warnings

It does not yet fully solve:

- deep knowledge-state graphs
- freeform semantic conflict resolution

## Primary Command

```bash
python3 scripts/check_idea_consistency.py \
  --workspace <workspace> \
  --idea-id <idea-id>
```

## Outputs

The command writes:

- `state/consistency-checks/<idea-id>.json`
- `views/consistency-checks/<idea-id>.html`

## Operating Rules

- Run this after intake and before apply-merge for any risky idea.
- The orchestrator should prefer `check-consistency` before `plan-merge` for fresh pending ideas.
- Prefer exact, explainable checks over vague semantic guesses.
- Treat this as a gate, not as an auto-fix step.
- If the report is clean but low-confidence warnings remain, keep human review in the loop.
