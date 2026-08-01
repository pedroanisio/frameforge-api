"""The closed base and the pattern-gated scalars everything else is built from.

`FG` is where `extra="forbid"` is decided once, for every model in the contract.
The `*_RE` patterns are the reason a bad unit fails at schema time rather than
coercing to a default downstream.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
#  Base + scalar value types                                                  #
# --------------------------------------------------------------------------- #
class FG(BaseModel):
    """Closed base: unknown keys are errors (the closed-model decision)."""
    model_config = ConfigDict(extra="forbid")


# A Length is a number (points) or a CSS-ish string ending in a known unit.
# pt/px/mm/in/cm absolute; % and fr are relative (resolved in §3.4/§3.6g).
# The string branch is pattern-gated to the units the toolchain resolves
# (renderer geometry.num + the relative %/fr contexts), so '12ptx' fails at
# schema time instead of silently coercing to a default.
LENGTH_STR_RE = r"^-?(?:\d+\.?\d*|\.\d+)(?:pt|px|pc|mm|cm|in|em|rem|%|fr)$"


ANGLE_STR_RE = r"^-?(?:\d+\.?\d*|\.\d+)(?:deg|rad|grad|turn)$"


PERCENT_STR_RE = r"^-?(?:\d+\.?\d*|\.\d+)%$"


DASH_TOKEN_RE = r"(?:\d+\.?\d*|\.\d+)(?:pt|px|pc|mm|cm|in|em|rem|%)?"


DASH_ARRAY_STR_RE = rf"^\s*{DASH_TOKEN_RE}(?:\s*(?:,\s*|\s+){DASH_TOKEN_RE})*\s*$"


Length = Union[
    float, int,
    Annotated[str, Field(
        pattern=LENGTH_STR_RE,
        description="Length string: '<n><unit>' with unit pt|px|pc|mm|cm|in|em|rem "
                    "(absolute; bare numbers are pt/px, treated 1:1) or %|fr "
                    "(relative — % resolves against the container content-box, "
                    "fr only inside a layout container; spec §3.4/§3.6g).")],
]


DashArrayString = Annotated[str, Field(
    pattern=DASH_ARRAY_STR_RE,
    description="SVG dash list as whitespace/comma-separated non-negative lengths.",
)]


DashArray = Union[Literal["none"], list[Length], DashArrayString]


Color = str                 # hex (#rgb[a]/#rrggbb[aa]), CSS name, or a tokens.colors key


UnitInterval = Annotated[float, Field(
    ge=0.0, le=1.0, description="Unit-interval number in 0.0..1.0.")]


Point = Annotated[list[float], Field(
    min_length=2, max_length=2,
    description="[x, y] coordinate pair in the parent-local space (top-left origin, +y down).")]


Box = Annotated[list[Length], Field(
    min_length=4, max_length=4,
    description="[x, y, w, h] box, top-left origin, +y down; x/y are parent-local "
                "(page space at the root); w/h may be relative (%/fr) inside layout "
                "containers (spec §3.4/§3.6).")]


Padding = Union[Length, Annotated[list[Length], Field(
    min_length=1, max_length=4,
    description="CSS-shorthand padding: 1..4 lengths (all / v h / t h b / t r b l).")]]


NumberFormat = Literal["decimal", "lower-roman", "upper-roman", "lower-alpha", "upper-alpha"]


PagePreset = Literal[
    "A3", "A4", "A5", "Letter", "Legal", "Tabloid",
    "deck-16x9", "deck-4x3", "square", "phone", "tablet", "web",
    # Screen resolution ladder (device px; mirror CanvasResolver.PRESETS).
    "qhd", "4k", "uhd", "8k",
    # Social-media canvases — pixel sizes mirror CanvasResolver.PRESETS.
    "instagram-square", "instagram-portrait", "instagram-landscape", "instagram-story",
    "facebook-post", "facebook-cover", "facebook-story",
    "twitter-post", "twitter-header", "linkedin-post", "linkedin-cover",
    "youtube-thumbnail", "youtube-banner", "tiktok-video", "pinterest-pin",
    "snapchat", "story",
    # Aspect-ratio aliases (canonical canvas at the named ratio).
    "1x1", "4x5", "5x4", "9x16", "16x9", "2x3", "3x2", "1.91x1", "3x1",
    # Book trim sizes (final width×height after cutting; points @ 72dpi —
    # mirror CanvasResolver.PRESETS). Names follow publishing convention.
    "book-pocket", "book-mass-market", "book-trade", "book-novel", "book-digest",
    "book-6x9", "book-7x10", "book-8x10", "book-textbook",
    "book-square-8", "book-picture", "book-square-10",
    "book-coffee-table", "book-art-10x12", "book-art-11x14",
]


Units = Literal["pt", "px", "mm", "in", "cm"]


Align = Literal["left", "center", "right"]


VAlign = Literal["top", "middle", "bottom"]
