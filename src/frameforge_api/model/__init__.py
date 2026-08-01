"""
FrameForge v2 — HEAD models (the single source of truth).
=========================================================

These Pydantic v2 models are the authoritative definition of the FrameForge v2
*core conformance profile* at HEAD. This package is the whole reason
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

This package folds in the full patch series and the complement's recommendations:

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

Layout of the package
---------------------
The declarations were a single 2,128-line module until they were split along the
section boundaries the file already carried. Nothing was edited in the move: the
generated JSON Schema is byte-identical, and `tests/golden/declarations.json`
compares every declaration's AST against its pre-split form.

Modules are ordered by dependency, base first::

    version      HEAD_VERSION — the contract clock
    base         FG (the closed base) + the pattern-gated scalars
    style        the authoritative style module (2.2.0)
    assets       fonts and assets
    layout       layout, sizing, effect/appearance stacks
    inline       the inline span algebra
    humanize     the seeded imperfection layer
    objects/     the visual objects, and the VisualObject union
    flow         flowables (story content)
    page         canvas, masters, pages
    document     tokens, defs, targets, Document

**Everything declared in any of them is importable from here**, which is the
interface consumers actually hold: ``from frameforge_api.model import Style``
resolves regardless of which file `Style` currently lives in. `__all__` stays
narrow (`Document`, `HEAD_VERSION`) because those are what a *document*
compatibility decision is made against — it is a statement about emphasis, not a
restriction on what may be imported.
"""
from __future__ import annotations

from .assets import AssetDef, FontDef, FontDefOrName
from .base import (
    ANGLE_STR_RE,
    DASH_ARRAY_STR_RE,
    DASH_TOKEN_RE,
    FG,
    LENGTH_STR_RE,
    PERCENT_STR_RE,
    Align,
    Box,
    CmykColor,
    Color,
    ColorObject,
    DashArray,
    DashArrayString,
    IccColor,
    Length,
    NumberFormat,
    Padding,
    PagePreset,
    Point,
    ShapeDirection,
    SpotColor,
    Units,
    UnitInterval,
    VAlign,
)
from .document import (
    SEMVER_RE,
    ColorProfileDef,
    CounterDef,
    Defs,
    Document,
    RenderOutput,
    RenderTarget,
    SymbolDef,
    TargetAdjustments,
    Tokens,
)
from .flow import (
    BibliographyFlow,
    BlockFlow,
    BreakFields,
    CodeFlow,
    ColumnBreakFlow,
    FigureFlow,
    Flowable,
    HeadingFlow,
    ImageFlow,
    KeepTogetherFlow,
    ListFlow,
    ListItemFlow,
    ListItemVal,
    MathFlow,
    PageBreakFlow,
    ParagraphFlow,
    SpacerFlow,
    StringSet,
    TableFlow,
    TocFlow,
)
from .humanize import Humanize
from .inline import (
    Caption,
    CiteInline,
    CodeInline,
    FootnoteInline,
    Inline,
    LinkInline,
    MathInline,
    RefInline,
    RubyInline,
    Span,
    WarichuInline,
)
from .layout import (
    Anchor,
    AnchorObject,
    AppearancePass,
    BaselineGrid,
    ClipSpec,
    ClipSpecOrBool,
    Effect,
    EffectObject,
    EffectStackEntry,
    Layout,
    Number,
    OuterRing,
    Rotation,
    RotationOrNumber,
    SizeMode,
    Sizing,
)
from .objects import (
    BulletList,
    Cell,
    CellValue,
    Circle,
    ColumnSpec,
    ColumnSpecVal,
    Connector,
    ConnectorAnchor,
    ConnectorEndpoint,
    ConnectorLabel,
    ConnectorRoute,
    Curve,
    Dimension,
    Ellipse,
    GenerationParams,
    GenerativeObject,
    Group,
    Icon,
    Image,
    Line,
    MatteMode,
    MatteSpec,
    ObjBase,
    Path,
    PathCommand,
    PathSeg,
    Polygon,
    Polyline,
    Rect,
    Star,
    StarType,
    TableObject,
    Text,
    UMLAction,
    UMLActivationBar,
    UMLActivityNodeObject,
    UMLActorObject,
    UMLArtifactBox,
    UMLClassifierBox,
    UMLComponentBox,
    UMLFragmentFrame,
    UMLLifeline,
    UMLLollipop,
    UMLMarkerGlyph,
    UMLNodeBox,
    UMLPseudostateObject,
    UMLSocket,
    UMLStateBox,
    UMLSwimlane,
    UMLTimingLane,
    UMLVisualBase,
    VisualObject,
    _SegArc,
    _SegClose,
    _SegCubic,
    _SegHoriz,
    _SegLine,
    _SegMove,
    _SegQuad,
    _SegSmooth,
    _SegTquad,
    _SegVert,
)
from .page import (
    BloomEffect,
    CanvasObject,
    CanvasSpec,
    FlowRegion,
    FlowSection,
    GrainEffect,
    Layer,
    MarginSpec,
    Page,
    PageLink,
    PageMargin,
    PageMaster,
    PageProducer,
    PageSide,
    PostEffects,
    RenderingContract,
    Running,
    TextContract,
)
from .style import (
    ARROW_MARKER_KINDS,
    Angle,
    ArrowMarkerKind,
    BackgroundLayer,
    BlendMode,
    Border,
    BorderSide,
    ClipPath,
    ClipPathVal,
    Edges,
    Fill,
    Filter,
    FilterFn,
    FontStretch,
    FontStyle,
    Gradient,
    GradientStop,
    ImagePaint,
    Overflow,
    Paint,
    Pattern,
    Percentage,
    Radius,
    Shadow,
    ShadowVal,
    SizeValue,
    StrList,
    StrokeStyle,
    StrokeStyleRef,
    Style,
    StyleRef,
    TextDecoration,
    TextDecorationVal,
    TextStyle,
    TransformFn,
    UrlImage,
)
from .version import HEAD_VERSION

# `FootnoteInline.content` is the package's one back-edge: inline content and
# block content are mutually recursive (a footnote holds blocks; blocks hold
# inlines), and no placement of the class removes that. `inline` therefore
# defers the import, and the name is published into its namespace here — the
# module globals are exactly where `model_rebuild()` below will look for it.
#
# Every other forward reference resolves inside its own declaring module, which
# is why `Group` sits beside the `VisualObject` union rather than beside the
# other container objects.
from . import inline as _inline

_inline.Flowable = Flowable

# Resolve forward references (recursive groups, footnotes-in-spans, blocks).
#
# Deferred to here, and not to each declaring module, because a forward
# reference is only resolvable once every name it might mention exists.
for _m in (
    Style, Gradient, GradientStop, FootnoteInline, LinkInline, Group, Text, FigureFlow, BlockFlow,
    KeepTogetherFlow, ListFlow, Running, PageMaster, Layer,
    # 2.9.0: ruby and warichu carry inline content, so they forward-reference
    # the union they are themselves members of.
    RubyInline, WarichuInline,
):
    _m.model_rebuild()
Document.model_rebuild()


# Order is upstream's, and the declarations golden compares it. RUF022 would
# alphabetise it; that is why the rule is off for this package.
__all__ = ["Document", "HEAD_VERSION"]
