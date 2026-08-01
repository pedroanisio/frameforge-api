#!/usr/bin/env python3
"""regen_goldens.py — rewrite the t0 snapshots in `tests/golden/`.

    python tests/regen_goldens.py          # or: make goldens

Run this ONLY when a change to the contract is intended, and review the diff as
carefully as the code change: a golden that moves without a deliberate reason is
the bug. The point of these files is that a refactor produces **no diff at all**
— that is the whole safety argument for moving declarations between modules.

Four files, four lenses (see `_introspect` for what each one sees):

  schema.json        the generated JSON Schema, canonicalised
  declarations.json  every top-level declaration, as a normalised AST
  surface.json       what is importable, and the per-model facts schema omits
  behaviour.json     accept/reject verdicts for the probe corpus
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _introspect import GOLDEN_DIR, behaviour, declarations, dump, surface
from _probes import PROBES

from frameforge_api import build_schema


def main() -> int:
    GOLDEN_DIR.mkdir(exist_ok=True)
    for name, payload in (
        ("schema.json", build_schema()),
        ("declarations.json", declarations()),
        ("surface.json", surface()),
        ("behaviour.json", behaviour(PROBES)),
    ):
        target = GOLDEN_DIR / name
        text = dump(payload)
        changed = not target.is_file() or target.read_text(encoding="utf-8") != text
        target.write_text(text, encoding="utf-8")
        print(f"{'wrote  ' if changed else 'same   '} {target.relative_to(Path.cwd())}  "
              f"({len(text):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
