"""Portable closures are runtime evidence, not serialized document state."""
from pathlib import Path

from frameforge_api.model import Document, FontDef

ROOT = Path(__file__).parents[1]


def test_document_contract_keeps_font_identity_but_not_runtime_closure_selection():
    pinned = FontDef(
        family="Pinned Sans",
        src="fonts/pinned-sans.woff2",
        hash="sha256:" + "a" * 64,
        weight=400,
    )

    assert pinned.src == "fonts/pinned-sans.woff2"
    assert pinned.hash == "sha256:" + "a" * 64
    assert "font_closure" not in Document.model_fields
    assert "font_generics" not in Document.model_fields


def test_runtime_boundary_is_documented_from_the_api_readme():
    boundary = ROOT / "docs" / "runtime-font-closure-boundary.md"
    text = boundary.read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "font_closure" in text
    assert "FontDef.src" in text
    assert "FRAMEFORGE_MCP_INPUT_ROOTS" in text
    assert "runtime-font-closure-boundary.md" in readme
