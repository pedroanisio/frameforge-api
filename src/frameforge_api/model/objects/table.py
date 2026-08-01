"""Tables: cells, column specs, and the table object.

`Group`, the other container object, is not here — it lives in this package's
`__init__` beside the `VisualObject` union its `children` field refers to.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union
from pydantic import Field

from ..base import Align, FG, Length
from ..inline import Span
from .base import ObjBase
from ..style import StyleRef


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
