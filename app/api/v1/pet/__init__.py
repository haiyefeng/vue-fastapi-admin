from fastapi import APIRouter

from .route import router

pet_router = APIRouter()
pet_router.include_router(router, tags=["养成猫"])

__all__ = ["pet_router"]
