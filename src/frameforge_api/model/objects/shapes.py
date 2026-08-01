"""The primitive shapes: rect, ellipse, circle, line, polyline, polygon.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import ConfigDict, Field

from ..base import Length, Point
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
    """Renderer-shortcut alias for an ellipse with rx==ry. Deprecated at HEAD;
    the codemod normalises it to `ellipse`."""
    type: Literal["circle"] = Field(
        description="Discriminator: DEPRECATED alias of ellipse with rx==ry (codemod normalises).")
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


class Polygon(ObjBase):
    """Renderer-shortcut alias for a closed polyline. Deprecated; codemod normalises."""
    type: Literal["polygon"] = Field(
        description="Discriminator: DEPRECATED alias of a closed polyline (codemod normalises).")
    points: list[Point] = Field(
        min_length=3, description="Vertices [x, y], parent-local, in draw order (>= 3).")
    fill: Optional[Fill] = Field(default=None, description="Fill paint of the closed region.")
    stroke: Optional[Paint] = Field(
        default=None, description="Stroke paint only (P3); geometry lives in `stroke_style`.")
