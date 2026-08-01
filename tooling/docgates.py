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
        for phrase in (r"(\w+) entries", r"the (\w+) forms", r"all (\w+)\b"):
            for word, _window in _counted_in_registry_context(text, phrase):
                if word != _spelled(total):
                    problems.append(
                        f"{rel} says `{word}` where the registry has "
                        f"{total} entries (`{_spelled(total)}`)")

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

_DECL_COUNT = re.compile(r"\b(\d{2,4}) (?:top-level )?declarations\b")


def golden_count_problems() -> list[str]:
    """`tests/test_golden.py` quotes the size of the declaration corpus.

    The defect this catches, verbatim: two docstrings said "183 declarations"
    while the golden held 203 — the corpus grew at 2.9.0, 2.10.0 and 2.11.0 and
    the prose did not follow. Harmless on its own, and exactly the drift that
    teaches a reader to stop trusting the numbers around it.
    """
    golden = ROOT / "tests" / "golden" / "declarations.json"
    if not golden.is_file():
        return ["tests/golden/declarations.json is missing"]
    actual = len(json.loads(golden.read_text(encoding="utf-8")))

    doc = ROOT / "tests" / "test_golden.py"
    problems = []
    for found in _DECL_COUNT.findall(doc.read_text(encoding="utf-8")):
        # 183 is the corpus size at the split, named as history. Only a claim
        # about the *current* corpus can be stale.
        if int(found) not in (actual, 183):
            problems.append(
                f"tests/test_golden.py says `{found} declarations`; the golden "
                f"holds {actual}")
    if str(actual) not in doc.read_text(encoding="utf-8"):
        problems.append(
            f"tests/test_golden.py never names the current corpus size ({actual})")
    return problems


# --------------------------------------------------------------------------
# 8. Markdown link integrity
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
    ("changelog sections", changelog_problems),
    ("CLI flag coverage", cli_flag_problems),
    ("quoted counts", deprecation_count_problems),
    ("golden corpus size", golden_count_problems),
    ("markdown links", link_problems),
)
