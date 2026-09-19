from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from evalplatform.api.deps import SessionDep
from evalplatform.db.models import PromptTemplate, PromptVersion
from evalplatform.schemas import (
    PromptPreviewRequest,
    PromptTemplateCreate,
    PromptTemplateOut,
    PromptVersionCreate,
    PromptVersionOut,
)
from evalplatform.services.prompts import (
    PromptRenderError,
    build_variables,
    render,
    validate_template,
)

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


def _version_out(v: PromptVersion) -> PromptVersionOut:
    out = PromptVersionOut.model_validate(v)
    out.variables = sorted(
        set(validate_template(v.user_template)) | set(validate_template(v.system_prompt))
    )
    return out


def _out(t: PromptTemplate) -> PromptTemplateOut:
    return PromptTemplateOut(
        id=t.id,
        name=t.name,
        description=t.description,
        created_at=t.created_at,
        versions=[_version_out(v) for v in t.versions],
    )


def _validate(payload: PromptVersionCreate) -> None:
    try:
        validate_template(payload.system_prompt)
        validate_template(payload.user_template)
    except PromptRenderError as exc:
        raise HTTPException(422, str(exc)) from exc


async def _load(session: SessionDep, template_id: str) -> PromptTemplate:
    t = await session.get(
        PromptTemplate,
        template_id,
        options=[selectinload(PromptTemplate.versions)],
        populate_existing=True,
    )
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prompt template not found")
    return t


@router.get("", response_model=list[PromptTemplateOut])
async def list_prompts(session: SessionDep) -> list[PromptTemplateOut]:
    rows = (
        await session.scalars(
            select(PromptTemplate)
            .options(selectinload(PromptTemplate.versions))
            .order_by(PromptTemplate.name)
        )
    ).all()
    return [_out(t) for t in rows]


@router.post("", response_model=PromptTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_prompt(payload: PromptTemplateCreate, session: SessionDep) -> PromptTemplateOut:
    _validate(payload)
    if await session.scalar(select(PromptTemplate.id).where(PromptTemplate.name == payload.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Prompt '{payload.name}' already exists")
    t = PromptTemplate(name=payload.name, description=payload.description)
    t.versions.append(
        PromptVersion(
            version=1,
            system_prompt=payload.system_prompt,
            user_template=payload.user_template,
            notes=payload.notes,
        )
    )
    session.add(t)
    await session.commit()
    return _out(await _load(session, t.id))


@router.get("/{template_id}", response_model=PromptTemplateOut)
async def get_prompt(template_id: str, session: SessionDep) -> PromptTemplateOut:
    return _out(await _load(session, template_id))


@router.post(
    "/{template_id}/versions", response_model=PromptVersionOut, status_code=status.HTTP_201_CREATED
)
async def create_version(
    template_id: str, payload: PromptVersionCreate, session: SessionDep
) -> PromptVersionOut:
    _validate(payload)
    t = await _load(session, template_id)
    v = PromptVersion(
        template_id=t.id,
        version=max((x.version for x in t.versions), default=0) + 1,
        system_prompt=payload.system_prompt,
        user_template=payload.user_template,
        notes=payload.notes,
    )
    session.add(v)
    await session.commit()
    return _version_out(v)


@router.post("/preview")
async def preview(payload: PromptPreviewRequest) -> dict[str, Any]:
    variables = build_variables(payload.input, payload.context, [], payload.metadata)
    try:
        return {
            "system": render(payload.system_prompt, variables),
            "user": render(payload.user_template, variables),
            "variables": sorted(
                set(validate_template(payload.user_template))
                | set(validate_template(payload.system_prompt))
            ),
        }
    except PromptRenderError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(template_id: str, session: SessionDep) -> None:
    await session.delete(await _load(session, template_id))
    await session.commit()
