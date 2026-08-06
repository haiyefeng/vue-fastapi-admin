import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.controllers.subtask import subtask_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.schemas.base import Success
from app.schemas.subtask import SubTaskCreate, SubTaskOut, SubTaskUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="获取指定待办事项下的子任务列表")
async def list_subtasks(
    todo_item_id: int = Query(..., description="待办事项ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    subtasks = await subtask_controller.list_by_todo(todo_item_id, current_user.id)
    if subtasks is None:
        raise HTTPException(status_code=404, detail="待办事项不存在")
    result = [SubTaskOut(**(await s.to_dict())).model_dump() for s in subtasks]
    return Success(data=result)


@router.post("/create", summary="创建子任务")
async def create_subtask(subtask_in: SubTaskCreate, current_user: User = Depends(AuthControl.is_authed)):
    subtask = await subtask_controller.create_subtask(subtask_in, current_user.id)
    if not subtask:
        raise HTTPException(status_code=404, detail="待办事项不存在")
    return Success(data=SubTaskOut(**(await subtask.to_dict())).model_dump())


@router.post("/update", summary="更新子任务")
async def update_subtask(subtask_in: SubTaskUpdate, current_user: User = Depends(AuthControl.is_authed)):
    subtask = await subtask_controller.update_subtask(subtask_in.id, subtask_in, current_user.id)
    if not subtask:
        raise HTTPException(status_code=404, detail="子任务不存在")
    return Success(data=SubTaskOut(**(await subtask.to_dict())).model_dump())


@router.delete("/delete", summary="删除子任务")
async def delete_subtask(
    subtask_id: int = Query(..., description="子任务ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    success = await subtask_controller.delete_subtask(subtask_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="子任务不存在")
    return Success(msg="删除成功")
