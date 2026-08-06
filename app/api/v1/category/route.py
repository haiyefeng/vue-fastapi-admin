import logging

from fastapi import APIRouter, Depends

from app.controllers.category import category_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.schemas.base import Success
from app.schemas.category import CategoryOut

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="获取当前用户可用的分类列表")
async def list_categories(current_user: User = Depends(AuthControl.is_authed)):
    categories = await category_controller.get_categories_for_user(current_user.id)
    result = [CategoryOut(**(await c.to_dict())).model_dump() for c in categories]
    return Success(data=result)
