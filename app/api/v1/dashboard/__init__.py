from fastapi import APIRouter

from .route import router

dashboard_router = APIRouter()
dashboard_router.include_router(router, tags=["今日概览"])

__all__ = ["dashboard_router"]
