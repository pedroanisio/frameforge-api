#!/usr/bin/env python3
"""test_print_book_cjkv.py — acceptance criteria for the 2.9.0 contract widening.

Four gaps closed here, all of them cases where the contract advertised an
intent it could not express:

  PRINT COLOUR   `bleed` and twelve `book-*` trim presets shipped, while a
                 colour was a bare string — no CMYK, no spot ink, no ICC, no
                 overprint. A document could ask for a 6x9 trade book and could
                 not say what ink prints.
  BOOK GEOMETRY  Twelve bound-book trim sizes, and a margin of
                 [top, right, bottom, left] — no gutter, no inside/outside, no
                 recto/verso, no spread. Mirrored margins were inexpressible.
  CJKV           `writing_mode`, `direction` and `unicode_bidi` were all
                 declarable, so vertical Japanese was expressible — and then
                 could not be annotated, because the inline union had no ruby
                 and no warichu.
  RENDER TARGET  Three fields: name, canvas, adjustments. No output format, no
                 raster resolution, no colour profile, no font-embedding policy,
                 no printer's marks — for a family that renders to SVG, HTML,
                 PNG, PDF and LaTeX.

Every addition is OPTIONAL and every union is EXTENDED rather than replaced, so
the widening is backward compatible by construction. `test_backward_compat.py`
asserts that empirically against the whole fixture corpus; this file asserts the
new capability is actually reachable, correctly typed, and guarded.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from _probes import TEXT, doc

from frameforge_api import Document, build_schema

pytestmark = pytest.mark.filterwarnings("ignore")


def valid(d) -> Document:
    """Validate, surfacing the first error rather than a bare exception."""
    return Document.model_validate(d)


def rejected(d) -> list[str]:
    with pytest.raises(Exception) as ei:
        Document.model_validate(d)
    errs = ei.value.errors() if hasattr(ei.value, "errors") else []
    return [e["type"] for e in errs]


# --------------------------------------------------------------------------- #
#  GAP 1 — print colour: CMYK, spot ink, ICC, overprint                       #
# --------------------------------------------------------------------------- #
class TestPrintColour:
    def test_a_cmyk_colour_is_accepted_wherever_a_colour_is(self):
        d = valid(doc({"type": "rect", "box": [0, 0, 10, 10],
                       "fill": {"space": "cmyk", "c": 0, "m": 0.9, "y": 0.8, "k": 0}}))
        rect = d.pages[0].layers[0].objects[0]
        assert rect.fill.space == "cmyk"
        assert rect.fill.m == 0.9

    def test_cmyk_components_are_unit_interval_gated(self):
        """Ink coverage is 0..1. A 90 that meant 90% must fail loudly, not clip."""
        assert rejected(doc({"type": "rect", "box": [0, 0, 10, 10],
                             "fill": {"space": "cmyk", "c": 0, "m": 90, "y": 0, "k": 0}}))

    def test_a_spot_ink_carries_its_system_tint_and_process_alternate(self):
        d = valid(doc({"type": "rect", "box": [0, 0, 10, 10],
                       "fill": {"space": "spot", "name": "PANTONE 283 C",
                                "system": "pantone", "tint": 0.4,
                                "alternate": {"space": "cmyk",
                                              "c": 0.31, "m": 0.09, "y": 0, "k": 0}}}))
        ink = d.pages[0].layers[0].objects[0].fill
        assert ink.name == "PANTONE 283 C"
        assert ink.alternate.space == "cmyk"

    def test_a_spot_ink_without_a_name_is_rejected(self):
        """A separation with no name cannot become a printing plate."""
        assert rejected(doc({"type": "rect", "box": [0, 0, 10, 10],
                             "fill": {"space": "spot", "tint": 0.4}}))

    def test_an_icc_colour_names_a_declared_profile(self):
        d = doc({"type": "rect", "box": [0, 0, 10, 10],
                 "fill": {"space": "icc", "profile": "coated_fogra39",
                          "components": [0.1, 0.8, 0.7, 0.0], "fallback": "#d4145a"}})
        d["defs"] = {"color_profiles": {"coated_fogra39": {
            "space": "cmyk", "src": "profiles/CoatedFOGRA39.icc",
            "hash": "sha256:" + "0" * 64, "rendering_intent": "relative-colorimetric"}}}
        out = valid(d)
        assert out.defs.color_profiles["coated_fogra39"].rendering_intent == \
            "relative-colorimetric"

    def test_a_hex_string_still_validates_unchanged(self):
        """The widening must not cost the common path anything."""
        valid(doc({"type": "rect", "box": [0, 0, 10, 10], "fill": "#d4145a"}))
        valid(doc({"type": "rect", "box": [0, 0, 10, 10], "fill": "rebeccapurple"}))

    def test_an_unknown_colour_space_is_rejected(self):
        assert rejected(doc({"type": "rect", "box": [0, 0, 10, 10],
                             "fill": {"space": "pantone", "name": "x"}}))

    def test_a_colour_token_may_resolve_to_a_spot_ink(self):
        d = doc({"type": "rect", "box": [0, 0, 10, 10], "fill": "brand_ink"})
        d["defs"] = {"tokens": {"colors": {
            "brand_ink": {"space": "spot", "name": "PANTONE 032 C", "system": "pantone"}}}}
        out = valid(d)
        assert out.defs.tokens.colors["brand_ink"].name == "PANTONE 032 C"

    def test_overprint_is_declarable_on_a_style(self):
        d = valid(doc({"type": "rect", "box": [0, 0, 10, 10],
                       "style": {"overprint": "both", "overprint_mode": "nonzero-cmyk"}}))
        assert d.pages[0].layers[0].objects[0].style.overprint == "both"

    def test_an_unknown_overprint_value_is_rejected(self):
        assert rejected(doc({"type": "rect", "box": [0, 0, 10, 10],
                             "style": {"overprint": "sometimes"}}))

    def test_a_gradient_stop_takes_a_cmyk_colour(self):
        """Typed colour must reach every place a colour is accepted, not just fill."""
        valid(doc({"type": "rect", "box": [0, 0, 10, 10],
                   "fill": {"kind": "linear", "stops": [
                       {"color": {"space": "cmyk", "c": 0, "m": 0, "y": 0, "k": 1}},
                       {"color": "#fff"}]}}))


# --------------------------------------------------------------------------- #
#  GAP 2 — book geometry: gutter, mirrored margins, recto/verso, spreads       #
# --------------------------------------------------------------------------- #
class TestBookGeometry:
    def test_a_margin_can_be_declared_inside_outside_with_a_gutter(self):
        d = doc(**{"pages": [{
            "mode": "page", "id": "p1",
            "canvas": {"preset": "book-6x9",
                       "margin": {"top": "18mm", "bottom": "22mm",
                                  "inside": "20mm", "outside": "14mm", "gutter": "5mm"}},
            "layers": [{"id": "l", "objects": [TEXT]}]}]})
        out = valid(d)
        assert out.pages[0].canvas.margin.gutter == "5mm"

    def test_the_four_value_box_margin_still_validates(self):
        valid(doc(**{"pages": [{
            "mode": "page", "id": "p1",
            "canvas": {"size": [400, 200], "units": "px", "margin": [10, 10, 10, 10]},
            "layers": [{"id": "l", "objects": [TEXT]}]}]}))

    def test_mixing_left_right_with_inside_outside_is_rejected(self):
        """They are two coordinate systems for the same edge. Picking one silently
        would place the text block wrong on every verso page."""
        assert rejected(doc(**{"pages": [{
            "mode": "page", "id": "p1",
            "canvas": {"preset": "book-6x9",
                       "margin": {"left": "20mm", "inside": "20mm"}},
            "layers": [{"id": "l", "objects": [TEXT]}]}]}))

    def test_a_master_binds_to_a_page_side(self):
        d = doc(**{
            "defs": {"masters": {
                "recto": {"canvas": {"preset": "book-6x9"}, "side": "recto",
                          "margin": {"inside": "20mm", "outside": "14mm"},
                          "regions": [{"id": "body", "box": [20, 20, 100, 160]}]},
                "verso": {"canvas": {"preset": "book-6x9"}, "side": "verso",
                          "margin": {"inside": "20mm", "outside": "14mm"},
                          "regions": [{"id": "body", "box": [20, 20, 100, 160]}]}}},
            "pages": [{"mode": "flow", "id": "s1", "master": "recto",
                       "story": [{"type": "paragraph", "text": "a"}]}]})
        out = valid(d)
        assert out.defs.masters["verso"].side == "verso"

    def test_an_unknown_page_side_is_rejected(self):
        assert rejected(doc(**{
            "defs": {"masters": {"m": {"canvas": {"preset": "book-6x9"}, "side": "left"}}},
            "pages": [{"mode": "flow", "id": "s1", "master": "m", "story": []}]}))

    def test_a_page_declares_its_own_side(self):
        d = doc(**{"pages": [{
            "mode": "page", "id": "p1", "side": "verso",
            "canvas": {"preset": "book-6x9"},
            "layers": [{"id": "l", "objects": [TEXT]}]}]})
        assert valid(d).pages[0].side == "verso"

    def test_a_canvas_can_be_a_two_page_spread(self):
        d = doc(**{"pages": [{
            "mode": "page", "id": "p1",
            "canvas": {"preset": "book-6x9", "spread": True},
            "layers": [{"id": "l", "objects": [TEXT]}]}]})
        assert valid(d).pages[0].canvas.spread is True


# --------------------------------------------------------------------------- #
#  GAP 3 — CJKV inline annotation: ruby and warichu                           #
# --------------------------------------------------------------------------- #
class TestCJKVAnnotation:
    def test_a_ruby_run_annotates_a_base_run(self):
        d = valid(doc({"type": "text", "box": [0, 0, 100, 20], "spans": [
            {"kind": "ruby", "base": "漢字", "text": "かんじ", "position": "over"}]}))
        span = d.pages[0].layers[0].objects[0].spans[0]
        assert span.base == "漢字" and span.text == "かんじ"

    def test_ruby_accepts_per_character_annotation(self):
        """Mono-ruby: one annotation per base character, not one for the run."""
        valid(doc({"type": "text", "box": [0, 0, 100, 20], "spans": [
            {"kind": "ruby", "base": "漢字", "text": ["かん", "じ"]}]}))

    def test_ruby_without_an_annotation_is_rejected(self):
        assert rejected(doc({"type": "text", "box": [0, 0, 100, 20], "spans": [
            {"kind": "ruby", "base": "漢字"}]}))

    def test_an_unknown_ruby_position_is_rejected(self):
        assert rejected(doc({"type": "text", "box": [0, 0, 100, 20], "spans": [
            {"kind": "ruby", "base": "a", "text": "b", "position": "beside"}]}))

    def test_a_warichu_run_carries_inline_content(self):
        d = valid(doc({"type": "text", "box": [0, 0, 100, 20], "spans": [
            "本文", {"kind": "warichu", "content": ["割注"], "lines": 2,
                     "brackets": "parenthesis"}]}))
        assert d.pages[0].layers[0].objects[0].spans[1].lines == 2

    def test_ruby_nests_inside_other_inline_content(self):
        """Ruby is a run like any other: it must compose with links and spans."""
        valid(doc({"type": "text", "box": [0, 0, 100, 20], "spans": [
            {"kind": "link", "href": "#x", "content": ["見出し"]},
            {"kind": "ruby", "base": [{"kind": "code", "text": "kbd"}], "text": "キー"}]}))

    def test_ruby_and_warichu_work_in_flowed_paragraphs(self):
        valid({**doc(), "defs": {"masters": {"m1": {
            "canvas": {"size": [400, 200], "units": "px"},
            "regions": [{"id": "body", "box": [20, 20, 360, 160]}]}}},
            "pages": [{"mode": "flow", "id": "s1", "master": "m1", "story": [
                {"type": "paragraph", "spans": [
                    {"kind": "ruby", "base": "日本語", "text": "にほんご"}]}]}]})


# --------------------------------------------------------------------------- #
#  GAP 4 — render target: format, resolution, colour, fonts, printer's marks  #
# --------------------------------------------------------------------------- #
class TestRenderTarget:
    def test_a_target_declares_its_output_format_and_resolution(self):
        d = valid(doc(**{"targets": [{
            "name": "print", "canvas": {"preset": "book-6x9"},
            "output": {"format": "pdf", "dpi": 300, "output_intent": "press",
                       "color_space": "cmyk", "font_embedding": "subset"}}]}))
        assert d.targets[0].output.dpi == 300

    def test_a_target_declares_printers_marks(self):
        d = valid(doc(**{"targets": [{
            "name": "press", "canvas": {"preset": "book-6x9"},
            "output": {"format": "pdf", "crop_marks": True, "bleed_marks": True,
                       "registration_marks": True, "color_bars": True,
                       "page_information": True}}]}))
        assert d.targets[0].output.crop_marks is True

    def test_a_target_names_a_declared_colour_profile(self):
        d = doc(**{"targets": [{"name": "press", "canvas": {"preset": "book-6x9"},
                                "output": {"format": "pdf",
                                           "color_profile": "coated_fogra39"}}]})
        d["defs"] = {"color_profiles": {"coated_fogra39": {"space": "cmyk"}}}
        assert valid(d).targets[0].output.color_profile == "coated_fogra39"

    def test_an_unknown_output_format_is_rejected(self):
        assert rejected(doc(**{"targets": [{
            "name": "x", "canvas": {"preset": "A4"}, "output": {"format": "docx"}}]}))

    def test_an_unknown_font_embedding_policy_is_rejected(self):
        assert rejected(doc(**{"targets": [{
            "name": "x", "canvas": {"preset": "A4"},
            "output": {"font_embedding": "maybe"}}]}))

    def test_a_target_may_change_only_the_output_leaving_the_canvas_alone(self):
        """A raster and a vector export of the SAME canvas is the common case;
        forcing a canvas restatement invites the two to drift apart."""
        d = valid(doc(**{"targets": [{"name": "web", "output": {"format": "png", "dpi": 144}}]}))
        assert d.targets[0].canvas is None

    def test_the_existing_three_field_target_still_validates(self):
        valid(doc(**{"targets": [{
            "name": "mobile", "canvas": {"preset": "phone"},
            "adjustments": {"font_scale": 0.8, "hide": ["sidebar"]}}]}))

    def test_dpi_must_be_positive(self):
        assert rejected(doc(**{"targets": [{
            "name": "x", "canvas": {"preset": "A4"}, "output": {"dpi": 0}}]}))


# --------------------------------------------------------------------------- #
#  Cross-cutting: the schema is the contract every non-Python consumer reads  #
# --------------------------------------------------------------------------- #
class TestSchemaExposure:
    def test_every_new_model_reaches_the_generated_schema(self):
        defs = build_schema()["$defs"]
        for name in ("CmykColor", "SpotColor", "IccColor", "ColorProfileDef",
                     "PageMargin", "RubyInline", "WarichuInline", "RenderOutput"):
            assert name in defs, f"{name} is unreachable from Document"

    def test_the_new_models_are_closed_like_everything_else(self):
        from frameforge_api import model as m
        for cls in (m.CmykColor, m.SpotColor, m.IccColor, m.ColorProfileDef,
                    m.PageMargin, m.RubyInline, m.WarichuInline, m.RenderOutput):
            assert cls.model_config.get("extra") == "forbid", cls.__name__

    def test_the_new_names_are_importable_from_the_package(self):
        import frameforge_api.model as m
        for name in ("CmykColor", "SpotColor", "IccColor", "ColorObject",
                     "ColorProfileDef", "PageMargin", "MarginSpec", "PageSide",
                     "RubyInline", "WarichuInline", "RenderOutput"):
            assert hasattr(m, name), name
