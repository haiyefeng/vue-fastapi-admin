from enum import StrEnum
from tortoise import fields

from .base import BaseModel, TimestampMixin


class QuadrantType(StrEnum):
    """四象限类型枚举"""

    URGENT_IMPORTANT = "urgent_important"  # 紧急且重要
    URGENT_NOT_IMPORTANT = "urgent_not_important"  # 紧急但不重要
    IMPORTANT_NOT_URGENT = "important_not_urgent"  # 重要但不紧急
    NOT_URGENT_NOT_IMPORTANT = "not_urgent_not_important"  # 不紧急也不重要


class TodoItem(BaseModel, TimestampMixin):
    """待办事项模型"""

    title = fields.CharField(max_length=200, description="待办事项标题")
    quadrant_type = fields.CharEnumField(QuadrantType, description="象限类型", index=True)
    due_date = fields.DateField(null=True, description="截止日期")
    is_completed = fields.BooleanField(default=False, description="是否已完成", index=True)
    completed_at = fields.DatetimeField(null=True, description="完成时间")
    user = fields.ForeignKeyField("models.User", related_name="todo_items", description="关联用户")

    class Meta:
        table = "todo_item"
