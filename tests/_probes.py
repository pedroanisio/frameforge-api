#!/usr/bin/env python3
"""_probes.py — the documents whose verdicts are goldened.

A schema pins *shape*. It cannot pin the eleven `@model_validator`s that make up
the rest of the contract: the legacy-key normalisations (`offset`→`position`,
`object`→`ref`, `c1`→`control1`, `dash`→`stroke_dasharray`), the XOR rules
(`text` vs `spans`, `preset` vs `size`), the user-space geometry coherence rules
on gradients, and the P3 stroke rejection. Those are *behaviour*, and behaviour
is goldened by recording what each probe below is judged to be.

Each probe is named for the rule it exercises. Both verdicts are valuable: a
probe that must be ACCEPTED catches a refactor that drops a normalisation, and a
probe that must be REJECTED catches one that drops a guard. Losing a guard is
the more dangerous failure, because nothing downstream complains.

Kept deliberately free of the sibling monorepo: these run in CI with no checkout.
"""
from __future__ import annotations

from frameforge_api import HEAD_VERSION


def doc(*objects, **over) -> dict:
    """A minimal valid document wrapping `objects` on one page."""
    d = {
        "dsl": "FrameForge",
        "version": HEAD_VERSION,
        "title": "probe",
        "pages": [{
            "mode": "page",
            "id": "p1",
            "canvas": {"size": [400, 200], "units": "px"},
            "layers": [{"id": "main", "objects": list(objects) or [
                {"type": "text", "box": [20, 20, 360, 40], "text": "Hello"}]}],
        }],
    }
    d.update(over)
    return d


TEXT = {"type": "text", "box": [20, 20, 360, 40], "text": "Hello"}


def flow_doc(*flowables) -> dict:
    """A minimal valid document whose single page producer is a flowed section.

    A `FlowSection` carries no canvas of its own — it names a master under
    `defs.masters`, and R12 requires that key to resolve. Getting this shape
    wrong makes every flow probe fail for a reason that has nothing to do with
    the rule it was written to exercise.
    """
    return {
        "dsl": "FrameForge",
        "version": HEAD_VERSION,
        "title": "probe",
        "defs": {"masters": {"m1": {
            "canvas": {"size": [400, 200], "units": "px"},
            "regions": [{"id": "body", "box": [20, 20, 360, 160]}],
        }}},
        "pages": [{"mode": "flow", "id": "s1", "master": "m1", "story": list(flowables)}],
    }


#: (name, document). Order is irrelevant — the golden is keyed by name.
PROBES: list[tuple[str, dict]] = [
    # -- the baseline ------------------------------------------------------- #
    ("minimal_document", doc()),

    # -- CLOSED: unknown keys are errors, at every depth --------------------- #
    ("unknown_document_key", doc(nonsense_key="silently dropped?")),
    ("unknown_object_key", doc({**TEXT, "colour": "#fff"})),
    ("unknown_page_key", doc(**{"pages": [{
        "mode": "page", "id": "p1", "not_a_field": 1,
        "canvas": {"size": [400, 200], "units": "px"},
        "layers": [{"id": "main", "objects": [TEXT]}]}]})),

    # -- discriminated unions ------------------------------------------------ #
    ("unknown_object_type", doc({"type": "no_such_object", "box": [0, 0, 1, 1]})),
    ("missing_discriminator", doc({"box": [0, 0, 1, 1], "text": "no type"})),

    # -- ObjBase._stroke_paint_only (P3, the one breaking change of the 2.x line)
    ("p3_inline_stroke_geometry_rejected", doc(
        {"type": "line", "from": [0, 0], "to": [10, 10],
         "stroke": {"color": "#000", "width": 2}})),
    ("p3_stroke_as_paint_accepted", doc(
        {"type": "line", "from": [0, 0], "to": [10, 10], "stroke": "#000"})),

    # -- Text._one_of_text_spans (XOR) --------------------------------------- #
    ("text_with_both_text_and_spans", doc(
        {"type": "text", "box": [0, 0, 10, 10], "text": "a", "spans": ["b"]})),
    ("text_with_neither_text_nor_spans", doc({"type": "text", "box": [0, 0, 10, 10]})),
    ("text_with_spans_only_accepted", doc(
        {"type": "text", "box": [0, 0, 10, 10], "spans": ["a"]})),

    # -- GradientStop._accept_offset (legacy key normalisation) -------------- #
    ("gradient_stop_legacy_offset_accepted", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"kind": "linear", "stops": [
            {"color": "#000", "offset": 0}, {"color": "#fff", "offset": 1}]}})),
    ("gradient_stop_canonical_position_accepted", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"kind": "linear", "stops": [
            {"color": "#000", "position": "0%"}, {"color": "#fff", "position": "100%"}]}})),

    # -- Gradient._check_user_space_geometry (A1 coherence) ------------------ #
    ("gradient_line_on_radial_rejected", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"kind": "radial", "line": [[0, 0], [10, 10]],
                 "stops": [{"color": "#000"}, {"color": "#fff"}]}})),
    ("gradient_line_and_angle_rejected", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"kind": "linear", "line": [[0, 0], [10, 10]], "angle": 45,
                 "stops": [{"color": "#000"}, {"color": "#fff"}]}})),
    ("gradient_radius_on_linear_rejected", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"kind": "linear", "radius": 5,
                 "stops": [{"color": "#000"}, {"color": "#fff"}]}})),
    ("gradient_user_space_radial_accepted", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"kind": "radial", "at": [5, 5], "radius": 5,
                 "stops": [{"color": "#000"}, {"color": "#fff"}]}})),

    # -- Style._normalize_dash_array (legacy key + mutual exclusion) --------- #
    ("style_dash_alias_accepted", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "stroke_style": {"dash": "4 2"}})),
    ("style_dash_and_stroke_dasharray_rejected", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "stroke_style": {"dash": "4 2", "stroke_dasharray": "1 1"}})),

    # -- Curve._canonical_controls (alias agreement) ------------------------- #
    ("curve_short_control_keys_accepted", doc({
        "type": "curve", "from": [0, 0], "to": [10, 10], "c1": [2, 2], "c2": [8, 8]})),
    ("curve_contradictory_aliases_rejected", doc({
        "type": "curve", "from": [0, 0], "to": [10, 10],
        "c1": [2, 2], "control1": [3, 3]})),

    # -- ConnectorEndpoint._accept_object_key / _ref_or_point ---------------- #
    ("connector_legacy_object_key_accepted", doc(
        {**TEXT, "id": "a"}, {**TEXT, "id": "b"},
        {"type": "connector", "from": {"object": "a"}, "to": {"object": "b"}})),
    ("connector_endpoint_without_ref_or_point_rejected", doc(
        {"type": "connector", "from": {"side": "north"}, "to": {"point": [1, 1]}})),
    ("connector_point_endpoints_accepted", doc(
        {"type": "connector", "from": {"point": [0, 0]}, "to": {"point": [9, 9]}})),

    # -- ConnectorRoute._accept_type_key ------------------------------------- #
    ("connector_route_legacy_type_key_accepted", doc(
        {"type": "connector", "from": {"point": [0, 0]}, "to": {"point": [9, 9]},
         "route": {"type": "orthogonal"}})),

    # -- CanvasObject._preset_or_size (XOR) ---------------------------------- #
    ("canvas_with_both_preset_and_size", doc(**{"pages": [{
        "mode": "page", "id": "p1",
        "canvas": {"preset": "a4", "size": [400, 200]},
        "layers": [{"id": "main", "objects": [TEXT]}]}]})),
    ("canvas_with_neither_preset_nor_size", doc(**{"pages": [{
        "mode": "page", "id": "p1", "canvas": {"units": "px"},
        "layers": [{"id": "main", "objects": [TEXT]}]}]})),

    # -- ParagraphFlow._one_of (XOR, the flowable side) ---------------------- #
    ("flow_section_accepted", flow_doc({"type": "paragraph", "text": "a"})),
    ("paragraph_with_both_text_and_spans",
     flow_doc({"type": "paragraph", "text": "a", "spans": ["b"]})),
    ("paragraph_with_neither_text_nor_spans", flow_doc({"type": "paragraph"})),

    # -- pattern-gated scalars (Length / Angle / semver) --------------------- #
    # Exercised through `stroke_style`, which takes a real Style: a bare dict
    # cannot fall through to the StyleRef string branch, so the pattern is what
    # actually decides the verdict.
    ("bad_length_unit_rejected", doc({
        "type": "rect", "box": [0, 0, 10, 10], "stroke_style": {"stroke_width": "12ptx"}})),
    ("good_length_unit_accepted", doc({
        "type": "rect", "box": [0, 0, 10, 10], "stroke_style": {"stroke_width": "12pt"}})),
    ("bad_angle_unit_rejected", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"kind": "linear", "angle": "45degs",
                 "stops": [{"color": "#000"}, {"color": "#fff"}]}})),
    ("non_semver_document_version_rejected", doc(version="2.8")),

    # -- grammar sugar is NOT core profile ----------------------------------- #
    ("grammar_sugar_use_rejected", doc({"type": "use", "symbol": "badge", "box": [0, 0, 10, 10]})),

    # -- recursion still walks ------------------------------------------------ #
    ("nested_groups_accepted", doc({
        "type": "group", "box": [0, 0, 100, 100],
        "children": [{"type": "group", "box": [0, 0, 50, 50], "children": [TEXT]}]})),
]
