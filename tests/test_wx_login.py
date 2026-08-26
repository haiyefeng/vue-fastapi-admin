import httpx
import pytest

from app.models.admin import User
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
