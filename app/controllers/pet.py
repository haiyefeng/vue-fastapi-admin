"""养成猫业务逻辑。

配置数据（猫 + 台词）全用户共享、只读；用户数据一人一行。
返回体刻意贴合小程序 utils/cat.js 已有的消费格式（cats/lines 带 _id、
通用台词 cat_id 为 "*"），让客户端那份本地缓存与台词求值逻辑零改动。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from tortoise.transactions import in_transaction

from app.models.pet import PetCat, PetLine, PetProfile

# 计数维度：新增维度时在这里加一项，解锁条件与台词条件都能直接引用
STAT_FIELDS = ["todo_completed", "habit_checkin", "review_done", "goal_achieved"]

# 声明式条件求值支持的运算符
OPS = {
    "gte": lambda a, b: a >= b,
    "gt": lambda a, b: a > b,
    "lte": lambda a, b: a <= b,
    "lt": lambda a, b: a < b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
}


def _to_ms(dt: Optional[datetime]) -> int:
    return int(dt.timestamp() * 1000) if dt else 0


class PetController:
    def total_of(self, stats: Optional[dict]) -> int:
        """累计计数总和，驱动成长阶段与解锁"""
        stats = stats or {}
        return sum(int(stats.get(field, 0) or 0) for field in STAT_FIELDS)

    def matches(self, conditions: Optional[list], ctx: dict) -> bool:
        """声明式条件求值：[{field, op, value}]，多条为「与」关系"""
        if not conditions:
            return True
        for cond in conditions:
            fn = OPS.get(cond.get("op"))
            if fn is None:
                return False
            field = cond.get("field")
            left = self.total_of(ctx) if field == "_total" else (ctx.get(field, 0) or 0)
            if not fn(left, cond.get("value")):
                return False
        return True

    async def ensure_profile(self, user_id: int) -> PetProfile:
        """读取用户的猫，不存在则按初始状态创建"""
        profile = await PetProfile.filter(user_id=user_id).first()
        if profile:
            return profile
        return await PetProfile.create(
            user_id=user_id,
            active_cat_code="orange",
            owned_cats=[{"cat_id": "orange", "at": _to_ms(datetime.now())}],
            stats={},
            visit_streak=1,
            last_seen_at=datetime.now(),
        )

    async def apply_unlocks(self, profile: PetProfile) -> List[str]:
        """按 stats 判定应当拥有哪些猫，新解锁的写回并返回（供前端弹提示）"""
        owned = list(profile.owned_cats or [])
        owned_ids = {o.get("cat_id") for o in owned}
        newly: List[str] = []
        now_ms = _to_ms(datetime.now())

        for cat in await PetCat.filter(is_active=True).order_by("order"):
            if cat.code in owned_ids:
                continue
            if self.matches(cat.unlock, profile.stats or {}):
                owned.append({"cat_id": cat.code, "at": now_ms})
                newly.append(cat.code)

        if newly:
            profile.owned_cats = owned
            await profile.save(update_fields=["owned_cats", "updated_at"])
        return newly

    async def touch_visit(self, profile: PetProfile) -> PetProfile:
        """记录来访：跨天才更新，避免同一天反复进页面反复写库"""
        now = datetime.now()
        last = profile.last_seen_at
        if last and last.date() == now.date():
            return profile

        if last and (now - last).days < 2:
            profile.visit_streak = (profile.visit_streak or 0) + 1
        else:
            profile.visit_streak = 1
        profile.last_seen_at = now
        await profile.save(update_fields=["visit_streak", "last_seen_at", "updated_at"])
        return profile

    async def load_config(self) -> Dict[str, Any]:
        """配置版本 = 两张配置表中最大的 updated_at（毫秒）。

        改了台词自动生效，无需手工维护版本号。
        """
        cats = await PetCat.filter(is_active=True).order_by("order")
        lines = await PetLine.all()

        version = 0
        for row in list(cats) + list(lines):
            version = max(version, _to_ms(row.updated_at))

        return {
            "cats": [
                {
                    "_id": c.code,
                    "name": c.name,
                    "persona": c.persona,
                    "order": c.order,
                    "unlock": c.unlock or [],
                }
                for c in cats
            ],
            "lines": [
                {
                    "_id": line.code,
                    # 客户端用字面量 "*" 表示通用台词，这里做一次转换，
                    # 让 utils/cat.js 的过滤逻辑不用改
                    "cat_id": line.cat_code or "*",
                    "page": line.page,
                    "priority": line.priority,
                    "conditions": line.conditions or [],
                    "texts": line.texts or [],
                    "unlock": line.unlock or [],
                }
                for line in lines
            ],
            "version": version,
        }

    async def update_profile(self, user_id: int, active_cat_id: Optional[str], pet_name: Optional[str]) -> PetProfile:
        """更新用户的猫。切换到未解锁的猫会抛 ValueError，由路由转成 400。"""
        profile = await self.ensure_profile(user_id)
        fields = ["updated_at"]

        if active_cat_id is not None:
            owned = {o.get("cat_id") for o in (profile.owned_cats or [])}
            if active_cat_id not in owned:
                raise ValueError("这只猫还没解锁")
            profile.active_cat_code = active_cat_id
            fields.append("active_cat_code")

        if pet_name is not None:
            profile.pet_name = str(pet_name)[:20]
            fields.append("pet_name")

        await profile.save(update_fields=fields)
        return profile

    async def increment(self, user_id: int, field: str, delta: int = 1) -> None:
        """累加某个计数维度。只增不减。

        stats 是 JSON 字段，没法用 F() 原子自增，所以整行加锁读-改-写；
        不加锁的话，同时完成两个任务会丢计数。
        """
        if field not in STAT_FIELDS:
            raise ValueError(f"未知的计数维度: {field}")

        async with in_transaction():
            profile = await PetProfile.filter(user_id=user_id).select_for_update().first()
            if profile is None:
                profile = await self.ensure_profile(user_id)
                profile = await PetProfile.filter(id=profile.id).select_for_update().first()

            stats = dict(profile.stats or {})
            stats[field] = int(stats.get(field, 0) or 0) + delta
            profile.stats = stats
            await profile.save(update_fields=["stats", "updated_at"])

    def profile_out(self, profile: PetProfile) -> Dict[str, Any]:
        """客户端 saveBootstrap 消费的字段集合"""
        return {
            "active_cat_id": profile.active_cat_code,
            "pet_name": profile.pet_name or "",
            "stats": profile.stats or {},
            "owned_cats": profile.owned_cats or [],
            "visit_streak": profile.visit_streak or 0,
            "last_seen_at": _to_ms(profile.last_seen_at),
        }


pet_controller = PetController()
