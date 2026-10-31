import logging
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.llm.provider import LLMProviderError


T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


def _gemini_schema(schema: Any) -> Any:
    """Copy a JSON schema while removing Gemini-incompatible object keywords."""
    if isinstance(schema, dict):
        return {
            key: _gemini_schema(value)
            for key, value in schema.items()
            if key != "additionalProperties"
        }
    if isinstance(schema, list):
        return [_gemini_schema(value) for value in schema]
    return schema


class GeminiProvider:
    """Gemini structured-output adapter; MongoDB is never exposed here."""

    def __init__(self, api_key: str | None = None, model: str | None = None, client=None):
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        self.model = model or settings.gemini_model
        self._client = client
        if not self.api_key and self._client is None:
            raise LLMProviderError("GEMINI_API_KEY is not configured")

    def generate_structured(self, prompt: str, output_model: type[T]) -> T:
        try:
            schema = _gemini_schema(output_model.model_json_schema())
            if self._client is None:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=self.api_key)
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                )
            else:
                client = self._client
                config = {
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                }
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, output_model):
                return parsed
            text = getattr(response, "text", None)
            if isinstance(text, str) and text.strip():
                return output_model.model_validate_json(text)
            if isinstance(parsed, dict):
                return output_model.model_validate(parsed)
            raise LLMProviderError("Gemini returned no structured response")
        except ImportError as exc:
            logger.exception("Gemini SDK is unavailable")
            raise LLMProviderError("google-genai is required for Gemini analysis") from exc
        except LLMProviderError:
            logger.exception("Gemini structured generation failed")
            raise
        except ValidationError as exc:
            logger.exception("Gemini response validation failed")
            raise LLMProviderError("Gemini response did not match the requested schema") from exc
        except Exception as exc:
            logger.exception("Gemini generation failed")
            raise LLMProviderError("Gemini generation failed") from exc

