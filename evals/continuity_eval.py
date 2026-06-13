"""Continuity eval — does the `continuity` check catch seeded canon violations?

The harness is dependency-injected so it's unit-testable offline (see
``tests/test_context.py``); ``main()`` wires the real engine + an Anthropic judge
and requires ``ANTHROPIC_API_KEY``.

    python -m evals.continuity_eval      # exits non-zero if detection rate < 2/3
"""

from __future__ import annotations

import re
import sys

PASS_RATE = 2 / 3  # catch at least two of three seeded violations

FIXTURE = {
    "context": ("Chapter 1 established that Mara has dark green eyes and is terrified "
                "of the open sea. Her younger brother is named Tomas."),
    "passage": ("Mara gazed out at the calm water with her bright blue eyes and smiled. "
                "The sea had always been her favorite place. \"Race you to the pier, "
                "Lucas!\" she called to her brother."),
    "violations": ["eye color", "fear of the sea", "brother's name"],
}


def run_eval(check, judge, fixture=FIXTURE) -> dict:
    """check(context, passage) -> report ; judge(report, fixture) -> int detected (0..3)."""
    report = check(fixture["context"], fixture["passage"])
    detected = int(judge(report, fixture))
    rate = detected / len(fixture["violations"])
    return {"report": report, "detected": detected, "rate": rate,
            "passed": rate >= PASS_RATE}


def _engine_check(context: str, passage: str) -> str:  # pragma: no cover - needs key
    from write_better.engine import Request, improve
    return improve(Request(text=passage, services=["continuity"],
                           output_format="plain", context=context)).text


def _llm_judge(report: str, fixture: dict) -> int:  # pragma: no cover - needs key
    import anthropic
    client = anthropic.Anthropic()
    prompt = (f"A continuity report is below. How many of these {len(fixture['violations'])} "
              f"issues does it correctly flag: {', '.join(fixture['violations'])}? "
              f"Reply with ONLY a single integer.\n\nREPORT:\n{report}")
    msg = client.messages.create(model="claude-opus-4-8", max_tokens=16,
                                 messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    m = re.search(r"\d", text)
    return int(m.group(0)) if m else 0


def main() -> int:  # pragma: no cover - needs key
    result = run_eval(_engine_check, _llm_judge)
    print(f"detected: {result['detected']}/3  rate: {result['rate']:.2f}  "
          f"passed: {result['passed']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
