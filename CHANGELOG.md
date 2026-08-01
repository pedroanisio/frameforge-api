# frameforge-api — CHANGELOG

*Two version clocks, deliberately independent: these headings are the **package**
release line (`__version__`), while `HEAD_VERSION` is the FrameForge **document
format** revision the package carries. A packaging release must not look like a
format change, so they are never welded together.*

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
