"""Deprecated FrameForge forms: the registry, the codemod, and the ``ff-codemod`` CLI.

The contract has always *had* deprecations. What it did not have was a way for
anyone to act on them.

**The migration path did not ship.** Three model docstrings and the P3 stroke
error message told the reader to "run ``tooling/codemod.py``" — a script in the
``frameforge`` monorepo, not in this wheel. Someone who installed
``frameforge-api`` was pointed at a file they do not have. This module is that
script, rewritten as an ordinary importable function with a console script over
it, exactly the way :mod:`frameforge_api.schema` replaced the monorepo's
un-importable ``build_schema.py``.

**The status was invisible to machines.** Deprecation lived only in English
``description`` prose, so a codegen tool, an editor, or a model reading the JSON
Schema had no signal. Two things fix that, because one is not enough:

* the three deprecated object types and the superseded ``tokens.text_styles``
  namespace carry the standard JSON Schema 2020-12 ``deprecated`` keyword;
* the **legacy keys cannot**. ``offset``, ``object``, ``type``, ``c1``/``c2``
  and ``dash`` are normalised by ``mode="before"`` validators, so they never
  appear in the schema as properties and there is nothing for the keyword to
  attach to. They are published instead as :data:`DEPRECATIONS`, emitted into
  the schema under ``x-frameforge-deprecations``.

Nothing here is a validation change. :data:`frameforge_api.COMPATIBILITY` is
``backward`` — a document valid under any earlier 2.x revision stays valid at
HEAD — so a deprecated form cannot start being rejected inside the 2.x line.
Deprecation here means *discouraged, mechanically migratable, and still valid*;
the two ``removed-form`` entries are the exception, and they were already
rejected before this module existed.

    >>> from frameforge_api import migrate_document
    >>> result = migrate_document({"dsl": "FrameForge", "pages": []})
    >>> result.changed
    False

CLI::

    ff-codemod doc.fg.yaml            # lint: report, write nothing, exit 1 if found
    ff-codemod --write doc.fg.yaml    # rewrite in place
    ff-codemod --stdout doc.json      # print the migrated document
    ff-codemod --json doc.json        # findings as machine-readable JSON
    ff-codemod --list                 # print the registry
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DEPRECATIONS",
    "DEPRECATIONS_BY_ID",
    "Deprecation",
    "Finding",
    "MigrationResult",
    "main",
    "migrate",
    "registry_json",
    "scan",
]


# --------------------------------------------------------------------------- #
#  The registry                                                               #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Deprecation:
    """One deprecated form, as data rather than as prose.

    `valid_at_head` is the field a consumer actually branches on. A
    ``legacy-key`` still parses — a validator normalises it before field
    validation — while a ``removed-form`` does not, and telling those apart is
    the difference between "tidy this up when convenient" and "this document
    does not load".
    """

    id: str
    kind: str
    """``object-type`` | ``legacy-key`` | ``namespace`` | ``removed-form``."""
    subject: str
    replacement: str
    fix: str
    """``automatic`` (the codemod rewrites it) or ``manual``."""
    valid_at_head: bool
    """Whether a document using this form still validates against HEAD."""
    code: str
    """The engine validator's error code for the same form, so the contract's
    lint and the engine's report name one thing one way."""
    note: str

    @property
    def severity(self) -> str:
        """Default severity of a finding for this form."""
        return "info" if self.valid_at_head else "error"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "subject": self.subject,
            "replacement": self.replacement,
            "fix": self.fix,
            "valid_at_head": self.valid_at_head,
            "code": self.code,
            "severity": self.severity,
            "note": self.note,
        }


DEPRECATIONS: tuple[Deprecation, ...] = (
    # ---- renderer-shortcut object types: aliases of a more general primitive #
    Deprecation(
        id="deprecated-alias-circle",
        kind="object-type",
        subject="circle",
        replacement="ellipse",
        fix="automatic",
        valid_at_head=True,
        code="deprecated-alias",
        note="A circle is an ellipse with rx == ry. Two spellings of one shape means "
             "two code paths in every renderer and two ways for a document to be "
             "internally inconsistent; the codemod rewrites it to `ellipse`.",
    ),
    Deprecation(
        id="deprecated-alias-polygon",
        kind="object-type",
        subject="polygon",
        replacement="polyline (closed: true)",
        fix="automatic",
        valid_at_head=True,
        code="deprecated-alias",
        note="A polygon is a closed polyline. `polyline` already carries `closed`, so "
             "the alias adds a union member without adding an expressible shape.",
    ),
    Deprecation(
        id="deprecated-alias-curve",
        kind="object-type",
        subject="curve / bezier",
        replacement="path",
        fix="automatic",
        valid_at_head=True,
        code="deprecated-alias",
        note="A curve is a path of one cubic segment, and `path` can already say every "
             "curve plus everything a curve cannot. Two discriminator spellings "
             "(`curve` and `bezier`) for one object compound the problem.",
    ),
    # ---- legacy keys: normalised before field validation, invisible in schema #
    Deprecation(
        id="curve-control-shorthand",
        kind="legacy-key",
        subject="c1 / c2 on curve",
        replacement="control1 / control2",
        fix="automatic",
        valid_at_head=True,
        code="deprecated-alias",
        note="Short aliases of the canonical control points. Setting a short and a long "
             "form that disagree is an error rather than a silent pick, but the two "
             "spellings still let one document contradict itself between objects.",
    ),
    Deprecation(
        id="gradient-stop-offset",
        kind="legacy-key",
        subject="GradientStop.offset",
        replacement="GradientStop.position",
        fix="automatic",
        valid_at_head=True,
        code="deprecated-alias",
        note="2.2.0 made `position` authoritative. `offset` is still accepted and "
             "normalised — including the 0..1 unit-interval spelling, which becomes a "
             "percentage — but it never appears in the schema, so a consumer reading "
             "the schema alone cannot know it is legal.",
    ),
    Deprecation(
        id="connector-endpoint-object",
        kind="legacy-key",
        subject="ConnectorEndpoint.object",
        replacement="ConnectorEndpoint.ref",
        fix="automatic",
        valid_at_head=True,
        code="deprecated-alias",
        note="`ref` is the canonical name for the target object id, matching every "
             "other reference in the contract; `object` is the renderer's older "
             "spelling, kept because the committed fixtures use it.",
    ),
    Deprecation(
        id="connector-route-type",
        kind="legacy-key",
        subject="ConnectorRoute.type",
        replacement="ConnectorRoute.kind",
        fix="automatic",
        valid_at_head=True,
        code="deprecated-alias",
        note="`type` is the discriminator key everywhere else in the contract, so a "
             "route whose `type` is a routing mode rather than an object kind reads as "
             "a discriminator and is not one.",
    ),
    Deprecation(
        id="style-dash-shorthand",
        kind="legacy-key",
        subject="Style.dash",
        replacement="Style.stroke_dasharray",
        fix="automatic",
        valid_at_head=True,
        code="deprecated-alias",
        note="A shorthand for the CSS-named property the style module standardised on. "
             "It serialises as `stroke_dasharray` anyway, so authoring `dash` only "
             "moves the normalisation later. Declaring both is an error.",
    ),
    # ---- a superseded namespace, and the shadowing hazard it carries -------- #
    Deprecation(
        id="tokens-text-styles",
        kind="namespace",
        subject="tokens.text_styles",
        replacement="tokens.styles",
        fix="automatic",
        valid_at_head=True,
        code="deprecated-alias",
        note="Unlike every other entry here this one does NOT collapse at parse time: "
             "`text_styles` and `styles` are both live `dict[str, Style]` maps and the "
             "renderer resolves `text_styles` first. A name present in both therefore "
             "resolves to the one the author probably did not mean, and nothing in the "
             "contract reports it. The codemod merges them, `text_styles` winning, "
             "which is what the renderer already does.",
    ),
    # ---- removed forms: these do not validate at HEAD ---------------------- #
    Deprecation(
        id="stroke-single-form",
        kind="removed-form",
        subject="inline-geometry stroke {color, width, dash, ...}",
        replacement="stroke (paint) + stroke_style (geometry)",
        fix="automatic",
        valid_at_head=False,
        code="stroke-single-form",
        note="The one breaking change of the 2.x line (P3). Paint and geometry were "
             "split so a stroke could reference a shared geometry token; the old bundle "
             "is rejected with an actionable error rather than a vague type error.",
    ),
    Deprecation(
        id="size-renamed",
        kind="removed-form",
        subject="content-sizing size (an object)",
        replacement="sizing",
        fix="automatic",
        valid_at_head=False,
        code="size-renamed",
        note="P4 renamed the content-sizing key because it collided with the numeric "
             "`Icon.size`. The rewrite is unambiguous: every current `size` field in "
             "the contract is a scalar or a pair, so only the pre-P4 key was ever an "
             "object.",
    ),
)

DEPRECATIONS_BY_ID: dict[str, Deprecation] = {d.id: d for d in DEPRECATIONS}


def registry_json() -> list[dict[str, Any]]:
    """The registry as plain JSON, for embedding in the schema or shipping over a wire."""
    return [d.as_dict() for d in DEPRECATIONS]


# --------------------------------------------------------------------------- #
#  Findings                                                                   #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Finding:
    """One occurrence of a deprecated form, located by RFC 6901 JSON Pointer."""

    id: str
    path: str
    detail: str
    severity: str
    automatic: bool
    """Whether :func:`migrate` can rewrite THIS occurrence.

    Not the same as ``Deprecation.fix``: a form that is normally automatic can
    still be un-rewritable in context — a pre-P3 stroke bundle beside a *named*
    ``stroke_style`` token, or a ``dash`` that contradicts an explicit
    ``stroke_dasharray``.
    """

    @property
    def deprecation(self) -> Deprecation:
        return DEPRECATIONS_BY_ID[self.id]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "detail": self.detail,
            "severity": self.severity,
            "automatic": self.automatic,
            "replacement": self.deprecation.replacement,
            "code": self.deprecation.code,
        }

    def __str__(self) -> str:
        return f"{self.severity:<7} {self.path}  {self.id}: {self.detail}"


@dataclass(frozen=True)
class MigrationResult:
    """A migrated document, plus what was found getting there."""

    document: dict[str, Any]
    findings: tuple[Finding, ...] = ()

    @property
    def changed(self) -> bool:
        """True when the codemod actually rewrote something."""
        return any(f.automatic for f in self.findings)

    @property
    def manual(self) -> tuple[Finding, ...]:
        """Occurrences the codemod refused to rewrite; a human has to resolve these."""
        return tuple(f for f in self.findings if not f.automatic)


# --------------------------------------------------------------------------- #
#  Traversal                                                                  #
# --------------------------------------------------------------------------- #
#: Documented free-form bags. `meta` is "never interpreted as geometry", `data`
#: holds arbitrary payloads (CSL-JSON bibliographies), `params` holds named
#: scalars. Rewriting a key inside one of these corrupts a payload the contract
#: promised not to read — and `meta.offset` beside a `meta.color` is an entirely
#: ordinary annotation, indistinguishable by shape from a gradient stop.
_OPAQUE = frozenset({"meta", "data", "params"})

#: Keys whose VALUES are maps of name -> Style. Used to recognise a style bundle
#: without needing to know where in the document it sits.
_STYLE_MAPS = frozenset({"styles", "text_styles", "stroke_styles", "fill_styles"})

#: Keys whose value IS a Style bundle.
_STYLE_KEYS = frozenset({"style", "stroke_style"})

_GRADIENT_KINDS = frozenset({"linear", "radial", "conic"})

#: Exactly the keys `ObjBase._stroke_paint_only` guards on, so the codemod fires
#: precisely where the model rejects — no wider, no narrower.
_P3_GEOMETRY_MARKERS = ("width", "dash", "linecap", "linejoin")

#: Pre-P3 inline stroke geometry -> the CSS-named `Style` properties it became.
#: `opacity` maps to `Style.opacity`, NOT to `stroke_opacity`: there is no such
#: field, and `Style` is `extra="forbid"`, so emitting it produces a migrated
#: document that does not validate.
_P3_GEOMETRY_TO_STYLE = {
    "width": "stroke_width",
    "dash": "stroke_dasharray",
    "dashoffset": "stroke_dashoffset",
    "linecap": "stroke_linecap",
    "linejoin": "stroke_linejoin",
    "miterlimit": "stroke_miterlimit",
    "opacity": "opacity",
    "arrow_start": "arrow_start",
    "arrow_end": "arrow_end",
}


def _escape(token: str) -> str:
    """RFC 6901 escaping: `~` -> `~0`, `/` -> `~1`."""
    return token.replace("~", "~0").replace("/", "~1")


@dataclass
class _Pass:
    """One traversal. `fix` decides whether rewrites are applied or only reported."""

    fix: bool
    findings: list[Finding] = field(default_factory=list)

    def report(self, dep_id: str, path: str, detail: str, *,
               automatic: bool = True, severity: str | None = None) -> None:
        self.findings.append(Finding(
            id=dep_id,
            path=path or "/",
            detail=detail,
            severity=severity or DEPRECATIONS_BY_ID[dep_id].severity,
            automatic=automatic,
        ))


def _walk(node: Any, path: str, key: str | None, is_style: bool, pas: _Pass) -> Any:
    """Rewrite (or merely inspect) one node, returning the new value.

    Never mutates its input: every container is rebuilt. That is what lets
    :func:`scan` and :func:`migrate` share one traversal, and what keeps a
    caller's document intact when they only asked a question.
    """
    if isinstance(node, list):
        return [_walk(v, f"{path}/{i}", key, is_style, pas) for i, v in enumerate(node)]
    if not isinstance(node, dict):
        return node

    out = dict(node)

    # -- gradient stops: `offset` -> `position` -------------------------------
    # Keyed on the gradient's own shape (a `kind` from the gradient vocabulary
    # plus a `stops` list) rather than on the `offset` key, because
    # `ConnectorEndpoint.offset` and `OuterRing.offset` are current fields that
    # a key-only rule would rename out from under the renderer.
    if out.get("kind") in _GRADIENT_KINDS and isinstance(out.get("stops"), list):
        out["stops"] = [
            _gradient_stop(s, f"{path}/stops/{i}", pas) for i, s in enumerate(out["stops"])
        ]

    obj_type = out.get("type")

    # -- P3: an inline-geometry `stroke` splits into paint + geometry ---------
    # Gated on the `stroke` KEY, not on the bundle's shape: `OuterRing` is
    # `{color, width, gap, offset, dash, opacity}` — the same shape — and is a
    # perfectly current field. A shape-only rule deletes the ring.
    # Excluded inside a Style bundle, where `stroke` is paint and there is no
    # `stroke_style` sibling to move geometry into.
    stroke = out.get("stroke")
    if (not is_style and isinstance(stroke, dict)
            and any(k in stroke for k in _P3_GEOMETRY_MARKERS)):
        out = _split_p3_stroke(out, path, pas)

    # -- P4: a dict-valued `size` is the pre-rename content-sizing key --------
    if isinstance(out.get("size"), dict):
        pas.report("size-renamed", path,
                   "content-sizing `size` object; `size` is now the numeric icon size")
        if pas.fix:
            out["sizing"] = out.pop("size")

    # -- the deprecated object types ------------------------------------------
    if obj_type == "circle" and "r" in out and "center" in out:
        pas.report("deprecated-alias-circle", path, "circle is an ellipse with rx == ry")
        if pas.fix:
            r = out.pop("r")
            out["type"] = "ellipse"
            out["rx"] = out["ry"] = r
    elif obj_type == "polygon" and isinstance(out.get("points"), list):
        pas.report("deprecated-alias-polygon", path, "polygon is a closed polyline")
        if pas.fix:
            out["type"] = "polyline"
            out["closed"] = True
    elif obj_type in ("curve", "bezier") and "from" in out and "to" in out:
        out = _curve_to_path(out, path, pas)

    # -- connector endpoints and routing --------------------------------------
    if obj_type == "connector":
        for endpoint in ("from", "to"):
            value = out.get(endpoint)
            if isinstance(value, dict) and "object" in value and "ref" not in value:
                pas.report("connector-endpoint-object", f"{path}/{endpoint}",
                           "`object` names the target; the canonical key is `ref`")
                if pas.fix:
                    value = dict(value)
                    value["ref"] = value.pop("object")
                    out[endpoint] = value
        route = out.get("route")
        if isinstance(route, dict) and "type" in route and "kind" not in route:
            pas.report("connector-route-type", f"{path}/route",
                       "`type` reads as a discriminator; the routing mode is `kind`")
            if pas.fix:
                route = dict(route)
                route["kind"] = route.pop("type")
                out["route"] = route

    # -- a Style bundle's `dash` shorthand ------------------------------------
    if is_style and "dash" in out:
        if "stroke_dasharray" in out:
            # The model rejects the pair outright. Picking one here would make
            # the output validate while drawing a dash neither spelling asked
            # for — the worst thing a migration can do.
            pas.report("style-dash-shorthand", path,
                       f"`dash` ({out['dash']!r}) and `stroke_dasharray` "
                       f"({out['stroke_dasharray']!r}) both set; only the author knows "
                       f"which was meant",
                       automatic=False, severity="error")
        else:
            pas.report("style-dash-shorthand", path,
                       "`dash` is a shorthand for `stroke_dasharray`")
            if pas.fix:
                out["stroke_dasharray"] = out.pop("dash")

    # -- the superseded token namespace ---------------------------------------
    if key == "tokens" and isinstance(out.get("text_styles"), dict):
        out = _merge_token_styles(out, path, pas)

    # -- recurse ---------------------------------------------------------------
    is_style_map = key in _STYLE_MAPS
    for child_key, value in list(out.items()):
        if child_key in _OPAQUE:
            continue
        out[child_key] = _walk(
            value,
            f"{path}/{_escape(child_key)}",
            child_key,
            is_style_map or child_key in _STYLE_KEYS,
            pas,
        )
    return out


def _gradient_stop(stop: Any, path: str, pas: _Pass) -> Any:
    if not isinstance(stop, dict) or "offset" not in stop or "position" in stop:
        return stop
    pas.report("gradient-stop-offset", path, "`position` has been authoritative since 2.2.0")
    if not pas.fix:
        return stop
    out = dict(stop)
    value = out.pop("offset")
    # Mirrors `GradientStop._accept_offset` exactly: a 0..1 unit-interval number
    # is a fraction of the gradient line, and becomes the percentage spelling.
    out["position"] = (
        f"{value * 100:g}%" if isinstance(value, (int, float)) and not isinstance(value, bool)
        and value <= 1 else value
    )
    return out


def _split_p3_stroke(out: dict[str, Any], path: str, pas: _Pass) -> dict[str, Any]:
    """Paint into `stroke`, geometry into `stroke_style`."""
    bundle = out["stroke"]
    geometry = {_P3_GEOMETRY_TO_STYLE[k]: v
                for k, v in bundle.items() if k in _P3_GEOMETRY_TO_STYLE}
    existing = out.get("stroke_style")

    if isinstance(existing, str):
        # A string names a SHARED token. Editing it would restyle every other
        # object referencing it, so the geometry is reported rather than moved.
        pas.report(
            "stroke-single-form", path,
            f"inline stroke geometry {sorted(geometry)} alongside the named "
            f"stroke_style {existing!r}; move it into that token (or inline the "
            f"bundle) — rewriting a shared token would restyle its other users",
            automatic=False, severity="error")
        if not pas.fix:
            return out
        out = dict(out)
        if "color" in bundle:
            out["stroke"] = bundle["color"]
        else:
            out.pop("stroke", None)
        return out

    pas.report("stroke-single-form", path,
               "inline-geometry `stroke` was removed in P3: paint in `stroke`, "
               "geometry in `stroke_style`")
    if not pas.fix:
        return out

    out = dict(out)
    if "color" in bundle:
        out["stroke"] = bundle["color"]
    else:
        # A geometry-only bundle has no paint to keep; leaving the dict behind
        # would fail validation for the same reason it does today.
        out.pop("stroke", None)
    if geometry:
        # An explicit `stroke_style` is authoritative: it is the current form,
        # authored deliberately, and the legacy bundle is what is being retired.
        out["stroke_style"] = {**geometry, **existing} if isinstance(existing, dict) else geometry
    return out


def _curve_to_path(out: dict[str, Any], path: str, pas: _Pass) -> dict[str, Any]:
    """`curve`/`bezier` -> a `path` of one cubic segment."""
    if any(k in out for k in ("c1", "c2")):
        pas.report("curve-control-shorthand", path,
                   "`c1`/`c2` are short aliases of `control1`/`control2`")
    pas.report("deprecated-alias-curve", path,
               "a curve is a path of one cubic segment")
    if not pas.fix:
        return out

    out = dict(out)
    start = out.pop("from")
    end = out.pop("to")
    # The documented defaults, reproduced exactly: `control1` defaults to
    # `from`, `control2` defaults to `control1`. Anything else redraws the shape.
    c1 = out.pop("control1", None)
    if c1 is None:
        c1 = out.pop("c1", None)
    else:
        out.pop("c1", None)
    c2 = out.pop("control2", None)
    if c2 is None:
        c2 = out.pop("c2", None)
    else:
        out.pop("c2", None)
    c1 = start if c1 is None else c1
    c2 = c1 if c2 is None else c2

    out["type"] = "path"
    out["d"] = [["M", start[0], start[1]],
                ["C", c1[0], c1[1], c2[0], c2[1], end[0], end[1]]]
    return out


def _merge_token_styles(out: dict[str, Any], path: str, pas: _Pass) -> dict[str, Any]:
    """Fold `tokens.text_styles` into `tokens.styles`, the older map winning.

    Winning is not a preference: the renderer resolves `text_styles` first, so
    any other merge order silently restyles every block that used a shadowed
    name.
    """
    legacy = out["text_styles"]
    has_styles = isinstance(out.get("styles"), dict)
    current = out["styles"] if has_styles else {}
    shadowed = sorted(set(legacy) & set(current))

    if shadowed:
        pas.report(
            "tokens-text-styles", f"{path}/text_styles",
            f"{len(shadowed)} name(s) declared in BOTH `text_styles` and `styles`: "
            f"{', '.join(shadowed)}. `text_styles` resolves first, so the `styles` "
            f"definition is dead — merging keeps the one the renderer already picks",
            severity="warning")
    elif legacy:
        pas.report("tokens-text-styles", f"{path}/text_styles",
                   "`text_styles` is superseded by `styles`; two live namespaces over "
                   "one key space is a shadowing hazard waiting to happen")
    else:
        pas.report("tokens-text-styles", f"{path}/text_styles",
                   "an empty `text_styles` map — the deprecated namespace with nothing "
                   "in it; dropping the key")
    if not pas.fix:
        return out

    out = dict(out)
    merged = {**current, **legacy}
    # Don't invent a `styles` map to hold nothing: an empty legacy namespace is
    # dead weight, and replacing it with an empty current one is not progress.
    if merged or has_styles:
        out["styles"] = merged
    out.pop("text_styles")
    return out


# --------------------------------------------------------------------------- #
#  Public API                                                                 #
# --------------------------------------------------------------------------- #
def scan(document: Mapping[str, Any]) -> list[Finding]:
    """Report every deprecated form in `document`, in document order.

    Read-only and non-mutating: the document handed in comes back untouched.
    """
    pas = _Pass(fix=False)
    _walk(dict(document), "", None, False, pas)
    return list(pas.findings)


def migrate(document: Mapping[str, Any]) -> MigrationResult:
    """Rewrite every automatically-migratable deprecated form to its canonical spelling.

    The input is never mutated. Idempotent by construction: each rewrite removes
    the form it matched, so a second pass reports nothing and
    :attr:`MigrationResult.changed` is ``False``.

    Occurrences the codemod refuses to rewrite — a pre-P3 bundle beside a named
    ``stroke_style`` token, a ``dash`` contradicting an explicit
    ``stroke_dasharray`` — come back in :attr:`MigrationResult.manual` rather
    than being resolved by a guess.
    """
    pas = _Pass(fix=True)
    migrated = _walk(deepcopy(dict(document)), "", None, False, pas)
    return MigrationResult(document=migrated, findings=tuple(pas.findings))


# --------------------------------------------------------------------------- #
#  CLI                                                                        #
# --------------------------------------------------------------------------- #
def _read(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml  # optional: only YAML input needs it

        return yaml.safe_load(text)
    return json.loads(text)


def _write(path: Path, data: Any) -> None:
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml

        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                        encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")


def _print_registry() -> None:
    print(f"{len(DEPRECATIONS)} deprecated forms in the FrameForge v2 contract\n")
    for dep in DEPRECATIONS:
        status = "still valid" if dep.valid_at_head else "REJECTED at HEAD"
        print(f"  {dep.id}")
        print(f"      {dep.subject}  ->  {dep.replacement}")
        print(f"      {dep.kind}, {dep.fix} fix, {status} (engine code: {dep.code})")
        print(f"      {dep.note}\n")


def _report(path: Path, findings: Iterable[Finding], migrated: bool) -> None:
    findings = list(findings)
    if not findings:
        print(f"clean    {path.name}  (no deprecated forms)")
        return
    verb = "migrated" if migrated else "found"
    print(f"{verb:<8} {path.name}  ({len(findings)} deprecated form(s))")
    for finding in findings:
        print(f"  {finding}")
        if not finding.automatic:
            print("      ^ NOT rewritten — resolve this one by hand")


def parser() -> argparse.ArgumentParser:
    """The ``ff-codemod`` parser, built separately so a gate can read it.

    `tooling/docgates.py` introspects this to assert every flag is documented in
    README.md. Constructing the parser must therefore stay free of side effects.
    """
    ap = argparse.ArgumentParser(
        prog="ff-codemod",
        description="Report or migrate deprecated forms in a FrameForge document.")
    ap.add_argument("document", nargs="*", type=Path,
                    help="FrameForge document(s) (.json/.yaml/.yml)")
    ap.add_argument("--write", action="store_true",
                    help="rewrite each document in place (default: report only)")
    ap.add_argument("--stdout", action="store_true",
                    help="print the migrated document instead of writing it")
    ap.add_argument("--json", dest="as_json", action="store_true",
                    help="emit findings as JSON")
    ap.add_argument("--list", dest="list_registry", action="store_true",
                    help="print the deprecation registry and exit")
    return ap


def main(argv: list[str] | None = None) -> int:
    """``ff-codemod`` — find and migrate deprecated FrameForge forms.

    Exit status: ``0`` nothing left to do, ``1`` deprecated forms remain (or were
    found, in the read-only default mode), ``2`` a document could not be read.
    """
    ap = parser()
    args = ap.parse_args(argv)

    if args.list_registry:
        _print_registry()
        return 0
    if not args.document:
        ap.error("give at least one document, or --list")

    rc = 0
    payload: dict[str, Any] = {"documents": [], "findings": []}
    for path in args.document:
        try:
            data = _read(path)
        except ImportError:
            print("PyYAML is not installed; install `frameforge-api[yaml]` to migrate "
                  "YAML documents (JSON always works)", file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"could not read {path}: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:
            print(f"could not parse {path}: {exc}", file=sys.stderr)
            return 2
        if not isinstance(data, dict):
            print(f"{path}: not a FrameForge document (expected an object)", file=sys.stderr)
            return 2

        result = migrate(data)
        writing = args.write or args.stdout

        if args.stdout:
            print(json.dumps(result.document, indent=2, ensure_ascii=False))
        elif args.write and result.changed:
            _write(path, result.document)

        if args.as_json:
            payload["documents"].append(
                {"path": str(path), "changed": result.changed, "written": bool(args.write)})
            payload["findings"].extend(f.as_dict() for f in result.findings)
        elif not args.stdout:
            _report(path, result.findings, migrated=bool(args.write) and result.changed)

        # After a write, only the occurrences the codemod refused to touch are
        # still outstanding; in read-only mode everything found is outstanding.
        outstanding = result.manual if writing else result.findings
        if outstanding:
            rc = 1

    if args.as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return rc


if __name__ == "__main__":                                    # pragma: no cover
    raise SystemExit(main())
