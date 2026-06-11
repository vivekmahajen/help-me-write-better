"""Command-line interface for the Write Better + Format engine.

Examples:
    echo "their going to the store" | write-better -s correct
    write-better -s tighten,structure -f markdown --show-changes -i draft.txt
    write-better -s translate --language Spanish -i note.txt
    write-better -s check -i essay.txt           # analysis only, no rewrite
    write-better --list                          # show available services
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .engine import (
    PREMIUM_MODEL,
    ROUTINE_MODEL,
    STANDARD_MODEL,
    Request,
    has_api_key,
    improve,
    route_model,
)
from .modes import MODES, resolve_services
from .prompt import VALID_FORMATS


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="write-better",
        description="Improve and format text with Claude — preserving meaning and voice.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-s", "--service", default="",
                   help="service(s): letter, name, or alias; comma-separated. "
                        "e.g. 'tighten', 'D', 'correct,structure'. Default: clarify.")
    p.add_argument("-f", "--format", dest="output_format", default="markdown",
                   choices=VALID_FORMATS, metavar="FORMAT",
                   help="output format: " + " | ".join(VALID_FORMATS))
    p.add_argument("-i", "--in", dest="infile", metavar="PATH",
                   help="read TEXT from a file (default: stdin)")
    p.add_argument("-o", "--out", dest="outfile", metavar="PATH",
                   help="write result to a file (default: stdout)")
    p.add_argument("--show-changes", action="store_true",
                   help="include a summary of what changed and why")
    p.add_argument("--request", dest="free_form", metavar="TEXT",
                   help="free-form instruction to guide the engine")

    target = p.add_argument_group("targets")
    target.add_argument("--audience")
    target.add_argument("--tone")
    target.add_argument("--length", help="e.g. '120 words', 'half', 'one paragraph'")
    target.add_argument("--reading-level", dest="reading_level",
                        help="e.g. 'grade 8', 'expert'")
    target.add_argument("--language", help="target language for translate")

    model = p.add_argument_group("model")
    model.add_argument("--model", help="override the routed model id")
    model.add_argument("--effort", default="high",
                       choices=("low", "medium", "high", "max"),
                       help="thinking effort (Opus/Sonnet tiers only)")
    model.add_argument("--no-stream", action="store_true",
                       help="disable streaming output")

    p.add_argument("--list", action="store_true", help="list available services and exit")
    p.add_argument("--pricing", action="store_true",
                   help="print the plan pricing & margin table and exit")
    p.add_argument("--dry-run", action="store_true",
                   help="show the routed model without calling the API")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _print_services() -> None:
    tier_model = {
        "routine": ROUTINE_MODEL,
        "standard": STANDARD_MODEL,
        "premium": PREMIUM_MODEL,
    }
    print("Core services (letter / name — tier):\n")
    printed_extended_header = False
    for m in MODES:
        if not m.letter and not printed_extended_header:
            print("\nExtended services (name — tier):\n")
            printed_extended_header = True
        marker = m.letter or "·"
        aliases = f"  [aliases: {', '.join(m.aliases)}]" if m.aliases else ""
        print(f"  {marker}  {m.name:<17} {m.tier:<8} ({tier_model[m.tier]})")
        print(f"       {m.summary}{aliases}")


def _read_text(infile: str | None) -> str:
    if infile:
        with open(infile, "r", encoding="utf-8") as fh:
            return fh.read()
    if sys.stdin.isatty():
        return ""
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.list:
        _print_services()
        return 0

    if args.pricing:
        from .plans import margin_table

        print(margin_table())
        print("\nFull rationale: docs/PRICING.md")
        return 0

    try:
        modes = resolve_services(args.service) if args.service else resolve_services("clarify")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    model = args.model or route_model(modes)

    if args.dry_run:
        names = ", ".join(m.name for m in modes)
        print(f"services: {names}")
        print(f"routed model: {model}")
        return 0

    text = _read_text(args.infile)
    if not text.strip():
        print("error: no input text. Pipe text in, or use -i FILE.", file=sys.stderr)
        return 2

    if not has_api_key() and not args.model:
        print(
            "error: no Anthropic credential found. Set ANTHROPIC_API_KEY "
            "(or ANTHROPIC_AUTH_TOKEN), or run `ant auth login`.",
            file=sys.stderr,
        )
        return 1

    req = Request(
        text=text,
        services=[m.name for m in modes],
        output_format=args.output_format,
        show_changes=args.show_changes,
        audience=args.audience,
        tone=args.tone,
        length=args.length,
        reading_level=args.reading_level,
        language=args.language,
        free_form=args.free_form,
        model=args.model,
        effort=args.effort,
    )

    to_stdout = args.outfile is None
    # Stream live to the terminal only when writing to stdout and streaming is on.
    stream_to = (sys.stdout.write if (to_stdout and not args.no_stream) else None)

    try:
        result = improve(req, stream_to=stream_to)
    except Exception as exc:  # surface SDK/network errors cleanly
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1

    if args.outfile:
        with open(args.outfile, "w", encoding="utf-8") as fh:
            fh.write(result.text)
        print(f"wrote {args.outfile} ({result.model}, "
              f"{result.output_tokens} output tokens)", file=sys.stderr)
    elif stream_to is None:
        # Non-streaming stdout: print the buffered result.
        print(result.text)
    else:
        # Streamed already; just add a trailing newline if needed.
        if result.text and not result.text.endswith("\n"):
            sys.stdout.write("\n")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
