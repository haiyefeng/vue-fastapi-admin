import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query, HTTPException
from tortoise.exceptions import DoesNotExist

from app.controllers.todo import todo_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.todo import QuadrantType, TodoItem
from app.schemas.base import Success, SuccessExtra, Fail
from app.schemas.todo import TodoItemCreate, TodoItemUpdate, TodoItemOut, TodoStatisticsByDate, QuadrantStatistics

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", summary="获取待办事项列表")
async def list_todos(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    quadrant_type: Optional[QuadrantType] = Query(None, description="象限类型"),
    is_completed: Optional[bool] = Query(None, description="是否已完成"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    获取当前用户的待办事项列表，支持按象限和完成状态筛选
    """
    total, todos = await todo_controller.get_todos_by_user(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        quadrant_type=quadrant_type,
        is_completed=is_completed,
        start_date=start_date,
        end_date=end_date,
    )

    result = []
    for todo in todos:
        todo_dict = await todo.to_dict()
        result.append(TodoItemOut(**todo_dict))

    return SuccessExtra(data=result, total=total, page=page, page_size=page_size)


@router.post("/", summary="创建待办事项")
async def create_todo(
    todo_in: TodoItemCreate,
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    创建新的待办事项
    """
    todo = await todo_controller.create_todo(todo_in, current_user.id)
    todo_dict = await todo.to_dict()

    return Success(data=TodoItemOut(**todo_dict))


@router.get("/{todo_id}", summary="获取指定ID的待办事项")
async def get_todo(
    todo_id: int = Path(..., description="待办事项ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    获取指定ID的待办事项
    """
    try:
        todo = await TodoItem.get(id=todo_id, user_id=current_user.id)
        todo_dict = await todo.to_dict()
        return Success(data=TodoItemOut(**todo_dict))
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="待办事项不存在")


@router.put("/{todo_id}", summary="更新指定ID的待办事项")
async def update_todo(
    todo_in: TodoItemUpdate,
    todo_id: int = Path(..., description="待办事项ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    更新指定ID的待办事项
    """
    todo = await todo_controller.update_todo(todo_id, todo_in, current_user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="待办事项不存在")

    todo_dict = await todo.to_dict()
    return Success(data=TodoItemOut(**todo_dict))


@router.delete("/{todo_id}", summary="删除指定ID的待办事项")
async def delete_todo(
    todo_id: int = Path(..., description="待办事项ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    删除指定ID的待办事项
    """
    success = await todo_controller.delete_todo(todo_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="待办事项不存在")

    return Success(msg="删除成功")


@router.get("/statistics/daily", summary="获取按日期统计的已完成待办事项数量")
async def get_daily_statistics(
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    获取按日期统计的已完成待办事项数量
    """
    statistics = await todo_controller.get_statistics_by_date(
        user_id=current_user.id, start_date=start_date, end_date=end_date
    )

    return Success(data=statistics)


@router.get("/statistics/quadrant", summary="获取按象限统计的待办事项数量")
async def get_quadrant_statistics(
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    获取按象限统计的待办事项数量
    """
    statistics = await todo_controller.get_quadrant_statistics(user_id=current_user.id)

    return Success(data=statistics)
