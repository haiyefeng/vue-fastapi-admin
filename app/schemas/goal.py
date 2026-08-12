from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    name: str = Field(..., description="计划/目标名称")
    description: Optional[str] = Field(None, description="描述")
    target_date: Optional[date] = Field(None, description="目标完成日期")
    category_id: Optional[int] = Field(None, description="已有分类ID")
    category_name: Optional[str] = Field(None, description="新分类名称，与 category_id 二选一")


class GoalUpdate(BaseModel):
    id: int = Field(..., description="计划ID")
    name: Optional[str] = None
    description: Optional[str] = None
    target_date: Optional[date] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    is_archived: Optional[bool] = None


class GoalOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    target_date: Optional[date] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    is_archived: bool
    task_total: int = Field(0, description="关联任务总数")
    task_completed: int = Field(0, description="关联任务已完成数")
    habit_count: int = Field(0, description="关联习惯数量")

    class Config:
        from_attributes = True


class GoalTaskItem(BaseModel):
    id: int
    title: str
    is_completed: bool

    class Config:
        from_attributes = True


class GoalHabitItem(BaseModel):
    id: int
    name: str
    frequency_type: str
    frequency_config: Optional[dict] = None

    class Config:
        from_attributes = True


class GoalDetailOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    target_date: Optional[date] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    is_archived: bool
    tasks: List[GoalTaskItem] = Field(default_factory=list)
    habits: List[GoalHabitItem] = Field(default_factory=list)

    class Config:
        from_attributes = True
