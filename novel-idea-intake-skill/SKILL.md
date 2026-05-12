---
name: novel-idea-intake
description: Normalize raw story ideas into structured intake records with inferred kind, tags, target files, and next-step guidance for the novel outline workspace.
---

# Novel Idea Intake

Use this skill when the user has a raw story idea and wants it turned into a reusable workspace entry instead of leaving it as loose chat text.

This skill is the intake gate.

Its job is to:

- accept raw, messy idea text
- infer a likely idea kind when possible
- infer starter tags
- infer likely target files
- infer a structured intake draft
- write the idea into the workspace
- leave the workspace ready for consistency checking or merge planning

## Default Workflow

1. Read the idea as-is. Do not force early polish.
2. If the user did not provide `kind`, let intake infer one.
3. If tags are missing, let intake infer starter tags from the title and content.
4. If target files are missing, let intake infer likely impact files.
5. Build an intake draft with starter structure hints.
6. Write the idea into:
   - `state/idea-log.json`
   - `inbox/<idea-id>-<slug>.md`
   - `state/intake-drafts/<idea-id>.json`
   - `views/intake-drafts/<idea-id>.html`
7. Refresh workspace status and HTML views.

## Primary Command

```bash
python3 scripts/ingest_idea.py \
  --workspace <workspace> \
  --title "<idea title>" \
  --content "<raw idea>"
```

### Optional structured hints

```bash
python3 scripts/ingest_idea.py \
  --workspace <workspace> \
  --title "<idea title>" \
  --content "<raw idea>" \
  --kind reveal \
  --tag 女主 \
  --tag 真相 \
  --target-file outline/master-outline.md
```

## Intake Rules

- Prefer preserving the raw idea over over-cleaning it.
- Use inference to assist, not to overwrite explicit user input.
- Keep the draft lightweight enough that later skills can still reinterpret it.
- Do not mark anything `applied` during intake.

## When To Read More

- For inference rules and common keyword patterns, read [references/intake-rules.md](references/intake-rules.md).
- For command examples, read [references/intake-examples.md](references/intake-examples.md).
