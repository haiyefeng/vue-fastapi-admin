import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app import app as fastapi_app
from app.models.admin import User

TEST_DB_URL = "sqlite://:memory:"


@pytest_asyncio.fixture
async def db():
    """每个测试用例独立的内存 SQLite 库，不影响本地开发用的真实数据库配置"""
    await Tortoise.init(db_url=TEST_DB_URL, modules={"models": ["app.models"]}, timezone="Asia/Shanghai")
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()


@pytest_asyncio.fixture
async def test_user(db):
    """is_superuser=True 绕开 PermissionControl 的角色/API 校验，专注测试业务逻辑本身"""
    user = await User.create(
        username="tester",
        email="tester@example.com",
        password="x",
        is_superuser=True,
    )
    return user


@pytest_asyncio.fixture
async def client(test_user):
    """token=dev 时 AuthControl.is_authed 会取库里第一个用户，配合 test_user 即完成认证"""
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test", headers={"token": "dev"}) as ac:
        yield ac
