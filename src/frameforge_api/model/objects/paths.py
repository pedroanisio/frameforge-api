"""Path segment algebra (G-1), and the two objects that carry it.
"""
from __future__ import annotations

from typing import Literal, Optional, Union
from pydantic import ConfigDict, Field, model_validator

from ..base import Point
from .base import ObjBase
from ..style import Fill, Paint


# --------------------------------------------------------------------------- #
#  Path segment algebra (G-1)                                                   #
# --------------------------------------------------------------------------- #
# A path's `d` may be either the SVG path-data string (the compiled view) or a
# structured list of typed segments — one SVG command per segment, `[cmd, *coords]`.
# Lowercase command letters are relative, uppercase absolute (mirroring SVG path
# data). Typing each segment is what lets the JSON Schema validate geometry shape
# and arity instead of accepting an opaque array; the `d` string remains the
# compiled view of the same geometry (roadmap item G-1).
PathCommand = Literal[
    "M", "m", "L", "l", "H", "h", "V", "v",
    "C", "c", "S", "s", "Q", "q", "T", "t", "A", "a", "Z", "z",
]


_SegMove = tuple[Literal["M", "m"], float, float]                      # moveto x y


_SegLine = tuple[Literal["L", "l"], float, float]                      # lineto x y


_SegHoriz = tuple[Literal["H", "h"], float]                            # horizontal x


_SegVert = tuple[Literal["V", "v"], float]                             # vertical y


_SegCubic = tuple[Literal["C", "c"], float, float, float, float, float, float]  # x1 y1 x2 y2 x y


_SegSmooth = tuple[Literal["S", "s"], float, float, float, float]      # x2 y2 x y


_SegQuad = tuple[Literal["Q", "q"], float, float, float, float]        # x1 y1 x y


_SegTquad = tuple[Literal["T", "t"], float, float]                     # x y


_SegArc = tuple[Literal["A", "a"], float, float, float, float, float, float, float]  # rx ry rot large sweep x y


_SegClose = tuple[Literal["Z", "z"]]                                   # closepath


# One typed segment: the first element is the command, the rest its coordinates.
PathSeg = Union[
    _SegMove, _SegLine, _SegHoriz, _SegVert, _SegCubic,
    _SegSmooth, _SegQuad, _SegTquad, _SegArc, _SegClose,
]


class Path(ObjBase):
    type: Literal["path"] = Field(description="Discriminator: SVG path geometry.")
    # SVG `d` string, or structured `[[cmd, *coords], ...]` segments (G-1).
    d: Union[str, list[PathSeg]] = Field(
        union_mode="left_to_right",
        description="Path data: an SVG `d` string, or typed segments [[cmd, *coords], ...] "
                    "(uppercase absolute, lowercase relative; G-1 compiled view).")
    fill: Optional[Fill] = Field(default=None, description="Fill paint of the enclosed region.")
    stroke: Optional[Paint] = Field(
        default=None, description="Stroke paint only (P3); geometry lives in `stroke_style`.")


class Curve(ObjBase):
    """Renderer-shortcut alias for a single cubic Bézier. Deprecated; codemod → path.

    `c1`/`c2` are accepted as legacy aliases of `control1`/`control2` and are
    normalised to the canonical keys; setting both with different values is an
    error (mirrors the GradientStop offset→position pattern)."""
    type: Literal["curve", "bezier"] = Field(
        description="Discriminator: DEPRECATED single cubic Bézier (codemod normalises to path).")
    from_: Point = Field(alias="from", description="Start point [x, y].")
    to: Point = Field(description="End point [x, y].")
    control1: Optional[Point] = Field(
        default=None, description="First control point (defaults to `from`); legacy alias `c1`.")
    control2: Optional[Point] = Field(
        default=None, description="Second control point (defaults to control1); legacy alias `c2`.")
    stroke: Optional[Paint] = Field(
        default=None, description="Stroke paint only (P3); geometry lives in `stroke_style`.")
    fill: Optional[Fill] = Field(default=None, description="Fill paint of the enclosed region.")
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _canonical_controls(cls, v):
        # Normalise the legacy short keys onto the canonical ones; reject a
        # contradictory pair instead of silently preferring one side.
        if isinstance(v, dict):
            for short, canon in (("c1", "control1"), ("c2", "control2")):
                if short in v:
                    v = dict(v)
                    sv = v.pop(short)
                    if v.get(canon) is not None and v[canon] != sv:
                        raise ValueError(
                            f"`{short}` and `{canon}` are aliases and disagree "
                            f"({sv!r} vs {v[canon]!r}); set exactly one (or equal values)")
                    v[canon] = sv
        return v
