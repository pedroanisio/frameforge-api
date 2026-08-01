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


def doc(*objects, defs=None, **over) -> dict:
    """A minimal valid document wrapping `objects` on one page."""
    if defs is not None:
        over.setdefault("defs", defs)
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

    # ======================================================================== #
    #  2.9.0 — print colour, book geometry, CJKV annotation, render output     #
    # ======================================================================== #
    # These are goldened for the same reason as everything above: the schema
    # proves the SHAPE of the new models, and only a verdict proves the guards
    # around them still fire.

    # -- typed colour --------------------------------------------------------- #
    ("cmyk_fill_accepted", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"space": "cmyk", "c": 0, "m": 0.9, "y": 0.8, "k": 0}})),
    ("cmyk_component_above_one_rejected", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"space": "cmyk", "c": 0, "m": 90, "y": 0, "k": 0}})),
    ("cmyk_missing_a_separation_rejected", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"space": "cmyk", "c": 0, "m": 0.5, "y": 0}})),
    ("spot_ink_accepted", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"space": "spot", "name": "PANTONE 283 C", "system": "pantone", "tint": 0.4}})),
    ("spot_ink_without_name_rejected", doc({
        "type": "rect", "box": [0, 0, 10, 10], "fill": {"space": "spot", "tint": 0.4}})),
    ("unknown_color_space_rejected", doc({
        "type": "rect", "box": [0, 0, 10, 10], "fill": {"space": "hsv", "h": 1}})),
    ("icc_color_with_declared_profile_accepted", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "fill": {"space": "icc", "profile": "fogra39", "components": [0.1, 0.8, 0.7, 0]}},
        defs={"color_profiles": {"fogra39": {"space": "cmyk"}}})),
    ("color_profile_without_space_rejected",
     doc(TEXT, defs={"color_profiles": {"fogra39": {"src": "x.icc"}}})),
    ("overprint_accepted", doc({
        "type": "rect", "box": [0, 0, 10, 10],
        "style": {"overprint": "both", "overprint_mode": "nonzero-cmyk"}})),
    ("unknown_overprint_rejected", doc({
        "type": "rect", "box": [0, 0, 10, 10], "style": {"overprint": "sometimes"}})),
    ("hex_color_still_accepted", doc({
        "type": "rect", "box": [0, 0, 10, 10], "fill": "#d4145a"})),

    # -- book geometry -------------------------------------------------------- #
    ("spine_relative_margin_accepted", doc(**{"pages": [{
        "mode": "page", "id": "p1", "side": "verso",
        "canvas": {"preset": "book-6x9", "margin": {
            "top": "18mm", "bottom": "22mm", "inside": "20mm",
            "outside": "14mm", "gutter": "5mm"}},
        "layers": [{"id": "l", "objects": [TEXT]}]}]})),
    ("mixed_margin_vocabularies_rejected", doc(**{"pages": [{
        "mode": "page", "id": "p1",
        "canvas": {"preset": "book-6x9", "margin": {"left": "20mm", "inside": "20mm"}},
        "layers": [{"id": "l", "objects": [TEXT]}]}]})),
    ("box_margin_still_accepted", doc(**{"pages": [{
        "mode": "page", "id": "p1",
        "canvas": {"size": [400, 200], "units": "px", "margin": [10, 10, 10, 10]},
        "layers": [{"id": "l", "objects": [TEXT]}]}]})),
    ("spread_canvas_accepted", doc(**{"pages": [{
        "mode": "page", "id": "p1",
        "canvas": {"preset": "book-6x9", "spread": True},
        "layers": [{"id": "l", "objects": [TEXT]}]}]})),
    ("unknown_page_side_rejected", doc(**{"pages": [{
        "mode": "page", "id": "p1", "side": "left",
        "canvas": {"preset": "book-6x9"},
        "layers": [{"id": "l", "objects": [TEXT]}]}]})),

    # -- CJKV annotation ------------------------------------------------------ #
    ("ruby_group_annotation_accepted", doc({
        "type": "text", "box": [0, 0, 100, 20],
        "spans": [{"kind": "ruby", "base": "漢字", "text": "かんじ", "position": "over"}]})),
    ("ruby_mono_annotation_accepted", doc({
        "type": "text", "box": [0, 0, 100, 20],
        "spans": [{"kind": "ruby", "base": "漢字", "text": ["かん", "じ"]}]})),
    ("ruby_without_annotation_rejected", doc({
        "type": "text", "box": [0, 0, 100, 20],
        "spans": [{"kind": "ruby", "base": "漢字"}]})),
    ("unknown_ruby_position_rejected", doc({
        "type": "text", "box": [0, 0, 100, 20],
        "spans": [{"kind": "ruby", "base": "a", "text": "b", "position": "beside"}]})),
    ("warichu_accepted", doc({
        "type": "text", "box": [0, 0, 100, 20],
        "spans": ["本文", {"kind": "warichu", "content": ["割注"], "lines": 2,
                           "brackets": "parenthesis"}]})),
    ("warichu_with_one_line_rejected", doc({
        "type": "text", "box": [0, 0, 100, 20],
        "spans": [{"kind": "warichu", "content": ["x"], "lines": 1}]})),

    # -- render output -------------------------------------------------------- #
    ("render_output_press_accepted", doc(**{"targets": [{
        "name": "press", "canvas": {"preset": "book-6x9"},
        "output": {"format": "pdf", "dpi": 300, "output_intent": "press",
                   "color_space": "cmyk", "font_embedding": "subset",
                   "crop_marks": True, "registration_marks": True}}]})),
    ("render_output_without_canvas_accepted", doc(**{"targets": [{
        "name": "web", "output": {"format": "png", "dpi": 144}}]})),
    ("unknown_output_format_rejected", doc(**{"targets": [{
        "name": "x", "canvas": {"preset": "A4"}, "output": {"format": "docx"}}]})),
    ("non_positive_dpi_rejected", doc(**{"targets": [{
        "name": "x", "canvas": {"preset": "A4"}, "output": {"dpi": 0}}]})),
    ("legacy_three_field_target_accepted", doc(**{"targets": [{
        "name": "mobile", "canvas": {"preset": "phone"},
        "adjustments": {"font_scale": 0.8}}]})),

    # -- unresolved generative authoring intent ----------------------------- #
    ("generative_image_with_alt_accepted", doc({
        "type": "generative", "kind": "image",
        "prompt": "A paper-cut forest", "model": "image-model-v1",
        "params": {"seed": 42, "size": [1024, 1024]},
        "box": [0, 0, 100, 100], "alt": "Layered paper trees."})),
    ("generative_image_without_accessible_text_rejected", doc({
        "type": "generative", "kind": "image",
        "prompt": "A paper-cut forest", "model": "image-model-v1",
        "box": [0, 0, 100, 100]})),

    # -- typographic rhythm: the baseline grid (2.10.0) ---------------------- #
    # The guards here are the whole value of the field. A grid with a zero or
    # negative pitch is not a stricter grid, it is a non-terminating layout, and
    # nothing downstream would report it — the renderer would divide by it.
    ("baseline_grid_accepted", doc(defs={"baseline_grid": {
        "increment": "13pt", "start": 0, "relative_to": "top_margin"}})),
    ("baseline_grid_bare_increment_accepted", doc(defs={"baseline_grid": {"increment": 13}})),
    ("baseline_grid_page_override_accepted", doc(**{"pages": [{
        "mode": "page", "id": "p1", "canvas": {"size": [400, 200], "units": "px"},
        "rendering": {"baseline_grid": {"increment": 15}},
        "layers": [{"id": "main", "objects": [
            {"type": "text", "box": [20, 20, 360, 40], "text": "Hello"}]}]}]})),
    ("baseline_grid_zero_increment_rejected", doc(defs={"baseline_grid": {"increment": 0}})),
    ("baseline_grid_negative_increment_rejected", doc(defs={"baseline_grid": {"increment": -13}})),
    ("baseline_grid_negative_length_string_rejected",
     doc(defs={"baseline_grid": {"increment": "-13pt"}})),
    ("baseline_grid_bad_unit_rejected", doc(defs={"baseline_grid": {"increment": "13ptx"}})),
    ("baseline_grid_without_increment_rejected", doc(defs={"baseline_grid": {"start": 0}})),
    ("baseline_grid_unknown_datum_rejected",
     doc(defs={"baseline_grid": {"increment": 13, "relative_to": "middle"}})),
    ("align_to_baseline_on_a_token_style_accepted", doc(defs={
        "baseline_grid": {"increment": 13},
        "tokens": {"styles": {"body": {"line_height": 13, "align_to_baseline": True}}}})),
    ("align_to_baseline_inline_accepted", doc({
        "type": "text", "box": [0, 0, 100, 20], "text": "x",
        "style": {"align_to_baseline": True}})),

    # -- typographic rhythm: measure (2.10.0) -------------------------------- #
    ("measure_accepted", doc(**{"text_contract": {"measure": [45, 75]}})),
    ("measure_exact_accepted", doc(**{"text_contract": {"measure": [66, 66]}})),
    ("measure_inverted_rejected", doc(**{"text_contract": {"measure": [75, 45]}})),
    ("measure_zero_bound_rejected", doc(**{"text_contract": {"measure": [0, 75]}})),
    ("measure_single_bound_rejected", doc(**{"text_contract": {"measure": [45]}})),

    # -- prepress: the total ink cap (2.10.0) -------------------------------- #
    # 400 is the percentage spelling of the same number. Accepting it would read
    # as 40000% coverage and pass every downstream check.
    ("total_ink_limit_accepted", doc(defs={"color_profiles": {"press": {
        "space": "cmyk", "name": "Coated FOGRA39", "total_ink_limit": 3.0}}})),
    ("total_ink_limit_percentage_form_rejected", doc(defs={"color_profiles": {"press": {
        "space": "cmyk", "total_ink_limit": 300}}})),
    ("total_ink_limit_above_four_separations_rejected", doc(defs={"color_profiles": {"press": {
        "space": "cmyk", "total_ink_limit": 4.1}}})),
    ("total_ink_limit_zero_rejected", doc(defs={"color_profiles": {"press": {
        "space": "cmyk", "total_ink_limit": 0}}})),
    # ======================================================================== #
    #  Lottie-parity — matte, parametric star, winding, name, symbol shape     #
    # ======================================================================== #
    ("matte_alpha_accepted", doc(
        {"type": "image", "id": "photo", "box": [0, 0, 100, 100], "src": "p.jpg"},
        {"type": "text", "id": "knock", "box": [0, 0, 100, 100], "text": "M",
         "matte": {"source": "photo", "mode": "alpha"}})),
    ("matte_luma_inverted_accepted", doc(
        {"type": "rect", "id": "ramp", "box": [0, 0, 10, 10], "fill": "#fff"},
        {"type": "rect", "box": [0, 0, 10, 10], "fill": "#f00",
         "matte": {"source": "ramp", "mode": "luma", "invert": True}})),
    ("matte_without_source_rejected", doc({**TEXT, "matte": {"mode": "alpha"}})),
    ("matte_unknown_mode_rejected", doc({**TEXT, "matte": {"source": "x", "mode": "stencil"}})),
    ("matte_self_reference_rejected", doc(
        {**TEXT, "id": "a", "matte": {"source": "a", "mode": "alpha"}})),

    ("star_accepted", doc({"type": "star", "center": [50, 50], "points": 5,
                           "outer_radius": 50, "inner_radius": 20})),
    ("polygon_star_type_accepted", doc({"type": "star", "star_type": "polygon",
                                        "center": [50, 50], "points": 6, "outer_radius": 40})),
    ("star_without_inner_radius_rejected", doc({"type": "star", "center": [50, 50],
                                                "points": 5, "outer_radius": 50})),
    ("polygon_with_inner_radius_rejected", doc({"type": "star", "star_type": "polygon",
                                                "center": [50, 50], "points": 6,
                                                "outer_radius": 40, "inner_radius": 10})),
    ("star_with_two_points_rejected", doc({"type": "star", "center": [50, 50], "points": 2,
                                           "outer_radius": 50, "inner_radius": 20})),
    ("star_with_zero_outer_radius_rejected", doc({"type": "star", "center": [50, 50],
                                                  "points": 5, "outer_radius": 0,
                                                  "inner_radius": 20})),
    ("star_roundness_above_one_rejected", doc({"type": "star", "center": [50, 50], "points": 5,
                                               "outer_radius": 50, "inner_radius": 20,
                                               "outer_roundness": 2})),

    ("shape_direction_accepted", doc({"type": "path", "d": "M 0 0 L 1 1",
                                      "direction": "counter-clockwise"})),
    ("unknown_shape_direction_rejected", doc({"type": "path", "d": "M 0 0 L 1 1",
                                              "direction": "widdershins"})),

    ("object_name_accepted", doc({**TEXT, "id": "h1", "name": "Chapter heading"})),

    ("typed_symbol_def_accepted", doc(TEXT, defs={"symbols": {"badge": {
        "content": [{"type": "circle", "center": [8, 8], "r": 8}],
        "viewbox": [0, 0, 16, 16]}}})),
    ("loose_symbol_body_still_accepted", doc(TEXT, defs={"symbols": {"legacy": {"x": [1]}}})),
]
