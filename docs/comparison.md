# How help-me-write-better compares

Capability coverage after the Trust Layer + Template Layer + Depth (Gap-4)
release. Rows flip to **Full** only once the feature passes its acceptance tests
(see `tests/` and each `docs/features/*` page).

| Capability | Status |
|---|---|
| Grammar / spelling / punctuation | ✅ Full |
| Clarity / conciseness / flow | ✅ Full |
| Tone & formality control | ✅ Full |
| Paraphrase / rewrite | ✅ Full |
| Reading-level (simplify / elevate) | ✅ Full |
| Expand / shorten to length | ✅ Full |
| Summarize / TL;DR | ✅ Full |
| Translate | ✅ Full |
| Structure (headings / lists / tables) | ✅ Full |
| Format conversion (MD/HTML/email/…) | ✅ Full |
| Readability report | ✅ Full |
| Tone detection | ✅ Full |
| Weakness detection (passive, hedging, filler) | ✅ Full |
| Consistency checks | ✅ Full |
| Inclusive-language checks | ✅ Full |
| Style/cliché/jargon detection | ✅ Full |
| Fact-claim flagging | ✅ Full |
| Real-time inline checking | ✅ Full |
| Vocabulary enhancement | ✅ Full |
| ESL fluency pass | ✅ Full |
| Report-card scoring | ✅ Full |
| Accounts / saved docs / history | ✅ Full |
| Teams / shared style guide | ✅ Full |
| Writing analytics | ✅ Full |
| Developer API / SDK / CLI | ✅ Full |
| Multi-surface (web / extension / Word / Docs / desktop / mobile) | ✅ Full |
| **True plagiarism detection** | ✅ Full *(new)* |
| **AI-content detection** | ✅ Full *(new)* |
| **Citation generator / formatter** | ✅ Full — APA/MLA/Chicago/Harvard/IEEE × 4 item types + BibTeX |
| **Marketing-copy templates** | ✅ Full — 26 marketing templates |
| **Everyday-life templates** (cover letter, complaint, condolence, …) | ✅ Full *(new)* — 16 |
| **Creative / fiction tools + long-form context** | ✅ Full — typed context, continuity check, eval-gated |
| **Composition services** (merge, reverse-dictionary, argument map, localize) | ✅ Full *(new)* |
| **Hard length guarantees** (RSA / meta-description limits) | ✅ Full *(new)* |
| **Snippets / personal goals / weekly recap** | ✅ Full *(new)* |
| System-wide desktop checking (OS accessibility) | ◐ Partial — later milestone |
| Document-version **diff UI** | ◐ Partial — restore + caps shipped; visual diff later |

**35 Full / 2 Partial.**

Honesty notes carried into the product:
- Plagiarism reports textual similarity, **not** a legal determination.
- AI detection is **probabilistic and banded** (human / uncertain / likely_ai),
  never a binary verdict, and always shows a confidence note.
- Citations ship **5 golden-tested styles + graceful degradation** (an unbundled
  style renders in APA *with a warning*), not the full CSL universe — see
  `docs/decisions/ADR-002-csl.md`.
- `localize-tone` is a **register shift, not cultural consultation**, and stays
  in English.
- Hard length limits **never lie**: an unmet cap is trimmed and flagged
  `limit_met: false`.
