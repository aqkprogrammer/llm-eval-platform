"""Embedding backends used by similarity metrics.

The default :class:`LexicalEmbedder` is dependency-free and deterministic (stemmed words plus
character trigrams). Set ``EMBEDDING_PROVIDER=openai`` to use real semantic embeddings.
"""

from __future__ import annotations

from typing import Any, Protocol

from evalplatform.metrics.text import cosine, dense_cosine, lexical_vector


class Embedder(Protocol):
    name: str

    async def similarity(self, a: str, b: str) -> float: ...


class LexicalEmbedder:
    name = "lexical"

    async def similarity(self, a: str, b: str) -> float:
        return cosine(lexical_vector(a), lexical_vector(b))


class OpenAIEmbedder:
    name = "openai"

    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        import openai

        self._client: Any = openai.AsyncOpenAI(api_key=api_key)
        self._model = model

    async def similarity(self, a: str, b: str) -> float:
        resp = await self._client.embeddings.create(model=self._model, input=[a or " ", b or " "])
        return max(0.0, dense_cosine(resp.data[0].embedding, resp.data[1].embedding))


def build_embedder(provider: str, openai_api_key: str | None, model: str) -> Embedder:
    if provider == "openai" and openai_api_key:
        return OpenAIEmbedder(openai_api_key, model)
    return LexicalEmbedder()
