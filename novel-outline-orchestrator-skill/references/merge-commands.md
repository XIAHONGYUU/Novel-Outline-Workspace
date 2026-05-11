# Merge Commands

## Minimal plan pass

```bash
python3 scripts/plan_idea_merge.py --workspace <workspace> --idea-id <idea-id> --json
```

This creates:

- `state/merge-plans/<idea-id>.json`
- `views/merge-plans/<idea-id>.html`

## Common apply patterns

### Add or update a character

```bash
python3 scripts/apply_idea_merge.py \
  --workspace <workspace> \
  --idea-id <idea-id> \
  --resolution-note "<how it was resolved>" \
  --character-id char-heroine \
  --character-name 女主 \
  --character-role deuteragonist
```

### Add an event

```bash
python3 scripts/apply_idea_merge.py \
  --workspace <workspace> \
  --idea-id <idea-id> \
  --resolution-note "<how it was resolved>" \
  --event-id event-secret-reveal \
  --event-label "女主提前知道真相" \
  --chronological-index 12 \
  --reading-chapter 7 \
  --participant-id char-heroine
```

### Add a scene and bind it to an event

```bash
python3 scripts/apply_idea_merge.py \
  --workspace <workspace> \
  --idea-id <idea-id> \
  --resolution-note "<how it was resolved>" \
  --chapter-number 7 \
  --scene-id scene-secret-reveal \
  --scene-title "女主假装不知情" \
  --scene-character-id char-heroine \
  --scene-event-id event-secret-reveal
```

## Operational Rule

When a single idea needs canon + timeline + outline updates, prefer applying all three in one pass so validation sees the full patch.
