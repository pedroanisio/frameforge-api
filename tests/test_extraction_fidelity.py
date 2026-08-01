#!/usr/bin/env python3
"""test_extraction_fidelity.py — the extracted contract still speaks for the corpus.

A contract package is only worth anything if it accepts exactly what the system
it was extracted from accepts. These tests run the standalone models against the
**real** FrameForge fixture corpus and against the monorepo's own committed
schema, so a divergence shows up here rather than in a downstream consumer.

They are skipped — not failed — when the sibling checkout is absent, because the
package must build and test standalone (that is the point of the split). When it
IS present, the comparison is the strongest evidence available that the
extraction was faithful.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from _introspect import declarations

from frameforge_api import HEAD_VERSION, Document, build_schema

#: The sibling monorepo checkout, if this is a developer machine rather than CI.
MONOREPO = Path(
    os.environ.get("FRAMEFORGE_REPO", Path(__file__).resolve().parents[2] / "frameforge"))
FIXTURES = MONOREPO / "tests" / "fixtures"
MONOREPO_SCHEMA = MONOREPO / "docs" / "schema" / "frameforge-v2.schema.json"

needs_monorepo = pytest.mark.skipif(
    not FIXTURES.is_dir(),
    reason=f"sibling FrameForge checkout not found at {MONOREPO} "
           f"(set FRAMEFORGE_REPO to point at one)")

#: True when the operator named a checkout, rather than one merely happening to
#: sit next to this one on disk. It is the difference between "no gate was
#: asked for" and "the gate that was asked for did not run".
EXPLICIT_MONOREPO = "FRAMEFORGE_REPO" in os.environ


def _unusable(reason: str) -> None:
    """Skip, or fail if this gate was explicitly requested.

    Skipping is correct when the sibling checkout merely happens to be absent or
    behind: the contract moves in this package first and the monorepo catches
    up, so a revision or two of lag is the normal state and must never fail a
    standalone build or CI, where there is no sibling at all.

    It is wrong when `FRAMEFORGE_REPO` was set. That is an explicit request for
    this gate, and a silent skip then reports green while covering nothing —
    which is exactly how this suite spent 2026-08-01 not running.
    """
    if EXPLICIT_MONOREPO:
        pytest.fail(
            f"FRAMEFORGE_REPO={os.environ['FRAMEFORGE_REPO']} was set explicitly, "
            f"so the fidelity gate was requested — but it cannot run: {reason}")
    pytest.skip(f"{reason} (the fidelity gate is covering nothing)")


def _upstream_schema_version() -> str | None:
    if not MONOREPO_SCHEMA.is_file():
        return None
    return json.loads(MONOREPO_SCHEMA.read_text(encoding="utf-8")).get("version")


def _fixtures() -> list[Path]:
    return sorted(FIXTURES.rglob("*.fg.yaml"))


@needs_monorepo
def test_the_extracted_schema_matches_the_monorepos_committed_schema():
    """The proof of a faithful extraction: same models in, same contract out.

    Compared semantically (key order and indentation are serializer choices, not
    contract), so a formatting difference between the two generators never
    masquerades as a contract change.
    """
    if not MONOREPO_SCHEMA.is_file():
        _unusable(f"no committed schema at {MONOREPO_SCHEMA}")
    theirs = json.loads(MONOREPO_SCHEMA.read_text(encoding="utf-8"))
    ours = build_schema()
    if theirs.get("version") != HEAD_VERSION:
        _unusable(f"monorepo is at {theirs.get('version')}, "
                  f"this package at {HEAD_VERSION}")
    assert json.dumps(ours, sort_keys=True) == json.dumps(theirs, sort_keys=True)


#: Grammar-level authoring sugar. These `type` values are NOT core-profile
#: objects: the SDK lowers them (`sdk.expand()` / `DocumentBuilder.build()`)
#: into real groups before the core model ever sees them. A document carrying
#: them is pre-lowering source, so the contract package rejecting it is correct
#: behaviour — and is precisely the api/sdk boundary this split draws.
GRAMMAR_SUGAR = ("use", "component")


def _has_grammar_sugar(node) -> bool:
    if isinstance(node, dict):
        if node.get("type") in GRAMMAR_SUGAR:
            return True
        return any(_has_grammar_sugar(v) for v in node.values())
    if isinstance(node, list):
        return any(_has_grammar_sugar(v) for v in node)
    return False


@needs_monorepo
def test_the_whole_fixture_corpus_still_validates():
    """Every LOWERED document the monorepo gates on must pass the standalone models.

    A fixture the extracted contract rejects — other than the two documented
    exclusions below — is a regression in the extraction, not a bad fixture: the
    corpus predates the split.

    Two exclusions, both by design and both counted so they cannot quietly grow:
      * ``b1/`` is the frozen pre-P3 oracle, kept as codemod *input*;
      * documents carrying `use`/`component` are pre-lowering SDK source.
    """
    yaml = pytest.importorskip("yaml")
    docs = _fixtures()
    assert docs, f"no fixtures under {FIXTURES}"

    checked, sugar, oracle, failures = 0, [], [], []
    for path in docs:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("dsl") != "FrameForge":
            continue
        if "b1" in path.parts:
            oracle.append(path.name)
            continue
        if _has_grammar_sugar(data):
            sugar.append(path.name)
            continue
        try:
            Document.model_validate(data)
            checked += 1
        except Exception as exc:
            failures.append(f"{path.relative_to(FIXTURES)}: {str(exc)[:180]}")

    assert not failures, (
        f"{len(failures)} corpus document(s) the extracted contract rejects:\n  "
        + "\n  ".join(failures[:10]))
    assert checked >= 45, f"only {checked} documents actually checked"
    # Measured at extraction: 4 of 56 v2 fixtures carry grammar sugar. A jump
    # means either the SDK grew a new pre-lowering form the contract should know
    # about, or a fixture regressed — both worth a look.
    assert len(sugar) <= 6, f"grammar-sugar exclusions grew to {len(sugar)}: {sugar}"


@needs_monorepo
def test_grammar_sugar_is_rejected_on_purpose():
    """The boundary, asserted from the other side: `use` is SDK source, not a
    core object, so the contract must NOT quietly accept it."""
    doc = {
        "dsl": "FrameForge", "version": HEAD_VERSION, "title": "sugar",
        "pages": [{"mode": "page", "id": "p1",
                   "canvas": {"size": [100, 100], "units": "px"},
                   "layers": [{"id": "l", "objects": [
                       {"type": "use", "symbol": "badge", "box": [0, 0, 10, 10]}]}]}],
    }
    with pytest.raises(Exception):
        Document.model_validate(doc)


@needs_monorepo
def test_every_declaration_still_matches_the_monorepos():
    """The models moved verbatim — compared declaration for declaration.

    This was a line-for-line comparison while the contract was a single file. It
    could not survive the split into `model/`, and forcing it to would have meant
    freezing the file layout forever to keep a test happy. Comparing normalised
    ASTs keyed by name is the same assertion minus the accident: it is blind to
    which file a class lives in, to declaration order and to import wiring — the
    three things a module split is *allowed* to change — and it still fails on
    any edit to a class body, a default, a description or a validator.

    `tests/golden/declarations.json` applies the identical lens against this
    package's own pre-split state; this one points it at upstream.
    """
    theirs = MONOREPO / "src" / "frameforge" / "model.py"
    if not theirs.is_file():
        _unusable(f"monorepo model.py not present at {theirs}")
    upstream_version = _upstream_schema_version()
    if upstream_version is not None and upstream_version != HEAD_VERSION:
        _unusable(f"monorepo is at {upstream_version}, "
                  f"this package at {HEAD_VERSION}")

    ours = declarations()
    up = declarations([theirs])
    # `__all__` is package wiring on our side and module wiring on theirs.
    ours.pop("__all__", None)
    up.pop("__all__", None)

    assert sorted(ours) == sorted(up), (
        f"declaration set diverged from upstream: "
        f"only here={sorted(set(ours) - set(up))} only upstream={sorted(set(up) - set(ours))}")
    changed = sorted(k for k in up if ours[k] != up[k])
    assert not changed, f"declarations diverged from the monorepo's source of truth: {changed}"
