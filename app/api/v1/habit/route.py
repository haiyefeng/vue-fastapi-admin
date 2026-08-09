import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.controllers.habit import habit_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.todo import Habit
from app.schemas.base import Success
from app.schemas.habit import HabitCreate, HabitOut, HabitUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="获取当前用户进行中的习惯列表")
async def list_habits(current_user: User = Depends(AuthControl.is_authed)):
    habits = await Habit.filter(user_id=current_user.id, is_archived=False).order_by("-created_at")
    result = [HabitOut(**(await h.to_dict())).model_dump() for h in habits]
    return Success(data=result)


@router.get("/archived", summary="获取已归档的习惯列表")
async def list_archived_habits(current_user: User = Depends(AuthControl.is_authed)):
    habits = await habit_controller.get_archived_habits(current_user.id)
    result = [HabitOut(**(await h.to_dict())).model_dump() for h in habits]
    return Success(data=result)


@router.post("/create", summary="创建习惯")
async def create_habit(habit_in: HabitCreate, current_user: User = Depends(AuthControl.is_authed)):
    habit = await habit_controller.create_habit(habit_in, current_user.id)
    return Success(data=HabitOut(**(await habit.to_dict())).model_dump())


@router.post("/update", summary="更新习惯")
async def update_habit(habit_in: HabitUpdate, current_user: User = Depends(AuthControl.is_authed)):
    habit = await habit_controller.update_habit(habit_in.id, habit_in, current_user.id)
    if not habit:
        raise HTTPException(status_code=404, detail="习惯不存在")
    return Success(data=HabitOut(**(await habit.to_dict())).model_dump())


@router.delete("/delete", summary="删除习惯（级联删除历史打卡待办）")
async def delete_habit(
    habit_id: int = Query(..., description="习惯ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    success = await habit_controller.delete_habit(habit_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="习惯不存在")
    return Success(msg="删除成功")
