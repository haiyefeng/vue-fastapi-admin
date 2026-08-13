from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

from tortoise.functions import Count

from app.core.crud import CRUDBase
from app.models.todo import (
    Category,
    Goal,
    Habit,
    HabitFrequencyType,
    QuadrantType,
    Review,
    ReviewPeriodType,
    ReviewStatus,
    TodoItem,
)
from app.schemas.review import ReviewSaveIn


def _add_months(d: date, months: int) -> date:
    """按月数偏移，返回该月 1 号；用于计算月/季度周期的结束边界（下个周期起点减一天）"""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


class ReviewController(CRUDBase[Review, ReviewSaveIn, ReviewSaveIn]):
    def __init__(self):
        super().__init__(model=Review)

    @staticmethod
    def calc_period_range(period_type: ReviewPeriodType, anchor_date: date) -> Tuple[date, date]:
        """根据周期类型和锚点日期（周期内任意一天）计算周期起止日期"""
        if period_type == ReviewPeriodType.WEEK:
            start = anchor_date - timedelta(days=anchor_date.isoweekday() - 1)
            end = start + timedelta(days=6)
        elif period_type == ReviewPeriodType.MONTH:
            start = anchor_date.replace(day=1)
            end = _add_months(start, 1) - timedelta(days=1)
        elif period_type == ReviewPeriodType.QUARTER:
            quarter_start_month = ((anchor_date.month - 1) // 3) * 3 + 1
            start = anchor_date.replace(month=quarter_start_month, day=1)
            end = _add_months(start, 3) - timedelta(days=1)
        else:  # ReviewPeriodType.YEAR
            start = anchor_date.replace(month=1, day=1)
            end = anchor_date.replace(month=12, day=31)
        return start, end

    async def save_review(self, obj_in: ReviewSaveIn, user_id: int) -> Review:
        """同一用户同一周期类型同一起始日只保留一条记录：存在则覆盖更新，不存在则创建"""
        period_start, period_end = self.calc_period_range(obj_in.period_type, obj_in.anchor_date)
        review = await Review.filter(
            user_id=user_id, period_type=obj_in.period_type, period_start=period_start
        ).first()
        if review:
            await review.update_from_dict(
                {"period_end": period_end, "answers": obj_in.answers, "status": obj_in.status}
            ).save()
            return review
        return await Review.create(
            user_id=user_id,
            period_type=obj_in.period_type,
            period_start=period_start,
            period_end=period_end,
            answers=obj_in.answers,
            status=obj_in.status,
        )

    async def get_review_detail(
        self, period_type: ReviewPeriodType, anchor_date: date, user_id: int
    ) -> Optional[Review]:
        period_start, _ = self.calc_period_range(period_type, anchor_date)
        return await Review.filter(user_id=user_id, period_type=period_type, period_start=period_start).first()

    async def get_review_list(
        self, user_id: int, period_type: Optional[ReviewPeriodType] = None
    ) -> List[Review]:
        query = Review.filter(user_id=user_id)
        if period_type:
            query = query.filter(period_type=period_type)
        return await query.order_by("-period_start")

    async def get_data_summary(self, user_id: int, period_type: ReviewPeriodType, anchor_date: date) -> dict:
        """数据回顾聚合：不依赖 Review 记录是否存在，纯只读查询，可重复调用"""
        period_start, period_end = self.calc_period_range(period_type, anchor_date)
        return {
            "period_start": period_start,
            "period_end": period_end,
            "task_completion": await self._get_task_completion_summary(user_id, period_start, period_end),
            "habits": await self._get_habit_checkin_summary(user_id, period_start, period_end),
            "goals": await self._get_goal_progress_summary(user_id, period_start, period_end),
        }

    async def _get_task_completion_summary(self, user_id: int, period_start: date, period_end: date) -> dict:
        day_start = datetime.combine(period_start, time.min)
        day_end = datetime.combine(period_end, time.max)
        common_filter = dict(
            user_id=user_id, habit_id__isnull=True, due_date__gte=day_start, due_date__lte=day_end
        )

        total = await TodoItem.filter(**common_filter).count()
        completed = await TodoItem.filter(**common_filter, is_completed=True).count()
        urgent_important_total = await TodoItem.filter(
            **common_filter, quadrant_type=QuadrantType.URGENT_IMPORTANT
        ).count()
        urgent_important_completed = await TodoItem.filter(
            **common_filter, quadrant_type=QuadrantType.URGENT_IMPORTANT, is_completed=True
        ).count()

        category_totals = (
            await TodoItem.filter(**common_filter, project__category_id__isnull=False)
            .annotate(cnt=Count("id"))
            .group_by("project__category_id")
            .values("project__category_id", "cnt")
        )
        category_completed_rows = (
            await TodoItem.filter(**common_filter, project__category_id__isnull=False, is_completed=True)
            .annotate(cnt=Count("id"))
            .group_by("project__category_id")
            .values("project__category_id", "cnt")
        )
        completed_map = {row["project__category_id"]: row["cnt"] for row in category_completed_rows}

        category_ids = [row["project__category_id"] for row in category_totals]
        categories = await Category.filter(id__in=category_ids).values("id", "name")
        name_map = {c["id"]: c["name"] for c in categories}

        by_category = [
            {
                "category_id": row["project__category_id"],
                "category_name": name_map.get(row["project__category_id"], ""),
                "total": row["cnt"],
                "completed": completed_map.get(row["project__category_id"], 0),
            }
            for row in category_totals
        ]

        return {
            "total": total,
            "completed": completed,
            "urgent_important_total": urgent_important_total,
            "urgent_important_completed": urgent_important_completed,
            "by_category": by_category,
        }

    async def _get_habit_checkin_summary(self, user_id: int, period_start: date, period_end: date) -> List[dict]:
        from app.controllers.habit import habit_controller

        habits = await Habit.filter(user_id=user_id, is_archived=False, is_paused=False)
        today = date.today()
        result = []
        for habit in habits:
            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT:
                count = (habit.frequency_config or {}).get("count", 0)
                total_days = (period_end - period_start).days + 1
                full_weeks = total_days // 7
                expected = full_weeks * count
                completed = await TodoItem.filter(
                    habit_id=habit.id,
                    is_completed=True,
                    generated_date__gte=period_start,
                    generated_date__lte=period_end,
                ).count()
                streak = None
            else:
                expected = 0
                completed = 0
                cursor = period_start
                while cursor <= period_end:
                    if await habit_controller.should_generate_today(habit, cursor):
                        expected += 1
                        todo = await TodoItem.filter(habit_id=habit.id, generated_date=cursor).first()
                        if todo and todo.is_completed:
                            completed += 1
                    cursor += timedelta(days=1)
                streak = await habit_controller.calc_streak(habit, today)

            result.append(
                {
                    "habit_id": habit.id,
                    "name": habit.name,
                    "frequency_type": habit.frequency_type,
                    "completed": completed,
                    "expected": expected,
                    "streak": streak,
                }
            )
        return result

    async def _get_goal_progress_summary(self, user_id: int, period_start: date, period_end: date) -> List[dict]:
        goals = await Goal.filter(user_id=user_id, is_archived=False)
        day_start = datetime.combine(period_start, time.min)
        day_end = datetime.combine(period_end, time.max)
        result = []
        for goal in goals:
            total_linked = await TodoItem.filter(goal_id=goal.id).count()
            newly_completed = await TodoItem.filter(
                goal_id=goal.id, is_completed=True, completed_at__gte=day_start, completed_at__lte=day_end
            ).count()
            progress_percent = round(newly_completed / total_linked * 100, 1) if total_linked else None
            result.append(
                {
                    "goal_id": goal.id,
                    "name": goal.name,
                    "newly_completed": newly_completed,
                    "total_linked_tasks": total_linked,
                    "progress_percent": progress_percent,
                }
            )
        return result


review_controller = ReviewController()
