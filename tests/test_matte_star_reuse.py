#!/usr/bin/env python3
"""test_matte_star_reuse.py — acceptance criteria for the Lottie-parity gaps.

Four gaps found by inspecting the contract against the Lottie 1.0 schema, which
is the closest published peer for the *graphics* half of the model (the page,
flow and print halves have no Lottie equivalent at all):

  MATTE       Lottie gives every layer a matte mode naming a sibling as the
              matte — alpha or luma, either invertible. FrameForge could mask by
              an image (`style.mask`) and clip by a path (`style.clip_path`), and
              had no way for one OBJECT to matte another. "Knock this text out of
              that photo" meant pre-rasterising outside the document.
  STAR        Lottie's PolyStar is parametric: points, inner and outer radius,
              inner and outer roundness, star-or-polygon. FrameForge had an
              explicit point list and a deprecated `polygon` alias, so a
              five-point star was ten hand-computed vertices with the parameters
              thrown away.
  DIRECTION   Winding order, which decides hole behaviour together with
              `fill_rule`, and which Lottie carries per shape.
  NAME        Lottie separates a human label from the stable address. FrameForge
              had `id` (the address) and nowhere to put the label.

Reuse — Lottie's Precomposition — is deliberately NOT closed here as a runtime
primitive: `use`/`component` instances stay SDK-lowered, which is the same
boundary that keeps grammar sugar out of the core profile. What IS closed is the
untyped half: `defs.symbols` had the type `dict`, so a symbol definition could be
anything at all. See `docs/adr/0001-flat-document-model.md` for the decision.

Every addition is optional and every union is extended, so this stays inside the
declared `COMPATIBILITY = "backward"` guarantee.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from _probes import TEXT, doc

from frameforge_api import Document, build_schema


def valid(d) -> Document:
    return Document.model_validate(d)


def rejected(d) -> list[str]:
    with pytest.raises(Exception) as ei:
        Document.model_validate(d)
    return [e["type"] for e in (ei.value.errors() if hasattr(ei.value, "errors") else [])]


# --------------------------------------------------------------------------- #
#  GAP 1 — track matte: one object mattes another                             #
# --------------------------------------------------------------------------- #
class TestMatte:
    def test_an_object_is_matted_by_a_sibling(self):
        d = valid(doc(
            {"type": "image", "id": "photo", "box": [0, 0, 100, 100], "src": "p.jpg"},
            {"type": "text", "id": "knockout", "box": [0, 0, 100, 100], "text": "MASK",
             "matte": {"source": "photo", "mode": "alpha"}}))
        knock = d.pages[0].layers[0].objects[1]
        assert knock.matte.source == "photo" and knock.matte.mode == "alpha"

    def test_a_luma_matte_can_be_inverted(self):
        d = valid(doc(
            {"type": "rect", "id": "ramp", "box": [0, 0, 100, 100],
             "fill": {"kind": "linear", "stops": [{"color": "#000"}, {"color": "#fff"}]}},
            {"type": "rect", "id": "faded", "box": [0, 0, 100, 100], "fill": "#f00",
             "matte": {"source": "ramp", "mode": "luma", "invert": True}}))
        assert d.pages[0].layers[0].objects[1].matte.invert is True

    def test_the_matte_source_is_required(self):
        """A matte with no source is not a matte; silently ignoring it would
        paint the object unmasked, which is the opposite of the intent."""
        assert rejected(doc({**TEXT, "matte": {"mode": "alpha"}}))

    def test_an_unknown_matte_mode_is_rejected(self):
        assert rejected(doc({**TEXT, "matte": {"source": "x", "mode": "stencil"}}))

    def test_an_object_cannot_be_its_own_matte(self):
        """Locally checkable and always a mistake — it is a definition that
        consumes itself. Whether a source that is NOT self resolves is
        whole-document referential integrity, and lives with the engine."""
        assert rejected(doc({**TEXT, "id": "a", "matte": {"source": "a", "mode": "alpha"}}))

    def test_a_group_can_be_matted(self):
        """Matting a container is the common case — it is how a whole assembly
        gets faded or knocked out at once."""
        valid(doc(
            {"type": "rect", "id": "m", "box": [0, 0, 10, 10], "fill": "#fff"},
            {"type": "group", "box": [0, 0, 100, 100], "children": [TEXT],
             "matte": {"source": "m", "mode": "luma"}}))

    def test_absent_matte_is_the_default(self):
        assert valid(doc(TEXT)).pages[0].layers[0].objects[0].matte is None


# --------------------------------------------------------------------------- #
#  GAP 2 — parametric star and regular polygon                                #
# --------------------------------------------------------------------------- #
class TestStar:
    def test_a_five_point_star_is_parametric(self):
        d = valid(doc({"type": "star", "center": [50, 50], "points": 5,
                       "outer_radius": 50, "inner_radius": 20, "fill": "#fc0"}))
        star = d.pages[0].layers[0].objects[0]
        assert (star.points, star.outer_radius, star.inner_radius) == (5, 50, 20)

    def test_a_regular_polygon_needs_no_inner_radius(self):
        d = valid(doc({"type": "star", "star_type": "polygon", "center": [50, 50],
                       "points": 6, "outer_radius": 40}))
        assert d.pages[0].layers[0].objects[0].star_type == "polygon"

    def test_a_star_requires_an_inner_radius(self):
        """Without it there is no star — only a polygon that lost its type."""
        assert rejected(doc({"type": "star", "center": [50, 50], "points": 5,
                             "outer_radius": 50}))

    def test_a_polygon_with_an_inner_radius_is_rejected(self):
        """An incoherent combination is an error, never a silent reinterpretation
        — the same rule the gradient geometry validator applies."""
        assert rejected(doc({"type": "star", "star_type": "polygon", "center": [50, 50],
                             "points": 6, "outer_radius": 40, "inner_radius": 10}))

    def test_fewer_than_three_points_is_rejected(self):
        assert rejected(doc({"type": "star", "center": [50, 50], "points": 2,
                             "outer_radius": 50, "inner_radius": 20}))

    def test_radii_must_be_positive(self):
        assert rejected(doc({"type": "star", "center": [50, 50], "points": 5,
                             "outer_radius": 0, "inner_radius": 20}))

    def test_roundness_and_rotation_are_optional_and_bounded(self):
        valid(doc({"type": "star", "center": [50, 50], "points": 5, "outer_radius": 50,
                   "inner_radius": 20, "outer_roundness": 0.3, "inner_roundness": 0.1,
                   "rotation": 18}))
        assert rejected(doc({"type": "star", "center": [50, 50], "points": 5,
                             "outer_radius": 50, "inner_radius": 20, "outer_roundness": 2}))

    def test_a_star_takes_paint_like_every_other_shape(self):
        valid(doc({"type": "star", "center": [50, 50], "points": 5, "outer_radius": 50,
                   "inner_radius": 20,
                   "fill": {"space": "spot", "name": "PANTONE 032 C"},
                   "stroke": "#000", "stroke_style": {"stroke_width": "0.5pt"}}))

    def test_a_star_nests_in_a_group(self):
        valid(doc({"type": "group", "box": [0, 0, 100, 100], "children": [
            {"type": "star", "center": [50, 50], "points": 5,
             "outer_radius": 50, "inner_radius": 20}]}))


# --------------------------------------------------------------------------- #
#  GAP 3 — winding direction                                                  #
# --------------------------------------------------------------------------- #
class TestShapeDirection:
    @pytest.mark.parametrize("obj", [
        {"type": "path", "d": "M 0 0 L 10 0 L 10 10 Z"},
        {"type": "polyline", "points": [[0, 0], [10, 0], [10, 10]]},
        {"type": "polygon", "points": [[0, 0], [10, 0], [10, 10]]},
        {"type": "star", "center": [5, 5], "points": 5, "outer_radius": 5, "inner_radius": 2},
    ], ids=["path", "polyline", "polygon", "star"])
    def test_geometry_objects_carry_a_winding_direction(self, obj):
        d = valid(doc({**obj, "direction": "counter-clockwise"}))
        assert d.pages[0].layers[0].objects[0].direction == "counter-clockwise"

    def test_an_unknown_direction_is_rejected(self):
        assert rejected(doc({"type": "path", "d": "M 0 0 L 1 1", "direction": "widdershins"}))

    def test_direction_is_optional(self):
        assert valid(doc({"type": "path", "d": "M 0 0 L 1 1"})
                     ).pages[0].layers[0].objects[0].direction is None


# --------------------------------------------------------------------------- #
#  GAP 4 — a human label distinct from the stable address                     #
# --------------------------------------------------------------------------- #
class TestObjectName:
    def test_an_object_carries_a_name_beside_its_id(self):
        d = valid(doc({**TEXT, "id": "hdr_01", "name": "Chapter heading"}))
        obj = d.pages[0].layers[0].objects[0]
        assert (obj.id, obj.name) == ("hdr_01", "Chapter heading")

    def test_name_is_optional_and_independent_of_id(self):
        valid(doc({**TEXT, "name": "unnamed but labelled"}))


# --------------------------------------------------------------------------- #
#  Reuse — the definition side is typed; instancing stays SDK-lowered         #
# --------------------------------------------------------------------------- #
class TestSymbolDefinitions:
    def test_a_symbol_definition_has_a_declared_shape(self):
        d = valid(doc(TEXT, defs={"symbols": {"badge": {
            "content": [{"type": "circle", "center": [8, 8], "r": 8, "fill": "#fc0"}],
            "viewbox": [0, 0, 16, 16],
            "description": "A round status badge."}}}))
        assert d.defs.symbols["badge"].viewbox == [0, 0, 16, 16]

    def test_an_unrecognised_symbol_body_is_still_accepted(self):
        """`symbols` is out of the deep core profile (§8.5) and was typed `dict`.
        Narrowing it would reject documents that validate today, which the
        BACKWARD guarantee forbids — so the typed shape is offered, not imposed."""
        valid(doc(TEXT, defs={"symbols": {"legacy": {"anything": [1, 2, 3]}}}))

    def test_instancing_is_still_not_a_core_object(self):
        """The flat-document decision, asserted from the other side: `use` is SDK
        source that `sdk.expand()` lowers before the contract sees it. If this
        starts passing, the core profile has absorbed pre-lowering syntax."""
        assert rejected(doc({"type": "use", "symbol": "badge", "box": [0, 0, 16, 16]}))


# --------------------------------------------------------------------------- #
#  Cross-cutting                                                              #
# --------------------------------------------------------------------------- #
class TestSchemaExposure:
    def test_the_new_models_reach_the_generated_schema(self):
        defs = build_schema()["$defs"]
        for name in ("MatteSpec", "Star", "SymbolDef"):
            assert name in defs, f"{name} is unreachable from Document"

    def test_the_new_models_are_closed(self):
        from frameforge_api import model as m
        for cls in (m.MatteSpec, m.Star, m.SymbolDef):
            assert cls.model_config.get("extra") == "forbid", cls.__name__

    def test_the_new_names_are_importable(self):
        import frameforge_api.model as m
        for name in ("MatteSpec", "MatteMode", "Star", "StarType",
                     "ShapeDirection", "SymbolDef"):
            assert hasattr(m, name), name

    def test_star_joined_the_visual_object_union(self):
        from typing import get_args

        from frameforge_api import model as m
        members = {t.__name__ for t in get_args(get_args(m.VisualObject)[0])}
        assert "Star" in members
