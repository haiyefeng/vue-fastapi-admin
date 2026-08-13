from fastapi import APIRouter

from .route import router

review_router = APIRouter()
review_router.include_router(router, tags=["回顾总结"])

__all__ = ["review_router"]
