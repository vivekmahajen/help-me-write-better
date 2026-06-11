"""The bundled service modes and how user requests resolve to them.

Two kinds of service:

* The original A-M modes are defined in the operator system prompt; they carry a
  ``letter`` and no ``instruction``.
* Extended, name-only services each carry a full ``instruction`` (their prompt),
  which the engine injects into the request. They have no letter.

``tier`` drives model routing and the pricing-cap link (see ``plans.py``):
routine -> cheap model, standard -> balanced, premium -> top model.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mode:
    """One bundled service."""

    name: str            # canonical name, e.g. "tighten"
    summary: str         # one-line description
    tier: str            # "routine" | "standard" | "premium"
    letter: str = ""     # canonical letter for the operator-prompt modes (A-M)
    aliases: tuple[str, ...] = ()
    instruction: str = ""  # full prompt for extended services; "" for A-M


# --- The original A-M modes (defined in the operator system prompt) -----------

_CORE_MODES: tuple[Mode, ...] = (
    Mode("write", "Draft new text from a brief, in the target tone/format/length.",
         "premium", letter="A", aliases=("draft", "compose")),
    Mode("correct", "Fix grammar, spelling, punctuation, syntax (minimal, surgical touch).",
         "routine", letter="B", aliases=("grammar", "proofread", "fix")),
    Mode("clarify", "Improve clarity and flow; remove ambiguity and awkward phrasing.",
         "routine", letter="C", aliases=("clarity",)),
    Mode("tighten", "Make concise; cut wordiness, redundancy, and filler; prefer active voice.",
         "routine", letter="D", aliases=("concise", "trim", "shorten-wordiness")),
    Mode("retone", "Adjust tone/formality/voice (professional, friendly, persuasive, …).",
         "standard", letter="E", aliases=("tone",)),
    Mode("paraphrase", "Restate in fresh wording; or rewrite in a specified style/voice.",
         "premium", letter="F", aliases=("rewrite", "reword", "restate")),
    Mode("level", "Raise or lower reading level / simplify or elevate for the audience.",
         "standard", letter="G", aliases=("simplify", "elevate", "reading-level")),
    Mode("resize", "Expand or shorten to a target length while keeping substance.",
         "standard", letter="H", aliases=("expand", "lengthen", "shorten")),
    Mode("summarize", "Condense to key points / TL;DR / abstract.",
         "routine", letter="I", aliases=("summary", "tldr", "abstract")),
    Mode("translate", "Render into another language naturally and idiomatically.",
         "standard", letter="J", aliases=("translation",)),
    Mode("structure", "Organize into clean structure: headings, sections, lists, tables.",
         "standard", letter="K", aliases=("organize",)),
    Mode("convert", "Output in a specific format (Markdown, HTML, email, report, …).",
         "standard", letter="L", aliases=("format", "reformat")),
    Mode("check", "Analysis only: readability, tone, issues, and suggestions; no rewrite.",
         "standard", letter="M", aliases=("analyze", "review", "analysis")),
)


# --- Extended, name-only services (full prompt carried in ``instruction``) -----

_EXTENDED_MODES: tuple[Mode, ...] = (
    Mode("tone-detect", "Detect dominant tones, formality, and tone mismatches.",
         "standard", aliases=("tone-analysis",),
         instruction=(
             "Analyze the TONE of the text. Report: (1) the 2-4 dominant tones (e.g., "
             "confident, formal, friendly, urgent, tentative, salesy), each with a confidence; "
             "(2) the overall formality level (1-5); (3) the likely reader impression; (4) any "
             "tone mismatches with the stated AUDIENCE/intent; (5) 2-3 specific lines driving the "
             "tone. Do NOT rewrite. Output a short structured report."
         )),
    Mode("readability", "Score readability with metrics and flag the hardest sentences.",
         "standard", aliases=("readability-score", "grade-level"),
         instruction=(
             "Score the text's readability. Report: Flesch Reading Ease, Flesch-Kincaid grade "
             "level, estimated reading time, average sentence length, % long/hard sentences, % "
             "passive sentences, and adverb count. Flag the 3-5 hardest sentences (quote a snippet "
             "+ why). State the audience this currently suits and what to change to hit a target "
             "reading level. Analysis only - no rewrite."
         )),
    Mode("detect-weak", "List weak verbs, passive voice, hedging, and filler with fixes.",
         "standard", aliases=("weaknesses", "weak"),
         instruction=(
             "Find and list weaknesses WITHOUT rewriting the whole text: passive-voice sentences, "
             "weak/\"to be\" verbs, hedging (\"I think\", \"maybe\", \"sort of\"), filler/wordiness, "
             "and nominalizations. For each, quote the phrase, name the issue, and give a tighter "
             "alternative. Group by issue type; end with a one-line priority fix."
         )),
    Mode("consistency", "Report style/spelling/terminology inconsistencies across the text.",
         "standard", aliases=("consistency-check",),
         instruction=(
             "Check consistency across the whole text and report only inconsistencies: US vs UK "
             "spelling, hyphenation (e-mail/email), capitalization of terms, number style (5 vs "
             "five), Oxford comma usage, date/time formats, and terminology (same thing named "
             "differently). For each, show both variants, where they occur, and the recommended "
             "single standard. Do not change meaning."
         )),
    Mode("inclusive", "Flag non-inclusive or biased language with neutral alternatives.",
         "standard", aliases=("inclusive-language", "bias"),
         instruction=(
             "Scan for non-inclusive, biased, or potentially offensive language (gendered terms, "
             "ableist/ageist language, cultural insensitivity, loaded words). For each: quote it, "
             "explain the concern briefly, and offer a neutral alternative. Be helpful and "
             "non-preachy; flag only genuine issues, not style preferences. If none, say so."
         )),
    Mode("style-issues", "Find clichés, jargon, buzzwords, and overused words with fixes.",
         "standard", aliases=("style", "cliches"),
         instruction=(
             "Identify clichés, unnecessary jargon, buzzwords, overused/repeated words (with "
             "counts), and echoed phrasings. For each, quote it and suggest a fresher or plainer "
             "alternative. List repeated words sorted by frequency. Analysis + suggestions; do not "
             "rewrite the full text."
         )),
    Mode("flow", "Analyze sentence rhythm, pacing, and monotony.",
         "standard", aliases=("rhythm",),
         instruction=(
             "Analyze rhythm and flow: report the distribution of sentence lengths, flag runs of "
             "same-length or same-opener sentences (\"sticky\"/monotonous passages), and note "
             "pacing (too dense / too choppy). Quote 2-3 example spots and suggest where to vary "
             "length or combine/split. No full rewrite."
         )),
    Mode("originality", "Flag unoriginal/generic passages; recommend a real plagiarism check.",
         "standard", aliases=("plagiarism", "plagiarism-check"),
         instruction=(
             "You cannot access the web or a plagiarism corpus, so do NOT claim a plagiarism "
             "percentage. Instead: flag passages that read as unoriginal, generic, or closely "
             "matching common/known phrasing (clichés, boilerplate, likely-quoted lines), and flag "
             "any text that appears copied verbatim from a famous source. Recommend running flagged "
             "passages through a real plagiarism API (e.g., Copyleaks, Originality.ai) for a "
             "definitive check. Be clear about what you can and can't verify."
         )),
    Mode("humanize", "Rewrite to read naturally human while preserving meaning.",
         "premium", aliases=("human", "de-ai"),
         instruction=(
             "Rewrite the text to sound naturally human while preserving meaning and the author's "
             "intent: vary sentence length and openers, remove robotic hedging and over-balanced "
             "\"not only… but also\" constructions, cut generic filler, add natural transitions, "
             "and prefer concrete wording. Keep facts unchanged; do not fabricate. Return the "
             "rewritten text, then a 1-line note on what made it read machine-generated."
         )),
    Mode("fact-flag", "Flag factual claims/stats/quotes that need checking.",
         "standard", aliases=("fact-check", "facts"),
         instruction=(
             "Identify factual claims, statistics, quotes, dates, and named sources in the text. "
             "For each, mark it [verifiable] or [needs checking], and flag anything that looks "
             "invented, internally contradictory, or implausible. Do NOT add or \"correct\" facts "
             "and do NOT fabricate sources - only flag what a careful editor would double-check "
             "before publishing. Output a checklist."
         )),
    Mode("cite", "Format citations (APA/MLA/Chicago) without inventing sources.",
         "standard", aliases=("citation", "citations"),
         instruction=(
             "Given source details the user provides (or clearly-identified sources in the text), "
             "format citations in the requested style (APA, MLA, or Chicago - ask if unspecified) "
             "for both in-text citations and the reference list. Do NOT invent sources, authors, "
             "dates, or URLs; if a required field is missing, mark it [missing - supply]. Return "
             "the formatted citations only."
         )),
    Mode("variations", "Produce concise/formal/warm rewrites of each sentence.",
         "premium", aliases=("variants", "rephrase-options"),
         instruction=(
             "For each sentence (or the selected sentence), produce 3 distinct rewrites that keep "
             "the meaning: one more concise, one more formal/polished, and one warmer/more "
             "conversational. Label each. Keep the author's intent; don't change facts. Present as "
             "a compact list per original sentence."
         )),
    Mode("enhance-vocab", "Strengthen word choice in context without changing meaning.",
         "routine", aliases=("vocab", "word-choice"),
         instruction=(
             "Improve word choice without changing meaning or voice: replace vague, weak, or "
             "repetitive words with stronger, more precise ones IN CONTEXT (not random synonyms). "
             "Show each change as \"original → improved\" with the sentence, and don't over-elevate "
             "into thesaurus-speak. Return the improved text plus the change list."
         )),
    Mode("paraphrase-modes", "Paraphrase in a chosen mode (fluent/formal/simple/creative/…).",
         "premium", aliases=("rephrase",),
         instruction=(
             "Paraphrase the text in the requested MODE: standard | fluent | formal | simple | "
             "creative | shorten | expand. Preserve meaning exactly; change wording and structure "
             "to fit the mode (formal = professional and precise; simple = plain and short; "
             "creative = fresh and vivid; etc.). Do not add new facts. Return only the paraphrased "
             "text in that mode."
         )),
    Mode("fluency", "Make non-native English read fluent without changing meaning.",
         "routine", aliases=("esl", "non-native-english"),
         instruction=(
             "The author may be a non-native English speaker. Make the text read as natural, fluent "
             "English: fix article/preposition/tense errors, awkward literal translations, and "
             "unidiomatic phrasing - WITHOUT changing the author's meaning, simplifying their ideas, "
             "or erasing their voice. Return the polished text; if SHOW_CHANGES, list the "
             "corrections grouped by type (articles, prepositions, idiom, tense)."
         )),
    Mode("headline", "Generate titles / subject lines / hooks across angles.",
         "premium", aliases=("title", "subject-line", "headlines"),
         instruction=(
             "Generate options for the requested asset: blog title | headline | email subject line "
             "| social hook. Produce 8 options spanning angles (clear, curiosity, benefit, numbered, "
             "urgent, question). Match the TONE and AUDIENCE. Keep them honest - no clickbait that "
             "the content can't deliver. Return a labeled list."
         )),
    Mode("outline", "Produce a logical outline with sections and sub-points.",
         "premium", aliases=("outliner",),
         instruction=(
             "From the topic or draft, produce a clear, logical outline: a working title, 4-7 H2 "
             "sections each with 2-4 bullet sub-points, and a suggested intro hook and conclusion. "
             "Match the AUDIENCE, purpose, and target length. Don't write the full piece - just the "
             "outline."
         )),
    Mode("brainstorm", "Generate distinct ideas/angles as one-line pitches.",
         "premium", aliases=("ideas", "ideate"),
         instruction=(
             "Brainstorm for the user's topic: produce 10 distinct ideas/angles (mix of obvious and "
             "non-obvious), each as a one-line pitch. If asked, expand any one into 3 supporting "
             "points. Stay relevant to the AUDIENCE and goal. No fluff, no repetition."
         )),
    Mode("template", "Write a marketing asset from provided details (no invented claims).",
         "premium", aliases=("marketing", "copy", "ad-copy"),
         instruction=(
             "Write the requested marketing asset: ad copy | product description | landing-page "
             "section | cold email | social post | newsletter blurb. Use the provided PRODUCT/offer "
             "details only - do not invent features, claims, or results. Match brand TONE; include a "
             "clear CTA where appropriate. Provide 2 variants. Flag any claim that needs the user to "
             "verify."
         )),
    Mode("fiction", "Apply a creative tool to a passage in the existing voice.",
         "premium", aliases=("creative-writing", "story"),
         instruction=(
             "Apply the requested creative tool to the passage: describe (add sensory/grounding "
             "detail) | expand (continue in the same voice) | rewrite-vivid | rewrite-shorter | "
             "add-tension | brainstorm-plot. Match the existing voice, POV, and tense. Preserve "
             "established facts/characters; don't contradict the canon. Return only the new/edited "
             "prose."
         )),
    Mode("brand-voice", "Check text against the user's brand-voice/style rules.",
         "standard", aliases=("brand", "style-guide"),
         instruction=(
             "Given the user's STYLE GUIDE / brand-voice rules (tone, banned words, preferred terms, "
             "formality, formatting conventions), check the text against them. Report each violation "
             "(quote + rule broken + fix), then optionally return a corrected version that conforms. "
             "Apply only the user's rules; don't impose outside preferences."
         )),
    Mode("explain", "Teaching pass: explain the why behind each fix.",
         "standard", aliases=("teach", "why"),
         instruction=(
             "For each correction or suggestion in the text, explain the WHY in one plain sentence a "
             "learner can understand (the rule or principle), with the before→after. Group recurring "
             "issues so the writer learns the pattern, not just the fix. Encouraging, concise, never "
             "condescending. This is a teaching pass, not just an editing pass."
         )),
    Mode("score", "One-screen report card with sub-scores and top fixes.",
         "standard", aliases=("report-card", "grade"),
         instruction=(
             "Produce a one-screen \"report card\": overall score (0-100) with sub-scores for "
             "Correctness, Clarity, Conciseness, Engagement, and Tone-fit (vs the stated AUDIENCE). "
             "For each sub-score, give the top issue and the single highest-impact fix. End with the "
             "3 changes that would most improve the piece. Analysis only."
         )),
)


MODES: tuple[Mode, ...] = _CORE_MODES + _EXTENDED_MODES


# Lookup tables, built once.
_BY_LETTER = {m.letter.lower(): m for m in MODES if m.letter}
_BY_NAME = {m.name.lower(): m for m in MODES}
_BY_ALIAS = {alias.lower(): m for m in MODES for alias in m.aliases}


def resolve_one(token: str) -> Mode:
    """Resolve a single token (letter, name, or alias) to a :class:`Mode`."""
    key = token.strip().lower()
    if not key:
        raise ValueError("empty service token")
    mode = _BY_LETTER.get(key) or _BY_NAME.get(key) or _BY_ALIAS.get(key)
    if mode is None:
        valid = ", ".join(m.name for m in MODES)
        raise ValueError(f"unknown service {token!r}. Valid services: {valid}")
    return mode


def resolve_services(spec: str | list[str]) -> list[Mode]:
    """Resolve a comma/space-separated spec (or list) to ordered, de-duped modes."""
    if isinstance(spec, str):
        tokens = [t for t in spec.replace(",", " ").split() if t]
    else:
        tokens = list(spec)
    seen: dict[str, Mode] = {}
    for token in tokens:
        mode = resolve_one(token)
        seen.setdefault(mode.name, mode)
    if not seen:
        raise ValueError("no services resolved")
    return list(seen.values())
