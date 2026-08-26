from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise import Tortoise

from app.core.exceptions import SettingNotFound
from app.core.init_app import (
    init_data,
    make_middlewares,
    register_exceptions,
    register_routers,
)
from app.log import logger

try:
    from app.settings.config import settings
except ImportError:
    raise SettingNotFound("Can not import settings")


def _warn_missing_wechat_credentials() -> None:
    """微信凭据缺失时在启动阶段就告警。

    不阻止启动 —— 后端其余功能都不依赖它。但如果不在这里说一声，
    这个配置遗漏要等到第一个用户尝试微信登录、拿到 40013 才会暴露。
    """
    missing = [name for name in ("WX_APPID", "WX_SECRET") if not getattr(settings, name)]
    if missing:
        logger.warning(
            "微信小程序凭据缺失：{}。后端可正常启动，但 /api/v1/base/wx_login 会返回微信的 "
            "40013 invalid appid，小程序无法登录。在 .env 中配置后重启即可。",
            "、".join(missing),
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warn_missing_wechat_credentials()
    await init_data()
    yield
    await Tortoise.close_connections()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.VERSION,
        openapi_url="/openapi.json",
        middleware=make_middlewares(),
        lifespan=lifespan,
    )
    register_exceptions(app)
    register_routers(app, prefix="/api")
    return app


app = create_app()
