#!/usr/bin/env python3
"""test_typographic_rhythm.py — the vertical rhythm and ink-limit widening (2.10.0).

Three additions, all optional, all additive:

  BASELINE GRID   `defs.baseline_grid` declares the leading grid every text
                  baseline can snap to; a page overrides it through
                  `rendering.baseline_grid`; a paragraph opts in through
                  `align_to_baseline` on its style. The contract already had a
                  *spatial* grid (`Layout(kind="grid")`) and no way to say what
                  it should be divisible by — which is what makes gutters
                  between rows land inconsistently, and what makes balanced
                  columns fail to line up across a spread.

  MEASURE         `text_contract.measure` declares the intended line measure in
                  characters. It is the other half of the same decision: leading
                  fixes the vertical increment, measure fixes the column width
                  the increment is read at.

  TOTAL INK       `defs.color_profiles[*].total_ink_limit` caps summed coverage.
                  2.9.0 added `CmykColor` with four independent 0..1 components,
                  so `c=m=y=k=1.0` — 400% coverage — validates today. No press
                  takes that. The *limit* has to be declarable here for the
                  engine's validator to have anything to check a resolved paint
                  against.

Every test below is written against the public contract — `Document.model_validate`
and the generated schema — not against internal structure, so the file survives
the models being moved again.
"""
from __future__ import annotations

import pytest

from frameforge_api import HEAD_VERSION, Document, build_schema
from frameforge_api import model as M


# --------------------------------------------------------------------------- #
#  helpers                                                                     #
# --------------------------------------------------------------------------- #
def doc(**over) -> dict:
    """A minimal valid document; `over` is merged into the root."""
    d = {
        "dsl": "FrameForge",
        "version": HEAD_VERSION,
        "title": "rhythm",
        "pages": [{
            "mode": "page", "id": "p1",
            "canvas": {"size": [400, 200], "units": "px"},
            "layers": [{"id": "main", "objects": [
                {"type": "text", "box": [20, 20, 360, 40], "text": "Hello"},
            ]}],
        }],
    }
    d.update(over)
    return d


def accepts(**over) -> Document:
    return Document.model_validate(doc(**over))


def rejects(**over):
    with pytest.raises(Exception):
        Document.model_validate(doc(**over))


def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split("-")[0].split("."))


# --------------------------------------------------------------------------- #
#  1. BASELINE GRID — the document-level leading grid                          #
# --------------------------------------------------------------------------- #
def test_a_document_can_declare_a_baseline_grid():
    """The whole point: 10pt type on 13pt leading gets a 13pt grid."""
    d = accepts(defs={"baseline_grid": {"increment": 13}})
    assert d.defs.baseline_grid.increment == 13


def test_the_baseline_grid_takes_a_start_and_a_datum():
    d = accepts(defs={"baseline_grid": {
        "increment": "13pt", "start": "0pt", "relative_to": "top_margin"}})
    grid = d.defs.baseline_grid
    assert grid.increment == "13pt"
    assert grid.relative_to == "top_margin"


def test_the_increment_is_the_one_required_part_of_a_baseline_grid():
    """A grid with no pitch is not a grid."""
    rejects(defs={"baseline_grid": {"start": 0}})


def test_a_page_overrides_the_document_baseline_grid():
    """InDesign splits this as a document preference plus a frame-level override;
    the contract's frame-level scope is the page's rendering contract."""
    page = doc()["pages"][0] | {"rendering": {"baseline_grid": {"increment": 15}}}
    d = Document.model_validate(doc(
        defs={"baseline_grid": {"increment": 13}}, pages=[page]))
    assert d.defs.baseline_grid.increment == 13
    assert d.pages[0].rendering.baseline_grid.increment == 15


def test_a_paragraph_opts_into_the_grid_through_its_style():
    """Aligning to the grid is a per-paragraph decision, so it rides on Style —
    which is what paragraph formatting already composes through."""
    d = accepts(defs={
        "baseline_grid": {"increment": 13},
        "tokens": {"styles": {"body": {"font_size": 10, "line_height": 13,
                                       "align_to_baseline": True}}},
    })
    assert d.defs.tokens.styles["body"].align_to_baseline is True


def test_align_to_baseline_works_as_an_inline_style_too():
    obj = {"type": "text", "box": [0, 0, 100, 20], "text": "x",
           "style": {"align_to_baseline": True}}
    page = doc()["pages"][0] | {"layers": [{"id": "m", "objects": [obj]}]}
    Document.model_validate(doc(pages=[page]))


# ---- guards ---------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [0, -13, "0pt", "-13pt"])
def test_a_non_positive_increment_is_rejected(bad):
    """A zero or negative pitch is a degenerate grid — infinitely many
    gridlines, or ones marching backwards up the page."""
    rejects(defs={"baseline_grid": {"increment": bad}})


@pytest.mark.parametrize("bad", ["13ptx", "abc", "13 pt", ""])
def test_the_increment_is_pattern_gated_like_every_other_length(bad):
    rejects(defs={"baseline_grid": {"increment": bad}})


def test_the_baseline_grid_is_closed_like_everything_else():
    rejects(defs={"baseline_grid": {"increment": 13, "colour": "#fff"}})


def test_the_datum_vocabulary_is_constrained():
    accepts(defs={"baseline_grid": {"increment": 13, "relative_to": "page"}})
    rejects(defs={"baseline_grid": {"increment": 13, "relative_to": "middle"}})


# --------------------------------------------------------------------------- #
#  2. MEASURE — the intended line length, in characters                        #
# --------------------------------------------------------------------------- #
def test_a_text_contract_can_declare_a_target_measure():
    d = accepts(text_contract={"measure": [45, 75]})
    assert d.text_contract.measure == [45, 75]


def test_measure_is_declarable_per_page_as_well():
    page = doc()["pages"][0] | {"rendering": {"text": {"measure": [50, 66]}}}
    d = Document.model_validate(doc(pages=[page]))
    assert d.pages[0].rendering.text.measure == [50, 66]


@pytest.mark.parametrize("bad", [[45], [45, 60, 75], []])
def test_measure_is_exactly_a_lower_and_an_upper_bound(bad):
    rejects(text_contract={"measure": bad})


def test_measure_rejects_an_inverted_range():
    """[75, 45] is not a narrow measure, it is a typo."""
    rejects(text_contract={"measure": [75, 45]})


@pytest.mark.parametrize("bad", [[0, 75], [-10, 75]])
def test_measure_rejects_non_positive_bounds(bad):
    rejects(text_contract={"measure": bad})


def test_an_equal_lower_and_upper_bound_is_a_legal_exact_measure():
    accepts(text_contract={"measure": [66, 66]})


# --------------------------------------------------------------------------- #
#  3. TOTAL INK LIMIT — the cap 2.9.0's CMYK left open                          #
# --------------------------------------------------------------------------- #
def profile(**over) -> dict:
    p = {"space": "cmyk", "name": "Coated FOGRA39"}
    p.update(over)
    return {"color_profiles": {"press": p}}


def test_a_colour_profile_can_declare_a_total_ink_limit():
    d = accepts(defs=profile(total_ink_limit=3.0))
    assert d.defs.color_profiles["press"].total_ink_limit == 3.0


def test_the_limit_is_expressed_on_the_same_scale_as_the_cmyk_components():
    """CmykColor components are 0..1 each, so their sum runs 0..4. 3.0 is the
    common 300% sheet-fed limit; 4.0 is all four plates solid."""
    accepts(defs=profile(total_ink_limit=2.4))
    accepts(defs=profile(total_ink_limit=4.0))


@pytest.mark.parametrize("bad", [4.1, 400, 300, 0, -1])
def test_a_limit_outside_the_four_separations_is_rejected(bad):
    """400 is the percentage form — a plausible and expensive mistake, so it
    fails here rather than being read as 40000% coverage."""
    rejects(defs=profile(total_ink_limit=bad))


def test_the_total_ink_limit_is_optional():
    d = accepts(defs=profile())
    assert d.defs.color_profiles["press"].total_ink_limit is None


# --------------------------------------------------------------------------- #
#  4. INTEGRATION — exports, schema, version                                   #
# --------------------------------------------------------------------------- #
def test_baseline_grid_is_importable_from_the_model_package():
    """Every declared name must be reachable — the surface golden enforces it
    generally, this names the new one explicitly."""
    assert hasattr(M, "BaselineGrid")


def test_the_new_model_reaches_the_generated_schema():
    assert "BaselineGrid" in build_schema()["$defs"]


def test_the_new_fields_reach_the_generated_schema():
    defs = build_schema()["$defs"]
    assert "baseline_grid" in defs["Defs"]["properties"]
    assert "baseline_grid" in defs["RenderingContract"]["properties"]
    assert "align_to_baseline" in defs["Style"]["properties"]
    assert "measure" in defs["TextContract"]["properties"]
    assert "total_ink_limit" in defs["ColorProfileDef"]["properties"]


def test_the_new_model_is_closed_in_the_schema():
    assert build_schema()["$defs"]["BaselineGrid"]["additionalProperties"] is False


def test_the_contract_version_moved_for_the_widening():
    """Additive fields are a minor bump of the CONTRACT clock, not the wheel."""
    assert version_tuple(HEAD_VERSION) >= (2, 10, 0)


# --------------------------------------------------------------------------- #
#  5. REGRESSION — the widening is additive                                    #
# --------------------------------------------------------------------------- #
def test_a_document_using_none_of_this_still_validates():
    accepts()


def test_the_new_fields_are_all_absent_by_default():
    d = accepts(defs={"color_profiles": {"press": {"space": "cmyk"}}},
                text_contract={"min_font_size": 8})
    assert d.defs.baseline_grid is None
    assert d.text_contract.measure is None
    assert d.defs.color_profiles["press"].total_ink_limit is None
    assert M.Style().align_to_baseline is None


def test_the_three_additions_compose_in_one_press_ready_document():
    """The end-to-end shape the feature exists for: a bound book with a leading
    grid, a declared measure, and a press profile that caps coverage."""
    d = accepts(
        defs={
            "baseline_grid": {"increment": "13pt", "relative_to": "top_margin"},
            "color_profiles": {"press": {
                "space": "cmyk", "name": "Coated FOGRA39", "total_ink_limit": 3.0}},
            "tokens": {"styles": {"body": {
                "font_size": "10pt", "line_height": "13pt", "align_to_baseline": True}}},
        },
        text_contract={"measure": [60, 72]},
    )
    assert d.defs.baseline_grid.increment == "13pt"
    assert d.defs.color_profiles["press"].total_ink_limit == 3.0
    assert d.text_contract.measure == [60, 72]
    assert d.defs.tokens.styles["body"].align_to_baseline is True
