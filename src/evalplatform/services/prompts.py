"""Prompt template rendering (sandboxed Jinja2 with strict undefined variables)."""

from __future__ import annotations

from typing import Any

from jinja2 import StrictUndefined, TemplateSyntaxError, meta
from jinja2.sandbox import SandboxedEnvironment

_env = SandboxedEnvironment(
    undefined=StrictUndefined, autoescape=False, keep_trailing_newline=False
)

BUILTIN_VARIABLES = {"input", "context", "context_str", "tags", "metadata"}


class PromptRenderError(ValueError):
    pass


def template_variables(source: str) -> set[str]:
    try:
        return set(meta.find_undeclared_variables(_env.parse(source)))
    except TemplateSyntaxError as exc:
        raise PromptRenderError(f"Invalid template (line {exc.lineno}): {exc.message}") from exc


def validate_template(source: str) -> list[str]:
    return sorted(template_variables(source))


def build_variables(
    input: str,
    context: list[str] | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = context or []
    variables: dict[str, Any] = dict(metadata or {})
    variables.update(
        input=input,
        context=context,
        context_str="\n".join(f"- {c}" for c in context),
        tags=tags or [],
        metadata=metadata or {},
    )
    return variables


def render(source: str, variables: dict[str, Any]) -> str:
    try:
        return _env.from_string(source).render(**variables).strip()
    except TemplateSyntaxError as exc:
        raise PromptRenderError(f"Invalid template (line {exc.lineno}): {exc.message}") from exc
    except Exception as exc:  # UndefinedError, SecurityError, ...
        raise PromptRenderError(f"Failed to render template: {exc}") from exc
