# frameforge-api — CHANGELOG

*Two version clocks, deliberately independent: these headings are the **package**
release line (`__version__`), while `HEAD_VERSION` is the FrameForge **document
format** revision the package carries. A packaging release must not look like a
format change, so they are never welded together.*

## 1.3.0 — the docs are gated now (2026-08-01)

*Carries FrameForge document contract `HEAD_VERSION = 2.11.0` — unchanged. This
is packaging, docs and gates only; the contract did not move, which is the two
clocks doing exactly what they exist for: a package minor that a downstream
validator must not read as a format change.*

### The docs are gated now (`tooling`, `tests`)

A documentation audit found that the accuracy of this repository's prose was
entirely a matter of whoever last edited it. The product docs happened to be
right; the agent operating guide was wrong in every path it named.

- **`tooling/docgates.py` + `make doc-check`** — eight gates, each written
  against drift that had actually occurred, not against drift that seemed
  plausible: CLAUDE.md path references, rule-5 disclaimer frontmatter,
  `HEAD_VERSION` literals, the package version, CHANGELOG sectioning, CLI flag
  coverage, counts quoted in prose, and relative-link integrity.
  `tests/test_doc_gates.py` asserts on each one separately, so `pytest` names
  the kind of drift rather than reporting one opaque failure.

  They **verify** prose rather than **generating** it. Injecting `--help` output
  or a rendered tree would have traded accurate prose for accurate-but-worse
  prose; a gate buys the same protection and costs the reader nothing.

- **`CLAUDE.md` rewritten.** It was a near-verbatim copy of the monorepo's
  (`diff` = 2 lines) and all fifteen filesystem paths it named were absent here
  — it pointed agents at `src/frameforge/model.py`, `tooling/check_disclaimers.py`,
  `AGENTS.md`, `FIXTURE-STATUS.md` and `mkdocs.yml`, none of which exist in this
  tree. The behavioural half (PALS's LAW, the eight ranked constraints, TDD,
  English-default) was correct and is preserved verbatim; the structural half
  now describes this repository and `claude_path_problems()` fails the build if
  that stops being true.

- **`ff-schema.parser()` and `ff-codemod.parser()`** are built separately from
  `main()`, so a gate can enumerate the flags without executing anything.

### Fixed

- **The fidelity gate was silently not running.** `tests/test_extraction_fidelity.py`
  skipped when the sibling monorepo's contract revision differed from
  `HEAD_VERSION`, which is correct when the sibling merely happens to be on disk
  — but it also skipped when `FRAMEFORGE_REPO` had been set explicitly, which is
  a request for the gate. The suite reported green while covering nothing.
  Divergence is now a **failure** when the checkout was named, and a skip that
  says so otherwise.
- **Two source files documented the wrong contract version.** `pyproject.toml`
  and `frameforge_api/__init__.py` both described `HEAD_VERSION` as `2.8.x` when
  it was `2.11.0` — three revisions stale. Comments, so no schema gate or test
  saw them; `version_literal_problems()` does now.
- **`ff-schema --out` and `ff-codemod --stdout` shipped undocumented.** Both are
  in `README.md`, and `test_every_cli_flag_is_documented` keeps it that way.
- **README described the fidelity suite as having two outcomes**; it has three,
  and the third (sibling present, contract diverged) was the live one.
- **`docs/adr/0001-flat-document-model.md` and
  `docs/runtime-font-closure-boundary.md` carried no disclaimer frontmatter.**
  Rule 5 had been policy with no enforcement in this repository, because the
  script it named lives in the monorepo.
- **`1.2.0`'s entries were still under `## Unreleased`**, with no tag. Sectioned
  and tagged `v1.2.0` at the commit that bumped it. There is deliberately no
  `v1.1.0`: `pyproject.toml` went `1.0.0` → `1.2.0` in one commit, so no commit
  ever declared that version, though a `1.1.0` wheel was built from it.

### Added

- **`.github/workflows/ci.yml`** — the repository had no CI at all, so every
  gate it documented ran only on a developer's laptop. Runs `schema-check`,
  `doc-check`, `lint` and the suite on Python 3.10 and 3.13, then builds and
  asserts the generated schema is actually inside the wheel. `FRAMEFORGE_REPO`
  is deliberately never set: the package must build and test standalone.
- `make doc-check`; `make lint` now covers `tooling/` too.

## 1.2.0 — deprecation, made actionable (2026-08-01)

*Carries FrameForge document contract `HEAD_VERSION = 2.11.0`.*

### Deprecation, made actionable — contract `2.11.0` (`deprecations`, `schema`)

The contract always *had* deprecations. It had no way for anyone to act on them,
and three separate defects were in the way.

- **The migration path did not ship.** Three model docstrings and the P3 stroke
  error message told the reader to run `tooling/codemod.py` — a script in the
  `frameforge` monorepo, not in this wheel. Anyone who installed the contract on
  its own was pointed at a path they do not have, and those strings are copied
  verbatim into the generated JSON Schema, so the dangling pointer was
  *published*, not internal.

  **`frameforge_api.deprecations`** is that script as an ordinary importable
  module with a console script over it — the same move `frameforge_api.schema`
  made for the monorepo's un-importable `build_schema.py`.
  `scan_document()` reports, `migrate_document()` rewrites, `ff-codemod` is the
  CLI (`--write`, `--stdout`, `--json`, `--list`). Both functions are
  non-mutating, and `migrate` is idempotent by construction, so it is safe in a
  pre-commit hook or a CI gate.
  `test_no_published_description_points_at_a_file_the_package_does_not_ship`
  keeps the references honest.

- **Deprecation was invisible to machines.** The status lived only in English
  `description` prose: the count of the standard JSON Schema `deprecated`
  keyword in the emitted schema was **zero**. Both halves are fixed, because one
  is not enough — `Circle`, `Polygon`, `Curve` and `Tokens.text_styles` now
  carry the standard 2020-12 `deprecated` annotation, and the deprecated *keys*
  (`offset`, `object`, `type`, `c1`/`c2`, `dash`) **cannot**: they are
  normalised by `mode="before"` validators, so they are accepted by the models
  and never appear in the schema as properties. A consumer reading the schema
  alone could not learn those spellings are even legal. They are published
  instead as **`x-frameforge-deprecations`**, mirroring
  `frameforge_api.DEPRECATIONS` — eleven entries carrying `id`, `kind`,
  `subject`, `replacement`, `fix`, `valid_at_head`, the engine validator's
  `code` for the same form, `severity` and a reason.

- **`tokens.text_styles` was a shadowing hazard, not a deprecation.** Every
  other legacy spelling collapses to one representation at parse time. This one
  cannot: `text_styles` and `styles` are both live `dict[str, Style]` maps and
  the renderer resolves `text_styles` first, so a name declared in both renders
  as that one and the `styles` definition is dead — silently. It is the only
  entry in the registry that can render a document *wrong* rather than merely
  verbose. The codemod merges the two with `text_styles` winning (what the
  renderer already does, so the merge is appearance-preserving) and reports
  every shadowed name.

  **Deliberately a lint, not a validation error.** `COMPATIBILITY` is
  `backward`, and a collision was always valid; rejecting it now would break the
  guarantee this package makes. The same rule is why none of the eleven forms
  can be *removed* before 3.0 — "deprecated" in the 2.x line means discouraged,
  mechanically migratable, and still accepted.

*Why the contract clock moved for what is only annotation:* nothing validates
differently, but the emitted schema bytes changed, and `$id`/`version` embed
`HEAD_VERSION`. Two different files claiming to be `2.10.0` is exactly the drift
this package exists to prevent.

#### Also

- Documented the portable font-closure boundary: `FontDef.src` plus `hash`
  continue to pin document font identity, while `.fp` closure selection remains
  runtime configuration on the SDK, renderer, and MCP. No `font_closure` or
  `font_generics` field was added to the serialized document contract.

- **`examples/legacy-shortcuts.before.json` / `.after.json`** — one worked
  document carrying all eleven deprecated forms, and what `ff-codemod --write`
  produces from it. A test asserts the pair has not drifted, and another asserts
  the "before" half still demonstrates *every* registry entry. The pair is held
  out of the reference-example sweep explicitly (the "before" half is
  deliberately invalid), rather than by a silent glob.
- **The pre-P3 oracle corpus is finally exercised.** `b1/` has been excluded
  from every suite here with the words "kept as codemod *input*", and nothing
  had ever run a codemod over it from this package, because there was none. All
  nine documents — 552 deprecated forms, 544 of them inline stroke bundles —
  now migrate to documents that validate at HEAD, idempotently.
- **The codemod is bound by the compatibility guarantee too.** A migration tool
  shipped beside a backward-compatibility promise is a way to break that promise
  at arm's length. `test_backward_compat.py` now also asserts the codemod never
  turns a valid document invalid, over the committed corpus and all 50+ lowered
  monorepo fixtures.
- **A correctness note for anyone porting the monorepo's codemod:** it maps a
  pre-P3 `stroke.opacity` onto `stroke_opacity`, and `Style` has no such field.
  `Style` is `extra="forbid"`, so that output does not validate. This
  implementation maps it to `Style.opacity`.
- **`tests/compat/v2.10.0-typographic-rhythm.json`** pins the revision
  immediately before this one, for the usual reason: the revision before a
  change is the one that change can most easily break.
- The `$defs` count moves 115 → 119.

## 1.1.0 — compatibility stated, typographic rhythm, print and bound work (2026-08-01)

*Carries FrameForge document contract `HEAD_VERSION = 2.10.0`; bundles contract
`2.9.0` and `2.10.0`.*

> **Never tagged.** This version was built locally (a `1.1.0` wheel exists under
> the gitignored `dist/`) but the bump reached git only as part of `1.2.0`:
> `pyproject.toml` went `1.0.0` → `1.2.0` in a single commit. The section is
> kept because the work is real and the contract revisions it carries are
> referenced elsewhere; there is deliberately no `v1.1.0` tag, because no commit
> ever declared that version.

Both clocks move: new importable models are a package minor, and a contract
widening is a contract minor. Neither is a major, because **every addition is
optional and every union is extended rather than replaced.**

### Compatibility, now stated rather than assumed

- **`frameforge_api.COMPATIBILITY = "backward"`.** The 2.x line had been
  strictly backward compatible since 2.0.0 and nothing said so, which made it an
  accident rather than a promise. It is now a declared guarantee in the
  schema-registry sense: *a document valid under any earlier 2.x revision stays
  valid at HEAD.* Within the line a change may add an optional field, add a union
  member, widen a type, relax a constraint, or make a required field optional —
  and may not add a required field, remove or rename one, drop a union member,
  narrow a type, tighten a constraint, or change what an existing value means.
  The reverse direction (FORWARD) is deliberately not promised.
- **`tests/test_backward_compat.py` enforces it**, against two corpora:
  `tests/compat/*.json` (committed documents pinned at 2.2.0, 2.4.0, 2.7.1 and
  2.9.0, so CI needs no sibling checkout) and the monorepo's 57 fixtures
  replayed by declared revision. All lowered fixtures from 2.0.0 onward validate
  at 2.10.0.
- **A 2.9.0 document is in the committed corpus**, because the revision
  immediately before a widening is the one that widening can most easily break —
  it carries typed ink, overprint, spine-relative margins, a spread and
  printer's marks.

### Typographic rhythm — contract `2.10.0` (`layout`, `page`, `document`, `style`)

- **`BaselineGrid`**, declared at **`defs.baseline_grid`** and overridable per
  page at **`RenderingContract.baseline_grid`**; blocks opt in with
  **`Style.align_to_baseline`**. Three fields: `increment` (required, positive —
  the pitch, and normally the body `line_height`), `start`, and `relative_to`
  (`page` | `top_margin`).

  *Why:* `Layout(kind="grid")` places boxes and said nothing about what they
  should be *divisible by*. If body text is 10pt on 13pt leading and a module's
  height is not a multiple of 13, every row leaves a remainder at its foot and
  the horizontal gutters stop looking equal — authored identically, rendered
  unevenly. The same increment is what aligns type across a gutter and across a
  fold, which is precisely what 2.9.0's `FlowRegion.column_fill: "balance"` and
  `CanvasObject.spread` had no way to ask for. `defs` is the only scope a
  `FlowSection` has, so that is where a book states its rhythm.

  It is inert until something opts in, and `align_to_baseline: false` is a
  meaningful opt-*out* for a caption set smaller than the grid.

- **`TextContract.measure`** — `[min, max]` intended line length in
  **characters**, at `text_contract` or per page. Leading fixes the vertical
  increment; measure fixes the horizontal one. Advisory and structurally inert:
  the engine's validator is the only thing that can measure a resolved line.
  Inverted (`[75, 45]`) and non-positive bounds are rejected here.

- **`ColorProfileDef.total_ink_limit`** — maximum total coverage, as the sum of
  a `CmykColor`'s four `0..1` components, so the scale runs `0..4` and `3.0` is
  the common "300%" sheet-fed limit.

  *Why:* 2.9.0 bounded each separation independently, which leaves
  `c=m=y=k=1.0` — 400% — structurally legal and physically unprintable. This
  package cannot enforce the cap (the coverage of a gradient, a spot
  `alternate` or an ICC conversion is known only once resolved); declaring it
  is what gives the engine's validator something to check against. The
  percentage spelling (`300`) is rejected rather than read as 40000%.

### Fixed

- **Revision ordering compared semver as strings.**
  `tests/test_backward_compat.py` gated its corpus with
  `declared < HEAD_VERSION` on raw strings, and `"2.2.0" < "2.10.0"` is
  **False** — `'2'` sorts after `'1'`. Latent while every minor was one digit;
  2.10.0 is the first that is not, and it turned the entire committed compat
  corpus red while every document in it was still perfectly valid. Now compared
  as parsed precedence tuples, with a regression test pinning the exact
  comparison that was wrong.

### Print colour (`base`, `style`, `document`)

- **`CmykColor`, `SpotColor`, `IccColor`**, discriminated on `space`, joined to
  `Color` — which stays `Union[str, ColorObject]` with the string branch first,
  so every existing document is unaffected. `Paint` picks them up automatically,
  so typed ink reaches fills, strokes, gradient stops, backgrounds and tokens
  without a second spelling.
- **`ColorProfileDef` and `defs.color_profiles`** — declared ICC profiles,
  pinned by `hash` the way `FontDef` pins a font, because a profile that changes
  silently reprints the job in different colour.
- **`Style.overprint` / `Style.overprint_mode`** — whether ink prints through or
  knocks out. CSS has no equivalent (on screen the topmost paint just wins), and
  getting it wrong is visible only on the printed sheet.

  *Why:* the contract already shipped `bleed` and twelve `book-*` trim presets.
  It could ask for a 6×9 trade book and could not say what ink prints.

### Book geometry (`page`)

- **`PageMargin`** with `inside` / `outside` / `gutter` beside `top` / `bottom` /
  `left` / `right`, and `MarginSpec = Union[Box, PageMargin]` on both
  `CanvasObject.margin` and `PageMaster.margin`. A bound book is described
  spine-relative because the two horizontal margins swap sides on every leaf.
  Mixing the two vocabularies is a validation error, not a silent pick — the
  wrong pick misplaces the text block on every other page.
- **`PageSide`**, `PageMaster.side` (`recto`/`verso`/`any`) and `Page.side`, so a
  recto master and a verso master can mirror.
- **`CanvasObject.spread`** — one sheet spanning a verso and a recto.

### CJKV annotation (`inline`)

- **`RubyInline`** (group ruby via a string, mono ruby via a list) and
  **`WarichuInline`**, both added to the `Inline` union.

  *Why:* `writing_mode`, `direction` and `unicode_bidi` have been declarable
  since 2.2.0, so vertical Japanese was expressible and then could not be
  annotated — the single most common thing done to it.

### Render targets (`document`)

- **`RenderOutput`** on `RenderTarget.output`: `format`, `dpi`, `scale`,
  `quality`, `background`, `color_space`, `color_profile`, `output_intent`,
  `font_embedding`, and printer's marks (`crop_marks`, `bleed_marks`,
  `registration_marks`, `color_bars`, `page_information`).
- **`RenderTarget.canvas` is now optional** — a required-to-optional widening,
  which is backward compatible. Exporting one layout several ways no longer
  means restating the canvas each time and watching the copies drift.

  *Why:* the family renders to SVG, HTML, PNG, PDF and LaTeX, and none of that
  was expressible in the document's own render contract. Every one of those was
  a flag on somebody's command line, so it did not travel with the document.

### Graphics primitives — parity with Lottie 1.0 (`objects`, `document`)

Read against [Lottie 1.0](https://lottie.github.io/lottie-spec/1.0/specs/schema/),
the closest published peer for the graphics half of the model. Four gaps closed,
one difference documented rather than closed.

- **`MatteSpec` and `ObjBase.matte`** — one object used as another's matte,
  `alpha` or `luma`, either invertible. `style.mask` masked by an image and
  `style.clip_path` clipped by a path; no object could matte another, so every
  knockout and gradient fade needed rasterising outside the document. An object
  naming itself is rejected; resolution of a non-self source is R12, the
  engine's.
- **`Star`** — a parametric star or regular polygon (`points`, `outer_radius`,
  `inner_radius`, `outer_roundness`, `inner_roundness`, `star_type`), joined to
  the `VisualObject` union beside the other primitives. `Polygon` took an
  explicit vertex list, so a five-point star was ten computed points with the
  parameters discarded. A star requires `inner_radius`; a polygon forbids it.
  Orientation is the inherited `rotation` rather than a duplicate field.
- **`ShapeDirection`** on `path`, `polyline`, `polygon` and `star` — winding
  order, which with `fill_rule` decides which enclosed regions are holes.
- **`ObjBase.name`** — a human label distinct from `id`, which stays the stable
  address cross-references and mattes point at.
- **`SymbolDef`** gives `defs.symbols` a declared shape. Typed as
  `dict[str, Union[SymbolDef, dict]]`, not narrowed to `SymbolDef`, because
  narrowing would reject documents that validate today.

**Not closed, and documented instead:** Lottie's Precomposition. Instancing
stays a pre-lowering authoring construct — `use` is resolved by `sdk.expand()`
before validation, so a validated document is flat. See
[ADR 0001](docs/adr/0001-flat-document-model.md) for why a document format and
an animation format want opposite things here, and
`examples/matte-and-star.json` for the primitives in use.

### Also

- `examples/press-ready-book.json` exercises all four areas in one document, and
  `tests/test_examples.py` validates every example on each run, so a snippet
  cannot rot into a confident wrong answer.
- The `$defs` count moves 105 → 115.

### Concurrently, from another change

- Added `GenerationParams` and the prompt-bearing `GenerativeObject` to the
  visual-object union. The new authoring object covers image, text, and diagram
  requests, requires reproducibility metadata (`model`, optional seed/size/style),
  enforces accessible text for visual outputs, and exposes explicit cache-bypass
  intent through `regenerate`. It remains an unresolved request: downstream
  generation must verify, lower, and pin the result before rendering.

## 1.0.0 — extracted from the frameforge monorepo (2026-07-31)

*Carries FrameForge document contract `HEAD_VERSION = 2.8.2`.*

First standalone release. The models are unchanged: this is a move, not a
rewrite, and the generated JSON Schema is semantically identical to the one the
monorepo committed at 2.8.2 (105 `$defs`, same `$id`, same `version`).

- **`frameforge_api.model`** — the authoritative Pydantic models, moved verbatim
  from `frameforge/src/frameforge/model.py`. Only the module docstring changed,
  to point at the new home. A test asserts the declarations are still identical
  to the monorepo's, line for line.
- **`frameforge_api.schema` is a library, not a script.** The monorepo's
  `docs/schema/build_schema.py` mutated `sys.path` to find the model and could
  not be imported, so consumers either re-implemented schema generation or
  shelled out. `build()`, `check()`, `load()` and `write()` are now ordinary
  functions; `ff-schema` is a thin CLI over them.
- **The schema ships inside the wheel** (`frameforge_api/schema/
  frameforge-v2.schema.json`), so a consumer that never runs Python still gets
  the contract.
- **One runtime dependency** (`pydantic>=2`). PyYAML is an extra, needed only by
  `ff-schema <doc.yaml>`. A test pins this: the contract must stay cheap to
  depend on.
- **The leaf property is gated.** `test_the_model_imports_nothing_from_frameforge`
  parses every source file in the contract and fails if any of them grows a
  FrameForge import — the property the whole split rests on.
- **`frameforge_api.model` is a package, not a 2,128-line module.** Split along
  the section boundaries the file already carried, into 18 modules ordered by
  dependency (`version`, `base`, `style`, `assets`, `layout`, `inline`,
  `humanize`, `objects/`, `flow`, `page`, `document`). Nothing was edited in the
  move.

  Every declared name stays importable from `frameforge_api.model`, so
  `from frameforge_api.model import Style` is unaffected; `__all__` is unchanged
  at `["Document", "HEAD_VERSION"]`. The generated JSON Schema is byte-identical,
  all 105 `$defs` in the same order. Under SemVer this is not an API change.

  Two forward references cross a module boundary, and they are resolved
  differently on purpose. `Group.children` refers to the `VisualObject` union, so
  `Group` is declared beside it in `model/objects/__init__.py` — placement
  removes the cycle. `FootnoteInline.content` refers to `Flowable`, and no
  placement removes that one (inline and block content are mutually recursive,
  and `flow` depends on `objects` which depends on `inline`), so `inline` defers
  the import and the package `__init__` publishes the name before rebuilding.
- **Four golden files (`tests/golden/`) freeze the interfaces**, taken before the
  split and compared on every run: the generated schema byte-for-byte, all 183
  declarations as normalised ASTs, the import surface plus each model's bases /
  config / field order / validators, and accept-reject verdicts for 36 probe
  documents covering the eleven `@model_validator`s a JSON Schema cannot express.
  Regenerate with `make goldens`, only when the contract is meant to move.
- **The contract is linted again, for correctness.** It was excluded from ruff
  outright; now only the style rules that would diverge it from upstream are off
  (`UP007`/`UP045`/`UP037`, `I001`, `RUF001`/`RUF003`/`RUF022`, `SIM102`). `F821`
  immediately caught a name the split had left unimported (`FigureFlow.object`).
- **The upstream fidelity test compares declarations, not lines.**
  `test_every_declaration_still_matches_the_monorepos` normalises both sides to
  ASTs keyed by name, so it is blind to file layout, declaration order and import
  wiring while still failing on any edit to a body, default, description or
  validator.
