#!/usr/bin/env python3
"""``make doc-check`` — run every doc-vs-code gate and report all failures at once.

The gates themselves live in `tooling/docgates.py`, which `tests/test_doc_gates.py`
also imports; this script is the CLI face so `make check` can run them without
pytest. It reports every problem rather than stopping at the first, because a
doc audit that makes you re-run it once per finding is a doc audit nobody runs.

Exit status: ``0`` every gate clean, ``1`` at least one problem.
"""
from __future__ import annotations

import sys
from pathlib import Path

TOOLING = Path(__file__).resolve().parent
if str(TOOLING) not in sys.path:
    sys.path.insert(0, str(TOOLING))

from docgates import GATES  # noqa: E402


def main() -> int:
    total = 0
    for name, gate in GATES:
        problems = gate()
        total += len(problems)
        if problems:
            print(f"FAIL  {name}")
            for p in problems:
                print(f"        {p}")
        else:
            print(f"ok    {name}")

    if total:
        print(f"\ndoc-check: {total} problem(s). Docs and code disagree.")
        return 1
    print(f"\ndoc-check: OK — {len(GATES)} gates, no drift.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
