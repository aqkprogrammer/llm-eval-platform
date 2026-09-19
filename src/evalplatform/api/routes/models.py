from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from evalplatform.api.deps import ServicesDep, SessionDep
from evalplatform.db.models import ModelConfig
from evalplatform.providers.pricing import get_pricing
from evalplatform.providers.registry import PROVIDER_NAMES
from evalplatform.schemas import ModelConfigCreate, ModelConfigOut

router = APIRouter(prefix="/api", tags=["models"])


def _out(mc: ModelConfig, available: dict[str, bool]) -> ModelConfigOut:
    out = ModelConfigOut.model_validate(mc)
    out.available = available.get(mc.provider, False)
    return out


@router.get("/models", response_model=list[ModelConfigOut])
async def list_models(session: SessionDep, services: ServicesDep) -> list[ModelConfigOut]:
    avail = services.providers.status()
    rows = (
        await session.scalars(select(ModelConfig).order_by(ModelConfig.provider, ModelConfig.name))
    ).all()
    return [_out(m, avail) for m in rows]


@router.post("/models", response_model=ModelConfigOut, status_code=status.HTTP_201_CREATED)
async def create_model(
    payload: ModelConfigCreate, session: SessionDep, services: ServicesDep
) -> ModelConfigOut:
    if await session.scalar(select(ModelConfig.id).where(ModelConfig.name == payload.name)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Model config '{payload.name}' already exists"
        )
    mc = ModelConfig(**payload.model_dump())
    session.add(mc)
    await session.commit()
    return _out(mc, services.providers.status())


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(model_id: str, session: SessionDep) -> None:
    mc = await session.get(ModelConfig, model_id)
    if mc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model config not found")
    await session.delete(mc)
    await session.commit()


@router.get("/providers")
async def providers(services: ServicesDep) -> dict[str, Any]:
    return {
        "providers": [
            {"name": n, "configured": services.providers.status()[n]} for n in PROVIDER_NAMES
        ],
        "pricing": get_pricing().as_dict(),
    }
