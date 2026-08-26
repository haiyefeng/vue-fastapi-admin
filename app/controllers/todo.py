from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from tortoise.expressions import Q
from tortoise.functions import Count

from app.controllers.pet import pet_controller
from app.core.crud import CRUDBase
from app.models.todo import Goal, Project, QuadrantType, TimeBlock, TodoItem
from app.schemas.todo import (
    QuadrantStatistics,
    TodoItemCreate,
    TodoItemUpdate,
    TodoStatisticsByDate,
)


class TodoController(CRUDBase[TodoItem, TodoItemCreate, TodoItemUpdate]):
    def __init__(self):
        super().__init__(model=TodoItem)

    async def _validate_project(self, project_id: Optional[int], user_id: int) -> None:
        """确保 project_id 存在且属于当前用户，否则拒绝而不是让外键约束在 DB 层报错"""
        if project_id is None:
            return
        exists = await Project.filter(id=project_id, user_id=user_id).exists()
        if not exists:
            raise HTTPException(status_code=404, detail="项目不存在")

    async def _validate_goal(self, goal_id: Optional[int], user_id: int) -> None:
        """确保 goal_id 存在且属于当前用户，否则拒绝而不是让外键约束在 DB 层报错"""
        if goal_id is None:
            return
        exists = await Goal.filter(id=goal_id, user_id=user_id).exists()
        if not exists:
            raise HTTPException(status_code=404, detail="计划不存在")

    async def create_todo(self, obj_in: TodoItemCreate, user_id: int) -> TodoItem:
        """创建待办事项，可同时提交多个时间块（周视图拖拽/多选创建）"""
        await self._validate_project(obj_in.project_id, user_id)
        await self._validate_goal(obj_in.goal_id, user_id)
        if obj_in.time_blocks:
            for block in obj_in.time_blocks:
                if block.end_time <= block.start_time:
                    raise HTTPException(status_code=400, detail="time_blocks 中 end_time 必须晚于 start_time")
                if block.start_time.date() != block.end_time.date():
                    raise HTTPException(status_code=400, detail="time_blocks 不能跨天")

        todo_dict = obj_in.model_dump(exclude={"time_blocks"})
        todo = TodoItem(**todo_dict, user_id=user_id)
        await todo.save()

        if obj_in.time_blocks:
            await TimeBlock.bulk_create(
                [
                    TimeBlock(todo_item_id=todo.id, user_id=user_id, start_time=b.start_time, end_time=b.end_time)
                    for b in obj_in.time_blocks
                ]
            )
        return todo

    async def get_todos_by_user(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        quadrant_type: Optional[str] = None,
        is_completed: Optional[bool] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        completed_start: Optional[date] = None,
        completed_end: Optional[date] = None,
        project_id: Optional[int] = None,
        inbox_only: Optional[bool] = None,
        unscheduled_only: Optional[bool] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Tuple[int, List[TodoItem]]:
        """获取用户的待办事项列表"""
        query = Q(user_id=user_id)

        if quadrant_type:
            quadrants = [q.strip() for q in quadrant_type.split(",") if q.strip()]
            if quadrants:
                query &= Q(quadrant_type__in=quadrants)

        if is_completed is not None:
            query &= Q(is_completed=is_completed)

        if start_date:
            query &= Q(created_at__gte=datetime.combine(start_date, datetime.min.time()))

        if end_date:
            query &= Q(created_at__lte=datetime.combine(end_date, datetime.max.time()))

        # 完成时间范围。与 start_date/end_date（筛创建时间）是两组独立参数，
        # 统计页要的是「这段时间内完成了什么」，用的是这一组。
        if completed_start:
            query &= Q(completed_at__gte=datetime.combine(completed_start, datetime.min.time()))

        if completed_end:
            query &= Q(completed_at__lte=datetime.combine(completed_end, datetime.max.time()))

        if inbox_only:
            query &= Q(project_id__isnull=True)
        elif project_id is not None:
            query &= Q(project_id=project_id)

        if unscheduled_only:
            from app.controllers.timeblock import time_block_controller

            scheduled_ids = await time_block_controller.get_scheduled_todo_ids(user_id)
            query &= Q(is_completed=False)
            if scheduled_ids:
                query &= ~Q(id__in=scheduled_ids)

        if sort_by is None:
            order = ["-created_at"]
        else:
            field = sort_by if sort_by in ("due_date", "quadrant_type", "created_at", "completed_at") else "created_at"
            direction = "-" if sort_order == "desc" else ""
            order = [f"{direction}{field}"]

        return await self.list(page=page, page_size=page_size, search=query, order=order)

    async def update_todo(self, todo_id: int, obj_in: TodoItemUpdate, user_id: int) -> Optional[TodoItem]:
        """更新待办事项"""
        todo = await self.model.filter(id=todo_id, user_id=user_id).first()
        if not todo:
            return None

        if "project_id" in obj_in.model_fields_set:
            await self._validate_project(obj_in.project_id, user_id)
        if "goal_id" in obj_in.model_fields_set:
            await self._validate_goal(obj_in.goal_id, user_id)

        update_data = obj_in.model_dump(exclude_unset=True)

        # 如果设置为已完成，并且之前未完成，则设置完成时间
        just_completed = bool(obj_in.is_completed) and not todo.is_completed
        if just_completed:
            update_data["completed_at"] = datetime.now()
        # 如果设置为未完成，则清除完成时间
        elif obj_in.is_completed is False:
            update_data["completed_at"] = None

        await todo.update_from_dict(update_data).save()

        # 养成猫计数：只在「由未完成变为已完成」时 +1，取消完成不回滚（与小程序云函数行为一致）
        if just_completed:
            await pet_controller.increment(user_id, "todo_completed")

        return todo

    async def delete_todo(self, todo_id: int, user_id: int) -> bool:
        """删除待办事项"""
        deleted_count = await self.model.filter(id=todo_id, user_id=user_id).delete()
        return deleted_count > 0

    async def get_statistics_by_date(
        self, user_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[TodoStatisticsByDate]:
        """获取按日期统计的待办事项数量：一次查询取出范围内所有已完成待办的 (完成日期, 象限)，
        在内存中按天/象限归位，避免按天 x 象限循环发起 count() 查询（30 天 x 4 象限 = 120 次独立查询）"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        day_start = datetime.combine(start_date, datetime.min.time())
        day_end = datetime.combine(end_date, datetime.max.time())

        rows = await TodoItem.filter(
            user_id=user_id,
            habit_id__isnull=True,
            completed_at__gte=day_start,
            completed_at__lte=day_end,
        ).values("completed_at", "quadrant_type")

        counts: Dict[Tuple[date, str], int] = {}
        for row in rows:
            key = (row["completed_at"].date(), row["quadrant_type"])
            counts[key] = counts.get(key, 0) + 1

        result = []
        current_date = start_date
        while current_date <= end_date:
            stats = TodoStatisticsByDate(date=current_date)
            stats.urgent_important = counts.get((current_date, QuadrantType.URGENT_IMPORTANT), 0)
            stats.urgent_not_important = counts.get((current_date, QuadrantType.URGENT_NOT_IMPORTANT), 0)
            stats.important_not_urgent = counts.get((current_date, QuadrantType.IMPORTANT_NOT_URGENT), 0)
            stats.not_urgent_not_important = counts.get((current_date, QuadrantType.NOT_URGENT_NOT_IMPORTANT), 0)
            stats.total = (
                stats.urgent_important
                + stats.urgent_not_important
                + stats.important_not_urgent
                + stats.not_urgent_not_important
            )
            result.append(stats)
            current_date += timedelta(days=1)

        return result

    async def get_quadrant_statistics(self, user_id: int) -> QuadrantStatistics:
        """获取按象限统计的待办事项数量"""
        stats = QuadrantStatistics()

        # 统计各象限的待办事项数量
        for quadrant in QuadrantType:
            count = await TodoItem.filter(user_id=user_id, quadrant_type=quadrant, habit_id__isnull=True).count()

            # 根据象限类型设置相应的字段
            if quadrant == QuadrantType.URGENT_IMPORTANT:
                stats.urgent_important = count
            elif quadrant == QuadrantType.URGENT_NOT_IMPORTANT:
                stats.urgent_not_important = count
            elif quadrant == QuadrantType.IMPORTANT_NOT_URGENT:
                stats.important_not_urgent = count
            elif quadrant == QuadrantType.NOT_URGENT_NOT_IMPORTANT:
                stats.not_urgent_not_important = count

        stats.total = (
            stats.urgent_important
            + stats.urgent_not_important
            + stats.important_not_urgent
            + stats.not_urgent_not_important
        )

        return stats


todo_controller = TodoController()
