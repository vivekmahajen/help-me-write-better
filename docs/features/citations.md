# Citation generator / formatter (Feature 3)

Resolve identifiers to metadata and format them per style. **Free on all tiers**,
**no external key** required — DOI → Crossref, ISBN → OpenLibrary, URL → page meta
tags, free-text → an LLM/heuristic parse (flagged so the UI can say "verify
fields").

> **Scope note:** rather than bundle `citeproc-py` + the full CSL repo, this ships
> focused, regression-fixtured formatters for the launch styles (**APA 7, MLA 9,
> Chicago author-date, Harvard, IEEE**) across four item types (journal article,
> book, chapter, webpage), plus **BibTeX** export. An unbundled style renders in
> APA **with a warning** — never a silent substitution. The CSL-JSON intermediate
> allows swapping in a full CSL engine later; see `docs/decisions/ADR-002-csl.md`.

## Request

```bash
curl -s http://localhost:8000/v1/cite \
  -H "Authorization: Bearer $KEY" -H "content-type: application/json" \
  -d '{"cite":{"inputs":["10.1038/nature14539","https://example.com/post","978-0-13-468599-1"],
                "style":"apa","output":["bibliography","in_text"],"save":false}}'
```

Mixed inputs resolve **independently** — one bad line yields a per-line `warning`,
not a failed batch.

## Response

```json
{ "style": "apa",
  "items": [
    { "input": "10.1038/nature14539",
      "csl_json": { "type": "article-journal", "title": "Deep learning", "author": [...] },
      "bibliography_entry": "LeCun, Y., Bengio, Y., Hinton, G. (2015). Deep learning. *Nature*, 521(7553), 436-444. https://doi.org/10.1038/nature14539",
      "in_text": "(LeCun, 2015)",
      "resolver": "crossref", "parsed_by": "crossref", "warnings": [] }
  ],
  "bibliography": ["… alphabetized entries …"] }
```

`resolver`/`parsed_by` are one of `crossref` · `openlibrary` · `url` · `heuristic`
· `llm`. **LLM/heuristic-parsed references are flagged** so the UI can prompt the
user to verify fields.

## Saved bibliography

Pass `"save": true` (optionally `"doc_id"`) to persist each citation to the user's
bibliography; `GET /v1/citations` lists them (stores **CSL-JSON only**).

## Integration

The plagiarism results from Feature 1 expose a "Cite this source" action: pass the
matched source URL into `/v1/cite` and append it to the doc's bibliography.

## SDK

```js
const { items, bibliography } = await client.cite(
  ["10.1038/nature14539"], "apa", { output: ["bibliography", "in_text"] });
```
