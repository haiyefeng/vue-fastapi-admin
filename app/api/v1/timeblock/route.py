import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.controllers.timeblock import time_block_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.todo import TimeBlock
from app.schemas.base import Success
from app.schemas.timeblock import TimeBlockCreate, TimeBlockOut

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_out_dict(block: TimeBlock) -> dict:
    return {
        "id": block.id,
        "todo_item_id": block.todo_item_id,
        "start_time": block.start_time,
        "end_time": block.end_time,
        "title": block.todo_item.title,
        "quadrant_type": block.todo_item.quadrant_type,
    }


@router.get("/list", summary="获取时间块列表（按日期范围或按待办事项二选一）")
async def list_time_blocks(
    start_date: Optional[date] = Query(None, description="开始日期，与 end_date 搭配使用"),
    end_date: Optional[date] = Query(None, description="结束日期，与 start_date 搭配使用"),
    todo_item_id: Optional[int] = Query(None, description="待办事项ID，与日期范围二选一"),
    current_user: User = Depends(AuthControl.is_authed),
):
    if todo_item_id is not None:
        blocks = await time_block_controller.list_by_todo(todo_item_id, current_user.id)
        if blocks is None:
            raise HTTPException(status_code=404, detail="待办事项不存在")
    elif start_date is not None and end_date is not None:
        blocks = await time_block_controller.list_by_date_range(current_user.id, start_date, end_date)
    else:
        raise HTTPException(status_code=400, detail="必须传 todo_item_id，或同时传 start_date 和 end_date")

    result = [TimeBlockOut(**_to_out_dict(b)).model_dump() for b in blocks]
    return Success(data=result)


@router.post("/create", summary="为待办事项新增一个时间块")
async def create_time_block(time_block_in: TimeBlockCreate, current_user: User = Depends(AuthControl.is_authed)):
    try:
        block = await time_block_controller.create_time_block(time_block_in, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not block:
        raise HTTPException(status_code=404, detail="待办事项不存在")
    await block.fetch_related("todo_item")
    return Success(data=TimeBlockOut(**_to_out_dict(block)).model_dump())


@router.delete("/delete", summary="删除时间块")
async def delete_time_block(
    time_block_id: int = Query(..., description="时间块ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    success = await time_block_controller.delete_time_block(time_block_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="时间块不存在")
    return Success(msg="删除成功")
