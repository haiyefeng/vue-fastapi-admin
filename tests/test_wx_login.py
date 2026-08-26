import httpx
import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

from app import app as fastapi_app
from app.controllers.user import user_controller
from app.core.init_app import init_miniprogram_role
from app.models.admin import Api, Role, User
from app.settings import settings
from app.utils import wechat
from app.utils.wechat import WeChatError, code2session


async def test_user_openid_can_be_null_for_web_users(db):
    """Web 端用户没有 openid，多条 None 不应触发唯一约束冲突"""
    await User.create(username="web1", email="web1@example.com", password="x")
    await User.create(username="web2", email="web2@example.com", password="x")
    assert await User.filter(openid=None).count() == 2


async def test_user_openid_is_unique(db):
    await User.create(username="wx1", email="wx1@wx.local", openid="o_aaa")
    found = await User.get_or_none(openid="o_aaa")
    assert found is not None
    assert found.username == "wx1"


def _mock_transport(payload: dict, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "js_code" in request.url.params
        return httpx.Response(status_code, json=payload)

    return httpx.MockTransport(handler)


async def test_code2session_returns_openid():
    transport = _mock_transport({"openid": "o_abc123", "session_key": "sk"})
    result = await code2session("the-code", transport=transport)
    assert result["openid"] == "o_abc123"
    assert result["session_key"] == "sk"


async def test_code2session_raises_on_wechat_errcode():
    transport = _mock_transport({"errcode": 40029, "errmsg": "invalid code"})
    with pytest.raises(WeChatError) as exc:
        await code2session("bad-code", transport=transport)
    assert "40029" in str(exc.value)


async def test_code2session_raises_when_openid_missing():
    transport = _mock_transport({"session_key": "sk"})
    with pytest.raises(WeChatError):
        await code2session("weird-code", transport=transport)


async def test_code2session_raises_wechaterror_on_timeout():
    """微信接口超时/连接失败：httpx.RequestError 要被兜住转成 WeChatError，而不是原样上抛"""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout")

    transport = httpx.MockTransport(handler)
    with pytest.raises(WeChatError):
        await code2session("the-code", transport=transport)


def _mock_transport_text(text: str, status_code: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text=text)

    return httpx.MockTransport(handler)


async def test_code2session_raises_wechaterror_on_non_json_response():
    """微信返回非 JSON 体（WAF/代理的 HTML 错误页）：不应把原始 ValueError 抛出去"""
    transport = _mock_transport_text("<html>error</html>")
    with pytest.raises(WeChatError):
        await code2session("the-code", transport=transport)


async def test_create_wx_user_reuses_existing_on_integrity_error(db):
    """并发首次登录：两个请求带同一个新 openid 同时通过 get_or_none 判空，
    第二个撞唯一约束时应回查复用已存在的用户，而不是把 IntegrityError 原样抛给客户端"""
    existing = await user_controller.create_wx_user("o_concurrent_openid_1")

    user = await user_controller.create_wx_user("o_concurrent_openid_1")

    assert user.id == existing.id
    assert await User.filter(openid="o_concurrent_openid_1").count() == 1


def _patch_code2session(monkeypatch, openid: str):
    async def fake(code: str, *, transport=None):
        return {"openid": openid, "session_key": "sk"}

    # base.py 里是 `from app.utils.wechat import code2session` 直接引入的名字，
    # 所以要打在 base 模块的命名空间上，打在 wechat 模块上不生效
    import app.api.v1.base.base as base_module

    monkeypatch.setattr(base_module, "code2session", fake)


async def test_wx_login_creates_user_on_first_call(db, monkeypatch):
    _patch_code2session(monkeypatch, "o_first_login_openid_1234")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/base/wx_login", json={"code": "any"})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_new"] is True
    assert data["username"] == "wx_ogin_openid_1234"  # f"wx_{openid[-16:]}"，19 字符，卡在 username 的 20 上限内

    user = await User.get_or_none(openid="o_first_login_openid_1234")
    assert user is not None
    assert user.password is None
    assert user.is_superuser is False
    assert user.email == "o_first_login_openid_1234@wx.local"

    payload = pyjwt.decode(data["access_token"], settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["user_id"] == user.id


async def test_wx_login_reuses_existing_user(db, monkeypatch):
    existing = await User.create(username="old_wx", email="old@wx.local", openid="o_exists")
    _patch_code2session(monkeypatch, "o_exists")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/base/wx_login", json={"code": "any"})

    data = resp.json()["data"]
    assert data["is_new"] is False
    assert data["username"] == "old_wx"
    assert await User.filter(openid="o_exists").count() == 1

    payload = pyjwt.decode(data["access_token"], settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert payload["user_id"] == existing.id


async def test_wx_login_returns_400_when_wechat_fails(db, monkeypatch):
    async def fake(code: str, *, transport=None):
        raise wechat.WeChatError("微信返回错误 40029: invalid code")

    import app.api.v1.base.base as base_module

    monkeypatch.setattr(base_module, "code2session", fake)
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/base/wx_login", json={"code": "bad"})

    assert resp.json()["code"] == 400


async def test_wx_login_rejects_inactive_user(db, monkeypatch):
    await User.create(username="banned", email="banned@wx.local", openid="o_banned", is_active=False)
    _patch_code2session(monkeypatch, "o_banned")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/base/wx_login", json={"code": "any"})

    assert resp.json()["code"] == 403


async def test_init_miniprogram_role_is_idempotent(db):
    await Api.create(path="/api/v1/todo/list", method="GET", summary="列表", tags="待办事项")
    await Api.create(path="/api/v1/user/list", method="GET", summary="用户", tags="用户管理")

    await init_miniprogram_role()
    await init_miniprogram_role()

    roles = await Role.filter(name=settings.MINIPROGRAM_ROLE_NAME)
    assert len(roles) == 1

    apis = await roles[0].apis.all()
    paths = {a.path for a in apis}
    assert "/api/v1/todo/list" in paths
    assert "/api/v1/user/list" not in paths, "小程序角色不应拿到 RBAC 管理类 API"


async def test_init_miniprogram_role_picks_up_new_apis(db):
    await init_miniprogram_role()
    await Api.create(path="/api/v1/pet/bootstrap", method="GET", summary="猫", tags="养成猫")
    await init_miniprogram_role()

    role = await Role.get(name=settings.MINIPROGRAM_ROLE_NAME)
    paths = {a.path for a in await role.apis.all()}
    assert "/api/v1/pet/bootstrap" in paths
