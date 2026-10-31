import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict

from app.llm.gemini import GeminiProvider
from app.llm.provider import LLMProviderError


class NestedDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str


class NestedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: NestedDetail


class StructuredResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    items: list[NestedItem]


class FakeModels:
    def __init__(self, response):
        self.response = response
        self.call = None

    def generate_content(self, **kwargs):
        self.call = kwargs
        return self.response


class FakeClient:
    def __init__(self, response):
        self.models = FakeModels(response)


def _assert_no_additional_properties(value):
    if isinstance(value, dict):
        assert "additionalProperties" not in value
        for nested in value.values():
            _assert_no_additional_properties(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_no_additional_properties(nested)


def test_nested_schema_conversion_preserves_supported_schema_and_validates_response():
    payload = {"title": "Report", "items": [{"detail": {"label": "Ready"}}]}
    client = FakeClient(SimpleNamespace(text=json.dumps(payload), parsed=None))
    result = GeminiProvider(client=client).generate_structured("analyze", StructuredResult)

    sent_schema = client.models.call["config"]["response_schema"]
    _assert_no_additional_properties(sent_schema)
    assert sent_schema["required"] == ["title", "items"]
    assert sent_schema["properties"]["items"]["items"]["$ref"].startswith("#/$defs/")
    assert "NestedItem" in sent_schema["$defs"]
    assert sent_schema["$defs"]["NestedItem"]["required"] == ["detail"]
    assert result == StructuredResult.model_validate(payload)


def test_gemini_response_is_validated_against_original_pydantic_model():
    client = FakeClient(SimpleNamespace(text='{"title": 7, "items": []}', parsed=None))
    with pytest.raises(LLMProviderError, match="did not match the requested schema"):
        GeminiProvider(client=client).generate_structured("analyze", StructuredResult)
