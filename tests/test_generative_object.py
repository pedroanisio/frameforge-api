"""Contract tests for unresolved generative content objects.

Generation is deliberately represented as authoring intent. A downstream
generation tier resolves the request once and replaces it with an ordinary,
pinned FrameForge object; the contract package never calls a model provider.
"""
from __future__ import annotations

import pytest

from frameforge_api import HEAD_VERSION, Document, build_schema
from frameforge_api.model import GenerationParams, GenerativeObject


def document_with_object(obj: dict) -> dict:
    """Return the smallest positioned document containing ``obj``."""
    return {
        "dsl": "FrameForge",
        "version": HEAD_VERSION,
        "title": "generative contract",
        "pages": [{
            "mode": "page",
            "id": "p1",
            "canvas": {"size": [1024, 1024], "units": "px"},
            "layers": [{"id": "main", "objects": [obj]}],
        }],
    }


def image_request(**overrides) -> dict:
    """Return a complete image-generation request with optional overrides."""
    request = {
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
    }
    request.update(overrides)
    return request


def test_generative_object_image_request_validates_and_round_trips():
    document = Document.model_validate(document_with_object(image_request()))
    obj = document.pages[0].layers[0].objects[0]

    assert isinstance(obj, GenerativeObject)
    assert isinstance(obj.params, GenerationParams)
    assert obj.params.seed == 42
    assert obj.model_dump(mode="json", exclude_none=True)["prompt"] == (
        "A cut-paper forest at blue hour"
    )


def test_generative_object_accepts_named_size_and_explicit_regeneration():
    obj = GenerativeObject.model_validate(image_request(
        params={"size": "1792x1024", "style": "natural"},
        regenerate=True,
    ))

    assert obj.params.size == "1792x1024"
    assert obj.regenerate is True


def test_generative_object_can_be_nested_in_a_group():
    grouped = {
        "type": "group",
        "box": [0, 0, 1024, 1024],
        "children": [image_request(box=[0, 0, 1024, 1024])],
    }
    document = Document.model_validate(document_with_object(grouped))

    assert isinstance(document.pages[0].layers[0].objects[0].children[0], GenerativeObject)


@pytest.mark.parametrize("field", ["prompt", "model"])
@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_generative_object_rejects_blank_required_text(field, value):
    request = image_request(**{field: value})

    with pytest.raises(Exception):
        GenerativeObject.model_validate(request)


@pytest.mark.parametrize("kind", ["image", "diagram"])
def test_generative_visual_output_requires_accessible_text(kind):
    request = image_request(kind=kind)
    request.pop("alt")

    with pytest.raises(Exception, match=r"alt.*actual_text"):
        GenerativeObject.model_validate(request)


def test_generative_visual_output_accepts_actual_text_instead_of_alt():
    request = image_request(actual_text="A node-link diagram of the service topology.")
    request.pop("alt")

    assert GenerativeObject.model_validate(request).actual_text.startswith("A node-link")


def test_generative_text_output_does_not_require_image_alt_text():
    request = image_request(kind="text")
    request.pop("alt")

    assert GenerativeObject.model_validate(request).kind == "text"


@pytest.mark.parametrize("size", [[1024], [1024, 1024, 1024], [1024, 0], [1024, -1]])
def test_generation_params_reject_invalid_pixel_dimensions(size):
    with pytest.raises(Exception):
        GenerationParams.model_validate({"size": size})


def test_generation_params_reject_unknown_keys():
    with pytest.raises(Exception):
        GenerationParams.model_validate({"vendor_magic": True})


def test_generated_schema_exposes_the_generative_discriminator_and_fields():
    schema = build_schema()
    definition = schema["$defs"]["GenerativeObject"]

    assert definition["properties"]["type"]["const"] == "generative"
    assert definition["properties"]["kind"]["enum"] == ["image", "text", "diagram"]
    assert set(definition["required"]) >= {"type", "kind", "prompt", "model"}
    assert "GenerationParams" in schema["$defs"]
