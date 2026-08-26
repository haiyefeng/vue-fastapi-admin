from tortoise import fields

from .base import BaseModel, TimestampMixin


class PetProfile(BaseModel, TimestampMixin):
    """养成猫的用户状态，一人一行。

    stats / owned_cats 用 JSON 而非独立表：这两份数据只按 user 单行读写、
    从不跨用户查询，拆成关系表并换不来查询能力，反而多两次 JOIN。
    """

    user = fields.OneToOneField("models.User", related_name="pet_profile", description="所属用户")
    active_cat_code = fields.CharField(max_length=32, default="orange", description="当前陪伴的猫")
    pet_name = fields.CharField(max_length=20, null=True, description="用户给猫起的名字")
    stats = fields.JSONField(default=dict, description="分维度累计计数，键为维度名、值为累计次数")
    owned_cats = fields.JSONField(default=list, description="已解锁的猫，元素含 cat_id 与解锁时间戳 at")
    visit_streak = fields.IntField(default=1, description="连续来访天数")
    last_seen_at = fields.DatetimeField(null=True, description="最近一次来访时间")

    class Meta:
        table = "pet_profile"


class PetCat(BaseModel, TimestampMixin):
    """猫的定义，全用户共享的只读配置"""

    code = fields.CharField(max_length=32, unique=True, description="猫的标识，如 orange", index=True)
    name = fields.CharField(max_length=32, description="猫的名字，如 橘猫")
    persona = fields.CharField(max_length=32, description="性格，如 元气/毒舌/温柔")
    order = fields.IntField(default=0, description="展示顺序")
    unlock = fields.JSONField(default=list, description="解锁条件，[{field, op, value}] 与关系；空数组表示初始猫")
    is_active = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "pet_cat"


class PetLine(BaseModel, TimestampMixin):
    """猫的台词，全用户共享的只读配置"""

    code = fields.CharField(max_length=64, unique=True, description="台词标识，如 t_overdue", index=True)
    cat_code = fields.CharField(max_length=32, null=True, description="专属于哪只猫；为空表示通用兜底", index=True)
    page = fields.CharField(max_length=32, description="生效页面：today/quadrant/habit/pet 等", index=True)
    priority = fields.IntField(default=0, description="优先级，同页面取最高的一条")
    conditions = fields.JSONField(default=list, description="页面上下文触发条件，[{field, op, value}]")
    texts = fields.JSONField(default=list, description="文案变体数组，客户端按日期种子轮换")
    unlock = fields.JSONField(default=list, description="解锁条件；未达成时这句话不会出现")

    class Meta:
        table = "pet_line"
