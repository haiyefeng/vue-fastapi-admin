"""微信开放接口封装。

只放对外的 HTTP 调用，不掺业务逻辑——业务判断（建号、发 token）留在 base 路由里。
"""

import httpx

from app.settings import settings

CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"

# 微信接口偶发抖动，超时设短一点，让小程序端尽快看到失败而不是白等
TIMEOUT_SECONDS = 5.0


class WeChatError(Exception):
    """微信接口返回业务错误，或返回体不符合预期"""


async def code2session(code: str, *, transport: httpx.AsyncBaseTransport | None = None) -> dict:
    """用小程序 wx.login 拿到的 code 换取 openid。

    transport 仅供测试注入 httpx.MockTransport，生产调用不要传。
    """
    params = {
        "appid": settings.WX_APPID,
        "secret": settings.WX_SECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=transport) as client:
        response = await client.get(CODE2SESSION_URL, params=params)

    data = response.json()
    if data.get("errcode"):
        raise WeChatError(f"微信返回错误 {data.get('errcode')}: {data.get('errmsg')}")

    openid = data.get("openid")
    if not openid:
        raise WeChatError("微信未返回 openid")

    return {"openid": openid, "session_key": data.get("session_key")}
