"""frameforge-api — the FrameForge v2 document contract, standalone.

This distribution is the **contract layer** of the FrameForge family: the
authoritative Pydantic models, the JSON Schema generated from them, and the
version they both pin. Nothing here renders, lays out, or authors anything.

Why it is its own package
-------------------------
The models are a true leaf — they import ``re``, ``typing`` and ``pydantic``,
and nothing else. Every other FrameForge package (the authoring SDK, the render
engine, the MCP server, third-party tooling) needs to agree on *what a document
is*, and none of them should have to depend on an engine to find out. Depending
on a 24k-line SDK to learn the shape of a `Document` is the coupling this split
removes.

The contract is deliberately narrow:

  * :class:`Document` — the root model; ``Document.model_validate(data)`` is the
    structural verdict. Every object sets ``extra="forbid"``, so an unknown key
    is an error rather than silent data loss.
  * :data:`HEAD_VERSION` — the contract revision the models target. Consumers
    should range-pin against it rather than copying the string.
  * :func:`build_schema` / :data:`SCHEMA_PATH` — the same contract as JSON
    Schema, shipped in the wheel so non-Python consumers can validate too.

What is NOT here (by design)
----------------------------
Structural validity is necessary, not sufficient. The static/semantic rules a
JSON Schema cannot express — referential integrity, containment, text fit, ink
collisions, paint intent — live with the engine that can measure them, in the
``frameforge`` distribution's validator. A document that passes
``Document.model_validate`` is *well-formed*, not *well-made*.

Usage
-----
    >>> from frameforge_api import Document, HEAD_VERSION
    >>> doc = Document.model_validate({
    ...     "dsl": "FrameForge",
    ...     "version": HEAD_VERSION,
    ...     "title": "Hello",
    ...     "pages": [{
    ...         "mode": "page", "id": "p1",
    ...         "canvas": {"size": [400, 200], "units": "px"},
    ...         "layers": [{"id": "main", "objects": [
    ...             {"type": "text", "box": [20, 20, 360, 40], "text": "Hello"},
    ...         ]}],
    ...     }],
    ... })
    >>> doc.title
    'Hello'
"""
from __future__ import annotations

from frameforge_api import deprecations
from frameforge_api.deprecations import migrate as migrate_document
from frameforge_api.deprecations import scan as scan_document
from frameforge_api.model import HEAD_VERSION, Document
from frameforge_api.schema import SCHEMA_PATH
from frameforge_api.schema import build as build_schema
from frameforge_api.schema import check as check_schema
from frameforge_api.schema import load as load_schema

#: The PACKAGE version — this distribution's own release line, independent of
#: the contract it carries.
#:
#: Two different clocks, and conflating them was the mistake worth avoiding:
#:
#:   * :data:`HEAD_VERSION` (``2.11.0``) is the FrameForge **document format**
#:     revision. It moves when the *contract* moves — a new field, a retyped
#:     one — and every FrameForge package must agree on it.
#:   * :data:`__version__` (``1.x.y``) is the **wheel**. It moves when this
#:     package changes: a packaging fix, a new helper, a CLI flag.
#:
#: A packaging bug fix must not claim the document format changed, and a format
#: change must not force a major bump of a package whose API did not move. Pin
#: the distribution with ``frameforge-api>=1.0``; branch on ``HEAD_VERSION``
#: when you need to know what the *document* contract supports.
__version__ = "1.2.0"

#: The FrameForge document-format revision carried by this package. Re-exported
#: at the root because it, not `__version__`, is what document-level
#: compatibility is decided against.
CONTRACT_VERSION = HEAD_VERSION

#: What a move of :data:`HEAD_VERSION` inside the 2.x line promises a DOCUMENT.
#:
#: SemVer says what the *numbers* mean; it does not answer the only question a
#: consumer actually has, which is whether the file they wrote last year still
#: parses. This does, in the schema-registry sense the term carries in Avro and
#: Kafka:
#:
#:   ``backward`` — a document valid under ANY earlier 2.x revision stays valid
#:   at HEAD. Within the line, a change may add an optional field, add a union
#:   member, widen a type, relax a constraint, or make a required field
#:   optional. It may not add a required field, remove or rename one, drop a
#:   union member, narrow a type, tighten a constraint, or change what an
#:   existing value means.
#:
#: The reverse (a HEAD document read by an older validator) is deliberately NOT
#: promised: a reader that predates spot ink cannot interpret it.
#:
#: The 2.x line had held this property since 2.0.0 without stating it, which
#: made it an accident rather than a guarantee. `tests/test_backward_compat.py`
#: is what turns it into one — it replays a committed corpus of older documents,
#: and the whole monorepo fixture corpus by declared revision, on every run.
COMPATIBILITY = "backward"

#: Every deprecated form in the contract, as data rather than as prose.
#:
#: Deprecation used to live only inside English ``description`` strings, which
#: meant no tool could see it: a codegen pass, an editor, or a model reading the
#: JSON Schema had nothing to key on. It is machine-readable now — here, and in
#: the schema under ``x-frameforge-deprecations``.
#:
#: Backward compatibility puts a hard floor under what "deprecated" can mean in
#: this line: a form valid under an earlier 2.x revision cannot start being
#: rejected at HEAD, so these stay valid until 3.0. Discouraged, mechanically
#: migratable (:func:`migrate_document` / ``ff-codemod``), and still accepted.
DEPRECATIONS = deprecations.DEPRECATIONS

__all__ = [
    "COMPATIBILITY",
    "CONTRACT_VERSION",
    "DEPRECATIONS",
    "HEAD_VERSION",
    "SCHEMA_PATH",
    "Document",
    "__version__",
    "build_schema",
    "check_schema",
    "deprecations",
    "load_schema",
    "migrate_document",
    "model",
    "scan_document",
]
