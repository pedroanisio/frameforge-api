"""Inline content: the span algebra that flows inside text.

Inline content and block content are mutually recursive in the domain — a
footnote holds blocks, and those blocks hold inlines — so `FootnoteInline.content`
forward-references `Flowable`, which lives downstream in `flow`. That is the only
back-edge in the package; every other dependency runs one way, base outward.

It cannot be closed by moving the class: `FootnoteInline` is a member of the
`Inline` union, `objects` depends on `Inline`, and `flow` depends on `objects`.
So the reference stays deferred, and the package `__init__` publishes `Flowable`
into this module's namespace immediately before rebuilding the models — see the
note above the rebuild sweep there.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional, Union
from pydantic import Field

from .base import FG, Length
from .style import StyleRef

if TYPE_CHECKING:
    from .flow import Flowable


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


class RubyInline(FG):
    """Ruby annotation: a pronunciation or gloss set alongside a base run.

    The contract has carried `writing_mode`, `direction` and `unicode_bidi`
    since 2.2.0, so vertical Japanese has always been expressible — and until
    2.9.0 it could not be annotated, which is the single most common thing done
    to it. `text` may be one annotation for the whole base (group ruby) or one
    per base character (mono ruby); both are in daily use and the renderer
    cannot infer which was meant, so the shape says it.
    """
    kind: Literal["ruby"] = Field(description="Discriminator: a ruby-annotated run.")
    base: Union[str, list["Inline"]] = Field(
        description="The annotated text: a plain string, or inline content.")
    text: Union[str, list[str]] = Field(
        description="The annotation. A string annotates the whole base (group ruby); a list "
                    "annotates base characters one for one (mono ruby).")
    position: Optional[Literal["over", "under", "inter-character"]] = Field(
        default=None, description="Where the annotation sits relative to the base. Absent = over "
                                  "for horizontal text, right for vertical (the CSS default).")
    align: Optional[Literal["start", "center", "space-between", "space-around",
                            "distribute-letter", "distribute-space"]] = Field(
        default=None, description="Distribution of the annotation across the base (CSS ruby-align).")
    size: Optional[Length] = Field(
        default=None, description="Annotation type size; absent = the renderer's ruby default "
                                  "(conventionally half the base size).")


class WarichuInline(FG):
    """Warichu: an inline note set as two or more short lines inside the text line.

    Distinct from a footnote, which leaves the line and lands in the page's note
    area. A warichu stays in the run and simply sets narrower, so it is inline
    content, not block content.
    """
    kind: Literal["warichu"] = Field(description="Discriminator: an inline split-line note.")
    content: list["Inline"] = Field(description="The note's inline content.")
    lines: Optional[int] = Field(
        default=None, ge=2, le=4,
        description="Lines the note is split across; absent = 2, the convention.")
    brackets: Optional[Literal["none", "parenthesis", "bracket", "tortoise", "lenticular"]] = Field(
        default=None, description="Enclosing marks drawn around the note.")


Inline = Union[str, RefInline, CiteInline, MathInline, CodeInline, FootnoteInline, LinkInline,
               Span, RubyInline, WarichuInline]


Caption = Union[str, list[Inline]]
