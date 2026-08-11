import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.controllers.goal import goal_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.schemas.base import Success
from app.schemas.goal import GoalCreate, GoalOut, GoalUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="获取当前用户进行中的计划列表")
async def list_goals(current_user: User = Depends(AuthControl.is_authed)):
    goals = await goal_controller.get_active_goals(current_user.id)
    goal_ids = [g.id for g in goals]
    task_counts = await goal_controller.get_task_counts(goal_ids)
    habit_counts = await goal_controller.get_habit_counts(goal_ids)

    result = []
    for goal in goals:
        data = await goal_controller.to_out_dict(goal)
        task_total, task_completed = task_counts.get(goal.id, (0, 0))
        data["task_total"] = task_total
        data["task_completed"] = task_completed
        data["habit_count"] = habit_counts.get(goal.id, 0)
        result.append(GoalOut(**data).model_dump())
    return Success(data=result)


@router.get("/archived", summary="获取已归档的计划列表")
async def list_archived_goals(current_user: User = Depends(AuthControl.is_authed)):
    goals = await goal_controller.get_archived_goals(current_user.id)
    result = [GoalOut(**(await goal_controller.to_out_dict(g))).model_dump() for g in goals]
    return Success(data=result)


@router.post("/create", summary="创建计划")
async def create_goal(goal_in: GoalCreate, current_user: User = Depends(AuthControl.is_authed)):
    goal = await goal_controller.create_goal(goal_in, current_user.id)
    return Success(data=GoalOut(**(await goal_controller.to_out_dict(goal))).model_dump())


@router.post("/update", summary="更新计划")
async def update_goal(goal_in: GoalUpdate, current_user: User = Depends(AuthControl.is_authed)):
    goal = await goal_controller.update_goal(goal_in.id, goal_in, current_user.id)
    if not goal:
        raise HTTPException(status_code=404, detail="计划不存在")
    return Success(data=GoalOut(**(await goal_controller.to_out_dict(goal))).model_dump())


@router.delete("/delete", summary="删除计划（关联任务/习惯自动解除关联，本身不受影响）")
async def delete_goal(
    goal_id: int = Query(..., description="计划ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    success = await goal_controller.delete_goal(goal_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="计划不存在")
    return Success(msg="删除成功")
