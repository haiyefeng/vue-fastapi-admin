from fastapi import APIRouter

from .route import router

timeblock_router = APIRouter()
timeblock_router.include_router(router, tags=["时间块"])

__all__ = ["timeblock_router"]
