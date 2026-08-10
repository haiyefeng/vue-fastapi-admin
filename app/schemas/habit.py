from datetime import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.models.todo import HabitFrequencyType, QuadrantType


class HabitCreate(BaseModel):
    name: str = Field(..., description="习惯名称")
    icon: Optional[str] = Field(None, description="图标，emoji 或简短文本")
    color_hex: Optional[str] = Field(None, description="颜色代码")
    frequency_type: HabitFrequencyType = Field(..., description="频率类型")
    frequency_config: Optional[Dict[str, Any]] = Field(None, description="频率配置，随类型不同结构不同")
    default_quadrant: QuadrantType = Field(QuadrantType.IMPORTANT_NOT_URGENT, description="生成待办的默认象限")
    goal_desc: Optional[str] = Field(None, description="目标描述，仅展示")
    reminder_time: Optional[time] = Field(None, description="每日提醒时间")


class HabitUpdate(BaseModel):
    id: int = Field(..., description="习惯ID")
    name: Optional[str] = None
    icon: Optional[str] = None
    color_hex: Optional[str] = None
    frequency_type: Optional[HabitFrequencyType] = None
    frequency_config: Optional[Dict[str, Any]] = None
    default_quadrant: Optional[QuadrantType] = None
    goal_desc: Optional[str] = None
    reminder_time: Optional[time] = None
    is_paused: Optional[bool] = None
    is_archived: Optional[bool] = None


class HabitOut(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    color_hex: Optional[str] = None
    frequency_type: HabitFrequencyType
    frequency_config: Optional[Dict[str, Any]] = None
    default_quadrant: QuadrantType
    goal_desc: Optional[str] = None
    reminder_time: Optional[time] = None
    is_paused: bool
    is_archived: bool
    today_todo_id: Optional[int] = Field(None, description="今天对应的待办ID，Task 3 补上生成检查后才会有值")
    today_completed: Optional[bool] = Field(None, description="今天对应的待办是否已完成，None 表示今天未生成（暂停中）")
    streak: Optional[int] = Field(None, description="连续天数，定日型才有值，Task 3 补上")
    week_progress: Optional[str] = Field(None, description="本周进度如'1/3'，弹性型才有值，Task 3 补上")

    class Config:
        from_attributes = True
