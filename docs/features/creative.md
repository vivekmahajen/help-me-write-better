# Creative / fiction tools (Feature 5)

The same template engine (`category: creative`) plus two service-level upgrades
for long-form work.

## Creative templates

12 shipped in `templates/creative/*.yaml` (appear in the API/CLI/UI automatically):
`story-premise`, `beat-sheet-three-act`, `save-the-cat`, `character-profile`,
`character-voice`, `dialogue-tightener`, `show-dont-tell`, `sensory-enrichment`,
`scene-expander`, `synopsis`, `blurb`, `worldbuilding-questionnaire`.

```bash
POST /v1/improve { "template": "character-voice",
                   "template_fields": { "profile": "gruff retired sailor…",
                                        "passage": "She was very happy to see the harbor…" } }
```

## Long-form `context`

Pass preceding manuscript so passes stay consistent with established voice/canon:

```bash
POST /v1/improve { "template": "scene-expander", "template_fields": {...},
                   "context": "<preceding chapters…>" }
```

- The engine injects `context` as a clearly-fenced block: *"keep voice/facts/canon
  consistent; do not summarize or alter it."*
- **Never silently truncated.** Over the budget (`CONTEXT_BUDGET_CHARS`, 200k chars
  ≈ 50k tokens — our models carry 1M-token windows), the response includes an
  explicit `warnings: ["context (… chars) exceeds the 200000-char budget and was
  not applied …"]` and runs without it.

## Style fingerprint

`POST /v1/fingerprint { "text": "…" }` — local, uncapped prose metrics for the
craft panel (sibling to the readability report), tracked in analytics so novelists
can watch drift across chapters:

```json
{ "fingerprint": {
    "sentences": 312, "words": 4820,
    "sentence_length": { "mean": 14.2, "min": 2, "max": 41,
                         "distribution": { "short_<10": 120, "medium_10_20": 150, "long_>20": 42 } },
    "dialogue_ratio": 0.38,
    "adverb_density": 0.021,
    "filter_words": { "count": 73, "density": 0.015, "top": ["just","very","felt","saw","seemed"] } } }
```

## Acceptance eval

`evals/character_voice_eval.py` runs the `character-voice` template and scores the
rewrite with an LLM judge for voice consistency (event preserved). **Pass ≥ 4/5.**
The harness is dependency-injected (unit-tested offline in `tests/test_creative.py`);
run the real eval with a key:

```bash
python -m evals.character_voice_eval     # exits non-zero if score < 4
```

## SDK

```js
const fp = await client.fingerprint(chapterText);
const { variants } = await client.useTemplate("character-voice",
  { profile, passage }, { context: precedingChapters });
```
