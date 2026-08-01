"""THE STYLE MODULE (authoritative) — adopted at 2.2.0.

Faithful translation of `grammar/frameforge-v2-style.ebnf`. `Style` is the
CSS-parity bag; TextStyle and StrokeStyle are PROJECTIONS of it; fill/stroke are
`Paint` (= colour | image | gradient | pattern). `class` composes named token
styles; `css` is the bounded raw-CSS escape (§8.4).
"""
from __future__ import annotations

import re

from typing import Annotated, Literal, Optional, Union, get_args
from pydantic import ConfigDict, Field, model_validator

from .base import ANGLE_STR_RE, Color, DASH_ARRAY_STR_RE, DashArray, FG, Length, PERCENT_STR_RE, Point, UnitInterval


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


# "none"|"currentColor"|<color>|<image>|<pattern>. The trailing `Color` is the
# colour branch: since 2.9.0 that is a string OR a typed ink (CMYK/spot/ICC),
# so every paintable surface accepts print colour without a second spelling.
Paint = Union[Gradient, Pattern, UrlImage, Color]


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
    align_to_baseline: Optional[bool] = Field(
        default=None,
        description="FG typographic extension (2.10.0): snap this block's baselines to the "
                    "resolved baseline grid (`rendering.baseline_grid`, else "
                    "`defs.baseline_grid`), so type lines up across columns, spreads and "
                    "facing pages. Absent/False = free leading. Aligning to the grid rounds "
                    "each line down to the next gridline, so a block whose `line_height` "
                    "exceeds the grid increment will open up to a whole multiple of it — set "
                    "the increment to the body leading. Nothing happens if no grid is in "
                    "scope. Not a CSS property.")
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
    # ---- prepress ink behaviour (2.9.0) ----
    # CSS has no equivalent: on screen the topmost paint simply wins. On press,
    # whether the ink underneath is removed (knockout, the default) or printed
    # through (overprint) is a per-object decision that changes the plates, and
    # getting it wrong shows up only on the printed sheet.
    overprint: Optional[Literal["none", "fill", "stroke", "both"]] = Field(
        default=None, description="Which paints overprint the ink beneath instead of knocking "
                                  "it out. Absent = the renderer's default (knockout).")
    overprint_mode: Optional[Literal["zero-cmyk", "nonzero-cmyk"]] = Field(
        default=None, description="PDF overprint mode (OPM). zero-cmyk: a 0 component erases the "
                                  "ink below; nonzero-cmyk: a 0 component leaves it untouched.")
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
