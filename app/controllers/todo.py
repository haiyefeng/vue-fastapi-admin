from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from tortoise.expressions import Q
from tortoise.functions import Count

from app.core.crud import CRUDBase
from app.models.todo import QuadrantType, TodoItem
from app.schemas.todo import (
    QuadrantStatistics,
    TodoItemCreate,
    TodoItemUpdate,
    TodoStatisticsByDate,
)


class TodoController(CRUDBase[TodoItem, TodoItemCreate, TodoItemUpdate]):
    def __init__(self):
        super().__init__(model=TodoItem)

    async def create_todo(self, obj_in: TodoItemCreate, user_id: int) -> TodoItem:
        """创建待办事项"""
        todo_dict = obj_in.model_dump()
        todo = TodoItem(**todo_dict, user_id=user_id)
        await todo.save()
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
        project_id: Optional[int] = None,
        inbox_only: Optional[bool] = None,
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

        if inbox_only:
            query &= Q(project_id__isnull=True)
        elif project_id is not None:
            query &= Q(project_id=project_id)

        if sort_by is None:
            order = ["-created_at"]
        else:
            field = sort_by if sort_by in ("due_date", "quadrant_type", "created_at") else "created_at"
            direction = "-" if sort_order == "desc" else ""
            order = [f"{direction}{field}"]

        return await self.list(page=page, page_size=page_size, search=query, order=order)

    async def update_todo(self, todo_id: int, obj_in: TodoItemUpdate, user_id: int) -> Optional[TodoItem]:
        """更新待办事项"""
        todo = await self.model.filter(id=todo_id, user_id=user_id).first()
        if not todo:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)

        # 如果设置为已完成，并且之前未完成，则设置完成时间
        if obj_in.is_completed and not todo.is_completed:
            update_data["completed_at"] = datetime.now()
        # 如果设置为未完成，则清除完成时间
        elif obj_in.is_completed is False:
            update_data["completed_at"] = None

        await todo.update_from_dict(update_data).save()
        return todo

    async def delete_todo(self, todo_id: int, user_id: int) -> bool:
        """删除待办事项"""
        deleted_count = await self.model.filter(id=todo_id, user_id=user_id).delete()
        return deleted_count > 0

    async def get_statistics_by_date(
        self, user_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[TodoStatisticsByDate]:
        """获取按日期统计的待办事项数量"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        result = []
        current_date = start_date
        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date, datetime.max.time())

            stats = TodoStatisticsByDate(date=current_date)

            # 统计各象限的已完成数量
            for quadrant in QuadrantType:
                count = await TodoItem.filter(
                    user_id=user_id, quadrant_type=quadrant, completed_at__gte=day_start, completed_at__lte=day_end
                ).count()

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

            result.append(stats)
            current_date += timedelta(days=1)

        return result

    async def get_quadrant_statistics(self, user_id: int) -> QuadrantStatistics:
        """获取按象限统计的待办事项数量"""
        stats = QuadrantStatistics()

        # 统计各象限的待办事项数量
        for quadrant in QuadrantType:
            count = await TodoItem.filter(user_id=user_id, quadrant_type=quadrant).count()

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
