from datetime import datetime

from pydantic import BaseModel, Field

from app.models.todo import QuadrantType


class TimeBlockCreate(BaseModel):
    todo_item_id: int = Field(..., description="所属待办事项ID")
    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")


class TimeBlockOut(BaseModel):
    id: int
    todo_item_id: int
    start_time: datetime
    end_time: datetime
    title: str = Field(..., description="所属待办事项标题")
    quadrant_type: QuadrantType = Field(..., description="所属待办事项象限")

    class Config:
        from_attributes = True
