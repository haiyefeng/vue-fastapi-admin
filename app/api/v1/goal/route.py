import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.controllers.goal import goal_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.schemas.base import Success
from app.schemas.goal import GoalCreate, GoalDetailOut, GoalOut, GoalUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="获取当前用户进行中的计划列表")
async def list_goals(current_user: User = Depends(AuthControl.is_authed)):
    result = [GoalOut(**d).model_dump() for d in await goal_controller.list_active_out(current_user.id)]
    return Success(data=result)


@router.get("/archived", summary="获取已归档的计划列表")
async def list_archived_goals(current_user: User = Depends(AuthControl.is_authed)):
    goals = await goal_controller.get_archived_goals(current_user.id)
    result = [GoalOut(**(await goal_controller.to_out_dict(g))).model_dump() for g in goals]
    return Success(data=result)


@router.get("/bootstrap", summary="计划页首屏聚合（进行中 + 已归档）")
async def bootstrap_goals(current_user: User = Depends(AuthControl.is_authed)):
    active = [GoalOut(**d).model_dump() for d in await goal_controller.list_active_out(current_user.id)]
    archived = [
        GoalOut(**(await goal_controller.to_out_dict(g))).model_dump()
        for g in await goal_controller.get_archived_goals(current_user.id)
    ]
    return Success(data={"list": active, "archived": archived})


@router.get("/detail", summary="获取计划详情（含关联任务/习惯列表）")
async def get_goal_detail(
    goal_id: int = Query(..., description="计划ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    data = await goal_controller.get_goal_detail(goal_id, current_user.id)
    if not data:
        raise HTTPException(status_code=404, detail="计划不存在")
    return Success(data=GoalDetailOut(**data).model_dump())


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
