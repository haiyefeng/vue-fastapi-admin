from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.timeblock import TimeBlockOut


class TodayTaskItem(BaseModel):
    id: int
    title: str
    due_date: Optional[datetime] = None
    quadrant_type: str
    project_id: Optional[int] = None

    class Config:
        from_attributes = True


class TodayHabitItem(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    color_hex: Optional[str] = None
    frequency_type: str
    frequency_config: Optional[dict] = None
    today_todo_id: int
    today_completed: bool
    streak: Optional[int] = None
    week_progress: Optional[str] = None


class TodayOverviewOut(BaseModel):
    date: date
    schedule: List[TimeBlockOut] = Field(default_factory=list)
    tasks: List[TodayTaskItem] = Field(default_factory=list)
    habits: List[TodayHabitItem] = Field(default_factory=list)
