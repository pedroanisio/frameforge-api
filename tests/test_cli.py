#!/usr/bin/env python3
"""test_cli.py — `ff-schema` behaves like a tool you can trust in CI.

The CLI writes to a path *inside the installed package*, so "what does this
invocation write?" is a correctness question, not a cosmetic one: a command that
regenerates package data as a side effect will fail on a read-only install and
silently mutate a wheel on a writable one.
"""
from __future__ import annotations

import json

import pytest

from frameforge_api import HEAD_VERSION, SCHEMA_PATH
from frameforge_api.schema import main


def minimal_doc():
    return {
        "dsl": "FrameForge", "version": HEAD_VERSION, "title": "cli",
        "pages": [{"mode": "page", "id": "p1",
                   "canvas": {"size": [400, 200], "units": "px"},
                   "layers": [{"id": "m", "objects": [
                       {"type": "text", "box": [20, 20, 360, 40], "text": "hi"}]}]}],
    }


def test_validating_a_document_writes_nothing(tmp_path, capsys):
    """REGRESSION: `ff-schema doc.json` used to regenerate the schema into
    site-packages before validating. Validation is a read-only operation."""
    before = SCHEMA_PATH.read_bytes()
    doc = tmp_path / "d.json"
    doc.write_text(json.dumps(minimal_doc()), encoding="utf-8")

    assert main([str(doc)]) == 0
    assert SCHEMA_PATH.read_bytes() == before, "validation must not rewrite package data"
    assert "wrote " not in capsys.readouterr().out


def test_an_invalid_document_exits_nonzero(tmp_path):
    """The CI contract: a bad document must fail the command, not just print."""
    bad = minimal_doc()
    bad["bogus_key"] = 1
    doc = tmp_path / "bad.json"
    doc.write_text(json.dumps(bad), encoding="utf-8")
    assert main([str(doc)]) == 1


def test_an_unreadable_document_exits_two(tmp_path):
    assert main([str(tmp_path / "missing.json")]) == 2


def test_check_passes_on_the_committed_schema(capsys):
    assert main(["--check"]) == 0
    assert "OK" in capsys.readouterr().out


def test_check_fails_loudly_on_a_stale_file(tmp_path, capsys):
    stale = tmp_path / "stale.json"
    stale.write_text('{"not": "the schema"}\n', encoding="utf-8")
    assert main(["--check", "--out", str(stale)]) == 1
    assert "STALE" in capsys.readouterr().err


def test_print_emits_the_schema_without_touching_disk(capsys):
    before = SCHEMA_PATH.read_bytes()
    assert main(["--print"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["version"] == HEAD_VERSION
    assert SCHEMA_PATH.read_bytes() == before


def test_out_redirects_generation_away_from_the_package(tmp_path):
    target = tmp_path / "nested" / "schema.json"
    assert main(["--out", str(target)]) == 0
    assert json.loads(target.read_text(encoding="utf-8"))["version"] == HEAD_VERSION


def test_check_and_validate_compose(tmp_path):
    """`--check doc` does both jobs and returns the worst status."""
    bad = minimal_doc()
    bad["bogus_key"] = 1
    doc = tmp_path / "bad.json"
    doc.write_text(json.dumps(bad), encoding="utf-8")
    assert main(["--check", str(doc)]) == 1


def test_yaml_input_is_supported_when_pyyaml_is_present(tmp_path):
    yaml = pytest.importorskip("yaml")
    doc = tmp_path / "d.fg.yaml"
    doc.write_text(yaml.safe_dump(minimal_doc()), encoding="utf-8")
    assert main([str(doc)]) == 0
