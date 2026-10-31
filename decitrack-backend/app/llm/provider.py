from typing import Protocol, TypeVar

from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class LLMProviderError(RuntimeError):
    """The configured language model could not produce a response."""


class LLMProvider(Protocol):
    def generate_structured(self, prompt: str, output_model: type[T]) -> T:
        """Generate and validate a response against a Pydantic model."""

