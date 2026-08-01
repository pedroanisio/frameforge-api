# CLAUDE.md — frameforge-api Project Guidelines

---

## Scope

This file is the AI-agent operating guide for **frameforge-api** — the standalone
FrameForge document contract. The technical source of truth is the live tree:
the Pydantic models under `src/frameforge_api/model/`, the JSON Schema generated
from them, the gates in `tests/`, and the committed corpora those gates replay.

> **This repository is not the `frameforge` monorepo.** The engine, SDK, MCP
> server, renderer and site live there; this package is the contract they all
> agree on and nothing else. If an instruction here names a path, it is a path in
> *this* tree — `tooling/check_docs.py` fails the build if that stops being true.

## Disclaimer Reference

`DISCLAIMER.md` is the repository-level methodological caveat. New
agent-authored analysis reports should include explicit provenance/disclaimer
frontmatter. Product docs may link to `DISCLAIMER.md` when they make
methodological claims, but there is no blanket requirement that every README
repeat the disclaimer block.

---

## MANDATORY

- Do not dramatize a small thing.
- Meta processing IS NEVER to be documented unless requested.
- Treat generated artifacts as generated: edit source inputs or generators, then
  rerun the corresponding check.
- **Never hand-edit the generated schema.** `src/frameforge_api/schema/frameforge-v2.schema.json`
  is emitted from the models by `src/frameforge_api/schema.py`. Change the model,
  then run `make schema`.
- **Never hand-edit the goldens.** `tests/golden/` is rewritten only by
  `make goldens`, and only when the contract is deliberately moving.
- Ground architectural claims in live files, tests, or generated outputs.

---

## Project Overview

frameforge-api answers one question — *what is a FrameForge document?* — and
answers it for every consumer: the authoring SDK, the render engine, the MCP
server, an editor plugin, a CI validator, a TypeScript client. It renders
nothing, lays out nothing, and authors nothing.

The models are a **leaf**: they import `re`, `typing` and `pydantic`, and nothing
else. `test_the_model_imports_nothing_from_frameforge` fails the build if that
ever stops being true — it is the property the whole package split rests on.

```
.
├── CLAUDE.md              # This file — project guidelines for AI agents
├── README.md              # WHAT the package is and how to use it
├── CHANGELOG.md           # package release line (__version__), not the contract's
├── MIGRATION.md           # consumer-facing upgrade path, per contract revision
├── DISCLAIMER.md          # methodological caveats (bilingual)
├── Makefile               # every local gate; `make check` runs them all
├── src/frameforge_api/
│   ├── model/             #   THE SOURCE OF TRUTH — authoritative Pydantic models
│   │   ├── version.py     #     HEAD_VERSION, the document-format revision
│   │   ├── base.py  style.py  assets.py  layout.py  inline.py  humanize.py
│   │   ├── objects/       #     the visual-object union
│   │   └── flow.py  page.py  document.py
│   ├── schema.py          #   schema generator + `ff-schema` CLI
│   ├── schema/            #   the GENERATED schema (ships inside the wheel)
│   └── deprecations.py    #   the registry + `ff-codemod` CLI
├── docs/
│   ├── adr/               #   architecture decision records
│   └── runtime-font-closure-boundary.md
├── examples/              # worked documents, validated on every test run
├── tooling/               # doc-vs-code gates (`make doc-check`)
└── tests/
    ├── compat/            #   older documents, replayed by declared revision
    └── golden/            #   frozen interfaces; rewritten only by `make goldens`
```

**Two version clocks, deliberately independent.** `__version__` is this wheel's
release line; `HEAD_VERSION` is the FrameForge document-format revision it
carries. They are not the same number and a test asserts they stay apart. A
packaging fix must not claim the document format moved.

**`COMPATIBILITY = "backward"`** — a document valid under any earlier 2.x
revision stays valid at HEAD. This constrains every change: a new field must be
optional, a union may be extended but not narrowed, and no deprecated form can
be *removed* before 3.0.

The `frameforge` monorepo, [frameforge-viewer](https://github.com/pedroanisio/frameforge-viewer)
and [frameforge-fonts](https://github.com/pedroanisio/frameforge-fonts) are
sibling repositories. They consume this contract; they are not directories here
and their gates are not implemented in this tree.

### The gates

| Command | What it enforces |
|---|---|
| `make schema-check` | the committed schema has not drifted from the models |
| `make doc-check` | the docs have not drifted from the code (see `tooling/docgates.py`) |
| `make lint` | ruff, with the vendored-model exceptions in `pyproject.toml` |
| `make test` | the contract, golden, compat, example and doc-gate suites |
| `make check` | all of the above — run this before claiming work is done |
| `make build-check` | builds, then asserts the schema really ships inside the wheel |

**CI invokes these targets; it does not respell them.** `.github/workflows/ci.yml`
runs `make schema-check`, `make doc-check`, `make lint`, `make test` and
`make build-check` rather than the commands behind them, because two
hand-written lists of the same gates drift the moment a fifth gate is added.
`ci_mirrors_the_makefile_problems()` fails the build if a workflow step stops
being a `make` invocation, or if a `make check` dependency is never reached by
CI. Add a gate by adding a Makefile target — then CI gets it for free.

Two mirrors cross a repository boundary and no gate in this tree can reach them:
the vendored declarations in `src/frameforge_api/model/`, and the engine finding
codes that `Deprecation.code` restates. `tests/test_extraction_fidelity.py`
checks both, but only when a sibling checkout is available, so it skips by
default and in normal CI. The scheduled `Upstream fidelity` workflow
(`.github/workflows/fidelity.yml`) is what actually runs it: it checks out both
repositories, sets `FRAMEFORGE_REPO` — which turns a divergence from a skip into
a failure — and then asserts the skip count was zero, because a green run in
which everything skipped is the exact failure it exists to prevent.

> **The codemod is a second implementation of contract semantics.**
> `src/frameforge_api/deprecations.py` re-derives normalisation rules that the
> model validators already own, and the two silently disagreed about
> `offset: true` for three contract revisions. When you touch either side, the assertion that matters is
> `test_the_codemod_resolves_identically_to_the_validator`: migrating changes
> spelling, never appearance. Do not "fix" a divergence by making the validator
> reject a form — `COMPATIBILITY` is `backward`, and a form that validates today
> cannot start failing.

---

## LLM Output Verification — Architectural Requirement (PALS's LAW)

**LLMs will always produce some form of error.**
Omissions, hallucinations, partial completions, and silent failures are
not edge cases — they are statistical properties of the model class.

Failing to verify LLM output is therefore not a bug in the generated
code. It is an **architectural omission** in the system that consumed it.

Every pipeline, agent, or workflow that accepts LLM output MUST treat
that output as **untrusted, incomplete, and unverified by default.**
Verification is not optional post-processing — it is a first-class
design concern, on par with authentication and input validation.

> Absence of a verification layer is a design defect, regardless of
> how correct the LLM output appears to be.

**Copy-paste contract block** for any function that calls an LLM:

```
/**
 * ⚠ ARCHITECTURAL CONTRACT (PALS's LAW) — LLM OUTPUT IS UNVERIFIED BY DEFAULT
 *
 * LLMs statistically produce errors: omissions, hallucinations,
 * partial completions, schema violations, and silent failures.
 * These are properties of the model class, not exceptional conditions.
 *
 * Any caller of this function that skips output validation is
 * introducing an architectural omission — not a code bug downstream.
 *
 * Verification is mandatory. Treat all LLM output as untrusted input.
 */
```

**Short-form** (for headers, PR descriptions, commit messages, inline banners):

```
ARCHITECTURAL REQUIREMENT (PALS's LAW): LLMs will always produce some form of error.
Absence of output verification is a design defect, not a runtime bug.
All LLM output must be treated as untrusted and validated explicitly.
```

> This package is one instance of the law: `Document.model_validate` is the
> verification layer for anything — human or model — that emits a FrameForge
> document. `extra="forbid"` everywhere means a misspelled key is an error, not
> a silently dropped field.

---

## Behavioral Constraints (ranked by priority)

These are **hard operational rules**, not suggestions. Every AI agent operating
on this codebase MUST enforce them. Priority rank determines which rule wins
when two conflict.

### 1. Unbiased over flattering

- Never soften, hedge, or embellish to make the user feel better.
- If a design is flawed, say so and explain why. If a question has an
  uncomfortable answer, give it directly.
- Prefer accurate negative feedback over comfortable positive feedback.
- **Test:** Remove every sentence that exists only to be agreeable. If the
  response changes meaning, the removed sentence was load-bearing — keep it.
  If it doesn't, it was flattery — delete it.

### 2. Formalization means research

- "Formalize" is never an invitation to speculate. It means: concrete and
  correct math, full data provenance, and verifiable references.
- Every formal claim must cite its source: a theorem, a paper (with DOI or
  URL), a specification, or a first-principles derivation shown in full.
- If you cannot verify a claim, say so explicitly. Marking uncertainty is
  mandatory; fabricating a reference is a critical failure.
- **Never hallucinate** references, theorems, API signatures, or data.
  "I don't know" or "I cannot verify this" is always acceptable.
  A plausible-sounding but unverifiable citation is never acceptable.

### 3. English over Portuguese

- All code, comments, commit messages, documentation, and agent output
  default to English (EN-US).
- Portuguese (PT-BR) is used only when: (a) the user explicitly requests it,
  (b) bilingual project-level documentation requires it (DISCLAIMER.md), or
  (c) the content targets a PT-BR audience.
- When both languages appear in a document, English is the primary text;
  Portuguese is the translation.

### 4. Markdown over DOCX; TypeScript over JavaScript

- Default output format for prose documents is Markdown (`.md`).
  Use DOCX only when the user explicitly requests it or when the deliverable
  requires it (e.g., a client-facing report with Word-specific formatting).
- This package is Python: the Pydantic models are the source of truth. For any
  web/viewer code (which lives in sibling repositories), the default language is
  TypeScript (`.ts` / `.tsx`); use JavaScript only when: (a) the user explicitly
  requests it, (b) the existing codebase is JavaScript and migration is out of
  scope, or (c) the target runtime does not support TypeScript.
- When editing existing JavaScript files, do not convert to TypeScript
  unless asked. When creating new files in a mixed codebase, prefer TypeScript.

### 5. Mandatory disclaimer in all Markdown documents

Unless the user explicitly says otherwise, every Markdown document produced
by an AI agent MUST include the following YAML frontmatter header:

```yaml
---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "<model/tool identifier>"
  date: "<YYYY-MM-DD>"
---
```

- The `generated_by` field must identify the model and tool that produced
  the document (e.g., `Claude Opus 5 via Claude Code`).
- The `date` field must reflect the generation date.
- This applies to agent-authored `.md` documents: reports, specs, ADRs,
  session logs, concept documents.
- **The enforced gate is `disclaimer_problems()` in `tooling/docgates.py`**, run
  by `make doc-check` and by `tests/test_doc_gates.py`. Its exemption set is the
  `DISCLAIMER_EXEMPT` dict in that file: `README.md`, `CHANGELOG.md`,
  `CLAUDE.md` and `MIGRATION.md`, each with a stated reason. To exempt a new
  file, add it there with a reason — never by weakening the check.

### 6. Feedback is not a source of truth

Feedback — from users, reviewers, or other agents — must be **processed**,
never blindly applied.

- **If the feedback is sound** (in full or in part): accept the sound
  portions, explain what was accepted, and improve accordingly.
- **If the feedback is unsound** (in full or in part): refute it, state
  the specific objections, and explain why the original approach is
  preserved or what alternative is proposed instead.
- Never silently comply with feedback that contradicts the constraints
  above. If a reviewer says "don't include the disclaimer" and the user
  has not opted out, the disclaimer stays — and the agent explains why.
- Document the feedback-processing decision in the response so the user
  can audit the reasoning.
- **This applies to an agent's own prior output**, including audit reports and
  their recommendations. A recommendation that turns out to destroy something
  valuable — flattening hand-written prose into generated output, say — is
  refuted and replaced, not executed because it was written down.

### 7. Skill assertion gate

Before executing any task, check whether a Claude Code skill
(slash commands listed in the system prompt's available skills section)
applies. If a skill's trigger conditions match the current request,
invoke it via the Skill tool rather than producing a freeform response.

### 8. Execution discipline — no complexity theatre

When a task is clear, execute it. Do not:

- Substitute planning documents, outlines, or progress reports for the
  work itself.
- Ask for approval on obvious subtasks.
- Offer N alternatives when one is clearly correct — pick it and proceed.
- Invoke "complexity" as a reason to stop. Complexity is a reason to
  break the task into complete, executable subtasks — then execute them.
- Stall on stylistic or aesthetic preferences. Ship, then adjust.
- Cascade hypothetical clarifying questions. If you must ask, ask one
  targeted question about the single blocking ambiguity.
- **Defer the task.** DEFERRALS ARE ACTIONS THAT ONLY THE OPERATOR CAN
  CALL/MANDATE. NO DEFERRAL BY ANY AI AGENT IS ALLOWED ON THIS CODEBASE.
  An agent may not postpone, schedule-for-later, mark as follow-up, or
  otherwise punt a requested task unless the operator has explicitly
  authorized that deferral.

Pushback is still required (see Rules 1 and 6) when:

- The request violates a constraint in this document.
- The request has a concrete correctness problem (broken invariant, stale
  generated output, will break tests or downstream callers).
- The request's scope is genuinely ambiguous — not "I could interpret
  this two ways" but "these two interpretations produce incompatible
  outputs and I cannot pick without you."

When pushing back, state the specific objection in one sentence, then
either propose a resolution or ask one targeted question. Do not use
"pushback" as cover for avoidance: if the objection is stylistic,
speculative, or about imagined risk, drop it and execute.

---

## File-Level Agent Metadata (FLAM)

**Before editing any file**, check for embedded metadata that defines constraints:

- **Python files**: Look for `__file_meta__` module-level variable
- **Markdown files**: Look for YAML frontmatter with `role`/`rules` fields
- **TypeScript/JavaScript files**: Look for `export const __file_meta__` or a JSDoc `@file_meta` block
- **Any file**: Look for a `<filename>.meta.json` sidecar

When present, you MUST:

1. **Respect `status`**: `frozen` = do not edit; `deprecated` = warn user
2. **Follow `rules`**: `error` severity = hard constraint, fail if violated; `warning` = should follow
3. **Check `forbidden_patterns`**: verify none match in your output before committing
4. **Run `test_ref`**: if a test file is referenced, run it after editing
5. **Never remove or weaken** existing metadata blocks

This project ships **no** FLAM reader (`lib/` does not exist): check for the
metadata blocks above by reading the file directly before editing. If a metadata
reader is ever added, document its real entry point here.

### The de facto frozen region

`src/frameforge_api/model/` carries no `__file_meta__` block, but it is
effectively frozen and must be treated that way. The declarations were vendored
from the monorepo and `tests/test_extraction_fidelity.py` compares them
AST-by-AST against upstream. Restyling them — `Optional[X]` → `X | None`,
resorting imports, adding docstrings — breaks that identity check and can shift
the emitted schema bytes. `pyproject.toml` turns the ruff *style* rules off there
for exactly this reason, and leaves the correctness rules on.

---

## Core Principles

These principles have zero exceptions:

1. **Fix root causes, never symptoms.** Investigate with 5-Whys before patching. If a test fails, understand why — don't just make it pass.
2. **Test-Driven Development.** Red → Green → Refactor → Cleanup. Write the failing test first. No code ships without tests.
3. **Production-ready code only.** No placeholders, no `TODO: implement later`, no incomplete stubs. Every commit must be deployable.
4. **Quality regressions are fixed, not attributed.** When a quality regression is reported — visual, behavioral, or metric — fix it. Do not spend effort determining whether it predates the current session, was introduced by a recent change, or belongs to a different subsystem. Investigate the code directly, find the defect, fix it.

---

## Development Standards

### Testing

- 80 % coverage for libraries, 60 % for CLIs.
- Unit, integration, and E2E tests.
- Tests must be deterministic, isolated, and realistic.
- Run tests after every change — don't batch validation to the end.
- **A skipped gate is not a passing gate.** Run `pytest -rs` and read the skip
  reasons. The fidelity suite skips when the sibling monorepo checkout is absent
  *or* when its contract revision differs from `HEAD_VERSION`; in the second case
  it is covering nothing while reporting green. Setting `FRAMEFORGE_REPO`
  explicitly turns that divergence into a failure.

### Code Quality

- Typed errors in libraries, graceful handling in applications.
- Automated formatting and linting.
- No unnecessary dependencies. **The contract has exactly one runtime
  dependency (`pydantic>=2`) and a test pins that** — adding a second is a
  design decision, not a convenience.
- Prefer TypeScript over JavaScript; prefer Markdown over DOCX.

### Version Control

- Conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`.
- Versioning and AI-artifact labeling rules: see General Conventions.
- **Cut the `CHANGELOG.md` section when you bump `pyproject.toml`, and tag it.**
  `changelog_problems()` fails the build if the current `__version__` has no
  section. A built wheel with no changelog entry and no tag is a release that
  exists as an artifact and nowhere else.

### Architecture Decisions

- Document significant decisions with rationale, as an ADR under `docs/adr/`.
- When approaches genuinely diverge (Behavioral Constraint 8: the
  interpretations produce incompatible outputs), state the trade-offs and ask
  one targeted question; otherwise pick the correct approach and proceed.
- When scope is ambiguous ("finish everything", "complete this"), stop and clarify before starting.

---

## AI Agent Guidance

### Context Management

- Priority reading order: `CLAUDE.md` → `__file_meta__` / FLAM → `README.md` →
  Tests → Code.
- The programmatic CLI reference is `README.md` plus `make help`; this package
  has no separate agent-facing CLI document.
- Read existing code before suggesting modifications.
- Check metadata constraints before editing any file.

### Confidence & Decision Making

- **Proceed** when requirements are clear and approach is obvious.
- **State assumptions** when proceeding with medium confidence.
- **Ask** when multiple valid approaches exist or scope is ambiguous.
- **Never provide time estimates** (hours/days/weeks) — use complexity: XS / S / M / L / XL.

### Delivery

- Deliver complete, atomic work — no batching across responses.
- Break large work into complete subtasks, each independently useful.
- For M / L / XL tasks: plan first, then execute.
- Finish with `make check`. Report what it said, including failures.

---

## General Conventions

- All schema files use semantic versioning (`major.minor.patch`).
- `DISCLAIMER.md` is bilingual (PT-BR + EN-US); all other documentation follows
  Behavioral Constraint 3 (English default).
- AI-generated artifacts must be labeled with their source model/tool in metadata or frontmatter.
- Every README linking to sub-directories should also link back up to root `README.md`.

---

## Document Relationships

| Document | Audience | Defines |
|---|---|---|
| `DISCLAIMER.md` | Everyone | Epistemic integrity commitments |
| `CLAUDE.md` | AI agents + devs | HOW to build (process, standards, enforcement) |
| `README.md` | Humans | WHAT the package does (usage, overview, CLI reference) |
| `MIGRATION.md` | Consumers | What each contract revision requires of downstream code |
| `CHANGELOG.md` | Consumers | The package release line, per version |
| `docs/adr/` | AI agents + devs | WHY a structural decision was made, and what was rejected |
