from fastapi import APIRouter, Depends

from app.deps import get_current_admin, get_current_user
from app.models.registry import ModelCreate, ModelListResponse, ModelRecord, ModelUpdate
from app.models.user import UserInDB
from app.services import registry as registry_service

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=ModelListResponse)
async def list_models(_user: UserInDB = Depends(get_current_user)) -> ModelListResponse:
    models = await registry_service.list_enabled_models()
    return ModelListResponse(models=models)


@router.get("/all", response_model=ModelListResponse)
async def list_all_models(_admin: UserInDB = Depends(get_current_admin)) -> ModelListResponse:
    models = await registry_service.list_all_models()
    return ModelListResponse(models=models)


@router.post("", response_model=ModelRecord)
async def create_model(
    payload: ModelCreate,
    _admin: UserInDB = Depends(get_current_admin),
) -> ModelRecord:
    return await registry_service.create_model(payload)


@router.patch("/{model_id:path}", response_model=ModelRecord)
async def patch_model(
    model_id: str,
    payload: ModelUpdate,
    _admin: UserInDB = Depends(get_current_admin),
) -> ModelRecord:
    return await registry_service.update_model(model_id, payload)


@router.delete("/{model_id:path}")
async def remove_model(
    model_id: str,
    _admin: UserInDB = Depends(get_current_admin),
) -> dict[str, bool]:
    await registry_service.delete_model(model_id)
    return {"ok": True}
