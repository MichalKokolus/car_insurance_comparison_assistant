"""Real Claude provider. Only instantiated when an API key is configured."""

from __future__ import annotations

import base64
from typing import TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str) -> None:
        # Model id / params come from settings. For anything about model choice, pricing, or
        # structured-output behavior, consult the `claude-api` skill — don't hardcode assumptions.
        self._model = ChatAnthropic(model=model, api_key=api_key, timeout=60, max_retries=2)

    async def structured(self, system: str, user: str, schema: type[T]) -> T:
        model = self._model.with_structured_output(schema)
        return await model.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])

    async def structured_with_images(
        self, system: str, text: str, images: list[bytes], schema: type[T]
    ) -> T:
        content: list[dict] = [{"type": "text", "text": text}]
        for png in images:
            b64 = base64.b64encode(png).decode("ascii")
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            )
        model = self._model.with_structured_output(schema)
        return await model.ainvoke([SystemMessage(content=system), HumanMessage(content=content)])

    def chat_model(self) -> ChatAnthropic:
        return self._model
