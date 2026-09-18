from fastapi import APIRouter

from app.db import ping_mongo

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/api/health")
async def health() -> dict[str, bool]:
    return {"mongo": await ping_mongo()}
