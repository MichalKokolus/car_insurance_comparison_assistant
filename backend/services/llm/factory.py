"""Provider selection. One place decides stub vs. real Claude."""

from __future__ import annotations

from functools import lru_cache

from backend.config import get_settings

from .anthropic_provider import AnthropicProvider
from .base import LLMProvider
from .stub_provider import StubProvider


@lru_cache
def get_provider() -> LLMProvider:
    settings = get_settings()
    if settings.anthropic_api_key and settings.llm_provider != "stub":
        return AnthropicProvider(settings.anthropic_api_key, settings.model)
    return StubProvider()
