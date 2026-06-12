"""Character-voice consistency eval (Feature 5 acceptance).

Runs the `character-voice` template and scores the rewrite with an LLM judge for
voice consistency while preserving the event. Pass threshold ≥ 4/5.

The harness is dependency-injected so it's unit-testable offline (see
``tests/test_creative.py``); ``main()`` wires the real engine + an Anthropic judge
and requires ``ANTHROPIC_API_KEY``.

    python -m evals.character_voice_eval      # exits non-zero if score < 4
"""

from __future__ import annotations

import re
import sys

PASS_THRESHOLD = 4

FIXTURE = {
    "profile": ("A gruff retired sailor. Clipped, declarative sentences. Reaches for "
                "nautical metaphors. Never uses the word 'feel' or names emotions directly."),
    "passage": "She was very happy to see the harbor again after being away for so long.",
    "rubric": ("On a 1-5 scale, how well does the REWRITE match the described character "
               "voice while preserving the underlying event (returning to the harbor "
               "after a long absence)? 5 = strong, distinctive voice with the event "
               "intact; 1 = generic voice or the event changed."),
}


def run_eval(generate, judge, fixture=FIXTURE) -> dict:
    """generate(profile, passage) -> str ; judge(output, fixture) -> int(1..5)."""
    output = generate(fixture["profile"], fixture["passage"])
    score = int(judge(output, fixture))
    return {"output": output, "score": score, "passed": score >= PASS_THRESHOLD}


def _engine_generate(profile: str, passage: str) -> str:  # pragma: no cover - needs key
    from write_better.engine import Request, improve
    from write_better.templating import get_template, validate_and_render
    tpl = get_template("character-voice")
    text = validate_and_render(tpl, {"profile": profile, "passage": passage})
    return improve(Request(text=text, services=["paraphrase"], output_format="plain")).text


def _llm_judge(output: str, fixture: dict) -> int:  # pragma: no cover - needs key
    import anthropic
    client = anthropic.Anthropic()
    prompt = (f"{fixture['rubric']}\n\nORIGINAL EVENT: {fixture['passage']}\n\n"
              f"REWRITE:\n{output}\n\nReply with ONLY a single integer from 1 to 5.")
    msg = client.messages.create(model="claude-opus-4-8", max_tokens=16,
                                 messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    m = re.search(r"[1-5]", text)
    return int(m.group(0)) if m else 0


def main() -> int:  # pragma: no cover - needs key
    result = run_eval(_engine_generate, _llm_judge)
    print(f"score: {result['score']}/5  passed: {result['passed']}")
    print("--- rewrite ---")
    print(result["output"])
    return 0 if result["passed"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
