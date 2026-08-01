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
  * PINNED — the distribution version and the contract version are the same
    number, because shipping a wheel that claims a different revision than the
    models it carries is the first thing that would drift.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import frameforge_api
from frameforge_api import (
    HEAD_VERSION,
    SCHEMA_PATH,
    Document,
    build_schema,
    check_schema,
    load_schema,
)
from frameforge_api import model as model_module

MODEL_SRC = Path(model_module.__file__)


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
    engine and defeat the whole extraction."""
    tree = ast.parse(MODEL_SRC.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert not {m for m in imported if m.startswith("frameforge")}, (
        f"the contract grew a FrameForge dependency: {sorted(imported)}")
    assert imported <= {"__future__", "re", "typing", "pydantic"}, sorted(imported)


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
    """105 `$defs` at extraction time. A collapse to a handful means the union
    stopped being walked — the schema would still be 'valid' and useless."""
    assert len(build_schema()["$defs"]) >= 100


# --------------------------------------------------------------------------- #
#  4. PINNED — the wheel and the contract are the same revision                #
# --------------------------------------------------------------------------- #
def test_distribution_version_tracks_the_contract_version():
    assert frameforge_api.__version__ == HEAD_VERSION
    pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    declared = pyproject.split('version = "', 1)[1].split('"', 1)[0]
    assert declared == HEAD_VERSION, (
        f"pyproject version {declared!r} != contract HEAD_VERSION {HEAD_VERSION!r}")


def test_public_surface_is_importable_from_the_package_root():
    for name in ("Document", "HEAD_VERSION", "SCHEMA_PATH", "build_schema",
                 "check_schema", "load_schema", "__version__"):
        assert hasattr(frameforge_api, name), name
