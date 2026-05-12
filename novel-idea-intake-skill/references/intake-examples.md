# Intake Examples

## Example 1: raw reveal idea

```bash
python3 scripts/ingest_idea.py \
  --workspace ./demo-workspace \
  --title "师姐提前知情" \
  --content "师姐在第三章就知道议会内部有人泄密，但先没有告诉林舟。"
```

Expected outcome:

- inferred kind: `reveal`
- inferred tags: `师姐`, `议会`, `泄密`
- inferred target files:
  - `outline/master-outline.md`
  - `outline/scene-index.json`
  - `timeline/events.json`
- generated draft:
  - `state/intake-drafts/<idea-id>.json`
  - `views/intake-drafts/<idea-id>.html`

## Example 2: raw scene idea

```bash
python3 scripts/ingest_idea.py \
  --workspace ./demo-workspace \
  --title "旧港口夜谈" \
  --content "林舟在旧港口第一次确认黑潮会提前来袭。"
```

Expected outcome:

- inferred kind: `scene` or `event`
- inferred tags: `林舟`, `旧港口`, `黑潮`
- next step: generate merge plan
