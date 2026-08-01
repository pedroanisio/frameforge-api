"""UML 2.5 visual objects (the semantic ontology lives in `sdk.uml_models`).
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import ConfigDict, Field

from ..base import Color, Point
from .base import ObjBase


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
