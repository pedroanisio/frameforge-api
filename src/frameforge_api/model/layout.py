"""Layout, content sizing, the baseline grid, and the ordered effect/appearance
stacks (P1 + P4 + 2.10.0).
"""
from __future__ import annotations

import re

from typing import Annotated, Literal, Optional, Union
from pydantic import Field, model_validator

from .base import Color, FG, Length, NumberFormat, Padding, Point, UnitInterval
from .style import Paint, StrokeStyleRef


# --------------------------------------------------------------------------- #
#  Layout + content sizing (P1 + P4)                                          #
# --------------------------------------------------------------------------- #
class Layout(FG):
    kind: Literal["row", "column", "grid", "wrap", "free"] = Field(
        description="Placement algorithm for the container's children (§3.6e); free (the "
                    "default when layout is absent) is the only kind that reads child x/y.")
    gap: Optional[Length] = Field(
        default=None, description="Gap between children on both axes (overridden per axis "
                                  "by row_gap/column_gap).")
    row_gap: Optional[Length] = Field(default=None, description="Vertical gap between rows (+P1).")
    column_gap: Optional[Length] = Field(default=None, description="Horizontal gap between columns (+P1).")
    padding: Optional[Padding] = Field(
        default=None, description="Inset applied to the container box before placing children.")
    columns: Optional[int] = Field(
        default=None, description="grid: cells per row (row-major placement).")
    align: Optional[Literal["start", "center", "end", "stretch"]] = Field(
        default=None, description="CROSS-axis alignment of children (default start).")
    justify: Optional[Literal["start", "center", "end", "space-between", "space-around", "space-evenly"]] = Field(
        default=None, description="MAIN-axis packing/distribution of children.")


# --------------------------------------------------------------------------- #
#  Baseline grid — the vertical rhythm the spatial grid is measured against    #
# --------------------------------------------------------------------------- #
class BaselineGrid(FG):
    """The leading grid text baselines snap to.

    `Layout(kind="grid")` places boxes; it says nothing about what those boxes
    should be *divisible by*. That is what a baseline grid supplies, and its
    absence is visible: if body text is 10pt on 13pt leading and a module's
    height is not a multiple of 13, every row leaves a remainder at its foot and
    the horizontal gutters stop looking equal. The same increment is what aligns
    type across the gutter between columns and across the two leaves of a
    spread — which is exactly where `FlowRegion.column_fill: balance` and
    `CanvasObject.spread` need it.

    Declared once at `defs.baseline_grid` (the document default, and the only
    scope a flowed section has), overridden per page at
    `RenderingContract.baseline_grid`. It is inert until something opts in:
    a block snaps to it by setting `align_to_baseline` on its style.

    The increment IS the body leading — set them to the same value.
    """
    increment: Length = Field(
        description="Grid pitch: the distance between successive gridlines, and normally "
                    "the body text's `line_height`. Must be positive.")
    start: Optional[Length] = Field(
        default=None, description="Offset of the first gridline from `relative_to` "
                                  "(default 0).")
    relative_to: Optional[Literal["page", "top_margin"]] = Field(
        default=None, description="Datum the grid is measured from: the page edge, or the top "
                                  "content margin (default top_margin, so the grid follows the "
                                  "text block rather than the trim).")

    @model_validator(mode="after")
    def _increment_is_positive(self):
        raw = self.increment
        # The pattern is inlined rather than hoisted to a module constant: every
        # top-level declaration in this package is part of the import surface
        # (the surface golden enforces it), and this is an implementation detail.
        # `LENGTH_STR_RE` has already guaranteed a leading numeric part.
        number = float(raw) if isinstance(raw, (int, float)) else float(
            re.match(r"-?(?:\d+\.?\d*|\.\d+)", raw).group())
        if number <= 0:
            raise ValueError(
                "baseline_grid.increment must be positive: a zero pitch is infinitely "
                "many gridlines and a negative one marches up the page")
        return self


SizeMode = Literal["fixed", "hug", "fill"]


class Sizing(FG):
    """P4 content sizing. The field on objects is `sizing` (renamed from `size`
    to resolve the collision with IconObject.size)."""
    width: Optional[SizeMode] = Field(
        default=None, description="Width mode: fixed (authored box), hug (measure content; "
                                  "invalid on pure shapes), fill (share container free space).")
    height: Optional[SizeMode] = Field(
        default=None, description="Height mode: fixed (authored box), hug (measure content; "
                                  "invalid on pure shapes), fill (share container free space).")
    grow: Optional[float] = Field(
        default=None, description="Free-space share weight among fill siblings (default 1).")
    min: Optional[Annotated[list[Length], Field(min_length=2, max_length=2)]] = Field(
        default=None, description="[w, h] lower clamp applied when resolving hug/fill.")
    max: Optional[Annotated[list[Length], Field(min_length=2, max_length=2)]] = Field(
        default=None, description="[w, h] upper clamp applied when resolving hug/fill.")


class ClipSpec(FG):
    shape: Literal["rect", "ellipse", "path"] = Field(
        description="Clip region shape fitted to the object box.")
    radius: Optional[Length] = Field(
        default=None, description="rect: corner radius of the clip rectangle.")


ClipSpecOrBool = Union[bool, ClipSpec]


class Rotation(FG):
    angle: float = Field(description="Rotation in degrees, clockwise (+y-down coordinates).")
    center: Optional[Point] = Field(
        default=None, description="Rotation centre [x, y] (defaults to the box centre).")


RotationOrNumber = Union[float, int, Rotation]


class EffectObject(FG):
    color: Optional[Color] = Field(default=None, description="Effect colour.")
    blur: Optional[float] = Field(default=None, description="Blur radius of the effect.")
    dx: Optional[float] = Field(default=None, description="Horizontal effect offset (+x right).")
    dy: Optional[float] = Field(default=None, description="Vertical effect offset (+y down).")
    opacity: Optional[UnitInterval] = Field(default=None, description="Effect opacity in 0..1.")


Effect = Union[str, bool, EffectObject]


class EffectStackEntry(EffectObject):
    """One entry of the ordered per-object effect stack (2.4.0, W4/#48).

    Unlike the single `shadow`/`glow` fields, the stack is ORDERED and a
    kind may repeat; entries apply first→last (the last wraps outermost).
    Outside the deep-core profile (§8.5)."""

    kind: Literal["shadow", "glow"] = Field(
        description="Effect family the entry's parameters feed.")
    preset: Optional[str] = Field(
        default=None, description="Named preset of the kind (e.g. 'neon', "
                                  "'soft_shadow'); explicit params override it.")


class AppearancePass(FG):
    """One paint pass of the appearance stack (2.4.0, W4/#48): the object's
    geometry re-painted with this pass's fill/stroke, bottom→top in list
    order. Outside the deep-core profile (§8.5)."""

    fill: Optional[Paint] = Field(
        default=None, description="Pass fill paint (colour/gradient/pattern).")
    stroke: Optional[Paint] = Field(
        default=None, description="Pass stroke PAINT (P3: geometry in stroke_style).")
    stroke_style: Optional[StrokeStyleRef] = Field(
        default=None, description="Pass stroke geometry: a tokens.stroke_styles "
                                  "key or an inline Style bundle.")
    opacity: Optional[UnitInterval] = Field(
        default=None, description="Pass opacity in 0..1.")


class OuterRing(FG):
    color: Optional[Color] = Field(default=None, description="Ring stroke colour.")
    width: Optional[float] = Field(default=None, description="Ring stroke width.")
    gap: Optional[float] = Field(default=None, description="Gap between the object edge and the ring.")
    offset: Optional[float] = Field(default=None, description="Additional radial offset of the ring.")
    dash: Optional[Union[list[float], str]] = Field(
        default=None, description="Ring dash pattern (list of lengths or an SVG dash string).")
    opacity: Optional[UnitInterval] = Field(default=None, description="Ring opacity in 0..1.")


class AnchorObject(FG):
    ref: str = Field(description="Target object id the anchor attaches to (must resolve; §3.1).")
    port: Optional[str] = Field(
        default=None, description="Named port on the target (a key of its `ports` map).")


Anchor = Union[str, Point, AnchorObject]


class Number(FG):
    series: str = Field(description="Counter series name this element numbers into (defs.counters).")
    parent: Optional[str] = Field(
        default=None, description="Parent series for compound numbers (e.g. figures per chapter).")
    reset_with: Optional[str] = Field(
        default=None, description="Series whose increment resets this one.")
    format: Optional[NumberFormat] = Field(
        default=None, description="Number rendering: decimal or roman/alpha variants.")
    prefix: Optional[str] = Field(default=None, description="Literal text before the number.")
    suffix: Optional[str] = Field(default=None, description="Literal text after the number.")
