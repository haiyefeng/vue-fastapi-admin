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
    habit = fields.ForeignKeyField(
        "models.Habit",
        related_name="todos",
        null=True,
        on_delete=fields.CASCADE,
        description="所属习惯，非空表示是习惯生成的打卡待办",
    )
    generated_date = fields.DateField(
        null=True,
        description="习惯待办的所属日期，仅习惯生成的待办有值；用于幂等判断，与用户可改的 due_date 语义分离",
    )
    goal = fields.ForeignKeyField(
        "models.Goal", related_name="todos", null=True, on_delete=fields.SET_NULL,
        description="关联的计划，为空表示未关联",
    )
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


class TimeBlock(BaseModel, TimestampMixin):
    """时间块模型：一个待办事项可以有多个时间块，用于日历排程"""

    todo_item = fields.ForeignKeyField(
        "models.TodoItem", related_name="time_blocks", on_delete=fields.CASCADE, description="所属待办事项"
    )
    user = fields.ForeignKeyField(
        "models.User", related_name="time_blocks", description="所属用户，冗余存储，按用户+日期范围直查"
    )
    start_time = fields.DatetimeField(description="开始时间")
    end_time = fields.DatetimeField(description="结束时间")

    class Meta:
        table = "time_block"

    def __str__(self):
        return f"{self.start_time} - {self.end_time}"


class HabitFrequencyType(StrEnum):
    DAILY = "daily"
    WEEKLY_DAYS = "weekly_days"  # 每周固定几天，如周一三五
    WEEKLY_COUNT = "weekly_count"  # 每周任意 N 次（弹性型）
    INTERVAL_DAYS = "interval_days"  # 每隔 N 天一次


class Habit(BaseModel, TimestampMixin):
    """习惯模型：按频率规则惰性生成带 habit_id 的 TodoItem，勾掉即打卡"""

    user = fields.ForeignKeyField("models.User", related_name="habits", description="所属用户")
    name = fields.CharField(max_length=100, description="习惯名称")
    icon = fields.CharField(max_length=50, null=True, description="图标，emoji 或简短文本")
    color_hex = fields.CharField(max_length=7, null=True, description="颜色代码")
    frequency_type = fields.CharEnumField(HabitFrequencyType, description="频率类型")
    frequency_config = fields.JSONField(
        null=True,
        description=(
            'weekly_days: {"days": [1,3,5]}（ISO 星期一=1）；'
            'weekly_count: {"count": 3}；interval_days: {"interval": 2}；daily 不需要配置'
        ),
    )
    default_quadrant = fields.CharEnumField(
        QuadrantType, default=QuadrantType.IMPORTANT_NOT_URGENT, description="生成待办的默认象限"
    )
    goal_desc = fields.CharField(max_length=100, null=True, description="目标描述，如「30分钟」，仅展示")
    reminder_time = fields.TimeField(null=True, description="每日提醒时间，写入生成待办的 reminder_at")
    is_paused = fields.BooleanField(default=False, description="暂停后停止生成新待办，历史保留")
    is_archived = fields.BooleanField(default=False, description="归档后从主列表隐藏，历史保留")
    goal = fields.ForeignKeyField(
        "models.Goal", related_name="habits", null=True, on_delete=fields.SET_NULL,
        description="关联的计划，为空表示未关联",
    )

    class Meta:
        table = "habit"

    def __str__(self):
        return self.name


class Goal(BaseModel, TimestampMixin):
    """计划/目标模型"""

    user = fields.ForeignKeyField("models.User", related_name="goals", description="所属用户")
    name = fields.CharField(max_length=100, description="计划/目标名称")
    description = fields.TextField(null=True, description="描述")
    target_date = fields.DateField(null=True, description="目标完成日期")
    category = fields.ForeignKeyField(
        "models.Category", related_name="goals", null=True, description="归属分类"
    )
    is_archived = fields.BooleanField(default=False, description="归档后从主列表隐藏，历史保留")

    class Meta:
        table = "goal"

    def __str__(self):
        return self.name


class ReviewPeriodType(StrEnum):
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    COMPLETED = "completed"


class Review(BaseModel, TimestampMixin):
    """周期回顾模型：数据回顾区实时聚合计算不落库，这里只存七步反思答案与状态"""

    user = fields.ForeignKeyField("models.User", related_name="reviews", description="所属用户")
    period_type = fields.CharEnumField(ReviewPeriodType, description="回顾周期类型")
    period_start = fields.DateField(description="周期开始日期")
    period_end = fields.DateField(description="周期结束日期")
    answers = fields.JSONField(default=dict, description="七步提问法答案，key 为 step1~step7")
    status = fields.CharEnumField(ReviewStatus, default=ReviewStatus.DRAFT, description="草稿/已完成")

    class Meta:
        table = "review"
        unique_together = (("user", "period_type", "period_start"),)

    def __str__(self):
        return f"{self.period_type} {self.period_start}"
