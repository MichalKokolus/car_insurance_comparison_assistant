"""LLMProvider abstraction.

The graph talks to this interface, never to a concrete SDK. That's the seam that lets us run
keyless today (StubProvider) and swap in real Claude — or another vendor — without touching nodes.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def structured(self, system: str, user: str, schema: type[T]) -> T:
        """Return an instance of `schema` produced from the prompt."""
        ...

    def chat_model(self) -> Any:
        """Return a LangChain chat model for the ReAct research agent (real providers only)."""
        ...
