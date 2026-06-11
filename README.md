# Help Me Write Better

A bundled **write-better + format** engine built on Claude. Give it any text and a
service, and it returns writing that reads better and is cleanly formatted —
while preserving the author's meaning and voice.

It wraps the full *improve → structure → format* toolset behind one consistent
engine, with a model-routing layer that keeps cost-to-serve low.

## What it does

One engine, thirteen bundled services (the **modes**):

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

- `prompts/operator_prompt.md` — the operator system prompt that powers the
  engine (the hard rules, modes, quality bar, formatting standards, output
  contract). Edit this to tune behavior.
- `src/write_better/modes.py` — the 13 services and their routing tiers.
- `src/write_better/prompt.py` — loads the operator prompt and builds the
  per-request `INPUTS` block.
- `src/write_better/engine.py` — model routing + the Claude call (streaming).
- `src/write_better/cli.py` — the command-line interface.

## Develop

```bash
pip install -e ".[dev]"
pytest
```

The tests use a fake client, so the full routing and prompt-assembly logic is
verified without any network calls or API key.

## License

MIT
