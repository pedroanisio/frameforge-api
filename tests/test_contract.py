#!/usr/bin/env python3
"""test_contract.py — the contract this package exists to hold still.

`frameforge-api` is the leaf every other FrameForge package depends on, so its
whole value is that it does not move under them. These tests pin the four
properties that make that true:

  * LEAF — the models import nothing from FrameForge. If this ever fails, the
    contract has grown a dependency on an engine and the split has collapsed.
  * CLOSED — every object forbids unknown keys, so a typo is an error rather
    than silent data loss (the failure mode a permissive schema hides).
  * GENERATED — the JSON Schema is emitted from the models and gated for
    staleness; they are one artifact in two forms.
  * TWO CLOCKS — the distribution version and the contract version are
    deliberately independent: `__version__` is the wheel's release line,
    `HEAD_VERSION` is the FrameForge document-format revision it carries.
    Welding them together makes one of the two unshippable.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from _introspect import model_sources

import frameforge_api
from frameforge_api import (
    HEAD_VERSION,
    SCHEMA_PATH,
    Document,
    build_schema,
    check_schema,
    load_schema,
)


def minimal_doc(**over):
    doc = {
        "dsl": "FrameForge",
        "version": HEAD_VERSION,
        "title": "contract",
        "pages": [{
            "mode": "page",
            "id": "p1",
            "canvas": {"size": [400, 200], "units": "px"},
            "layers": [{"id": "main", "objects": [
                {"type": "text", "box": [20, 20, 360, 40], "text": "Hello"},
            ]}],
        }],
    }
    doc.update(over)
    return doc


# --------------------------------------------------------------------------- #
#  1. LEAF — the reason this package can be depended on by everything          #
# --------------------------------------------------------------------------- #
def test_the_model_imports_nothing_from_frameforge():
    """The models must stay a leaf: `re`, `typing`, `pydantic` and nothing else
    from the family. A FrameForge import here would re-couple the contract to an
    engine and defeat the whole extraction.

    Checked per FILE, not per module object. `frameforge_api.model` is a package,
    so parsing only the module `__file__` points at would inspect `__init__.py`
    and nothing else — and `__init__.py` imports exclusively relative names, so
    that version of this test would pass no matter what the other 17 files did.
    """
    for path in model_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        assert not {m for m in imported if m.startswith("frameforge")}, (
            f"{path.name} grew a FrameForge dependency: {sorted(imported)}")
        assert imported <= {"__future__", "re", "typing", "pydantic"}, (
            f"{path.name}: {sorted(imported)}")


def test_the_package_has_exactly_one_runtime_dependency():
    """Cheap to depend on is the feature. Anything beyond pydantic belongs in an
    extra, not in the base install."""
    pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    block = pyproject.split("dependencies = [", 1)[1].split("]", 1)[0]
    deps = [ln.strip().strip('",') for ln in block.strip().splitlines() if ln.strip().startswith('"')]
    assert deps == ["pydantic>=2"], deps


# --------------------------------------------------------------------------- #
#  2. CLOSED — an unknown key is an error, never silent data loss              #
# --------------------------------------------------------------------------- #
def test_a_valid_document_validates():
    doc = Document.model_validate(minimal_doc())
    assert doc.title == "contract"


def test_an_unknown_key_is_rejected_not_ignored():
    with pytest.raises(Exception):
        Document.model_validate(minimal_doc(nonsense_key="silently dropped?"))


def test_an_unknown_object_key_is_rejected():
    bad = minimal_doc()
    bad["pages"][0]["layers"][0]["objects"][0]["colour"] = "#fff"   # not a field
    with pytest.raises(Exception):
        Document.model_validate(bad)


def test_the_p3_stroke_single_form_is_still_enforced():
    """The one breaking change of the 2.x line: inline-geometry `stroke` is dead.
    It has a bespoke, actionable error, and losing that error would silently
    resurrect the pre-P3 dialect."""
    bad = minimal_doc()
    bad["pages"][0]["layers"][0]["objects"].append(
        {"type": "line", "from": [0, 0], "to": [10, 10],
         "stroke": {"color": "#000", "width": 2}})
    with pytest.raises(Exception, match="paint-only"):
        Document.model_validate(bad)


# --------------------------------------------------------------------------- #
#  3. GENERATED — models and schema are one artifact in two forms              #
# --------------------------------------------------------------------------- #
def test_the_committed_schema_is_not_stale():
    assert check_schema(), "run `ff-schema` and commit the result"


def test_the_schema_ships_inside_the_package():
    """Package data, not a repo path — a non-Python consumer gets the contract
    from the wheel without a checkout."""
    assert SCHEMA_PATH.is_file()
    assert SCHEMA_PATH.parent.parent.name == "frameforge_api"


def test_the_schema_is_version_pinned_and_resolvable():
    schema = build_schema()
    assert schema["version"] == HEAD_VERSION
    assert schema["$id"] == (
        f"https://frameforge.dev/schema/{HEAD_VERSION}/frameforge-v2.schema.json")
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_build_is_pure_and_reproducible():
    assert json.dumps(build_schema(), sort_keys=True) == json.dumps(build_schema(), sort_keys=True)


def test_the_committed_schema_equals_a_fresh_build():
    assert json.dumps(load_schema(), sort_keys=True) == json.dumps(build_schema(), sort_keys=True)


def test_the_schema_covers_the_whole_model():
    """119 `$defs` today (105 at extraction). A collapse to a handful means the
    union stopped being walked — the schema would still be 'valid' and useless.

    The assertion stays a floor rather than an equality on purpose: the exact set
    is already pinned byte-for-byte by `tests/golden/schema.json`, and a second
    exact check here would just be a second thing to regenerate. The *narrated*
    figure is what drifts, and `golden_count_problems()` owns that.
    """
    assert len(build_schema()["$defs"]) >= 100


# --------------------------------------------------------------------------- #
#  4. TWO CLOCKS — the wheel and the document format release separately        #
# --------------------------------------------------------------------------- #
def test_the_package_version_and_the_contract_version_are_independent():
    """Two clocks, deliberately not synchronised.

    `__version__` is the wheel's release line; `HEAD_VERSION` is the FrameForge
    document-format revision the wheel carries. A packaging fix must not claim
    the document format changed, and a format change must not force a major bump
    of a package whose API did not move. Asserting they are EQUAL — which an
    earlier draft of this package did — silently welds the two release cycles
    together and makes one of them unshippable.
    """
    assert frameforge_api.__version__ != HEAD_VERSION, (
        "package and contract versions have collided; if that is genuinely "
        "intended, delete this test rather than letting it pass by accident")
    pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    declared = pyproject.split('\nversion = "', 1)[1].split('"', 1)[0]
    assert declared == frameforge_api.__version__, (
        f"pyproject version {declared!r} != __version__ {frameforge_api.__version__!r}")


def test_the_contract_version_is_reachable_under_both_names():
    """Document-level compatibility is decided against the CONTRACT version, so
    it must be obvious at the package root which number that is."""
    assert frameforge_api.CONTRACT_VERSION == HEAD_VERSION
    assert HEAD_VERSION.startswith("2."), "the v2 document line"


def test_the_schema_carries_the_contract_version_not_the_package_version():
    """The schema describes the document format; stamping the wheel's version
    into `$id` would make a packaging release look like a format change to every
    downstream validator."""
    schema = build_schema()
    assert schema["version"] == HEAD_VERSION
    assert frameforge_api.__version__ not in schema["$id"]


def test_public_surface_is_importable_from_the_package_root():
    for name in ("Document", "HEAD_VERSION", "SCHEMA_PATH", "build_schema",
                 "check_schema", "load_schema", "__version__"):
        assert hasattr(frameforge_api, name), name
