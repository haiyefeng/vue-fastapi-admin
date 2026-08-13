from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.todo import ReviewPeriodType, ReviewStatus


class ReviewSaveIn(BaseModel):
    period_type: ReviewPeriodType = Field(..., description="回顾周期类型")
    anchor_date: date = Field(..., description="周期内任意一天，用于定位周期起止")
    answers: Dict[str, str] = Field(
        default_factory=dict, description="七步提问法答案，key 为 step1~step7，前端一次性提交当前完整表单状态"
    )
    status: ReviewStatus = Field(ReviewStatus.DRAFT, description="草稿/已完成")


class ReviewOut(BaseModel):
    id: int
    period_type: ReviewPeriodType
    period_start: date
    period_end: date
    answers: Dict[str, str] = Field(default_factory=dict)
    status: ReviewStatus

    class Config:
        from_attributes = True


class ReviewListItem(BaseModel):
    id: int
    period_type: ReviewPeriodType
    period_start: date
    period_end: date
    status: ReviewStatus

    class Config:
        from_attributes = True
