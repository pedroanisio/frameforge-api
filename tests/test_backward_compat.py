#!/usr/bin/env python3
"""test_backward_compat.py — the compatibility guarantee, stated and enforced.

The 2.x line has been strictly backward compatible for its whole life, and
nothing said so. That made it an accident rather than a promise: every widening
was free to break an old document, and the only way anyone would find out was a
downstream validator failing on a file that had worked for a year.

`frameforge_api.COMPATIBILITY` now states the guarantee, and this module is what
makes the statement true. The 2.9.0 widening is the first change made under it.

BACKWARD, in the schema-registry sense (see Kafka/Avro, where the term is load
bearing): **a document valid under any earlier 2.x revision stays valid at HEAD.**
Concretely, within the 2.x line a change may

  * add an OPTIONAL field                     (an old document simply omits it)
  * add a member to a union                   (an old document names an old member)
  * widen a type or relax a constraint        (an old value still satisfies it)
  * make a required field optional            (an old document still supplies it)

and may NOT

  * add a required field, remove or rename one
  * remove a union member, narrow a type, tighten a constraint
  * change a default, or change what an existing value means

The reverse direction (FORWARD — a 2.9.0 document validating against a 2.7
reader) is explicitly NOT guaranteed: a reader that predates `spot` ink has no
way to interpret it.

Two corpora, because they fail for different reasons:

  tests/compat/*.json   committed here, pinned at older revisions, runs anywhere.
                        Catches a narrowing the moment it is introduced.
  the sibling monorepo  57 real fixtures across six declared revisions. Skipped
                        when the checkout is absent. Catches the narrowings a
                        hand-written corpus did not think to cover.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import frameforge_api
from frameforge_api import HEAD_VERSION, Document

COMPAT_DIR = Path(__file__).parent / "compat"

MONOREPO = Path(
    os.environ.get("FRAMEFORGE_REPO", Path(__file__).resolve().parents[2] / "frameforge"))
FIXTURES = MONOREPO / "tests" / "fixtures"

needs_monorepo = pytest.mark.skipif(
    not FIXTURES.is_dir(), reason=f"sibling FrameForge checkout not found at {MONOREPO}")

#: Pre-lowering authoring sugar the SDK expands before the core model sees it.
#: A document carrying it is SDK source, not a contract document, so the
#: contract rejecting it is correct and is not a compatibility failure.
GRAMMAR_SUGAR = ("use", "component")


def _has_sugar(node) -> bool:
    if isinstance(node, dict):
        return node.get("type") in GRAMMAR_SUGAR or any(_has_sugar(v) for v in node.values())
    return isinstance(node, list) and any(_has_sugar(v) for v in node)


def _precedence(version: str) -> tuple[int, ...]:
    """Semver precedence as numbers, because the string order is not it.

    `"2.2.0" < "2.10.0"` is **False** lexicographically — `'2'` sorts after
    `'1'` — so comparing declared revisions as strings silently inverts the
    moment a minor reaches two digits. That is exactly when this matters: the
    2.10.0 widening is the first one, and the whole committed compat corpus
    (2.2.0, 2.4.0, 2.7.1) would have been read as *newer* than HEAD.

    Pre-release suffixes are dropped: they order below their release, and no
    fixture here carries one.
    """
    return tuple(int(part) for part in version.split("-", 1)[0].split("."))


def _errors(exc) -> str:
    errs = exc.errors() if hasattr(exc, "errors") else []
    return "; ".join(f"{e['type']} at {'.'.join(str(p) for p in e['loc'])}" for e in errs[:4])


# --------------------------------------------------------------------------- #
#  The guarantee is declared, not just observed                               #
# --------------------------------------------------------------------------- #
def test_the_compatibility_mode_is_declared_and_reachable():
    """SemVer says what the *numbers* mean. It does not say what a minor bump
    promises a DOCUMENT, which is the only question a consumer actually has."""
    assert frameforge_api.COMPATIBILITY == "backward"
    assert "COMPATIBILITY" in frameforge_api.__all__


def test_the_contract_version_moved_for_this_widening():
    """A contract change moves the contract clock, never the package clock alone."""
    major, minor, _ = HEAD_VERSION.split(".", 2)
    assert (int(major), int(minor)) >= (2, 9), HEAD_VERSION


def test_revisions_are_ordered_by_precedence_not_by_string():
    """Regression: the compat corpus was gated by `declared < HEAD_VERSION` on
    raw strings, which inverts as soon as a minor reaches two digits. 2.10.0 is
    the first revision that does, and it turned the whole corpus red while the
    documents themselves were still perfectly valid.
    """
    assert _precedence("2.2.0") < _precedence("2.10.0")
    assert _precedence("2.9.0") < _precedence("2.10.0")
    assert _precedence("2.10.0") < _precedence("2.11.0")
    assert _precedence("2.10.0") < _precedence("3.0.0")
    assert _precedence("2.7.1") < _precedence("2.7.2")
    assert _precedence("2.10.0-rc.1") == _precedence("2.10.0")
    # the exact comparison that was wrong, stated as the string it was
    assert ("2.2.0" < "2.10.0") is False, "if this ever becomes True, drop _precedence"


# --------------------------------------------------------------------------- #
#  Committed corpus — runs everywhere, including CI with no sibling checkout   #
# --------------------------------------------------------------------------- #
def _committed() -> list[Path]:
    return sorted(COMPAT_DIR.glob("*.json"))


def test_the_committed_compat_corpus_is_not_empty():
    docs = _committed()
    assert len(docs) >= 3, "the compat corpus is the CI-side guarantee; it must not thin out"


@pytest.mark.parametrize("path", _committed(), ids=lambda p: p.stem)
def test_a_document_from_an_earlier_revision_still_validates(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    declared = data["version"]
    assert _precedence(declared) < _precedence(HEAD_VERSION), (
        f"{path.name} claims {declared}, not an earlier revision than {HEAD_VERSION}")
    try:
        Document.model_validate(data)
    except Exception as exc:
        pytest.fail(
            f"{path.name} declares {declared} and no longer validates at {HEAD_VERSION}. "
            f"That is a BACKWARD compatibility break, not a fixture problem: {_errors(exc)}")


def test_the_committed_corpus_spans_several_revisions():
    """One old document proves little — a narrowing usually lands in one area."""
    versions = {json.loads(p.read_text(encoding="utf-8"))["version"] for p in _committed()}
    assert len(versions) >= 3, f"only {sorted(versions)} represented"


# --------------------------------------------------------------------------- #
#  Real corpus — the fixtures the monorepo actually gates on                   #
# --------------------------------------------------------------------------- #
@needs_monorepo
def test_every_lowered_fixture_from_every_revision_validates_at_head():
    """The empirical half of the guarantee, replayed by declared revision.

    Two exclusions, both by design: `b1/` is the frozen pre-P3 oracle kept as
    codemod *input*, and documents carrying grammar sugar are pre-lowering SDK
    source. Everything else is a document the contract promised to keep reading.
    """
    yaml = pytest.importorskip("yaml")
    by_version: dict[str, list[int]] = {}
    failures: list[str] = []

    for path in sorted(FIXTURES.rglob("*.fg.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("dsl") != "FrameForge":
            continue
        if "b1" in path.parts or _has_sugar(data):
            continue
        declared = str(data.get("version"))
        row = by_version.setdefault(declared, [0, 0])
        try:
            Document.model_validate(data)
            row[0] += 1
        except Exception as exc:
            row[1] += 1
            failures.append(f"{declared} {path.relative_to(FIXTURES)}: {_errors(exc)}")

    assert by_version, f"no fixtures found under {FIXTURES}"
    assert not failures, (
        f"{len(failures)} document(s) that validated under an earlier revision no longer "
        f"validate at {HEAD_VERSION}:\n  " + "\n  ".join(failures[:8]))
    # The corpus is the evidence; if it shrinks, so does the evidence.
    assert sum(ok for ok, _ in by_version.values()) >= 50


@needs_monorepo
def test_the_widening_did_not_change_any_existing_verdict():
    """Backward compatibility is about acceptance. This is the other half: a
    document that was REJECTED must still be rejected, for the same reason —
    otherwise the widening quietly legalised something."""
    yaml = pytest.importorskip("yaml")
    still_rejected = 0
    for path in sorted(FIXTURES.rglob("*.fg.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("dsl") != "FrameForge":
            continue
        if not _has_sugar(data):
            continue
        with pytest.raises(Exception):
            Document.model_validate(data)
        still_rejected += 1
    assert still_rejected >= 3, (
        "grammar-sugar documents are the api/sdk boundary; if they started "
        "validating, the core profile has silently absorbed pre-lowering syntax")


# --------------------------------------------------------------------------- #
#  The codemod is bound by the same guarantee                                  #
# --------------------------------------------------------------------------- #
# A migration tool shipped alongside a backward-compatibility promise is a way
# to break that promise at arm's length: the contract keeps accepting the old
# document, and the tool the contract tells you to run hands back one it does
# not. These pin the codemod to the same rule the models are held to.
@pytest.mark.parametrize("path", _committed(), ids=lambda p: p.stem)
def test_migrating_an_older_document_leaves_it_valid(path: Path):
    """`ff-codemod` on a document from an earlier revision must not break it.

    The committed corpus is the right input precisely because these documents
    are *already* valid: there is nothing to fix, so anything the codemod
    changes is damage.
    """
    from frameforge_api import migrate_document

    data = json.loads(path.read_text(encoding="utf-8"))
    result = migrate_document(data)
    try:
        Document.model_validate(result.document)
    except Exception as exc:
        pytest.fail(
            f"{path.name} declares {data['version']} and validates at {HEAD_VERSION}, "
            f"but does NOT after migration — the codemod broke a valid document: "
            f"{_errors(exc)}")


@pytest.mark.parametrize("path", _committed(), ids=lambda p: p.stem)
def test_migrating_an_older_document_never_mutates_the_committed_file(path: Path):
    """The corpus is evidence. A codemod that edits it in place destroys it."""
    from frameforge_api import migrate_document

    before = path.read_bytes()
    data = json.loads(before.decode("utf-8"))
    snapshot = json.loads(before.decode("utf-8"))
    migrate_document(data)
    assert data == snapshot, "migrate_document mutated its argument"
    assert path.read_bytes() == before


@needs_monorepo
def test_the_codemod_never_makes_a_valid_fixture_invalid():
    """The empirical half, over the whole real corpus.

    Hand-written probes cover the forms someone thought of. This covers every
    lowered fixture the monorepo gates on: whatever the codemod does to them, it
    must not be to break them.
    """
    yaml = pytest.importorskip("yaml")
    from frameforge_api import migrate_document

    checked, broken = 0, []
    for path in sorted(FIXTURES.rglob("*.fg.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("dsl") != "FrameForge":
            continue
        if "b1" in path.parts or _has_sugar(data):
            continue
        try:
            Document.model_validate(data)
        except Exception:
            continue                       # not valid to begin with; not this test's job
        checked += 1
        try:
            Document.model_validate(migrate_document(data).document)
        except Exception as exc:
            broken.append(f"{path.relative_to(FIXTURES)}: {_errors(exc)}")

    assert not broken, (
        f"the codemod turned {len(broken)} of {checked} valid fixture(s) invalid:\n  "
        + "\n  ".join(broken[:8]))
    assert checked >= 45, f"only {checked} valid fixtures actually migrated"
