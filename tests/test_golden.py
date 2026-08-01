#!/usr/bin/env python3
"""test_golden.py — the interfaces, frozen at t0.

These are the tests that make it safe to move `model.py`'s 183 declarations into
a package. Every other test in this suite asserts a *property* ("unknown keys are
rejected"); these assert **identity** — that the contract observable from outside
is bit-for-bit what it was before the refactor started.

Four independent lenses, because no single one is sufficient:

  SCHEMA        catches a changed field, type, default, description, union member
                or discriminator. Blind to anything not serialised into JSON.
  DECLARATIONS  catches an edited class body, even one the schema cannot see
                (a validator's logic, a docstring). Blind to import wiring, which
                is exactly what a module split is allowed to change.
  SURFACE       catches a name that stopped being importable, a re-parented
                class, a changed `model_config`, a dropped validator. This is the
                lens that fails if the split forgets to re-export something.
  BEHAVIOUR     catches a validator that stopped firing. A dropped `@model_validator`
                keeps the schema, the declarations AND the surface identical while
                silently accepting documents that were errors yesterday.

Regenerate with `make goldens` — and only when the contract is meant to move.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _introspect import behaviour, declarations, dump, read_golden, surface
from _probes import PROBES

from frameforge_api import build_schema

REGEN = "regenerate deliberately with `make goldens`, and review the diff"


# --------------------------------------------------------------------------- #
#  SCHEMA — the contract as every non-Python consumer sees it                 #
# --------------------------------------------------------------------------- #
def test_the_generated_schema_is_byte_identical_to_t0():
    """The strongest single gate: same models in, same 105 `$defs` out.

    Compared as canonical text rather than as parsed JSON, so a change in `$defs`
    ordering — which a module split can plausibly cause, and which downstream
    diffs would show — fails here instead of passing silently.
    """
    assert dump(build_schema()) == dump(read_golden("schema.json")), REGEN


# --------------------------------------------------------------------------- #
#  DECLARATIONS — the source of the contract, wherever it now lives           #
# --------------------------------------------------------------------------- #
def test_every_declaration_survives_the_move_unedited():
    """183 top-level declarations, keyed by name, compared as normalised ASTs.

    File layout, ordering and import statements are invisible to this lens by
    construction — so it stays green through a pure move and goes red the moment
    a move turns into an edit.
    """
    now, then = declarations(), read_golden("declarations.json")
    assert sorted(now) == sorted(then), (
        f"declaration set changed: added={sorted(set(now) - set(then))} "
        f"removed={sorted(set(then) - set(now))}")
    changed = sorted(k for k in then if now[k] != then[k])
    assert not changed, f"declarations edited, not moved: {changed}"


# --------------------------------------------------------------------------- #
#  SURFACE — what a consumer can import, and what they get                    #
# --------------------------------------------------------------------------- #
def test_the_import_surface_is_unchanged():
    now, then = surface(), read_golden("surface.json")

    for key in ("frameforge_api.__all__", "frameforge_api.model.__all__",
                "frameforge_api.schema.__all__"):
        assert now[key] == then[key], f"{key} changed — {REGEN}"

    missing = sorted(set(then["frameforge_api.model.importable"])
                     - set(now["frameforge_api.model.importable"]))
    assert not missing, (
        f"no longer importable from frameforge_api.model: {missing}. A package "
        f"split must re-export every declared name, or it is a breaking change.")

    assert not now["frameforge_api.model.not_importable"], (
        f"declared but not reachable at runtime: {now['frameforge_api.model.not_importable']}")


def test_every_model_keeps_its_bases_config_fields_and_validators():
    """Per-model facts the JSON Schema cannot show.

    Field *order* is included on purpose: it drives `$defs` property order, so a
    reordering that the schema gate would catch is diagnosed here by name.
    """
    now, then = surface()["models"], read_golden("surface.json")["models"]
    assert sorted(now) == sorted(then), (
        f"model set changed: added={sorted(set(now) - set(then))} "
        f"removed={sorted(set(then) - set(now))}")
    for name in sorted(then):
        assert now[name] == then[name], f"{name} changed: {then[name]} -> {now[name]}"


# --------------------------------------------------------------------------- #
#  BEHAVIOUR — the eleven validators the schema cannot express                #
# --------------------------------------------------------------------------- #
def test_every_probe_still_gets_the_same_verdict():
    """A dropped validator is invisible to all three lenses above.

    36 probes: 14 that must be ACCEPTED (the legacy-key normalisations — losing
    one silently breaks existing documents) and 22 that must be REJECTED (the
    guards — losing one silently widens the contract, which nothing downstream
    reports).
    """
    now, then = behaviour(PROBES), read_golden("behaviour.json")
    assert sorted(now) == sorted(then), (
        f"probe set changed: added={sorted(set(now) - set(then))} "
        f"removed={sorted(set(then) - set(now))}")

    flipped = sorted(k for k in then if now[k]["valid"] != then[k]["valid"])
    assert not flipped, (
        "the verdict changed for: " + ", ".join(
            f"{k} ({'rejected' if then[k]['valid'] else 'accepted'} now, "
            f"{'accepted' if then[k]['valid'] else 'rejected'} at t0)" for k in flipped))

    resigned = sorted(k for k in then if now[k]["errors"] != then[k]["errors"])
    assert not resigned, (
        f"same verdict, different error type/location for: {resigned}. Callers "
        f"branch on these, so this is a contract change even though the "
        f"accept/reject decision held.")
