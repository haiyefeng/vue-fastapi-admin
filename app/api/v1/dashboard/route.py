import logging

from fastapi import APIRouter, Depends

from app.controllers.dashboard import dashboard_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.schemas.base import Success
from app.schemas.dashboard import TodayOverviewOut

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/today", summary="获取今日概览（今日日程/今日待办/今日习惯）")
async def get_today_overview(current_user: User = Depends(AuthControl.is_authed)):
    data = await dashboard_controller.get_today_overview(current_user.id)
    return Success(data=TodayOverviewOut(**data).model_dump())
