"""Dataset import/export (JSONL, JSON and CSV)."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

INPUT_KEYS = ("input", "question", "query", "prompt")
EXPECTED_KEYS = ("expected_output", "expected", "reference", "answer", "ground_truth")
CONTEXT_KEYS = ("context", "contexts", "retrieval_context")


class DatasetImportError(ValueError):
    pass


class CaseIn(BaseModel):
    input: str = Field(min_length=1)
    context: list[str] = Field(default_factory=list)
    expected_output: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("context", mode="before")
    @classmethod
    def _ctx(cls, v: Any) -> list[str]:
        if v is None or v == "":
            return []
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    return [str(x) for x in parsed]
                except json.JSONDecodeError:
                    pass
            return [p.strip() for p in stripped.split("\n\n") if p.strip()] or [stripped]
        return [str(x) for x in v]

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, v: Any) -> list[str]:
        if v is None or v == "":
            return []
        if isinstance(v, str):
            sep = ";" if ";" in v else ","
            return [t.strip() for t in v.split(sep) if t.strip()]
        return [str(t) for t in v]

    @field_validator("metadata", mode="before")
    @classmethod
    def _meta(cls, v: Any) -> dict[str, Any]:
        if v is None or v == "":
            return {}
        if isinstance(v, str):
            try:
                return dict(json.loads(v))
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError("metadata must be a JSON object") from exc
        return dict(v)

    @field_validator("expected_output", mode="before")
    @classmethod
    def _expected(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return None


def normalize_row(row: dict[str, Any]) -> CaseIn:
    known = set(INPUT_KEYS + EXPECTED_KEYS + CONTEXT_KEYS + ("tags", "metadata"))
    metadata = row.get("metadata") or {}
    extras = {k: v for k, v in row.items() if k not in known and v not in (None, "")}
    if isinstance(metadata, dict):
        metadata = {**extras, **metadata}
    return CaseIn(
        input=_pick(row, INPUT_KEYS) or "",
        context=_pick(row, CONTEXT_KEYS),
        expected_output=_pick(row, EXPECTED_KEYS),
        tags=row.get("tags"),
        metadata=metadata,
    )


def parse_cases(content: str | bytes, fmt: str) -> list[CaseIn]:
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    fmt = fmt.lower().lstrip(".")
    rows: list[dict[str, Any]]
    try:
        if fmt == "jsonl":
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        elif fmt == "json":
            data = json.loads(text)
            rows = data.get("cases", []) if isinstance(data, dict) else data
        elif fmt == "csv":
            rows = list(csv.DictReader(io.StringIO(text)))
        else:
            raise DatasetImportError(f"Unsupported format '{fmt}' (use jsonl, json or csv)")
    except json.JSONDecodeError as exc:
        raise DatasetImportError(f"Invalid JSON on line {exc.lineno}: {exc.msg}") from exc
    cases: list[CaseIn] = []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise DatasetImportError(f"Row {i}: expected an object")
        try:
            cases.append(normalize_row(row))
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first["loc"])
            raise DatasetImportError(f"Row {i}: {loc}: {first['msg']}") from exc
    if not cases:
        raise DatasetImportError("No test cases found")
    return cases


def detect_format(filename: str) -> str:
    lower = filename.lower()
    for ext in ("jsonl", "json", "csv"):
        if lower.endswith("." + ext):
            return ext
    if lower.endswith(".ndjson"):
        return "jsonl"
    raise DatasetImportError(f"Cannot infer format from '{filename}'")
