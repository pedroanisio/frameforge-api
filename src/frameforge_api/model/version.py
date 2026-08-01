"""The contract version this package carries.

Its own module because it is the one declaration here that is not a type: it
names the FrameForge *document format* revision, which releases on a different
clock from the wheel (see `frameforge_api.__version__`).
"""
from __future__ import annotations


HEAD_VERSION = "2.8.2"  # v2 line; 2.4.0 adds the ordered per-object effect stack (`effects`) and the multi-pass appearance stack (`appearance`) — additive, outside the deep-core profile (§8.5, W4/#48). 2.3.0 added typed Connector, per-field schema descriptions, R12 referential integrity, Length/Angle value patterns (additive). 2.2.0 adopted the authoritative style module; P3 stroke collapse remains the one breaking change (codemod provided).
