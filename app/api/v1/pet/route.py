import logging

from fastapi import APIRouter, Depends, Query

from app.controllers.pet import pet_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.schemas.base import Fail, Success
from app.schemas.pet import PetUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/bootstrap", summary="养成猫首屏聚合（用户状态 + 按需的配置）")
async def bootstrap_pet(
    config_version: int = Query(0, description="客户端已缓存的配置版本，一致则不回传配置体"),
    touch: bool = Query(True, description="是否记录本次来访；后台静默同步时传 false"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """一次拿齐用户状态与（必要时的）配置。

    客户端把配置缓存到本地 Storage，版本未变就不重复传输——
    热页面（今日/四象限/习惯）因此可以完全走本地缓存、零网络开销地渲染猫。
    """
    profile = await pet_controller.ensure_profile(current_user.id)
    config = await pet_controller.load_config()
    newly = await pet_controller.apply_unlocks(profile)
    if touch:
        profile = await pet_controller.touch_visit(profile)

    data = {
        "pet": pet_controller.profile_out(profile),
        "total": pet_controller.total_of(profile.stats),
        "newly_unlocked": newly,
        "config_version": config["version"],
    }
    if config_version != config["version"]:
        data["config"] = config

    return Success(data=data)


@router.post("/update", summary="切换陪伴的猫 / 给猫起名")
async def update_pet(pet_in: PetUpdate, current_user: User = Depends(AuthControl.is_authed)):
    try:
        profile = await pet_controller.update_profile(
            user_id=current_user.id, active_cat_id=pet_in.active_cat_id, pet_name=pet_in.pet_name
        )
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    return Success(data=pet_controller.profile_out(profile))
