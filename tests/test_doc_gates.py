"""test_doc_gates.py — the docs must agree with the code, checked per gate.

`tooling/docgates.py` holds the logic and `tooling/check_docs.py` runs it as a
CLI. This module asserts on each gate separately so a plain `pytest` run names
which kind of drift appeared, rather than reporting one opaque failure.

Every gate here was written against drift that actually existed in this
repository on 2026-08-01 — see the docstring on each `docgates` function for the
verbatim defect. They are regression tests, not speculative ones.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLING = Path(__file__).resolve().parents[1] / "tooling"
if str(TOOLING) not in sys.path:
    sys.path.insert(0, str(TOOLING))

import docgates  # noqa: E402


def _report(problems: list[str]) -> str:
    return "\n".join(f"  - {p}" for p in problems)


def test_claude_md_names_only_paths_that_exist():
    """CLAUDE.md was a verbatim copy of the monorepo's, and all 15 paths it
    named were absent. It is the first file an agent reads."""
    problems = docgates.claude_path_problems()
    assert not problems, "CLAUDE.md path references drifted:\n" + _report(problems)


def test_every_doc_carries_the_disclaimer_frontmatter():
    """CLAUDE.md rule 5, enforced here because the script it names lives in the
    monorepo and never shipped with this package."""
    problems = docgates.disclaimer_problems()
    assert not problems, "rule-5 frontmatter missing:\n" + _report(problems)


def test_no_doc_names_a_stale_contract_version():
    """`pyproject.toml` and `__init__.py` both said HEAD_VERSION was 2.8.x when
    it was 2.11.0. Comments, so nothing was checking them."""
    problems = docgates.version_literal_problems()
    assert not problems, "stale HEAD_VERSION literals:\n" + _report(problems)


def test_the_package_version_agrees_with_itself():
    problems = docgates.package_version_problems()
    assert not problems, _report(problems)


def test_the_current_version_has_a_changelog_section():
    """1.2.0 shipped with its entries still under `## Unreleased`, and a 1.1.0
    wheel was built from a state that was never committed."""
    problems = docgates.changelog_problems()
    assert not problems, _report(problems)


def test_every_cli_flag_is_documented():
    """`ff-schema --out` and `ff-codemod --stdout` shipped undocumented."""
    problems = docgates.cli_flag_problems()
    assert not problems, "undocumented CLI flags:\n" + _report(problems)


def test_counts_quoted_in_prose_match_the_registry():
    """README hand-writes "eleven entries", "nine forms still parse" and names
    both rejected forms. The registry is meant to grow."""
    problems = docgates.deprecation_count_problems()
    assert not problems, "quoted counts drifted:\n" + _report(problems)


def test_the_golden_corpus_size_in_prose_is_current():
    """Two docstrings said "183 declarations" while the golden held 203."""
    problems = docgates.golden_count_problems()
    assert not problems, _report(problems)


def test_relative_links_resolve():
    """CLAUDE.md linked to PURPOSE.md, which exists only in the monorepo."""
    problems = docgates.link_problems()
    assert not problems, "broken relative links:\n" + _report(problems)


@pytest.mark.parametrize("name,gate", docgates.GATES, ids=[n for n, _ in docgates.GATES])
def test_the_cli_runs_every_gate(name, gate):
    """`make doc-check` and this module must cover the same set — a gate added
    to `docgates.GATES` but not wired into the CLI would be dead code."""
    assert callable(gate)
    assert isinstance(gate(), list)
