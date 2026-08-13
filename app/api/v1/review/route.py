import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.controllers.review import review_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.todo import ReviewPeriodType
from app.schemas.base import Success
from app.schemas.review import ReviewDataSummaryOut, ReviewListItem, ReviewOut, ReviewSaveIn

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/data-summary", summary="获取指定周期的数据回顾聚合（任务完成情况/习惯打卡情况/计划进展）")
async def get_data_summary(
    period_type: ReviewPeriodType = Query(..., description="回顾周期类型"),
    anchor_date: date = Query(..., description="周期内任意一天"),
    current_user: User = Depends(AuthControl.is_authed),
):
    data = await review_controller.get_data_summary(current_user.id, period_type, anchor_date)
    return Success(data=ReviewDataSummaryOut(**data).model_dump())


@router.post("/save", summary="保存回顾（草稿或完成），同周期已存在则覆盖更新")
async def save_review(review_in: ReviewSaveIn, current_user: User = Depends(AuthControl.is_authed)):
    review = await review_controller.save_review(review_in, current_user.id)
    return Success(data=ReviewOut(**(await review.to_dict())).model_dump())


@router.get("/detail", summary="获取指定周期的回顾详情；不存在时 data 为 null（不是 404）")
async def get_review_detail(
    period_type: ReviewPeriodType = Query(..., description="回顾周期类型"),
    anchor_date: date = Query(..., description="周期内任意一天"),
    current_user: User = Depends(AuthControl.is_authed),
):
    review = await review_controller.get_review_detail(period_type, anchor_date, current_user.id)
    if not review:
        return Success(data=None)
    return Success(data=ReviewOut(**(await review.to_dict())).model_dump())


@router.get("/list", summary="获取历史回顾列表，按周期开始日期倒序")
async def list_reviews(
    period_type: Optional[ReviewPeriodType] = Query(None, description="按周期类型筛选，留空返回全部"),
    current_user: User = Depends(AuthControl.is_authed),
):
    reviews = await review_controller.get_review_list(current_user.id, period_type)
    result = [ReviewListItem(**(await r.to_dict())).model_dump() for r in reviews]
    return Success(data=result)
