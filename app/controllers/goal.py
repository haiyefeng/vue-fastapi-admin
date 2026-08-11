from typing import Dict, List, Optional, Tuple

from tortoise.expressions import Q
from tortoise.functions import Count

from app.controllers.category import category_controller
from app.core.crud import CRUDBase
from app.models.todo import Category, Goal, Habit, TodoItem
from app.schemas.goal import GoalCreate, GoalUpdate


class GoalController(CRUDBase[Goal, GoalCreate, GoalUpdate]):
    def __init__(self):
        super().__init__(model=Goal)

    async def create_goal(self, obj_in: GoalCreate, user_id: int) -> Goal:
        category_id = await self._resolve_category(user_id, obj_in.category_id, obj_in.category_name)
        return await Goal.create(
            user_id=user_id,
            name=obj_in.name,
            description=obj_in.description,
            target_date=obj_in.target_date,
            category_id=category_id,
        )

    async def update_goal(self, goal_id: int, obj_in: GoalUpdate, user_id: int) -> Optional[Goal]:
        goal = await Goal.filter(id=goal_id, user_id=user_id).first()
        if not goal:
            return None

        update_data = obj_in.model_dump(exclude_unset=True, exclude={"id", "category_id", "category_name"})
        if "category_id" in obj_in.model_fields_set or "category_name" in obj_in.model_fields_set:
            update_data["category_id"] = await self._resolve_category(
                user_id, obj_in.category_id, obj_in.category_name
            )

        await goal.update_from_dict(update_data).save()
        return goal

    async def delete_goal(self, goal_id: int, user_id: int) -> bool:
        deleted_count = await Goal.filter(id=goal_id, user_id=user_id).delete()
        return deleted_count > 0

    async def get_active_goals(self, user_id: int) -> List[Goal]:
        return await Goal.filter(user_id=user_id, is_archived=False).order_by("-created_at")

    async def get_archived_goals(self, user_id: int) -> List[Goal]:
        return await Goal.filter(user_id=user_id, is_archived=True).order_by("-updated_at")

    async def to_out_dict(self, goal: Goal) -> dict:
        data = await goal.to_dict()
        category_name = None
        if goal.category_id:
            category = await goal.category
            category_name = category.name if category else None
        data["category_name"] = category_name
        return data

    async def get_task_counts(self, goal_ids: List[int]) -> Dict[int, Tuple[int, int]]:
        """一次聚合查询算出每个计划关联任务的总数/已完成数，避免列表页 N+1"""
        if not goal_ids:
            return {}
        totals = (
            await TodoItem.filter(goal_id__in=goal_ids)
            .annotate(cnt=Count("id"))
            .group_by("goal_id")
            .values("goal_id", "cnt")
        )
        completed = (
            await TodoItem.filter(goal_id__in=goal_ids, is_completed=True)
            .annotate(cnt=Count("id"))
            .group_by("goal_id")
            .values("goal_id", "cnt")
        )
        total_map = {row["goal_id"]: row["cnt"] for row in totals}
        completed_map = {row["goal_id"]: row["cnt"] for row in completed}
        return {gid: (total_map.get(gid, 0), completed_map.get(gid, 0)) for gid in goal_ids}

    async def get_habit_counts(self, goal_ids: List[int]) -> Dict[int, int]:
        """一次聚合查询算出每个计划关联的习惯数量"""
        if not goal_ids:
            return {}
        rows = (
            await Habit.filter(goal_id__in=goal_ids)
            .annotate(cnt=Count("id"))
            .group_by("goal_id")
            .values("goal_id", "cnt")
        )
        return {row["goal_id"]: row["cnt"] for row in rows}

    async def _resolve_category(
        self, user_id: int, category_id: Optional[int], category_name: Optional[str]
    ) -> Optional[int]:
        if category_id is not None:
            category = await Category.filter(
                Q(id=category_id, user_id=user_id) | Q(id=category_id, user_id__isnull=True)
            ).first()
            if category:
                return category_id
        if category_name:
            category = await category_controller.get_or_create(user_id, category_name)
            return category.id
        return None


goal_controller = GoalController()
