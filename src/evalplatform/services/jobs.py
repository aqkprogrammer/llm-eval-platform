"""In-process background job manager for experiment runs.

Runs execute as asyncio tasks inside the API process. Progress and results are persisted after
every case, so the UI can poll, and a restart leaves a consistent (if interrupted) record. For
multi-node deployments swap this for a queue (Arq/Celery) - the runner itself is stateless.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime

from sqlalchemy import update

from evalplatform.db.models import Experiment
from evalplatform.logging import get_logger
from evalplatform.services.context import AppServices
from evalplatform.services.runner import ExperimentRunner

log = get_logger(__name__)


class JobManager:
    def __init__(self, services: AppServices) -> None:
        self.services = services
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def submit(self, experiment_id: str) -> asyncio.Task[None]:
        runner = ExperimentRunner(self.services)
        task = asyncio.create_task(runner.run(experiment_id), name=f"experiment:{experiment_id}")
        self._tasks[experiment_id] = task
        task.add_done_callback(lambda _t: self._tasks.pop(experiment_id, None))
        return task

    def is_running(self, experiment_id: str) -> bool:
        return experiment_id in self._tasks

    async def cancel(self, experiment_id: str) -> bool:
        task = self._tasks.get(experiment_id)
        if task is None:
            return False
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        return True

    async def wait(self, experiment_id: str) -> None:
        task = self._tasks.get(experiment_id)
        if task is not None:
            await asyncio.shield(task)

    async def recover(self) -> None:
        """Mark runs interrupted by a restart as failed so they don't look stuck."""
        async with self.services.db.sessionmaker() as session:
            result = await session.execute(
                update(Experiment)
                .where(Experiment.status.in_(["queued", "running"]))
                .values(
                    status="failed",
                    error="Interrupted: the server restarted before the run finished.",
                    finished_at=datetime.now(UTC),
                )
            )
            await session.commit()
            count = getattr(result, "rowcount", 0) or 0
            if count:
                log.warning("jobs.recovered_interrupted", count=count)

    async def shutdown(self) -> None:
        for task in list(self._tasks.values()):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
