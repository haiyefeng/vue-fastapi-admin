import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from tortoise.exceptions import DoesNotExist

from app.controllers.subtask import subtask_controller
from app.controllers.todo import todo_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.todo import TodoItem
from app.schemas.base import Fail, Success, SuccessExtra
from app.schemas.todo import (
    QuadrantStatistics,
    TodoItemCreate,
    TodoItemOut,
    TodoItemUpdate,
    TodoStatisticsByDate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="获取待办事项列表")
async def list_todos(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    quadrant_type: Optional[str] = Query(None, description="象限类型，多个用逗号分隔"),
    is_completed: Optional[bool] = Query(None, description="是否已完成"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    project_id: Optional[int] = Query(None, description="项目ID"),
    inbox_only: Optional[bool] = Query(None, description="是否只看收件箱（project_id 为空），优先于 project_id"),
    unscheduled_only: Optional[bool] = Query(
        None, description="是否只看未排程任务（无任何时间块的未完成任务），用于日历页未安排面板"
    ),
    sort_by: Optional[str] = Query(None, description="排序字段: due_date/quadrant_type/created_at"),
    sort_order: Optional[str] = Query("asc", description="排序方向: asc/desc"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    获取当前用户的待办事项列表，支持按象限（可多选）、完成状态、项目/收件箱/未排程筛选，支持排序
    """
    total, todos = await todo_controller.get_todos_by_user(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        quadrant_type=quadrant_type,
        is_completed=is_completed,
        start_date=start_date,
        end_date=end_date,
        project_id=project_id,
        inbox_only=inbox_only,
        unscheduled_only=unscheduled_only,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    todo_ids = [todo.id for todo in todos]
    counts = await subtask_controller.get_counts_by_todo_ids(todo_ids)

    result = []
    for todo in todos:
        todo_dict = await todo.to_dict()
        total_sub, completed_sub = counts.get(todo.id, (0, 0))
        todo_out = TodoItemOut(**todo_dict, subtask_total=total_sub, subtask_completed=completed_sub)
        result.append(todo_out.model_dump())

    return SuccessExtra(data=result, total=total, page=page, page_size=page_size)


@router.post("/create", summary="创建待办事项")
async def create_todo(
    todo_in: TodoItemCreate,
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    创建新的待办事项
    """
    todo = await todo_controller.create_todo(todo_in, current_user.id)
    todo_dict = await todo.to_dict()
    todo_out = TodoItemOut(**todo_dict)

    return Success(data=todo_out.model_dump())


@router.get("/get", summary="获取指定ID的待办事项")
async def get_todo(
    todo_id: int = Query(..., description="待办事项ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    获取指定ID的待办事项
    """
    try:
        todo = await TodoItem.get(id=todo_id, user_id=current_user.id)
        todo_dict = await todo.to_dict()
        counts = await subtask_controller.get_counts_by_todo_ids([todo.id])
        total_sub, completed_sub = counts.get(todo.id, (0, 0))
        todo_out = TodoItemOut(**todo_dict, subtask_total=total_sub, subtask_completed=completed_sub)
        return Success(data=todo_out.model_dump())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="待办事项不存在")


@router.post("/update", summary="更新指定ID的待办事项")
async def update_todo(
    todo_in: TodoItemUpdate,
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    更新指定ID的待办事项
    """
    todo = await todo_controller.update_todo(todo_in.id, todo_in, current_user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="待办事项不存在")

    todo_dict = await todo.to_dict()
    counts = await subtask_controller.get_counts_by_todo_ids([todo.id])
    total_sub, completed_sub = counts.get(todo.id, (0, 0))
    todo_out = TodoItemOut(**todo_dict, subtask_total=total_sub, subtask_completed=completed_sub)
    return Success(data=todo_out.model_dump())


@router.delete("/delete", summary="删除指定ID的待办事项")
async def delete_todo(
    todo_id: int = Query(..., description="待办事项ID"),
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

    # 将统计对象转换为字典列表
    result = [stat.model_dump() for stat in statistics]

    return Success(data=result)


@router.get("/statistics/quadrant", summary="获取按象限统计的待办事项数量")
async def get_quadrant_statistics(
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    获取按象限统计的待办事项数量
    """
    statistics = await todo_controller.get_quadrant_statistics(user_id=current_user.id)

    return Success(data=statistics.model_dump())


@router.get("/stats-bootstrap", summary="统计页首屏聚合（每日统计 + 象限统计 + 已完成列表）")
async def stats_bootstrap(
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    page: int = Query(1, description="已完成列表页码"),
    page_size: int = Query(20, description="已完成列表每页数量"),
    sort_by: Optional[str] = Query("completed_at", description="已完成列表排序字段"),
    sort_order: Optional[str] = Query("desc", description="已完成列表排序方向"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """统计页三块数据一次返回，替代小程序原先的 3 次云函数往返。
    日期范围统一按「完成时间」口径：daily 与 completed 两块都筛 completed_at，
    保证同一次请求里的数据人群一致。"""
    statistics = await todo_controller.get_statistics_by_date(
        user_id=current_user.id, start_date=start_date, end_date=end_date
    )
    quadrant = await todo_controller.get_quadrant_statistics(user_id=current_user.id)
    total, todos = await todo_controller.get_todos_by_user(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        is_completed=True,
        completed_start=start_date,
        completed_end=end_date,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    todo_ids = [todo.id for todo in todos]
    counts = await subtask_controller.get_counts_by_todo_ids(todo_ids)
    completed_list = []
    for todo in todos:
        todo_dict = await todo.to_dict()
        total_sub, completed_sub = counts.get(todo.id, (0, 0))
        completed_list.append(
            TodoItemOut(**todo_dict, subtask_total=total_sub, subtask_completed=completed_sub).model_dump()
        )

    return Success(
        data={
            "daily": [stat.model_dump() for stat in statistics],
            "quadrant": quadrant.model_dump(),
            "completed": {
                "list": completed_list,
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )
