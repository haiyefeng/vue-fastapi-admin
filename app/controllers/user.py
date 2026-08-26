from datetime import datetime
from typing import List, Optional

from fastapi.exceptions import HTTPException
from tortoise.exceptions import IntegrityError

from app.core.crud import CRUDBase
from app.log import logger
from app.models.admin import Role, User
from app.schemas.login import CredentialsSchema
from app.schemas.users import UserCreate, UserUpdate
from app.settings import settings
from app.utils.password import get_password_hash, verify_password

from .role import role_controller


class UserController(CRUDBase[User, UserCreate, UserUpdate]):
    def __init__(self):
        super().__init__(model=User)

    async def get_by_email(self, email: str) -> Optional[User]:
        return await self.model.filter(email=email).first()

    async def get_by_username(self, username: str) -> Optional[User]:
        return await self.model.filter(username=username).first()

    async def create_user(self, obj_in: UserCreate) -> User:
        obj_in.password = get_password_hash(password=obj_in.password)
        obj = await self.create(obj_in)
        return obj

    async def update_last_login(self, id: int) -> None:
        user = await self.model.get(id=id)
        user.last_login = datetime.now()
        await user.save()

    async def authenticate(self, credentials: CredentialsSchema) -> Optional["User"]:
        user = await self.model.filter(username=credentials.username).first()
        if not user:
            raise HTTPException(status_code=400, detail="无效的用户名")
        verified = verify_password(credentials.password, user.password)
        if not verified:
            raise HTTPException(status_code=400, detail="密码错误!")
        if not user.is_active:
            raise HTTPException(status_code=400, detail="用户已被禁用")
        return user

    async def update_roles(self, user: User, role_ids: List[int]) -> None:
        await user.roles.clear()
        for role_id in role_ids:
            role_obj = await role_controller.get(id=role_id)
            await user.roles.add(role_obj)

    async def create_wx_user(self, openid: str) -> User:
        """为微信 openid 自动建号。

        username 上限 20 字符而 openid 是 28 位，所以取后 16 位拼前缀；
        email 是 unique 且非空，用占位域名满足约束。
        """
        try:
            user = await User.create(
                username=f"wx_{openid[-16:]}",
                email=f"{openid}@wx.local",
                password=None,
                openid=openid,
                is_active=True,
                is_superuser=False,
            )
        except IntegrityError:
            # 并发首次登录：另一个请求刚建好同一个 openid 的用户，回查复用即可
            user = await User.get_or_none(openid=openid)
            if user is None:
                raise
            return user

        role = await Role.get_or_none(name=settings.MINIPROGRAM_ROLE_NAME)
        if role:
            await user.roles.add(role)
        else:
            logger.warning(f"小程序角色 {settings.MINIPROGRAM_ROLE_NAME!r} 不存在，用户 {user.username} 未绑定任何角色")
        return user

    async def reset_password(self, user_id: int):
        user_obj = await self.get(id=user_id)
        if user_obj.is_superuser:
            raise HTTPException(status_code=403, detail="不允许重置超级管理员密码")
        user_obj.password = get_password_hash(password="123456")
        await user_obj.save()


user_controller = UserController()
