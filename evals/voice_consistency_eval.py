"""Voice-consistency eval — does a context-matched continuation keep the voice?

Combines a deterministic pre-check (``voice.voice_drift`` over style metrics) with
an LLM judge that scores voice match 1-5. Dependency-injected for offline tests
(see ``tests/test_context.py``); ``main()`` needs ``ANTHROPIC_API_KEY``.

    python -m evals.voice_consistency_eval   # exits non-zero if score < 4
"""

from __future__ import annotations

import re
import sys

PASS_THRESHOLD = 4

FIXTURE = {
    "context": ("The old lighthouse stood at the edge of the cliff. Mara climbed the "
                "last few steps and pushed open the heavy door. Salt and dust. She had "
                "not been here in years."),
    "brief": "Continue the scene: Mara explores the lighthouse interior.",
    "rubric": ("On a 1-5 scale, how well does the CONTINUATION match the voice, rhythm, "
               "and POV of the CONTEXT while staying consistent with it? 5 = seamless; "
               "1 = different voice or contradicts the context."),
}


def run_eval(generate, judge, fixture=FIXTURE) -> dict:
    """generate(context, brief) -> continuation ; judge(context, output) -> int(1..5)."""
    from write_better.voice import voice_drift
    output = generate(fixture["context"], fixture["brief"])
    score = int(judge(fixture["context"], output))
    drift = voice_drift(fixture["context"], output)        # deterministic signal
    return {"output": output, "score": score, "drift": drift,
            "passed": score >= PASS_THRESHOLD}


def _engine_generate(context: str, brief: str) -> str:  # pragma: no cover - needs key
    from write_better.engine import Request, improve
    return improve(Request(text=brief, services=["write"], output_format="plain",
                           context=context, context_role="preceding_manuscript")).text


def _llm_judge(context: str, output: str) -> int:  # pragma: no cover - needs key
    import anthropic
    client = anthropic.Anthropic()
    prompt = (f"{FIXTURE['rubric']}\n\nCONTEXT:\n{context}\n\nCONTINUATION:\n{output}\n\n"
              f"Reply with ONLY a single integer from 1 to 5.")
    msg = client.messages.create(model="claude-opus-4-8", max_tokens=16,
                                 messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    m = re.search(r"[1-5]", text)
    return int(m.group(0)) if m else 0


def main() -> int:  # pragma: no cover - needs key
    result = run_eval(_engine_generate, _llm_judge)
    print(f"score: {result['score']}/5  drift: {result['drift']['drift']}  "
          f"passed: {result['passed']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
