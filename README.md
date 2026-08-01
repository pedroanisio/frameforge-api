# frameforge-api

The **FrameForge v2 document contract**, standalone: the authoritative Pydantic
models and the JSON Schema generated from them.

Nothing here renders, lays out, or authors anything. This package answers one
question — *what is a FrameForge document?* — and answers it for everyone:
the authoring SDK, the render engine, the MCP server, an editor plugin, a CI
validator, a TypeScript client.

```bash
pip install frameforge-api
```

```python
from frameforge_api import Document, HEAD_VERSION

doc = Document.model_validate({
    "dsl": "FrameForge",
    "version": HEAD_VERSION,
    "title": "Hello",
    "pages": [{
        "mode": "page", "id": "p1",
        "canvas": {"size": [400, 200], "units": "px"},
        "layers": [{"id": "main", "objects": [
            {"type": "text", "box": [20, 20, 360, 40], "text": "Hello"},
        ]}],
    }],
})
```

---

## Why this is its own package

The models are a **leaf**: they import `re`, `typing` and `pydantic`, and
nothing else. Every other package in the family needs to agree on what a
document *is*, and none of them should have to depend on an engine to find out.

Before the split, learning the shape of a `Document` meant depending on a
24,000-line SDK and a 15,000-line renderer. Now it costs one wheel and one
runtime dependency. A test enforces the leaf property — if the contract ever
grows a FrameForge import, the build fails.

```
frameforge-api      the contract          ← imports nothing from the family
   ↑            ↑
frameforge-sdk   frameforge-render        ← both agree on the contract,
   ↑            ↑                            neither depends on the other
        consumers
```

---

## What you get

| | |
|---|---|
| `Document` | The root model. `Document.model_validate(data)` is the structural verdict. |
| `HEAD_VERSION` | The contract revision the models target. Range-pin against it rather than copying the string. |
| `build_schema()` | The same contract as JSON Schema, generated from the models. |
| `SCHEMA_PATH` | The generated schema, shipped **inside the wheel**. |
| `ff-schema` | CLI: regenerate, verify staleness, or validate a document. |

The schema is never hand-authored — it is emitted from `Document`, and
`ff-schema --check` fails if the committed file has drifted. Models and schema
are one artifact in two forms.

```bash
ff-schema                      # regenerate the committed schema
ff-schema --check              # CI gate: fail if stale
ff-schema --print              # write it to stdout
ff-schema doc.fg.yaml          # validate a document against the models
```

YAML input needs a parser: `pip install "frameforge-api[yaml]"`. JSON always
works with no extra.

---

## The closed-model guarantee

Every object sets `extra="forbid"`. A misspelled key is an **error**, not a
silently dropped field — which matters more than it sounds, because the failure
mode of a permissive schema is a document that validates and renders wrong.

```python
Document.model_validate({..., "colour": "#fff"})   # ValidationError, not a shrug
```

---

## What this package deliberately does NOT do

Structural validity is necessary, not sufficient. **A document that passes
`Document.model_validate` is well-formed, not well-made.**

The rules a JSON Schema cannot express — referential integrity, containment,
text fit, ink collisions, paint intent, legibility — need to measure a *render*,
so they live with the engine that can: the `frameforge` distribution's
validator. Ask this package whether a document is legal; ask the engine whether
it is any good.

Two boundaries worth knowing:

- **Grammar-level authoring sugar is not core.** `use` and simple `component`
  objects are SDK conveniences that `sdk.expand()` lowers into real groups
  *before* the core model sees them. This package rejects them on purpose — a
  document carrying them is pre-lowering source, not a finished document.
- **Out-of-profile types are the engine's business.** The UML zoo, charts and
  ontology blocks are outside the §8.5 core conformance profile; the engine's
  validator reports them as warnings rather than modelling them here.

---

## Versioning — two clocks, on purpose

| | what it is | moves when |
|---|---|---|
| `__version__` — **1.0.0** | this wheel's release line | the package changes: packaging, a new helper, a CLI flag |
| `HEAD_VERSION` / `CONTRACT_VERSION` — **2.8.2** | the FrameForge **document format** revision | the *contract* changes: a new field, a retyped one |

They are deliberately **not** the same number, and a test asserts they stay
apart. Welding them together means a packaging bug fix has to claim the document
format changed, and a format change has to major-bump a package whose API never
moved — one of the two release cycles becomes unshippable.

```python
import frameforge_api
frameforge_api.__version__        # '1.0.0'  → pin the dependency: frameforge-api>=1.0
frameforge_api.HEAD_VERSION       # '2.8.2'  → branch on this for document compatibility
```

Semantic versioning applies to each independently. For the contract, a new
optional field is a minor bump and a removed or retyped field is a major one;
the JSON Schema's `$id` and `version` carry the **contract** version, never the
package version, so a packaging release never looks like a format change to a
downstream validator.

---

## Development

```bash
uv sync --all-groups
uv run pytest                 # contract + extraction-fidelity suites
uv run ff-schema --check      # the drift gate
```

The fidelity suite validates the real FrameForge fixture corpus against these
models when a sibling checkout is present (set `FRAMEFORGE_REPO` to point at
one); it skips cleanly when it is absent, because the package must build and
test standalone.

## Related

- [`frameforge`](https://github.com/pedroanisio/frameforge) — the engine, SDK and MCP server
- [`frameforge-fonts`](https://github.com/pedroanisio/frameforge-fonts) — font discovery, shaping and portable closure

## License

MIT.
