from fastapi import APIRouter

from .route import router

goal_router = APIRouter()
goal_router.include_router(router, tags=["计划"])

__all__ = ["goal_router"]
