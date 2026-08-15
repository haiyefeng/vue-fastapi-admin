from datetime import date, datetime, time
from typing import Any, Dict, List

from app.controllers.habit import habit_controller
from app.controllers.timeblock import time_block_controller
from app.models.todo import TimeBlock, TodoItem


class DashboardController:
    async def get_today_overview(self, user_id: int) -> dict:
        today = date.today()
        task_counts = await self._get_today_task_counts(user_id, today)
        return {
            "date": today,
            "schedule": await self._get_today_schedule(user_id, today),
            "tasks": await self._get_today_tasks(user_id, today),
            "habits": await self._get_today_habits(user_id),
            "completed_task_count": task_counts["completed_task_count"],
            "total_task_count": task_counts["total_task_count"],
        }

    async def _get_today_schedule(self, user_id: int, today: date) -> List[dict]:
        blocks = await time_block_controller.list_by_date_range(user_id, today, today)
        return [
            {
                "id": b.id,
                "todo_item_id": b.todo_item_id,
                "start_time": b.start_time,
                "end_time": b.end_time,
                "title": b.todo_item.title,
                "quadrant_type": b.todo_item.quadrant_type,
            }
            for b in blocks
        ]

    async def _get_today_tasks(self, user_id: int, today: date) -> List[TodoItem]:
        """今日待办：due_date 落在今天，或存在今天的时间块（取并集），排除已完成、排除习惯生成的待办。
        due_date 非空的按时间升序排前面，due_date 为空但靠时间块入选的排最后——用 Python 侧排序，
        不依赖数据库 ORDER BY 对 NULL 的默认位置（SQLite/MySQL 行为不一致，且都不满足这里的排序要求）"""
        day_start = datetime.combine(today, time.min)
        day_end = datetime.combine(today, time.max)

        due_today_ids = await TodoItem.filter(
            user_id=user_id,
            habit_id__isnull=True,
            is_completed=False,
            due_date__gte=day_start,
            due_date__lte=day_end,
        ).values_list("id", flat=True)

        scheduled_today_ids = await TimeBlock.filter(
            user_id=user_id,
            start_time__gte=day_start,
            start_time__lte=day_end,
        ).values_list("todo_item_id", flat=True)

        combined_ids = set(due_today_ids) | set(scheduled_today_ids)
        if not combined_ids:
            return []

        tasks = await TodoItem.filter(id__in=combined_ids, user_id=user_id, is_completed=False, habit_id__isnull=True)
        return sorted(tasks, key=lambda t: (t.due_date is None, t.due_date))

    async def _get_today_task_counts(self, user_id: int, today: date) -> Dict[str, int]:
        """今日待办完成度统计：口径与 _get_today_tasks 一致（due_date 今天或今天排了时间块，
        排除习惯生成的待办），但这里不过滤 is_completed——用于今日概览页顶部的完成度圆环。
        这里独立重新计算 due_today_ids/scheduled_today_ids 的并集，没有复用 _get_today_tasks
        内部已经算过的同一份并集（那个方法只返回过滤后的 List[TodoItem]，没有把并集暴露出来）——
        对个人应用的数据量级，多跑两次这个量级的查询可以忽略不计，不值得为了省这几次查询去改动
        _get_today_tasks 已经过测试验证的返回契约"""
        day_start = datetime.combine(today, time.min)
        day_end = datetime.combine(today, time.max)

        due_today_ids = await TodoItem.filter(
            user_id=user_id,
            habit_id__isnull=True,
            due_date__gte=day_start,
            due_date__lte=day_end,
        ).values_list("id", flat=True)

        scheduled_today_ids = await TimeBlock.filter(
            user_id=user_id, start_time__gte=day_start, start_time__lte=day_end
        ).values_list("todo_item_id", flat=True)

        combined_ids = set(due_today_ids) | set(scheduled_today_ids)
        if not combined_ids:
            return {"completed_task_count": 0, "total_task_count": 0}

        total = await TodoItem.filter(id__in=combined_ids, user_id=user_id, habit_id__isnull=True).count()
        completed = await TodoItem.filter(
            id__in=combined_ids, user_id=user_id, habit_id__isnull=True, is_completed=True
        ).count()
        return {"completed_task_count": completed, "total_task_count": total}

    async def _get_today_habits(self, user_id: int) -> List[Dict[str, Any]]:
        """今日习惯：today_todo_id 非空的（暂停中的、或按频率规则今天不该做的habit会是 None，排除）。
        list_active_with_status 内部会触发 ensure_today_generated——今日概览是这个惰性生成检查
        的合法触发点之一，不是需要规避的副作用"""
        habits = await habit_controller.list_active_with_status(user_id)
        return [h for h in habits if h.get("today_todo_id") is not None]


dashboard_controller = DashboardController()
