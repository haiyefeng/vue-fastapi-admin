from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.core.crud import CRUDBase
from app.models.todo import Goal, Habit, HabitFrequencyType, TodoItem
from app.schemas.habit import HabitCreate, HabitUpdate
from app.utils.time_helpers import to_naive_time


class HabitController(CRUDBase[Habit, HabitCreate, HabitUpdate]):
    def __init__(self):
        super().__init__(model=Habit)

    def _validate_frequency_config(self, frequency_type: HabitFrequencyType, frequency_config: Optional[dict]) -> None:
        config = frequency_config or {}
        if frequency_type == HabitFrequencyType.WEEKLY_DAYS:
            days = config.get("days")
            if not days or not isinstance(days, list) or not all(isinstance(d, int) and 1 <= d <= 7 for d in days):
                raise HTTPException(
                    status_code=400, detail="weekly_days 类型需要 frequency_config.days 为 1-7 的整数列表"
                )
        elif frequency_type == HabitFrequencyType.WEEKLY_COUNT:
            count = config.get("count")
            if not isinstance(count, int) or count < 1:
                raise HTTPException(status_code=400, detail="weekly_count 类型需要 frequency_config.count 为正整数")
        elif frequency_type == HabitFrequencyType.INTERVAL_DAYS:
            interval = config.get("interval")
            if not isinstance(interval, int) or interval < 1:
                raise HTTPException(status_code=400, detail="interval_days 类型需要 frequency_config.interval 为正整数")

    async def _validate_goal(self, goal_id: Optional[int], user_id: int) -> None:
        """确保 goal_id 存在且属于当前用户，否则拒绝而不是让外键约束在 DB 层报错"""
        if goal_id is None:
            return
        exists = await Goal.filter(id=goal_id, user_id=user_id).exists()
        if not exists:
            raise HTTPException(status_code=404, detail="计划不存在")

    async def create_habit(self, obj_in: HabitCreate, user_id: int) -> Habit:
        self._validate_frequency_config(obj_in.frequency_type, obj_in.frequency_config)
        await self._validate_goal(obj_in.goal_id, user_id)
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
        if "goal_id" in update_data:
            await self._validate_goal(update_data["goal_id"], user_id)

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
                data["today_completed"] = None
            else:
                todo = await TodoItem.filter(habit_id=habit.id, generated_date=today).first()
                data["today_todo_id"] = todo.id if todo else None
                data["today_completed"] = todo.is_completed if todo else False

            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT:
                data["streak"] = None
                count = (habit.frequency_config or {}).get("count", 0)
                completed = await self.completed_this_week(habit.id, today)
                data["week_progress"] = f"{completed}/{count}"
            else:
                data["streak"] = await self.calc_streak(habit, today)
                data["week_progress"] = None

            result.append(data)
        return result

    async def ensure_today_generated(self, user_id: int) -> None:
        """惰性生成检查：为该用户所有生效中的习惯，补上今天该生成但还没生成的打卡待办"""
        today = date.today()
        habits = await Habit.filter(user_id=user_id, is_paused=False, is_archived=False)

        for habit in habits:
            should_generate = await self.should_generate_today(habit, today)

            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT and not should_generate:
                week_start, week_end = self.week_range(today)
                await TodoItem.filter(
                    habit_id=habit.id,
                    is_completed=False,
                    generated_date__gte=week_start,
                    generated_date__lte=week_end,
                ).delete()

            if should_generate:
                exists = await TodoItem.filter(habit_id=habit.id, generated_date=today).exists()
                if not exists:
                    # habit.reminder_time 是从 DB 读回的 TimeField，不同后端读回的 python 类型不一致
                    # （MySQL 固定读回 timedelta，SQLite 读回 time 但可能挂着虚假 tzinfo），统一交给
                    # to_naive_time 归一化为纯挂钟时间，详见该函数的说明
                    reminder_time = to_naive_time(habit.reminder_time)
                    reminder_at = datetime.combine(today, reminder_time) if reminder_time else None
                    await TodoItem.create(
                        title=habit.name,
                        habit_id=habit.id,
                        user_id=user_id,
                        quadrant_type=habit.default_quadrant,
                        generated_date=today,
                        due_date=datetime.combine(today, time(23, 59, 59)),
                        reminder_at=reminder_at,
                    )

    async def should_generate_today(self, habit: Habit, today: date) -> bool:
        """今天是否该为该习惯生成打卡待办。

        weekly_count（每周 N 次）不绑定具体星期，要查本周已完成次数才能判定，
        这是本方法独有的有状态分支；其余频率类型是纯粹的日期判定，
        与 summary 逐日回溯共用 is_scheduled_day，避免两处各自维护同一套分支。
        """
        if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT:
            count = (habit.frequency_config or {}).get("count", 0)
            completed = await self.completed_this_week(habit.id, today)
            return completed < count
        return self.is_scheduled_day(habit, today)

    async def completed_this_week(self, habit_id: int, today: date) -> int:
        week_start, week_end = self.week_range(today)
        return await TodoItem.filter(
            habit_id=habit_id, is_completed=True, generated_date__gte=week_start, generated_date__lte=week_end
        ).count()

    async def calc_streak(self, habit: Habit, today: date) -> int:
        streak = 0
        # 从昨天开始回看：今天的打卡待办可能刚生成、还未完成，不能算作"断签"，
        # 连续天数只统计已经完整过去的天数
        cursor = today - timedelta(days=1)
        for _ in range(3650):  # 防止极端配置导致死循环，最多回看 10 年
            if not await self.should_generate_today(habit, cursor):
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
    def week_range(today: date) -> Tuple[date, date]:
        week_start = today - timedelta(days=today.isoweekday() - 1)
        week_end = week_start + timedelta(days=6)
        return week_start, week_end

    def is_scheduled_day(self, habit: Habit, day: date) -> bool:
        """某天是否是该习惯的计划日。纯函数，不查库。

        与 should_generate_today 的区别：那个方法对 weekly_count 要查本周已完成次数，
        是有状态的，没法用来逐日回溯；这里的 weekly_count 一律返回 False，
        因为「每周 N 次」不绑定具体星期，期望次数在 summary 里按周数换算。
        """
        config = habit.frequency_config or {}
        if habit.frequency_type == HabitFrequencyType.DAILY:
            return True
        if habit.frequency_type == HabitFrequencyType.WEEKLY_DAYS:
            return day.isoweekday() in config.get("days", [])
        if habit.frequency_type == HabitFrequencyType.INTERVAL_DAYS:
            interval = config.get("interval", 1)
            anchor = habit.created_at.date()
            diff = (day - anchor).days
            # 必须先判 diff >= 0：习惯创建之前的日子不算计划日；
            # 云函数 habit/index.js:38 有同一守卫
            return diff >= 0 and diff % interval == 0
        return False

    async def summary(self, user_id: int, start: date, end: date, today: date) -> List[Dict[str, Any]]:
        """周期内的习惯坚持度统计，供回顾总结页使用。

        移植自云函数 habit.summary：
        - weekly_count：期望 = 整周数 × 每周次数（不逐日判定）
        - 其余频率：从 max(习惯创建日, start) 逐日走到 min(today, end)，
          计划日计入 expected，当天打卡待办已完成则计入 completed
        统计窗口右端夹到 today，避免把未来的计划日算成「没做到」。
        """
        habits = await Habit.filter(user_id=user_id, is_archived=False, is_paused=False).order_by("-created_at")

        result: List[Dict[str, Any]] = []
        for habit in habits:
            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT:
                count = (habit.frequency_config or {}).get("count", 0)
                total_days = (end - start).days + 1
                expected = (total_days // 7) * count
                completed = await TodoItem.filter(
                    habit_id=habit.id,
                    is_completed=True,
                    generated_date__gte=start,
                    generated_date__lte=end,
                ).count()
                result.append(
                    {
                        "habit_id": habit.id,
                        "name": habit.name,
                        "frequency_type": habit.frequency_type,
                        "completed": completed,
                        "expected": expected,
                        "streak": None,
                    }
                )
                continue

            created_day = habit.created_at.date()
            range_start = max(created_day, start)
            range_end = min(today, end)

            todos = await TodoItem.filter(habit_id=habit.id, generated_date__gte=start, generated_date__lte=end).values(
                "generated_date", "is_completed"
            )
            done_map = {t["generated_date"]: t["is_completed"] for t in todos}

            expected = 0
            completed = 0
            cursor = range_start
            while cursor <= range_end:
                if self.is_scheduled_day(habit, cursor):
                    expected += 1
                    if done_map.get(cursor):
                        completed += 1
                cursor += timedelta(days=1)

            result.append(
                {
                    "habit_id": habit.id,
                    "name": habit.name,
                    "frequency_type": habit.frequency_type,
                    "completed": completed,
                    "expected": expected,
                    "streak": await self.calc_streak(habit, today),
                }
            )

        return result


habit_controller = HabitController()
