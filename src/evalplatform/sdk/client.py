"""Background, non-blocking HTTP shipper for traces."""

from __future__ import annotations

import atexit
import logging
import os
import queue
import threading
from typing import Any

import httpx

log = logging.getLogger("evalplatform.sdk")


class EvalClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = 5.0,
        max_queue: int = 10_000,
        enabled: bool = True,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.getenv("EVAL_PLATFORM_URL", "http://127.0.0.1:8000")
        ).rstrip("/")
        self.enabled = enabled
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=max_queue)
        self._thread = threading.Thread(target=self._loop, name="evalplatform-sdk", daemon=True)
        self._thread.start()
        self.sent = 0
        self.failed = 0

    def log_trace(self, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            self.failed += 1
            log.warning("evalplatform sdk queue full; dropping trace")

    def send_now(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._http.post("/api/traces", json=payload)
        resp.raise_for_status()
        return resp.json()

    def _loop(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                self.send_now(item)
                self.sent += 1
            except Exception as exc:  # never crash the host application
                self.failed += 1
                log.warning("evalplatform sdk failed to send trace: %s", exc)
            finally:
                self._queue.task_done()

    def flush(self, timeout: float | None = 10.0) -> None:
        """Block until queued traces are sent (best effort, bounded by ``timeout``)."""
        done = threading.Event()

        def _wait() -> None:
            self._queue.join()
            done.set()

        threading.Thread(target=_wait, daemon=True).start()
        done.wait(timeout)

    def close(self) -> None:
        self.flush()
        self._http.close()


_client: EvalClient | None = None
_lock = threading.Lock()


def configure(base_url: str | None = None, **kwargs: Any) -> EvalClient:
    global _client
    with _lock:
        _client = EvalClient(base_url, **kwargs)
    return _client


def get_client() -> EvalClient:
    global _client
    with _lock:
        if _client is None:
            _client = EvalClient()
    return _client


def log_trace(**payload: Any) -> None:
    get_client().log_trace({k: v for k, v in payload.items() if v is not None})


def flush(timeout: float | None = 10.0) -> None:
    if _client is not None:
        _client.flush(timeout)


atexit.register(flush, 2.0)
