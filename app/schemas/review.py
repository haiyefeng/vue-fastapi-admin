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


class TaskCompletionByCategory(BaseModel):
    category_id: int
    category_name: str
    total: int
    completed: int


class TaskCompletionSummary(BaseModel):
    total: int = Field(0, description="周期内到期的任务总数")
    completed: int = Field(0, description="其中已完成数")
    urgent_important_total: int = Field(0, description="周期内到期的高优先级（紧急且重要）任务总数")
    urgent_important_completed: int = Field(0, description="其中已完成数")
    by_category: List[TaskCompletionByCategory] = Field(default_factory=list)


class HabitCheckInSummary(BaseModel):
    habit_id: int
    name: str
    frequency_type: str
    completed: int = Field(0, description="周期内完成天数（定日型）或完成次数（弹性型）")
    expected: int = Field(0, description="周期内应完成天数（定日型）或配额总数（弹性型）")
    streak: Optional[int] = Field(None, description="当前连续天数，仅定日型有意义，弹性型为 null")


class GoalProgressSummary(BaseModel):
    goal_id: int
    name: str
    newly_completed: int = Field(0, description="周期内新完成的关联任务数")
    total_linked_tasks: int = Field(0, description="计划关联任务总数")
    progress_percent: Optional[float] = Field(None, description="newly_completed/total_linked_tasks 的百分比，无关联任务时为 null（对应“无明显进展”）")


class ReviewDataSummaryOut(BaseModel):
    period_start: date
    period_end: date
    task_completion: TaskCompletionSummary
    habits: List[HabitCheckInSummary] = Field(default_factory=list)
    goals: List[GoalProgressSummary] = Field(default_factory=list)
