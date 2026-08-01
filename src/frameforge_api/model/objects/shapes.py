"""The primitive shapes: rect, ellipse, circle, line, polyline, polygon, star.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import ConfigDict, Field, model_validator

from ..base import Length, Point, ShapeDirection, UnitInterval
from ..layout import Anchor
from .base import ObjBase
from ..style import Fill, Paint


# --------------------------------------------------------------------------- #
#  Visual objects (core profile + DimensionObject; renderer-shortcut aliases) #
# --------------------------------------------------------------------------- #
class Rect(ObjBase):
    type: Literal["rect"] = Field(description="Discriminator: axis-aligned rectangle drawn at `box`.")
    fill: Optional[Paint] = Field(
        default=None, description="Fill paint: 'none'/colour/gradient/pattern/image or a tokens key.")
    radius: Optional[Length] = Field(default=None, description="Corner radius.")
    stroke: Optional[Paint] = Field(
        default=None, description="Stroke paint only (P3); geometry lives in `stroke_style`.")


class Ellipse(ObjBase):
    type: Literal["ellipse"] = Field(description="Discriminator: ellipse by centre + radii.")
    center: Point = Field(description="Centre [cx, cy] in parent-local space.")
    rx: float = Field(description="Horizontal radius.")
    ry: float = Field(description="Vertical radius.")
    fill: Optional[Fill] = Field(
        default=None, description="Fill paint: 'none'/colour/gradient/pattern/image or a tokens key.")
    stroke: Optional[Paint] = Field(
        default=None, description="Stroke paint only (P3); geometry lives in `stroke_style`.")


class Circle(ObjBase):
    """Renderer-shortcut alias for an ellipse with rx==ry. DEPRECATED at HEAD;
    `ff-codemod` normalises it to `ellipse`.

    Still valid, and will stay valid for the life of the 2.x line: dropping a
    union member is exactly what `COMPATIBILITY = "backward"` forbids. Carries
    the JSON Schema `deprecated` keyword so a tool can see the status without
    reading this sentence."""
    model_config = ConfigDict(extra="forbid", json_schema_extra={"deprecated": True})
    type: Literal["circle"] = Field(
        description="Discriminator: DEPRECATED alias of ellipse with rx==ry "
                    "(`ff-codemod` normalises).")
    center: Point = Field(description="Centre [cx, cy] in parent-local space.")
    r: float = Field(description="Radius.")
    fill: Optional[Fill] = Field(
        default=None, description="Fill paint: 'none'/colour/gradient/pattern/image or a tokens key.")
    stroke: Optional[Paint] = Field(
        default=None, description="Stroke paint only (P3); geometry lives in `stroke_style`.")


class Line(ObjBase):
    type: Literal["line"] = Field(description="Discriminator: straight segment from `from` to `to`.")
    from_: Anchor = Field(
        alias="from", description="Start anchor: [x, y] point, an object id string, or {ref, port}.")
    to: Anchor = Field(description="End anchor: [x, y] point, an object id string, or {ref, port}.")
    stroke: Optional[Paint] = Field(
        default=None, description="Stroke paint only (P3); geometry lives in `stroke_style`.")
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Polyline(ObjBase):
    type: Literal["polyline"] = Field(description="Discriminator: open (or closed) point chain.")
    points: list[Point] = Field(
        min_length=2, description="Vertices [x, y], parent-local, in draw order (>= 2).")
    closed: Optional[bool] = Field(
        default=None, description="Close the chain back to the first point (fillable region).")
    fill: Optional[Fill] = Field(
        default=None, description="Fill paint (applies when closed).")
    stroke: Optional[Paint] = Field(
        default=None, description="Stroke paint only (P3); geometry lives in `stroke_style`.")
    direction: Optional[ShapeDirection] = Field(
        default=None, description="Winding order of the outline; with `fill_rule` it decides\n                                  which enclosed regions are holes.")


class Polygon(ObjBase):
    """Renderer-shortcut alias for a closed polyline. DEPRECATED; `ff-codemod`
    normalises it to `polyline` + `closed: true`.

    Still valid for the life of the 2.x line, and marked with the JSON Schema
    `deprecated` keyword so tooling can see that without parsing prose."""
    model_config = ConfigDict(extra="forbid", json_schema_extra={"deprecated": True})
    type: Literal["polygon"] = Field(
        description="Discriminator: DEPRECATED alias of a closed polyline "
                    "(`ff-codemod` normalises).")
    points: list[Point] = Field(
        min_length=3, description="Vertices [x, y], parent-local, in draw order (>= 3).")
    fill: Optional[Fill] = Field(default=None, description="Fill paint of the closed region.")
    stroke: Optional[Paint] = Field(
        default=None, description="Stroke paint only (P3); geometry lives in `stroke_style`.")
    direction: Optional[ShapeDirection] = Field(
        default=None, description="Winding order of the outline; with `fill_rule` it decides\n                                  which enclosed regions are holes.")


#: Whether the figure alternates between two radii (a star) or uses one (a
#: regular polygon). Named rather than inlined so a consumer can reason about
#: the choice without reaching into the model.
StarType = Literal["star", "polygon"]


class Star(ObjBase):
    """A parametric star or regular polygon.

    `Polygon` takes an explicit vertex list, so a five-point star was ten
    hand-computed points with the parameters discarded — nothing downstream could
    recover that it *was* a star, or restyle it as a seven-point one. This keeps
    the parameters, which is what makes the shape editable rather than merely
    drawn.

    Orientation is the inherited `rotation`, not a field of its own: a rotated
    star is a rotated object, and duplicating the concept would let the two
    disagree. Absent, the first point is at twelve o'clock.

    `star_type` decides whether `inner_radius` is meaningful: a star alternates
    between the two radii, a polygon has only the outer one. Supplying the wrong
    combination is an error rather than a silent reinterpretation — the same rule
    the gradient geometry validator applies, and for the same reason: the
    agent-native surface has exactly one meaning.
    """
    type: Literal["star"] = Field(
        description="Discriminator: a parametric star or regular polygon.")
    star_type: StarType = Field(
        default="star", description="Alternate between two radii (star) or use one (polygon).")
    center: Point = Field(description="Centre [x, y], parent-local.")
    points: int = Field(
        ge=3, description="Number of points (star) or sides (polygon); at least 3.")
    outer_radius: float = Field(gt=0, description="Distance from centre to the outer vertices.")
    inner_radius: Optional[float] = Field(
        default=None, gt=0,
        description="Distance from centre to the inner vertices. Required for a star, "
                    "forbidden for a polygon.")
    outer_roundness: Optional[UnitInterval] = Field(
        default=None, description="Corner rounding at the outer vertices, 0..1.")
    inner_roundness: Optional[UnitInterval] = Field(
        default=None, description="Corner rounding at the inner vertices, 0..1.")
    direction: Optional[ShapeDirection] = Field(
        default=None, description="Winding order of the outline; with `fill_rule` it decides "
                                  "which enclosed regions are holes.")
    fill: Optional[Fill] = Field(default=None, description="Fill paint of the enclosed region.")
    stroke: Optional[Paint] = Field(
        default=None, description="Stroke paint only (P3); geometry lives in `stroke_style`.")

    @model_validator(mode="after")
    def _radii_match_the_figure(self):
        if self.star_type == "polygon":
            if self.inner_radius is not None:
                raise ValueError(
                    "`inner_radius` is star-only geometry; a regular polygon has one radius "
                    "(drop it, or set star_type='star')")
        elif self.inner_radius is None:
            raise ValueError(
                "a star needs `inner_radius` — without it there is no star, only a polygon "
                "that lost its type (set star_type='polygon' if that is what was meant)")
        return self
