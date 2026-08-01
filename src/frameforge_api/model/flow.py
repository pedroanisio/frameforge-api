"""Flowables — story content, paginated through a master's regions.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union
from pydantic import Field, model_validator

from .base import FG, Length, Units
from .inline import Caption, Inline
from .layout import Number
from .objects import VisualObject
from .objects.table import CellValue, ColumnSpecVal
from .style import Edges, Fill, Paint, StrokeStyleRef, StyleRef


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
