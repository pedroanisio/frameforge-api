"""Connector — typed at HEAD to match the renderer's implemented surface.
"""
from __future__ import annotations

from typing import Literal, Optional, Union
from pydantic import ConfigDict, Field, model_validator

from ..base import Box, FG, Point
from .base import ObjBase
from ..style import Paint, StyleRef


# --------------------------------------------------------------------------- #
#  Connector (typed at HEAD to match the renderer's implemented surface)      #
# --------------------------------------------------------------------------- #
class ConnectorEndpoint(FG):
    """Connector endpoint attached to an object or an explicit point.

    Mirrors the renderer's anchor resolver: `ref` (accepting the legacy `object`
    key) names a target object on the same page; `port` picks a named port,
    else `side` (or a port-named side) picks a box edge midpoint offset by
    `offset`; a `point` short-circuits to fixed page coordinates and wins over
    `ref`. Without port/side/point the endpoint is the target's box centre."""
    ref: Optional[str] = Field(
        default=None, description="Target object id on the same page (legacy key `object` is "
                                  "accepted and normalised); must resolve (§3.1).")
    port: Optional[str] = Field(
        default=None, description="Named port of the target (key of its `ports` map); a "
                                  "side-named port falls back to that box side.")
    side: Optional[Literal["north", "south", "east", "west"]] = Field(
        default=None, description="Box side to attach to (edge midpoint) when no port matches.")
    offset: Optional[float] = Field(
        default=None, description="Slide along the chosen side: +x for north/south, +y for "
                                  "east/west (ignored for ports/points).")
    point: Optional[Point] = Field(
        default=None, description="Explicit [x, y] page-space endpoint; takes precedence over `ref`.")

    @model_validator(mode="before")
    @classmethod
    def _accept_object_key(cls, v):
        # The renderer (and the committed fixtures) accept `object` for the
        # target id; normalise it onto the canonical `ref`.
        if isinstance(v, dict) and "ref" not in v and "object" in v:
            v = dict(v)
            v["ref"] = v.pop("object")
        return v

    @model_validator(mode="after")
    def _ref_or_point(self):
        if self.ref is None and self.point is None:
            raise ValueError("a connector endpoint needs `ref` (an object id) or `point`")
        return self


ConnectorAnchor = Union[Point, ConnectorEndpoint]


class ConnectorRoute(FG):
    """Optional routing between the endpoints. Authored `points` always win:
    the renderer draws the polyline start → points… → end verbatim. With
    `kind: "orthogonal"` and NO points, the renderer computes a deterministic
    axis-aligned elbow chain from the endpoint attachment sides (perpendicular
    stubs, midpoint/outermost/corner rules — §3.11); `straight`/`curved`
    remain advisory. Legacy key `type` is accepted for `kind`."""
    kind: Optional[Literal["straight", "orthogonal", "curved"]] = Field(
        default=None, description="Routing kind (legacy key `type` accepted). `orthogonal` "
                                  "with no `points` computes real elbows from the endpoint "
                                  "sides; authored `points` always win; `straight`/`curved` "
                                  "are advisory.")
    points: Optional[list[Point]] = Field(
        default=None, description="Intermediate waypoints [x, y] in page space, in order.")

    @model_validator(mode="before")
    @classmethod
    def _accept_type_key(cls, v):
        if isinstance(v, dict) and "kind" not in v and "type" in v:
            v = dict(v)
            v["kind"] = v.pop("type")
        return v


class ConnectorLabel(FG):
    text: str = Field(description="Label text drawn in `box`.")
    box: Box = Field(description="Label box [x, y, w, h] in page space (not auto-placed).")
    style: Optional[StyleRef] = Field(
        default=None, description="Label text style: a tokens key or an inline Style.")


class Connector(ObjBase):
    type: Literal["connector"] = Field(
        description="Discriminator: anchored connector line/polyline between two endpoints.")
    from_: ConnectorAnchor = Field(
        alias="from", description="Start endpoint: [x, y] point or {ref|object, port|side, offset, point}.")
    to: ConnectorAnchor = Field(
        description="End endpoint: [x, y] point or {ref|object, port|side, offset, point}.")
    route: Optional[ConnectorRoute] = Field(
        default=None, description="Optional waypoint route between the endpoints.")
    label: Optional[ConnectorLabel] = Field(
        default=None, description="Optional boxed text label (drawn at its own box).")
    stroke: Optional[Paint] = Field(
        default=None, description="Stroke paint only (P3); geometry + arrow_* live in `stroke_style`.")
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
