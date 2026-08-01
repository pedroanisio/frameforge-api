"""humanize — a seeded, bounded "hand" (the imperfection layer).
"""
from __future__ import annotations

from pydantic import Field

from .base import FG


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
