from fastapi import APIRouter

from .route import router

todos_router = APIRouter()
todos_router.include_router(router, tags=["待办事项"])

__all__ = ["todos_router"]
