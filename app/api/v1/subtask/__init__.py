from fastapi import APIRouter

from .route import router

subtask_router = APIRouter()
subtask_router.include_router(router, tags=["子任务"])

__all__ = ["subtask_router"]
