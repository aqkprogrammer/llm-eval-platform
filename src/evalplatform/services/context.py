"""Application service container shared by the API, background workers and the CLI."""

from __future__ import annotations

from dataclasses import dataclass, field

from evalplatform.config import Settings
from evalplatform.db.session import Database
from evalplatform.metrics.base import MetricContext
from evalplatform.metrics.embeddings import Embedder, build_embedder
from evalplatform.providers.registry import ProviderRegistry


@dataclass
class AppServices:
    settings: Settings
    db: Database
    providers: ProviderRegistry
    embedder: Embedder = field(init=False)

    def __post_init__(self) -> None:
        self.embedder = build_embedder(
            self.settings.embedding_provider,
            self.settings.openai_api_key,
            self.settings.embedding_model,
        )

    def metric_context(self) -> MetricContext:
        return MetricContext(
            providers=self.providers,
            judge_provider=self.settings.judge_provider,
            judge_model=self.settings.judge_model,
            embedder=self.embedder,
        )

    async def aclose(self) -> None:
        await self.providers.aclose()
        await self.db.dispose()
