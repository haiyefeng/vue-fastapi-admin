from typing import List, Optional

from fastapi import HTTPException

from app.core.crud import CRUDBase
from app.models.todo import Habit, HabitFrequencyType
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


habit_controller = HabitController()
