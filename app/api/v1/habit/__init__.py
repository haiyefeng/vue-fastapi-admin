from fastapi import APIRouter

from .route import router

habit_router = APIRouter()
habit_router.include_router(router, tags=["习惯"])

__all__ = ["habit_router"]
