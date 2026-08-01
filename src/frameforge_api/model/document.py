"""Tokens, defs, targets, and `Document`: the root of the contract.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union
from pydantic import Field

from .assets import AssetDef, FontDefOrName
from .base import Color, FG, NumberFormat
from .humanize import Humanize
from .page import CanvasSpec, PageMaster, PageProducer, TextContract
from .style import Fill, StrokeStyle, Style
from .version import HEAD_VERSION


# --------------------------------------------------------------------------- #
#  Tokens, defs, targets, document root                                       #
# --------------------------------------------------------------------------- #
class CounterDef(FG):
    start: Optional[int] = Field(default=None, description="Initial counter value (default 1).")
    reset_with: Optional[str] = Field(
        default=None, description="Series whose increment resets this counter.")
    format: Optional[NumberFormat] = Field(
        default=None, description="Number rendering: decimal or roman/alpha variants.")


class Tokens(FG):
    colors: Optional[dict[str, Color]] = Field(
        default=None, description="Named colours; referenced anywhere a Color is accepted.")
    fonts: Optional[dict[str, FontDefOrName]] = Field(
        default=None, description="Named fonts (family string or FontDef; src+hash = pinned).")
    text_styles: Optional[dict[str, Style]] = Field(
        default=None, description="Named text styles (legacy namespace; superseded by `styles`, "
                                  "still resolved first by the renderer).")
    styles: Optional[dict[str, Style]] = Field(
        default=None, description="Named styles; referenced by `style`/`class`.")
    stroke_styles: Optional[dict[str, StrokeStyle]] = Field(
        default=None, description="Named stroke-geometry bundles; referenced by `stroke_style`.")
    fill_styles: Optional[dict[str, Fill]] = Field(
        default=None, description="Named fill paints; referenced by `fill`.")
    glyph_map: Optional[dict[str, str]] = Field(
        default=None, description="Icon glyph names to characters (IconObject.glyph keys).")


class Defs(FG):
    params: Optional[dict[str, Union[float, int, str]]] = Field(
        default=None, description="Named document parameters (numbers, or '=expr' strings over "
                                  "earlier parameters). Any '=expr' string field in the document "
                                  "resolves against them before validation — geometry and labels "
                                  "driven by the same numbers.")
    tokens: Optional[Tokens] = Field(
        default=None, description="Design tokens: colours, fonts, styles, stroke styles, glyphs.")
    counters: Optional[dict[str, CounterDef]] = Field(
        default=None, description="Counter series definitions for `number` fields.")
    masters: Optional[dict[str, PageMaster]] = Field(
        default=None, description="Named page masters referenced by Page.master/FlowSection.master.")
    assets: Optional[dict[str, AssetDef]] = Field(
        default=None, description="Pinned external assets referenced by `src` (§9.3).")
    data: Optional[dict] = Field(
        default=None, description="Data sources (e.g. CSL-JSON bibliographies) keyed by name.")
    # Grammar-allowed but OUT of the deep core profile — accepted loosely so they
    # are not hard errors; validate.py reports their presence as a warning.
    symbols: Optional[dict] = Field(
        default=None, description="Reusable symbol definitions (grammar SymbolDef), expanded by "
                                  "`use` objects; out of the deep core profile — accepted "
                                  "loosely, reported as a warning (§8.5).")
    components: Optional[dict] = Field(
        default=None, description="Component definitions (grammar ComponentDef); out of the deep "
                                  "core profile — accepted loosely, warned (§8.5).")
    ontology: Optional[dict] = Field(
        default=None, description="Ontology/annotation vocabulary; out of the deep core "
                                  "profile — accepted loosely, warned (§8.5).")


class TargetAdjustments(FG):
    font_scale: Optional[float] = Field(
        default=None, description="Multiplier applied to font sizes for this target.")
    hide: Optional[list[str]] = Field(
        default=None, description="Object ids omitted when rendering this target.")
    padding_delta: Optional[float] = Field(
        default=None, description="Additive padding adjustment for this target.")


class RenderTarget(FG):
    name: str = Field(description="Target name (selects the canvas + adjustments at render).")
    canvas: CanvasSpec = Field(description="Canvas the document is re-targeted onto.")
    adjustments: Optional[TargetAdjustments] = Field(
        default=None, description="Per-target reflow adjustments (font_scale/hide/padding_delta).")


SEMVER_RE = r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"


class Document(FG):
    dsl: Literal["FrameForge"] = Field(description="Format marker; always 'FrameForge'.")
    version: Annotated[str, Field(pattern=SEMVER_RE)] = Field(
        description=f"Spec version the document targets (semver; HEAD is {HEAD_VERSION}; older targets like 2.2.0 remain valid).")
    profile: Optional[Literal["deck", "book", "letter", "report", "diagram", "mixed"]] = Field(
        default=None, description="Document genre hint (does not change validation).")
    title: Optional[str] = Field(default=None, description="Document title (metadata).")
    description: Optional[str] = Field(default=None, description="Document description (metadata).")
    lang: Optional[str] = Field(default=None, description="BCP-47 default language of the document.")
    defs: Optional[Defs] = Field(
        default=None, description="Shared definitions: tokens, counters, masters, assets, data.")
    targets: Optional[list[RenderTarget]] = Field(
        default=None, description="Named render targets (canvas + adjustments).")
    pages: list[PageProducer] = Field(
        min_length=1, description="Page producers: fixed pages (mode: page) and flowed "
                                  "sections (mode: flow), in document order.")
    meta: Optional[dict] = Field(
        default=None, description="Free-form document metadata bag.")
    humanize: Optional[Humanize] = Field(
        default=None, description="Document-level humanize default: a seeded imperfection 'hand' "
                                  "applied to every object unless an object (or its container) "
                                  "declares its own. Absent = off; renders stay mechanically exact.")
    text_contract: Optional[TextContract] = Field(
        default=None, description="Top-level text contract (renderer convenience; the normative "
                                  "home is a master/page RenderingContract.text — validator warns).")
