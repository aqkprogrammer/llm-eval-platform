"""Client SDK for logging production LLM calls to the platform.

    from evalplatform.sdk import configure, observe

    configure(base_url="http://localhost:8000")

    @observe(name="support-chat", model="claude-sonnet-5", provider="anthropic")
    def answer(question: str) -> str:
        ...

Each call is timed and shipped in the background (never blocking or failing your app); the
platform scores it asynchronously with the configured monitoring metrics.
"""

from evalplatform.sdk.client import EvalClient, configure, flush, get_client, log_trace
from evalplatform.sdk.observe import current_trace, observe

__all__ = [
    "EvalClient",
    "configure",
    "current_trace",
    "flush",
    "get_client",
    "log_trace",
    "observe",
]
