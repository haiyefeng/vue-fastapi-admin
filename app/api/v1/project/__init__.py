from fastapi import APIRouter

from .route import router

project_router = APIRouter()
project_router.include_router(router, tags=["项目"])

__all__ = ["project_router"]
