"""
FrameForge v2 — HEAD models (the single source of truth).
=========================================================

These Pydantic v2 models are the authoritative definition of the FrameForge v2
*core conformance profile* at HEAD. This module is the whole reason
``frameforge-api`` exists as a standalone distribution: it is a **leaf** — it
imports nothing from FrameForge, only ``re``/``typing``/``pydantic`` — so every
other package in the family can depend on the contract without depending on an
engine, an authoring SDK, or each other.

Everything else is derived from or checked against these models:

  * ``frameforge_api/schema/frameforge-v2.schema.json`` is GENERATED from
    ``Document`` (``frameforge_api.schema.build``; ``ff-schema --check`` gates it)
  * the FrameForge renderer consumes plain document *dicts*, so it validates
    against this contract structurally rather than importing it
  * ``tooling/validate.py`` (frameforge) layers the static/semantic rules a JSON
    Schema cannot express on top of these models
  * ``grammar/frameforge-v2.ebnf`` is kept consistent by hand (the EBNF is a
    view, not the source)

This module folds in the full patch series and the complement's recommendations:

  P1  nesting/box-model + text-fit ........ Layout(align/row_gap/column_gap), Style/TextStyle text-fit fields
  P2  assets/media/pattern/captions/spans .. AssetDef, FlowSection.media, Pattern, Caption, grid_span
  P3  stroke single form (BREAKING) ........ Stroke = Color (paint); geometry only in stroke_style; +DimensionObject
  P4  content sizing + font pinning ........ Sizing (field renamed `sizing`), FontDef.hash, validator precondition
  gap#1  the CSS style module .............. `Style` and `BorderSide` are DRAFTED here (harvested from the renderer)

Closed model: every object sets `extra="forbid"`. The visual-object and flowable
unions cover the *implemented* core; the kitchen-sink extended objects (UML zoo,
charts, components, ontology) are intentionally OUT of the core profile and are
reported as warnings by validate.py (the §8.5 conformance mechanism), not modelled
here.

Version of the spec these models target: HEAD_VERSION (defined below).
"""
from __future__ import annotations

import re
from typing import Annotated, Literal, Optional, Union, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

HEAD_VERSION = "2.8.2"  # v2 line; 2.4.0 adds the ordered per-object effect stack (`effects`) and the multi-pass appearance stack (`appearance`) — additive, outside the deep-core profile (§8.5, W4/#48). 2.3.0 added typed Connector, per-field schema descriptions, R12 referential integrity, Length/Angle value patterns (additive). 2.2.0 adopted the authoritative style module; P3 stroke collapse remains the one breaking change (codemod provided).


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


# --------------------------------------------------------------------------- #
#  THE STYLE MODULE (authoritative) — adopted at 2.2.0                        #
#  Faithful translation of grammar/frameforge-v2-style.ebnf. `Style` is the   #
#  CSS-parity bag; TextStyle and StrokeStyle are PROJECTIONS of it; fill/      #
#  stroke are `Paint` (= colour | image | gradient | pattern). `class`         #
#  composes named token styles; `css` is the bounded raw-CSS escape (§8.4).   #
# --------------------------------------------------------------------------- #
Angle = Union[
    float, int,
    Annotated[str, Field(
        pattern=ANGLE_STR_RE,
        description="Angle string '<n>deg|rad|grad|turn'; bare numbers are degrees.")],
]
Percentage = Annotated[str, Field(
    pattern=PERCENT_STR_RE, description="Percentage string '<n>%'.")]
StrList = Union[str, list[str]]


# ---- paint sources: gradients, patterns, images ----
class GradientStop(FG):
    color: Color = Field(description="Stop colour: hex, CSS name, or a tokens.colors key.")
    position: Optional[Union[Length, Percentage]] = Field(
        default=None,
        description="Stop position along the gradient line (length or '<n>%'); "
                    "authoritative key — the legacy `offset` (incl. 0..1 unit-interval "
                    "numbers) is accepted and normalised to `position`.")
    opacity: Optional[UnitInterval] = Field(
        default=None,
        description="Stop alpha 0..1 (SVG stop-opacity); omitted = fully opaque. "
                    "Prefer this over 8-digit hex when the alpha ramp is the point "
                    "(soft glows, feathered highlights).")

    @model_validator(mode="before")
    @classmethod
    def _accept_offset(cls, v):
        # 2.2.0 flips canonicalisation: `position` is authoritative; accept the
        # legacy `offset` and unit-interval forms, normalised to `position`.
        if isinstance(v, dict) and "position" not in v and "offset" in v:
            v = dict(v)
            o = v.pop("offset")
            v["position"] = (f"{o*100:g}%" if isinstance(o, (int, float)) and o <= 1 else o)
        return v


class Gradient(FG):
    kind: Literal["linear", "radial", "conic"] = Field(
        description="Gradient family: linear (angle), radial (centre `at`), or conic (start `from`).")
    stops: list[GradientStop] = Field(
        min_length=1, description="Colour stops, in order; at least one.")
    repeating: Optional[bool] = Field(
        default=None, description="Repeat the stop run beyond the last stop (CSS repeating-*-gradient).")
    angle: Optional[Angle] = Field(
        default=None, description="Linear gradients: direction angle (bare number = degrees).")
    from_: Optional[Angle] = Field(
        default=None, alias="from", description="Conic gradients: start angle (key `from`).")
    at: Optional[Union[str, Point]] = Field(
        default=None, description="Radial/conic centre: a CSS position string or an [x, y] point.")
    shape: Optional[Literal["circle", "ellipse"]] = Field(
        default=None, description="Radial gradients: end shape (default ellipse).")
    line: Optional[list[Point]] = Field(
        default=None,
        description="Linear gradients: EXACT gradient line [[x1,y1],[x2,y2]] in the "
                    "object's local (user) coordinate space — page px unless the "
                    "object carries a transform. Mutually exclusive with `angle`; "
                    "lowered as SVG gradientUnits=userSpaceOnUse. The fitted-"
                    "reconstruction emitter (vision.gradient_fit) targets this form: "
                    "bbox-relative `angle` cannot place a sampled ramp exactly on "
                    "shapes whose bbox is mostly empty.")
    radius: Optional[float] = Field(
        default=None, gt=0,
        description="Radial gradients: user-space radius in local px; switches the "
                    "gradient to userSpaceOnUse and therefore requires `at` as a "
                    "numeric [x, y] point (position keywords are bbox-language and "
                    "have no meaning without a bbox).")
    focal: Optional[Point] = Field(
        default=None,
        description="Radial gradients: user-space focus [fx, fy] in local px — the "
                    "gloss-highlight primitive (off-centre sheen). Requires `radius`; "
                    "omitted = focus at the centre `at`.")
    meta: Optional[dict] = Field(
        default=None, description="Free-form annotation bag; never interpreted by the renderer.")
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def _check_user_space_geometry(self):
        # A1 (user-space geometry): incoherent combinations are ERRORS, never a
        # silent reinterpretation — the agent-native surface has one meaning.
        if self.line is not None:
            if self.kind != "linear":
                raise ValueError(
                    f"`line` is linear-only geometry (kind={self.kind!r}); radial "
                    "gradients place themselves with `at` + `radius`")
            if self.angle is not None:
                raise ValueError(
                    "`line` and `angle` are mutually exclusive — `line` already "
                    "fixes the gradient direction exactly")
            if len(self.line) != 2:
                raise ValueError(
                    "`line` must be exactly two points [[x1,y1],[x2,y2]]")
        if self.radius is not None:
            if self.kind != "radial":
                raise ValueError(
                    f"`radius` is radial-only geometry (kind={self.kind!r})")
            at = self.at
            if not (isinstance(at, list) and len(at) == 2):
                raise ValueError(
                    "a user-space radial (`radius`) requires `at` as a numeric "
                    "[x, y] point — keywords/percentages are bbox-relative and "
                    "cannot anchor a px radius")
        if self.focal is not None:
            if self.kind != "radial" or self.radius is None:
                raise ValueError(
                    "`focal` requires a user-space radial: kind='radial' with "
                    "`radius` (and a numeric [x, y] `at`)")
        return self


class Pattern(FG):
    """FG extension paint (P2): tiled hatch/dots/grid, region-clipped."""
    kind: Literal["pattern"] = Field(description="Discriminator: a tiled-pattern paint.")
    pattern: Literal["hatch", "cross_hatch", "dots", "grid"] = Field(
        description="Built-in tile family: hatch, cross_hatch, dots, or grid.")
    angle: Optional[Angle] = Field(
        default=None, description="Tile rotation (hatch direction); bare number = degrees.")
    spacing: Optional[Length] = Field(
        default=None, description="Distance between tile strokes/dots.")
    stroke: Optional[Paint] = Field(
        default=None, description="Paint of the tile strokes/dots.")
    background: Optional[Color] = Field(
        default=None, description="Fill behind the tiles (default transparent).")


class UrlImage(FG):
    url: str = Field(description="Image source: url(...), data: URI, or a defs.assets key.")


ImagePaint = Union[Gradient, UrlImage, str]       # image paint value: url("…")/data-uri/token, or a gradient
Paint = Union[Gradient, Pattern, UrlImage, str]   # "none"|"currentColor"|<color>|<image>|<pattern>
# NOTE: this alias was named `Image`, colliding with the `Image` object class
# below (§visual objects). Under `from __future__ import annotations` that made
# field-type resolution definition-order dependent; renamed to free the name.


# ---- supporting value types ----
class BorderSide(FG):
    width: Optional[Length] = Field(default=None, description="Border line width.")
    style: Optional[Literal["none", "hidden", "solid", "dashed", "dotted",
                            "double", "groove", "ridge", "inset", "outset"]] = Field(
        default=None, description="CSS border-style keyword.")
    color: Optional[Color] = Field(default=None, description="Border colour.")


Border = Union[str, BorderSide]                    # "1px solid #333" or object
Radius = Union[Length, Annotated[list[Length], Field(
    description="Corner radii, CSS shorthand order: 1..4 values (TL TR BR BL).")]]
Edges = Union[Length, Annotated[list[Length], Field(
    description="CSS edge shorthand: 1..4 lengths (all / v h / t h b / t r b l).")]]
SizeValue = Union[Length, Literal["auto", "min-content", "max-content"], dict]
Overflow = Literal["visible", "hidden", "clip", "scroll", "auto"]
BlendMode = Literal["normal", "multiply", "screen", "overlay", "darken", "lighten",
                    "color-dodge", "color-burn", "hard-light", "soft-light", "difference",
                    "exclusion", "hue", "saturation", "color", "luminosity"]
FontStyle = Union[Literal["normal", "italic", "oblique"], dict]
FontStretch = Union[Literal["normal", "ultra-condensed", "extra-condensed", "condensed",
                            "semi-condensed", "semi-expanded", "expanded", "extra-expanded",
                            "ultra-expanded"], str]


class Shadow(FG):
    offset_x: Length = Field(description="Horizontal shadow offset (+x right).")
    offset_y: Length = Field(description="Vertical shadow offset (+y down).")
    blur: Optional[Length] = Field(default=None, description="Blur radius (0 = hard edge).")
    spread: Optional[Length] = Field(default=None, description="Spread distance (box-shadow only).")
    color: Optional[Color] = Field(default=None, description="Shadow colour.")
    inset: Optional[bool] = Field(default=None, description="Inner shadow instead of drop shadow.")


ShadowVal = Union[str, Shadow]


class FilterFn(FG):
    fn: Literal["blur", "brightness", "contrast", "drop_shadow", "grayscale",
                "hue_rotate", "invert", "opacity", "saturate", "sepia",
                "turbulence", "displacement_map", "diffuse_lighting", "specular_lighting"] = Field(
        description="Filter function name (CSS filter function or SVG filter primitive).")
    value: Optional[Union[float, int, str]] = Field(
        default=None, description="Primary argument of the simple CSS functions (amount/angle/length).")
    shadow: Optional[ShadowVal] = Field(
        default=None, description="drop_shadow: the shadow spec.")
    base_frequency: Optional[Union[float, int, str, list[Union[float, int, str]]]] = Field(
        default=None, description="turbulence/displacement_map: generated feTurbulence baseFrequency (one value or [x, y]).")
    num_octaves: Optional[int] = Field(
        default=None, description="turbulence/displacement_map: generated feTurbulence numOctaves.")
    seed: Optional[int] = Field(
        default=None, description="turbulence/displacement_map: deterministic feTurbulence seed.")
    stitch_tiles: Optional[Literal["stitch", "noStitch"]] = Field(
        default=None, description="turbulence: feTurbulence stitchTiles.")
    type: Optional[Literal["fractalNoise", "turbulence"]] = Field(
        default=None, description="turbulence/displacement_map: generated feTurbulence noise type.")
    mode: Optional[str] = Field(
        default=None, description="turbulence/displacement_map/lighting: preset blend or composite mode string.")
    opacity: Optional[Union[float, int, str]] = Field(
        default=None, description="Filter-level opacity applied to the primitive result.")
    scale: Optional[Union[float, int, str]] = Field(
        default=None, description="displacement_map: feDisplacementMap scale.")
    x_channel: Optional[Literal["R", "G", "B", "A"]] = Field(
        default=None, description="displacement_map: xChannelSelector.")
    y_channel: Optional[Literal["R", "G", "B", "A"]] = Field(
        default=None, description="displacement_map: yChannelSelector.")
    surface_scale: Optional[Union[float, int, str]] = Field(
        default=None, description="lighting: surfaceScale of the lit surface.")
    lighting_color: Optional[Color] = Field(
        default=None, description="lighting: light colour (lighting-color).")
    azimuth: Optional[Union[float, int, str]] = Field(
        default=None, description="lighting: feDistantLight azimuth in degrees.")
    elevation: Optional[Union[float, int, str]] = Field(
        default=None, description="lighting: feDistantLight elevation in degrees.")
    x: Optional[Union[float, int, str]] = Field(
        default=None, description="lighting: fePointLight/feSpotLight x position.")
    y: Optional[Union[float, int, str]] = Field(
        default=None, description="lighting: fePointLight/feSpotLight y position.")
    z: Optional[Union[float, int, str]] = Field(
        default=None, description="lighting: fePointLight/feSpotLight z position.")
    points_at_x: Optional[Union[float, int, str]] = Field(
        default=None, description="lighting: feSpotLight pointsAtX.")
    points_at_y: Optional[Union[float, int, str]] = Field(
        default=None, description="lighting: feSpotLight pointsAtY.")
    points_at_z: Optional[Union[float, int, str]] = Field(
        default=None, description="lighting: feSpotLight pointsAtZ.")
    diffuse_constant: Optional[Union[float, int, str]] = Field(
        default=None, description="diffuse_lighting: kd diffuse constant.")
    specular_constant: Optional[Union[float, int, str]] = Field(
        default=None, description="specular_lighting: ks specular constant.")
    specular_exponent: Optional[Union[float, int, str]] = Field(
        default=None, description="specular_lighting: specular exponent (shininess).")


Filter = Union[str, list[FilterFn]]


class TransformFn(FG):
    fn: Literal["translate", "translate_x", "translate_y", "scale", "scale_x", "scale_y",
                "rotate", "skew", "skew_x", "skew_y", "matrix"] = Field(
        description="Transform function name (CSS transform function, underscore-cased).")
    args: list[Union[float, int, str]] = Field(
        description="Positional arguments of the function (numbers, or strings with units).")


class TextDecoration(FG):
    line: Optional[Union[str, list[str]]] = Field(
        default=None, description="Decoration line(s): underline/overline/line-through (one or a list).")
    style: Optional[Literal["solid", "double", "dotted", "dashed", "wavy"]] = Field(
        default=None, description="Decoration line style.")
    color: Optional[Color] = Field(default=None, description="Decoration line colour.")
    thickness: Optional[Length] = Field(default=None, description="Decoration line thickness.")


TextDecorationVal = Union[str, TextDecoration]


class BackgroundLayer(FG):
    color: Optional[Color] = Field(default=None, description="Layer background colour.")
    image: Optional[ImagePaint] = Field(
        default=None, description="Layer background image: url/data URI/asset token or a gradient.")
    position: Optional[str] = Field(
        default=None, description="CSS background-position string for this layer.")
    size: Optional[Union[Literal["auto", "cover", "contain"], str]] = Field(
        default=None, description="CSS background-size keyword or explicit size string.")
    repeat: Optional[Literal["repeat", "repeat-x", "repeat-y", "no-repeat", "space", "round"]] = Field(
        default=None, description="CSS background-repeat for this layer.")
    clip: Optional[Literal["border-box", "padding-box", "content-box", "text"]] = Field(
        default=None, description="CSS background-clip box for this layer.")


class ClipPath(FG):
    shape: Literal["inset", "circle", "ellipse", "polygon", "path"] = Field(
        description="CSS basic-shape family used as the clip path.")
    args: Optional[dict] = Field(
        default=None, description="Shape arguments (per CSS basic-shape: inset offsets, "
                                  "circle/ellipse radii + centre, polygon points, path data).")


ClipPathVal = Union[str, ClipPath]

# Arrow-marker vocabulary for `arrow_start`/`arrow_end`. The SVG painter's
# `_MARKER_SHAPES` is the geometry authority for the SAME five names — a sync
# test (tests/test_arrow_marker_vocabulary.py) keeps model, painter, and the
# grammar's `ArrowMarkerKind` production identical, so an unknown name fails
# HERE instead of silently substituting at render time.
ArrowMarkerKind = Literal["filled_triangle", "hollow_triangle", "filled_diamond",
                          "hollow_diamond", "open_arrow"]
ARROW_MARKER_KINDS: tuple[str, ...] = get_args(ArrowMarkerKind)


# ---- Style: the umbrella (closed bag of CSS-mapped properties) ----
class Style(FG):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    class_: Optional[StrList] = Field(
        default=None, alias="class",
        description="Named style composition: one or more tokens.styles keys merged "
                    "in order before this object's own properties.")
    css: Optional[str] = Field(
        default=None, description="Bounded raw-CSS escape hatch (§8.4); passed through, not parsed.")
    # ---- accepted shorthand sugar (desugars to the canonical CSS property; §8.4) ----
    font: Optional[str] = Field(
        default=None, description="Shorthand for font_family (a family name or tokens.fonts key).")
    size: Optional[Length] = Field(default=None, description="Shorthand for font_size.")
    weight: Optional[Union[int, str]] = Field(default=None, description="Shorthand for font_weight.")
    italic: Optional[bool] = Field(default=None, description="Shorthand for font_style: italic.")
    bold: Optional[bool] = Field(default=None, description="Shorthand for font_weight: bold.")
    align: Optional[Literal["left", "right", "center", "justify", "start", "end"]] = Field(
        default=None, description="Shorthand for text_align.")
    v_align: Optional[Literal["baseline", "top", "middle", "bottom", "sub", "super"]] = Field(
        default=None, description="Shorthand for vertical_align.")
    radius: Optional[Radius] = Field(default=None, description="Shorthand for border_radius.")
    wrap: Optional[bool] = Field(
        default=None, description="Shorthand for text_wrap (False = nowrap).")
    dash: Optional[DashArray] = Field(
        default=None, exclude=True,
        description="Shorthand for stroke_dasharray; accepts a list or SVG whitespace/"
                    "comma-separated string and serializes canonically as stroke_dasharray.")
    # text & font (CSS Text L3 + Fonts L3/L4)
    color: Optional[Color] = Field(
        default=None, description="Text/foreground colour (hex, CSS name, or tokens.colors key).")
    font_family: Optional[StrList] = Field(
        default=None, description="Font family name(s): a fontconfig-resolvable family or a "
                                  "tokens.fonts key; a list is a fallback stack.")
    font_size: Optional[Length] = Field(default=None, description="Font size (bare number = pt/px 1:1).")
    font_weight: Optional[Union[int, Literal["normal", "bold", "lighter", "bolder"]]] = Field(
        default=None, description="Font weight: 1..1000 number or CSS keyword.")
    font_style: Optional[FontStyle] = Field(
        default=None, description="Font style keyword (normal/italic/oblique) or object form.")
    font_stretch: Optional[FontStretch] = Field(
        default=None, description="Font stretch keyword or percentage string.")
    font_variant: Optional[str] = Field(default=None, description="CSS font-variant shorthand string.")
    font_variant_caps: Optional[Literal["normal", "small-caps", "all-small-caps", "petite-caps",
                                        "all-petite-caps", "unicase", "titling-caps"]] = Field(
        default=None, description="CSS font-variant-caps keyword.")
    font_variant_numeric: Optional[str] = Field(
        default=None, description="CSS font-variant-numeric value string.")
    font_variant_ligatures: Optional[str] = Field(
        default=None, description="CSS font-variant-ligatures value string.")
    font_feature_settings: Optional[str] = Field(
        default=None, description="Raw OpenType feature settings string.")
    font_variation_settings: Optional[str] = Field(
        default=None, description="Raw variable-font axis settings string.")
    font_kerning: Optional[Literal["auto", "normal", "none"]] = Field(
        default=None, description="CSS font-kerning keyword.")
    line_height: Optional[Union[float, int, Length, Literal["normal"]]] = Field(
        default=None, description="Line height: bare number = multiplier of font_size; "
                                  "length = absolute; 'normal' = renderer default.")
    letter_spacing: Optional[Length] = Field(default=None, description="Extra inter-glyph spacing.")
    word_spacing: Optional[Length] = Field(default=None, description="Extra inter-word spacing.")
    text_align: Optional[Literal["left", "right", "center", "justify", "start", "end"]] = Field(
        default=None, description="Horizontal text alignment inside the box.")
    text_align_last: Optional[Literal["auto", "left", "right", "center", "justify", "start", "end"]] = Field(
        default=None, description="Alignment of the final line of a justified block.")
    vertical_align: Optional[Union[Literal["baseline", "top", "middle", "bottom", "sub", "super"], Length]] = Field(
        default=None, description="Vertical alignment keyword, or a baseline-shift length.")
    text_decoration: Optional[TextDecorationVal] = Field(
        default=None, description="Text decoration: CSS shorthand string or TextDecoration object.")
    text_transform: Optional[Literal["none", "uppercase", "lowercase", "capitalize"]] = Field(
        default=None, description="Case transform applied at render.")
    text_indent: Optional[Length] = Field(
        default=None, description="First-line indent of a paragraph. In flow, an "
                                  "explicit value (including 0) overrides the engine's "
                                  "positional first-line-indent default (ADR-0006).")
    text_shadow: Optional[list[ShadowVal]] = Field(
        default=None, description="Text shadow list (strings or Shadow objects).")
    white_space: Optional[Literal["normal", "nowrap", "pre", "pre-wrap", "pre-line", "break-spaces"]] = Field(
        default=None, description="CSS white-space collapsing/wrapping mode.")
    word_break: Optional[Literal["normal", "break-all", "keep-all", "break-word"]] = Field(
        default=None, description="CSS word-break rule.")
    overflow_wrap: Optional[Literal["normal", "break-word", "anywhere"]] = Field(
        default=None, description="CSS overflow-wrap (emergency in-word breaking).")
    hyphens: Optional[Literal["none", "manual", "auto"]] = Field(
        default=None, description="Hyphenation mode ('manual' honours soft hyphens only).")
    text_wrap: Optional[Literal["wrap", "nowrap", "balance", "pretty", "stable"]] = Field(
        default=None, description="CSS text-wrap mode (nowrap disables line breaking).")
    hanging_punctuation: Optional[Literal["none", "first", "last", "allow-end", "force-end"]] = Field(
        default=None, description="CSS hanging-punctuation keyword.")
    hyphenate_character: Optional[str] = Field(
        default=None, description="Character shown at a hyphenation break.")
    hyphenate_limit_chars: Optional[Annotated[list[int], Field(min_length=3, max_length=3)]] = Field(
        default=None, description="[word, before, after] minimum character counts for hyphenation.")
    tab_size: Optional[Union[int, Length]] = Field(
        default=None, description="Tab advance: a space count or a length.")
    text_overflow: Optional[Union[Literal["clip", "ellipsis"], str]] = Field(
        default=None, description="Overflowing-text marker: clip, ellipsis, or a custom string.")
    line_clamp: Optional[int] = Field(
        default=None, description="Maximum rendered line count; text beyond it is truncated.")
    max_lines: Optional[int] = Field(
        default=None, description="CSS max-lines: block-axis line limit (pairs with line_clamp).")
    min_font_size: Optional[float] = Field(
        default=None, description="FG text-fit extension (P1): floor font size for "
                                  "overflow:shrink_to_fit. Not a CSS property.")
    writing_mode: Optional[Literal["horizontal-tb", "vertical-rl", "vertical-lr"]] = Field(
        default=None, description="CSS writing-mode (block flow direction).")
    direction: Optional[Literal["ltr", "rtl"]] = Field(
        default=None, description="Inline base direction.")
    unicode_bidi: Optional[Literal["normal", "embed", "isolate", "bidi-override",
                                   "isolate-override", "plaintext"]] = Field(
        default=None, description="CSS unicode-bidi embedding/override behaviour.")
    # box, border, overflow (CSS 2.1 box + Backgrounds & Borders L3)
    width: Optional[SizeValue] = Field(
        default=None, description="Preferred width: length, auto, min-content, or max-content.")
    height: Optional[SizeValue] = Field(
        default=None, description="Preferred height: length, auto, min-content, or max-content.")
    min_width: Optional[SizeValue] = Field(default=None, description="Lower width bound.")
    max_width: Optional[SizeValue] = Field(default=None, description="Upper width bound.")
    min_height: Optional[SizeValue] = Field(default=None, description="Lower height bound.")
    max_height: Optional[SizeValue] = Field(default=None, description="Upper height bound.")
    box_sizing: Optional[Literal["content-box", "border-box"]] = Field(
        default=None, description="Whether width/height include padding+border.")
    padding: Optional[Edges] = Field(
        default=None, description="Inner spacing, CSS shorthand (1..4 lengths).")
    margin: Optional[Edges] = Field(
        default=None, description="Outer spacing, CSS shorthand (1..4 lengths).")
    border: Optional[Border] = Field(
        default=None, description="All-sides border: '1px solid #333' string or BorderSide object.")
    border_top: Optional[BorderSide] = Field(default=None, description="Top border side.")
    border_right: Optional[BorderSide] = Field(default=None, description="Right border side.")
    border_bottom: Optional[BorderSide] = Field(default=None, description="Bottom border side.")
    border_left: Optional[BorderSide] = Field(default=None, description="Left border side.")
    border_radius: Optional[Radius] = Field(
        default=None, description="Corner rounding: one length or 1..4 corner radii.")
    outline: Optional[BorderSide] = Field(
        default=None, description="Non-layout-affecting outline drawn outside the border box.")
    outline_offset: Optional[Length] = Field(
        default=None, description="Gap between the border box and the outline.")
    overflow: Optional[Literal["visible", "hidden", "clip", "scroll", "auto", "shrink_to_fit"]] = Field(
        default=None, description="Content-overflow policy; FG extension shrink_to_fit scales "
                                  "text down to fit (respecting min_font_size; P1 autofit).")
    overflow_x: Optional[Overflow] = Field(default=None, description="Horizontal overflow policy.")
    overflow_y: Optional[Overflow] = Field(default=None, description="Vertical overflow policy.")
    opacity: Optional[UnitInterval] = Field(
        default=None, description="Element opacity in 0..1 (composited per SVG rules).")
    visibility: Optional[Literal["visible", "hidden", "collapse"]] = Field(
        default=None, description="Visibility keyword: hidden keeps layout, collapse removes it.")
    z_index: Optional[int] = Field(
        default=None, description="Stacking order within the parent (higher paints later).")
    # background (multi-layer)
    background: Optional[Union[str, list[BackgroundLayer]]] = Field(
        default=None, description="Background: CSS shorthand string or explicit layer list.")
    background_color: Optional[Color] = Field(default=None, description="Background colour.")
    background_image: Optional[Union[ImagePaint, list[ImagePaint]]] = Field(
        default=None, description="Background image(s): url/data URI/asset token or gradient(s).")
    background_position: Optional[str] = Field(
        default=None, description="CSS background-position string.")
    background_size: Optional[Union[Literal["auto", "cover", "contain"], str]] = Field(
        default=None, description="CSS background-size keyword or explicit size string.")
    background_repeat: Optional[Literal["repeat", "repeat-x", "repeat-y", "no-repeat", "space", "round"]] = Field(
        default=None, description="CSS background-repeat keyword.")
    background_clip: Optional[Literal["border-box", "padding-box", "content-box", "text"]] = Field(
        default=None, description="Box the background paints within ('text' clips to glyphs).")
    background_origin: Optional[Literal["border-box", "padding-box", "content-box"]] = Field(
        default=None, description="Box background-position is resolved against.")
    background_blend_mode: Optional[BlendMode] = Field(
        default=None, description="Blend mode between background layers.")
    # paint & SVG stroke
    fill: Optional[Paint] = Field(
        default=None, description="Shape fill paint: 'none'/'currentColor'/colour/gradient/pattern/image.")
    fill_rule: Optional[Literal["nonzero", "evenodd"]] = Field(
        default=None, description="Winding rule used to compute the filled region.")
    stroke: Optional[Paint] = Field(
        default=None, description="Stroke PAINT only (P3): colour/gradient/pattern; geometry "
                                  "(width/dash/caps) lives in the stroke_* properties.")
    stroke_width: Optional[Length] = Field(default=None, description="Stroke width.")
    stroke_dasharray: Optional[DashArray] = Field(
        default=None, description="Dash pattern lengths as a list or SVG whitespace/comma-"
                                  "separated string; strings normalize to a list. 'none' "
                                  "selects a solid line.")
    stroke_dashoffset: Optional[Length] = Field(
        default=None, description="Distance into the dash pattern at the path start.")
    stroke_linecap: Optional[Literal["butt", "round", "square"]] = Field(
        default=None, description="Open-path end-cap shape.")
    stroke_linejoin: Optional[Literal["miter", "round", "bevel", "arcs", "miter-clip"]] = Field(
        default=None, description="Corner join shape.")
    stroke_miterlimit: Optional[float] = Field(
        default=None, description="Miter length limit before falling back to bevel.")
    paint_order: Optional[str] = Field(
        default=None, description="SVG paint-order string (e.g. 'stroke fill markers').")
    vector_effect: Optional[Literal["none", "non-scaling-stroke"]] = Field(
        default=None, description="non-scaling-stroke keeps stroke width fixed under transforms.")
    arrow_start: Optional[Union[bool, ArrowMarkerKind]] = Field(
        default=None, description="FG stroke extension: arrowhead at the path start — true "
                                  "(= filled_triangle) or one of filled_triangle, "
                                  "hollow_triangle, filled_diamond, hollow_diamond, "
                                  "open_arrow; read from the resolved stroke_style.")
    arrow_end: Optional[Union[bool, ArrowMarkerKind]] = Field(
        default=None, description="FG stroke extension: arrowhead at the path end — true "
                                  "(= filled_triangle) or one of filled_triangle, "
                                  "hollow_triangle, filled_diamond, hollow_diamond, "
                                  "open_arrow; read from the resolved stroke_style.")
    # effects
    box_shadow: Optional[Union[Literal["none"], list[ShadowVal]]] = Field(
        default=None, description="Box shadow list (strings or Shadow objects), or 'none'.")
    filter: Optional[Filter] = Field(
        default=None, description="Filter chain: CSS filter string or a list of stacked self-contained presets; each list entry is applied independently in order, never wired into one SVG primitive graph.")
    backdrop_filter: Optional[Filter] = Field(
        default=None, description="Filter applied to the backdrop behind the element.")
    mix_blend_mode: Optional[BlendMode] = Field(
        default=None, description="Blend mode against the backdrop.")
    isolation: Optional[Literal["auto", "isolate"]] = Field(
        default=None, description="isolate creates a new stacking/blending context.")
    clip_path: Optional[ClipPathVal] = Field(
        default=None, description="Clip region: CSS basic-shape string or ClipPath object.")
    mask: Optional[Union[Literal["none"], ImagePaint, str]] = Field(
        default=None, description="Mask source: 'none', an image/gradient, or a reference string.")
    # transforms
    transform: Optional[Union[Literal["none"], str, list[TransformFn]]] = Field(
        default=None, description="Transform: 'none', a CSS transform string, or a TransformFn list "
                                  "(applied to the whole subtree of a container; §3.6b).")
    transform_origin: Optional[Union[str, Point]] = Field(
        default=None, description="Transform origin: CSS position string or [x, y] "
                                  "(defaults to the box centre; §3.6b).")
    transform_box: Optional[Literal["border-box", "fill-box", "view-box", "content-box"]] = Field(
        default=None, description="Box the transform and its origin are resolved against.")
    # NON-CONFORMANT (G-2): accepted for round-trip, but no render target applies a
    # 3D perspective — it passes through inert and the validator WARNs
    # (`non-conformant-3d`). Author 3D via the SDK Scene3D 2D-projection (Appendix A.5).
    perspective: Optional[Union[Literal["none"], Length]] = Field(
        default=None, description="NON-CONFORMANT (G-2): accepted for round-trip but no render "
                                  "target applies 3D perspective; the validator warns. "
                                  "Author 3D via the SDK Scene3D projection.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_dash_array(cls, data):
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if "dash" in out:
            if "stroke_dasharray" in out:
                raise ValueError("use either dash or stroke_dasharray, not both")
            out["stroke_dasharray"] = out.pop("dash")
        value = out.get("stroke_dasharray")
        if not isinstance(value, str) or value == "none":
            return out
        if not re.fullmatch(DASH_ARRAY_STR_RE, value):
            raise ValueError(
                "stroke_dasharray must be 'none', a list, or an SVG whitespace/"
                "comma-separated list of non-negative lengths"
            )
        parts = [part for part in re.split(r"(?:\s*,\s*|\s+)", value.strip()) if part]
        out["stroke_dasharray"] = [
            float(part) if re.fullmatch(r"(?:\d+\.?\d*|\.\d+)", part) else part
            for part in parts
        ]
        return out


# TextStyle and StrokeStyle are PROJECTIONS of Style (the module's contract).
TextStyle = Style
StrokeStyle = Style
StyleRef = Union[str, Style]
Fill = Paint                                       # fill is a Paint
StrokeStyleRef = Union[str, Style]                 # a named stroke bundle is a Style


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


# --------------------------------------------------------------------------- #
#  Inline content                                                             #
# --------------------------------------------------------------------------- #
class Span(FG):
    text: str = Field(description="The run's literal text.")
    style: Optional[StyleRef] = Field(
        default=None, description="Run style: a tokens key or an inline Style.")
    lang: Optional[str] = Field(
        default=None, description="BCP-47 language tag overriding the ambient language.")


class RefInline(FG):
    kind: Literal["ref"] = Field(description="Discriminator: an internal cross-reference run.")
    target: str = Field(description="Id of the referenced element (heading/figure/table/…); must resolve.")
    show: Optional[Literal["auto", "number", "page", "label", "title"]] = Field(
        default=None, description="What the reference renders as (default auto).")


class CiteInline(FG):
    kind: Literal["cite"] = Field(description="Discriminator: a bibliographic citation run.")
    key: Union[str, list[str]] = Field(description="Citation key(s) into the CSL data source.")
    mode: Optional[Literal["parenthetical", "textual", "author", "year", "note"]] = Field(
        default=None, description="Citation rendering mode.")
    locator: Optional[str] = Field(
        default=None, description="Locator within the work (page/chapter/…).")
    prefix: Optional[str] = Field(default=None, description="Text prepended inside the citation.")
    suppress_author: Optional[bool] = Field(
        default=None, description="Render year-only (author already named in prose).")


class MathInline(FG):
    kind: Literal["math"] = Field(description="Discriminator: an inline math run.")
    mathml: Optional[str] = Field(default=None, description="MathML source of the formula.")
    tex: Optional[str] = Field(default=None, description="TeX source of the formula.")


class CodeInline(FG):
    kind: Literal["code"] = Field(description="Discriminator: an inline code run.")
    text: str = Field(description="The literal code text (rendered monospace, no wrapping transforms).")


class FootnoteInline(FG):
    kind: Literal["footnote"] = Field(description="Discriminator: a footnote call.")
    content: list["Flowable"] = Field(description="The note body (block content).")
    placement: Optional[Literal["footnote", "endnote"]] = Field(
        default=None, description="Note placement: page footnote area or end-of-section endnote.")
    id: Optional[str] = Field(default=None, description="Stable id for cross-referencing the note.")


class LinkInline(FG):
    kind: Literal["link"] = Field(description="Discriminator: a hyperlink run.")
    href: str = Field(description="Link target URL (or internal #id).")
    content: list["Inline"] = Field(description="The link's visible inline content.")
    title: Optional[str] = Field(default=None, description="Advisory tooltip/title text.")


Inline = Union[str, RefInline, CiteInline, MathInline, CodeInline, FootnoteInline, LinkInline, Span]
Caption = Union[str, list[Inline]]


# --------------------------------------------------------------------------- #
#  humanize — a seeded, bounded "hand" (the imperfection layer)               #
# --------------------------------------------------------------------------- #
class Humanize(FG):
    """A seeded, bounded *hand* that perturbs objects so a mechanically-perfect
    layout reads as hand-placed — the visual analogue of a sampler's round-robin /
    velocity / pitch-drift humanization.

    It is **deterministic**: perturbation is drawn from a per-object RNG keyed on
    ``seed`` + the object's identity, so the same document and seed render
    byte-identically (the discipline the ``greeble``/``lorem`` helpers already
    follow — fixtures and golden renders stay stable). Bump ``seed`` to re-perform
    the whole page like a fresh take. Attach at the document (global default) or
    on any object (scoped override); an object's spec wins for its subtree.

    Perturbation is **topology-preserving**: whole-object channels (rotation, opacity,
    inline stroke weight) leave geometry alone, and the ``roughen`` channel — which
    *does* rewrite geometry into hand-drawn wobble — anchors every segment endpoint
    (the displacement tapers to zero at the ends) so lines still meet. An object a
    connector attaches to is exempt from both rotation and roughen so anchors keep
    meeting. Scalar deltas are hard-clamped to their amplitude, so those channels are
    provably bounded (never a wild rotation, never invisible ink)."""
    enabled: bool = Field(
        default=True, description="Master switch; False leaves the subtree untouched "
                                  "without deleting the spec.")
    seed: int = Field(
        default=0, ge=0, description="The 'take': the base RNG seed. Same seed → identical "
                                     "output; bump it to re-perform the whole page.")
    weight: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Velocity channel: ± fraction by which an object's inline stroke width "
                    "varies (0 = off; 0.15 = ±15%). Ignored for token-ref stroke styles.")
    opacity: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Velocity channel: ± band by which object opacity varies, as ink density "
                    "(0 = off). Result is clamped to 0..1.")
    drift_deg: float = Field(
        default=0.0, ge=0.0, le=45.0,
        description="Pitch-drift channel: ± maximum rotation (degrees) added per object "
                    "(0 = off). Small values (0.4–1.5) read as a hand-set tilt.")
    roughen: float = Field(
        default=0.0, ge=0.0, le=20.0,
        description="Effect channel: perpendicular wobble amplitude (px) that turns straight "
                    "primitives (line/rect/ellipse/circle/polyline/polygon) into hand-drawn "
                    "ones — coherent two-band noise, endpoint-anchored so segment ends stay "
                    "pinned. 0 = off; 0.5–1.5 reads as a sketched line. Straight primitives "
                    "convert to a polyline; text/image/group/path are left as-is.")
    grain: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="Hand tension: 1.0 = tight (excursions concentrate near zero), "
                    "0.0 = loose (larger, more frequent excursions). Shapes the noise, "
                    "not its amplitude cap.")


# --------------------------------------------------------------------------- #
#  common-object-fields (mixin) + stroke single-form enforcement              #
# --------------------------------------------------------------------------- #
class ObjBase(FG):
    id: Optional[str] = Field(
        default=None, description="Stable object id: the target namespace for anchors, "
                                  "bind, reading_order and adjustments (§3.1).")
    box: Optional[Box] = Field(
        default=None, description="Placement box [x, y, w, h], parent-local, +y down; under "
                                  "row/column/grid layout the authored x/y are replaced by "
                                  "computed positions (§3.6).")
    rotation: Optional[RotationOrNumber] = Field(
        default=None, description="Rotation in degrees (clockwise, +y down) or a "
                                  "{angle, center} object; composes onto the subtree for containers.")
    ports: Optional[dict[str, Point]] = Field(
        default=None, description="Named attachment points in the object's local space, "
                                  "addressed by anchors as {ref, port}.")
    bind: Optional[str] = Field(
        default=None, description="Data-binding expression/reference (resolved at expansion).")
    decorative: Optional[bool] = Field(
        default=None, description="Marks a purely decorative object: excluded from reading-order/"
                                  "accessibility requirements and scoped overlap audits. It does "
                                  "not suppress canvas containment; use containment: allowed for "
                                  "intentional bleed.")
    containment: Optional[Literal["allowed"]] = Field(
        default=None, description="Explicit consent for intentional canvas bleed. `allowed` "
                                  "suppresses the containment advisory for this object and, for "
                                  "a group, its subtree; it never changes clipping or rendering.")
    overlap: Optional[Literal["allowed"]] = Field(
        default=None, description="Consent for INTENTIONAL same-layer overlap (§3.3): "
                                  "`allowed` declares that this object may share ink with a "
                                  "same-layer sibling on purpose — a watermark, a caption over "
                                  "an image, double-exposure type. Absence means no consent, so "
                                  "the render-time collision detector reports the overlap as an "
                                  "accident. Read only by the audit; it never changes how the "
                                  "object draws. Cross-layer overlap is exempt by construction.")
    construction: Optional[bool] = Field(
        default=None, description="Marks non-printing construction geometry (datums, guides, "
                                  "snap targets): excluded from rendering unless the document "
                                  "opts in via meta.show_construction.")
    z: Optional[float] = Field(
        default=None, description="Stacking order within the layer (higher paints later).")
    opacity: Optional[UnitInterval] = Field(
        default=None, description="Object opacity in 0..1; on a group it composites the "
                                  "subtree as one unit (§3.6d).")
    fill_opacity: Optional[UnitInterval] = Field(
        default=None, description="Fill-only opacity in 0..1 (multiplies with `opacity`).")
    stroke_opacity: Optional[UnitInterval] = Field(
        default=None, description="Stroke-only opacity in 0..1 (multiplies with `opacity`).")
    stroke_style: Optional[StrokeStyleRef] = Field(
        default=None, description="Stroke GEOMETRY bundle (P3): a tokens.stroke_styles key or an "
                                  "inline Style carrying stroke_width/dash/caps/arrow_*; its "
                                  "colour is a default overridden by the object's `stroke` paint.")
    style: Optional[StyleRef] = Field(
        default=None, description="Object style: a tokens key or an inline Style bag.")
    shadow: Optional[Effect] = Field(
        default=None, description="Drop-shadow effect: preset name, bool, or EffectObject.")
    glow: Optional[Effect] = Field(
        default=None, description="Glow effect: preset name, bool, or EffectObject.")
    effects: Optional[list[EffectStackEntry]] = Field(
        default=None, description="ORDERED effect stack (2.4.0): entries apply "
                                  "first→last and a kind may repeat — the live-"
                                  "effects analogue of the single shadow/glow "
                                  "fields. Out of the deep-core profile (§8.5).")
    appearance: Optional[list[AppearancePass]] = Field(
        default=None, description="Appearance stack (2.4.0): the geometry is "
                                  "painted once per pass (fill/stroke/opacity), "
                                  "bottom→top in list order. Out of the deep-"
                                  "core profile (§8.5).")
    outer_ring: Optional[OuterRing] = Field(
        default=None, description="Decorative ring drawn around the object at a gap/offset.")
    grid_span: Optional[Annotated[list[int], Field(min_length=2, max_length=2)]] = Field(
        default=None, description="[column_span, row_span] cell span; only meaningful under a "
                                  "grid layout parent (default [1, 1]; §3.6e).")
    sizing: Optional[Sizing] = Field(
        default=None, description="P4 per-axis content sizing (fixed|hug|fill with grow/min/max); "
                                  "renamed from `size` (IconObject.size collision).")
    meta: Optional[dict] = Field(
        default=None, description="Free-form annotation bag (e.g. meta.no_overlap, meta.role); "
                                  "never interpreted as geometry.")
    humanize: Optional[Humanize] = Field(
        default=None, description="Scoped humanize override: a seeded imperfection 'hand' applied "
                                  "to this object (and, for containers, its subtree), overriding "
                                  "any document-level default.")

    @model_validator(mode="before")
    @classmethod
    def _stroke_paint_only(cls, data):
        # P3 BREAKING: an inline-geometry `stroke` object is removed. Catch it with
        # an actionable error pointing at the codemod, instead of a vague type error.
        # Runs before field validation so it fires for every visual object subclass.
        sv = data.get("stroke") if isinstance(data, dict) else None
        if isinstance(sv, dict) and any(k in sv for k in ("width", "dash", "linecap", "linejoin")):
            raise ValueError(
                "stroke is paint-only (P3): an inline geometry object {color,width,dash,...} "
                "is not allowed. Put paint in `stroke` (a colour/gradient/pattern) and geometry "
                "in `stroke_style` (a named Style). Run tooling/codemod.py to migrate."
            )
        return data


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


class Cell(FG):
    content: str = Field(description="Cell text content.")
    style: Optional[StyleRef] = Field(
        default=None, description="Cell style: a tokens key or an inline Style.")
    span: Optional[Annotated[list[int], Field(min_length=2, max_length=2)]] = Field(
        default=None, description="[column_span, row_span] the cell covers.")


CellValue = Union[str, float, int, bool, None, Span, Cell]


class ColumnSpec(FG):
    label: Optional[str] = Field(default=None, description="Column header label.")
    width: Optional[Length] = Field(default=None, description="Column width.")
    align: Optional[Align] = Field(default=None, description="Column text alignment.")


ColumnSpecVal = Union[str, ColumnSpec]


class TableObject(ObjBase):
    type: Literal["table"] = Field(description="Discriminator: absolutely-placed table in `box`.")
    rows: list[list[CellValue]] = Field(
        description="Row-major cell values (scalar, Span, or Cell with span).")
    columns: Optional[list[ColumnSpecVal]] = Field(
        default=None, description="Column specs (label/width/align) or plain header strings.")
    header: Optional[list[CellValue]] = Field(
        default=None, description="Header row cells (styled separately from body rows).")
    row_height: Optional[Length] = Field(default=None, description="Fixed body row height.")
    header_height: Optional[Length] = Field(default=None, description="Fixed header row height.")
    zebra: Optional[bool] = Field(default=None, description="Alternate-row background striping.")
    cell_padding: Optional[Union[Length, list[Length]]] = Field(
        default=None, description="Cell inner padding (one length or CSS shorthand list).")
    style: Optional[Union[str, dict]] = Field(
        default=None, description="Table theme: a tokens key or a loose dict of "
                                  "renderer keys: header_fill, header_text, cell_text, "
                                  "zebra_fill, grid_color, cell_size, and the chrome geometry "
                                  "keys grid_width, cell_padding, header_weight, "
                                  "cell_line_height (documented fallbacks 0.5/4.0/700/1.25; "
                                  "chrome the table does not define is not drawn; ADR-0006). "
                                  "header_text/cell_text are colour-or-style-ref, identical "
                                  "in BOTH table renderers: a dict = inline text-style "
                                  "fragment; a string naming a defined tokens style = style "
                                  "ref (wins wholesale); any other string = a colour; "
                                  "grammar: object-any.")


class Group(ObjBase):
    type: Literal["group"] = Field(
        description="Discriminator: container establishing a local coordinate system (§3.6); "
                    "child boxes are parent-relative.")
    children: list["VisualObject"] = Field(description="Child objects, in paint order.")
    layout: Optional[Layout] = Field(
        default=None, description="Child placement algorithm; absent behaves as kind: free.")


# --------------------------------------------------------------------------- #
#  UML 2.5 visual objects (semantic ontology lives in sdk.uml_models)          #
# --------------------------------------------------------------------------- #
class UMLVisualBase(ObjBase):
    """Shared typed envelope for the renderer's UML extension object family.

    Diagram-level semantic constraints are intentionally enforced by
    ``frameforge.sdk.uml_models`` before composition.  These visual models type
    the rendering boundary while permitting notation-specific payload fields.
    """

    name: Optional[str] = Field(default=None, description="Displayed UML element name.")
    kind: Optional[str] = Field(default=None, description="Notation-specific UML element kind.")
    label: Optional[str] = Field(default=None, description="Optional displayed label.")
    color: Optional[Color] = Field(default=None, description="Notation colour override.")
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class UMLMarkerGlyph(UMLVisualBase):
    type: Literal["uml.marker_glyph"] = Field(description="UML endpoint marker glyph.")
    position: Point = Field(description="Marker centre in page space.")


class UMLClassifierBox(UMLVisualBase):
    type: Literal["uml.classifier_box"] = Field(description="UML classifier compartment box.")


class UMLComponentBox(UMLVisualBase):
    type: Literal["uml.component_box"] = Field(description="UML component classifier box.")


class UMLStateBox(UMLVisualBase):
    type: Literal["uml.state_box"] = Field(description="UML state with optional behavior rows.")


class UMLAction(UMLVisualBase):
    type: Literal["uml.action"] = Field(description="Rounded UML activity action.")


class UMLArtifactBox(UMLVisualBase):
    type: Literal["uml.artifact_box"] = Field(description="UML deployment artifact box.")


class UMLNodeBox(UMLVisualBase):
    type: Literal["uml.node_box"] = Field(description="UML deployment node or device box.")


class UMLLifeline(UMLVisualBase):
    type: Literal["uml.lifeline"] = Field(description="UML sequence or communication lifeline.")


class UMLActivationBar(UMLVisualBase):
    type: Literal["uml.activation_bar"] = Field(description="UML sequence activation bar.")


class UMLActorObject(UMLVisualBase):
    type: Literal["uml.actor"] = Field(description="UML actor glyph and label.")


class UMLSocket(UMLVisualBase):
    type: Literal["uml.socket"] = Field(description="UML required-interface socket glyph.")


class UMLLollipop(UMLVisualBase):
    type: Literal["uml.lollipop"] = Field(description="UML provided-interface lollipop glyph.")


class UMLActivityNodeObject(UMLVisualBase):
    type: Literal["uml.activity_node"] = Field(description="UML activity control-node glyph.")


class UMLPseudostateObject(UMLVisualBase):
    type: Literal["uml.pseudostate"] = Field(description="UML state-machine pseudostate glyph.")


class UMLFragmentFrame(UMLVisualBase):
    type: Literal["uml.fragment_frame"] = Field(description="UML interaction combined-fragment frame.")


class UMLSwimlane(UMLVisualBase):
    type: Literal["uml.swimlane"] = Field(description="UML activity swimlane frame.")


class UMLTimingLane(UMLVisualBase):
    type: Literal["uml.timing_lane"] = Field(description="UML timing-diagram state lane.")


VisualObject = Annotated[
    Union[
        Rect, Ellipse, Circle, Line, Polyline, Polygon, Path, Curve,
        Text, Image, Icon, BulletList, Dimension, Connector, TableObject, Group,
        UMLMarkerGlyph, UMLClassifierBox, UMLComponentBox, UMLStateBox,
        UMLAction, UMLArtifactBox, UMLNodeBox, UMLLifeline, UMLActivationBar,
        UMLActorObject, UMLSocket, UMLLollipop, UMLActivityNodeObject,
        UMLPseudostateObject, UMLFragmentFrame, UMLSwimlane, UMLTimingLane,
    ],
    Field(discriminator="type"),
]


# --------------------------------------------------------------------------- #
#  Flowables (story content)                                                  #
# --------------------------------------------------------------------------- #
class BreakFields(FG):
    break_before: Optional[Literal["auto", "always", "avoid", "page", "column"]] = Field(
        default=None, description="Break policy before this block (CSS break-before subset).")
    break_after: Optional[Literal["auto", "always", "avoid", "page", "column"]] = Field(
        default=None, description="Break policy after this block (CSS break-after subset).")
    break_inside: Optional[Literal["auto", "avoid", "avoid-page", "avoid-column"]] = Field(
        default=None, description="Whether the block may split across pages/columns.")


class StringSet(FG):
    name: str = Field(description="Named running-string slot to set (read by running headers).")
    value: Optional[str] = Field(
        default=None, description="Value to set (defaults to the element's own text).")


class ParagraphFlow(BreakFields):
    type: Literal["paragraph"] = Field(description="Discriminator: a prose paragraph.")
    text: Optional[str] = Field(
        default=None, description="Plain text content; exactly one of `text` or `spans` (XOR).")
    spans: Optional[list[Inline]] = Field(
        default=None, description="Styled inline runs; exactly one of `text` or `spans` (XOR).")
    style: Optional[StyleRef] = Field(
        default=None, description="Paragraph style: a tokens key or an inline Style.")
    lang: Optional[str] = Field(
        default=None, description="BCP-47 language tag overriding the section language.")
    widows: Optional[int] = Field(
        default=None, description="Minimum lines kept at the top of a page/column after a break.")
    orphans: Optional[int] = Field(
        default=None, description="Minimum lines kept at the bottom of a page/column before a break.")

    @model_validator(mode="after")
    def _one_of(self):
        if (self.text is None) == (self.spans is None):
            raise ValueError("a paragraph needs exactly one of `text` or `spans`")
        return self


class HeadingFlow(BreakFields):
    type: Literal["heading"] = Field(description="Discriminator: a section heading.")
    level: int = Field(description="Heading depth (1 = top level).")
    text: str = Field(description="Heading text.")
    id: Optional[str] = Field(default=None, description="Stable id for `ref` cross-references.")
    number: Optional[Number] = Field(
        default=None, description="Counter series this heading numbers into.")
    set_string: Optional[list[StringSet]] = Field(
        default=None, description="Running-string slots this heading sets (for headers/footers).")
    lang: Optional[str] = Field(default=None, description="BCP-47 language tag override.")
    style: Optional[StyleRef] = Field(
        default=None, description="Heading style: a tokens key or an inline Style.")


class ListItemFlow(FG):
    text: Optional[str] = Field(default=None, description="Plain item text (or use `spans`).")
    spans: Optional[list[Inline]] = Field(default=None, description="Styled inline item content.")
    style: Optional[StyleRef] = Field(
        default=None, description="Item style: a tokens key or an inline Style.")


ListItemVal = Union[str, ListItemFlow, list["ParagraphFlow"]]


class ListFlow(BreakFields):
    type: Literal["list"] = Field(description="Discriminator: a flowed (paginating) list.")
    items: list[ListItemVal] = Field(
        description="Items: strings, ListItemFlow objects, or paragraph lists (multi-block items).")
    ordered: Optional[bool] = Field(default=None, description="Numbered instead of bulleted.")
    marker: Optional[str] = Field(default=None, description="Custom bullet marker character.")
    style: Optional[StyleRef] = Field(
        default=None, description="List style: a tokens key or an inline Style.")
    indent: Optional[Length] = Field(
        default=None, description="Item indent from the column edge "
                                  "(documented fallback 16).")


class SpacerFlow(FG):
    type: Literal["spacer"] = Field(description="Discriminator: fixed vertical whitespace.")
    height: Optional[Length] = Field(default=None, description="Space height.")


class PageBreakFlow(FG):
    type: Literal["page_break"] = Field(description="Discriminator: force the next page.")


class ColumnBreakFlow(FG):
    type: Literal["column_break"] = Field(description="Discriminator: force the next column.")


class TableFlow(BreakFields):
    type: Literal["table"] = Field(description="Discriminator: a flowed (paginating) table.")
    rows: list[list[CellValue]] = Field(
        description="Row-major cell values (scalar, Span, or Cell with span).")
    columns: Optional[list[ColumnSpecVal]] = Field(
        default=None, description="Column specs (label/width/align) or plain header strings.")
    header: Optional[list[CellValue]] = Field(
        default=None, description="Header row cells (repeated after page breaks).")
    row_height: Optional[Length] = Field(default=None, description="Fixed body row height.")
    header_height: Optional[Length] = Field(default=None, description="Fixed header row height.")
    zebra: Optional[bool] = Field(default=None, description="Alternate-row background striping.")
    cell_padding: Optional[Union[Length, list[Length]]] = Field(
        default=None, description="Cell inner padding (one length or CSS shorthand list).")
    style: Optional[Union[str, dict]] = Field(
        default=None, description="Table theme: a tokens key or a loose dict of "
                                  "renderer keys: header_fill, header_text, cell_text, "
                                  "zebra_fill, grid_color, cell_size, and the chrome geometry "
                                  "keys grid_width, cell_padding, header_weight, "
                                  "cell_line_height (documented fallbacks 0.5/4.0/700/1.25; "
                                  "chrome the table does not define is not drawn; ADR-0006). "
                                  "header_text/cell_text are colour-or-style-ref, identical "
                                  "in BOTH table renderers: a dict = inline text-style "
                                  "fragment; a string naming a defined tokens style = style "
                                  "ref (wins wholesale); any other string = a colour; "
                                  "grammar: object-any.")
    caption: Optional[Caption] = Field(
        default=None, description="Caption: a string or inline runs (P2).")
    credit: Optional[Caption] = Field(
        default=None, description="Source/credit line, separate from the caption (P2).")
    id: Optional[str] = Field(default=None, description="Stable id for `ref` cross-references.")
    number: Optional[Number] = Field(
        default=None, description="Counter series this table numbers into.")


class ImageFlow(BreakFields):
    type: Literal["image"] = Field(description="Discriminator: a flowed image block.")
    src: str = Field(
        description="Image source: a literal path/URL/data URI or a defs.assets key (§9.3).")
    alt: Optional[str] = Field(
        default=None, description="Accessibility alternative text (a11y lint warns when absent).")
    actual_text: Optional[str] = Field(
        default=None, description="Full replacement text for tagged/a11y export.")
    width: Optional[Length] = Field(default=None, description="Rendered width (height keeps ratio).")
    height: Optional[Length] = Field(default=None, description="Rendered height (width keeps ratio).")
    preserve_aspect_ratio: Optional[Union[bool, str]] = Field(
        default=None, description="True/False, or an SVG preserveAspectRatio string.")
    caption: Optional[Caption] = Field(
        default=None, description="Caption: a string or inline runs (P2).")
    credit: Optional[Caption] = Field(
        default=None, description="Source/credit line, separate from the caption (P2).")


class FigureFlow(BreakFields):
    type: Literal["figure"] = Field(
        description="Discriminator: a visual object embedded in flow as a figure.")
    object: "VisualObject" = Field(description="The embedded visual object (any core object).")
    alt: Optional[str] = Field(
        default=None, description="Accessibility alternative text for the figure.")
    actual_text: Optional[str] = Field(
        default=None, description="Full replacement text for tagged/a11y export.")
    align: Optional[Literal["left", "center", "right"]] = Field(
        default=None, description="Horizontal placement of the figure in the column.")
    units: Optional[Units] = Field(
        default=None, description="Coordinate unit of the figure's drawing space (default px).")
    size: Optional[Annotated[list[Length], Field(min_length=2, max_length=2)]] = Field(
        default=None, description="[w, h] the figure's drawing space is scaled to.")
    caption: Optional[Caption] = Field(
        default=None, description="Caption: a string or inline runs (P2).")
    credit: Optional[Caption] = Field(
        default=None, description="Source/credit line, separate from the caption (P2).")
    id: Optional[str] = Field(default=None, description="Stable id for `ref` cross-references.")
    number: Optional[Number] = Field(
        default=None, description="Counter series this figure numbers into.")


class BlockFlow(BreakFields):
    type: Literal["block"] = Field(
        description="Discriminator: styled grouping block around child flowables.")
    children: list["Flowable"] = Field(description="Child flowables, in order.")
    style: Optional[StyleRef] = Field(
        default=None, description="Block style: a tokens key or an inline Style.")
    role: Optional[str] = Field(
        default=None, description="Semantic role hint (e.g. note/aside) for tagged export.")
    fill: Optional[Fill] = Field(default=None, description="Block background paint.")
    stroke: Optional[Paint] = Field(
        default=None, description="Block border paint only (P3); geometry lives in `stroke_style`.")
    stroke_style: Optional[StrokeStyleRef] = Field(
        default=None, description="Border geometry bundle: a tokens.stroke_styles key or inline Style.")
    padding: Optional[Edges] = Field(
        default=None, description="Inner padding, CSS shorthand (1..4 lengths).")
    id: Optional[str] = Field(default=None, description="Stable id for `ref` cross-references.")


class KeepTogetherFlow(BreakFields):
    type: Literal["keep_together"] = Field(
        description="Discriminator: children must not split across a page/column break.")
    children: list["Flowable"] = Field(description="Child flowables kept on one page/column.")


class CodeFlow(BreakFields):
    type: Literal["code"] = Field(description="Discriminator: a code listing block.")
    source: str = Field(description="Verbatim code text (whitespace preserved).")
    language: Optional[str] = Field(
        default=None, description="Language tag for syntax highlighting.")
    line_numbers: Optional[bool] = Field(default=None, description="Render line numbers.")
    style: Optional[StyleRef] = Field(
        default=None, description="Listing style: a tokens key or an inline Style.")


class MathFlow(BreakFields):
    type: Literal["math"] = Field(description="Discriminator: a display math block.")
    tex: Optional[str] = Field(default=None, description="TeX source of the formula.")
    mathml: Optional[str] = Field(default=None, description="MathML source of the formula.")
    alt: Optional[str] = Field(
        default=None, description="Plain-text fallback for accessibility (a11y/tagged export).")
    id: Optional[str] = Field(default=None, description="Stable id for `ref` cross-references.")
    number: Optional[Number] = Field(
        default=None, description="Counter series this equation numbers into.")


class TocFlow(BreakFields):
    type: Literal["toc"] = Field(description="Discriminator: a generated table of contents.")
    of: Optional[Literal["headings", "figures", "tables", "equations", "listings"]] = Field(
        default=None, description="Which numbered series the TOC lists (default headings).")
    levels: Optional[list[int]] = Field(
        default=None, description="Heading levels to include (default all).")
    title: Optional[str] = Field(default=None, description="TOC title text.")
    style: Optional[StyleRef] = Field(
        default=None, description="TOC entry style: a tokens key or an inline Style. Absent, "
                                  "entries resolve the reserved `toc` style; the title resolves "
                                  "the reserved `toc_title` style (spec §5.2.2, ADR-0006).")
    leader: Optional[str] = Field(
        default=None, description="Leader between entry and page number (e.g. '.').")
    number_width: Optional[Length] = Field(
        default=None, description="Width of the right-anchored page-number column "
                                  "(documented fallback 24).")
    level_indent: Optional[Length] = Field(
        default=None, description="Indent per heading level below the first "
                                  "(documented fallback 14).")


class BibliographyFlow(BreakFields):
    type: Literal["bibliography"] = Field(
        description="Discriminator: a generated bibliography from cited keys.")
    title: Optional[str] = Field(default=None, description="Bibliography title text.")
    source: Optional[str] = Field(
        default=None, description="defs.data key of the CSL-JSON source to draw entries from.")
    csl: Optional[str] = Field(default=None, description="Citation style (CSL style name/source).")
    entries: Optional[list[dict]] = Field(
        default=None, description="Inline CSL-JSON entries (alternative to `source`).")
    id: Optional[str] = Field(default=None, description="Stable id for `ref` cross-references.")


Flowable = Annotated[
    Union[
        ParagraphFlow, HeadingFlow, ListFlow, SpacerFlow, PageBreakFlow, ColumnBreakFlow,
        TableFlow, ImageFlow, FigureFlow, BlockFlow, KeepTogetherFlow,
        CodeFlow, MathFlow, TocFlow, BibliographyFlow,
    ],
    Field(discriminator="type"),
]


# --------------------------------------------------------------------------- #
#  Pages, masters, canvas                                                     #
# --------------------------------------------------------------------------- #
class CanvasObject(FG):
    preset: Optional[PagePreset] = Field(
        default=None, description="Named canvas preset (pixel sizes mirror the renderer's "
                                  "CanvasResolver.PRESETS); exactly one of `preset` or `size`.")
    size: Optional[Annotated[list[float], Field(min_length=2, max_length=2)]] = Field(
        default=None, description="[width, height] in `units`; exactly one of `preset` or `size`.")
    units: Optional[Units] = Field(
        default=None, description="Unit of `size` (default px; pt/px treated 1:1 by the renderer).")
    orientation: Optional[Literal["portrait", "landscape"]] = Field(
        default=None, description="Swap preset width/height for landscape.")
    bleed: Optional[Length] = Field(
        default=None, description="Bleed extended beyond the canvas on all sides (print).")
    margin: Optional[Box] = Field(
        default=None, description="Default content margin [top, right, bottom, left].")
    background: Optional[Color] = Field(
        default=None, description="Page background colour (token or literal), painted behind "
                                  "all layers/flow content. Absent = the renderer's documented "
                                  "white default (ADR-0006 sanctioned fallback).")

    @model_validator(mode="after")
    def _preset_or_size(self):
        if (self.preset is None) == (self.size is None):
            raise ValueError("a canvas object needs exactly one of `preset` or `size`")
        return self


CanvasSpec = Union[PagePreset, CanvasObject]


class FlowRegion(FG):
    id: str = Field(description="Region id (referenced by another region's `next`).")
    box: Box = Field(description="Region box [x, y, w, h] on the master's canvas.")
    columns: Optional[int] = Field(default=None, description="Column count inside the region.")
    column_gap: Optional[Length] = Field(default=None, description="Gap between columns.")
    column_fill: Optional[Literal["auto", "balance"]] = Field(
        default=None, description="Fill columns sequentially (auto) or balance heights.")
    column_rule: Optional[BorderSide] = Field(
        default=None, description="Rule line drawn between columns.")
    next: Optional[str] = Field(
        default=None, description="Id of the region the story continues into (same master).")


class Running(FG):
    header: Optional[list[VisualObject]] = Field(
        default=None, description="Objects repeated at the top of every page using the master.")
    footer: Optional[list[VisualObject]] = Field(
        default=None, description="Objects repeated at the bottom of every page using the master.")
    page_number: Optional[Union[bool, Style]] = Field(
        default=None, description="Draw the page number: true for default styling, or a Style.")


class PageMaster(FG):
    canvas: CanvasSpec = Field(description="Canvas of pages produced from this master.")
    margin: Optional[Box] = Field(
        default=None, description="Content margin [top, right, bottom, left].")
    fixed: Optional[list[VisualObject]] = Field(
        default=None, description="Objects painted on every page before flow content.")
    regions: Optional[list[FlowRegion]] = Field(
        default=None, description="Flow regions the story fills, chained via `next`.")
    running: Optional[Running] = Field(
        default=None, description="Repeating header/footer/page-number furniture.")
    footnote_area: Optional[FlowRegion] = Field(
        default=None, description="Region collecting footnote content on each page.")
    next: Optional[str] = Field(
        default=None, description="Master used for continuation pages (defs.masters key).")


class Layer(FG):
    id: str = Field(description="Layer id (unique within the page).")
    role: Optional[Literal["geometry", "construction", "annotation", "dimension"]] = Field(
        default=None, description="Semantic role of the layer. 'construction' layers are "
                                  "non-printing (their objects render only under "
                                  "meta.show_construction); other roles declare intent for "
                                  "tooling without changing paint behaviour.")
    z: Optional[float] = Field(
        default=None, description="Layer stacking order (higher paints later).")
    opacity: Optional[UnitInterval] = Field(
        default=None, description="Layer opacity in 0..1, composited over lower layers.")
    objects: Optional[list[VisualObject]] = Field(
        default=None, description="The layer's visual objects, in paint order.")


class TextContract(FG):
    min_font_size: Optional[float] = Field(
        default=None, description="Floor font size for shrink_to_fit across the scope.")
    overflow: Optional[Literal["visible", "clip", "shrink_to_fit"]] = Field(
        default=None, description="Default text-overflow policy across the scope.")
    line_clamp: Optional[int] = Field(
        default=None, description="Default maximum rendered line count.")
    text_overflow: Optional[Literal["clip", "ellipsis"]] = Field(
        default=None, description="Marker for clamped text (clip or ellipsis).")


class RenderingContract(FG):
    coordinate_mode: Optional[Literal["absolute", "flow"]] = Field(
        default=None, description="Whether object boxes are absolute or flow-computed.")
    text: Optional[TextContract] = Field(
        default=None, description="Text fitting/overflow defaults for the page (the "
                                  "normative home of text_contract).")
    typography: Optional[dict] = Field(
        default=None, description="Loose typography hints bag (renderer-specific; not deeply typed).")
    semantics: Optional[dict] = Field(
        default=None, description="Loose semantic hints bag for tagged export (not deeply typed).")
    debug_boxes: Optional[bool] = Field(
        default=None, description="Draw layout boxes for debugging.")
    preserve_manual_line_breaks: Optional[bool] = Field(
        default=None, description="Keep authored \\n line breaks instead of re-wrapping.")


class PageLink(FG):
    to: str = Field(description="Target page id (or external URL when `external` is true).")
    relation: Optional[Literal["next", "prev", "see_also", "appendix", "source", "child", "parent", "external"]] = Field(
        default=None, description="Navigation relation of the link.")
    label: Optional[str] = Field(default=None, description="Human-readable link label.")
    external: Optional[bool] = Field(
        default=None, description="Marks `to` as an external URL rather than a page id.")


class BloomEffect(FG):
    """A3 raster post: screen-composite glow around above-threshold luminance."""
    radius: float = Field(
        default=8.0, gt=0,
        description="Halo spread in canvas px (scaled by the raster zoom).")
    strength: UnitInterval = Field(
        default=0.5, description="Halo intensity 0..1 (screen-composited).")
    threshold: UnitInterval = Field(
        default=0.75, description="Luminance floor 0..1: pixels at or above it bloom.")


class GrainEffect(FG):
    """A3 raster post: deterministic seeded sensor/film grain."""
    amount: UnitInterval = Field(
        description="Noise sigma as a fraction of full scale (0..1; ~0.02-0.06 is film-like).")
    seed: int = Field(
        default=0, ge=0,
        description="Deterministic noise seed — same seed, same bytes; never wall-clock.")
    monochrome: Optional[bool] = Field(
        default=None, description="Luminance-only noise (default) vs per-channel colour noise.")


class PostEffects(FG):
    """Page-level raster post effects (A3): applied to the rasterized PNG in the
    fixed order blur → bloom → grain. Vector targets (SVG/PDF/TeX) are
    byte-unaffected — the renderer notes a structured `post_raster_only` warning
    so the degradation is observable (PALS). Radii are canvas px, multiplied by
    the raster zoom."""
    blur: Optional[float] = Field(
        default=None, ge=0,
        description="Gaussian soft-focus radius in canvas px over the final raster.")
    bloom: Optional[BloomEffect] = Field(
        default=None, description="Glow around bright regions (JPEG/photographic bloom).")
    grain: Optional[GrainEffect] = Field(
        default=None, description="Seeded noise floor (matches soft-media references).")


class Page(FG):
    mode: Literal["page"] = Field(
        description="Discriminator: a fixed page of absolutely-placed layers.")
    id: str = Field(description="Page id (unique within the document; PageLink target).")
    master: Optional[str] = Field(
        default=None, description="defs.masters key supplying canvas/fixed/running furniture.")
    canvas: Optional[CanvasSpec] = Field(
        default=None, description="Page canvas (preset name or explicit object); defaults to "
                                  "the master's canvas, else the renderer default.")
    rendering: Optional[RenderingContract] = Field(
        default=None, description="Per-page rendering contract overrides.")
    layers: Optional[list[Layer]] = Field(
        default=None, description="Paint layers, ordered by z (then list order).")
    reading_order: Optional[list[str]] = Field(
        default=None, description="Object ids in logical reading order (a11y; checked by the lint).")
    semantic: Optional[dict] = Field(
        default=None, description="Loose semantic annotations for the page (not deeply typed).")
    links: Optional[list[PageLink]] = Field(
        default=None, description="Page-level navigation links.")
    notes: Optional[str] = Field(default=None, description="Author/presenter notes (not rendered).")
    post: Optional[PostEffects] = Field(
        default=None,
        description="Raster-stage post effects (blur → bloom → grain), applied to the "
                    "rasterized PNG only; vector targets are unaffected and carry a "
                    "structured warning. (A3, HEAD)")
    meta: Optional[dict] = Field(
        default=None, description="Free-form annotation bag; never interpreted by the renderer.")


class FlowSection(FG):
    mode: Literal["flow"] = Field(
        description="Discriminator: a flowed section paginated through a master's regions.")
    id: str = Field(description="Section id (unique within the document).")
    master: str = Field(
        description="defs.masters key whose regions the story flows through (must resolve).")
    story: list[Flowable] = Field(description="The section's block content, in order.")
    media: Optional[Literal["paged", "continuous"]] = Field(
        default=None, description="Paginate into pages, or lay out as one continuous canvas (P2).")
    page_numbering: Optional[dict] = Field(
        default=None, description="Loose page-numbering options bag (start/format; not deeply typed).")
    lang: Optional[str] = Field(default=None, description="BCP-47 language of the section.")
    links: Optional[list[PageLink]] = Field(
        default=None, description="Section-level navigation, mirroring Page.links.")
    semantic: Optional[dict] = Field(
        default=None, description="Loose semantic annotations for the section (not deeply typed).")
    meta: Optional[dict] = Field(
        default=None, description="Free-form annotation bag; never interpreted by the renderer.")


PageProducer = Annotated[Union[Page, FlowSection], Field(discriminator="mode")]


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


# Resolve forward references (recursive groups, footnotes-in-spans, blocks).
for _m in (
    Style, Gradient, GradientStop, FootnoteInline, LinkInline, Group, Text, FigureFlow, BlockFlow,
    KeepTogetherFlow, ListFlow, Running, PageMaster, Layer,
):
    _m.model_rebuild()
Document.model_rebuild()


__all__ = ["Document", "HEAD_VERSION"]
