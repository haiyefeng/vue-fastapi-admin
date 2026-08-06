from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.todo import QuadrantType


class TodoItemBase(BaseModel):
    """待办事项基础模型"""

    title: str = Field(..., description="待办事项标题")
    quadrant_type: QuadrantType = Field(..., description="象限类型")
    due_date: Optional[datetime] = Field(None, description="截止时间")
    notes: Optional[str] = Field(None, description="备注信息")
    project_id: Optional[int] = Field(None, description="所属项目ID，为空则属于收件箱")
    reminder_at: Optional[datetime] = Field(None, description="提醒时间，仅存储与展示，不做推送")

    class Config:
        json_encoders = {date: lambda v: v.isoformat() if v else None}


class TodoItemCreate(TodoItemBase):
    """创建待办事项的请求体"""

    pass


class TodoItemUpdate(BaseModel):
    """更新待办事项的请求体"""

    id: int = Field(..., description="待办事项ID")
    title: Optional[str] = Field(None, description="待办事项标题")
    quadrant_type: Optional[QuadrantType] = Field(None, description="象限类型")
    due_date: Optional[datetime] = Field(None, description="截止时间")
    notes: Optional[str] = Field(None, description="备注信息")
    is_completed: Optional[bool] = Field(None, description="是否已完成")
    project_id: Optional[int] = Field(None, description="所属项目ID，传 null 可退回收件箱")
    reminder_at: Optional[datetime] = Field(None, description="提醒时间")


class TodoItemOut(TodoItemBase):
    """待办事项的响应体"""

    id: int
    is_completed: bool = Field(False, description="是否已完成")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    created_at: datetime
    updated_at: datetime
    subtask_total: int = Field(0, description="子任务总数")
    subtask_completed: int = Field(0, description="已完成子任务数")

    class Config:
        from_attributes = True


class TodoStatisticsByDate(BaseModel):
    """按日期统计的待办事项数量"""

    date: date
    urgent_important: int = Field(0, description="紧急且重要的待办事项数量")
    urgent_not_important: int = Field(0, description="紧急但不重要的待办事项数量")
    important_not_urgent: int = Field(0, description="重要但不紧急的待办事项数量")
    not_urgent_not_important: int = Field(0, description="不紧急也不重要的待办事项数量")
    total: int = Field(0, description="总待办事项数量")


class QuadrantStatistics(BaseModel):
    """按象限统计的待办事项数量"""

    urgent_important: int = Field(0, description="紧急且重要的待办事项数量")
    urgent_not_important: int = Field(0, description="紧急但不重要的待办事项数量")
    important_not_urgent: int = Field(0, description="重要但不紧急的待办事项数量")
    not_urgent_not_important: int = Field(0, description="不紧急也不重要的待办事项数量")
    total: int = Field(0, description="总待办事项数量")
