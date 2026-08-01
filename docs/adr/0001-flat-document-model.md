---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 5 via Claude Code"
  date: "2026-08-01"
---

# ADR 0001 — A validated document is flat

**Status:** accepted · **Date:** 2026-08-01 · **Contract:** 2.10.0

## Context

Comparing the contract against [Lottie 1.0](https://lottie.github.io/lottie-spec/1.0/)
surfaced one structural difference that is not a missing field: Lottie has
**Precomposition** — a reusable sub-composition, defined once as an asset and
placed by a layer with its own transform. FrameForge has no runtime equivalent.

It looks like it does. `defs.symbols` and `defs.components` exist, and `use`
objects reference them. But `use` is *grammar sugar*: `sdk.expand()` resolves it
before the contract sees a document, and `Document.model_validate` rejects any
document still carrying one. A badge repeated two hundred times is two hundred
objects in the validated file.

This has been true since the beginning and was never written down, so it reads
as an oversight. It is not.

## Decision

**Instancing stays a pre-lowering authoring construct. A validated FrameForge
document contains no unresolved references to reusable definitions.**

The definition *side* is typed — `SymbolDef` gives `defs.symbols` a declared
shape — but placing an instance is the SDK's job, and the core profile has no
instance object.

## Why

A document format and an animation format want opposite things here.

- **Determinism.** A flat document renders the same regardless of the order
  definitions are resolved in, and cannot express a cycle. With instancing,
  `symbol A` containing `use B` containing `use A` is a well-formed file that
  never finishes rendering, and every consumer needs its own cycle detector.
- **Diffability.** The document is a review artifact. `git diff` on a flat
  document shows what moved; on an instanced one it shows a definition changed
  and leaves the reader to work out which two hundred places that touched.
- **One consumer, not five.** The renderer, the validator, the MCP tools, the
  vision reconstructor and any third-party client would each need identical
  expansion logic, and any divergence between them is a rendering difference
  nobody can attribute.
- **The boundary already exists.** `use` and `component` are on the same footing
  as every other piece of grammar sugar, and `test_grammar_sugar_is_rejected_on_purpose`
  has asserted it from the other side since the package was extracted. Adding an
  instance object would reverse that decision, not extend it.

Lottie chooses the opposite because a precomp is also a *time* container — it has
its own timeline that a layer can remap and stretch. There is no analogue in a
static document, so the thing instancing buys Lottie is not on offer here.

## Consequences

- Documents are larger. A 200-instance badge costs 200 objects. Accepted: they
  compress well, and nothing in the pipeline is size-bound.
- Editing a symbol after expansion does not update its uses. The SDK re-expands
  from source; the validated document is an artifact, not a source file. This is
  the same relationship as compiled output to code, and the same discipline
  applies — edit the source, re-emit.
- A tool that wants to *recover* instancing (dedupe repeated subtrees back into
  symbols) can, but it is inferring structure that the document deliberately
  discarded, and it must not assume its inference round-trips.

## Alternatives rejected

**Add an `instance` object to the core profile.** Reverses the grammar-sugar
boundary, requires cycle detection in every consumer, and makes the rendering of
a document depend on resolution order.

**Type `defs.symbols` strictly and reject anything else.** Would narrow an
`Optional[dict]` that documents rely on today, breaking the declared
`COMPATIBILITY = "backward"` guarantee. `SymbolDef` is therefore offered
(`dict[str, Union[SymbolDef, dict]]`), not imposed.

**Leave `defs.symbols` untyped.** Rejected: the definition side has no
determinism argument behind it. It was untyped by omission, and a consumer
reading a symbol had to guess. Typing it costs nothing and breaks nothing.
