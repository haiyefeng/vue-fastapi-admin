# 小程序迁移 · 阶段一：后端接口就位 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 FastAPI 后端具备小程序切换所需的全部接口能力——微信登录、RBAC 授权、4 个聚合端点、`habit/summary`、以及完整的 pet 模块——使小程序在阶段二可以逐模块切过来。

**Architecture:** 全部改动落在 `app/` 内，遵循现有的三层结构（`api/v1/<resource>/route.py` → `controllers/<resource>.py` → `models/`）。微信登录复用现有 JWT 体系，不另起认证机制。聚合端点是薄封装，内部并发调用已有 controller 方法。pet 是新增模块，但**返回体严格对齐小程序 `utils/cat.js` 已有的消费格式**，让那 133 行本地缓存逻辑零改动。

**Tech Stack:** FastAPI · Tortoise ORM · aerich（迁移）· pytest + pytest-asyncio + httpx（测试）· MySQL（生产）/ 内存 SQLite（测试）

**Spec:** `docs/superpowers/specs/2026-08-26-miniprogram-fastapi-migration-design.md`

## Global Constraints

- **中文交流与注释**：本仓库的代码注释、commit message、文档一律中文。
- **行宽 120**，black（py310/py311）+ isort（profile=black）；提交前跑 `make check`。
- **ruff 忽略 `F403`/`F405`**——schema 模块惯用 `from x import *`，沿用即可。
- **所有业务路由挂 `dependencies=[DependPermission]`**（在 `app/api/v1/__init__.py` 注册处），唯独 `base` 路由组不挂。新增的 `pet` 路由必须按此注册。
- **路由处理函数内用 `Depends(AuthControl.is_authed)` 取当前用户**，所有查询以 `user_id` 过滤——这是待办事项系列模块的既定模式，新代码必须遵守。
- **响应统一用 `app/schemas/base.py` 的 `Success` / `SuccessExtra` / `Fail`**，不要直接 `return dict`。
- **时区**：`TORTOISE_ORM.use_tz = False`，`timezone = "Asia/Shanghai"`。数据库里是**朴素（naive）本地时间**，写代码时不要引入 `datetime.now(timezone.utc)` 存库（JWT 的 `exp` 除外，那是 JWT 规范要求）。
- **测试库是内存 SQLite**（`tests/conftest.py`），通过 `Tortoise.generate_schemas()` 建表，**不跑 aerich 迁移**。所以新增模型改完就能测，但生产仍需生成迁移文件。
- **测试命令**：`python -m pytest tests/xxx.py -v`（在 `.venv` 内）。不要用 `make test`——它依赖一个仓库里并不存在的 `.env` 文件。
- **提交粒度**：每个 Task 末尾提交一次。

---

## File Structure

**新建**

| 文件 | 职责 |
|---|---|
| `app/utils/wechat.py` | 微信开放接口封装，目前只有 `code2session` |
| `app/models/pet.py` | 养成猫的 3 张表：`PetProfile` / `PetCat` / `PetLine` |
| `app/schemas/pet.py` | pet 的请求/响应模型 |
| `app/controllers/pet.py` | pet 业务逻辑：解锁判定、来访记录、配置版本、计数累加 |
| `app/api/v1/pet/__init__.py` | 路由组装（对齐其他资源的写法） |
| `app/api/v1/pet/route.py` | `GET /bootstrap`、`POST /update` |
| `app/core/pet_seed.py` | pet 配置初始数据（3 只猫 + 13 组台词），从 `weapp/cloudfunctions/pet/seed.js` 移植 |
| `tests/test_wx_login.py` | 微信登录与自动建号 |
| `tests/test_bootstrap.py` | 4 个聚合端点 |
| `tests/test_habit_summary.py` | `habit/summary` 周期聚合 |
| `tests/test_pet.py` | pet 全流程 |

**修改**

| 文件 | 改动 |
|---|---|
| `app/models/admin.py` | `User` 增 `openid` 字段 |
| `app/models/__init__.py` | 导入 pet 模型 |
| `app/settings/config.py` | 增 `WX_APPID` / `WX_SECRET` |
| `app/schemas/login.py` | 增 `WxLoginSchema` |
| `app/controllers/user.py` | 增 `create_wx_user` |
| `app/api/v1/base/base.py` | 增 `POST /wx_login` |
| `app/core/init_app.py` | 增 `init_miniprogram_role` / `init_pet_config`；`make_middlewares` 的 `exclude_paths` 增 `wx_login` |
| `app/api/v1/__init__.py` | 注册 `pet_router` |
| `app/api/v1/habit/route.py` | 增 `/bootstrap`、`/summary` |
| `app/controllers/habit.py` | 增 `summary` 与纯函数 `is_scheduled_day` |
| `app/api/v1/goal/route.py` | 增 `/bootstrap`，`/list` 改调抽取出的方法 |
| `app/controllers/goal.py` | 抽出 `list_active_out` |
| `app/api/v1/project/route.py` | 增 `/bootstrap` |
| `app/api/v1/todos/route.py` | 增 `/stats-bootstrap` |
| `app/controllers/todo.py` | `update_todo` 完成时累加 pet 计数 |

**边界说明**：pet 的解锁判定、条件求值属于业务规则，放 `controllers/pet.py`；配置内容（猫和台词的文本）放 `core/pet_seed.py` 与业务逻辑隔离——将来内容改动不碰逻辑代码。

---

### Task 1: `User.openid` 字段

**Files:**
- Modify: `app/models/admin.py:8-21`
- Test: `tests/test_wx_login.py`

**Interfaces:**
- Produces: `User.openid: str | None`（`max_length=64`, unique, index）

- [ ] **Step 1: 写失败的测试**

新建 `tests/test_wx_login.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_wx_login.py -v`
Expected: FAIL，`User` 没有 `openid` 字段（`FieldError` 或 `TypeError: 'openid' is an invalid keyword argument`）

- [ ] **Step 3: 加字段**

在 `app/models/admin.py` 的 `User` 类中，`dept_id` 之后加一行：

```python
    openid = fields.CharField(max_length=64, unique=True, null=True, description="微信openid", index=True)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_wx_login.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 生成迁移文件**

```bash
source .venv/bin/activate
aerich migrate --name add_user_openid
```

预期在 `migrations/models/` 下生成一个新的 `.py` 迁移文件。**打开它确认**：`upgrade` 中只有 `ALTER TABLE user ADD openid ...`，没有意外的 DROP。

> 如果 `aerich migrate` 因为连不上 MySQL 而失败，说明本机没起数据库——记录下来，在有数据库的环境补跑，不要跳过这一步就往下走。

- [ ] **Step 6: 提交**

```bash
git add app/models/admin.py tests/test_wx_login.py migrations/
git commit -m "feat(auth): User 增加 openid 字段，为微信登录做准备"
```

---

### Task 2: 微信 code2session 工具

**Files:**
- Create: `app/utils/wechat.py`
- Modify: `app/settings/config.py:23`
- Test: `tests/test_wx_login.py`

**Interfaces:**
- Produces:
  - `app.utils.wechat.code2session(code: str, *, transport=None) -> dict`，成功返回 `{"openid": str, "session_key": str | None}`
  - `app.utils.wechat.WeChatError`（异常类）
  - `settings.WX_APPID: str`、`settings.WX_SECRET: str`

`transport` 参数是为测试预留的注入点——传入 `httpx.MockTransport` 即可拦截请求，生产代码永远不传。

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_wx_login.py`：

```python
import httpx
import pytest

from app.utils.wechat import WeChatError, code2session


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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_wx_login.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.utils.wechat'`

- [ ] **Step 3: 实现**

新建 `app/utils/wechat.py`：

```python
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
```

在 `app/settings/config.py` 的 `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` 那一行后面加：

```python
    # 微信小程序凭据，务必通过环境变量注入，不要把真实值写进代码
    WX_APPID: str = os.getenv("WX_APPID", "")
    WX_SECRET: str = os.getenv("WX_SECRET", "")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_wx_login.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
git add app/utils/wechat.py app/settings/config.py tests/test_wx_login.py
git commit -m "feat(auth): 新增微信 code2session 工具与小程序凭据配置"
```

---

### Task 3: `POST /api/v1/base/wx_login`

**Files:**
- Modify: `app/schemas/login.py`
- Modify: `app/controllers/user.py`
- Modify: `app/api/v1/base/base.py:19-38`
- Modify: `app/core/init_app.py:40-48`（审计日志排除路径）
- Test: `tests/test_wx_login.py`

**Interfaces:**
- Consumes: `code2session`、`WeChatError`（Task 2）；`User.openid`（Task 1）
- Produces:
  - `POST /api/v1/base/wx_login`，请求体 `{"code": str}`，成功返回 `Success(data={"access_token": str, "username": str, "is_new": bool})`
  - `user_controller.create_wx_user(openid: str) -> User`
  - `app.schemas.login.WxLoginSchema`

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_wx_login.py`：

```python
import jwt as pyjwt
from httpx import ASGITransport, AsyncClient

from app import app as fastapi_app
from app.settings import settings
from app.utils import wechat


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
```


- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_wx_login.py -v`
Expected: FAIL，404（路由不存在）

- [ ] **Step 3: 实现**

`app/schemas/login.py` 末尾追加：

```python
class WxLoginSchema(BaseModel):
    code: str = Field(..., description="wx.login 返回的临时登录凭证")
```

`app/controllers/user.py` 的 `UserController` 内追加（注意确认文件顶部已 `from app.models.admin import Role, User`，没有就补上）：

```python
    async def create_wx_user(self, openid: str) -> User:
        """为微信 openid 自动建号。

        username 上限 20 字符而 openid 是 28 位，所以取后 16 位拼前缀；
        email 是 unique 且非空，用占位域名满足约束。
        """
        user = await User.create(
            username=f"wx_{openid[-16:]}",
            email=f"{openid}@wx.local",
            password=None,
            openid=openid,
            is_active=True,
            is_superuser=False,
        )
        role = await Role.get_or_none(name=MINIPROGRAM_ROLE_NAME)
        if role:
            await user.roles.add(role)
        return user
```

`MINIPROGRAM_ROLE_NAME` 在 Task 4 定义于 `app/core/init_app.py`。为避免循环导入，**在 `app/settings/config.py` 里定义这个常量**：

```python
    MINIPROGRAM_ROLE_NAME: str = "小程序用户"
```

于是 `create_wx_user` 里写 `await Role.get_or_none(name=settings.MINIPROGRAM_ROLE_NAME)`（在 `app/controllers/user.py` 顶部 `from app.settings import settings`）。

`app/api/v1/base/base.py`：顶部 import 追加

```python
from app.schemas.login import WxLoginSchema
from app.utils.wechat import WeChatError, code2session
```

（`from app.schemas.login import *` 已在，但显式再导入 `WxLoginSchema` 以便 monkeypatch 定位；`code2session` 必须是模块级名字，测试才能替换。）

在 `login_access_token` 之后追加：

```python
@router.post("/wx_login", summary="微信小程序登录")
async def wx_login(credentials: WxLoginSchema):
    """用 wx.login 的 code 换 openid，首次调用自动建号，返回与 Web 端同一套 JWT"""
    try:
        session = await code2session(credentials.code)
    except WeChatError as e:
        return Fail(code=400, msg=f"微信登录失败: {e}")

    openid = session["openid"]
    user = await User.get_or_none(openid=openid)
    is_new = False
    if user is None:
        user = await user_controller.create_wx_user(openid)
        is_new = True

    if not user.is_active:
        return Fail(code=403, msg="用户已被禁用")

    await user_controller.update_last_login(user.id)
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data=JWTPayload(
            user_id=user.id,
            username=user.username,
            is_superuser=user.is_superuser,
            exp=expire,
        )
    )
    return Success(data={"access_token": access_token, "username": user.username, "is_new": is_new})
```

`app/core/init_app.py` 的 `make_middlewares` 里，`HttpAuditLogMiddleware` 的 `exclude_paths` 加一项——**登录请求体里带 code，不该进审计日志**：

```python
                "/api/v1/base/wx_login",
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_wx_login.py -v`
Expected: PASS（9 passed）

- [ ] **Step 5: 提交**

```bash
git add app/schemas/login.py app/controllers/user.py app/api/v1/base/base.py app/core/init_app.py app/settings/config.py tests/test_wx_login.py
git commit -m "feat(auth): 新增微信小程序登录接口，首次登录自动建号"
```

---

### Task 4: 「小程序用户」角色初始化

**Files:**
- Modify: `app/core/init_app.py:353-383`
- Test: `tests/test_wx_login.py`

**Interfaces:**
- Consumes: `settings.MINIPROGRAM_ROLE_NAME`（Task 3）
- Produces: `init_miniprogram_role()`，幂等；被 `init_data()` 在 `init_roles()` 之后调用

**为什么必须单独一个函数**：现有 `init_roles()` 开头是 `if not await Role.exists(): ...`，只在**全库无角色**时执行一次。已经跑过的库再加角色不会生效，所以新角色必须走独立的幂等函数。

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_wx_login.py`：

```python
from app.core.init_app import init_miniprogram_role
from app.models.admin import Api, Role


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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_wx_login.py -v`
Expected: FAIL，`ImportError: cannot import name 'init_miniprogram_role'`

- [ ] **Step 3: 实现**

`app/core/init_app.py`，在 `init_roles()` 之后加：

```python
# 小程序用户能访问的 API 标签白名单。新增小程序用的路由组时，把它的 tags 加进来。
MINIPROGRAM_API_TAGS = [
    "基础模块",
    "待办事项",
    "子任务",
    "时间块",
    "分类",
    "习惯",
    "计划",
    "项目",
    "回顾总结",
    "今日概览",
    "养成猫",
]


async def init_miniprogram_role():
    """幂等地维护「小程序用户」角色的 API 授权。

    每次启动都跑：init_apis() 刚刷新完 Api 表，这里把新出现的业务 API 补授权给该角色，
    否则小程序用户（非超管）会在新接口上吃 403。
    """
    role = await Role.filter(name=settings.MINIPROGRAM_ROLE_NAME).first()
    if role is None:
        role = await Role.create(name=settings.MINIPROGRAM_ROLE_NAME, desc="小程序用户角色，仅含待办事项相关接口")

    apis = await Api.filter(tags__in=MINIPROGRAM_API_TAGS)
    if apis:
        await role.apis.add(*apis)
```

`init_data()` 改为：

```python
async def init_data():
    await init_db()
    await init_superuser()
    await init_menus()
    await init_apis()
    await init_roles()
    await init_miniprogram_role()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_wx_login.py -v`
Expected: PASS（11 passed）

- [ ] **Step 5: 提交**

```bash
git add app/core/init_app.py tests/test_wx_login.py
git commit -m "feat(rbac): 新增「小程序用户」角色并在启动时幂等授权"
```

---

### Task 5: `GET /api/v1/habit/bootstrap`

**Files:**
- Modify: `app/api/v1/habit/route.py`
- Test: `tests/test_bootstrap.py`

**Interfaces:**
- Produces: `GET /api/v1/habit/bootstrap` → `Success(data={"list": [...], "archived": [...]})`，两个数组的元素结构分别与 `GET /habit/list`、`GET /habit/archived` 完全一致

对应云函数 `weapp/cloudfunctions/habit/index.js:180`。

- [ ] **Step 1: 写失败的测试**

新建 `tests/test_bootstrap.py`：

```python
from app.models.todo import Habit, HabitFrequencyType


async def test_habit_bootstrap_returns_active_and_archived(client, test_user):
    await Habit.create(user_id=test_user.id, name="晨跑", frequency_type=HabitFrequencyType.DAILY)
    await Habit.create(
        user_id=test_user.id, name="旧习惯", frequency_type=HabitFrequencyType.DAILY, is_archived=True
    )

    resp = await client.get("/api/v1/habit/bootstrap")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert [h["name"] for h in data["list"]] == ["晨跑"]
    assert [h["name"] for h in data["archived"]] == ["旧习惯"]
    # 与 /habit/list 同构：带今日打卡状态字段
    assert "today_todo_id" in data["list"][0]
    assert "streak" in data["list"][0]


async def test_habit_bootstrap_matches_separate_endpoints(client, test_user):
    await Habit.create(user_id=test_user.id, name="读书", frequency_type=HabitFrequencyType.DAILY)

    merged = (await client.get("/api/v1/habit/bootstrap")).json()["data"]
    listed = (await client.get("/api/v1/habit/list")).json()["data"]
    archived = (await client.get("/api/v1/habit/archived")).json()["data"]

    assert merged["list"] == listed
    assert merged["archived"] == archived
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_bootstrap.py -v`
Expected: FAIL，404

- [ ] **Step 3: 实现**

`app/api/v1/habit/route.py`，在 `list_archived_habits` 之后加：

```python
@router.get("/bootstrap", summary="习惯页首屏聚合（进行中 + 已归档）")
async def bootstrap_habits(current_user: User = Depends(AuthControl.is_authed)):
    """一次返回进行中与已归档两份列表，省掉小程序/Web 首屏的第二次往返"""
    habits = await habit_controller.list_active_with_status(current_user.id)
    archived = await habit_controller.get_archived_habits(current_user.id)
    return Success(
        data={
            "list": [HabitOut(**h).model_dump(mode="json") for h in habits],
            "archived": [HabitOut(**(await h.to_dict())).model_dump(mode="json") for h in archived],
        }
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_bootstrap.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add app/api/v1/habit/route.py tests/test_bootstrap.py
git commit -m "feat(habit): 新增 bootstrap 聚合端点"
```

---

### Task 6: `GET /api/v1/goal/bootstrap`

**Files:**
- Modify: `app/controllers/goal.py`
- Modify: `app/api/v1/goal/route.py:16-39`
- Test: `tests/test_bootstrap.py`

**Interfaces:**
- Produces:
  - `goal_controller.list_active_out(user_id: int) -> list[dict]`——把原本写在 `/list` 路由里的「取计划 + 统计任务数 + 统计习惯数 + 拼 dict」逻辑抽出来
  - `GET /api/v1/goal/bootstrap` → `Success(data={"list": [...], "archived": [...]})`

**为什么要先抽方法**：`/list` 路由里那段拼装逻辑有十来行，直接复制到 bootstrap 就是两份会各自漂移的代码。抽到 controller 后两个路由共用一份。

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_bootstrap.py`：

```python
from app.models.todo import Goal


async def test_goal_bootstrap_returns_active_and_archived(client, test_user):
    await Goal.create(user_id=test_user.id, name="学英语")
    await Goal.create(user_id=test_user.id, name="旧目标", is_archived=True)

    data = (await client.get("/api/v1/goal/bootstrap")).json()["data"]
    assert [g["name"] for g in data["list"]] == ["学英语"]
    assert [g["name"] for g in data["archived"]] == ["旧目标"]


async def test_goal_bootstrap_matches_separate_endpoints(client, test_user):
    await Goal.create(user_id=test_user.id, name="健身")

    merged = (await client.get("/api/v1/goal/bootstrap")).json()["data"]
    listed = (await client.get("/api/v1/goal/list")).json()["data"]
    archived = (await client.get("/api/v1/goal/archived")).json()["data"]

    assert merged["list"] == listed
    assert merged["archived"] == archived
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_bootstrap.py -v`
Expected: FAIL，404

- [ ] **Step 3: 抽出 controller 方法**

把 `app/api/v1/goal/route.py:16-31` 里 `/list` 的整段拼装逻辑原样搬进 `app/controllers/goal.py` 的 `GoalController`（字段名 `task_total` / `task_completed` / `habit_count` 与 `app/schemas/goal.py::GoalOut` 一一对应，不要改名）：

```python
    async def list_active_out(self, user_id: int) -> List[dict]:
        """进行中计划的输出字典列表，附带关联任务数与习惯数。

        /list 与 /bootstrap 共用，避免两处拼装逻辑各自漂移。
        """
        goals = await self.get_active_goals(user_id)
        goal_ids = [g.id for g in goals]
        task_counts = await self.get_task_counts(goal_ids)
        habit_counts = await self.get_habit_counts(goal_ids)

        result = []
        for goal in goals:
            data = await self.to_out_dict(goal)
            task_total, task_completed = task_counts.get(goal.id, (0, 0))
            data["task_total"] = task_total
            data["task_completed"] = task_completed
            data["habit_count"] = habit_counts.get(goal.id, 0)
            result.append(data)
        return result
```

- [ ] **Step 4: 改造 `/list` 并新增 `/bootstrap`**

`/list` 改为：

```python
@router.get("/list", summary="获取当前用户进行中的计划列表")
async def list_goals(current_user: User = Depends(AuthControl.is_authed)):
    result = [GoalOut(**d).model_dump() for d in await goal_controller.list_active_out(current_user.id)]
    return Success(data=result)
```

在 `list_archived_goals` 之后加：

```python
@router.get("/bootstrap", summary="计划页首屏聚合（进行中 + 已归档）")
async def bootstrap_goals(current_user: User = Depends(AuthControl.is_authed)):
    active = [GoalOut(**d).model_dump() for d in await goal_controller.list_active_out(current_user.id)]
    archived = [
        GoalOut(**(await goal_controller.to_out_dict(g))).model_dump()
        for g in await goal_controller.get_archived_goals(current_user.id)
    ]
    return Success(data={"list": active, "archived": archived})
```

`/bootstrap` 必须放在 `/detail` 这类带 Query 参数的路由**之前或之后都可以**（都是字面量路径，不冲突），但为可读性放在 `archived` 之后。

- [ ] **Step 5: 运行全部计划相关测试确认通过**

Run: `python -m pytest tests/test_bootstrap.py tests/test_goal.py -v`
Expected: PASS，且 `tests/test_goal.py` 原有用例**全部仍然通过**（这是抽取重构没改变行为的证据）

- [ ] **Step 6: 提交**

```bash
git add app/controllers/goal.py app/api/v1/goal/route.py tests/test_bootstrap.py
git commit -m "feat(goal): 抽出 list_active_out 并新增 bootstrap 聚合端点"
```

---

### Task 7: `GET /api/v1/project/bootstrap`

**Files:**
- Modify: `app/api/v1/project/route.py`
- Test: `tests/test_bootstrap.py`

**Interfaces:**
- Produces: `GET /api/v1/project/bootstrap` → `Success(data={"list": [...], "categories": [...]})`

对应云函数的 `project.bootstrap`（`list` + `listCategories`）。分类部分复用已有的 `category_controller.get_categories_for_user`，**不新建 `project/listCategories`**。

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_bootstrap.py`：

```python
from app.models.todo import Category, Project


async def test_project_bootstrap_returns_projects_and_categories(client, test_user):
    category = await Category.create(user_id=test_user.id, name="工作")
    await Project.create(user_id=test_user.id, name="上线计划", category_id=category.id)

    data = (await client.get("/api/v1/project/bootstrap")).json()["data"]
    assert [p["name"] for p in data["list"]] == ["上线计划"]
    assert [c["name"] for c in data["categories"]] == ["工作"]


async def test_project_bootstrap_matches_separate_endpoints(client, test_user):
    await Category.create(user_id=test_user.id, name="生活")
    await Project.create(user_id=test_user.id, name="搬家")

    merged = (await client.get("/api/v1/project/bootstrap")).json()["data"]
    projects = (await client.get("/api/v1/project/list")).json()["data"]
    categories = (await client.get("/api/v1/category/list")).json()["data"]

    assert merged["list"] == projects
    assert merged["categories"] == categories
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_bootstrap.py -v`
Expected: FAIL，404

- [ ] **Step 3: 实现**

`app/api/v1/project/route.py` 顶部 import 追加：

```python
from app.controllers.category import category_controller
from app.schemas.category import CategoryOut
```

在 `list_projects` 之后加：

```python
@router.get("/bootstrap", summary="项目页首屏聚合（项目/清单 + 分类）")
async def bootstrap_projects(current_user: User = Depends(AuthControl.is_authed)):
    """项目列表与分类列表一次返回；分类复用 category 模块，不重复实现一份"""
    projects = await project_controller.get_projects_for_user(current_user.id)
    categories = await category_controller.get_categories_for_user(current_user.id)
    return Success(
        data={
            "list": [ProjectOut(**(await project_controller.to_out_dict(p))).model_dump() for p in projects],
            "categories": [CategoryOut(**(await c.to_dict())).model_dump() for c in categories],
        }
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_bootstrap.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add app/api/v1/project/route.py tests/test_bootstrap.py
git commit -m "feat(project): 新增 bootstrap 聚合端点（项目 + 分类）"
```

---

### Task 8: `GET /api/v1/todo/stats-bootstrap`

**Files:**
- Modify: `app/api/v1/todos/route.py`
- Test: `tests/test_bootstrap.py`

**Interfaces:**
- Produces: `GET /api/v1/todo/stats-bootstrap`，Query 参数 `start_date` / `end_date` / `page` / `page_size` / `sort_by` / `sort_order`
  → `Success(data={"daily": [...], "quadrant": {...}, "completed": {"list": [...], "total": int, "page": int, "page_size": int}})`

对应云函数 `todo.statsBootstrap`（`weapp/cloudfunctions/todo/index.js:323`）。`completed` 部分固定查**已完成**的待办，供统计页的「已完成列表」用。

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_bootstrap.py`：

```python
from datetime import datetime

from app.models.todo import QuadrantType, TodoItem


async def test_stats_bootstrap_returns_three_sections(client, test_user):
    await TodoItem.create(
        title="已完成的事",
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
        is_completed=True,
        completed_at=datetime(2026, 8, 20, 10, 0, 0),
    )
    await TodoItem.create(
        title="没完成的事",
        user_id=test_user.id,
        quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT,
    )

    resp = await client.get("/api/v1/todo/stats-bootstrap", params={"page": 1, "page_size": 10})
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert "daily" in data and isinstance(data["daily"], list)
    assert "quadrant" in data and isinstance(data["quadrant"], dict)
    assert [t["title"] for t in data["completed"]["list"]] == ["已完成的事"]
    assert data["completed"]["total"] == 1
    assert data["completed"]["page"] == 1


async def test_stats_bootstrap_sections_match_separate_endpoints(client, test_user):
    await TodoItem.create(
        title="A",
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
        is_completed=True,
        completed_at=datetime(2026, 8, 21, 9, 0, 0),
    )

    merged = (await client.get("/api/v1/todo/stats-bootstrap")).json()["data"]
    daily = (await client.get("/api/v1/todo/statistics/daily")).json()["data"]
    quadrant = (await client.get("/api/v1/todo/statistics/quadrant")).json()["data"]

    assert merged["daily"] == daily
    assert merged["quadrant"] == quadrant
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_bootstrap.py -v`
Expected: FAIL，404

- [ ] **Step 3: 实现**

`app/api/v1/todos/route.py` 末尾追加：

```python
@router.get("/stats-bootstrap", summary="统计页首屏聚合（每日统计 + 象限统计 + 已完成列表）")
async def stats_bootstrap(
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    page: int = Query(1, description="已完成列表页码"),
    page_size: int = Query(20, description="已完成列表每页数量"),
    sort_by: Optional[str] = Query("completed_at", description="已完成列表排序字段"),
    sort_order: Optional[str] = Query("desc", description="已完成列表排序方向"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """统计页三块数据一次返回，替代小程序原先的 3 次云函数往返"""
    statistics = await todo_controller.get_statistics_by_date(
        user_id=current_user.id, start_date=start_date, end_date=end_date
    )
    quadrant = await todo_controller.get_quadrant_statistics(user_id=current_user.id)
    total, todos = await todo_controller.get_todos_by_user(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        is_completed=True,
        start_date=start_date,
        end_date=end_date,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    todo_ids = [todo.id for todo in todos]
    counts = await subtask_controller.get_counts_by_todo_ids(todo_ids)
    completed_list = []
    for todo in todos:
        todo_dict = await todo.to_dict()
        total_sub, completed_sub = counts.get(todo.id, (0, 0))
        completed_list.append(
            TodoItemOut(**todo_dict, subtask_total=total_sub, subtask_completed=completed_sub).model_dump()
        )

    return Success(
        data={
            "daily": [stat.model_dump() for stat in statistics],
            "quadrant": quadrant.model_dump(),
            "completed": {
                "list": completed_list,
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        }
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_bootstrap.py tests/test_todo_statistics.py -v`
Expected: PASS，且 `test_todo_statistics.py` 原有用例仍全绿

- [ ] **Step 5: 提交**

```bash
git add app/api/v1/todos/route.py tests/test_bootstrap.py
git commit -m "feat(todo): 新增 stats-bootstrap 统计页聚合端点"
```

---

### Task 9: `GET /api/v1/habit/summary`

**Files:**
- Modify: `app/controllers/habit.py`
- Modify: `app/api/v1/habit/route.py`
- Test: `tests/test_habit_summary.py`

**Interfaces:**
- Produces:
  - `habit_controller.is_scheduled_day(habit: Habit, day: date) -> bool`——**纯函数**，只看频率配置，不查库
  - `habit_controller.summary(user_id: int, start: date, end: date, today: date) -> list[dict]`，元素为 `{"habit_id": int, "name": str, "frequency_type": str, "completed": int, "expected": int, "streak": int | None}`
  - `GET /api/v1/habit/summary?start_date=&end_date=` → `Success(data=[...])`

移植自云函数 `weapp/cloudfunctions/habit/index.js:268-298`，供回顾总结页的习惯坚持度统计使用。

**注意与现有 `should_generate_today` 的区别**：那个方法对 `weekly_count` 会查库（看本周完成了几次），是**有状态**的，不能用于逐日回溯。所以要单独一个纯函数版本，`weekly_count` 在 `summary` 里按「总天数 ÷ 7 × 每周次数」单独算，与云函数一致。

- [ ] **Step 1: 写失败的测试**

新建 `tests/test_habit_summary.py`：

```python
from datetime import date

from app.controllers.habit import habit_controller
from app.models.todo import Habit, HabitFrequencyType, QuadrantType, TodoItem


async def test_is_scheduled_day_daily(db, test_user):
    habit = await Habit.create(user_id=test_user.id, name="每天", frequency_type=HabitFrequencyType.DAILY)
    assert habit_controller.is_scheduled_day(habit, date(2026, 8, 24)) is True


async def test_is_scheduled_day_weekly_days(db, test_user):
    habit = await Habit.create(
        user_id=test_user.id,
        name="周一三五",
        frequency_type=HabitFrequencyType.WEEKLY_DAYS,
        frequency_config={"days": [1, 3, 5]},
    )
    assert habit_controller.is_scheduled_day(habit, date(2026, 8, 24)) is True   # 周一
    assert habit_controller.is_scheduled_day(habit, date(2026, 8, 25)) is False  # 周二


async def test_summary_counts_expected_and_completed(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="晨读", frequency_type=HabitFrequencyType.DAILY)
    for day, done in [(21, True), (22, True), (23, False)]:
        await TodoItem.create(
            title="晨读",
            user_id=test_user.id,
            habit_id=habit.id,
            quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT,
            generated_date=date(2026, 8, day),
            is_completed=done,
        )

    result = await habit_controller.summary(
        user_id=test_user.id, start=date(2026, 8, 21), end=date(2026, 8, 23), today=date(2026, 8, 23)
    )
    assert len(result) == 1
    assert result[0]["name"] == "晨读"
    assert result[0]["expected"] == 3
    assert result[0]["completed"] == 2


async def test_summary_excludes_paused_and_archived(client, test_user):
    await Habit.create(
        user_id=test_user.id, name="暂停的", frequency_type=HabitFrequencyType.DAILY, is_paused=True
    )
    await Habit.create(
        user_id=test_user.id, name="归档的", frequency_type=HabitFrequencyType.DAILY, is_archived=True
    )
    await Habit.create(user_id=test_user.id, name="正常的", frequency_type=HabitFrequencyType.DAILY)

    result = await habit_controller.summary(
        user_id=test_user.id, start=date(2026, 8, 21), end=date(2026, 8, 23), today=date(2026, 8, 23)
    )
    assert [r["name"] for r in result] == ["正常的"]


async def test_summary_weekly_count_uses_weekly_formula(client, test_user):
    habit = await Habit.create(
        user_id=test_user.id,
        name="每周三次",
        frequency_type=HabitFrequencyType.WEEKLY_COUNT,
        frequency_config={"count": 3},
    )
    await TodoItem.create(
        title="每周三次",
        user_id=test_user.id,
        habit_id=habit.id,
        quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT,
        generated_date=date(2026, 8, 24),
        is_completed=True,
    )

    # 8/17 ~ 8/30 共 14 天 = 2 周，期望 2*3 = 6 次
    result = await habit_controller.summary(
        user_id=test_user.id, start=date(2026, 8, 17), end=date(2026, 8, 30), today=date(2026, 8, 30)
    )
    assert result[0]["expected"] == 6
    assert result[0]["completed"] == 1
    assert result[0]["streak"] is None


async def test_summary_endpoint_returns_list(client, test_user):
    await Habit.create(user_id=test_user.id, name="喝水", frequency_type=HabitFrequencyType.DAILY)

    resp = await client.get(
        "/api/v1/habit/summary", params={"start_date": "2026-08-21", "end_date": "2026-08-23"}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert data[0]["name"] == "喝水"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_habit_summary.py -v`
Expected: FAIL，`AttributeError: 'HabitController' object has no attribute 'is_scheduled_day'`

- [ ] **Step 3: 实现 controller**

`app/controllers/habit.py` 的 `HabitController` 内追加（放在 `should_generate_today` 之后）：

```python
    def is_scheduled_day(self, habit: Habit, day: date) -> bool:
        """某天是否是该习惯的计划日。纯函数，不查库。

        与 should_generate_today 的区别：那个方法对 weekly_count 要查本周已完成次数，
        是有状态的，没法用来逐日回溯；这里的 weekly_count 一律返回 False，
        因为「每周 N 次」不绑定具体星期，期望次数在 summary 里按周数换算。
        """
        config = habit.frequency_config or {}
        if habit.frequency_type == HabitFrequencyType.DAILY:
            return True
        if habit.frequency_type == HabitFrequencyType.WEEKLY_DAYS:
            return day.isoweekday() in config.get("days", [])
        if habit.frequency_type == HabitFrequencyType.INTERVAL_DAYS:
            interval = config.get("interval", 1)
            anchor = habit.created_at.date()
            return (day - anchor).days % interval == 0
        return False

    async def summary(self, user_id: int, start: date, end: date, today: date) -> List[Dict[str, Any]]:
        """周期内的习惯坚持度统计，供回顾总结页使用。

        移植自云函数 habit.summary：
        - weekly_count：期望 = 整周数 × 每周次数（不逐日判定）
        - 其余频率：从 max(习惯创建日, start) 逐日走到 min(today, end)，
          计划日计入 expected，当天打卡待办已完成则计入 completed
        统计窗口右端夹到 today，避免把未来的计划日算成「没做到」。
        """
        habits = await Habit.filter(user_id=user_id, is_archived=False, is_paused=False).order_by("-created_at")

        result: List[Dict[str, Any]] = []
        for habit in habits:
            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT:
                count = (habit.frequency_config or {}).get("count", 0)
                total_days = (end - start).days + 1
                expected = (total_days // 7) * count
                completed = await TodoItem.filter(
                    habit_id=habit.id,
                    is_completed=True,
                    generated_date__gte=start,
                    generated_date__lte=end,
                ).count()
                result.append(
                    {
                        "habit_id": habit.id,
                        "name": habit.name,
                        "frequency_type": habit.frequency_type,
                        "completed": completed,
                        "expected": expected,
                        "streak": None,
                    }
                )
                continue

            created_day = habit.created_at.date()
            range_start = max(created_day, start)
            range_end = min(today, end)

            todos = await TodoItem.filter(
                habit_id=habit.id, generated_date__gte=start, generated_date__lte=end
            ).values("generated_date", "is_completed")
            done_map = {t["generated_date"]: t["is_completed"] for t in todos}

            expected = 0
            completed = 0
            cursor = range_start
            while cursor <= range_end:
                if self.is_scheduled_day(habit, cursor):
                    expected += 1
                    if done_map.get(cursor):
                        completed += 1
                cursor += timedelta(days=1)

            result.append(
                {
                    "habit_id": habit.id,
                    "name": habit.name,
                    "frequency_type": habit.frequency_type,
                    "completed": completed,
                    "expected": expected,
                    "streak": await self.calc_streak(habit, today),
                }
            )

        return result
```

> 检查 `app/controllers/habit.py` 顶部的 import：需要 `date`、`timedelta`、`List`、`Dict`、`Any`，缺什么补什么。

- [ ] **Step 4: 实现路由**

`app/api/v1/habit/route.py` 顶部 import 补 `from datetime import date`、`from typing import Optional`，末尾追加：

```python
@router.get("/summary", summary="周期内的习惯坚持度统计")
async def habit_summary(
    start_date: date = Query(..., description="统计开始日期"),
    end_date: date = Query(..., description="统计结束日期"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """回顾总结页用：每个进行中习惯在该周期内的应打卡次数、实际完成次数、连续天数"""
    result = await habit_controller.summary(
        user_id=current_user.id, start=start_date, end=end_date, today=date.today()
    )
    return Success(data=result)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_habit_summary.py tests/test_habit.py -v`
Expected: PASS，且 `test_habit.py` 原有 31 个用例仍全绿

- [ ] **Step 6: 提交**

```bash
git add app/controllers/habit.py app/api/v1/habit/route.py tests/test_habit_summary.py
git commit -m "feat(habit): 新增周期坚持度统计接口 summary"
```

---

### Task 10: pet 模型

**Files:**
- Create: `app/models/pet.py`
- Modify: `app/models/__init__.py`
- Test: `tests/test_pet.py`

**Interfaces:**
- Produces: `PetProfile` / `PetCat` / `PetLine` 三个 Tortoise 模型

**建模取舍**（见 spec §9.1）：`stats` 与 `owned_cats` 用 JSON 而非独立表——这些数据只按 user 单行读写、从不跨用户查询，拆表换不来查询能力。`unlock` / `conditions` 存声明式规则数组，是规则型配置的正常存法。

- [ ] **Step 1: 写失败的测试**

新建 `tests/test_pet.py`：

```python
from app.models.pet import PetCat, PetLine, PetProfile


async def test_pet_profile_defaults(db, test_user):
    profile = await PetProfile.create(user_id=test_user.id)
    assert profile.active_cat_code == "orange"
    assert profile.stats == {}
    assert profile.owned_cats == []
    assert profile.visit_streak == 1


async def test_pet_cat_stores_unlock_rules(db):
    cat = await PetCat.create(
        code="cow", name="奶牛猫", persona="毒舌", order=2,
        unlock=[{"field": "_total", "op": "gte", "value": 50}],
    )
    reloaded = await PetCat.get(code="cow")
    assert reloaded.unlock[0]["value"] == 50
    assert cat.is_active is True


async def test_pet_line_cat_code_nullable_means_universal(db):
    line = await PetLine.create(
        code="t_clear", cat_code=None, page="today", priority=10,
        conditions=[{"field": "pending", "op": "eq", "value": 0}],
        texts=["今天的事都做完了，好好歇会儿喵～"],
        unlock=[],
    )
    assert line.cat_code is None
    assert len(line.texts) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_pet.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.models.pet'`

- [ ] **Step 3: 实现模型**

新建 `app/models/pet.py`：

```python
from tortoise import fields

from .base import BaseModel, TimestampMixin


class PetProfile(BaseModel, TimestampMixin):
    """养成猫的用户状态，一人一行。

    stats / owned_cats 用 JSON 而非独立表：这两份数据只按 user 单行读写、
    从不跨用户查询，拆成关系表并换不来查询能力，反而多两次 JOIN。
    """

    user = fields.OneToOneField("models.User", related_name="pet_profile", description="所属用户")
    active_cat_code = fields.CharField(max_length=32, default="orange", description="当前陪伴的猫")
    pet_name = fields.CharField(max_length=20, null=True, description="用户给猫起的名字")
    stats = fields.JSONField(default=dict, description="分维度累计计数，如 {'todo_completed': 12}")
    owned_cats = fields.JSONField(default=list, description="已解锁的猫，如 [{'cat_id': 'orange', 'at': 1690000000000}]")
    visit_streak = fields.IntField(default=1, description="连续来访天数")
    last_seen_at = fields.DatetimeField(null=True, description="最近一次来访时间")

    class Meta:
        table = "pet_profile"


class PetCat(BaseModel, TimestampMixin):
    """猫的定义，全用户共享的只读配置"""

    code = fields.CharField(max_length=32, unique=True, description="猫的标识，如 orange", index=True)
    name = fields.CharField(max_length=32, description="猫的名字，如 橘猫")
    persona = fields.CharField(max_length=32, description="性格，如 元气/毒舌/温柔")
    order = fields.IntField(default=0, description="展示顺序")
    unlock = fields.JSONField(default=list, description="解锁条件，[{field, op, value}] 与关系；空数组表示初始猫")
    is_active = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "pet_cat"


class PetLine(BaseModel, TimestampMixin):
    """猫的台词，全用户共享的只读配置"""

    code = fields.CharField(max_length=64, unique=True, description="台词标识，如 t_overdue", index=True)
    cat_code = fields.CharField(max_length=32, null=True, description="专属于哪只猫；为空表示通用兜底", index=True)
    page = fields.CharField(max_length=32, description="生效页面：today/quadrant/habit/pet 等", index=True)
    priority = fields.IntField(default=0, description="优先级，同页面取最高的一条")
    conditions = fields.JSONField(default=list, description="页面上下文触发条件，[{field, op, value}]")
    texts = fields.JSONField(default=list, description="文案变体数组，客户端按日期种子轮换")
    unlock = fields.JSONField(default=list, description="解锁条件；未达成时这句话不会出现")

    class Meta:
        table = "pet_line"
```

`app/models/__init__.py` 末尾追加：

```python
from .pet import PetCat, PetLine, PetProfile
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_pet.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 生成迁移文件**

```bash
source .venv/bin/activate
aerich migrate --name add_pet_tables
```

打开生成的迁移文件确认建了 `pet_profile` / `pet_cat` / `pet_line` 三张表。

- [ ] **Step 6: 提交**

```bash
git add app/models/pet.py app/models/__init__.py tests/test_pet.py migrations/
git commit -m "feat(pet): 新增养成猫的 PetProfile/PetCat/PetLine 模型"
```

---

### Task 11: pet 配置初始数据

**Files:**
- Create: `app/core/pet_seed.py`
- Modify: `app/core/init_app.py`
- Test: `tests/test_pet.py`

**Interfaces:**
- Consumes: `PetCat` / `PetLine`（Task 10）
- Produces:
  - `app.core.pet_seed.CATS: list[dict]`、`app.core.pet_seed.LINES: list[dict]`
  - `init_pet_config()`，幂等（按 `code` upsert），由 `init_data()` 调用

内容全部移植自 `weapp/cloudfunctions/pet/seed.js`。**内容与逻辑分离**：文案改动只碰 `pet_seed.py`，不碰 controller。

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_pet.py`：

```python
from app.core.init_app import init_pet_config


async def test_init_pet_config_is_idempotent(db):
    await init_pet_config()
    first_count = await PetCat.all().count()
    await init_pet_config()
    assert await PetCat.all().count() == first_count
    assert first_count == 3


async def test_init_pet_config_seeds_lines(db):
    await init_pet_config()
    assert await PetLine.all().count() == 13
    universal = await PetLine.filter(cat_code=None).count()
    assert universal == 13, "移植阶段所有台词都是通用的（云函数里 cat_id 全是 '*'）"


async def test_init_pet_config_updates_changed_text(db):
    await init_pet_config()
    line = await PetLine.get(code="p_idle")
    await PetLine.filter(code="p_idle").update(texts=["被改坏了"])
    await init_pet_config()
    reloaded = await PetLine.get(code="p_idle")
    assert reloaded.texts != ["被改坏了"], "重跑初始化应把配置改回种子里的内容"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_pet.py -v`
Expected: FAIL，`ImportError: cannot import name 'init_pet_config'`

- [ ] **Step 3: 写种子数据**

新建 `app/core/pet_seed.py`，把 `weapp/cloudfunctions/pet/seed.js` 的 `CATS` 与 `LINES` 原样移植：

```python
"""养成猫的配置内容（猫的定义 + 台词）。

与业务逻辑分离：改文案只动这个文件。
texts 是数组，客户端按「日期种子」在其中轮换——同一天内稳定、跨天变化，
避免同一句话天天出现变成墙纸。
移植自 weapp/cloudfunctions/pet/seed.js。
"""

CATS = [
    {"code": "orange", "name": "橘猫", "persona": "元气", "order": 1, "unlock": []},
    {"code": "cow", "name": "奶牛猫", "persona": "毒舌", "order": 2,
     "unlock": [{"field": "_total", "op": "gte", "value": 50}]},
    {"code": "calico", "name": "三花", "persona": "温柔", "order": 3,
     "unlock": [{"field": "_total", "op": "gte", "value": 150}]},
]


def _line(code, page, priority, conditions, texts, unlock=None):
    return {
        "code": code,
        "cat_code": None,  # 云函数里 cat_id 全是 '*'（通用），移植阶段保持一致
        "page": page,
        "priority": priority,
        "conditions": conditions,
        "texts": texts,
        "unlock": unlock or [],
    }


LINES = [
    # ---- 今日 ----
    _line("t_overdue", "today", 30, [{"field": "overdue", "op": "gte", "value": 1}], [
        "有 {overdue} 件事已经过期了，别再拖啦喵",
        "{overdue} 件事在等你喵…要不先挑最简单的那个？",
        "过期 {overdue} 件。没关系，今天补回来就好喵",
    ]),
    _line("t_habits", "today", 20, [{"field": "pending_habits", "op": "gte", "value": 3}], [
        "还有 {pending_habits} 个习惯没打卡，去点一下喵",
        "{pending_habits} 个习惯在排队等你喵～",
    ]),
    _line("t_clear", "today", 10, [{"field": "pending", "op": "eq", "value": 0}], [
        "今天的事都做完了，好好歇会儿喵～",
        "全部清空！今天的你很厉害喵",
    ]),
    _line("t_deep", "today", 25, [{"field": "pending", "op": "gte", "value": 5}],
          ["今天排了 {pending} 件事…确定做得完吗喵？挑三件最重要的就好"],
          [{"field": "_total", "op": "gte", "value": 20}]),
    # ---- 四象限 ----
    _line("q_ui", "quadrant", 30, [{"field": "urgent_important", "op": "gte", "value": 3}], [
        "有 {urgent_important} 件又重要又急的事压着，先处理它们喵～",
        "{urgent_important} 件急事排队呢，挑一个开始吧喵",
        "第一象限有点满了（{urgent_important} 件），别硬扛喵",
    ]),
    _line("q_overdue", "quadrant", 20, [{"field": "overdue", "op": "gte", "value": 5}], [
        "积压了 {overdue} 件过期任务，抽空清理一下喵",
        "{overdue} 件过期的…要不要删掉几个其实不重要的喵？",
    ]),
    _line("q_clear", "quadrant", 10, [{"field": "total", "op": "eq", "value": 0}], [
        "四象限都清空啦，太厉害喵！",
    ]),
    # ---- 习惯 ----
    _line("h_pending", "habit", 10, [{"field": "pending", "op": "gte", "value": 1}], [
        "还有 {pending} 个习惯待打卡喵",
        "{pending} 个习惯还没完成，一起加油喵～",
    ]),
    _line("h_done", "habit", 20, [{"field": "pending", "op": "eq", "value": 0}], [
        "今天习惯全完成，真自律喵！",
        "一个不落，厉害喵～",
    ]),
    # ---- 猫窝页 ----
    _line("p_visit", "pet", 40, [{"field": "visit_streak", "op": "gte", "value": 3}], [
        "你已经连着 {visit_streak} 天来看我啦喵～",
    ]),
    _line("p_big", "pet", 30, [{"field": "_total", "op": "gte", "value": 150}], [
        "我们一起完成很多事啦，谢谢你喵～",
    ]),
    _line("p_small", "pet", 20, [{"field": "_total", "op": "lt", "value": 10}], [
        "我还小，陪着我一起长大喵～",
    ]),
    _line("p_idle", "pet", 10, [], [
        "喵～我在呢，今天也要加油呀",
        "今天想做点什么喵？",
    ]),
]
```

- [ ] **Step 4: 写初始化函数**

`app/core/init_app.py` 顶部 import 追加：

```python
from app.core.pet_seed import CATS as PET_CATS
from app.core.pet_seed import LINES as PET_LINES
from app.models.pet import PetCat, PetLine
```

在 `init_miniprogram_role()` 之后加：

```python
async def init_pet_config():
    """幂等地写入养成猫的配置数据（猫 + 台词）。

    按 code upsert：改了 pet_seed.py 里的文案，重启即生效；
    updated_at 随之刷新，客户端的 config_version 因此变化并自动拉取新配置。
    """
    for cat in PET_CATS:
        await PetCat.update_or_create(code=cat["code"], defaults={k: v for k, v in cat.items() if k != "code"})
    for line in PET_LINES:
        await PetLine.update_or_create(code=line["code"], defaults={k: v for k, v in line.items() if k != "code"})
```

`init_data()` 末尾追加 `await init_pet_config()`。

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_pet.py -v`
Expected: PASS（6 passed）

- [ ] **Step 6: 提交**

```bash
git add app/core/pet_seed.py app/core/init_app.py tests/test_pet.py
git commit -m "feat(pet): 移植猫与台词配置数据并在启动时幂等写入"
```

---

### Task 12: `GET /api/v1/pet/bootstrap`

**Files:**
- Create: `app/controllers/pet.py`
- Create: `app/schemas/pet.py`
- Create: `app/api/v1/pet/__init__.py`
- Create: `app/api/v1/pet/route.py`
- Modify: `app/api/v1/__init__.py`
- Test: `tests/test_pet.py`

**Interfaces:**
- Consumes: `PetProfile` / `PetCat` / `PetLine`（Task 10）、配置数据（Task 11）
- Produces:
  - `pet_controller.ensure_profile(user_id: int) -> PetProfile`
  - `pet_controller.apply_unlocks(profile: PetProfile) -> list[str]`（返回本次新解锁的 cat code）
  - `pet_controller.touch_visit(profile: PetProfile) -> PetProfile`
  - `pet_controller.load_config() -> dict`，形如 `{"cats": [...], "lines": [...], "version": int}`
  - `GET /api/v1/pet/bootstrap?config_version=&touch=` → `Success(data={"pet": {...}, "total": int, "newly_unlocked": [...], "config_version": int, "config"?: {...}})`

**关键兼容约束**：返回体必须严格匹配小程序 `weapp/miniprogram/utils/cat.js` 已有的消费格式，让那 133 行本地缓存与台词求值逻辑**零改动**。具体三条：

1. `pet.owned_cats` 是 `[{"cat_id": "orange", "at": <毫秒时间戳>}, ...]`
2. `config.cats` 的元素带 **`_id`** 键（值就是 `code`），`config.lines` 的元素带 **`_id`** 与 **`cat_id`** 键，其中通用台词的 `cat_id` 是字符串 `"*"`（不是 `null`）
3. `config_version` 是**毫秒时间戳整数**——取两张配置表 `updated_at` 的最大值

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_pet.py`：

```python
async def test_pet_bootstrap_creates_profile_on_first_call(client, test_user):
    await init_pet_config()
    resp = await client.get("/api/v1/pet/bootstrap")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["pet"]["active_cat_id"] == "orange"
    assert data["pet"]["owned_cats"] == [{"cat_id": "orange", "at": data["pet"]["owned_cats"][0]["at"]}]
    assert data["total"] == 0
    assert await PetProfile.filter(user_id=test_user.id).count() == 1


async def test_pet_bootstrap_returns_config_in_client_shape(client, test_user):
    await init_pet_config()
    data = (await client.get("/api/v1/pet/bootstrap")).json()["data"]

    config = data["config"]
    assert config["version"] == data["config_version"]
    assert {c["_id"] for c in config["cats"]} == {"orange", "cow", "calico"}
    # 通用台词的 cat_id 必须是 "*"，cat.js 的过滤逻辑依赖这个字面量
    assert all(line["cat_id"] == "*" for line in config["lines"])
    assert all("_id" in line for line in config["lines"])


async def test_pet_bootstrap_omits_config_when_version_matches(client, test_user):
    await init_pet_config()
    first = (await client.get("/api/v1/pet/bootstrap")).json()["data"]
    version = first["config_version"]

    second = (await client.get("/api/v1/pet/bootstrap", params={"config_version": version})).json()["data"]
    assert "config" not in second, "版本一致时不应回传配置体，这是热页面零流量的前提"
    assert second["config_version"] == version


async def test_pet_bootstrap_unlocks_cat_when_total_reaches_threshold(client, test_user):
    await init_pet_config()
    await PetProfile.create(user_id=test_user.id, stats={"todo_completed": 60}, owned_cats=[{"cat_id": "orange", "at": 0}])

    data = (await client.get("/api/v1/pet/bootstrap")).json()["data"]
    assert data["total"] == 60
    assert "cow" in data["newly_unlocked"]
    assert {o["cat_id"] for o in data["pet"]["owned_cats"]} == {"orange", "cow"}
    assert "calico" not in data["newly_unlocked"], "150 的门槛还没到"


async def test_pet_bootstrap_touch_false_does_not_update_visit(client, test_user):
    await init_pet_config()
    await client.get("/api/v1/pet/bootstrap")
    profile = await PetProfile.get(user_id=test_user.id)
    before = profile.last_seen_at

    await client.get("/api/v1/pet/bootstrap", params={"touch": "false"})
    profile = await PetProfile.get(user_id=test_user.id)
    assert profile.last_seen_at == before
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_pet.py -v`
Expected: FAIL，404

- [ ] **Step 3: 写 controller**

新建 `app/controllers/pet.py`：

```python
"""养成猫业务逻辑。

配置数据（猫 + 台词）全用户共享、只读；用户数据一人一行。
返回体刻意贴合小程序 utils/cat.js 已有的消费格式（cats/lines 带 _id、
通用台词 cat_id 为 "*"），让客户端那份本地缓存与台词求值逻辑零改动。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.pet import PetCat, PetLine, PetProfile

# 计数维度：新增维度时在这里加一项，解锁条件与台词条件都能直接引用
STAT_FIELDS = ["todo_completed", "habit_checkin", "review_done", "goal_achieved"]

# 声明式条件求值支持的运算符
OPS = {
    "gte": lambda a, b: a >= b,
    "gt": lambda a, b: a > b,
    "lte": lambda a, b: a <= b,
    "lt": lambda a, b: a < b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
}


def _to_ms(dt: Optional[datetime]) -> int:
    return int(dt.timestamp() * 1000) if dt else 0


class PetController:
    def total_of(self, stats: Optional[dict]) -> int:
        """累计计数总和，驱动成长阶段与解锁"""
        stats = stats or {}
        return sum(int(stats.get(field, 0) or 0) for field in STAT_FIELDS)

    def matches(self, conditions: Optional[list], ctx: dict) -> bool:
        """声明式条件求值：[{field, op, value}]，多条为「与」关系"""
        if not conditions:
            return True
        for cond in conditions:
            fn = OPS.get(cond.get("op"))
            if fn is None:
                return False
            field = cond.get("field")
            left = self.total_of(ctx) if field == "_total" else (ctx.get(field, 0) or 0)
            if not fn(left, cond.get("value")):
                return False
        return True

    async def ensure_profile(self, user_id: int) -> PetProfile:
        """读取用户的猫，不存在则按初始状态创建"""
        profile = await PetProfile.filter(user_id=user_id).first()
        if profile:
            return profile
        return await PetProfile.create(
            user_id=user_id,
            active_cat_code="orange",
            owned_cats=[{"cat_id": "orange", "at": _to_ms(datetime.now())}],
            stats={},
            visit_streak=1,
            last_seen_at=datetime.now(),
        )

    async def apply_unlocks(self, profile: PetProfile) -> List[str]:
        """按 stats 判定应当拥有哪些猫，新解锁的写回并返回（供前端弹提示）"""
        owned = list(profile.owned_cats or [])
        owned_ids = {o.get("cat_id") for o in owned}
        newly: List[str] = []
        now_ms = _to_ms(datetime.now())

        for cat in await PetCat.filter(is_active=True).order_by("order"):
            if cat.code in owned_ids:
                continue
            if self.matches(cat.unlock, profile.stats or {}):
                owned.append({"cat_id": cat.code, "at": now_ms})
                newly.append(cat.code)

        if newly:
            profile.owned_cats = owned
            await profile.save(update_fields=["owned_cats", "updated_at"])
        return newly

    async def touch_visit(self, profile: PetProfile) -> PetProfile:
        """记录来访：跨天才更新，避免同一天反复进页面反复写库"""
        now = datetime.now()
        last = profile.last_seen_at
        if last and last.date() == now.date():
            return profile

        if last and (now - last).days < 2:
            profile.visit_streak = (profile.visit_streak or 0) + 1
        else:
            profile.visit_streak = 1
        profile.last_seen_at = now
        await profile.save(update_fields=["visit_streak", "last_seen_at", "updated_at"])
        return profile

    async def load_config(self) -> Dict[str, Any]:
        """配置版本 = 两张配置表中最大的 updated_at（毫秒）。

        改了台词自动生效，无需手工维护版本号。
        """
        cats = await PetCat.filter(is_active=True).order_by("order")
        lines = await PetLine.all()

        version = 0
        for row in list(cats) + list(lines):
            version = max(version, _to_ms(row.updated_at))

        return {
            "cats": [
                {
                    "_id": c.code,
                    "name": c.name,
                    "persona": c.persona,
                    "order": c.order,
                    "unlock": c.unlock or [],
                }
                for c in cats
            ],
            "lines": [
                {
                    "_id": line.code,
                    # 客户端用字面量 "*" 表示通用台词，这里做一次转换，
                    # 让 utils/cat.js 的过滤逻辑不用改
                    "cat_id": line.cat_code or "*",
                    "page": line.page,
                    "priority": line.priority,
                    "conditions": line.conditions or [],
                    "texts": line.texts or [],
                    "unlock": line.unlock or [],
                }
                for line in lines
            ],
            "version": version,
        }

    def profile_out(self, profile: PetProfile) -> Dict[str, Any]:
        """客户端 saveBootstrap 消费的字段集合"""
        return {
            "active_cat_id": profile.active_cat_code,
            "pet_name": profile.pet_name or "",
            "stats": profile.stats or {},
            "owned_cats": profile.owned_cats or [],
            "visit_streak": profile.visit_streak or 0,
            "last_seen_at": _to_ms(profile.last_seen_at),
        }


pet_controller = PetController()
```

- [ ] **Step 4: 写 schema 与路由**

新建 `app/schemas/pet.py`：

```python
from typing import Optional

from pydantic import BaseModel, Field


class PetUpdate(BaseModel):
    active_cat_id: Optional[str] = Field(None, description="切换到的猫，必须已解锁")
    pet_name: Optional[str] = Field(None, description="给猫起的名字，超过 20 字会被截断")
```

新建 `app/api/v1/pet/route.py`：

```python
import logging

from fastapi import APIRouter, Depends, Query

from app.controllers.pet import pet_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.schemas.base import Success

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
```

新建 `app/api/v1/pet/__init__.py`：

```python
from fastapi import APIRouter

from .route import router

pet_router = APIRouter()
pet_router.include_router(router, tags=["养成猫"])

__all__ = ["pet_router"]
```

`app/api/v1/__init__.py`：import 处加 `from .pet import pet_router`，注册处加

```python
v1_router.include_router(pet_router, prefix="/pet", dependencies=[DependPermission])
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_pet.py -v`
Expected: PASS（11 passed）

- [ ] **Step 6: 提交**

```bash
git add app/controllers/pet.py app/schemas/pet.py app/api/v1/pet/ app/api/v1/__init__.py tests/test_pet.py
git commit -m "feat(pet): 新增 bootstrap 接口，返回体对齐小程序既有缓存格式"
```

---

### Task 13: `POST /api/v1/pet/update`

**Files:**
- Modify: `app/controllers/pet.py`
- Modify: `app/api/v1/pet/route.py`
- Test: `tests/test_pet.py`

**Interfaces:**
- Consumes: `pet_controller.ensure_profile`、`PetUpdate`（Task 12）
- Produces: `POST /api/v1/pet/update`，请求体 `{"active_cat_id"?: str, "pet_name"?: str}` → `Success(data=<profile_out 结构>)`；切到未解锁的猫返回 `code=400`

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_pet.py`：

```python
async def test_pet_update_switches_to_owned_cat(client, test_user):
    await init_pet_config()
    await PetProfile.create(
        user_id=test_user.id,
        owned_cats=[{"cat_id": "orange", "at": 0}, {"cat_id": "cow", "at": 0}],
    )

    resp = await client.post("/api/v1/pet/update", json={"active_cat_id": "cow"})
    assert resp.status_code == 200
    assert resp.json()["data"]["active_cat_id"] == "cow"

    profile = await PetProfile.get(user_id=test_user.id)
    assert profile.active_cat_code == "cow"


async def test_pet_update_rejects_locked_cat(client, test_user):
    await init_pet_config()
    await PetProfile.create(user_id=test_user.id, owned_cats=[{"cat_id": "orange", "at": 0}])

    resp = await client.post("/api/v1/pet/update", json={"active_cat_id": "calico"})
    assert resp.json()["code"] == 400
    assert "解锁" in resp.json()["msg"]

    profile = await PetProfile.get(user_id=test_user.id)
    assert profile.active_cat_code == "orange"


async def test_pet_update_truncates_long_name(client, test_user):
    await init_pet_config()
    await PetProfile.create(user_id=test_user.id, owned_cats=[{"cat_id": "orange", "at": 0}])

    long_name = "喵" * 30
    resp = await client.post("/api/v1/pet/update", json={"pet_name": long_name})
    assert resp.json()["data"]["pet_name"] == "喵" * 20


async def test_pet_update_creates_profile_if_missing(client, test_user):
    await init_pet_config()
    resp = await client.post("/api/v1/pet/update", json={"pet_name": "小橘"})
    assert resp.json()["data"]["pet_name"] == "小橘"
    assert await PetProfile.filter(user_id=test_user.id).count() == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_pet.py -v`
Expected: FAIL，404

- [ ] **Step 3: 实现**

`app/controllers/pet.py` 的 `PetController` 内追加：

```python
    async def update_profile(self, user_id: int, active_cat_id: Optional[str], pet_name: Optional[str]) -> PetProfile:
        """更新用户的猫。切换到未解锁的猫会抛 ValueError，由路由转成 400。"""
        profile = await self.ensure_profile(user_id)
        fields = ["updated_at"]

        if active_cat_id is not None:
            owned = {o.get("cat_id") for o in (profile.owned_cats or [])}
            if active_cat_id not in owned:
                raise ValueError("这只猫还没解锁")
            profile.active_cat_code = active_cat_id
            fields.append("active_cat_code")

        if pet_name is not None:
            profile.pet_name = str(pet_name)[:20]
            fields.append("pet_name")

        await profile.save(update_fields=fields)
        return profile
```

`app/api/v1/pet/route.py`：import 追加 `from app.schemas.base import Fail, Success` 与 `from app.schemas.pet import PetUpdate`，末尾加

```python
@router.post("/update", summary="切换陪伴的猫 / 给猫起名")
async def update_pet(pet_in: PetUpdate, current_user: User = Depends(AuthControl.is_authed)):
    try:
        profile = await pet_controller.update_profile(
            user_id=current_user.id, active_cat_id=pet_in.active_cat_id, pet_name=pet_in.pet_name
        )
    except ValueError as e:
        return Fail(code=400, msg=str(e))
    return Success(data=pet_controller.profile_out(profile))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_pet.py -v`
Expected: PASS（15 passed）

- [ ] **Step 5: 提交**

```bash
git add app/controllers/pet.py app/api/v1/pet/route.py tests/test_pet.py
git commit -m "feat(pet): 新增 update 接口，支持切换猫与起名"
```

---

### Task 14: 完成待办时累加 pet 计数

**Files:**
- Modify: `app/controllers/pet.py`
- Modify: `app/controllers/todo.py:116-137`
- Test: `tests/test_pet.py`

**Interfaces:**
- Consumes: `pet_controller.ensure_profile`（Task 12）
- Produces: `pet_controller.increment(user_id: int, field: str, delta: int = 1) -> None`；`todo_controller.update_todo` 在「由未完成变为已完成」时调用它

对应云函数 `weapp/cloudfunctions/todo/index.js:340` 的 `ensurePetIncrement`。

**注意 `stats` 是 JSON 字段，不能用 `F()` 原子自增**（见 spec §A.4 的同类说明），必须 `select_for_update()` 读-改-写，否则并发完成两个任务会丢计数。

**取消完成不做回滚**——与云函数一致，计数只增不减。

- [ ] **Step 1: 写失败的测试**

追加到 `tests/test_pet.py`：

```python
from app.models.todo import QuadrantType, TodoItem


async def test_completing_todo_increments_pet_counter(client, test_user):
    todo = await TodoItem.create(
        title="写周报", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT
    )

    await client.post("/api/v1/todo/update", json={"id": todo.id, "is_completed": True})

    profile = await PetProfile.get(user_id=test_user.id)
    assert profile.stats.get("todo_completed") == 1


async def test_completing_twice_only_counts_once(client, test_user):
    todo = await TodoItem.create(
        title="写周报", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT
    )

    await client.post("/api/v1/todo/update", json={"id": todo.id, "is_completed": True})
    await client.post("/api/v1/todo/update", json={"id": todo.id, "is_completed": True})

    profile = await PetProfile.get(user_id=test_user.id)
    assert profile.stats.get("todo_completed") == 1, "已完成的再标记完成不应重复计数"


async def test_uncompleting_todo_does_not_decrement(client, test_user):
    todo = await TodoItem.create(
        title="写周报", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT
    )

    await client.post("/api/v1/todo/update", json={"id": todo.id, "is_completed": True})
    await client.post("/api/v1/todo/update", json={"id": todo.id, "is_completed": False})

    profile = await PetProfile.get(user_id=test_user.id)
    assert profile.stats.get("todo_completed") == 1, "计数只增不减，与云函数行为一致"


async def test_updating_title_does_not_increment(client, test_user):
    todo = await TodoItem.create(
        title="写周报", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT
    )

    await client.post("/api/v1/todo/update", json={"id": todo.id, "title": "改个标题"})

    assert await PetProfile.filter(user_id=test_user.id).count() == 0, "非完成动作不该建猫"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_pet.py -v`
Expected: FAIL，最后一条以外的三条断言失败（`PetProfile.DoesNotExist`）

- [ ] **Step 3: 实现 increment**

`app/controllers/pet.py` 顶部 import 追加 `from tortoise.transactions import in_transaction`，`PetController` 内追加：

```python
    async def increment(self, user_id: int, field: str, delta: int = 1) -> None:
        """累加某个计数维度。只增不减。

        stats 是 JSON 字段，没法用 F() 原子自增，所以整行加锁读-改-写；
        不加锁的话，同时完成两个任务会丢计数。
        """
        if field not in STAT_FIELDS:
            raise ValueError(f"未知的计数维度: {field}")

        async with in_transaction():
            profile = await PetProfile.filter(user_id=user_id).select_for_update().first()
            if profile is None:
                profile = await self.ensure_profile(user_id)
                profile = await PetProfile.filter(id=profile.id).select_for_update().first()

            stats = dict(profile.stats or {})
            stats[field] = int(stats.get(field, 0) or 0) + delta
            profile.stats = stats
            await profile.save(update_fields=["stats", "updated_at"])
```

- [ ] **Step 4: 在完成待办时调用**

`app/controllers/todo.py` 的 `update_todo`，把现有的完成判断分支改成记录一个标志，保存后再累加：

```python
        # 如果设置为已完成，并且之前未完成，则设置完成时间
        just_completed = bool(obj_in.is_completed) and not todo.is_completed
        if just_completed:
            update_data["completed_at"] = datetime.now()
        # 如果设置为未完成，则清除完成时间
        elif obj_in.is_completed is False:
            update_data["completed_at"] = None

        await todo.update_from_dict(update_data).save()

        # 养成猫计数：只在「由未完成变为已完成」时 +1，取消完成不回滚（与小程序云函数行为一致）
        if just_completed:
            await pet_controller.increment(user_id, "todo_completed")

        return todo
```

文件顶部 import 追加 `from app.controllers.pet import pet_controller`。

> **检查循环导入**：`app/controllers/pet.py` 只 import `app.models.pet`，不 import `todo`，所以不会成环。改完跑一次 `python -c "import app"` 确认。

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_pet.py tests/test_todo_list_extension.py tests/test_todo_statistics.py -v`
Expected: PASS，且待办相关的原有用例全绿

- [ ] **Step 6: 提交**

```bash
git add app/controllers/pet.py app/controllers/todo.py tests/test_pet.py
git commit -m "feat(pet): 完成待办时累加养成猫计数"
```

---

### Task 15: 云函数与 controller 的行为差异校对

**Files:**
- Create: `docs/superpowers/notes/2026-08-26-cloudfn-parity.md`
- Modify: 校对中发现问题的 controller / route 文件
- Test: 针对每处差异补的回归测试

**Interfaces:**
- Produces: 一份差异清单文档 + 修复；后续阶段二切换 `services/*.js` 时以这份清单为准

**这是本阶段最大的隐藏工作量**（spec §7.3、§13）。路由名对上了不代表行为等价。**不要靠假设，逐条读代码核对。**

- [ ] **Step 1: 建立校对清单文档**

新建 `docs/superpowers/notes/2026-08-26-cloudfn-parity.md`，先把待校对项列成表格（结论列先留空，逐项填）：

```markdown
# 云函数 vs FastAPI controller 行为差异校对

对每一项：读云函数实现 → 读 controller 实现 → 判断是否等价 → 不等价则记录差异与处理方式（改后端 / 改小程序 / 接受差异）。

| # | 模块 | 校对项 | 云函数行为 | 后端行为 | 结论 |
|---|---|---|---|---|---|
| 1 | todo | 分页参数与上限 | `page`/`pageSize`，pageSize 上限 200，默认 20 | | |
| 2 | todo | 排序白名单 | `due_date`/`quadrant_type`/`created_at`/`completed_at` | | |
| 3 | todo | 默认排序方向 | `created_at`/`completed_at` 默认 desc，其余默认 asc | | |
| 4 | todo | `inbox_only` 语义 | `project_id` 字段不存在 | | |
| 5 | todo | `habit_only` 筛选 | `habit_id` 字段存在 | | |
| 6 | todo | `unscheduled_only` | 排除所有已有时间块的任务，且限定未完成 | | |
| 7 | todo | 日期范围筛选字段 | `due_date` 与 `completed_at` 是两组独立参数 | | |
| 8 | habit | 惰性生成时机 | list 时补生成今天该生成的打卡待办 | | |
| 9 | habit | weekly_count 未达标时清理 | 删除本周未完成的打卡待办 | | |
| 10 | habit | streak 缓存 | 云函数把 streak 缓存在习惯文档上（`streak_date`） | | |
| 11 | goal | 详情返回的关联数据 | 关联任务 + 关联习惯 | | |
| 12 | project | 删除项目时任务如何处理 | | | |
| 13 | review | 周期聚合口径 | `dataSummary` 的统计范围与字段 | | |
| 14 | review | 草稿/完成状态流转 | | | |
| 15 | dashboard | today 返回的字段集合 | | | |
| 16 | 全局 | 可空关联字段语义 | 不写字段 + `_.exists(false)` 查询 | 关系库 `NULL` | |
```

- [ ] **Step 2: 逐项校对并填写结论**

对每一行，打开两侧源码对照：

- 云函数：`weapp/cloudfunctions/<模块>/index.js`
- 后端：`app/controllers/<模块>.py` + `app/api/v1/<模块>/route.py`

**第 1-7 项**重点看 `weapp/cloudfunctions/todo/index.js:47-100`（`list` 函数）与 `app/controllers/todo.py` 的 `get_todos_by_user`。
**第 8-10 项**看 `weapp/cloudfunctions/habit/index.js` 与 `app/controllers/habit.py:99-172`。
**第 16 项**是横切的：云函数用「字段不存在」表示空值，关系库里是 `NULL`，要确认所有 `*_only` 筛选的等价性。

- [ ] **Step 3: 为每处发现的差异写回归测试**

差异分三类处理，在文档「结论」列写明选了哪类：

- **改后端**（后端行为不对）→ 在对应的 `tests/test_<模块>.py` 里补一条测试复现差异，再改 controller 让它通过
- **改小程序**（后端行为更合理）→ 记进文档，**阶段二的 `services/*.js` 改造要照此调整**，本阶段不动代码
- **接受差异**（无实际影响）→ 写明为什么无影响

每写一条测试，先跑一次确认它**失败**，再改实现。

- [ ] **Step 4: 跑全量测试**

Run: `python -m pytest tests/ -v`
Expected: 全部通过

- [ ] **Step 5: 跑格式与 lint 检查**

Run: `make check`
Expected: black 与 isort 均无差异，ruff 无告警。有问题先跑 `make format` 再重跑 `make check`。

- [ ] **Step 6: 提交**

```bash
git add docs/superpowers/notes/2026-08-26-cloudfn-parity.md app/ tests/
git commit -m "fix: 校对云函数与后端 controller 行为差异并补齐回归测试"
```

---

## 阶段验收

全部 15 个 Task 完成后，逐条确认：

- [ ] `python -m pytest tests/ -v` 全绿
- [ ] `make check` 无告警
- [ ] `migrations/` 下有 `add_user_openid` 与 `add_pet_tables` 两个迁移文件，且内容只做新增
- [ ] 启动 `python run.py`，访问 `http://localhost:9999/docs`，确认这些新接口都在：
      `POST /base/wx_login`、`GET /habit/bootstrap`、`GET /habit/summary`、`GET /goal/bootstrap`、
      `GET /project/bootstrap`、`GET /todo/stats-bootstrap`、`GET /pet/bootstrap`、`POST /pet/update`
- [ ] 后台「API 管理」页面能看到新接口（`refresh_api()` 已自动同步）
- [ ] 后台「角色管理」里存在「小程序用户」角色，且已勾选待办事项相关 API、未勾选 RBAC 管理类 API
- [ ] `docs/superpowers/notes/2026-08-26-cloudfn-parity.md` 的每一行都有结论，没有留空

达成后，阶段二（小程序切换）可以开工。
