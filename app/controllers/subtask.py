from typing import Dict, List, Optional, Tuple

from tortoise.functions import Count

from app.core.crud import CRUDBase
from app.models.todo import SubTask, TodoItem
from app.schemas.subtask import SubTaskCreate, SubTaskUpdate


class SubTaskController(CRUDBase[SubTask, SubTaskCreate, SubTaskUpdate]):
    def __init__(self):
        super().__init__(model=SubTask)

    async def create_subtask(self, obj_in: SubTaskCreate, user_id: int) -> Optional[SubTask]:
        todo = await TodoItem.filter(id=obj_in.todo_item_id, user_id=user_id).first()
        if not todo:
            return None
        order = await SubTask.filter(todo_item_id=obj_in.todo_item_id).count()
        return await SubTask.create(todo_item_id=obj_in.todo_item_id, title=obj_in.title, order=order)

    async def list_by_todo(self, todo_item_id: int, user_id: int) -> Optional[List[SubTask]]:
        todo = await TodoItem.filter(id=todo_item_id, user_id=user_id).first()
        if not todo:
            return None
        return await SubTask.filter(todo_item_id=todo_item_id).order_by("order", "id")

    async def update_subtask(self, subtask_id: int, obj_in: SubTaskUpdate, user_id: int) -> Optional[SubTask]:
        subtask = await SubTask.filter(id=subtask_id).select_related("todo_item").first()
        if not subtask or subtask.todo_item.user_id != user_id:
            return None
        update_data = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        await subtask.update_from_dict(update_data).save()
        return subtask

    async def delete_subtask(self, subtask_id: int, user_id: int) -> bool:
        subtask = await SubTask.filter(id=subtask_id).select_related("todo_item").first()
        if not subtask or subtask.todo_item.user_id != user_id:
            return False
        await subtask.delete()
        return True

    async def get_counts_by_todo_ids(self, todo_ids: List[int]) -> Dict[int, Tuple[int, int]]:
        """一次聚合查询算出每个待办事项的子任务总数/已完成数，避免列表页 N+1"""
        if not todo_ids:
            return {}

        totals = (
            await SubTask.filter(todo_item_id__in=todo_ids)
            .annotate(cnt=Count("id"))
            .group_by("todo_item_id")
            .values("todo_item_id", "cnt")
        )
        completed = (
            await SubTask.filter(todo_item_id__in=todo_ids, is_completed=True)
            .annotate(cnt=Count("id"))
            .group_by("todo_item_id")
            .values("todo_item_id", "cnt")
        )
        total_map = {row["todo_item_id"]: row["cnt"] for row in totals}
        completed_map = {row["todo_item_id"]: row["cnt"] for row in completed}
        return {tid: (total_map.get(tid, 0), completed_map.get(tid, 0)) for tid in todo_ids}


subtask_controller = SubTaskController()
