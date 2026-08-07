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
    due_date = fields.DatetimeField(null=True, description="截止时间")
    notes = fields.TextField(null=True, description="备注信息")
    project = fields.ForeignKeyField(
        "models.Project",
        related_name="tasks",
        null=True,
        on_delete=fields.SET_NULL,
        description="所属项目，为空则属于收件箱",
    )
    reminder_at = fields.DatetimeField(null=True, description="提醒时间，仅存储与展示，不做推送")
    is_completed = fields.BooleanField(default=False, description="是否已完成", index=True)
    completed_at = fields.DatetimeField(null=True, description="完成时间")
    user_id = fields.IntField(description="用户ID", index=True)

    class Meta:
        table = "todo_item"


class CategoryType(StrEnum):
    SYSTEM_PREDEFINED = "system_predefined"
    USER_CUSTOM = "user_custom"


class Category(BaseModel, TimestampMixin):
    id = fields.IntField(pk=True, description="分类ID")
    user = fields.ForeignKeyField(
        "models.User", related_name="categories", null=True, description="所属用户 (系统预设可为NULL)"
    )
    name = fields.CharField(max_length=100, description="分类名称")
    icon = fields.CharField(max_length=50, null=True, description="图标 (FontAwesome class 或 emoji)")
    type = fields.CharEnumField(CategoryType, default=CategoryType.USER_CUSTOM, description="分类类型")
    display_order = fields.IntField(default=0, description="显示顺序")
    is_archived = fields.BooleanField(default=False, description="是否归档")

    # 反向关系
    projects: fields.ReverseRelation["Project"]

    class Meta:
        table = "categories"
        unique_together = (("user", "name"),)  # 如果用户自定义分类名称需要唯一

    def __str__(self):
        return self.name


class ProjectType(StrEnum):
    PROJECT = "project"
    LIST = "list"


class Project(BaseModel, TimestampMixin):
    id = fields.IntField(pk=True, description="项目/清单ID")
    user = fields.ForeignKeyField("models.User", related_name="projects", description="所属用户")
    category = fields.ForeignKeyField("models.Category", related_name="projects", null=True, description="所属分类")
    name = fields.CharField(max_length=100, description="项目/清单名称")
    type = fields.CharEnumField(ProjectType, default=ProjectType.PROJECT, description="类型 (项目或清单)")
    color_hex = fields.CharField(max_length=7, null=True, description="颜色代码 (如 #RRGGBB)")
    is_archived = fields.BooleanField(default=False, description="是否归档")

    # 反向关系
    tasks: fields.ReverseRelation["TodoItem"]

    class Meta:
        table = "projects"

    def __str__(self):
        return self.name


class SubTask(BaseModel, TimestampMixin):
    """子任务模型"""

    todo_item = fields.ForeignKeyField(
        "models.TodoItem", related_name="subtasks", on_delete=fields.CASCADE, description="所属待办事项"
    )
    title = fields.CharField(max_length=200, description="子任务标题")
    is_completed = fields.BooleanField(default=False, description="是否已完成")
    order = fields.IntField(default=0, description="显示顺序，创建时按序递增赋值")

    class Meta:
        table = "sub_task"

    def __str__(self):
        return self.title
