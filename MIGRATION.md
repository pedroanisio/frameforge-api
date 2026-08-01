# Migration — 2.8.2 → 2.11.0

**Nothing to do.** This is a backward-compatible widening: every addition is
optional and every union was extended rather than replaced. A document that
validated at 2.8.2 validates at 2.11.0 unchanged, and `tests/test_backward_compat.py`
replays a committed corpus plus all lowered monorepo fixtures on every run to
keep that true.

Three contract revisions ship in this package line: **2.9.0** (print colour,
bound geometry, CJKV annotation, render targets), **2.10.0** (the typographic
rhythm layer and the total-ink cap), and **2.11.0** (deprecation, made
machine-readable). None is breaking, so there is one migration path and it is
the empty one.

The rest of this file is for people who want the new capability, and for the
consumers downstream of the contract who now have work to do.

---

## Deprecation — 2.11.0

Nothing became invalid. What changed is that a deprecated form can now be
**found and fixed** instead of only being complained about in a docstring.

### `ff-codemod`, the tool the errors were already pointing at

```bash
pip install --upgrade "frameforge-api>=1.2"

ff-codemod doc.fg.yaml          # report; writes nothing; exit 1 if anything found
ff-codemod --write doc.fg.yaml  # rewrite in place
ff-codemod --stdout doc.json    # print the migrated document
ff-codemod --json doc.json      # findings as JSON, for CI
ff-codemod --list               # the whole registry, with reasons
```

```python
from frameforge_api import migrate_document, scan_document, DEPRECATIONS

for finding in scan_document(doc):            # read-only, never mutates
    print(finding.path, finding.id, finding.severity)

result = migrate_document(doc)                # returns a NEW document
result.document                               # migrated
result.changed                                # did anything get rewritten?
result.manual                                 # what the codemod refused to guess at
```

Three model docstrings and the P3 stroke error message used to say *"run
`tooling/codemod.py`"*. That file lives in the `frameforge` monorepo, so for
anyone who installed this package on its own the only actionable line in the
message named a path they did not have. Those strings are copied verbatim into
the JSON Schema, which is what an editor, a codegen pass and a model actually
read — so the dangling pointer was published, not internal. They now name
`ff-codemod`, which is a console script of this distribution, and a test fails
if any published description names a file the wheel does not ship.

`migrate_document` never mutates its input and is idempotent: every rewrite
removes the form it matched, so a second pass reports nothing. That is what
makes it safe in a pre-commit hook or a CI gate.

### The registry

Deprecation used to live only inside English `description` prose. A tool reading
the JSON Schema had nothing to key on — the count of the standard `deprecated`
keyword in the emitted schema was zero. Both halves are fixed, because one is
not enough:

- **`Circle`, `Polygon`, `Curve` and `Tokens.text_styles`** carry the standard
  JSON Schema 2020-12 **`deprecated: true`** annotation.
- **The legacy *keys* cannot.** `offset`, `object`, `type`, `c1`/`c2` and `dash`
  are normalised by `mode="before"` validators, so they are accepted by the
  models and never appear in the schema as properties — there is nothing for the
  keyword to attach to, and a consumer reading the schema alone could not even
  learn those spellings are *legal*. They are published instead as
  **`x-frameforge-deprecations`**, a top-level array in the schema mirroring
  `frameforge_api.DEPRECATIONS`.

Each entry carries `id`, `kind`, `subject`, `replacement`, `fix`,
`valid_at_head`, the engine validator's `code` for the same form, `severity`,
and a `note` saying why. **`valid_at_head` is the field to branch on:** a
`legacy-key` still parses, a `removed-form` does not.

| id | form | becomes | valid at HEAD |
|---|---|---|---|
| `deprecated-alias-circle` | `type: circle` | `ellipse`, `rx == ry` | yes |
| `deprecated-alias-polygon` | `type: polygon` | `polyline`, `closed: true` | yes |
| `deprecated-alias-curve` | `type: curve` / `bezier` | `path`, one cubic segment | yes |
| `curve-control-shorthand` | `c1` / `c2` | `control1` / `control2` | yes |
| `gradient-stop-offset` | `GradientStop.offset` | `position` (`0.5` → `"50%"`) | yes |
| `connector-endpoint-object` | endpoint `object` | `ref` | yes |
| `connector-route-type` | `route.type` | `route.kind` | yes |
| `style-dash-shorthand` | `Style.dash` | `stroke_dasharray` | yes |
| `tokens-text-styles` | `tokens.text_styles` | `tokens.styles` | yes |
| `stroke-single-form` | inline `stroke: {color, width, …}` | `stroke` + `stroke_style` | **no** |
| `size-renamed` | object `size: {…}` | `sizing` | **no** |

Worked example: [`examples/legacy-shortcuts.before.json`](examples/legacy-shortcuts.before.json)
carries all eleven, and [`examples/legacy-shortcuts.after.json`](examples/legacy-shortcuts.after.json)
is what `ff-codemod --write` produces. A test asserts the pair has not drifted.

### `tokens.text_styles` was a shadowing hazard, not a deprecation

Worth calling out separately, because it is the only entry that can render a
document **wrong** rather than merely verbose.

Every other legacy form collapses to one representation at parse time.
`text_styles` does not: it and `styles` are both live `dict[str, Style]` maps,
and the renderer resolves `text_styles` **first**. A name declared in both
therefore renders as the `text_styles` one and the `styles` definition is dead —
and nothing in the contract said so.

```jsonc
"tokens": {
  "text_styles": {"body": {"font_size": "10pt"}},   // this one wins
  "styles":      {"body": {"font_size": "24pt"}}    // dead
}
```

`ff-codemod` merges the two with `text_styles` winning — which is what the
renderer already does, so the merge is appearance-preserving — and reports every
shadowed name.

**It is a lint, not a validation error, and deliberately so.**
`frameforge_api.COMPATIBILITY` is `backward`: a document valid under an earlier
2.x revision stays valid at HEAD. A collision was always valid, so rejecting it
now would break the guarantee this package makes. That is also why none of the
eleven forms above can be *removed* before 3.0.

### What the codemod refuses to do

Two cases come back in `result.manual` instead of being guessed at:

- **A pre-P3 stroke bundle beside a *named* `stroke_style`.** The string names a
  shared token; rewriting it would restyle every other object that references it.
- **`dash` contradicting an explicit `stroke_dasharray`.** The models reject the
  pair. Picking one would make the output validate while drawing a dash neither
  spelling asked for.

`--write` still exits `1` when anything is left in `manual`, so a CI gate does
not go green on a half-done migration.

> One correctness note for anyone porting the monorepo's `tooling/codemod.py`:
> it maps a pre-P3 `stroke.opacity` onto `stroke_opacity`, and `Style` has no
> such field. `Style` is `extra="forbid"`, so that output does not validate.
> This implementation maps it to `Style.opacity`, and
> `test_migrating_any_deprecated_form_yields_a_document_that_validates` is what
> would have caught it.

---

## Upgrading

```bash
pip install --upgrade "frameforge-api>=1.3"
```

Two clocks moved. The package is **1.3.1** (new importable models, then the doc
and codemod gates); the contract is **2.11.0** (new optional fields, then
machine-readable deprecation). Neither is a major.

You do **not** need to bump the `version:` line in your documents. It states the
revision the document was authored against, and 2.11.0 reads all of them. Bump it
only when you start using something 2.9.0, 2.10.0 or 2.11.0 added — at which
point older validators will correctly refuse the file, which is the point of the
field.

> **If you compare revision strings anywhere, stop.** `"2.2.0" < "2.10.0"` is
> `False` in every language that compares strings lexicographically — `'2'`
> sorts after `'1'`. 2.10.0 is the first two-digit minor in the 2.x line, so any
> code gating on `document.version < HEAD` silently inverts at this release.
> Compare parsed `(major, minor, patch)` tuples. This bit us: it turned the
> whole compat corpus red while every document in it was still valid.

---

## If you author documents

Seven things became expressible. Each is opt-in.

### Ink instead of a colour string

Nothing changes for `"#d4145a"`. To specify what actually prints:

```jsonc
{"space": "cmyk", "c": 0, "m": 0.9, "y": 0.8, "k": 0}   // process; components are 0..1, not 0..100
{"space": "spot", "name": "PANTONE 283 C", "system": "pantone", "tint": 0.4,
 "alternate": {"space": "cmyk", "c": 0.31, "m": 0.09, "y": 0, "k": 0}}
{"space": "icc",  "profile": "fogra39", "components": [0.1, 0.8, 0.7, 0.0]}
```

An ink works anywhere a colour does, including `tokens.colors` — define it once
there and keep referring to it by name.

`icc` values need the profile declared:

```jsonc
"defs": {"color_profiles": {"fogra39": {
  "space": "cmyk", "src": "profiles/CoatedFOGRA39.icc",
  "hash": "sha256:…", "rendering_intent": "relative-colorimetric"}}}
```

`hash` is optional but strongly advised, for the same reason `FontDef.hash` is: a
profile that changes silently reprints the job in different colour, and you find
out on paper.

**Two mistakes worth naming.** CMYK components are unit-interval — `"m": 90`
meaning 90% is a validation error, deliberately, rather than a clip to 1.0. And
a spot ink must be named: the name *is* the separation, so two spellings of the
same ink become two plates.

Overprint is a style, not a colour: `style.overprint` is `none`/`fill`/`stroke`/
`both`, with `overprint_mode` for PDF's OPM.

### Spine-relative margins

`[top, right, bottom, left]` is unchanged and still correct for loose sheets. For
anything bound:

```yaml
margin: {top: 18mm, bottom: 22mm, inside: 20mm, outside: 14mm, gutter: 5mm}
```

`inside` faces the binding, `outside` the fore-edge, and they swap sides on every
leaf — which is why a book cannot be described in `left`/`right` without
rewriting the numbers per page. `gutter` is the extra allowance at the binding
edge, on top of `inside`.

**Mixing the two vocabularies is rejected.** `{"left": "20mm", "inside": "20mm"}`
names the same edge twice; silently picking one would misplace the text block on
every other page.

Declare a master per side so the mirroring is explicit:

```yaml
defs:
  masters:
    recto: {canvas: {preset: book-6x9}, side: recto, margin: {inside: 20mm, outside: 14mm}}
    verso: {canvas: {preset: book-6x9}, side: verso, margin: {inside: 20mm, outside: 14mm}}
```

A page may also state its own `side`, and a canvas may be a `spread: true`.

### Ruby and warichu

```jsonc
{"kind": "ruby", "base": "漢字", "text": "かんじ"}      // group ruby
{"kind": "ruby", "base": "仮名", "text": ["か", "な"]}  // mono ruby, one per base char
{"kind": "warichu", "content": ["割注"], "lines": 2}
```

Both are ordinary `Inline` members, so they compose with links, spans and code
runs, and work in flowed paragraphs as well as `text` objects. A warichu is
*inline* — it stays in the line and sets narrower. If the note should leave the
line and land in the page's note area, that is still `footnote`.

### Targets that state their output

```jsonc
{"name": "press", "output": {
   "format": "pdf", "output_intent": "press", "color_space": "cmyk",
   "color_profile": "fogra39", "font_embedding": "subset",
   "crop_marks": true, "bleed_marks": true, "registration_marks": true}}
{"name": "web", "output": {"format": "png", "dpi": 144}}
```

`canvas` is now optional on a target. If you have several targets that only
differ by format, delete the duplicated canvas blocks — they were a drift hazard.

---

### A baseline grid, so columns line up

Declare the rhythm once, then opt blocks into it. **The increment is the body
leading** — set them to the same value or the two fight each other.

```jsonc
{
  "defs": {
    "baseline_grid": { "increment": "13pt", "relative_to": "top_margin" },
    "tokens": { "styles": {
      "body":    { "font_size": "10pt", "line_height": "13pt", "align_to_baseline": true },
      "caption": { "font_size": "8pt",  "line_height": "13pt", "align_to_baseline": false }
    }}
  }
}
```

`relative_to` is `top_margin` (default — the grid follows the text block) or
`page` (it follows the trim). A fixed page overrides the document grid:

```jsonc
{ "mode": "page", "id": "half-title",
  "rendering": { "baseline_grid": { "increment": "18pt", "relative_to": "page" } } }
```

A `FlowSection` has no rendering contract, so a flowed book uses
`defs.baseline_grid` — which is the intended scope anyway, since the point is
that every column of every page shares one increment.

Three things worth knowing before you turn it on:

- **It is inert until something opts in.** Declaring the grid changes no output.
- **Snapping rounds a line down to the next gridline**, so a block whose
  `line_height` exceeds the increment opens up to a whole multiple of it. A
  26pt heading on a 13pt grid occupies 39pt, not 26pt. That is the grid working.
- **`align_to_baseline: false` is a real opt-out**, not just a default. Use it
  for captions and marginalia set smaller than the grid, which should sit tight
  to what they annotate.

`increment` must be positive: `0` and `-13pt` are rejected here, because a zero
pitch is infinitely many gridlines and a negative one marches up the page.

### A declared measure

Leading fixes the vertical increment; measure fixes the horizontal one.

```jsonc
{ "text_contract": { "measure": [60, 72] } }        // characters, [min, max]
```

Also settable per page at `rendering.text.measure`. It is **advisory** — it
constrains nothing structurally, because only something that can lay out a
resolved line can count characters in it. The contract rejects the two ways of
writing it that are certainly wrong: inverted (`[75, 45]`) and non-positive.
45–75 is the conventional range for continuous prose.

### A total-ink cap

2.9.0 let you specify process ink. It bounded each separation independently, so
`c=m=y=k=1.0` — 400% coverage — was structurally legal and physically
unprintable: it floods, offsets, and will not dry.

```jsonc
{ "defs": { "color_profiles": { "fogra39": {
    "space": "cmyk",
    "name": "Coated FOGRA39 (ISO 12647-2:2004)",
    "total_ink_limit": 3.0          // the sum of the four 0..1 components → "300%"
}}}}
```

The scale is `0..4`, matching `CmykColor`'s components — **not** a percentage.
`300` is rejected rather than silently read as 40000%. The contract cannot
enforce the cap (the coverage of a gradient, a spot `alternate` or an ICC
conversion is known only once resolved); declaring it is what gives the
engine's validator something to check a resolved paint against.


### Matte, star, winding and name

```jsonc
// one object mattes another — alpha or luma, either invertible
{"type": "text", "box": [40, 120, 520, 180], "text": "HARBOUR",
 "matte": {"source": "photo", "mode": "alpha", "invert": false}}

// a star that keeps its parameters
{"type": "star", "center": [520, 720], "points": 5,
 "outer_radius": 48, "inner_radius": 20, "outer_roundness": 0.15}

// a regular polygon — inner_radius is FORBIDDEN here, not ignored
{"type": "star", "star_type": "polygon", "center": [80, 720],
 "points": 6, "outer_radius": 36}

// winding, on path / polyline / polygon / star
{"type": "path", "d": "M 0 0 …", "direction": "counter-clockwise"}

// a label for humans; `id` stays the address links point at
{"type": "text", "id": "hdr_01", "name": "Chapter heading", …}
```

**Three things worth naming.** A star without `inner_radius` is rejected rather
than silently drawn as a polygon, and a polygon *with* one is rejected rather
than having it ignored — same rule as the gradient geometry validator. A star's
orientation is the inherited `rotation`, not a field of its own, so the two
cannot disagree. And an object naming itself as its own matte is rejected;
whether some *other* source resolves is R12 and belongs to the engine.

If you were drawing stars as `polygon` point lists, nothing breaks — that still
validates. Converting is worthwhile only where you want the parameters back.

### Typed symbol definitions

`defs.symbols` was `dict`. It now accepts a declared shape:

```jsonc
"symbols": {"rosette": {
  "content": [{"type": "star", "center": [16, 16], "points": 12,
               "outer_radius": 16, "inner_radius": 11}],
  "viewbox": [0, 0, 32, 32],
  "description": "A twelve-point rosette used as an award mark."}}
```

An arbitrary mapping is **still accepted** — narrowing would break documents
that validate today. Adopt the shape when convenient.

Instancing is unchanged and stays SDK-side: `use` is lowered by `sdk.expand()`
before validation, and the contract still rejects it. That is a decision, not an
omission — see [ADR 0001](docs/adr/0001-flat-document-model.md).

---

## If you consume the contract

### Renderers

The contract can now *say* things no renderer implements yet. That gap is
deliberate and is why `RenderOutput` is optional, but it needs handling:

- **A colour may no longer be a string.** Anywhere you did `if isinstance(color, str)`
  you now need a `space` branch, or an explicit "unsupported ink" error. Silently
  falling through to a default paints the wrong colour.
- `SpotColor.alternate` is the sanctioned fallback when you cannot image a spot;
  `IccColor.fallback` is the sRGB hex for the same purpose. Use them rather than
  inventing a conversion.
- `PageMargin` needs resolving against a page's `side` before it is geometry.
  A master with `side: verso` mirrors `inside`/`outside`.
- **Matte is a compositing pass, not a style.** `matte` names a sibling that must
  be rendered first, read as alpha or luminance, and applied — a renderer that
  ignores it paints the object unmasked, which is the loudest possible wrong
  answer. If you cannot composite, fail rather than degrade.
- **`star` is geometry you generate.** `points`, the two radii and the two
  roundness values produce the vertex list; `direction` sets the winding.
- Unrecognised `output` fields should be reported, not ignored: a document that
  asked for `crop_marks` and got none is a job that comes back from the printer.

### Validators and linters

Structural validity is unchanged in scope. Two new *semantic* rules belong in the
engine's validator, not here, because a JSON Schema cannot express them:

- **R13 — an `icc` colour's `profile` must resolve** against `defs.color_profiles`,
  and a target's `output.color_profile` likewise. The contract types the
  reference; only a whole-document pass can check it lands.
- **R14 — printer's marks need somewhere to print.** `crop_marks` /
  `bleed_marks` are drawn outside the trim, so a target requesting them on a
  canvas with no `bleed` is asking for marks that will be cut off.
- **R15 — total ink coverage must not exceed the declared cap.** Needs a
  *resolved* paint: a gradient ramps between two coverages, a spot ink converts
  through its `alternate`, and an ICC colour converts through its profile. The
  contract can only carry the number; measuring the ink is the engine's job.
  This is the rule `total_ink_limit` exists to feed.
- **R16 — a block that opts into the grid should fit it.** `align_to_baseline`
  with no grid in scope is a silent no-op, and a `line_height` larger than the
  increment silently opens the block to the next whole multiple. Both are
  warnings, not errors: the second is legitimate for headings.
- **R17 — measure is advisory and checkable.** A resolved line falling far
  outside `text_contract.measure` is a warning; nothing structural can catch it,
  because character count depends on the shaped font.

### SDKs and MCP servers

See the tables in the repository's issue tracker entry for this release. The
short version, unchanged by 2.10.0: the contract exposes all seven capabilities
today, and the authoring SDK, renderer and MCP tool surfaces expose **none** of
them yet. Until they do, these fields are authored by hand or by a client
writing JSON/YAML directly, which is supported and validated but not convenient.

The rhythm layer widens that gap in a specific way worth stating, because it is
the one addition here that is **not** self-executing:

| Field | Contract | Renderer | SDK | MCP |
|---|---|---|---|---|
| `defs.baseline_grid` | ✅ typed, validated | ❌ must snap baselines | ❌ no builder | ❌ not in tool schema |
| `Style.align_to_baseline` | ✅ | ❌ | ❌ | ❌ |
| `TextContract.measure` | ✅ | n/a (advisory) | ❌ | ❌ |
| `ColorProfileDef.total_ink_limit` | ✅ | n/a (validator R15) | ❌ | ❌ |

A document may declare a grid today and every consumer will accept it; **none
will yet align anything to it.** That is a deliberate contract-first ordering —
the format has to be able to say it before an engine can implement it — but it
means `align_to_baseline: true` is currently a declaration of intent, not a
rendering guarantee. Do not ship it to a customer expecting visual change until
the renderer lands its half.

---

## Rollback

Pin `frameforge-api>=1.0,<1.1`. Documents authored against 2.9.0, 2.10.0 or
2.11.0 that use any of the new fields will fail there — correctly, since 1.0.x
carries contract 2.8.2 and cannot interpret them. Forward compatibility is
explicitly not promised; see `frameforge_api.COMPATIBILITY`.

Note that rolling back this far also gives up `ff-codemod`, which did not exist
before 1.2.0 — so migrate *before* you pin, not after.
