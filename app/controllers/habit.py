from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.core.crud import CRUDBase
from app.models.todo import Habit, HabitFrequencyType, TodoItem
from app.schemas.habit import HabitCreate, HabitUpdate


class HabitController(CRUDBase[Habit, HabitCreate, HabitUpdate]):
    def __init__(self):
        super().__init__(model=Habit)

    def _validate_frequency_config(self, frequency_type: HabitFrequencyType, frequency_config: Optional[dict]) -> None:
        config = frequency_config or {}
        if frequency_type == HabitFrequencyType.WEEKLY_DAYS:
            days = config.get("days")
            if not days or not isinstance(days, list) or not all(isinstance(d, int) and 1 <= d <= 7 for d in days):
                raise HTTPException(status_code=400, detail="weekly_days 类型需要 frequency_config.days 为 1-7 的整数列表")
        elif frequency_type == HabitFrequencyType.WEEKLY_COUNT:
            count = config.get("count")
            if not isinstance(count, int) or count < 1:
                raise HTTPException(status_code=400, detail="weekly_count 类型需要 frequency_config.count 为正整数")
        elif frequency_type == HabitFrequencyType.INTERVAL_DAYS:
            interval = config.get("interval")
            if not isinstance(interval, int) or interval < 1:
                raise HTTPException(status_code=400, detail="interval_days 类型需要 frequency_config.interval 为正整数")

    async def create_habit(self, obj_in: HabitCreate, user_id: int) -> Habit:
        self._validate_frequency_config(obj_in.frequency_type, obj_in.frequency_config)
        return await Habit.create(user_id=user_id, **obj_in.model_dump())

    async def update_habit(self, habit_id: int, obj_in: HabitUpdate, user_id: int) -> Optional[Habit]:
        habit = await Habit.filter(id=habit_id, user_id=user_id).first()
        if not habit:
            return None

        update_data = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        if "frequency_type" in update_data or "frequency_config" in update_data:
            frequency_type = update_data.get("frequency_type", habit.frequency_type)
            frequency_config = update_data.get("frequency_config", habit.frequency_config)
            self._validate_frequency_config(frequency_type, frequency_config)

        await habit.update_from_dict(update_data).save()
        return habit

    async def delete_habit(self, habit_id: int, user_id: int) -> bool:
        deleted_count = await Habit.filter(id=habit_id, user_id=user_id).delete()
        return deleted_count > 0

    async def get_archived_habits(self, user_id: int) -> List[Habit]:
        return await Habit.filter(user_id=user_id, is_archived=True).order_by("-updated_at")

    async def list_active_with_status(self, user_id: int) -> List[Dict[str, Any]]:
        """进行中习惯列表，附带今日生成检查、今日待办ID、连续天数/本周进度"""
        await self.ensure_today_generated(user_id)

        habits = await Habit.filter(user_id=user_id, is_archived=False).order_by("-created_at")
        today = date.today()
        result = []
        for habit in habits:
            data = await habit.to_dict()

            if habit.is_paused:
                data["today_todo_id"] = None
            else:
                todo = await TodoItem.filter(habit_id=habit.id, generated_date=today).first()
                data["today_todo_id"] = todo.id if todo else None

            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT:
                data["streak"] = None
                count = (habit.frequency_config or {}).get("count", 0)
                completed = await self._completed_this_week(habit.id, today)
                data["week_progress"] = f"{completed}/{count}"
            else:
                data["streak"] = await self._calc_streak(habit, today)
                data["week_progress"] = None

            result.append(data)
        return result

    async def ensure_today_generated(self, user_id: int) -> None:
        """惰性生成检查：为该用户所有生效中的习惯，补上今天该生成但还没生成的打卡待办"""
        today = date.today()
        habits = await Habit.filter(user_id=user_id, is_paused=False, is_archived=False)

        for habit in habits:
            should_generate = await self._should_generate_today(habit, today)

            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT and not should_generate:
                week_start, week_end = self._week_range(today)
                await TodoItem.filter(
                    habit_id=habit.id,
                    is_completed=False,
                    generated_date__gte=week_start,
                    generated_date__lte=week_end,
                ).delete()

            if should_generate:
                exists = await TodoItem.filter(habit_id=habit.id, generated_date=today).exists()
                if not exists:
                    # habit.reminder_time 是从 DB 读回的 TimeField：tortoise 在非 UTC 时区下会给它挂上
                    # pytz 时区对象作为 tzinfo，但由于没有日期上下文，pytz 会用 LMT（历史时区，Asia/Shanghai
                    # 为 +8:06 而非 +8:00）兜底，导致 datetime.combine 后的时间被错误偏移几分钟。这里的
                    # reminder_time 本质是纯挂钟时间，用之前先剥离这个虚假 tzinfo，避免污染 reminder_at。
                    reminder_at = (
                        datetime.combine(today, habit.reminder_time.replace(tzinfo=None))
                        if habit.reminder_time
                        else None
                    )
                    await TodoItem.create(
                        title=habit.name,
                        habit_id=habit.id,
                        user_id=user_id,
                        quadrant_type=habit.default_quadrant,
                        generated_date=today,
                        due_date=datetime.combine(today, time(23, 59, 59)),
                        reminder_at=reminder_at,
                    )

    async def _should_generate_today(self, habit: Habit, today: date) -> bool:
        config = habit.frequency_config or {}
        if habit.frequency_type == HabitFrequencyType.DAILY:
            return True
        if habit.frequency_type == HabitFrequencyType.WEEKLY_DAYS:
            return today.isoweekday() in config.get("days", [])
        if habit.frequency_type == HabitFrequencyType.INTERVAL_DAYS:
            interval = config.get("interval", 1)
            anchor = habit.created_at.date()
            return (today - anchor).days % interval == 0
        if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT:
            count = config.get("count", 0)
            completed = await self._completed_this_week(habit.id, today)
            return completed < count
        return False

    async def _completed_this_week(self, habit_id: int, today: date) -> int:
        week_start, week_end = self._week_range(today)
        return await TodoItem.filter(
            habit_id=habit_id, is_completed=True, generated_date__gte=week_start, generated_date__lte=week_end
        ).count()

    async def _calc_streak(self, habit: Habit, today: date) -> int:
        streak = 0
        # 从昨天开始回看：今天的打卡待办可能刚生成、还未完成，不能算作"断签"，
        # 连续天数只统计已经完整过去的天数
        cursor = today - timedelta(days=1)
        for _ in range(3650):  # 防止极端配置导致死循环，最多回看 10 年
            if not await self._should_generate_today(habit, cursor):
                cursor -= timedelta(days=1)
                continue
            todo = await TodoItem.filter(habit_id=habit.id, generated_date=cursor).first()
            if todo and todo.is_completed:
                streak += 1
                cursor -= timedelta(days=1)
            else:
                break
        return streak

    @staticmethod
    def _week_range(today: date) -> Tuple[date, date]:
        week_start = today - timedelta(days=today.isoweekday() - 1)
        week_end = week_start + timedelta(days=6)
        return week_start, week_end


habit_controller = HabitController()
