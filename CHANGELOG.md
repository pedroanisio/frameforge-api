# frameforge-api — CHANGELOG

*The distribution version tracks the contract version (`HEAD_VERSION`): this
package **is** the contract, so the two never differ.*

## 2.8.2 — extracted from the frameforge monorepo (2026-07-31)

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
  parses the module AST and fails if the contract ever grows a FrameForge
  import — the property the whole split rests on.
