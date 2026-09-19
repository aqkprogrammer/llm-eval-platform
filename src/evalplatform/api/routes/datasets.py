from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from evalplatform.api.deps import SessionDep
from evalplatform.db.models import Dataset, TestCase
from evalplatform.schemas import CasesAppend, DatasetCreate, DatasetOut, DatasetSummary, TestCaseOut
from evalplatform.services.datasets import DatasetImportError, detect_format, parse_cases
from evalplatform.services.seed import upsert_dataset

router = APIRouter(prefix="/api/datasets", tags=["datasets"])
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


async def _load(session: SessionDep, dataset_id: str) -> Dataset:
    ds = await session.get(Dataset, dataset_id, options=[selectinload(Dataset.cases)])
    if ds is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    return ds


def _out(ds: Dataset) -> DatasetOut:
    return DatasetOut(
        id=ds.id,
        name=ds.name,
        description=ds.description,
        tags=ds.tags or [],
        created_at=ds.created_at,
        case_count=len(ds.cases),
        cases=[TestCaseOut.model_validate(c) for c in ds.cases],
    )


@router.get("", response_model=list[DatasetSummary])
async def list_datasets(session: SessionDep) -> list[DatasetSummary]:
    counts = dict(
        (
            await session.execute(
                select(TestCase.dataset_id, func.count()).group_by(TestCase.dataset_id)
            )
        ).all()
    )
    rows = (await session.scalars(select(Dataset).order_by(Dataset.created_at.desc()))).all()
    return [
        DatasetSummary(
            id=d.id,
            name=d.name,
            description=d.description,
            tags=d.tags or [],
            created_at=d.created_at,
            case_count=counts.get(d.id, 0),
        )
        for d in rows
    ]


@router.post("", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
async def create_dataset(payload: DatasetCreate, session: SessionDep) -> DatasetOut:
    ds, created = await upsert_dataset(
        session, payload.name, payload.cases, payload.description, payload.tags
    )
    if not created:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Dataset '{payload.name}' already exists")
    await session.commit()
    return _out(await _load(session, ds.id))


@router.post("/import", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
async def import_dataset(
    session: SessionDep,
    file: Annotated[UploadFile, File(description="JSONL, JSON or CSV file")],
    name: Annotated[str | None, Form()] = None,
    description: Annotated[str, Form()] = "",
) -> DatasetOut:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large (max 20MB)")
    filename = file.filename or "upload.jsonl"
    try:
        cases = parse_cases(content, detect_format(filename))
    except DatasetImportError as exc:
        raise HTTPException(422, str(exc)) from exc
    ds_name = (name or filename.rsplit(".", 1)[0]).strip()
    ds, created = await upsert_dataset(session, ds_name, cases, description)
    if not created:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Dataset '{ds_name}' already exists")
    await session.commit()
    return _out(await _load(session, ds.id))


@router.get("/{dataset_id}", response_model=DatasetOut)
async def get_dataset(dataset_id: str, session: SessionDep) -> DatasetOut:
    return _out(await _load(session, dataset_id))


@router.post("/{dataset_id}/cases", response_model=DatasetOut)
async def append_cases(dataset_id: str, payload: CasesAppend, session: SessionDep) -> DatasetOut:
    ds = await _load(session, dataset_id)
    start = max((c.position for c in ds.cases), default=-1) + 1
    for i, c in enumerate(payload.cases):
        ds.cases.append(
            TestCase(
                position=start + i,
                input=c.input,
                context=c.context,
                expected_output=c.expected_output,
                tags=c.tags,
                metadata_=c.metadata,
            )
        )
    await session.commit()
    return _out(await _load(session, dataset_id))


@router.get("/{dataset_id}/export", response_class=PlainTextResponse)
async def export_dataset(
    dataset_id: str,
    session: SessionDep,
    fmt: Annotated[str, Query(alias="format", pattern="^jsonl$")] = "jsonl",
) -> PlainTextResponse:
    ds = await _load(session, dataset_id)
    lines = [
        json.dumps(
            {
                "input": c.input,
                "context": c.context,
                "expected_output": c.expected_output,
                "tags": c.tags,
                "metadata": c.metadata_,
            }
        )
        for c in ds.cases
    ]
    return PlainTextResponse(
        "\n".join(lines) + "\n",
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{ds.name}.jsonl"'},
    )


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(dataset_id: str, session: SessionDep) -> None:
    ds = await _load(session, dataset_id)
    await session.delete(ds)
    try:
        await session.commit()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Dataset is referenced by experiments"
        ) from exc
