#!/usr/bin/env python
"""Run the RssHub lite pytest suites from any checkout directory."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="RssHub lite test runner")
    parser.add_argument(
        "--category", choices=("unit", "integration", "all"), default="all"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--quick", action="store_true", help="Use concise pytest output"
    )
    args, extra = parser.parse_known_args()
    try:
        import pytest
    except ImportError:
        parser.error(
            "Install development dependencies: python -m pip install -r requirements-dev.txt"
        )
    tests = Path(__file__).resolve().parent
    target = tests if args.category == "all" else tests / args.category
    options = [str(target), "-v" if args.verbose else "-q", *extra]
    return pytest.main(options)


if __name__ == "__main__":
    raise SystemExit(main())
