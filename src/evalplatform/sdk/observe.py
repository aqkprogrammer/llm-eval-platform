"""``@observe`` decorator: time a function that calls an LLM and log it as a production trace."""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, ParamSpec, TypeVar

from evalplatform.sdk.client import get_client

P = ParamSpec("P")
R = TypeVar("R")

_current: ContextVar[dict[str, Any] | None] = ContextVar("evalplatform_current_trace", default=None)


def current_trace() -> dict[str, Any]:
    """Mutable dict for the active ``@observe`` call - set tokens, context, metadata, etc.

    Example: ``current_trace().update(input_tokens=usage.input_tokens, context=docs)``
    """
    trace = _current.get()
    if trace is None:
        raise RuntimeError("current_trace() called outside an @observe-decorated function")
    return trace


def _default_input(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    for value in (*args, *kwargs.values()):
        if isinstance(value, str):
            return value
    return repr((args, kwargs))[:4000]


def observe(
    name: str | None = None,
    *,
    model: str | None = None,
    provider: str | None = None,
    metrics: list[str] | None = None,
    tags: list[str] | None = None,
    capture_input: Callable[..., str] | None = None,
    capture_output: Callable[[Any], str] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorate a sync or async function; each call is shipped to ``POST /api/traces``."""

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        trace_name = name or fn.__qualname__

        def _start(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
            return {
                "name": trace_name,
                "input": capture_input(*args, **kwargs)
                if capture_input
                else _default_input(args, kwargs),
                "model": model,
                "provider": provider,
                "metrics": metrics,
                "tags": list(tags or []),
                "start_time": datetime.now(UTC).isoformat(),
                "metadata": {},
            }

        def _finish(
            trace: dict[str, Any], started: float, result: Any, error: BaseException | None
        ) -> None:
            trace.setdefault("latency_ms", round((time.perf_counter() - started) * 1000, 2))
            if error is not None:
                trace["status"] = "error"
                trace["output"] = trace.get("output") or ""
                trace["metadata"]["error"] = f"{type(error).__name__}: {error}"
            elif "output" not in trace:
                trace["output"] = capture_output(result) if capture_output else str(result)
            get_client().log_trace({k: v for k, v in trace.items() if v is not None})

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                trace = _start(args, kwargs)
                token = _current.set(trace)
                started = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)  # type: ignore[misc]
                except BaseException as exc:
                    _finish(trace, started, None, exc)
                    raise
                finally:
                    _current.reset(token)
                _finish(trace, started, result, None)
                return result

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            trace = _start(args, kwargs)
            token = _current.set(trace)
            started = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:
                _finish(trace, started, None, exc)
                raise
            finally:
                _current.reset(token)
            _finish(trace, started, result, None)
            return result

        return sync_wrapper

    return decorator
