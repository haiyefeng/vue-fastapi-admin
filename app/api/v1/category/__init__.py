from fastapi import APIRouter

from .route import router

category_router = APIRouter()
category_router.include_router(router, tags=["分类"])

__all__ = ["category_router"]
