"""Fonts and assets — the external files a document pins by hash.
"""
from __future__ import annotations

from typing import Literal, Optional, Union
from pydantic import Field

from .base import FG


# --------------------------------------------------------------------------- #
#  Fonts, assets                                                              #
# --------------------------------------------------------------------------- #
class FontDef(FG):
    family: str = Field(description="Font family name as resolved by fontconfig.")
    src: Optional[str] = Field(
        default=None, description="Font file source (path/URL); with `hash`, pins the font (P4).")
    hash: Optional[str] = Field(
        default=None, description="Content hash of `src`; src+hash = a PINNED font, required "
                                  "for content-sized text (§9.6 determinism).")
    fallback: Optional[list[str]] = Field(
        default=None, description="Fallback family names, in preference order.")
    weight: Optional[Union[int, str]] = Field(
        default=None, description="Weight this face provides (number or keyword).")
    style: Optional[Literal["normal", "italic", "oblique"]] = Field(
        default=None, description="Style this face provides.")


FontDefOrName = Union[str, FontDef]


class AssetDef(FG):
    src: str = Field(description="Asset source (path/URL); resolved at expansion, never at render (§9.3).")
    hash: Optional[str] = Field(
        default=None, description="Content hash pinning the asset bytes (§9.3 hermetic expansion).")
    kind: Optional[Literal["image", "icon_font", "font", "data"]] = Field(
        default=None, description="Asset category hint.")
    media_type: Optional[str] = Field(
        default=None, description="MIME type of the asset (e.g. image/png).")
