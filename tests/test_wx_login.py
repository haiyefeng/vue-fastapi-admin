from app.models.admin import User


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
