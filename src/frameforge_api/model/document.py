"""Tokens, defs, targets, and `Document`: the root of the contract.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union
from pydantic import Field

from .assets import AssetDef, FontDefOrName
from .base import Color, FG, NumberFormat, UnitInterval
from .humanize import Humanize
from .layout import BaselineGrid
from .objects import VisualObject
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
        default=None, deprecated=True,
        description="DEPRECATED namespace, superseded by `styles` — but NOT an alias of it. "
                    "Both maps stay live and the renderer resolves `text_styles` FIRST, so a "
                    "name declared in both silently renders as this one and the `styles` "
                    "definition is dead. Every other legacy spelling in the contract collapses "
                    "at parse time; this one cannot, because collapsing it would change which "
                    "definition wins. `ff-codemod` merges the two (this map winning, as the "
                    "renderer does) and reports every shadowed name.")
    styles: Optional[dict[str, Style]] = Field(
        default=None, description="Named styles; referenced by `style`/`class`.")
    stroke_styles: Optional[dict[str, StrokeStyle]] = Field(
        default=None, description="Named stroke-geometry bundles; referenced by `stroke_style`.")
    fill_styles: Optional[dict[str, Fill]] = Field(
        default=None, description="Named fill paints; referenced by `fill`.")
    glyph_map: Optional[dict[str, str]] = Field(
        default=None, description="Icon glyph names to characters (IconObject.glyph keys).")


class ColorProfileDef(FG):
    """A declared ICC colour profile: what device-independent colour is measured against.

    Pinned by `hash` for the same reason `FontDef` is — a profile that silently
    changes reprints the whole job in different colour, and the failure is only
    visible on paper.
    """
    space: Literal["cmyk", "rgb", "gray", "lab", "spot"] = Field(
        description="Colour space the profile describes; fixes how many components a value has.")
    src: Optional[str] = Field(
        default=None, description="Path or URL to the .icc/.icm profile. Absent = the renderer's "
                                  "built-in profile for `space`.")
    hash: Optional[str] = Field(
        default=None, description="Content hash of the profile file ('sha256:<hex>'), pinning it "
                                  "the way FontDef.hash pins a font.")
    name: Optional[str] = Field(
        default=None, description="Human-readable profile name, e.g. 'Coated FOGRA39 (ISO 12647-2:2004)'.")
    rendering_intent: Optional[Literal["perceptual", "relative-colorimetric",
                                       "saturation", "absolute-colorimetric"]] = Field(
        default=None, description="Conversion intent used when transforming into this profile.")
    total_ink_limit: Optional[float] = Field(
        default=None, gt=0.0, le=4.0,
        description="Maximum TOTAL ink coverage this press condition accepts, as the sum of a "
                    "CmykColor's four 0..1 components — so the scale runs 0..4 and 3.0 is the "
                    "common '300%' sheet-fed limit. `CmykColor` bounds each separation "
                    "independently, which leaves c=m=y=k=1.0 (400%) structurally legal and "
                    "unprintable: it floods, offsets and will not dry. Declaring the cap here "
                    "is what gives the engine's validator something to check a resolved paint "
                    "against — this package cannot do it, because the coverage of a gradient, "
                    "a spot `alternate` or an ICC conversion is only known once resolved "
                    "(2.10.0).")


class SymbolDef(FG):
    """A reusable drawing, defined once and expanded into the document by the SDK.

    Instancing is deliberately NOT a runtime primitive: `use` objects are
    pre-lowering grammar that `sdk.expand()` resolves before the contract ever
    sees a document, which is what keeps a validated document flat, diffable and
    free of resolution order. See `docs/adr/0001-flat-document-model.md`.

    What was missing was the DEFINITION side. `defs.symbols` was typed `dict`, so
    a symbol body could be anything at all and no consumer could read one without
    guessing. This gives it a shape without imposing it: `Defs.symbols` accepts
    this model OR an arbitrary mapping, because narrowing it would reject
    documents that validate today and the BACKWARD guarantee forbids that.
    """
    content: list[VisualObject] = Field(
        min_length=1, description="The symbol's objects, in paint order, in its own coordinate space.")
    viewbox: Optional[Annotated[list[float], Field(min_length=4, max_length=4)]] = Field(
        default=None, description="[x, y, w, h] the content is authored against; instances scale "
                                  "into their own box against it. Absent = the content's bounds.")
    description: Optional[str] = Field(
        default=None, description="What the symbol depicts — the accessible description an "
                                  "instance inherits when it states none of its own.")
    meta: Optional[dict] = Field(
        default=None, description="Free-form annotation bag; never interpreted by the renderer.")


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
    color_profiles: Optional[dict[str, ColorProfileDef]] = Field(
        default=None, description="Declared ICC profiles, keyed by the name an `icc` colour or a "
                                  "render target's `color_profile` refers to (§9.4).")
    baseline_grid: Optional[BaselineGrid] = Field(
        default=None,
        description="The document's leading grid — the vertical increment every module height "
                    "and every snapped baseline is a multiple of. This is the only scope a "
                    "flowed section has (a `FlowSection` carries no rendering contract), so it "
                    "is where a book declares its rhythm; a fixed page may override it at "
                    "`rendering.baseline_grid`. Inert until a block opts in with "
                    "`align_to_baseline` (2.10.0).")
    data: Optional[dict] = Field(
        default=None, description="Data sources (e.g. CSL-JSON bibliographies) keyed by name.")
    # Grammar-allowed but OUT of the deep core profile — accepted loosely so they
    # are not hard errors; validate.py reports their presence as a warning.
    symbols: Optional[dict[str, Union[SymbolDef, dict]]] = Field(
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


class RenderOutput(FG):
    """What the renderer is asked to PRODUCE, as opposed to what to lay out.

    Until 2.9.0 a target could only restate the canvas and nudge the type: the
    document could not say whether it wanted SVG or a press-ready PDF, at what
    resolution, in which colour, with which fonts embedded. Every one of those
    was a flag on somebody's command line, which meant it was not part of the
    document and did not travel with it.
    """
    format: Optional[Literal["svg", "html", "png", "jpeg", "webp", "pdf", "latex"]] = Field(
        default=None, description="Output format the target produces.")
    dpi: Optional[float] = Field(
        default=None, gt=0, description="Raster resolution in dots per inch (raster formats only). "
                                        "Press work is conventionally 300; screen 72-144.")
    scale: Optional[float] = Field(
        default=None, gt=0, description="Uniform output scale factor applied after layout.")
    quality: Optional[UnitInterval] = Field(
        default=None, description="Encoder quality 0..1 for lossy formats (jpeg/webp).")
    background: Optional[Literal["transparent", "opaque"]] = Field(
        default=None, description="Whether the output canvas is painted or left transparent.")
    color_space: Optional[Literal["srgb", "display-p3", "rec2020", "cmyk", "gray"]] = Field(
        default=None, description="Colour space the output is written in.")
    color_profile: Optional[str] = Field(
        default=None, description="`defs.color_profiles` key embedded as the output intent.")
    output_intent: Optional[Literal["screen", "print", "press"]] = Field(
        default=None, description="Who the output is for. Selects the renderer's defaults for "
                                  "resolution, colour and marks when they are not stated.")
    font_embedding: Optional[Literal["none", "subset", "full"]] = Field(
        default=None, description="Font embedding policy. `subset` is the press default; `none` "
                                  "requires the fonts to be resident wherever it is opened.")
    # ---- printer's marks: drawn OUTSIDE the trim, in the bleed area ----
    crop_marks: Optional[bool] = Field(
        default=None, description="Draw trim marks at the page corners.")
    bleed_marks: Optional[bool] = Field(
        default=None, description="Draw marks at the bleed boundary.")
    registration_marks: Optional[bool] = Field(
        default=None, description="Draw registration targets used to align the separations.")
    color_bars: Optional[bool] = Field(
        default=None, description="Draw ink-density control bars for the press operator.")
    page_information: Optional[bool] = Field(
        default=None, description="Print filename, date and separation name outside the trim.")


class RenderTarget(FG):
    name: str = Field(description="Target name (selects the canvas + adjustments at render).")
    canvas: Optional[CanvasSpec] = Field(
        default=None, description="Canvas the document is re-targeted onto. Absent = keep the "
                                  "document's own canvas and change only `output` — the common "
                                  "case when one layout is exported several ways.")
    adjustments: Optional[TargetAdjustments] = Field(
        default=None, description="Per-target reflow adjustments (font_scale/hide/padding_delta).")
    output: Optional[RenderOutput] = Field(
        default=None, description="What this target produces: format, resolution, colour, font "
                                  "embedding and printer's marks.")


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
