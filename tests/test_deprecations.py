#!/usr/bin/env python3
"""test_deprecations.py — deprecation is a contract, not a comment.

Three defects motivated this module, and each one has its own section below.

  1. **The escape hatch did not exist.** Four places in the contract told the
     reader to "run tooling/codemod.py" — three docstrings and the P3 stroke
     error message — and that file lives in the monorepo, not in this wheel.
     Someone who `pip install frameforge-api` was pointed at a path they do not
     have. `frameforge_api.deprecations` ships the migration itself, the way
     `frameforge_api.schema` ships schema generation.

  2. **Deprecation was invisible to machines.** The status lived only inside
     English `description` prose, so a codegen tool, an editor, or a model
     reading the JSON Schema had no signal at all. The three deprecated object
     types now carry the standard 2020-12 `deprecated` keyword, and the legacy
     keys — which are normalised by a `mode="before"` validator and therefore
     never appear in the schema as properties — are published as a registry
     under `x-frameforge-deprecations`.

  3. **`tokens.text_styles` was a shadowing hazard, not a deprecation.** Every
     other legacy form collapses to one representation at parse time. That one
     did not: two live namespaces over the same key space, with an implicit
     precedence rule, so the same name in both resolves to the one you did not
     intend and nothing reports it.

The load-bearing assertion in the whole file is
`test_migrating_any_deprecated_form_yields_a_document_that_validates`: a codemod
whose output does not validate is worse than no codemod, because it converts a
loud failure into a confident wrong answer.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import warnings
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from _probes import TEXT, doc

import frameforge_api
from frameforge_api import HEAD_VERSION, Document, build_schema
from frameforge_api.deprecations import (
    DEPRECATIONS,
    Deprecation,
    Finding,
    main,
    migrate,
    registry_json,
    scan,
)
from frameforge_api.model import GradientStop

REPO = Path(__file__).resolve().parents[1]


def valid(document) -> bool:
    try:
        Document.model_validate(document)
    except Exception:
        return False
    return True


def ids_of(findings) -> list[str]:
    return sorted(f.id for f in findings)


# --------------------------------------------------------------------------- #
#  The corpus of deprecated forms, one document per registry entry             #
# --------------------------------------------------------------------------- #
#: (deprecation id, document). Every registry entry must appear here — a test
#: below asserts the mapping is total, so adding a deprecation without a probe
#: document is itself a failure.
DEPRECATED_DOCS: list[tuple[str, dict]] = [
    ("deprecated-alias-circle", doc({
        "type": "circle", "id": "c", "center": [50, 50], "r": 20,
        "fill": "#d4145a", "stroke": "#000"})),
    ("deprecated-alias-polygon", doc({
        "type": "polygon", "id": "p", "points": [[0, 0], [10, 0], [5, 8]],
        "fill": "#eee"})),
    ("deprecated-alias-curve", doc({
        "type": "curve", "id": "q", "from": [0, 0], "to": [10, 10],
        "control1": [2, 8], "control2": [8, 2], "stroke": "#000"})),
    ("curve-control-shorthand", doc({
        "type": "curve", "id": "q", "from": [0, 0], "to": [10, 10],
        "c1": [2, 8], "c2": [8, 2]})),
    ("gradient-stop-offset", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"kind": "linear", "stops": [
            {"color": "#000", "offset": 0}, {"color": "#fff", "offset": 1}]}})),
    ("connector-endpoint-object", doc(
        {**TEXT, "id": "a"}, {**TEXT, "id": "b"},
        {"type": "connector", "from": {"object": "a"}, "to": {"object": "b"}})),
    ("connector-route-type", doc(
        {"type": "connector", "from": {"point": [0, 0]}, "to": {"point": [9, 9]},
         "route": {"type": "orthogonal"}})),
    ("style-dash-shorthand", doc({
        "type": "rect", "box": [0, 0, 10, 10], "stroke": "#000",
        "stroke_style": {"dash": "4 2"}})),
    ("tokens-text-styles", doc(
        TEXT, defs={"tokens": {"text_styles": {"body": {"font_size": 10}}}})),
    # -- the two removed forms: these do NOT validate at HEAD ---------------- #
    ("stroke-single-form", doc({
        "type": "line", "from": [0, 0], "to": [10, 10],
        "stroke": {"color": "#000", "width": 2, "dash": "4 2"}})),
    ("size-renamed", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "size": {"width": "fill", "height": "hug", "grow": 1}})),
]


# =========================================================================== #
#  1. THE REGISTRY — deprecation as data                                      #
# =========================================================================== #
def test_the_registry_is_not_empty_and_ids_are_unique():
    assert DEPRECATIONS, "the registry is the machine-readable half of the contract"
    ids = [d.id for d in DEPRECATIONS]
    assert len(ids) == len(set(ids)), f"duplicate ids: {sorted(ids)}"


def test_every_entry_names_a_replacement_a_fix_mode_and_a_reason():
    """A deprecation with no stated replacement is a complaint, not guidance."""
    for d in DEPRECATIONS:
        assert isinstance(d, Deprecation)
        assert d.replacement, f"{d.id} deprecates something and offers nothing"
        assert d.fix in ("automatic", "manual"), f"{d.id}: {d.fix}"
        assert d.kind in ("object-type", "legacy-key", "namespace", "removed-form")
        assert len(d.note) > 30, f"{d.id}: the note must say WHY, not restate the id"
        assert isinstance(d.valid_at_head, bool)


def test_removed_forms_are_the_ones_that_no_longer_validate():
    """`valid_at_head` is the field a consumer branches on, so it must be true.

    A `legacy-key` still parses (a validator normalises it); a `removed-form`
    does not (P3 rejects it outright). Getting this backwards would tell a
    caller a document is fine when the contract refuses it.
    """
    for dep_id, document in DEPRECATED_DOCS:
        dep = next(d for d in DEPRECATIONS if d.id == dep_id)
        assert valid(document) is dep.valid_at_head, (
            f"{dep_id}: registry says valid_at_head={dep.valid_at_head}, "
            f"the models disagree")


def test_every_registry_entry_has_a_probe_document():
    """A deprecation nobody wrote a document for is a deprecation nobody tested."""
    covered = {dep_id for dep_id, _ in DEPRECATED_DOCS}
    assert covered == {d.id for d in DEPRECATIONS}, (
        f"uncovered={sorted({d.id for d in DEPRECATIONS} - covered)} "
        f"unknown={sorted(covered - {d.id for d in DEPRECATIONS})}")


def test_the_registry_is_reachable_from_the_package_root():
    assert "DEPRECATIONS" in frameforge_api.__all__
    assert frameforge_api.DEPRECATIONS is DEPRECATIONS
    assert "migrate_document" in frameforge_api.__all__
    assert "scan_document" in frameforge_api.__all__


def test_the_registry_serialises_to_plain_json():
    """It ships inside the JSON Schema, so it has to survive `json.dumps`."""
    payload = registry_json()
    assert json.loads(json.dumps(payload)) == payload
    assert {e["id"] for e in payload} == {d.id for d in DEPRECATIONS}


# =========================================================================== #
#  2. THE SCHEMA — a machine can now see the deprecation                      #
# =========================================================================== #
@pytest.mark.parametrize("name", ["Circle", "Polygon", "Curve"])
def test_the_deprecated_object_types_carry_the_json_schema_keyword(name):
    """DEFECT 2: this was zero-for-three. `deprecated` is a standard 2020-12
    annotation; prose in `description` is not one."""
    assert build_schema()["$defs"][name].get("deprecated") is True


@pytest.mark.parametrize("name", ["Ellipse", "Polyline", "Path"])
def test_the_canonical_replacements_are_not_marked_deprecated(name):
    """The other half: marking everything is the same as marking nothing."""
    assert "deprecated" not in build_schema()["$defs"][name]


def test_the_superseded_token_namespace_is_marked_deprecated():
    tokens = build_schema()["$defs"]["Tokens"]["properties"]
    assert tokens["text_styles"].get("deprecated") is True
    assert "deprecated" not in tokens["styles"]


def test_the_schema_publishes_the_whole_registry():
    """The legacy KEYS never appear as schema properties — they are normalised
    away by a `mode="before"` validator — so `deprecated` has nothing to attach
    to. They are published as a registry instead, or they stay invisible."""
    published = build_schema()["x-frameforge-deprecations"]
    assert {e["id"] for e in published} == {d.id for d in DEPRECATIONS}
    for entry in published:
        assert entry["replacement"] and entry["note"]


def test_the_committed_schema_on_disk_carries_it_too():
    """The wheel ships the schema for consumers that never run Python; if the
    registry only exists in a fresh build, they never see it."""
    on_disk = json.loads(frameforge_api.SCHEMA_PATH.read_text(encoding="utf-8"))
    assert {e["id"] for e in on_disk["x-frameforge-deprecations"]} == {
        d.id for d in DEPRECATIONS}
    assert on_disk["$defs"]["Circle"].get("deprecated") is True


# =========================================================================== #
#  3. scan() — read-only detection                                            #
# =========================================================================== #
def test_a_canonical_document_produces_no_findings():
    assert scan(doc()) == []


@pytest.mark.parametrize("dep_id,document", DEPRECATED_DOCS, ids=[d for d, _ in DEPRECATED_DOCS])
def test_each_deprecated_form_is_detected_exactly_once(dep_id, document):
    found = [f for f in scan(document) if f.id == dep_id]
    assert found, f"{dep_id} not detected; scan saw {ids_of(scan(document))}"
    assert all(f.path.startswith("/") for f in found), "paths are RFC 6901 pointers"
    assert all(isinstance(f, Finding) for f in found)


def test_a_finding_points_at_the_node_that_carries_the_form():
    """A finding whose path is `/` is a finding you cannot act on."""
    document = doc({"type": "circle", "center": [5, 5], "r": 2})
    (finding,) = [f for f in scan(document) if f.id == "deprecated-alias-circle"]
    assert finding.path == "/pages/0/layers/0/objects/0"
    assert finding.deprecation.replacement == "ellipse"


def test_scan_never_mutates_the_document():
    document = DEPRECATED_DOCS[0][1]
    before = deepcopy(document)
    scan(document)
    assert document == before


def test_free_form_bags_are_not_scanned():
    """REGRESSION: `meta`, `data` and `params` are documented as free-form and
    are never interpreted as geometry. A codemod that rewrites keys inside them
    corrupts payloads it was never asked to read — and `meta.offset` beside a
    `meta.color` is an entirely ordinary annotation."""
    document = doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "meta": {"color": "#000", "offset": 0.5, "object": "a", "size": {"width": "fill"}}})
    assert scan(document) == []
    assert migrate(document).changed is False


def test_an_outer_ring_is_not_mistaken_for_a_pre_p3_stroke():
    """REGRESSION: `OuterRing` is `{color, width, gap, offset, dash, opacity}` —
    the exact shape of the removed inline stroke bundle. It is a legitimate,
    current field. Detecting the P3 form by shape alone rewrites it and silently
    deletes the ring; the rule is keyed on the `stroke` KEY for that reason."""
    document = doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "outer_ring": {"color": "#000", "width": 2, "dash": "4 2", "offset": 1}})
    assert valid(document)
    assert scan(document) == []
    assert migrate(document).document == document


def test_a_connector_endpoint_offset_is_not_a_gradient_stop():
    """REGRESSION: `ConnectorEndpoint.offset` is a current float field. Keying
    the gradient rule on the `offset` key alone renames it and the endpoint
    stops resolving."""
    document = doc(
        {**TEXT, "id": "a"},
        {"type": "connector", "from": {"ref": "a", "side": "north", "offset": 4},
         "to": {"point": [9, 9]}})
    assert valid(document)
    assert scan(document) == []


def test_a_typed_ink_stroke_is_not_a_pre_p3_bundle():
    """A CMYK stroke is a dict too. It carries no geometry keys, and the P3 rule
    must be gated on those rather than on `stroke` being a dict."""
    document = doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "stroke": {"space": "cmyk", "c": 0, "m": 0.9, "y": 0.8, "k": 0}})
    assert valid(document)
    assert scan(document) == []


# =========================================================================== #
#  4. THE SHADOWING HAZARD — defect 3                                         #
# =========================================================================== #
def test_a_name_in_both_style_namespaces_is_reported_as_shadowed():
    """DEFECT 3. `text_styles` and `styles` are both live `dict[str, Style]`
    maps and `text_styles` resolves first, so a name in both renders as the one
    the author probably did not mean — and nothing in the contract says so."""
    document = doc(TEXT, defs={"tokens": {
        "text_styles": {"body": {"font_size": 10}},
        "styles": {"body": {"font_size": 24}}}})
    assert valid(document), "still valid — this is a hazard, not an error"
    shadowed = [f for f in scan(document) if f.severity == "warning"]
    assert shadowed, f"collision not reported; saw {[ (f.id, f.severity) for f in scan(document)]}"
    assert "body" in shadowed[0].detail


def test_a_shadowing_collision_is_not_a_validation_error():
    """It cannot be one. `COMPATIBILITY = "backward"` promises that a document
    valid under an earlier 2.x stays valid at HEAD, and a collision was always
    valid. Tightening it here would break the guarantee this package makes —
    so it is a lint, deliberately, and the codemod is what resolves it."""
    document = doc(TEXT, defs={"tokens": {
        "text_styles": {"body": {"font_size": 10}},
        "styles": {"body": {"font_size": 24}}}})
    Document.model_validate(document)


def test_migrating_a_collision_keeps_the_winner_that_the_renderer_picks():
    """`text_styles` is resolved first, so merging must let it win. Merging the
    other way would silently restyle every block using the name."""
    document = doc(TEXT, defs={"tokens": {
        "text_styles": {"body": {"font_size": 10}, "note": {"font_size": 8}},
        "styles": {"body": {"font_size": 24}, "lead": {"font_size": 18}}}})
    tokens = migrate(document).document["defs"]["tokens"]
    assert "text_styles" not in tokens
    assert tokens["styles"] == {
        "body": {"font_size": 10},      # text_styles wins, as the renderer does
        "note": {"font_size": 8},
        "lead": {"font_size": 18},
    }


# =========================================================================== #
#  5. migrate() — the codemod, defect 1                                       #
# =========================================================================== #
@pytest.mark.parametrize("dep_id,document", DEPRECATED_DOCS, ids=[d for d, _ in DEPRECATED_DOCS])
def test_migrating_any_deprecated_form_yields_a_document_that_validates(dep_id, document):
    """THE load-bearing test. A codemod that emits an invalid document turns a
    loud failure into a confident wrong answer.

    It is also the test that catches a wrong target name: the monorepo's codemod
    maps a pre-P3 `stroke.opacity` onto `stroke_opacity`, which is not a `Style`
    field — and `Style` is `extra="forbid"`, so its output does not validate.
    """
    result = migrate(document)
    assert valid(result.document), (
        f"{dep_id}: migrated document is invalid\n"
        f"{json.dumps(result.document, indent=2)[:1200]}")


@pytest.mark.parametrize("dep_id,document", DEPRECATED_DOCS, ids=[d for d, _ in DEPRECATED_DOCS])
def test_migrating_removes_the_form_it_migrated(dep_id, document):
    remaining = [f.id for f in scan(migrate(document).document)]
    assert dep_id not in remaining, f"{dep_id} survived its own codemod: {remaining}"


@pytest.mark.parametrize("dep_id,document", DEPRECATED_DOCS, ids=[d for d, _ in DEPRECATED_DOCS])
def test_migrate_never_mutates_its_input(dep_id, document):
    """The corpus above is shared between tests; an in-place codemod would make
    every later test depend on execution order."""
    before = deepcopy(document)
    migrate(document)
    assert document == before


@pytest.mark.parametrize("dep_id,document", DEPRECATED_DOCS, ids=[d for d, _ in DEPRECATED_DOCS])
def test_migrate_is_idempotent(dep_id, document):
    once = migrate(document).document
    twice = migrate(once)
    assert twice.document == once
    assert twice.changed is False, f"second pass still changed things: {ids_of(twice.findings)}"


def test_migrating_a_canonical_document_changes_nothing():
    document = doc()
    result = migrate(document)
    assert result.changed is False
    assert result.findings == ()
    assert result.document == document


# ---- the individual rewrites, asserted on their output shape -------------- #
def obj(document, index=0):
    return document["pages"][0]["layers"][0]["objects"][index]


def test_circle_becomes_an_ellipse_with_equal_radii():
    document = doc({"type": "circle", "id": "c", "center": [50, 50], "r": 20,
                    "fill": "#d4145a", "stroke": "#000"})
    o = obj(migrate(document).document)
    assert o == {"type": "ellipse", "id": "c", "center": [50, 50], "rx": 20, "ry": 20,
                 "fill": "#d4145a", "stroke": "#000"}


def test_polygon_becomes_a_closed_polyline():
    document = doc({"type": "polygon", "id": "p", "points": [[0, 0], [10, 0], [5, 8]]})
    o = obj(migrate(document).document)
    assert o == {"type": "polyline", "id": "p", "points": [[0, 0], [10, 0], [5, 8]],
                 "closed": True}


def test_curve_becomes_a_single_segment_cubic_path():
    document = doc({"type": "curve", "id": "q", "from": [0, 0], "to": [10, 10],
                    "control1": [2, 8], "control2": [8, 2], "stroke": "#000"})
    o = obj(migrate(document).document)
    assert o == {"type": "path", "id": "q", "stroke": "#000",
                 "d": [["M", 0, 0], ["C", 2, 8, 8, 2, 10, 10]]}


def test_the_bezier_spelling_of_curve_migrates_too():
    document = doc({"type": "bezier", "from": [0, 0], "to": [4, 4], "c1": [1, 3], "c2": [3, 1]})
    assert obj(migrate(document).document)["d"] == [["M", 0, 0], ["C", 1, 3, 3, 1, 4, 4]]


def test_omitted_curve_controls_take_the_documented_defaults():
    """`control1` defaults to `from`, `control2` defaults to `control1` — stated
    in the field descriptions, so the codemod must reproduce exactly that or it
    changes the drawn shape."""
    document = doc({"type": "curve", "from": [0, 0], "to": [10, 10]})
    assert obj(migrate(document).document)["d"] == [["M", 0, 0], ["C", 0, 0, 0, 0, 10, 10]]


def test_a_unit_interval_gradient_offset_becomes_a_percentage():
    document = doc({"type": "rect", "box": [0, 0, 10, 10], "fill": {
        "kind": "linear", "stops": [
            {"color": "#000", "offset": 0}, {"color": "#888", "offset": 0.5},
            {"color": "#fff", "offset": 1}]}})
    stops = obj(migrate(document).document)["fill"]["stops"]
    assert [s["position"] for s in stops] == ["0%", "50%", "100%"]
    assert all("offset" not in s for s in stops)


def test_an_already_canonical_gradient_position_is_left_alone():
    document = doc({"type": "rect", "box": [0, 0, 10, 10], "fill": {
        "kind": "linear", "stops": [
            {"color": "#000", "position": "0%"}, {"color": "#fff", "position": "100%"}]}})
    assert migrate(document).changed is False


def test_a_connector_endpoint_object_key_becomes_ref():
    document = doc(
        {**TEXT, "id": "a"}, {**TEXT, "id": "b"},
        {"type": "connector", "from": {"object": "a"}, "to": {"object": "b", "side": "west"}})
    o = obj(migrate(document).document, 2)
    assert o["from"] == {"ref": "a"}
    assert o["to"] == {"ref": "b", "side": "west"}


def test_a_connector_route_type_key_becomes_kind():
    document = doc({"type": "connector", "from": {"point": [0, 0]}, "to": {"point": [9, 9]},
                    "route": {"type": "orthogonal", "points": [[4, 0]]}})
    assert obj(migrate(document).document)["route"] == {
        "kind": "orthogonal", "points": [[4, 0]]}


def test_a_style_dash_shorthand_becomes_stroke_dasharray():
    document = doc({"type": "rect", "box": [0, 0, 10, 10], "stroke": "#000",
                    "stroke_style": {"dash": "4 2", "stroke_width": 1}})
    assert obj(migrate(document).document)["stroke_style"] == {
        "stroke_dasharray": "4 2", "stroke_width": 1}


def test_a_dash_that_contradicts_stroke_dasharray_is_reported_not_silently_picked():
    """The model rejects the pair. Choosing one here would make the codemod's
    output validate while drawing a different dash than either spelling asked
    for — the single worst thing a migration can do."""
    document = doc({"type": "rect", "box": [0, 0, 10, 10],
                    "stroke_style": {"dash": "4 2", "stroke_dasharray": "1 1"}})
    assert not valid(document)
    result = migrate(document)
    conflict = [f for f in result.findings if f.severity == "error"]
    assert conflict, f"conflict not reported: {[(f.id, f.severity) for f in result.findings]}"
    assert result.document["pages"][0]["layers"][0]["objects"][0]["stroke_style"] == {
        "dash": "4 2", "stroke_dasharray": "1 1"}, "left untouched for the author to resolve"


# ---- the two removed forms ------------------------------------------------ #
def test_a_pre_p3_stroke_bundle_splits_into_paint_and_geometry():
    document = doc({"type": "line", "from": [0, 0], "to": [10, 10], "stroke": {
        "color": "#d5d0c6", "width": 2, "dash": "4 2", "linecap": "round",
        "linejoin": "bevel", "opacity": 0.5}})
    o = obj(migrate(document).document)
    assert o["stroke"] == "#d5d0c6"
    assert o["stroke_style"] == {
        "stroke_width": 2, "stroke_dasharray": "4 2", "stroke_linecap": "round",
        "stroke_linejoin": "bevel", "opacity": 0.5}


def test_a_pre_p3_split_merges_into_an_existing_stroke_style_without_clobbering():
    document = doc({"type": "line", "from": [0, 0], "to": [10, 10],
                    "stroke": {"color": "#000", "width": 2},
                    "stroke_style": {"stroke_width": 9, "stroke_linecap": "butt"}})
    o = obj(migrate(document).document)
    assert o["stroke_style"] == {"stroke_width": 9, "stroke_linecap": "butt"}, (
        "an explicit stroke_style is authoritative over the legacy bundle")


def test_a_pre_p3_bundle_beside_a_named_stroke_style_is_reported_not_merged():
    """A `stroke_style` string names a SHARED token. Editing it would restyle
    every other object that references it, so the codemod refuses and says so."""
    document = doc({"type": "line", "from": [0, 0], "to": [10, 10],
                    "stroke": {"color": "#000", "width": 2},
                    "stroke_style": "hairline"})
    result = migrate(document)
    manual = [f for f in result.findings if f.severity == "error"]
    assert manual, "silently dropping the geometry is not an option"


def test_a_dict_valued_size_is_renamed_to_sizing():
    """Unambiguous: every current `size` field in the contract is a scalar or a
    list (`Icon.size` numeric, `CanvasObject.size` a pair, `Style.size` a
    Length). Only the pre-P4 content-sizing key was ever an object."""
    document = doc({"type": "rect", "box": [0, 0, 10, 10],
                    "size": {"width": "fill", "height": "hug", "grow": 1}})
    o = obj(migrate(document).document)
    assert "size" not in o
    assert o["sizing"] == {"width": "fill", "height": "hug", "grow": 1}


def test_a_numeric_icon_size_is_left_alone():
    """REGRESSION: `Icon.size` is the reason `sizing` was renamed in the first
    place. Renaming it back would break every icon in the corpus."""
    document = doc({"type": "icon", "box": [0, 0, 10, 10], "glyph": "star", "size": 12})
    assert valid(document)
    assert scan(document) == []
    assert migrate(document).document == document


def test_a_canvas_size_pair_is_left_alone():
    assert migrate(doc()).document == doc()
    assert scan(doc()) == []


# =========================================================================== #
#  6. THE CLI — `ff-codemod`                                                  #
# =========================================================================== #
def write_doc(tmp_path: Path, document: dict, name: str = "d.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_the_cli_reports_findings_and_exits_nonzero(tmp_path, capsys):
    path = write_doc(tmp_path, DEPRECATED_DOCS[0][1])
    assert main([str(path)]) == 1
    assert "deprecated-alias-circle" in capsys.readouterr().out


def test_the_cli_exits_zero_on_a_clean_document(tmp_path, capsys):
    assert main([str(write_doc(tmp_path, doc()))]) == 0
    assert "clean" in capsys.readouterr().out.lower()


def test_linting_writes_nothing(tmp_path):
    path = write_doc(tmp_path, DEPRECATED_DOCS[0][1])
    before = path.read_bytes()
    main([str(path)])
    assert path.read_bytes() == before, "the default mode is read-only"


def test_write_migrates_in_place_and_the_result_lints_clean(tmp_path):
    path = write_doc(tmp_path, DEPRECATED_DOCS[0][1])
    assert main(["--write", str(path)]) == 0
    migrated = json.loads(path.read_text(encoding="utf-8"))
    assert valid(migrated)
    assert main([str(path)]) == 0


def test_stdout_prints_the_migrated_document_without_touching_disk(tmp_path, capsys):
    path = write_doc(tmp_path, DEPRECATED_DOCS[0][1])
    before = path.read_bytes()
    assert main(["--stdout", str(path)]) == 0
    assert valid(json.loads(capsys.readouterr().out))
    assert path.read_bytes() == before


def test_json_output_is_machine_readable(tmp_path, capsys):
    path = write_doc(tmp_path, DEPRECATED_DOCS[0][1])
    main(["--json", str(path)])
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"][0]["id"] == "deprecated-alias-circle"
    assert payload["findings"][0]["path"].startswith("/")
    assert payload["findings"][0]["severity"] in ("info", "warning", "error")


def test_list_prints_the_registry(capsys):
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    for d in DEPRECATIONS:
        assert d.id in out


def test_an_unreadable_document_exits_two(tmp_path):
    assert main([str(tmp_path / "missing.json")]) == 2


def test_a_malformed_document_exits_two(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert main([str(path)]) == 2


def test_the_cli_handles_several_documents_and_returns_the_worst_status(tmp_path):
    clean = write_doc(tmp_path, doc(), "clean.json")
    dirty = write_doc(tmp_path, DEPRECATED_DOCS[0][1], "dirty.json")
    assert main([str(clean)]) == 0
    assert main([str(clean), str(dirty)]) == 1


def test_yaml_documents_round_trip_when_pyyaml_is_present(tmp_path):
    yaml = pytest.importorskip("yaml")
    path = tmp_path / "d.fg.yaml"
    path.write_text(yaml.safe_dump(DEPRECATED_DOCS[0][1]), encoding="utf-8")
    assert main(["--write", str(path)]) == 0
    assert valid(yaml.safe_load(path.read_text(encoding="utf-8")))


def test_the_console_script_is_installed():
    """The whole defect was a migration path nobody could run. An importable
    function that no entry point exposes would only half-fix it."""
    out = subprocess.run([sys.executable, "-m", "frameforge_api.deprecations", "--list"],
                         capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stderr
    assert "deprecated-alias-circle" in out.stdout


# =========================================================================== #
#  7. THE DANGLING POINTER — defect 1, stated as a regression                 #
# =========================================================================== #
def _descriptions(node, path="") -> list[tuple[str, str]]:
    """Every `description` string in the schema, with its location."""
    out: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "description" and isinstance(value, str):
                out.append((path, value))
            else:
                out += _descriptions(value, f"{path}/{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            out += _descriptions(value, f"{path}/{i}")
    return out


def test_no_published_description_points_at_a_file_the_package_does_not_ship():
    """REGRESSION: three model docstrings and the P3 error message told the
    reader to run `tooling/codemod.py`, which lives in the frameforge monorepo.
    Those strings are not internal notes — they are copied verbatim into the
    JSON Schema, which is the surface a wheel user, an editor and a codegen tool
    actually read. Pointing all of them at a path the wheel does not contain is
    worse than saying nothing.

    Scoped to published descriptions on purpose: the *history* of the defect is
    still worth recording in source comments, and this must not forbid that.
    """
    schema = build_schema()
    dangling = [(where, text) for where, text in _descriptions(schema)
                if "tooling/codemod" in text]
    assert not dangling, f"published descriptions naming an unshipped file: {dangling}"

    unnamed = [(where, text) for where, text in _descriptions(schema)
               if "codemod" in text and "ff-codemod" not in text]
    assert not unnamed, (
        f"a description mentions a codemod without naming the shipped one: {unnamed}")


def test_the_p3_error_message_names_the_shipped_tool():
    document = doc({"type": "line", "from": [0, 0], "to": [1, 1],
                    "stroke": {"color": "#000", "width": 2}})
    with pytest.raises(Exception) as exc:
        Document.model_validate(document)
    assert "ff-codemod" in str(exc.value)


def test_every_deprecation_is_documented_for_a_human_too():
    """The registry is for machines; MIGRATION.md is for the person holding the
    document. A deprecation in one and not the other is half-shipped."""
    prose = (REPO / "MIGRATION.md").read_text(encoding="utf-8")
    missing = [d.id for d in DEPRECATIONS if d.id not in prose]
    assert not missing, f"undocumented in MIGRATION.md: {missing}"


# =========================================================================== #
#  8. INTEGRATION — the corpus the codemod was written for                    #
# =========================================================================== #
BEFORE = REPO / "examples" / "legacy-shortcuts.before.json"
AFTER = REPO / "examples" / "legacy-shortcuts.after.json"


def test_the_worked_example_is_a_before_and_after_pair():
    """The migrated half is validated on every run by `test_examples.py`, so it
    cannot rot into a confident wrong answer; the legacy half is deliberately
    NOT valid, because two of the forms it demonstrates were removed."""
    legacy = json.loads(BEFORE.read_text(encoding="utf-8"))
    migrated = json.loads(AFTER.read_text(encoding="utf-8"))

    assert not valid(legacy), "the 'before' example must actually be pre-migration"
    assert valid(migrated)

    result = migrate(legacy)
    assert result.document == migrated, "the committed pair drifted from the codemod"
    assert result.manual == (), "the worked example is the fully-automatic path"
    assert scan(migrated) == []


def test_the_worked_example_demonstrates_every_deprecated_form():
    """One document per deprecation would be eleven files nobody reads. One
    document showing all eleven is a reference — as long as it stays complete."""
    legacy = json.loads(BEFORE.read_text(encoding="utf-8"))
    assert {f.id for f in scan(legacy)} == {d.id for d in DEPRECATIONS}


# --------------------------------------------------------------------------- #
#  The real corpus: `b1/`, the frozen pre-P3 oracle                            #
# --------------------------------------------------------------------------- #
MONOREPO = Path(
    os.environ.get("FRAMEFORGE_REPO", REPO.parent / "frameforge"))
ORACLE = MONOREPO / "tests" / "fixtures" / "b1"

needs_oracle = pytest.mark.skipif(
    not ORACLE.is_dir(),
    reason=f"pre-P3 oracle corpus not found at {ORACLE} (set FRAMEFORGE_REPO)")


def _oracle_docs() -> list[Path]:
    return sorted(ORACLE.glob("*.fg.json")) if ORACLE.is_dir() else []


@needs_oracle
def test_the_pre_p3_oracle_corpus_is_the_reason_this_codemod_exists():
    """`b1/` is excluded from every other suite in this package with the words
    "kept as codemod *input*". Nothing had ever run a codemod over it from here,
    because there was no codemod here to run.

    Every one of those documents must come out of `migrate()` valid at HEAD.
    Hand-written probes cover the forms someone thought of; this corpus covers
    the ones a real deck actually contains — 1,008 inline stroke bundles among
    them.
    """
    docs = _oracle_docs()
    assert docs, f"no oracle documents under {ORACLE}"

    failures, checked, rejected, found = [], 0, 0, 0
    for path in docs:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("dsl") != "FrameForge":
            continue
        checked += 1
        if not valid(data):
            rejected += 1
        result = migrate(data)
        found += len(result.findings)
        try:
            Document.model_validate(result.document)
        except Exception as exc:
            failures.append(f"{path.name}: {str(exc).splitlines()[0]} "
                            f"| manual={[f.id for f in result.manual]}")

    assert not failures, (
        f"{len(failures)} of {checked} oracle document(s) do not validate after "
        f"migration:\n  " + "\n  ".join(failures[:6]))
    assert checked >= 8, f"only {checked} oracle documents checked"
    # Measured at the time this was written: 9 documents, 4 of them rejected at
    # HEAD outright, 552 deprecated forms between them (544 pre-P3 stroke
    # bundles, 8 legacy token namespaces). The corpus is the evidence; if it
    # thins out, so does the evidence.
    assert rejected >= 4, f"only {rejected} of {checked} oracle documents are rejected at HEAD"
    assert found >= 500, f"only {found} deprecated forms found across the oracle corpus"


@needs_oracle
@pytest.mark.parametrize("path", _oracle_docs(), ids=lambda p: p.stem)
def test_migrating_an_oracle_document_is_idempotent(path: Path):
    """Run twice, get the same thing. A codemod that keeps finding work on its
    own output cannot be wired into a pre-commit hook or a CI gate."""
    once = migrate(json.loads(path.read_text(encoding="utf-8"))).document
    assert migrate(once).document == once


# =========================================================================== #
#  9. EDGE CASES                                                              #
# =========================================================================== #
def test_the_deprecated_field_marker_does_not_turn_ordinary_use_into_an_error():
    """`Field(deprecated=True)` makes pydantic warn on ATTRIBUTE ACCESS. A
    consumer running under `-W error::DeprecationWarning` — which CI often does
    — would then crash on a document the contract still promises to accept.
    Validation and dumping must stay silent; only reading `.text_styles` warns.
    """
    document = doc(TEXT, defs={"tokens": {"text_styles": {"body": {"font_size": 10}}}})
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        parsed = Document.model_validate(document)
        parsed.model_dump(exclude_none=True)

    with pytest.warns(DeprecationWarning):
        _ = parsed.defs.tokens.text_styles


def test_deprecated_forms_nested_in_a_group_subtree_are_migrated():
    """Objects nest arbitrarily. A codemod that only walks the top level of a
    layer silently skips every shape inside a group."""
    document = doc({
        "type": "group", "box": [0, 0, 100, 100], "children": [
            {"type": "group", "box": [0, 0, 50, 50], "children": [
                {"type": "circle", "center": [5, 5], "r": 2}]}]})
    result = migrate(document)
    inner = obj(result.document)["children"][0]["children"][0]
    assert inner["type"] == "ellipse" and inner["rx"] == inner["ry"] == 2
    assert result.findings[0].path == (
        "/pages/0/layers/0/objects/0/children/0/children/0")


def test_deprecated_forms_inside_a_flowed_story_are_migrated():
    """Flow sections are a second object tree with a different shape. Walking
    only `pages[].layers[].objects[]` misses a whole authoring mode."""
    document = {
        "dsl": "FrameForge", "version": HEAD_VERSION, "title": "flow",
        "defs": {"masters": {"m1": {
            "canvas": {"size": [400, 200], "units": "px"},
            "regions": [{"id": "body", "box": [20, 20, 360, 160]}]}}},
        "pages": [{"mode": "flow", "id": "s1", "master": "m1", "story": [
            {"type": "figure", "object": {"type": "circle", "center": [5, 5], "r": 2}}]}],
    }
    result = migrate(document)
    assert result.document["pages"][0]["story"][0]["object"]["type"] == "ellipse"
    assert valid(result.document)


def test_deprecated_forms_inside_a_page_master_are_migrated():
    """`defs.masters` carries background objects that never appear on a page."""
    document = doc(TEXT, defs={"masters": {"m1": {
        "canvas": {"size": [400, 200], "units": "px"},
        "background": [{"type": "polygon", "points": [[0, 0], [1, 0], [0, 1]]}]}}})
    migrated = migrate(document).document
    assert migrated["defs"]["masters"]["m1"]["background"][0] == {
        "type": "polyline", "points": [[0, 0], [1, 0], [0, 1]], "closed": True}


def test_a_document_with_no_pages_at_all_is_handled():
    assert migrate({"dsl": "FrameForge"}).changed is False
    assert scan({}) == []


def test_json_pointer_tokens_are_escaped():
    """RFC 6901: a key containing `/` or `~` must be escaped, or the pointer
    silently addresses a different node."""
    document = doc(TEXT, defs={"tokens": {"styles": {
        "brand/dark": {"dash": "4 2"}, "a~b": {"dash": "1 1"}}}})
    paths = {f.path for f in scan(document)}
    assert "/defs/tokens/styles/brand~1dark" in paths
    assert "/defs/tokens/styles/a~0b" in paths


def test_a_gradient_offset_already_written_as_a_percentage_survives():
    """Only the 0..1 unit-interval spelling is rescaled. Rescaling `"50%"` would
    turn it into `"5000%"`."""
    document = doc({"type": "rect", "box": [0, 0, 10, 10], "fill": {
        "kind": "linear", "stops": [
            {"color": "#000", "offset": "0%"}, {"color": "#fff", "offset": "100%"}]}})
    stops = obj(migrate(document).document)["fill"]["stops"]
    assert [s["position"] for s in stops] == ["0%", "100%"]


def test_a_gradient_offset_above_one_is_carried_through_unscaled():
    """A value over 1 is already a length, not a fraction — mirrors
    `GradientStop._accept_offset` exactly, because a codemod that disagrees with
    the validator produces a different gradient than the one that was authored."""
    document = doc({"type": "rect", "box": [0, 0, 10, 10], "fill": {
        "kind": "linear", "stops": [
            {"color": "#000", "offset": "0%"}, {"color": "#fff", "offset": "12pt"}]}})
    stops = obj(migrate(document).document)["fill"]["stops"]
    assert stops[1]["position"] == "12pt"


def test_a_boolean_offset_is_migrated_the_way_the_validator_reads_it():
    """REGRESSION: this test used to assert the opposite, and pinned a bug.

    `isinstance(True, int)` is True in Python, so `GradientStop._accept_offset`
    normalises `offset: true` to `"100%"` — the far end of the gradient line.
    The codemod excluded bools and passed `true` through, and `position: true`
    validates as a *Length* of 1 unit (`base.py`: "bare numbers are pt/px,
    treated 1:1") — the near end. Both documents validated, so no gate fired,
    and `ff-codemod --write` moved the stop from one end to the other.

    The old test called `"100%"` "a nonsense value invented out of a nonsense
    one". That is a fair reading of `offset: true` — but the codemod does not get
    to hold a different opinion from the validator, because its entire contract
    is that migrating changes spelling and not appearance. Rejecting the form
    outright is unavailable: `COMPATIBILITY` is `backward`.
    """
    document = doc({"type": "rect", "box": [0, 0, 10, 10], "fill": {
        "kind": "linear", "stops": [{"color": "#000", "offset": True}]}})
    assert obj(migrate(document).document)["fill"]["stops"][0]["position"] == "100%"


#: Raw `offset` values spanning every branch of the normalisation: below/at/above
#: the unit interval, both bools, both string spellings, a unit-bearing length
#: and a negative. The bools are the pair that diverged.
_OFFSETS = [0, 0.5, 1, 1.5, True, False, "0%", "50%", "12pt", -0.2, 0.001, 2]


@pytest.mark.parametrize("raw", _OFFSETS, ids=lambda v: f"{type(v).__name__}:{v}")
def test_the_codemod_resolves_identically_to_the_validator(raw):
    """The real contract: migrating changes spelling, never appearance.

    The comment on `_gradient_stop` claims it "mirrors `_accept_offset` exactly".
    Asserting that the *output validates* — which the suite already did — is much
    weaker than asserting the two agree, and it is precisely the gap the boolean
    divergence lived in for three contract revisions.

    So compare what a renderer would actually receive: the resolved `position`
    of the raw document, and the resolved `position` of the migrated one.
    """
    raw_stop = {"color": "#000", "offset": raw}
    document = doc({"type": "rect", "box": [0, 0, 10, 10], "fill": {
        "kind": "linear", "stops": [raw_stop]}})
    migrated_stop = obj(migrate(document).document)["fill"]["stops"][0]

    direct = GradientStop.model_validate(raw_stop).position
    through_codemod = GradientStop.model_validate(migrated_stop).position

    assert direct == through_codemod, (
        f"offset={raw!r}: the validator resolves it to {direct!r}, but the "
        f"codemod emits {migrated_stop!r} which resolves to {through_codemod!r}. "
        f"Migrating must not change what is drawn.")
    assert type(direct) is type(through_codemod), (
        f"offset={raw!r}: same value, different type "
        f"({type(direct).__name__} vs {type(through_codemod).__name__}) — a "
        f"Length and a Percentage are not interchangeable downstream.")


#: Deprecation kinds whose migration is a pure RESPELLING: the same object, the
#: same type, written the canonical way. For these the resolved document must be
#: identical before and after — that is the whole promise of the codemod.
#:
#: `object-type` is excluded because those three entries (`circle` -> `ellipse`,
#: `polygon` -> `path`, `curve` -> `path`) deliberately change `type` and
#: redistribute geometry across differently-named fields; a resolved-equality
#: assertion would be asserting the migration does not happen. `removed-form`
#: and `namespace` are excluded for the same reason — they restructure by design.
_RESPELLING_KINDS = {"legacy-key"}


#: One object per respelling form, in the spelling `examples/legacy-shortcuts.before.json`
#: uses. Built here rather than read from that file because every committed
#: document mixes respellings with type-changing forms, and mixing them makes
#: resolved-equality untestable.
_RESPELLING_OBJECTS = [
    # gradient-stop-offset — the form that diverged.
    {"type": "rect", "id": "grad", "box": [0, 0, 100, 100],
     "fill": {"kind": "linear", "angle": 90, "stops": [
         {"color": "#ffffff", "offset": 0},
         {"color": "#eeeae1", "offset": 0.5},
         {"color": "#d5d0c6", "offset": 1}]}},
    # style-dash-shorthand
    {"type": "text", "id": "caption", "box": [220, 130, 180, 40],
     "text": "Deprecated, not removed.",
     "stroke_style": {"dash": "2 2", "stroke_width": 0.5}},
    # connector-endpoint-object + connector-route-type
    {"type": "connector", "id": "link",
     "from": {"object": "grad", "side": "east"},
     "to": {"object": "caption", "side": "west"},
     "route": {"type": "orthogonal"}, "stroke": "#1d1d1b"},
]


def _respelling_document() -> dict:
    return doc(*_RESPELLING_OBJECTS)


def test_the_respelling_corpus_covers_every_legacy_key_deprecation():
    """The equivalence test below is only as good as what it exercises.

    If a `legacy-key` entry is added to the registry and no object here carries
    it, the equivalence test would pass while covering nothing — the exact
    failure mode this whole finding is about.
    """
    found = {f.id for f in scan(_respelling_document())}
    expected = {d.id for d in DEPRECATIONS if d.kind in _RESPELLING_KINDS}
    # `curve-control-shorthand` only ever occurs inside a `curve`, which is
    # itself an `object-type` deprecation, so it cannot appear in a
    # respelling-only document. It is covered by the type-changing test instead.
    expected -= {"curve-control-shorthand"}
    assert expected <= found, (
        f"respelling corpus does not exercise {sorted(expected - found)}; "
        f"add an object to _RESPELLING_OBJECTS carrying that form")


def test_respelling_a_valid_document_does_not_change_what_it_resolves_to():
    """The same equivalence as the offset table, one level up: whole documents.

    A per-field property test only covers the fields someone parameterised.
    This one asserts migration is appearance-preserving across the entire model
    — every field, every nested object, at once.

    It is the assertion that would have caught the boolean-offset divergence
    without anyone thinking to test booleans.
    """
    data = _respelling_document()
    assert scan(data), "the respelling document carries no deprecated forms"

    before = Document.model_validate(data)
    after = Document.model_validate(migrate(data).document)
    assert before.model_dump(mode="json") == after.model_dump(mode="json"), (
        "respelling changed the resolved document")


def test_a_type_changing_migration_still_produces_a_valid_document():
    """The `object-type` / `removed-form` / `namespace` entries, which the
    equivalence test above deliberately excludes, are not left unguarded.

    They restructure on purpose — `circle` becomes an `ellipse`, `curve` becomes
    a `path` — so resolved equality is the wrong lens. What must hold is that the
    result validates and that migrating twice changes nothing more.
    """
    corpus = sorted((REPO / "tests" / "compat").glob("*.json"))
    corpus += [REPO / "examples" / "legacy-shortcuts.before.json"]

    checked = 0
    for path in corpus:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not scan(data):
            continue
        once = migrate(data).document
        Document.model_validate(once)
        twice = migrate(once).document
        assert once == twice, f"{path.name}: migration is not idempotent"
        assert not scan(once), f"{path.name}: findings survive their own migration"
        checked += 1
    assert checked, "no type-changing documents exercised"


def test_a_radial_and_a_conic_gradient_are_migrated_too():
    """The rule keys on the gradient vocabulary, so all three kinds or none."""
    for kind in ("radial", "conic"):
        document = doc({"type": "rect", "box": [0, 0, 10, 10], "fill": {
            "kind": kind, "stops": [{"color": "#000", "offset": 0.25}]}})
        assert obj(migrate(document).document)["fill"]["stops"][0]["position"] == "25%"


def test_a_geometry_only_stroke_bundle_loses_the_key_rather_than_keeping_a_dict():
    """With no `color` there is no paint to keep, and leaving the dict behind
    would fail validation for exactly the reason it does today."""
    document = doc({"type": "line", "from": [0, 0], "to": [1, 1],
                    "stroke": {"width": 2, "linejoin": "round"}})
    o = obj(migrate(document).document)
    assert "stroke" not in o
    assert o["stroke_style"] == {"stroke_width": 2, "stroke_linejoin": "round"}
    assert valid(migrate(document).document)


def test_text_styles_merges_when_there_is_no_styles_map_at_all():
    document = doc(TEXT, defs={"tokens": {"text_styles": {"body": {"font_size": 10}}}})
    tokens = migrate(document).document["defs"]["tokens"]
    assert tokens == {"styles": {"body": {"font_size": 10}}}


def test_an_empty_text_styles_map_is_dropped_without_inventing_a_styles_map():
    """The deprecated key with nothing in it is still the deprecated key, so it
    is reported and removed — but replacing an empty legacy namespace with an
    empty current one is not progress, so no `styles` map is conjured."""
    document = doc(TEXT, defs={"tokens": {"text_styles": {}}})
    result = migrate(document)
    (finding,) = [f for f in result.findings if f.id == "tokens-text-styles"]
    assert finding.severity == "info"
    assert result.document["defs"]["tokens"] == {}


def test_an_empty_text_styles_map_beside_a_real_one_leaves_it_alone():
    document = doc(TEXT, defs={"tokens": {"text_styles": {}, "styles": {"a": {"font_size": 9}}}})
    assert migrate(document).document["defs"]["tokens"] == {
        "styles": {"a": {"font_size": 9}}}
