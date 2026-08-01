#!/usr/bin/env python3
"""test_examples.py — the examples in `examples/` are real documents.

A README snippet that no longer validates is worse than no snippet: it is a
confident, wrong answer to "how do I do this". Every example ships as a file and
is validated here, so documentation rot becomes a test failure.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from frameforge_api import HEAD_VERSION, Document

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

#: The migration pair, held apart from the reference examples on purpose.
#:
#: `legacy-shortcuts.before.json` is deliberately INVALID — it demonstrates the
#: two forms P3 and P4 removed — so sweeping it with the others would fail, and
#: silently excluding it would let it rot. Neither half declares HEAD either: a
#: document's `version` states the revision it was authored against, and a
#: codemod that rewrites spellings has no business rewriting that claim.
#: `tests/test_deprecations.py` owns the pair; this module only states why they
#: are not reference examples.
MIGRATION_PAIR = ("legacy-shortcuts.before.json", "legacy-shortcuts.after.json")


def _examples() -> list[Path]:
    return sorted(p for p in EXAMPLES.glob("*.json") if p.name not in MIGRATION_PAIR)


def test_there_are_examples_to_check():
    assert _examples(), f"no examples under {EXAMPLES}"


def test_the_migration_pair_is_present_and_excluded_deliberately():
    """A silent exclusion is how an example stops being checked by anyone."""
    for name in MIGRATION_PAIR:
        assert (EXAMPLES / name).is_file(), f"{name} is excluded here but does not exist"
    assert not any(p.name in MIGRATION_PAIR for p in _examples())


@pytest.mark.parametrize("path", _examples(), ids=lambda p: p.stem)
def test_the_example_validates(path: Path):
    Document.model_validate(json.loads(path.read_text(encoding="utf-8")))


@pytest.mark.parametrize("path", _examples(), ids=lambda p: p.stem)
def test_the_example_declares_the_current_contract_version(path: Path):
    """An example is the reference answer, so it shows the contract as it is now."""
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == HEAD_VERSION


def test_the_press_ready_example_exercises_everything_2_9_0_added():
    """The point of this example is coverage of the widening; assert it keeps it."""
    doc = Document.model_validate(
        json.loads((EXAMPLES / "press-ready-book.json").read_text(encoding="utf-8")))

    assert doc.defs.color_profiles["fogra39"].space == "cmyk"
    assert doc.defs.tokens.colors["accent"].space == "spot"
    assert doc.defs.tokens.colors["accent"].alternate.space == "cmyk"

    recto, verso = doc.defs.masters["recto"], doc.defs.masters["verso"]
    assert (recto.side, verso.side) == ("recto", "verso")
    assert recto.margin.gutter == "5mm" and recto.margin.inside == "20mm"

    band = doc.pages[0].layers[0].objects[0]
    assert band.style.overprint == "fill"

    press = next(t for t in doc.targets if t.name == "press")
    assert press.canvas is None                       # output-only target
    assert press.output.color_profile == "fogra39"
    assert press.output.crop_marks and press.output.font_embedding == "subset"

    spans = doc.pages[1].story[2].spans
    kinds = [getattr(s, "kind", None) for s in spans]
    assert "ruby" in kinds and "warichu" in kinds


def test_the_baseline_grid_example_exercises_everything_2_10_0_added():
    """Same contract as the 2.9.0 example: this file is the reference answer for
    the rhythm layer, so it must keep demonstrating all of it."""
    doc = Document.model_validate(
        json.loads((EXAMPLES / "baseline-grid-book.json").read_text(encoding="utf-8")))

    # the document grid, and a page that overrides it
    assert doc.defs.baseline_grid.increment == "13pt"
    assert doc.defs.baseline_grid.relative_to == "top_margin"
    override = doc.pages[0].rendering.baseline_grid
    assert override.increment == "18pt" and override.relative_to == "page"

    # opt-in is per block, and opting OUT explicitly is part of the vocabulary
    styles = doc.defs.tokens.styles
    assert styles["body"].align_to_baseline is True
    assert styles["chapter"].align_to_baseline is True
    assert styles["caption"].align_to_baseline is False

    # the increment IS the leading — the whole point of the field
    assert styles["body"].line_height == doc.defs.baseline_grid.increment

    # measure, document-wide and overridden per page
    assert doc.text_contract.measure == [60, 72]
    assert doc.pages[0].rendering.text.measure == [30, 45]

    # the ink cap 2.9.0's CMYK left open
    assert doc.defs.color_profiles["fogra39"].total_ink_limit == 3.0

    # the case the grid exists for: balanced columns across a spread
    region = doc.defs.masters["spread"].regions[0]
    assert region.columns == 2 and region.column_fill == "balance"
    assert doc.defs.masters["spread"].canvas.spread is True


def test_the_matte_and_star_example_exercises_the_lottie_parity_additions():
    """The graphics primitives closed against Lottie 1.0, asserted end to end."""
    doc = Document.model_validate(
        json.loads((EXAMPLES / "matte-and-star.json").read_text(encoding="utf-8")))
    objs = {o.name or o.id: o for o in doc.pages[0].layers[0].objects}

    masthead = objs["Masthead knocked out of the photograph"]
    assert masthead.matte.source == "photo" and masthead.matte.mode == "alpha"

    standfirst = objs["Standfirst, faded out by the ramp"]
    assert standfirst.matte.mode == "luma"

    award = objs["Award mark"]
    assert (award.star_type, award.points, award.inner_radius) == ("star", 5, 20)
    assert award.direction == "counter-clockwise"
    assert award.fill.space == "spot"

    ornament = objs["Hexagonal rule ornament"]
    assert ornament.star_type == "polygon" and ornament.inner_radius is None

    rosette = doc.defs.symbols["rosette"]
    assert rosette.viewbox == [0, 0, 32, 32]
    assert rosette.content[0].points == 12
