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
| `DEPRECATIONS` | Every deprecated form, as data. Also in the schema as `x-frameforge-deprecations`. |
| `scan_document()` / `migrate_document()` | Find deprecated forms; rewrite them to the canonical spelling. |
| `ff-schema` | CLI: regenerate, verify staleness, or validate a document. |
| `ff-codemod` | CLI: report or migrate deprecated forms. |

The schema is never hand-authored — it is emitted from `Document`, and
`ff-schema --check` fails if the committed file has drifted. Models and schema
are one artifact in two forms.

```bash
ff-schema                      # regenerate the committed schema
ff-schema --check              # CI gate: fail if stale
ff-schema --print              # write it to stdout
ff-schema doc.fg.yaml          # validate a document against the models

ff-codemod doc.fg.yaml         # report deprecated forms; writes nothing
ff-codemod --write doc.fg.yaml # migrate in place
ff-codemod --list              # the deprecation registry, with reasons
```

YAML input needs a parser: `pip install "frameforge-api[yaml]"`. JSON always
works with no extra.

---

## Generative authoring requests

`GenerativeObject` records an unresolved request for image, text, or diagram
content. It is intentionally author-side intent: a generation tier consumes the
request once, verifies the output, lowers it to an ordinary FrameForge object,
and pins the resulting bytes. Renderers must not turn it into a live model call.

```python
from frameforge_api.model import GenerativeObject

request = GenerativeObject.model_validate({
    "type": "generative",
    "kind": "image",
    "prompt": "A cut-paper forest at blue hour",
    "model": "image-model-v1",
    "params": {
        "seed": 42,
        "size": [1024, 1024],
        "style": "layered editorial illustration",
    },
    "box": [0, 0, 1024, 1024],
    "alt": "Layered paper trees beneath a deep-blue evening sky.",
})
```

`prompt` and `model` must be nonblank. Image and diagram requests also require
nonblank `alt` or `actual_text`. Set `regenerate: true` only when the generation
tier should bypass its `(prompt, model, params)` cache and request a new result.

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

## Print, bound work, and CJKV — 2.9.0

The contract shipped `bleed` and twelve `book-*` trim sizes from the start, and
could not say what ink prints or which margin faces the spine. 2.9.0 closes
that, plus the two other places where the model advertised an intent it could
not express. Everything here is optional; nothing existing changed.

### Colour is a string **or** an ink

```python
from frameforge_api.model import CmykColor, SpotColor

{"fill": "#d4145a"}                                            # unchanged
{"fill": {"space": "cmyk", "c": 0, "m": 0.9, "y": 0.8, "k": 0}}
{"fill": {"space": "spot", "name": "PANTONE 283 C", "system": "pantone",
          "tint": 0.4,
          "alternate": {"space": "cmyk", "c": .31, "m": .09, "y": 0, "k": 0}}}
{"fill": {"space": "icc", "profile": "fogra39", "components": [.1, .8, .7, 0]}}
```

`Paint` picks the union up automatically, so an ink works anywhere a colour does
— fills, strokes, gradient stops, page backgrounds, `tokens.colors`. ICC values
name a profile declared once under `defs.color_profiles`, pinned by `hash` the
way a font is. Whether ink prints through or knocks out is
`style.overprint` (`none` | `fill` | `stroke` | `both`) with `overprint_mode`
for PDF's OPM.

### Margins that know where the spine is

```yaml
canvas:
  preset: book-6x9
  bleed: 3mm
  margin: {top: 18mm, bottom: 22mm, inside: 20mm, outside: 14mm, gutter: 5mm}
```

`[top, right, bottom, left]` still works and describes a *sheet*. A bound book is
spine-relative, because `inside` and `outside` swap sides on every leaf. Mixing
the two vocabularies is an error rather than a silent choice. Masters carry
`side: recto|verso|any` so the pair can mirror; a page may state its own `side`;
a canvas may be a two-page `spread`.

### Ruby and warichu

```json
{"kind": "ruby", "base": "漢字", "text": "かんじ", "position": "over"}
{"kind": "ruby", "base": "仮名", "text": ["か", "な"]}
{"kind": "warichu", "content": ["割注"], "lines": 2, "brackets": "parenthesis"}
```

A string annotation is group ruby, a list is mono ruby — the renderer cannot
infer which was meant, so the shape says it.

### Targets say what they produce

```json
{"name": "press",
 "output": {"format": "pdf", "output_intent": "press", "color_space": "cmyk",
            "color_profile": "fogra39", "font_embedding": "subset",
            "crop_marks": true, "bleed_marks": true, "registration_marks": true}}
{"name": "web", "output": {"format": "png", "dpi": 144}}
```

`canvas` is now optional on a target: exporting one layout several ways no longer
means restating it and watching the copies drift.

A worked document using all four is [`examples/press-ready-book.json`](examples/press-ready-book.json),
validated on every test run.

> **The contract declares; the engine renders.** A press PDF with real
> separations needs a renderer that implements them. This package's job is that
> the document can *say* it, travel with it, and be checked — see
> [MIGRATION.md](MIGRATION.md) for what each consumer needs to do.

---

## Typographic rhythm — 2.10.0

`Layout(kind="grid")` places boxes. It never said what those boxes should be
**divisible by**, and that is the number a page is actually built on.

### A baseline grid

```json
{"defs": {
  "baseline_grid": {"increment": "13pt", "relative_to": "top_margin"},
  "tokens": {"styles": {
    "body":    {"font_size": "10pt", "line_height": "13pt", "align_to_baseline": true},
    "caption": {"font_size": "8pt",  "line_height": "13pt", "align_to_baseline": false}
  }}
}}
```

The increment **is** the body leading. Set 10pt type on 13pt leading against a
13pt grid and type lines up across the gutter between columns, across the fold
of a spread, and across facing pages. Get it wrong — a module height that is not
a multiple of the increment — and every row leaves a remainder at its foot, so
gutters authored identically render unevenly.

That is exactly what 2.9.0's `column_fill: "balance"` and `spread` had no way to
ask for: balanced columns whose baselines do not align are still ragged.

Scopes, in resolution order: `rendering.baseline_grid` on a fixed page, else
`defs.baseline_grid`. A flowed section has no rendering contract, so a book
states its rhythm once in `defs` — which is the intended scope anyway.

The grid is **inert until a block opts in**, and `align_to_baseline: false` is a
real opt-out for captions set smaller than the grid. `increment` must be
positive.

### A declared measure

```json
{"text_contract": {"measure": [60, 72]}}
```

`[min, max]` characters — the column width the type is meant to be read at.
Leading fixes the vertical increment; measure fixes the horizontal one. Advisory
(only a laid-out line can be counted), but the two ways of writing it that are
certainly wrong — inverted and non-positive — fail here.

### A cap on total ink

```json
{"defs": {"color_profiles": {"fogra39": {
  "space": "cmyk", "total_ink_limit": 3.0
}}}}
```

2.9.0 bounded each CMYK separation independently, which left `c=m=y=k=1.0` —
400% coverage — legal and unprintable. The scale is the sum of the four `0..1`
components, so `3.0` is the familiar "300%"; the percentage spelling `300` is
rejected rather than read as 40000%. The engine's validator enforces it against
*resolved* paint, which is the only place a gradient or a spot `alternate` has a
coverage at all.

A worked document is [`examples/baseline-grid-book.json`](examples/baseline-grid-book.json),
validated on every test run.

> **No renderer aligns to this grid yet.** The format has to be able to state a
> rhythm before an engine can implement one, so `align_to_baseline: true` is a
> declaration of intent today, not a rendering guarantee. See
> [MIGRATION.md](MIGRATION.md#sdks-and-mcp-servers) for the per-consumer status.

---

## Matte, star, winding — parity with the closest published peer

[Lottie 1.0](https://lottie.github.io/lottie-spec/1.0/specs/schema/) is the
nearest thing to a published peer for the *graphics* half of this model. Reading
the contract against it surfaced four things it could not say. All are optional.

### One object as another's matte

```jsonc
{"type": "image", "id": "photo", "box": [0, 0, 600, 420], "src": "cover.jpg"},
{"type": "text",  "box": [40, 120, 520, 180], "text": "HARBOUR",
 "matte": {"source": "photo", "mode": "alpha"}}
```

`style.mask` masks by an image and `style.clip_path` clips by a path; neither
could use an **object** as the matte. `mode` is `alpha` or `luma`, and `invert`
flips it. An object naming itself is rejected; whether a source that is not self
resolves is whole-document referential integrity and belongs to the engine.

### A star that stays a star

```jsonc
{"type": "star", "center": [520, 720], "points": 5,
 "outer_radius": 48, "inner_radius": 20, "outer_roundness": 0.15}
{"type": "star", "star_type": "polygon", "center": [80, 720],
 "points": 6, "outer_radius": 36}
```

`polygon` took an explicit vertex list, so a five-point star was ten computed
points with the parameters thrown away — nothing downstream could restyle it as
a seven-point one. A star requires `inner_radius`; a polygon forbids it, rather
than quietly ignoring it. Orientation is the inherited `rotation`.

### Winding direction

`direction` (`clockwise` | `counter-clockwise`) on `path`, `polyline`, `polygon`
and `star`. With `fill_rule` it decides which enclosed regions are holes.

### A label distinct from the address

`name` is for humans and tooling; `id` remains the stable address that
cross-references and mattes point at, so renaming cannot break a link.

Worked document: [`examples/matte-and-star.json`](examples/matte-and-star.json).

### What is deliberately *not* here

Lottie's **Precomposition** — instancing a reusable definition at render time —
has no equivalent, on purpose. `use` stays pre-lowering grammar that
`sdk.expand()` resolves before validation, so a validated document is flat,
diffable and free of resolution order. The reasoning is
[ADR 0001](docs/adr/0001-flat-document-model.md). What *is* new is that the
definition side is typed: `SymbolDef` gives `defs.symbols` a declared shape
without narrowing it.

Everything time-shaped in Lottie — keyframes, easing, markers, time remapping —
is correctly absent from a static document contract and should stay that way.

---

## Deprecation — 2.11.0

Deprecation used to be a comment. It is a contract now: findable by a machine,
fixable by a command.

### `ff-codemod`

```bash
ff-codemod doc.fg.yaml          # report; writes nothing; exit 1 if anything found
ff-codemod --write doc.fg.yaml  # rewrite in place
ff-codemod --json doc.json      # findings as JSON, for CI
ff-codemod --list               # the registry, with reasons
```

```python
from frameforge_api import scan_document, migrate_document

for finding in scan_document(doc):        # read-only; never mutates
    print(finding.path, finding.id, finding.severity)

result = migrate_document(doc)            # returns a NEW document
result.document, result.changed, result.manual
```

Non-mutating and idempotent — every rewrite removes the form it matched, so a
second pass finds nothing. That is what makes it safe in a pre-commit hook.

> Three model docstrings and the P3 stroke error message used to say *"run
> `tooling/codemod.py`"*. That file is in the `frameforge` monorepo, so for
> anyone who installed this package alone the one actionable line named a path
> they did not have — and those strings are copied verbatim into the JSON
> Schema, which is what editors and codegen actually read. A test now fails if
> any published description names a file the wheel does not ship.

### The registry

```python
frameforge_api.DEPRECATIONS               # eleven entries, as data
```

```jsonc
// in the schema:
"$defs": {"Circle": {"deprecated": true, …}},
"x-frameforge-deprecations": [
  {"id": "gradient-stop-offset", "kind": "legacy-key",
   "subject": "GradientStop.offset", "replacement": "GradientStop.position",
   "fix": "automatic", "valid_at_head": true, "severity": "info", …}
]
```

Both halves are needed, because the standard keyword cannot carry all of it:

- **`Circle`, `Polygon`, `Curve`, `Tokens.text_styles`** take the standard JSON
  Schema 2020-12 `deprecated: true`.
- **The legacy *keys* cannot.** `offset`, `object`, `type`, `c1`/`c2` and `dash`
  are normalised by `mode="before"` validators, so they are accepted by the
  models and never appear in the schema as properties — a consumer reading the
  schema alone could not learn those spellings are even *legal*, let alone
  discouraged. `x-frameforge-deprecations` is where they are published.

`valid_at_head` is the field to branch on: nine forms still parse, two
(`stroke-single-form`, `size-renamed`) are rejected. The full table is in
[MIGRATION.md](MIGRATION.md#deprecation--2110), and
[`examples/legacy-shortcuts.before.json`](examples/legacy-shortcuts.before.json)
carries all eleven with its migrated twin beside it.

### `tokens.text_styles` is the one that can render wrong

```jsonc
"tokens": {
  "text_styles": {"body": {"font_size": "10pt"}},   // resolved FIRST — this wins
  "styles":      {"body": {"font_size": "24pt"}}    // dead
}
```

Every other legacy spelling collapses at parse time. This one does not: both
maps stay live, `text_styles` resolves first, and a name in both silently
renders as the one you probably did not mean. `ff-codemod` merges them —
`text_styles` winning, which is what the renderer already does, so the merge is
appearance-preserving — and names every shadowed key.

It is a **lint, not a validation error**, and that is forced: `COMPATIBILITY` is
`backward`, a collision was always valid, so rejecting it now would break the
guarantee below. For the same reason none of the eleven forms can be *removed*
before 3.0. Deprecated here means discouraged, migratable, and still accepted.

---

## Compatibility — what a version bump promises a document

```python
frameforge_api.COMPATIBILITY      # 'backward'
```

SemVer says what the numbers mean. It does not answer the only question a
consumer has, which is whether the file they wrote last year still parses. This
does, in the schema-registry sense:

**BACKWARD — a document valid under any earlier 2.x revision stays valid at HEAD.**

| within the 2.x line, a change **may** | and **may not** |
|---|---|
| add an optional field | add a required field |
| add a union member | remove or rename a field |
| widen a type, relax a constraint | remove a union member |
| make a required field optional | narrow a type, tighten a constraint |
| | change a default, or what a value means |

The reverse (a 2.9.0 document read by a 2.7 validator) is **not** promised: a
reader that predates spot ink cannot interpret it. Branch on `HEAD_VERSION` when
you need to know what a document may contain.

The 2.x line held this property from 2.0.0 without stating it.
`tests/test_backward_compat.py` is what turns it into a guarantee — it replays a
committed corpus of older documents plus the whole monorepo fixture corpus, by
declared revision, on every run.

> ⚠️ **Compare revisions as numbers, not as strings.** `"2.2.0" < "2.10.0"` is
> `False` under lexicographic ordering — `'2'` sorts after `'1'`. 2.10.0 is the
> first two-digit minor in this line, so any consumer gating on
> `document.version < HEAD_VERSION` as text inverts at this release. Parse to
> `(major, minor, patch)` and compare tuples.

---

## Versioning — two clocks, on purpose

| | what it is | moves when |
|---|---|---|
| `__version__` — **1.2.0** | this wheel's release line | the package changes: packaging, a new helper, a CLI flag |
| `HEAD_VERSION` / `CONTRACT_VERSION` — **2.11.0** | the FrameForge **document format** revision | the *contract* changes: a new field, a retyped one |

They are deliberately **not** the same number, and a test asserts they stay
apart. Welding them together means a packaging bug fix has to claim the document
format changed, and a format change has to major-bump a package whose API never
moved — one of the two release cycles becomes unshippable.

```python
import frameforge_api
frameforge_api.__version__        # '1.2.0'  → pin the dependency: frameforge-api>=1.2
frameforge_api.HEAD_VERSION       # '2.11.0' → branch on this for document compatibility
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

- [Runtime font-closure boundary](docs/runtime-font-closure-boundary.md) — why
  documents pin font identity while SDK/render/MCP calls select the `.fp`
- [`frameforge`](https://github.com/pedroanisio/frameforge) — the engine, SDK and MCP server
- [`frameforge-fonts`](https://github.com/pedroanisio/frameforge-fonts) — font discovery, shaping and portable closure

## License

MIT.
