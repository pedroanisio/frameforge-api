"""The visual objects, and the `VisualObject` union over them.

`Group` is declared here rather than beside the other container objects, and
that placement is load-bearing: its `children` field forward-references the
union, and a forward reference resolves against the namespace of the module that
declares the class. Keeping the two together is what lets the whole package be
acyclic — the alternative is a `TYPE_CHECKING` import plus a namespace injection
at rebuild time, for one field.

Union member order is contract, not style: it fixes the `anyOf` order in the
generated JSON Schema.

This module also re-exports every name its submodules declare, so `objects` can
be treated as one component from outside.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union
from pydantic import Field

from ..layout import Layout
from .base import MatteMode, MatteSpec, ObjBase
from .connector import (
    Connector,
    ConnectorAnchor,
    ConnectorEndpoint,
    ConnectorLabel,
    ConnectorRoute,
)
from .content import BulletList, Dimension, GenerationParams, GenerativeObject, Icon, Image, Text
from .paths import (
    Curve,
    Path,
    PathCommand,
    PathSeg,
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
from .shapes import Circle, Ellipse, Line, Polygon, Polyline, Rect, Star, StarType
from .table import Cell, CellValue, ColumnSpec, ColumnSpecVal, TableObject
from .uml import (
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
)


class Group(ObjBase):
    type: Literal["group"] = Field(
        description="Discriminator: container establishing a local coordinate system (§3.6); "
                    "child boxes are parent-relative.")
    children: list["VisualObject"] = Field(description="Child objects, in paint order.")
    layout: Optional[Layout] = Field(
        default=None, description="Child placement algorithm; absent behaves as kind: free.")


VisualObject = Annotated[
    Union[
        Rect, Ellipse, Circle, Line, Polyline, Polygon, Star, Path, Curve,
        Text, Image, GenerativeObject, Icon, BulletList, Dimension, Connector, TableObject, Group,
        UMLMarkerGlyph, UMLClassifierBox, UMLComponentBox, UMLStateBox,
        UMLAction, UMLArtifactBox, UMLNodeBox, UMLLifeline, UMLActivationBar,
        UMLActorObject, UMLSocket, UMLLollipop, UMLActivityNodeObject,
        UMLPseudostateObject, UMLFragmentFrame, UMLSwimlane, UMLTimingLane,
    ],
    Field(discriminator="type"),
]
