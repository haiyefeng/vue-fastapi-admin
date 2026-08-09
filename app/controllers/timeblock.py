from datetime import date, datetime, time
from typing import List, Optional

from app.core.crud import CRUDBase
from app.models.todo import TimeBlock, TodoItem
from app.schemas.timeblock import TimeBlockCreate


class TimeBlockController(CRUDBase[TimeBlock, TimeBlockCreate, TimeBlockCreate]):
    def __init__(self):
        super().__init__(model=TimeBlock)

    async def create_time_block(self, obj_in: TimeBlockCreate, user_id: int) -> Optional[TimeBlock]:
        todo = await TodoItem.filter(id=obj_in.todo_item_id, user_id=user_id).first()
        if not todo:
            return None
        if obj_in.end_time <= obj_in.start_time:
            raise ValueError("end_time 必须晚于 start_time")
        if obj_in.start_time.date() != obj_in.end_time.date():
            raise ValueError("时间块不能跨天")
        return await TimeBlock.create(
            todo_item_id=obj_in.todo_item_id,
            user_id=user_id,
            start_time=obj_in.start_time,
            end_time=obj_in.end_time,
        )

    async def list_by_date_range(self, user_id: int, start_date: date, end_date: date) -> List[TimeBlock]:
        return (
            await TimeBlock.filter(
                user_id=user_id,
                start_time__gte=datetime.combine(start_date, time.min),
                start_time__lte=datetime.combine(end_date, time.max),
            )
            .select_related("todo_item")
            .order_by("start_time")
        )

    async def list_by_todo(self, todo_item_id: int, user_id: int) -> Optional[List[TimeBlock]]:
        todo = await TodoItem.filter(id=todo_item_id, user_id=user_id).first()
        if not todo:
            return None
        return await TimeBlock.filter(todo_item_id=todo_item_id).select_related("todo_item").order_by("start_time")

    async def delete_time_block(self, time_block_id: int, user_id: int) -> bool:
        deleted_count = await TimeBlock.filter(id=time_block_id, user_id=user_id).delete()
        return deleted_count > 0

    async def get_scheduled_todo_ids(self, user_id: int) -> List[int]:
        """已有任意时间块的待办事项ID，供 /todo/list?unscheduled_only 排除用"""
        return await TimeBlock.filter(user_id=user_id).distinct().values_list("todo_item_id", flat=True)


time_block_controller = TimeBlockController()
