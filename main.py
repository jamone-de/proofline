"""Proofline CLI entry point.

Usage::

    python main.py scan
    python main.py propose --delete <module>::<symbol>
    python main.py propose --refactor <module>::<symbol> --new-code <file_or_inline>
    python main.py report

MIT License.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_scan(_args: argparse.Namespace) -> None:
    """Run the autonomy scanner and write proofline/autonomy_map.json."""
    from proofline import scanner
    scanner.scan()


def _cmd_propose(args: argparse.Namespace) -> None:
    """Propose a delete or refactor, running the adversary as needed."""
    from proofline import actions

    if args.delete:
        raw = args.delete
        if "::" not in raw:
            print("ERROR: --delete requires the format <module>::<symbol>", file=sys.stderr)
            sys.exit(1)
        module, symbol = raw.split("::", 1)
        result = actions.propose_delete(module, symbol)

    elif args.refactor:
        raw = args.refactor
        if "::" not in raw:
            print("ERROR: --refactor requires the format <module>::<symbol>", file=sys.stderr)
            sys.exit(1)
        module, symbol = raw.split("::", 1)

        new_code_src = args.new_code or ""
        # Allow passing a file path or inline code
        if new_code_src and Path(new_code_src).exists():
            new_code_src = Path(new_code_src).read_text(encoding="utf-8")

        result = actions.propose_refactor(module, symbol, new_code_src)

    else:
        print("ERROR: specify --delete or --refactor", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))


def _cmd_report(_args: argparse.Namespace) -> None:
    """Generate docs/index.html from the ledger and autonomy map."""
    from proofline import reporter
    out = reporter.generate()
    print(f"Report available at: {out}")


def _cmd_serve(args: argparse.Namespace) -> None:
    """Start the Proofline web dashboard."""
    from proofline.web.app import create_app
    app = create_app()
    print(f"Starting Proofline dashboard on http://127.0.0.1:{args.port}")
    app.run(host="127.0.0.1", port=args.port, debug=args.debug)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proofline",
        description="Proofline - verification layer for autonomous coding agents.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scan
    sub.add_parser("scan", help="Analyse target_app and write autonomy_map.json.")

    # propose
    propose_p = sub.add_parser("propose", help="Propose a code change.")
    group = propose_p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--delete", metavar="MODULE::SYMBOL",
        help="Delete SYMBOL from MODULE (GREEN modules only).",
    )
    group.add_argument(
        "--refactor", metavar="MODULE::SYMBOL",
        help="Refactor SYMBOL in MODULE (GREEN or YELLOW).",
    )
    propose_p.add_argument(
        "--new-code", metavar="CODE_OR_FILE",
        help="Replacement code (inline string or path to .py file). Required for --refactor.",
    )

    # report
    sub.add_parser("report", help="Generate docs/index.html verification certificate.")

    # serve
    serve_p = sub.add_parser("serve", help="Start the web dashboard.")
    serve_p.add_argument("--port", type=int, default=5050, help="Port to listen on (default: 5050).")
    serve_p.add_argument("--debug", action="store_true", help="Enable Flask debug mode.")

    return parser


def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate command."""
    parser = _build_parser()
    args = parser.parse_args()

    dispatch = {
        "scan": _cmd_scan,
        "propose": _cmd_propose,
        "report": _cmd_report,
        "serve": _cmd_serve,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
