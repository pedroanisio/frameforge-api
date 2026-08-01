"""JSON Schema generation for the FrameForge v2 contract.

The schema is never hand-authored: it is emitted from :class:`Document`, the
single source of truth in :mod:`frameforge_api.model`, so the two cannot drift.
The generated file ships **inside the wheel** (``frameforge_api/schema/
frameforge-v2.schema.json``), which is what lets a non-Python consumer — a
TypeScript client, an editor's linter, a CI job — validate a FrameForge document
without running Python at all.

This module is deliberately a *library first*. In the monorepo the equivalent
lived in ``docs/schema/build_schema.py`` as a script that mutated ``sys.path`` to
find the model; nothing could import it, so every consumer re-implemented the
generation or shelled out. Here :func:`build` is an ordinary function,
:func:`check` is the staleness gate, and :func:`main` is a thin CLI over both
(``ff-schema``).

    >>> from frameforge_api import build_schema
    >>> schema = build_schema()
    >>> schema["version"]                                     # doctest: +SKIP
    '2.8.2'
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from frameforge_api.model import HEAD_VERSION, Document

__all__ = ["SCHEMA_PATH", "build", "check", "load", "main", "write"]

#: The generated schema as shipped in the wheel. Package data, not a repo path,
#: so it resolves identically from a checkout and from an installed wheel.
SCHEMA_PATH: Path = Path(__file__).parent / "schema" / "frameforge-v2.schema.json"

#: Resolvable, version-pinned `$id`. A document self-declares conformance against
#: an exact schema version rather than an unversioned major line.
SCHEMA_ID_TEMPLATE = "https://frameforge.dev/schema/{version}/frameforge-v2.schema.json"


def build() -> dict[str, Any]:
    """Generate the JSON Schema from the Pydantic models.

    Pure: no I/O, no globals. The ``$id`` and ``version`` mirror
    :data:`~frameforge_api.model.HEAD_VERSION`, so a schema file can always be
    traced back to the exact contract revision that produced it.
    """
    schema = Document.model_json_schema(ref_template="#/$defs/{model}")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = SCHEMA_ID_TEMPLATE.format(version=HEAD_VERSION)
    schema["version"] = HEAD_VERSION
    schema["title"] = (
        f"FrameForge v2 (HEAD {HEAD_VERSION}) — generated from the Pydantic models "
        f"(core conformance profile)"
    )
    return schema


def _serialize(schema: dict[str, Any]) -> str:
    """The one canonical on-disk form — pinned so `--check` compares like with like."""
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def load(path: Path | None = None) -> dict[str, Any]:
    """Read the committed schema (the shipped package data by default)."""
    return json.loads(Path(path or SCHEMA_PATH).read_text(encoding="utf-8"))


def write(path: Path | None = None) -> Path:
    """Regenerate the schema on disk and return where it was written."""
    target = Path(path or SCHEMA_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_serialize(build()), encoding="utf-8")
    return target


def check(path: Path | None = None) -> bool:
    """True when the on-disk schema matches a fresh build.

    The drift gate: models and schema are one artifact in two forms, so a stale
    file is a defect, not a cosmetic lag.
    """
    target = Path(path or SCHEMA_PATH)
    if not target.is_file():
        return False
    return target.read_text(encoding="utf-8") == _serialize(build())


def main(argv: list[str] | None = None) -> int:
    """``ff-schema`` — regenerate, verify, or validate against the contract."""
    ap = argparse.ArgumentParser(
        prog="ff-schema", description="Generate/verify the FrameForge v2 JSON Schema.")
    ap.add_argument("document", nargs="?",
                    help="optional FrameForge document (.yaml/.yml/.json) to validate "
                         "against the models")
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if the committed schema is stale")
    ap.add_argument("--out", type=Path, default=None,
                    help=f"write the schema here instead of {SCHEMA_PATH}")
    ap.add_argument("--print", dest="to_stdout", action="store_true",
                    help="write the schema to stdout instead of a file")
    args = ap.parse_args(argv)

    rc = 0
    if args.to_stdout:
        sys.stdout.write(_serialize(build()))
    elif args.check:
        if check(args.out):
            print(f"schema OK — up to date with the models (HEAD {HEAD_VERSION})")
        else:
            print(f"STALE: {args.out or SCHEMA_PATH} differs from a fresh build; "
                  f"run `ff-schema` to regenerate", file=sys.stderr)
            rc = 1
    elif not args.document:
        # Regenerating is the default ONLY when no other job was asked for.
        # `ff-schema doc.yaml` must not write anything: the default schema path
        # is inside the installed package, so a validation run would otherwise
        # mutate site-packages as a side effect (and fail on a read-only install).
        target = write(args.out)
        print(f"wrote {target}  (HEAD {HEAD_VERSION}, "
              f"{len(build().get('$defs', {}))} $defs)")

    if args.document:
        rc = max(rc, _validate_document(Path(args.document)))
    return rc


def _validate_document(path: Path) -> int:
    """Validate one document against the models; 0 clean, 1 invalid, 2 unreadable."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"could not read {path}: {exc}", file=sys.stderr)
        return 2
    try:
        if path.suffix.lower() in (".yaml", ".yml"):
            import yaml  # optional: only YAML input needs it
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
    except ImportError:
        print("PyYAML is not installed; install `frameforge-api[yaml]` to validate "
              "YAML documents (JSON always works)", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"could not parse {path}: {exc}", file=sys.stderr)
        return 2
    try:
        Document.model_validate(data)
    except Exception as exc:
        print(f"INVALID  {path.name}\n{exc}", file=sys.stderr)
        return 1
    print(f"VALID    {path.name}  (FrameForge {HEAD_VERSION} core profile)")
    return 0


if __name__ == "__main__":                                    # pragma: no cover
    raise SystemExit(main())
