#!/usr/bin/env python3
"""_introspect.py — the three lenses the golden files are taken through.

Shared by the generator (`regen_goldens.py`) and the gate (`test_golden.py`), so
the two can never drift: a golden is only trustworthy if the thing that wrote it
and the thing that checks it agree on what "the interface" means.

Every lens here is deliberately **module-path independent**. The whole point of
the goldens is to survive `model.py` becoming `model/`, so anything that would
bake in a file layout — `__module__`, `repr()` of a class, a source line number —
is normalised away. What survives is what a consumer can actually observe:

  * DECLARATIONS — the source text of every top-level declaration, as an AST.
    Immune to which file a class lives in, to import statements, to ordering,
    and (see `canonical_dump`) to which Python parsed it.
  * SURFACE — the names importable from the package, plus the per-model facts
    (base classes, config, validator names) the JSON Schema cannot show.
  * BEHAVIOUR — accept/reject outcomes, with pydantic's error type and location,
    for a committed set of probe documents.

The fourth lens is the generated JSON Schema itself, which needs no helper: it
is already a module-agnostic rendering of every field, type, default, union and
description, and is goldened byte-for-byte.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

import frameforge_api
from frameforge_api import model as model_module

GOLDEN_DIR = Path(__file__).parent / "golden"


# --------------------------------------------------------------------------- #
#  Lens 1: declarations                                                       #
# --------------------------------------------------------------------------- #
def model_sources() -> list[Path]:
    """Every source file the contract is declared in, single-file or package.

    `model.py` and `model/` are both legitimate homes for the same declarations;
    this is the one place that difference is allowed to matter.
    """
    origin = Path(model_module.__file__)
    if origin.name == "__init__.py":                 # a package
        return sorted(p for p in origin.parent.rglob("*.py"))
    return [origin]                                  # a single module


def canonical_dump(node: ast.AST) -> str:
    """`ast.dump` that means the same thing on every supported Python.

    `ast.dump` itself does not. Two things move under it between 3.10 and 3.13:

      * **Default-valued fields.** 3.13 omits a field whose value equals its
        default; 3.10 always emits it. Every ``Field(...)`` call in the contract
        is a ``Call`` with no positional arguments, so 3.10 writes ``args=[]``
        and 3.13 writes nothing — and *every* declaration differs between them.
      * **New fields.** 3.12 added ``type_params`` to ``ClassDef`` and
        ``FunctionDef``. It is empty for every declaration here, but it exists
        in ``_fields`` on 3.12+ and does not on 3.10.

    Omitting empty lists and ``None`` handles both at once: the new field
    disappears where it is empty, and the old field stops being written where it
    is defaulted. The result is keyed on what the declaration actually *says*.

    `Constant(value=None)` renders as ``Constant()``. That is unambiguous —
    a bare ``Constant()`` can only be the literal ``None`` — and it is the one
    place this normalisation drops something a reader might expect to see.
    """
    if isinstance(node, ast.AST):
        parts = []
        for field in node._fields:
            value = getattr(node, field, None)
            # The two version-dependent shapes, collapsed to one.
            if value is None or (isinstance(value, list) and not value):
                continue
            parts.append(f"{field}={canonical_dump(value)}")
        return f"{type(node).__name__}({', '.join(parts)})"
    if isinstance(node, list):
        return "[" + ", ".join(canonical_dump(v) for v in node) + "]"
    return repr(node)


def _key(node: ast.AST) -> str | None:
    """The declared name, or None for statements that declare nothing."""
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None


def declarations(paths: list[Path] | None = None) -> dict[str, str]:
    """Map declared name -> normalised AST dump of its top-level statement.

    Imports and bare expressions (the `model_rebuild()` sweep) are excluded on
    purpose: those are wiring, and splitting a module is *entirely* a rewiring
    operation. Everything that defines the contract is a class or an assignment,
    and those must come through a refactor untouched.
    """
    out: dict[str, str] = {}
    for path in paths or model_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            name = _key(node)
            if name is None:
                continue
            dumped = canonical_dump(node)
            if name in out and out[name] != dumped:
                raise AssertionError(
                    f"{name!r} is declared twice with different bodies "
                    f"(second one in {path.name})")
            out[name] = dumped
    return out


# --------------------------------------------------------------------------- #
#  Lens 2: surface                                                            #
# --------------------------------------------------------------------------- #
def _model_facts(cls: type[BaseModel]) -> dict[str, Any]:
    """Per-model facts a JSON Schema does not carry.

    Base classes are recorded by bare name (not `module.Name`) so that moving a
    class between files is invisible here, while re-parenting it is not.
    """
    decorators = cls.__pydantic_decorators__
    return {
        "bases": [b.__name__ for b in cls.__bases__],
        "config": {k: str(v) for k, v in sorted(cls.model_config.items())},
        "fields": list(cls.model_fields),          # declaration order matters to the schema
        "validators": sorted(
            list(decorators.model_validators)
            + list(decorators.field_validators)
            + list(decorators.computed_fields)),
    }


def surface() -> dict[str, Any]:
    """What a consumer can import, and what they get when they do."""
    declared = declarations()
    importable = sorted(n for n in declared if hasattr(model_module, n))
    missing = sorted(n for n in declared if not hasattr(model_module, n))

    models: dict[str, Any] = {}
    for name in importable:
        obj = getattr(model_module, name)
        if isinstance(obj, type) and issubclass(obj, BaseModel):
            models[name] = _model_facts(obj)

    return {
        "frameforge_api.__all__": sorted(frameforge_api.__all__),
        "frameforge_api.model.__all__": sorted(model_module.__all__),
        "frameforge_api.schema.__all__": sorted(frameforge_api.schema.__all__),
        "frameforge_api.model.importable": importable,
        "frameforge_api.model.not_importable": missing,
        "models": models,
    }


# --------------------------------------------------------------------------- #
#  Lens 3: behaviour                                                          #
# --------------------------------------------------------------------------- #
def _error_signature(exc: Exception) -> list[list[str]]:
    """(error type, dotted location) for each complaint, sorted.

    The human-readable message is deliberately dropped: it is pydantic's to
    change. The type and the location are the contract — they are what a caller
    branches on.
    """
    errors = getattr(exc, "errors", None)
    if errors is None:
        return [[type(exc).__name__, ""]]
    return sorted([e["type"], ".".join(str(p) for p in e["loc"])] for e in errors())


def behaviour(probes: list[tuple[str, dict]]) -> dict[str, Any]:
    """Validate each probe and record the verdict, never the exception text."""
    out: dict[str, Any] = {}
    for name, doc in probes:
        try:
            model_module.Document.model_validate(doc)
        except Exception as exc:
            out[name] = {"valid": False, "errors": _error_signature(exc)}
        else:
            out[name] = {"valid": True, "errors": []}
    return out


# --------------------------------------------------------------------------- #
#  I/O                                                                        #
# --------------------------------------------------------------------------- #
def dump(obj: Any) -> str:
    """One canonical serialisation, so a golden diff is always a real diff."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def read_golden(name: str) -> Any:
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))
