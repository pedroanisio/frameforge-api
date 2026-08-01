"""Content-bearing visual objects: text, image, icon, bullet list, dimension.
"""
from __future__ import annotations

from typing import Literal, Optional, Union
from pydantic import ConfigDict, Field, model_validator

from ..base import Color, Length
from ..inline import Inline, Span
from ..layout import Anchor, ClipSpec
from .base import ObjBase


class Text(ObjBase):
    type: Literal["text"] = Field(description="Discriminator: a text block laid out inside `box`.")
    text: Optional[str] = Field(
        default=None, description="Plain text content; exactly one of `text` or `spans` (XOR).")
    spans: Optional[list[Inline]] = Field(
        default=None, description="Styled inline runs; exactly one of `text` or `spans` (XOR).")
    field: Optional[Union[Literal["page", "pages"], dict]] = Field(
        default=None, description="Running field substitution: 'page'/'pages' counters, or the "
                                  "grammar's {string: <name>} form for named strings.")

    @model_validator(mode="after")
    def _one_of_text_spans(self):
        if (self.text is None) == (self.spans is None):
            raise ValueError("a text object needs exactly one of `text` or `spans`")
        return self


class Image(ObjBase):
    type: Literal["image"] = Field(description="Discriminator: raster/vector image placed in `box`.")
    src: str = Field(
        description="Image source: a literal path/URL/data URI or a defs.assets key "
                    "(unpinned URLs fetched at render are non-conformant; §9.3).")
    alt: Optional[str] = Field(
        default=None, description="Accessibility alternative text (a11y lint warns when absent).")
    actual_text: Optional[str] = Field(
        default=None, description="Full replacement text for tagged/a11y export.")
    placeholder: Optional[bool] = Field(
        default=None, description="Render as a placeholder frame instead of fetching `src`.")
    preserve_aspect_ratio: Optional[Union[bool, str]] = Field(
        default=None, description="True/False, or an SVG preserveAspectRatio string.")
    clip: Optional[Union[bool, str, ClipSpec]] = Field(
        default=None, description="Clip the image to its box: bool, shape name, or ClipSpec.")
    radius: Optional[Length] = Field(default=None, description="Corner radius of the image frame.")
    label: Optional[str] = Field(default=None, description="Short caption/label drawn with the image.")


class Icon(ObjBase):
    type: Literal["icon"] = Field(description="Discriminator: a single glyph drawn centred in `box`.")
    glyph: str = Field(
        description="The glyph: a literal character or a tokens.glyph_map key.")
    color: Optional[Color] = Field(default=None, description="Glyph colour.")
    font: Optional[str] = Field(
        default=None, description="Icon font: a tokens.fonts key (pinned icon font).")
    size: Optional[float] = Field(
        default=None, description="Glyph size in pt/px (defaults to ~80% of the box); NB: icon "
                                  "keeps `size` — content sizing is `sizing`.")


class BulletList(ObjBase):
    type: Literal["bullet_list"] = Field(
        description="Discriminator: absolutely-placed bullet list (flow lists are `list`).")
    items: list[Union[str, Span]] = Field(description="List items: plain strings or styled spans.")
    marker: Optional[str] = Field(default=None, description="Bullet marker character (default '•').")
    marker_color: Optional[Color] = Field(
        default=None, description="Marker colour (defaults to the text colour).")
    gap: Optional[float] = Field(
        default=None, description="Inter-item pitch (floored at one line height when wrapping).")
    indent: Optional[float] = Field(
        default=None, description="Text indent right of the marker.")


class Dimension(ObjBase):
    """P3 §3.10 composite anchored dimension."""
    type: Literal["dimension"] = Field(
        description="Discriminator: measured dimension annotation between two anchors (§3.10).")
    kind: Literal["linear", "aligned", "angular", "radial", "diameter"] = Field(
        description="Measurement kind; radial/diameter measure from a centre anchor.")
    from_: Anchor = Field(
        alias="from", description="Measured-from anchor: [x, y] point (object/port anchors "
                                  "resolve in the measure pass).")
    to: Anchor = Field(
        description="Measured-to anchor ([x, y] point; the centre for radial/diameter).")
    value: Optional[Union[float, Literal["auto"]]] = Field(
        default=None, description="Measured value; 'auto' computes it from the resolved anchors.")
    text: Optional[str] = Field(default=None, description="Explicit label text override.")
    prefix: Optional[str] = Field(default=None, description="Label prefix (e.g. 'Ø', 'R').")
    suffix: Optional[str] = Field(default=None, description="Label suffix (e.g. a unit).")
    offset: Optional[Length] = Field(
        default=None, description="Dimension-line offset from the measured feature.")
    arrows: Optional[Literal["both", "first", "second", "none"]] = Field(
        default=None, description="Which ends carry arrowheads (default both).")
    text_style: Optional[str] = Field(
        default=None, description="Label text style: a tokens.text_styles key.")
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
