"""Doc-vs-code gates: the checks that keep prose from drifting away from the tree.

Every function here returns a ``list[str]`` of problems — empty means the gate
passes. They are consumed twice, on purpose:

  * ``tooling/check_docs.py`` runs them all as a CLI (``make doc-check``).
  * ``tests/test_doc_gates.py`` asserts on them individually, so a plain
    ``pytest`` run catches the same drift with a per-gate failure message.

The design rule is that a gate **verifies** prose rather than **generating** it.
The docs in this repository are hand-written and the writing is worth keeping;
injecting `--help` output or a rendered tree would trade accurate prose for
accurate-but-worse prose. A gate gets the same drift protection and costs the
reader nothing.

Every gate below exists because the corresponding drift was actually observed in
this repository on 2026-08-01, not because it seemed prudent.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import frameforge_api  # noqa: E402
from frameforge_api import deprecations as _deprecations  # noqa: E402
from frameforge_api import schema as _schema  # noqa: E402

# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------


def tracked_markdown() -> list[str]:
    """Tracked ``*.md`` paths that exist on disk.

    Tracked, so untracked scratch files never fail the build. On disk, so a doc
    deleted locally does not crash a gate that is about to read it.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "*.md"],
            capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        # Not a git checkout (an sdist, a vendored copy): fall back to a walk.
        return sorted(
            str(p.relative_to(ROOT)) for p in ROOT.rglob("*.md")
            if not any(part.startswith(".") for part in p.relative_to(ROOT).parts))
    return sorted(rel for rel in out.split("\n") if rel and (ROOT / rel).is_file())


def _frontmatter(path: Path) -> str:
    """The YAML frontmatter block, or ``""`` if the file has none."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[:end] if end != -1 else ""


#: Written-out numbers, for prose that spells a count rather than digits.
_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven",
    12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
    16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen",
    20: "twenty",
}


def _spelled(n: int) -> str:
    return _WORDS.get(n, str(n))


# --------------------------------------------------------------------------
# 1. CLAUDE.md path references
# --------------------------------------------------------------------------

#: Paths CLAUDE.md names in order to assert they are ABSENT. A gate that
#: demanded these exist would invert the sentence it is checking.
CLAUDE_ASSERTED_ABSENT = {
    "lib/",            # "This project ships no FLAM reader (`lib/` does not exist)"
}

#: Bare filenames CLAUDE.md discusses as a *convention* rather than as a file
#: in this tree (the FLAM section explains what to look for, generically).
CLAUDE_CONVENTIONS = {
    "<filename>.meta.json",
    ".eslintrc", ".prettierrc", "ruff.toml", "rustfmt.toml", ".editorconfig",
    ".nvmrc", ".python-version", "rust-toolchain.toml", "go.mod",
    "package.json", "Cargo.toml", "pom.xml", "setup.py",
}

_PATHISH = re.compile(
    r"`([A-Za-z0-9_][A-Za-z0-9_./-]*"
    r"(?:/|\.py|\.md|\.json|\.yml|\.yaml|\.toml|\.cfg|\.txt|\.sh))`")


def claude_path_problems() -> list[str]:
    """Every filesystem path CLAUDE.md names must exist.

    The defect this catches, verbatim: `CLAUDE.md` was copied from the
    `frameforge` monorepo when this package was extracted and all fifteen paths
    it named — `src/frameforge/model.py`, `tooling/`, `docs/schema/`,
    `tests/fixtures/b1/`, `AGENTS.md`, `PURPOSE.md`, `mkdocs.yml` … — described
    a tree this repository does not have. The file agents are required to read
    first was the least accurate document in the repo.
    """
    doc = ROOT / "CLAUDE.md"
    if not doc.is_file():
        return ["CLAUDE.md is missing"]
    text = doc.read_text(encoding="utf-8")

    named = {m for m in _PATHISH.findall(text)}
    named -= CLAUDE_ASSERTED_ABSENT | CLAUDE_CONVENTIONS
    missing = sorted(p for p in named if not (ROOT / p).exists())

    problems = [
        f"CLAUDE.md names `{p}`, which does not exist in this repository"
        for p in missing
    ]
    # The other direction: a path asserted absent must really be absent, or the
    # sentence around it has quietly become false.
    problems += [
        f"CLAUDE.md says `{p}` does not exist, but it does"
        for p in sorted(CLAUDE_ASSERTED_ABSENT) if (ROOT / p).exists()
    ]
    return problems


# --------------------------------------------------------------------------
# 2. Rule-5 disclaimer frontmatter
# --------------------------------------------------------------------------

#: Docs that do not carry the rule-5 block, each for a stated reason. Adding a
#: file here is the supported escape hatch; weakening the check is not.
DISCLAIMER_EXEMPT = {
    "README.md": "usage front door, not an authored analysis",
    "CHANGELOG.md": "release log (governance)",
    "CLAUDE.md": "the agent operating guide itself (governance)",
    "MIGRATION.md": "consumer-facing upgrade instructions, a product doc",
}


def disclaimer_problems() -> list[str]:
    """Every non-exempt tracked ``*.md`` carries ``disclaimer:`` frontmatter.

    This is CLAUDE.md Behavioural Constraint 5. Before this gate existed the
    rule was policy with no enforcement in this repository — the script it named
    (`tooling/check_disclaimers.py`) lived in the monorepo — and two docs under
    `docs/` had silently shipped without the block.
    """
    problems = []
    for rel in tracked_markdown():
        if rel in DISCLAIMER_EXEMPT or Path(rel).name == "README.md":
            continue
        if "disclaimer:" not in _frontmatter(ROOT / rel):
            problems.append(
                f"{rel} is missing the rule-5 `disclaimer:` frontmatter "
                f"(add the block, or add the file to DISCLAIMER_EXEMPT in "
                f"tooling/docgates.py with a reason)")
    return problems


# --------------------------------------------------------------------------
# 3. Version literals
# --------------------------------------------------------------------------

#: Files whose `HEAD_VERSION` mentions must name the CURRENT contract revision.
#:
#: CHANGELOG.md and MIGRATION.md are deliberately absent: both are historical
#: records and correctly name superseded revisions (`2.8.2`, `2.9.0`, `2.10.0`).
#: model/version.py is absent for the same reason — its comment narrates the
#: revision history.
VERSION_SCOPE = (
    "README.md",
    "CLAUDE.md",
    "pyproject.toml",
    "src/frameforge_api/__init__.py",
)

_HEAD_NEARBY = re.compile(
    r"HEAD_VERSION[^\n]{0,80}?`{0,2}(\d+\.\d+(?:\.\d+|\.x))`{0,2}")

#: Any 2.x contract revision literal, anywhere. Used only for the
#: "not ahead of HEAD" invariant, which needs no proximity window.
_ANY_2X = re.compile(r"\b(2\.\d+\.\d+)\b")

#: Files swept for future revisions. CHANGELOG and MIGRATION are included here
#: (unlike in VERSION_SCOPE) because naming a revision that does not exist is
#: wrong even in a historical record — history cannot run ahead of HEAD.
_NO_FUTURE_REVISION_SCOPE = (
    "README.md", "CLAUDE.md", "MIGRATION.md", "CHANGELOG.md",
    "pyproject.toml", "src/frameforge_api/__init__.py",
)


def version_literal_problems() -> list[str]:
    """A version literal written next to `HEAD_VERSION` must be the real one.

    The defect this catches, verbatim: `pyproject.toml` and
    `src/frameforge_api/__init__.py` both documented `HEAD_VERSION` as `2.8.x`
    while it was `2.11.0` — three contract revisions stale. Both were *comments*,
    so no schema gate and no test saw them.
    """
    head = frameforge_api.HEAD_VERSION
    problems = []
    for rel in VERSION_SCOPE:
        path = ROOT / rel
        if not path.is_file():
            problems.append(f"{rel} is in VERSION_SCOPE but does not exist")
            continue
        for found in _HEAD_NEARBY.findall(path.read_text(encoding="utf-8")):
            if found != head:
                problems.append(
                    f"{rel} names HEAD_VERSION as `{found}`; it is `{head}`")

    # The window above only sees literals written within 80 characters after the
    # token `HEAD_VERSION`, which is most of them and not all. This second sweep
    # needs no window because it checks an invariant that holds everywhere: no
    # document may name a 2.x revision that does not exist yet. A stale literal
    # is a judgement call about context; a FUTURE one is always wrong.
    for rel in _NO_FUTURE_REVISION_SCOPE:
        path = ROOT / rel
        if not path.is_file():
            continue
        for found in _ANY_2X.findall(path.read_text(encoding="utf-8")):
            if _precedence(found) > _precedence(head):
                problems.append(
                    f"{rel} names contract revision `{found}`, which is ahead of "
                    f"HEAD_VERSION `{head}` — that revision does not exist")
    return problems


def package_version_problems() -> list[str]:
    """`pyproject.toml`'s version and `__version__` are the same number."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    if not m:
        return ["pyproject.toml has no [project] version"]
    if m.group(1) != frameforge_api.__version__:
        return [f"pyproject.toml says version `{m.group(1)}` but "
                f"frameforge_api.__version__ is `{frameforge_api.__version__}`"]
    return []


def _precedence(version: str) -> tuple[int, ...]:
    """`(major, minor, patch)` for ordering. NEVER compare these as strings.

    `"2.2.0" < "2.10.0"` is False lexicographically — `'2'` sorts after `'1'`.
    MIGRATION.md warns consumers about exactly this trap, so a gate over
    MIGRATION.md that fell into it would be its own punchline.
    """
    return tuple(int(p) for p in version.split("."))


#: Headings whose contents make PRESENT-TENSE claims about the shipped package.
#: Everything else in MIGRATION.md is a historical record and correctly names
#: superseded revisions, which is why the file as a whole stays out of
#: VERSION_SCOPE.
_CURRENT_STATE_SECTIONS = ("## Upgrading", "## Rollback")

_PIN = re.compile(r"frameforge-api>=(\d+\.\d+(?:\.\d+)?)(?:,<(\d+\.\d+(?:\.\d+)?))?")


def _section(text: str, heading: str) -> str:
    """The body under `heading`, up to the next `##`."""
    start = text.find(heading)
    if start == -1:
        return ""
    nxt = text.find("\n## ", start + len(heading))
    return text[start:nxt if nxt != -1 else len(text)]


def migration_currency_problems() -> list[str]:
    """MIGRATION.md's present-tense claims match the shipped package.

    The defect this catches, verbatim: the `## Upgrading` section said the
    package was `1.1.0` and the contract `2.10.0`, and told consumers to
    `pip install "frameforge-api>=1.1"`, while the package was `1.2.0` and the
    contract `2.11.0`. The `## Rollback` section pinned `>=1.0,<1.1` — a range
    that **excludes the release the same document tells you to install**, and
    that resolves to a wheel with no `ff-codemod` in it.

    Those sections were written for 1.1.0 and carried through two package minors.
    MIGRATION.md is deliberately outside `VERSION_SCOPE` because most of it is
    history; this gate covers only the parts that claim to describe *now*.
    """
    text = (ROOT / "MIGRATION.md").read_text(encoding="utf-8")
    version = frameforge_api.__version__
    head = frameforge_api.HEAD_VERSION
    problems = []

    upgrading = _section(text, "## Upgrading")
    if not upgrading:
        return ["MIGRATION.md has no `## Upgrading` section to check"]

    # The install pin must actually admit the shipped version.
    for lower, upper in _PIN.findall(upgrading):
        if _precedence(version) < _precedence(lower):
            problems.append(
                f"MIGRATION.md `## Upgrading` tells consumers to install "
                f"frameforge-api>={lower}, which excludes the shipped {version}")
        if upper and _precedence(version) >= _precedence(upper):
            problems.append(
                f"MIGRATION.md `## Upgrading` pins <{upper}, which excludes the "
                f"shipped {version}")

    # The bolded package/contract literals must be the current ones.
    for literal in re.findall(r"\*\*(\d+\.\d+\.\d+)\*\*", upgrading):
        if literal not in (version, head):
            problems.append(
                f"MIGRATION.md `## Upgrading` states **{literal}**; the package "
                f"is {version} and the contract is {head}")
    if f"**{version}**" not in upgrading:
        problems.append(
            f"MIGRATION.md `## Upgrading` never names the shipped package "
            f"version ({version})")
    if f"**{head}**" not in upgrading:
        problems.append(
            f"MIGRATION.md `## Upgrading` never names the current contract "
            f"revision ({head})")

    # Rollback ranges are allowed to exclude the current version — that is what
    # rolling back means — but the lower bound must still be a real release.
    for lower, _upper in _PIN.findall(_section(text, "## Rollback")):
        if _precedence(lower) > _precedence(version):
            problems.append(
                f"MIGRATION.md `## Rollback` pins >={lower}, which is ahead of "
                f"the shipped {version}")
    return problems


#: A row of the deprecation table in MIGRATION.md:
#: `| id | form | becomes | valid at HEAD |`
_TABLE_ROW = re.compile(r"^\|\s*`([a-z0-9-]+)`\s*\|(.+?)\|(.+?)\|(.+?)\|\s*$", re.MULTILINE)

#: Parenthetical asides in a `replacement` string — "(paint)", "(closed: true)".
#: They are commentary, not identifiers a table row has to repeat.
_ASIDE = re.compile(r"\([^)]*\)")


def _replacement_identifiers(replacement: str) -> set[str]:
    """The names a table row must mention for it to be describing this entry.

    `Style.stroke_dasharray` -> {"stroke_dasharray"}: the class prefix is the
    registry's addressing, and the table names the field. `stroke (paint) +
    stroke_style (geometry)` -> {"stroke", "stroke_style"}: the asides are prose.
    """
    cleaned = _ASIDE.sub(" ", replacement)
    out = set()
    for part in re.split(r"[/+,]", cleaned):
        part = part.strip()
        if not part:
            continue
        # `tokens.styles` is a path the table repeats verbatim; `Style.dash` is
        # a class-qualified field where only the field is repeated. Keep the
        # last segment either way — it is present in both spellings.
        out.add(part.split(".")[-1])
    return {o for o in out if o}


def migration_table_problems() -> list[str]:
    """The deprecation table in MIGRATION.md is a checked projection of the registry.

    The defect this catches: the existing guard
    (`test_every_deprecation_is_documented_for_a_human_too`) asserts each `id`
    appears *somewhere* in the file — row existence, not row content. Changing an
    entry's `replacement`, or flipping its `valid_at_head`, leaves the id present
    and the test green while the published table tells a consumer the opposite of
    what `ff-codemod --list` prints.

    `valid at HEAD` is the column the document itself calls "the field to branch
    on", so a stale **no** -> **yes** there is advice to ignore a form that will
    in fact refuse to load.
    """
    text = (ROOT / "MIGRATION.md").read_text(encoding="utf-8")
    rows = {m.group(1): (m.group(3), m.group(4))
            for m in _TABLE_ROW.finditer(text)}
    by_id = {d.id: d for d in frameforge_api.DEPRECATIONS}

    problems = []
    missing = sorted(set(by_id) - set(rows))
    if missing:
        problems.append(
            f"MIGRATION.md's deprecation table has no row for: {missing}")
    unknown = sorted(set(rows) - set(by_id))
    if unknown:
        problems.append(
            f"MIGRATION.md's deprecation table has rows for entries not in the "
            f"registry: {unknown}")

    for dep_id, (becomes, valid_cell) in rows.items():
        dep = by_id.get(dep_id)
        if dep is None:
            continue

        for name in _replacement_identifiers(dep.replacement):
            if name not in becomes:
                problems.append(
                    f"MIGRATION.md row `{dep_id}`: the registry replacement is "
                    f"`{dep.replacement}` but the 'becomes' cell "
                    f"({becomes.strip()!r}) does not mention `{name}`")

        says_yes = "yes" in valid_cell.lower()
        says_no = "no" in valid_cell.lower()
        if says_yes == says_no:
            problems.append(
                f"MIGRATION.md row `{dep_id}`: cannot read the 'valid at HEAD' "
                f"cell ({valid_cell.strip()!r}) as yes or no")
        elif says_yes is not dep.valid_at_head:
            problems.append(
                f"MIGRATION.md row `{dep_id}`: the table says valid at HEAD = "
                f"{'yes' if says_yes else 'no'}, the registry says "
                f"{dep.valid_at_head}. This is the column consumers branch on.")
    return problems


# --------------------------------------------------------------------------
# 4. CHANGELOG sectioning
# --------------------------------------------------------------------------

_CHANGELOG_HEADING = re.compile(r"^## (\d+\.\d+\.\d+)", re.MULTILINE)


def changelog_problems() -> list[str]:
    """The current package version has its own CHANGELOG section.

    The defect this catches, verbatim: `pyproject.toml` read `1.2.0` while every
    post-1.0.0 entry still sat under `## Unreleased`, the only git tag was
    `v1.0.0`, and a `1.1.0` wheel had been built from a state that was never
    committed. The release existed as an artifact and nowhere else.
    """
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    versions = _CHANGELOG_HEADING.findall(text)
    current = frameforge_api.__version__
    problems = []
    if current not in versions:
        problems.append(
            f"CHANGELOG.md has no `## {current}` section, but that is the "
            f"version in pyproject.toml (sections found: "
            f"{', '.join(versions) or 'none'}). Cut the section before "
            f"releasing, or move the bump back to `## Unreleased`.")
    # The mirror image, which the original gate let through: a section for a
    # release that does not exist yet. A reader believes it shipped; pip
    # disagrees. Unreleased work belongs under `## Unreleased`.
    ahead = [v for v in versions if _precedence(v) > _precedence(current)]
    if ahead:
        problems.append(
            f"CHANGELOG.md documents {', '.join(ahead)} as released, but the "
            f"shipped version is {current}. Bump pyproject.toml, or move those "
            f"sections back under `## Unreleased`.")
    return problems


# --------------------------------------------------------------------------
# 5. CLI flag completeness
# --------------------------------------------------------------------------


def _option_strings(parser) -> list[str]:
    out = []
    # `_actions` is private, but argparse exposes no public way to enumerate a
    # parser's options, and the alternative — parsing `--help` output — is a
    # worse dependency on an even less stable surface.
    for action in parser._actions:
        for opt in action.option_strings:
            if opt not in ("-h", "--help"):
                out.append(opt)
    return sorted(set(out))


def cli_flag_problems() -> list[str]:
    """Every flag either console script accepts appears in README.md.

    The defect this catches, verbatim: `ff-schema --out` and `ff-codemod
    --stdout` both shipped without appearing in any user-facing doc. Nothing
    failed, because nothing was looking.
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    problems = []
    for prog, parser in (("ff-schema", _schema.parser()),
                         ("ff-codemod", _deprecations.parser())):
        for flag in _option_strings(parser):
            if flag not in readme:
                problems.append(
                    f"`{prog} {flag}` exists in the parser but is not "
                    f"documented in README.md")
    return problems


# --------------------------------------------------------------------------
# 6. Counts quoted in prose
# --------------------------------------------------------------------------


#: How far either side of a number word to look for evidence that the number is
#: about the deprecation registry. Wide enough to span a sentence, narrow enough
#: that an unrelated count in the next paragraph is not dragged in.
_CONTEXT = 160

_REGISTRY_CONTEXT = re.compile(r"deprecat|registry|codemod", re.IGNORECASE)


def _counted_in_registry_context(text: str, phrase: str) -> list[tuple[str, str]]:
    """(number-word, surrounding text) for `phrase` matches that are about the
    deprecation registry.

    Scoping matters: README also says "all four" of the 2.9.0 additions and
    MIGRATION says "all seven" elsewhere. Neither is a registry count, and a
    gate that flagged them would be noise the next reader learns to ignore.
    """
    out = []
    for m in re.finditer(phrase, text):
        word = m.group(1)
        if word not in _WORDS.values():
            continue
        window = text[max(0, m.start() - _CONTEXT):m.end() + _CONTEXT]
        if _REGISTRY_CONTEXT.search(window):
            out.append((word, window))
    return out


def deprecation_count_problems() -> list[str]:
    """The registry sizes README.md and MIGRATION.md quote are the real ones.

    README says the registry holds "eleven entries", that "nine forms still
    parse" and that two are rejected. Those are hand-written numbers over a list
    that is meant to grow, and nothing failed when they disagreed.
    """
    total = len(frameforge_api.DEPRECATIONS)
    invalid = [d for d in frameforge_api.DEPRECATIONS if not d.valid_at_head]
    valid = total - len(invalid)

    problems = []
    for rel in ("README.md", "MIGRATION.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")

        # Totals: "eleven entries", "the eleven forms", "all eleven".
        for phrase in (r"(\w+) entries", r"the (\w+) forms", r"all (\w+)\b",
                       r"(\w+) deprecated forms", r"(\w+) registry entries",
                       r"(\w+) deprecations\b"):
            for word, _window in _counted_in_registry_context(text, phrase):
                if word != _spelled(total):
                    problems.append(
                        f"{rel} says `{word}` where the registry has "
                        f"{total} entries (`{_spelled(total)}`)")

        # The same claims written as digits. Prose in this repo spells small
        # numbers out, but nothing enforces that, and "11 entries" drifting to
        # "12 entries" is the identical defect in a spelling the word-form
        # patterns above cannot see.
        for phrase in (r"\b(\d{1,3}) entries", r"\b(\d{1,3}) deprecated forms",
                       r"\b(\d{1,3}) deprecations\b", r"\bthe (\d{1,3}) forms"):
            for m in re.finditer(phrase, text):
                window = text[max(0, m.start() - _CONTEXT):m.end() + _CONTEXT]
                if _REGISTRY_CONTEXT.search(window) and int(m.group(1)) != total:
                    problems.append(
                        f"{rel} says `{m.group(1)}` where the registry has "
                        f"{total} entries")

        # The split: "nine forms still parse, two … are rejected".
        m = re.search(r"(\w+) forms? still parse", text)
        if m and m.group(1) != _spelled(valid):
            problems.append(
                f"{rel} says `{m.group(1)} forms still parse`; "
                f"{valid} are valid at head (`{_spelled(valid)}`)")

    # The rejected forms are named in prose; if the set changes, so must they.
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for dep in invalid:
        if dep.id not in readme:
            problems.append(
                f"README.md does not name `{dep.id}`, which is rejected at head")
    return problems


# --------------------------------------------------------------------------
# 7. Counts quoted in test prose
# --------------------------------------------------------------------------

def _golden_facts() -> dict[str, int]:
    """The figures the test docstrings narrate, read from the goldens."""
    gold = ROOT / "tests" / "golden"
    behaviour = json.loads((gold / "behaviour.json").read_text(encoding="utf-8"))
    accepted = sum(1 for v in behaviour.values() if v["valid"])
    return {
        "declarations": len(json.loads(
            (gold / "declarations.json").read_text(encoding="utf-8"))),
        "defs": len(json.loads(
            (gold / "schema.json").read_text(encoding="utf-8"))["$defs"]),
        "probes": len(behaviour),
        "accepted": accepted,
        "rejected": len(behaviour) - accepted,
    }


#: (regex over the prose, key into `_golden_facts()`, historical values that are
#: named deliberately as history rather than as a current claim).
#:
#: The historical allowlist is what lets a docstring say "183 at the split and
#: 203 today" without the gate treating the first number as drift. Every entry
#: is a t0 figure recorded in `CHANGELOG.md` 1.0.0.
_NARRATED_COUNTS = (
    (re.compile(r"\b(\d{2,4}) (?:top-level )?declarations\b"), "declarations", {183}),
    (re.compile(r"\b(\d{2,4}) `?\$defs`?"), "defs", {105}),
    (re.compile(r"\b(\d{2,4}) probes\b"), "probes", {36}),
    (re.compile(r"\b(\d{2,4}) that must be ACCEPTED\b"), "accepted", {14}),
    (re.compile(r"\b(\d{2,4}) that must be REJECTED\b"), "rejected", {22}),
)

#: Modules whose prose narrates the golden corpus.
_NARRATING_MODULES = ("tests/test_golden.py", "tests/test_contract.py")


def golden_count_problems() -> list[str]:
    """The figures the test suite narrates match the goldens it is describing.

    The defect this catches, verbatim: five figures across two modules were
    stale by 11-180%. Two docstrings said "183 declarations" while the golden
    held 203; one said "105 `$defs`" against 119; one said "36 probes: 14
    ACCEPTED ... 22 REJECTED" against 102: 45 and 57. The contract had grown
    through three revisions and the prose still described t0.

    These docstrings are the primary explanation of *why* the golden suite
    exists and *what* it covers. A reader reconciling "36 probes" against a
    102-entry `behaviour.json` has to decide which to believe, and the natural
    conclusion — that the goldens were regenerated carelessly — is the opposite
    of what happened.

    The adjacent *assertions* are deliberately loose (`>= 100`), which is right:
    the exact sets are already pinned byte-for-byte by the goldens themselves.
    It is the narrated figures that were unowned.
    """
    facts = _golden_facts()
    problems = []
    for rel in _NARRATING_MODULES:
        path = ROOT / rel
        if not path.is_file():
            problems.append(f"{rel} is in _NARRATING_MODULES but does not exist")
            continue
        text = path.read_text(encoding="utf-8")
        for pattern, key, historical in _NARRATED_COUNTS:
            for found in pattern.findall(text):
                if int(found) != facts[key] and int(found) not in historical:
                    problems.append(
                        f"{rel} narrates `{found}` {key}; the golden holds "
                        f"{facts[key]}")

    # A module may legitimately narrate none of these, but `test_golden.py`
    # describes all four lenses — if it stops naming the current figures at all,
    # the numbers were deleted rather than corrected and the gate would go quiet.
    golden_text = (ROOT / "tests" / "test_golden.py").read_text(encoding="utf-8")
    for key in ("declarations", "probes"):
        if str(facts[key]) not in golden_text:
            problems.append(
                f"tests/test_golden.py never names the current {key} count "
                f"({facts[key]})")
    return problems


# --------------------------------------------------------------------------
# 8. CI runs the Makefile rather than restating it
# --------------------------------------------------------------------------

_MAKE_TARGET = re.compile(r"^([a-z][a-z-]*):", re.MULTILINE)
_RUN_STEP = re.compile(r"^\s*run:\s*(.+?)$", re.MULTILINE)

#: Commands a workflow step may run without going through the Makefile. These
#: are environment setup and reporting, not gates — putting them in the Makefile
#: would mean the Makefile knew about GitHub Actions.
_CI_ALLOWED = (
    "uv python install",     # interpreter provisioning, matrix-specific
    "uv sync",               # environment setup
    "echo",                  # step summaries and annotations
    "ours=",                 # the fidelity workflow's revision report
    "skipped=",              # the fidelity workflow's skip-count assertion
)

#: Workflows whose gate steps must invoke Makefile targets.
_GATED_WORKFLOWS = (".github/workflows/ci.yml",)


def ci_mirrors_the_makefile_problems() -> list[str]:
    """Every gate CI runs is a Makefile target, not a re-spelling of one.

    The defect this catches: `ci.yml` listed four steps that restated
    `make check`'s command line by command line — `uv run ff-schema --check`,
    `uv run python tooling/check_docs.py`, and so on. The two lists agreed on the
    day they were written and nothing kept them agreeing. Adding a fifth gate to
    the Makefile left CI running the old four, so the new gate protected only
    whoever remembered to type `make check` — which is the exact hole the CI
    workflow was written to close, re-created for every gate added after it.

    The mirror ran the other way too: the wheel-contents assertion existed only
    in CI, so `make check` could not catch a broken `force-include`. It is
    `make build-check` now.
    """
    makefile = ROOT / "Makefile"
    if not makefile.is_file():
        return ["Makefile is missing"]
    targets = set(_MAKE_TARGET.findall(makefile.read_text(encoding="utf-8")))

    problems = []
    for rel in _GATED_WORKFLOWS:
        path = ROOT / rel
        if not path.is_file():
            problems.append(f"{rel} is in _GATED_WORKFLOWS but does not exist")
            continue
        for raw in _RUN_STEP.findall(path.read_text(encoding="utf-8")):
            command = raw.strip().strip("|").strip()
            if not command or command.startswith(("|", ">")):
                continue
            if command.startswith(_CI_ALLOWED):
                continue
            if not command.startswith("make "):
                problems.append(
                    f"{rel} runs `{command}` directly. Gate commands belong to "
                    f"the Makefile — add a target and call `make <target>`, so "
                    f"CI and a developer laptop cannot run different things.")
                continue
            target = command.split()[1]
            if target not in targets:
                problems.append(
                    f"{rel} runs `make {target}`, which is not a target in the "
                    f"Makefile (targets: {', '.join(sorted(targets))})")

    # The other direction: every gate in `make check` must actually be reached by
    # CI. A target that exists and is never invoked is a gate nobody runs.
    ci = (ROOT / _GATED_WORKFLOWS[0]).read_text(encoding="utf-8")
    check_line = re.search(r"^check:\s*(.+?)(?:\s*##|$)",
                           makefile.read_text(encoding="utf-8"), re.MULTILINE)
    if check_line:
        for dep in check_line.group(1).split():
            if f"make {dep}" not in ci:
                problems.append(
                    f"`make check` depends on `{dep}`, but {_GATED_WORKFLOWS[0]} "
                    f"never invokes it — that gate would run only on a laptop.")
    return problems


# --------------------------------------------------------------------------
# 9. Python support: manifest vs CI matrix vs lint target
# --------------------------------------------------------------------------

_REQUIRES_PYTHON = re.compile(r'^requires-python\s*=\s*"[><=~!]*(\d+\.\d+)"', re.MULTILINE)
_CLASSIFIER_PY = re.compile(r'"Programming Language :: Python :: (\d+\.\d+)"')
_MATRIX_PY = re.compile(r'python-version:\s*\[([^\]]+)\]')
_RUFF_TARGET = re.compile(r'^target-version\s*=\s*"py(\d)(\d+)"', re.MULTILINE)


def python_support_problems() -> list[str]:
    """The Pythons the package claims, tests and lints for are the same set.

    The defect this catches, verbatim: the trove classifiers advertised 3.10,
    3.11 and 3.12 while the CI matrix tested 3.10 and **3.13**. The package was
    being tested on an interpreter it did not claim to support, and advertising
    two it never ran. Nothing compared the two lists.

    Three sources have to agree:
      * `requires-python` — the floor, enforced by pip at install time;
      * the trove classifiers — what PyPI displays;
      * the CI matrix — what is actually executed.

    The matrix is deliberately allowed to be a *subset* of the classifiers:
    testing the floor and the ceiling catches the version-dependent breakage
    that 1.3.1 shipped, and testing every point release in between costs minutes
    to prove nothing. What it may not do is test a version the package does not
    claim, or skip the floor.
    """
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    ci_path = ROOT / ".github" / "workflows" / "ci.yml"
    if not ci_path.is_file():
        return [".github/workflows/ci.yml is missing"]
    ci = ci_path.read_text(encoding="utf-8")

    floor_m = _REQUIRES_PYTHON.search(pyproject)
    if not floor_m:
        return ["pyproject.toml has no parseable requires-python"]
    floor = floor_m.group(1)

    classifiers = set(_CLASSIFIER_PY.findall(pyproject)) - {"3"}
    matrix_m = _MATRIX_PY.search(ci)
    if not matrix_m:
        return ["ci.yml has no parseable python-version matrix"]
    matrix = {v.strip().strip('"\'') for v in matrix_m.group(1).split(",")}

    problems = []
    for version in sorted(matrix - classifiers):
        problems.append(
            f"CI tests Python {version} but pyproject.toml has no "
            f'"Programming Language :: Python :: {version}" classifier — the '
            f"package is tested on an interpreter it does not claim to support")
    if floor not in matrix:
        problems.append(
            f"requires-python floor is {floor} but the CI matrix "
            f"({sorted(matrix)}) does not test it — the oldest supported "
            f"interpreter is the one most likely to break")
    for version in sorted(classifiers):
        if _precedence(version) < _precedence(floor):
            problems.append(
                f"pyproject.toml claims Python {version} but requires-python "
                f"is >={floor}; pip would refuse to install there")

    ruff_m = _RUFF_TARGET.search(pyproject)
    if ruff_m:
        target = f"{ruff_m.group(1)}.{ruff_m.group(2)}"
        if target != floor:
            problems.append(
                f"ruff target-version is py{ruff_m.group(1)}{ruff_m.group(2)} "
                f"({target}) but requires-python floor is {floor}; lint would "
                f"allow syntax the floor cannot parse")
    return problems


# --------------------------------------------------------------------------
# 10. Packaging: the schema path the code reads vs the one the wheel ships
# --------------------------------------------------------------------------

_FORCE_INCLUDE = re.compile(
    r'^\s*"([^"]+)"\s*=\s*"([^"]+)"', re.MULTILINE)


def packaging_path_problems() -> list[str]:
    """`SCHEMA_PATH` and the wheel's `force-include` mapping name one file.

    `frameforge_api.schema.SCHEMA_PATH` is where the code looks for the shipped
    schema at runtime. The `[tool.hatch.build.targets.wheel.force-include]`
    stanza declares where the build puts it. They are two spellings of the same
    location, written by hand in two files.

    If they diverge, the wheel builds, imports and passes every other gate; the
    only symptom is `load_schema()` raising FileNotFoundError for a consumer who
    installed from PyPI — never for a developer running from a source checkout,
    where the file is found regardless.
    """
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = pyproject.split("[tool.hatch.build.targets.wheel.force-include]")
    if len(section) < 2:
        # No force-include is legitimate — hatchling ships everything under the
        # packaged directory anyway. Then there is nothing to disagree.
        return []
    body = section[1].split("\n[", 1)[0]

    # Where the runtime expects the file, relative to the package directory.
    from frameforge_api import schema as schema_module
    package_root = Path(schema_module.__file__).parent
    runtime_rel = schema_module.SCHEMA_PATH.relative_to(package_root.parent)

    problems = []
    mapped = dict(_FORCE_INCLUDE.findall(body))
    if not mapped:
        return ["force-include stanza present but no mappings parsed from it"]

    for source in mapped:
        if not (ROOT / source).is_file():
            problems.append(
                f"pyproject.toml force-includes `{source}`, which does not exist")
    if str(runtime_rel) not in mapped.values():
        problems.append(
            f"SCHEMA_PATH resolves to `{runtime_rel}` inside the wheel, but the "
            f"force-include stanza maps to {sorted(mapped.values())}. A consumer "
            f"installing from PyPI would not find the schema where the code looks.")
    return problems


# --------------------------------------------------------------------------
# 11. CLAUDE.md's gate table vs the Makefile
# --------------------------------------------------------------------------

_MAKE_MENTION = re.compile(r"`make ([a-z][a-z-]*)`")
_DOCUMENTED_TARGET = re.compile(r"^([a-z][a-z-]*):.*?##", re.MULTILINE)

#: Targets deliberately absent from CLAUDE.md's gate table. `help` documents
#: itself; `sync`, `build`, `goldens` and `schema` are described in prose
#: elsewhere in the file rather than as gates.
_GATE_TABLE_EXEMPT = {"help", "sync", "build", "goldens", "schema", "clean"}


def claude_gate_table_problems() -> list[str]:
    """CLAUDE.md's gate table names every gate, and only real ones.

    The path gate covers backticked *paths*; this covers the other half of
    CLAUDE.md that restates the tree — the table telling an agent which commands
    constitute "done". An agent that runs the documented gates and misses one
    added later reports success it did not earn.
    """
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    real = set(_MAKE_TARGET.findall(makefile))
    documented_targets = set(_DOCUMENTED_TARGET.findall(makefile))
    mentioned = set(_MAKE_MENTION.findall(claude))

    problems = []
    for target in sorted(mentioned - real):
        problems.append(
            f"CLAUDE.md tells an agent to run `make {target}`, which is not a "
            f"Makefile target")
    for target in sorted(documented_targets - mentioned - _GATE_TABLE_EXEMPT):
        problems.append(
            f"Makefile documents `{target}` but CLAUDE.md never mentions it — an "
            f"agent following CLAUDE.md would skip that gate. Add it to the gate "
            f"table, or to _GATE_TABLE_EXEMPT with a reason.")
    return problems


# --------------------------------------------------------------------------
# 12. The font-closure boundary doc vs the model
# --------------------------------------------------------------------------

_FONTDEF_FIELD = re.compile(r"`FontDef\.([a-z_]+)`")

#: Fields the boundary doc asserts are NOT on Document. The whole point of the
#: document is that these are runtime configuration, not serialised contract.
_NOT_DOCUMENT_FIELDS = ("font_closure", "font_generics")


def font_boundary_problems() -> list[str]:
    """`docs/runtime-font-closure-boundary.md` describes the real FontDef.

    Its ownership table names the exact fields that carry document-side font
    identity, and asserts two names are absent from the contract. Both halves
    are hand-written against a model that can change underneath them: renaming
    `FontDef.hash` would leave the published boundary document describing a
    field nobody can set.
    """
    doc_path = ROOT / "docs" / "runtime-font-closure-boundary.md"
    if not doc_path.is_file():
        return ["docs/runtime-font-closure-boundary.md is missing"]
    text = doc_path.read_text(encoding="utf-8")

    from frameforge_api.model import Document, FontDef
    real = set(FontDef.model_fields)

    problems = []
    named = set(_FONTDEF_FIELD.findall(text))
    for field in sorted(named - real):
        problems.append(
            f"the font-closure doc names `FontDef.{field}`, which is not a "
            f"FontDef field (real fields: {sorted(real)})")
    # The table claims to cover family, src and the content pin. If one of those
    # stops being named, the doc has quietly narrowed.
    for required in ("family", "src", "hash"):
        if required in real and required not in named:
            problems.append(
                f"the font-closure doc no longer names `FontDef.{required}`, "
                f"which it exists to describe")

    for absent in _NOT_DOCUMENT_FIELDS:
        if absent in Document.model_fields:
            problems.append(
                f"the font-closure doc asserts `{absent}` is not a Document "
                f"field, but it is now — the boundary moved and the doc did not")
    return problems


# --------------------------------------------------------------------------
# 13. Markdown link integrity
# --------------------------------------------------------------------------

_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def link_problems() -> list[str]:
    """Relative links in tracked docs resolve to something on disk.

    The defect this catches, verbatim: `CLAUDE.md` linked to `PURPOSE.md`, which
    exists in the monorepo and not here.
    """
    problems = []
    for rel in tracked_markdown():
        doc = ROOT / rel
        for target in _LINK.findall(doc.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path = target.split("#", 1)[0]
            if not path:
                continue
            if not (doc.parent / path).exists():
                problems.append(f"{rel} links to `{target}`, which does not exist")
    return problems


# --------------------------------------------------------------------------
# the suite
# --------------------------------------------------------------------------

GATES = (
    ("CLAUDE.md paths", claude_path_problems),
    ("disclaimer frontmatter", disclaimer_problems),
    ("version literals", version_literal_problems),
    ("package version", package_version_problems),
    ("MIGRATION.md currency", migration_currency_problems),
    ("MIGRATION.md deprecation table", migration_table_problems),
    ("changelog sections", changelog_problems),
    ("CLI flag coverage", cli_flag_problems),
    ("quoted counts", deprecation_count_problems),
    ("golden corpus size", golden_count_problems),
    ("python support", python_support_problems),
    ("packaging paths", packaging_path_problems),
    ("CLAUDE.md gate table", claude_gate_table_problems),
    ("font-closure boundary", font_boundary_problems),
    ("CI mirrors the Makefile", ci_mirrors_the_makefile_problems),
    ("markdown links", link_problems),
)
