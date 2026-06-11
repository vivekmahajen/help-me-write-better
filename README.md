# Help Me Write Better

A bundled **write-better + format** engine built on Claude. Give it any text and a
service, and it returns writing that reads better and is cleanly formatted —
while preserving the author's meaning and voice.

It wraps the full *improve → structure → format* toolset behind one consistent
engine, with a model-routing layer that keeps cost-to-serve low.

## What it does

One engine, **36 bundled services**. Thirteen core modes are defined in the
operator prompt; the rest are extended, name-only services that each carry their
own instruction (e.g. `tone-detect`, `readability`, `humanize`, `fact-flag`,
`headline`, `score`). Run `write-better --list` to see them all.

The thirteen core **modes**:

| | Service | What it does | Routed model |
|---|---|---|---|
| A | `write` | Draft new text from a brief | Opus (premium) |
| B | `correct` | Fix grammar, spelling, punctuation, syntax | Haiku (routine) |
| C | `clarify` | Improve clarity and flow; remove ambiguity | Haiku (routine) |
| D | `tighten` | Cut wordiness, redundancy, filler; prefer active voice | Haiku (routine) |
| E | `retone` | Adjust tone / formality / voice | Sonnet (standard) |
| F | `paraphrase` | Restate in fresh wording, or rewrite in a style | Opus (premium) |
| G | `level` | Raise or lower reading level for the audience | Sonnet (standard) |
| H | `resize` | Expand or shorten to a target length | Sonnet (standard) |
| I | `summarize` | Condense to key points / TL;DR / abstract | Haiku (routine) |
| J | `translate` | Render into another language, idiomatically | Sonnet (standard) |
| K | `structure` | Organize into headings, lists, tables | Sonnet (standard) |
| L | `convert` | Output in a specific format | Sonnet (standard) |
| M | `check` | Analysis only — readability, tone, issues; no rewrite | Sonnet (standard) |

Services compose: `-s tighten,structure` runs both in one pass.

### The margin lever: model routing

Routine cleanup jobs (`correct`, `clarify`, `tighten`, `summarize`) route to a
cheap model; generative and high-stakes rewrites (`write`, `paraphrase`) route to
a premium model; everything else uses a balanced default. A premium service
anywhere in a request promotes the whole job to premium. Override with `--model`.

```
correct                -> claude-haiku-4-5     (routine)
translate              -> claude-sonnet-4-6    (standard)
write                  -> claude-opus-4-8      (premium)
correct,paraphrase     -> claude-opus-4-8      (premium wins)
```

The Opus and Sonnet tiers run with adaptive thinking + the `effort` parameter;
the Haiku tier does not (it does not accept `effort`).

## Install

```bash
pip install -e .          # installs the `write-better` command + the anthropic SDK
# or, without installing the package:
pip install -r requirements.txt
export PYTHONPATH=src
```

Set a credential (the engine resolves it the way the Anthropic SDK does):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# or: ant auth login
```

## Use

```bash
# Fix grammar from a pipe
echo "their going to the store tommorow" | write-better -s correct

# Tighten + structure a draft into Markdown, with a change summary
write-better -s tighten,structure -f markdown --show-changes -i draft.txt

# Translate a note into Spanish
write-better -s translate --language Spanish -i note.txt

# Analyze without rewriting
write-better -s check -i essay.txt

# Draft new copy from a brief, at max effort, into an email
echo "brief: invite the team to Friday's launch party" \
  | write-better -s write -f email --tone friendly --effort max

# See where a request would route — no API call
echo "x" | write-better -s correct,paraphrase --dry-run

# List all services
write-better --list

# Print the plan pricing & margin table
write-better --pricing
```

Run `write-better --help` for the full flag set (targets: `--audience`, `--tone`,
`--length`, `--reading-level`, `--language`; `--out` to write to a file;
`--no-stream` to disable live streaming).

### As a library

```python
from write_better import improve, Request

result = improve(Request(text="make this shorter and clearer", services=["tighten"]))
print(result.text, "->", result.model)
```

## How it works

- `src/write_better/operator_prompt.md` — the operator system prompt that powers
  the engine (the hard rules, modes, quality bar, formatting standards, output
  contract). Ships as package data; edit this to tune behavior.
- `src/write_better/modes.py` — all 36 services and their routing tiers. Core
  modes (A–M) are defined in the operator prompt; extended services carry their
  own `instruction`, which the engine injects per request.
- `src/write_better/prompt.py` — loads the operator prompt and builds the
  per-request `INPUTS` block.
- `src/write_better/engine.py` — model routing + the Claude call (streaming).
- `src/write_better/cli.py` — the command-line interface.
- `src/write_better/plans.py` — the pricing & margin model (tiers, caps, unit
  costs); the live form of the pricing spreadsheet. Edit the unit costs and every
  margin recalculates.
- `docs/PRICING.md` — recommended end-user pricing and the margin rationale.

## Deploy (Vercel)

The suite ships an HTTP API + a browser UI so it runs on Vercel's native Python
runtime:

- `app.py` — the top-level Vercel entrypoint (serves the WSGI `app`).
- `src/write_better/web.py` — the app. `GET` content-negotiates: browsers
  (`Accept: text/html`) get a single-page UI; everyone else gets JSON service
  info. `POST` runs the engine on a JSON body.
- `src/write_better/ui.py` — the self-contained HTML page (no external assets);
  it calls the same `POST` endpoint.

Open the deployed URL in a browser for the UI; `curl` it for the JSON API.

The operator prompt travels with the package (it's package data), so no extra
file-bundling config is needed.

```bash
vercel deploy
# set the server-side credential the engine needs:
vercel env add ANTHROPIC_API_KEY
```

Once deployed:

```bash
# Discover the API
curl https://<your-app>.vercel.app/

# Improve some text
curl -X POST https://<your-app>.vercel.app/ \
  -H 'Content-Type: application/json' \
  -d '{"text":"their going to the store","services":"correct","format":"plain"}'
```

`POST` body fields: `text` (required), `services`, `format`, `show_changes`,
`tone`, `audience`, `length`, `reading_level`, `language`, `request`, `model`,
`effort`. The response is `{ text, model, services, usage }`.

You can also run the same app locally with any WSGI server:

```bash
pip install gunicorn
gunicorn write_better.web:app
```

## Develop

```bash
pip install -e ".[dev]"
pytest
```

The tests use a fake client, so the full routing and prompt-assembly logic is
verified without any network calls or API key.

## License

MIT
