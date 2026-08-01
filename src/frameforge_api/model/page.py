"""Pages, masters, canvas — the page-producing side of a document.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union
from pydantic import Field, model_validator

from .base import Box, Color, FG, Length, PagePreset, UnitInterval, Units
from .flow import Flowable
from .layout import BaselineGrid
from .objects import VisualObject
from .style import BorderSide, Style


# --------------------------------------------------------------------------- #
#  Pages, masters, canvas                                                     #
# --------------------------------------------------------------------------- #
#: Which side of a bound leaf a page falls on. Recto is the right-hand page (odd
#: folio), verso the left. A book's margins mirror across the two, which is why
#: this is contract rather than presentation.
PageSide = Literal["recto", "verso"]


class PageMargin(FG):
    """Named page margins, including the two a bound book needs.

    `[top, right, bottom, left]` describes a sheet. A bound book is described in
    *spine-relative* terms — `inside` sits against the binding, `outside` at the
    fore-edge — because the two swap sides on every turn of the leaf. Twelve
    `book-*` trim presets shipped from the start with no way to say this; a
    verso page could only be laid out by mirroring the numbers by hand.

    `gutter` is the extra allowance added at the binding edge on top of
    `inside`, for the paper the fold and the glue consume.

    The two vocabularies are mutually exclusive per axis: `left`/`right` and
    `inside`/`outside` name the same two edges, so accepting both would mean
    silently choosing one, and the wrong choice misplaces the text block on
    every other page of the book.
    """
    top: Optional[Length] = Field(default=None, description="Head margin.")
    bottom: Optional[Length] = Field(default=None, description="Foot margin.")
    left: Optional[Length] = Field(
        default=None, description="Left margin (sheet-relative; excludes inside/outside).")
    right: Optional[Length] = Field(
        default=None, description="Right margin (sheet-relative; excludes inside/outside).")
    inside: Optional[Length] = Field(
        default=None, description="Spine-side margin (binding edge); excludes left/right.")
    outside: Optional[Length] = Field(
        default=None, description="Fore-edge margin; excludes left/right.")
    gutter: Optional[Length] = Field(
        default=None, description="Extra allowance at the binding edge, added to `inside` "
                                  "(or to the spine side of left/right) for fold and glue.")

    @model_validator(mode="after")
    def _one_horizontal_vocabulary(self):
        sheet = self.left is not None or self.right is not None
        bound = self.inside is not None or self.outside is not None
        if sheet and bound:
            raise ValueError(
                "`left`/`right` and `inside`/`outside` are two names for the same two "
                "edges; use one vocabulary. Sheet-relative for loose pages, "
                "spine-relative (inside/outside) for anything bound.")
        return self


#: A margin as four lengths, or named — including the spine-relative pair.
MarginSpec = Union[Box, PageMargin]


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
    margin: Optional[MarginSpec] = Field(
        default=None, description="Default content margin: [top, right, bottom, left], or a "
                                  "named PageMargin (which adds inside/outside/gutter for "
                                  "bound work).")
    spread: Optional[bool] = Field(
        default=None, description="This canvas is a two-page spread — one sheet spanning a "
                                  "verso and a recto, with the binding down the middle. "
                                  "Absent = a single page.")
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
    margin: Optional[MarginSpec] = Field(
        default=None, description="Content margin: [top, right, bottom, left], or a named "
                                  "PageMargin (inside/outside/gutter for bound work).")
    side: Optional[Union[PageSide, Literal["any"]]] = Field(
        default=None, description="Which side of the leaf this master lays out. A bound book "
                                  "declares a recto master and a verso master so their "
                                  "spine-relative margins mirror. Absent = any.")
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
    measure: Optional[Annotated[list[int], Field(min_length=2, max_length=2)]] = Field(
        default=None,
        description="[min, max] intended line measure in CHARACTERS — the column width the "
                    "type is meant to be read at. Leading fixes the vertical increment; "
                    "measure fixes the horizontal one, and the two together are what make a "
                    "column readable. Advisory: it constrains nothing structurally, and is "
                    "checked by the engine's validator, which can measure a resolved line. "
                    "45-75 is the conventional range for continuous prose (2.10.0).")

    @model_validator(mode="after")
    def _measure_is_an_ordered_positive_range(self):
        if self.measure is None:
            return self
        low, high = self.measure
        if low <= 0:
            raise ValueError("text_contract.measure bounds are character counts, so both "
                             "must be positive")
        if low > high:
            raise ValueError(f"text_contract.measure is [min, max]; got [{low}, {high}], "
                             f"which is inverted")
        return self


class RenderingContract(FG):
    coordinate_mode: Optional[Literal["absolute", "flow"]] = Field(
        default=None, description="Whether object boxes are absolute or flow-computed.")
    text: Optional[TextContract] = Field(
        default=None, description="Text fitting/overflow defaults for the page (the "
                                  "normative home of text_contract).")
    baseline_grid: Optional[BaselineGrid] = Field(
        default=None,
        description="Per-page override of `defs.baseline_grid` — the frame-level scope, for "
                    "a page whose leading differs from the document's (a chapter opening, a "
                    "notes page set smaller). Absent = inherit the document grid. Typed "
                    "deliberately rather than added to the loose `typography` bag: the grid "
                    "changes where every baseline lands, which is not a hint (2.10.0).")
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
    side: Optional[PageSide] = Field(
        default=None, description="Which side of the leaf this page falls on. Fixes the folio "
                                  "parity of a bound sequence — and therefore which way its "
                                  "spine-relative margins face. Absent = inferred from position.")
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
