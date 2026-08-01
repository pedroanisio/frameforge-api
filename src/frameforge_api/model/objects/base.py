"""`ObjBase`: the common-object-fields mixin, and the P3 stroke single-form guard.

The guard runs `mode="before"` so it fires for every visual object subclass in
this package, not just the ones that happen to declare a `stroke`.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional
from pydantic import Field, model_validator

from ..base import Box, FG, Point, UnitInterval
from ..humanize import Humanize
from ..layout import AppearancePass, Effect, EffectStackEntry, OuterRing, RotationOrNumber, Sizing
from ..style import StrokeStyleRef, StyleRef


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
