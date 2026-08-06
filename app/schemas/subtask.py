from typing import Optional

from pydantic import BaseModel, Field


class SubTaskCreate(BaseModel):
    todo_item_id: int = Field(..., description="所属待办事项ID")
    title: str = Field(..., description="子任务标题")


class SubTaskUpdate(BaseModel):
    id: int = Field(..., description="子任务ID")
    title: Optional[str] = None
    is_completed: Optional[bool] = None


class SubTaskOut(BaseModel):
    id: int
    todo_item_id: int
    title: str
    is_completed: bool
    order: int

    class Config:
        from_attributes = True
