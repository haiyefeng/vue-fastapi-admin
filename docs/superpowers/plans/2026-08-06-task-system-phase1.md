# 一期：任务体系升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 `docs/superpowers/specs/2026-08-06-task-system-phase1-design.md` 描述的一期任务体系：激活 Category/Project、新增 SubTask、扩展 TodoItem，并交付任务列表页（收件箱 + 项目导航 + 任务详情弹窗）。

**Architecture:** 后端沿用 `app/api/v1/todos` 现有的 `/list /create /get /update /delete` 扁平路由风格 + `CRUDBase` 继承模式，新增 `category`/`project`/`subtask` 三个资源模块并扩展 `todos` 的过滤/排序能力；前端新增 `web/src/views/todo/TaskList/` 页面（`index.vue` 页面壳 + `ProjectNav.vue` 项目导航 + `NewProjectModal.vue` 新建项目弹窗 + `TaskDetailModal.vue` 任务详情弹窗），由新的 Menu 记录驱动路由。先后端（含 pytest 单测）后前端。

**Tech Stack:** FastAPI + Tortoise ORM（后端），Vue 3 `<script setup>` + Naive UI（前端），pytest + pytest-asyncio + httpx（后端测试，本仓库首次引入，Task 1 负责搭建）。

## Global Constraints

- 路由风格：`/list` `/create` `/get`（如需要） `/update` `/delete` + query 参数，不做嵌套 REST，路由文件放在 `app/api/v1/<resource>/route.py` + `__init__.py`。
- 所有新路由挂 `dependencies=[DependPermission]`；处理函数内部用 `Depends(AuthControl.is_authed)` 取当前用户，所有查询按 `user_id` 过滤，不做细粒度 RBAC（沿用 `todos` 模块现状）。
- 象限配色（前端展示用）：`urgent_important` = `#f5222d`，`urgent_not_important` = `#faad14`，`important_not_urgent` = `#1890ff`，`not_urgent_not_important` = `#909399`。
- 不做：Category 独立管理页/CRUD 入口、子任务拖拽重排、mockup 中属于三期的"关联计划"字段。
- 前端所有接口调用统一加进 `web/src/api/index.js` 的具名方法对象，组件内不写裸 `axios`/`request` 调用。
- 后端目前没有任何测试基础设施（`make test` 配置了 pytest 但仓库里零测试文件），Task 1 负责补齐最小可用的 pytest + Tortoise 内存库 + httpx 测试客户端；本计划里所有后端任务都遵循"写测试→跑测试确认现象→写实现→跑测试确认通过→提交"的顺序。前端本仓库未配置测试运行器（`pnpm lint` 是唯一自动化检查），前端任务改为"实现→手动在浏览器里验证→提交"。

---

## Task 1: 后端测试基础设施

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Produces：pytest fixture `db`（初始化内存 SQLite + 建表，函数级作用域）、`test_user`（依赖 `db`，创建一个 `is_superuser=True` 的测试用户，绕开 `PermissionControl` 的角色校验）、`client`（依赖 `test_user`，返回带 `token: dev` 请求头的 `httpx.AsyncClient`，通过 `ASGITransport` 直接调用 FastAPI app，不走真实网络也不触发 `lifespan`/`init_data()`，因此不需要连接项目当前配置的 MySQL）。后续所有任务的测试文件都直接用这三个 fixture 名字，不用重新声明。

- [ ] **Step 1: 加测试依赖和 pytest 配置**

在 `pyproject.toml` 的 `dependencies` 列表末尾（`"uvloop==0.21.0 ; sys_platform != 'win32'",` 之后）新增：

```toml
    "pytest==8.3.4",
    "pytest-asyncio==0.25.2",
```

并在文件末尾（`[tool.aerich]` 之后）新增：

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

（`asyncio_mode = "auto"` 让 `async def test_x()` 函数不用逐个加 `@pytest.mark.asyncio` 装饰器。）

- [ ] **Step 2: 安装依赖**

Run: `uv venv && source .venv/bin/activate && uv sync`

Expected: 虚拟环境创建成功，`pytest`/`pytest-asyncio` 安装完成，无报错。若已有 `.venv`，直接 `source .venv/bin/activate && uv sync` 即可。

- [ ] **Step 3: 写 conftest.py**

```python
# tests/conftest.py
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app import app as fastapi_app
from app.models.admin import User

TEST_DB_URL = "sqlite://:memory:"


@pytest_asyncio.fixture
async def db():
    """每个测试用例独立的内存 SQLite 库，不影响本地开发用的真实数据库配置"""
    await Tortoise.init(db_url=TEST_DB_URL, modules={"models": ["app.models"]})
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
```

- [ ] **Step 4: 写冒烟测试**

```python
# tests/test_smoke.py
async def test_todo_list_endpoint_reachable(client):
    response = await client.get("/api/v1/todo/list", params={"page": 1, "page_size": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["data"] == []
```

- [ ] **Step 5: 跑测试确认基础设施可用**

Run: `pytest tests/test_smoke.py -vv`
Expected: `1 passed`。如果失败，先排查是不是 `.venv` 没激活、依赖没装全，或者 `ASGITransport`/`httpx` 版本不匹配（本仓库锁定的 `httpx==0.28.1` 已经支持 `ASGITransport`）。

- [ ] **Step 6: 提交**

```bash
git add pyproject.toml tests/conftest.py tests/test_smoke.py
git commit -m "test: add minimal pytest + httpx test harness"
```

---

## Task 2: 数据模型变更（SubTask 新表 + TodoItem 扩展字段）

**Files:**
- Modify: `app/models/todo.py`
- Modify: `app/models/__init__.py`

**Interfaces:**
- Produces：`app.models.todo.SubTask`（字段：`todo_item`(FK→TodoItem，级联删除)、`title`、`is_completed`、`order`）；`TodoItem.project`（FK→Project，可空，`on_delete=SET_NULL`，`related_name="tasks"`，对应 db 字段 `project_id`）；`TodoItem.reminder_at`（可空 datetime）。这三者是 Task 3/4/5 的直接依赖。

- [ ] **Step 1: 修改 `app/models/todo.py`**

在 `TodoItem` 类里，`notes` 字段后面新增两行：

```python
    notes = fields.TextField(null=True, description="备注信息")
    project = fields.ForeignKeyField(
        "models.Project", related_name="tasks", null=True, on_delete=fields.SET_NULL, description="所属项目，为空则属于收件箱"
    )
    reminder_at = fields.DatetimeField(null=True, description="提醒时间，仅存储与展示，不做推送")
```

在文件末尾（`Project` 类之后）新增：

```python
class SubTask(BaseModel, TimestampMixin):
    """子任务模型"""

    todo_item = fields.ForeignKeyField(
        "models.TodoItem", related_name="subtasks", on_delete=fields.CASCADE, description="所属待办事项"
    )
    title = fields.CharField(max_length=200, description="子任务标题")
    is_completed = fields.BooleanField(default=False, description="是否已完成")
    order = fields.IntField(default=0, description="显示顺序，创建时按序递增赋值")

    class Meta:
        table = "sub_task"

    def __str__(self):
        return self.title
```

- [ ] **Step 2: 修改 `app/models/__init__.py`**

```python
# 新增model需要在这里导入
from .admin import *
from .todo import Category, Project, QuadrantType, SubTask, TodoItem
```

- [ ] **Step 3: 跑一次冒烟测试确认模型改动没有语法/引用错误**

Run: `pytest tests/test_smoke.py -vv`
Expected: `1 passed`（这一步顺带验证了 `Tortoise.generate_schemas()` 能正确建出新表结构，因为 fixture `db` 每次都会重新 `generate_schemas`）。

- [ ] **Step 4: 生成并应用 aerich 迁移**

本仓库 `migrations/` 目录被 gitignore（每个开发者本地各自生成），且这是全新 checkout，还没有任何历史迁移。`app/core/init_app.py::init_db()` 在应用启动时会自动跑 `aerich init_db`/`migrate`/`upgrade`，所以最简单的方式是直接启动一次应用：

Run: `python run.py`（等到控制台打出启动完成的日志后 Ctrl+C 停掉）

Expected: 无报错退出；若报连接数据库失败，说明 `app/settings/config.py` 里当前生效的 MySQL 连接配置（`DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME` 环境变量）在本机不可达——这是本机环境前置问题，需要先配好本地可访问的数据库（或按 CLAUDE.md 描述改回 SQLite 配置）再继续，不要绕过这一步。

- [ ] **Step 5: 提交**

```bash
git add app/models/todo.py app/models/__init__.py
git commit -m "feat: add SubTask model and TodoItem.project/reminder_at fields"
```

（`migrations/` 已被 gitignore，不需要提交生成的迁移文件。）

---

## Task 3: Category + Project 资源

**Files:**
- Create: `app/schemas/category.py`
- Create: `app/schemas/project.py`
- Create: `app/controllers/category.py`
- Create: `app/controllers/project.py`
- Create: `app/api/v1/category/__init__.py`
- Create: `app/api/v1/category/route.py`
- Create: `app/api/v1/project/__init__.py`
- Create: `app/api/v1/project/route.py`
- Modify: `app/api/v1/__init__.py`
- Create: `tests/test_category_and_project.py`

**Interfaces:**
- Consumes：Task 2 的 `Category`/`Project` 模型（已有模型，本任务首次激活）、`TodoItem.project_id`。
- Produces：`app.controllers.category.category_controller`（方法 `get_categories_for_user(user_id) -> List[Category]`、`get_or_create(user_id, name) -> Category`）；`app.controllers.project.project_controller`（方法 `create_project`、`update_project`、`delete_project`、`get_projects_for_user`、`to_out_dict`）。Task 5（TaskDetailModal 项目下拉）、Task 8（ProjectNav）在前端会调用 `GET /api/v1/project/list`、`GET /api/v1/category/list`。

- [ ] **Step 1: 写测试（先写，此时对应路由还不存在，预期会 404/连接失败）**

```python
# tests/test_category_and_project.py
from app.models.todo import Category, Project, QuadrantType, TodoItem


async def test_project_create_with_new_category_name(client, test_user):
    resp = await client.post(
        "/api/v1/project/create",
        json={"name": "Q4 营销活动", "type": "project", "category_name": "工作"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["name"] == "Q4 营销活动"
    assert body["category_name"] == "工作"
    assert await Category.filter(name="工作", user_id=test_user.id).count() == 1


async def test_project_create_reuses_existing_category(client, test_user):
    await client.post("/api/v1/project/create", json={"name": "官网改版", "category_name": "工作"})
    await client.post("/api/v1/project/create", json={"name": "Q4 营销活动", "category_name": "工作"})

    assert await Category.filter(name="工作", user_id=test_user.id).count() == 1


async def test_category_list_returns_created_categories(client):
    await client.post("/api/v1/project/create", json={"name": "React 进阶", "category_name": "学习"})

    resp = await client.get("/api/v1/category/list")
    names = [c["name"] for c in resp.json()["data"]]
    assert "学习" in names


async def test_delete_project_moves_tasks_to_inbox_instead_of_deleting(client, test_user):
    create_resp = await client.post("/api/v1/project/create", json={"name": "临时项目"})
    project_id = create_resp.json()["data"]["id"]

    todo = await TodoItem.create(
        title="挂在临时项目下的任务",
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        user_id=test_user.id,
        project_id=project_id,
    )

    resp = await client.delete("/api/v1/project/delete", params={"project_id": project_id})
    assert resp.status_code == 200
    assert await Project.filter(id=project_id).count() == 0

    await todo.refresh_from_db()
    assert todo.project_id is None


async def test_project_update_can_clear_category(client):
    create_resp = await client.post("/api/v1/project/create", json={"name": "本周购物清单", "category_name": "清单"})
    project_id = create_resp.json()["data"]["id"]

    resp = await client.post("/api/v1/project/update", json={"id": project_id, "category_id": None})
    assert resp.status_code == 200
    assert resp.json()["data"]["category_name"] is None


async def test_delete_nonexistent_project_returns_404(client):
    resp = await client.delete("/api/v1/project/delete", params={"project_id": 99999})
    assert resp.status_code == 404
```

- [ ] **Step 2: 跑测试确认现象**

Run: `pytest tests/test_category_and_project.py -vv`
Expected: 全部失败（`404 Not Found`，因为 `/api/v1/project/*`、`/api/v1/category/*` 还没注册）。

- [ ] **Step 3: 写 `app/schemas/category.py`**

```python
from pydantic import BaseModel

from app.models.todo import CategoryType


class CategoryOut(BaseModel):
    id: int
    name: str
    icon: str | None = None
    type: CategoryType
    display_order: int
    is_archived: bool

    class Config:
        from_attributes = True
```

- [ ] **Step 4: 写 `app/schemas/project.py`**

```python
from typing import Optional

from pydantic import BaseModel, Field

from app.models.todo import ProjectType


class ProjectCreate(BaseModel):
    name: str = Field(..., description="项目/清单名称")
    type: ProjectType = Field(ProjectType.PROJECT, description="类型（项目或清单）")
    category_id: Optional[int] = Field(None, description="已有分类ID")
    category_name: Optional[str] = Field(None, description="新分类名称，与 category_id 二选一")
    color_hex: Optional[str] = Field(None, description="颜色代码，如 #1890FF")


class ProjectUpdate(BaseModel):
    id: int = Field(..., description="项目ID")
    name: Optional[str] = None
    type: Optional[ProjectType] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    color_hex: Optional[str] = None
    is_archived: Optional[bool] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    type: ProjectType
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    color_hex: Optional[str] = None
    is_archived: bool

    class Config:
        from_attributes = True
```

- [ ] **Step 5: 写 `app/controllers/category.py`**

```python
from typing import List

from tortoise.expressions import Q

from app.core.crud import CRUDBase
from app.models.todo import Category


class CategoryController(CRUDBase[Category, Category, Category]):
    def __init__(self):
        super().__init__(model=Category)

    async def get_categories_for_user(self, user_id: int) -> List[Category]:
        """当前用户可见的分类：自己创建的 + 系统预设（user 为空，本期暂无预置数据）"""
        return await Category.filter(Q(user_id=user_id) | Q(user_id__isnull=True)).order_by(
            "display_order", "name"
        )

    async def get_or_create(self, user_id: int, name: str) -> Category:
        category = await Category.filter(user_id=user_id, name=name).first()
        if category:
            return category
        return await Category.create(user_id=user_id, name=name)


category_controller = CategoryController()
```

- [ ] **Step 6: 写 `app/controllers/project.py`**

```python
from typing import List, Optional

from app.controllers.category import category_controller
from app.core.crud import CRUDBase
from app.models.todo import Project, TodoItem
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectController(CRUDBase[Project, ProjectCreate, ProjectUpdate]):
    def __init__(self):
        super().__init__(model=Project)

    async def get_projects_for_user(self, user_id: int) -> List[Project]:
        return await Project.filter(user_id=user_id).order_by("name")

    async def create_project(self, obj_in: ProjectCreate, user_id: int) -> Project:
        category_id = await self._resolve_category(user_id, obj_in.category_id, obj_in.category_name)
        return await Project.create(
            user_id=user_id,
            name=obj_in.name,
            type=obj_in.type,
            category_id=category_id,
            color_hex=obj_in.color_hex,
        )

    async def update_project(self, project_id: int, obj_in: ProjectUpdate, user_id: int) -> Optional[Project]:
        project = await Project.filter(id=project_id, user_id=user_id).first()
        if not project:
            return None

        update_data = obj_in.model_dump(exclude_unset=True, exclude={"id", "category_id", "category_name"})
        if "category_id" in obj_in.model_fields_set or "category_name" in obj_in.model_fields_set:
            update_data["category_id"] = await self._resolve_category(
                user_id, obj_in.category_id, obj_in.category_name
            )

        await project.update_from_dict(update_data).save()
        return project

    async def delete_project(self, project_id: int, user_id: int) -> bool:
        """删除项目不级联删任务，任务的 project_id 显式置空退回收件箱"""
        project = await Project.filter(id=project_id, user_id=user_id).first()
        if not project:
            return False
        await TodoItem.filter(project_id=project_id).update(project_id=None)
        await project.delete()
        return True

    async def to_out_dict(self, project: Project) -> dict:
        data = await project.to_dict()
        category_name = None
        if project.category_id:
            category = await project.category
            category_name = category.name if category else None
        data["category_name"] = category_name
        return data

    async def _resolve_category(
        self, user_id: int, category_id: Optional[int], category_name: Optional[str]
    ) -> Optional[int]:
        if category_id is not None:
            return category_id
        if category_name:
            category = await category_controller.get_or_create(user_id, category_name)
            return category.id
        return None


project_controller = ProjectController()
```

- [ ] **Step 7: 写 `app/api/v1/category/route.py` 和 `__init__.py`**

```python
# app/api/v1/category/route.py
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
```

```python
# app/api/v1/category/__init__.py
from fastapi import APIRouter

from .route import router

category_router = APIRouter()
category_router.include_router(router, tags=["分类"])

__all__ = ["category_router"]
```

- [ ] **Step 8: 写 `app/api/v1/project/route.py` 和 `__init__.py`**

```python
# app/api/v1/project/route.py
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.controllers.project import project_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.schemas.base import Success
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="获取当前用户的项目/清单列表")
async def list_projects(current_user: User = Depends(AuthControl.is_authed)):
    projects = await project_controller.get_projects_for_user(current_user.id)
    result = [ProjectOut(**(await project_controller.to_out_dict(p))).model_dump() for p in projects]
    return Success(data=result)


@router.post("/create", summary="创建项目/清单")
async def create_project(project_in: ProjectCreate, current_user: User = Depends(AuthControl.is_authed)):
    project = await project_controller.create_project(project_in, current_user.id)
    data = await project_controller.to_out_dict(project)
    return Success(data=ProjectOut(**data).model_dump())


@router.post("/update", summary="更新项目/清单")
async def update_project(project_in: ProjectUpdate, current_user: User = Depends(AuthControl.is_authed)):
    project = await project_controller.update_project(project_in.id, project_in, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    data = await project_controller.to_out_dict(project)
    return Success(data=ProjectOut(**data).model_dump())


@router.delete("/delete", summary="删除项目/清单")
async def delete_project(
    project_id: int = Query(..., description="项目ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    success = await project_controller.delete_project(project_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="项目不存在")
    return Success(msg="删除成功")
```

```python
# app/api/v1/project/__init__.py
from fastapi import APIRouter

from .route import router

project_router = APIRouter()
project_router.include_router(router, tags=["项目"])

__all__ = ["project_router"]
```

- [ ] **Step 9: 挂载到 `app/api/v1/__init__.py`**

```python
from fastapi import APIRouter

from app.core.dependency import DependPermission

from .apis import apis_router
from .auditlog import auditlog_router
from .base import base_router
from .category import category_router
from .depts import depts_router
from .menus import menus_router
from .project import project_router
from .roles import roles_router
from .todos import todos_router
from .users import users_router

v1_router = APIRouter()

v1_router.include_router(base_router, prefix="/base")
v1_router.include_router(users_router, prefix="/user", dependencies=[DependPermission])
v1_router.include_router(roles_router, prefix="/role", dependencies=[DependPermission])
v1_router.include_router(menus_router, prefix="/menu", dependencies=[DependPermission])
v1_router.include_router(apis_router, prefix="/api", dependencies=[DependPermission])
v1_router.include_router(depts_router, prefix="/dept", dependencies=[DependPermission])
v1_router.include_router(auditlog_router, prefix="/auditlog", dependencies=[DependPermission])
v1_router.include_router(todos_router, prefix="/todo", dependencies=[DependPermission])
v1_router.include_router(category_router, prefix="/category", dependencies=[DependPermission])
v1_router.include_router(project_router, prefix="/project", dependencies=[DependPermission])
```

- [ ] **Step 10: 跑测试确认通过**

Run: `pytest tests/test_category_and_project.py -vv`
Expected: `6 passed`

- [ ] **Step 11: 提交**

```bash
git add app/schemas/category.py app/schemas/project.py app/controllers/category.py \
        app/controllers/project.py app/api/v1/category app/api/v1/project \
        app/api/v1/__init__.py tests/test_category_and_project.py
git commit -m "feat: activate Category/Project resources"
```

---

## Task 4: SubTask 资源

**Files:**
- Create: `app/schemas/subtask.py`
- Create: `app/controllers/subtask.py`
- Create: `app/api/v1/subtask/__init__.py`
- Create: `app/api/v1/subtask/route.py`
- Modify: `app/api/v1/__init__.py`
- Create: `tests/test_subtask.py`

**Interfaces:**
- Consumes：Task 2 的 `SubTask` 模型。
- Produces：`app.controllers.subtask.subtask_controller`，方法 `create_subtask(obj_in, user_id)`、`list_by_todo(todo_item_id, user_id)`、`update_subtask(id, obj_in, user_id)`、`delete_subtask(id, user_id)`、`get_counts_by_todo_ids(todo_ids: List[int]) -> Dict[int, Tuple[int, int]]`（返回 `{todo_id: (total, completed)}`）。Task 5 直接调用 `get_counts_by_todo_ids` 给 `/todo/list` 拼子任务计数。

- [ ] **Step 1: 写测试**

```python
# tests/test_subtask.py
from app.models.todo import QuadrantType, SubTask, TodoItem


async def _create_todo(user_id):
    return await TodoItem.create(
        title="完成项目报告初稿",
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
        user_id=user_id,
    )


async def test_create_and_list_subtasks_in_order(client, test_user):
    todo = await _create_todo(test_user.id)

    resp1 = await client.post("/api/v1/subtask/create", json={"todo_item_id": todo.id, "title": "收集数据"})
    assert resp1.status_code == 200
    assert resp1.json()["data"]["order"] == 0

    resp2 = await client.post("/api/v1/subtask/create", json={"todo_item_id": todo.id, "title": "撰写第一部分"})
    assert resp2.json()["data"]["order"] == 1

    list_resp = await client.get("/api/v1/subtask/list", params={"todo_item_id": todo.id})
    titles = [s["title"] for s in list_resp.json()["data"]]
    assert titles == ["收集数据", "撰写第一部分"]


async def test_update_subtask_completion(client, test_user):
    todo = await _create_todo(test_user.id)
    subtask = await SubTask.create(todo_item_id=todo.id, title="图表制作", order=0)

    resp = await client.post("/api/v1/subtask/update", json={"id": subtask.id, "is_completed": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["is_completed"] is True


async def test_delete_subtask(client, test_user):
    todo = await _create_todo(test_user.id)
    subtask = await SubTask.create(todo_item_id=todo.id, title="待删除", order=0)

    resp = await client.delete("/api/v1/subtask/delete", params={"subtask_id": subtask.id})
    assert resp.status_code == 200
    assert await SubTask.filter(id=subtask.id).count() == 0


async def test_create_subtask_for_missing_todo_returns_404(client):
    resp = await client.post("/api/v1/subtask/create", json={"todo_item_id": 99999, "title": "x"})
    assert resp.status_code == 404


async def test_deleting_todo_cascades_to_subtasks(client, test_user):
    todo = await _create_todo(test_user.id)
    await SubTask.create(todo_item_id=todo.id, title="子任务", order=0)

    resp = await client.delete("/api/v1/todo/delete", params={"todo_id": todo.id})
    assert resp.status_code == 200
    assert await SubTask.filter(todo_item_id=todo.id).count() == 0
```

- [ ] **Step 2: 跑测试确认现象**

Run: `pytest tests/test_subtask.py -vv`
Expected: 前 4 个失败（`404`，路由不存在），最后一个 `test_deleting_todo_cascades_to_subtasks` 也失败（此时 `SubTask` 表虽已建但没人往里插入数据，`await SubTask.create(...)` 会因为路由缺失前置调用失败——实际上这条测试不依赖新路由，可能直接跑通；不管哪种情况，本步骤只是确认"改代码之前测试不是意外全绿"）。

- [ ] **Step 3: 写 `app/schemas/subtask.py`**

```python
from typing import Optional

from pydantic import BaseModel, Field


class SubTaskCreate(BaseModel):
    todo_item_id: int = Field(..., description="所属待办事项ID")
    title: str = Field(..., description="子任务标题")


class SubTaskUpdate(BaseModel):
    id: int = Field(..., description="子任务ID")
    title: Optional[str] = None
    is_completed: Optional[bool] = None


class SubTaskOut(BaseModel):
    id: int
    todo_item_id: int
    title: str
    is_completed: bool
    order: int

    class Config:
        from_attributes = True
```

- [ ] **Step 4: 写 `app/controllers/subtask.py`**

```python
from typing import Dict, List, Optional, Tuple

from tortoise.functions import Count

from app.core.crud import CRUDBase
from app.models.todo import SubTask, TodoItem
from app.schemas.subtask import SubTaskCreate, SubTaskUpdate


class SubTaskController(CRUDBase[SubTask, SubTaskCreate, SubTaskUpdate]):
    def __init__(self):
        super().__init__(model=SubTask)

    async def create_subtask(self, obj_in: SubTaskCreate, user_id: int) -> Optional[SubTask]:
        todo = await TodoItem.filter(id=obj_in.todo_item_id, user_id=user_id).first()
        if not todo:
            return None
        order = await SubTask.filter(todo_item_id=obj_in.todo_item_id).count()
        return await SubTask.create(todo_item_id=obj_in.todo_item_id, title=obj_in.title, order=order)

    async def list_by_todo(self, todo_item_id: int, user_id: int) -> Optional[List[SubTask]]:
        todo = await TodoItem.filter(id=todo_item_id, user_id=user_id).first()
        if not todo:
            return None
        return await SubTask.filter(todo_item_id=todo_item_id).order_by("order", "id")

    async def update_subtask(self, subtask_id: int, obj_in: SubTaskUpdate, user_id: int) -> Optional[SubTask]:
        subtask = await SubTask.filter(id=subtask_id).select_related("todo_item").first()
        if not subtask or subtask.todo_item.user_id != user_id:
            return None
        update_data = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        await subtask.update_from_dict(update_data).save()
        return subtask

    async def delete_subtask(self, subtask_id: int, user_id: int) -> bool:
        subtask = await SubTask.filter(id=subtask_id).select_related("todo_item").first()
        if not subtask or subtask.todo_item.user_id != user_id:
            return False
        await subtask.delete()
        return True

    async def get_counts_by_todo_ids(self, todo_ids: List[int]) -> Dict[int, Tuple[int, int]]:
        """一次聚合查询算出每个待办事项的子任务总数/已完成数，避免列表页 N+1"""
        if not todo_ids:
            return {}

        totals = (
            await SubTask.filter(todo_item_id__in=todo_ids)
            .annotate(cnt=Count("id"))
            .group_by("todo_item_id")
            .values("todo_item_id", "cnt")
        )
        completed = (
            await SubTask.filter(todo_item_id__in=todo_ids, is_completed=True)
            .annotate(cnt=Count("id"))
            .group_by("todo_item_id")
            .values("todo_item_id", "cnt")
        )
        total_map = {row["todo_item_id"]: row["cnt"] for row in totals}
        completed_map = {row["todo_item_id"]: row["cnt"] for row in completed}
        return {tid: (total_map.get(tid, 0), completed_map.get(tid, 0)) for tid in todo_ids}


subtask_controller = SubTaskController()
```

- [ ] **Step 5: 写 `app/api/v1/subtask/route.py` 和 `__init__.py`**

```python
# app/api/v1/subtask/route.py
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.controllers.subtask import subtask_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.schemas.base import Success
from app.schemas.subtask import SubTaskCreate, SubTaskOut, SubTaskUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="获取指定待办事项下的子任务列表")
async def list_subtasks(
    todo_item_id: int = Query(..., description="待办事项ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    subtasks = await subtask_controller.list_by_todo(todo_item_id, current_user.id)
    if subtasks is None:
        raise HTTPException(status_code=404, detail="待办事项不存在")
    result = [SubTaskOut(**(await s.to_dict())).model_dump() for s in subtasks]
    return Success(data=result)


@router.post("/create", summary="创建子任务")
async def create_subtask(subtask_in: SubTaskCreate, current_user: User = Depends(AuthControl.is_authed)):
    subtask = await subtask_controller.create_subtask(subtask_in, current_user.id)
    if not subtask:
        raise HTTPException(status_code=404, detail="待办事项不存在")
    return Success(data=SubTaskOut(**(await subtask.to_dict())).model_dump())


@router.post("/update", summary="更新子任务")
async def update_subtask(subtask_in: SubTaskUpdate, current_user: User = Depends(AuthControl.is_authed)):
    subtask = await subtask_controller.update_subtask(subtask_in.id, subtask_in, current_user.id)
    if not subtask:
        raise HTTPException(status_code=404, detail="子任务不存在")
    return Success(data=SubTaskOut(**(await subtask.to_dict())).model_dump())


@router.delete("/delete", summary="删除子任务")
async def delete_subtask(
    subtask_id: int = Query(..., description="子任务ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    success = await subtask_controller.delete_subtask(subtask_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="子任务不存在")
    return Success(msg="删除成功")
```

```python
# app/api/v1/subtask/__init__.py
from fastapi import APIRouter

from .route import router

subtask_router = APIRouter()
subtask_router.include_router(router, tags=["子任务"])

__all__ = ["subtask_router"]
```

- [ ] **Step 6: 挂载到 `app/api/v1/__init__.py`**

在已有的 import 块里加一行 `from .subtask import subtask_router`（按字母序放在 `.roles` 和 `.todos` 之间），并在 `v1_router.include_router(...)` 列表末尾加：

```python
v1_router.include_router(subtask_router, prefix="/subtask", dependencies=[DependPermission])
```

- [ ] **Step 7: 跑测试确认通过**

Run: `pytest tests/test_subtask.py -vv`
Expected: `5 passed`

- [ ] **Step 8: 提交**

```bash
git add app/schemas/subtask.py app/controllers/subtask.py app/api/v1/subtask \
        app/api/v1/__init__.py tests/test_subtask.py
git commit -m "feat: add SubTask CRUD resource"
```

---

## Task 5: `/todo/list` 扩展（项目过滤、多象限过滤、排序、子任务计数）

**Files:**
- Modify: `app/schemas/todo.py`
- Modify: `app/controllers/todo.py`
- Modify: `app/api/v1/todos/route.py`
- Create: `tests/test_todo_list_extension.py`

**Interfaces:**
- Consumes：Task 3 的 `TodoItem.project_id`（Task 2 已加字段）、Task 4 的 `subtask_controller.get_counts_by_todo_ids`。
- Produces：`TodoItemOut` 新增字段 `project_id`、`reminder_at`、`subtask_total`、`subtask_completed`。`GET /todo/list` 新增 query 参数：`project_id`、`inbox_only`（优先于 `project_id`）、`quadrant_type`（改为逗号分隔的多选字符串）、`sort_by`（`due_date`/`quadrant_type`/`created_at`）、`sort_order`（`asc`/`desc`，默认 `asc`）。前端 Task 7 的 API 封装、Task 10 的任务列表页直接消费这些参数名。

- [ ] **Step 1: 写测试**

```python
# tests/test_todo_list_extension.py
from datetime import datetime

from app.models.todo import Project, QuadrantType, TodoItem


async def test_create_defaults_to_inbox_when_no_project_given(client):
    resp = await client.post(
        "/api/v1/todo/create",
        json={"title": "浏览行业资讯", "quadrant_type": "not_urgent_not_important"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["project_id"] is None


async def test_list_filters_by_inbox_only(client, test_user):
    project = await Project.create(user_id=test_user.id, name="工作项目")
    await TodoItem.create(
        title="收件箱任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id
    )
    await TodoItem.create(
        title="项目任务",
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        user_id=test_user.id,
        project_id=project.id,
    )

    resp = await client.get("/api/v1/todo/list", params={"inbox_only": True})
    titles = [t["title"] for t in resp.json()["data"]]
    assert titles == ["收件箱任务"]


async def test_list_filters_by_project_id(client, test_user):
    project = await Project.create(user_id=test_user.id, name="工作项目")
    await TodoItem.create(
        title="收件箱任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id
    )
    await TodoItem.create(
        title="项目任务",
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        user_id=test_user.id,
        project_id=project.id,
    )

    resp = await client.get("/api/v1/todo/list", params={"project_id": project.id})
    titles = [t["title"] for t in resp.json()["data"]]
    assert titles == ["项目任务"]


async def test_list_filters_by_multiple_quadrants(client, test_user):
    await TodoItem.create(title="A", quadrant_type=QuadrantType.URGENT_IMPORTANT, user_id=test_user.id)
    await TodoItem.create(title="B", quadrant_type=QuadrantType.URGENT_NOT_IMPORTANT, user_id=test_user.id)
    await TodoItem.create(title="C", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id)

    resp = await client.get(
        "/api/v1/todo/list", params={"quadrant_type": "urgent_important,urgent_not_important"}
    )
    titles = {t["title"] for t in resp.json()["data"]}
    assert titles == {"A", "B"}


async def test_list_sort_by_due_date_ascending(client, test_user):
    await TodoItem.create(
        title="晚任务",
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        user_id=test_user.id,
        due_date=datetime(2026, 8, 20),
    )
    await TodoItem.create(
        title="早任务",
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        user_id=test_user.id,
        due_date=datetime(2026, 8, 10),
    )

    resp = await client.get("/api/v1/todo/list", params={"sort_by": "due_date", "sort_order": "asc"})
    titles = [t["title"] for t in resp.json()["data"]]
    assert titles == ["早任务", "晚任务"]


async def test_list_includes_subtask_counts(client, test_user):
    todo = await TodoItem.create(title="带子任务", quadrant_type=QuadrantType.URGENT_IMPORTANT, user_id=test_user.id)
    await client.post("/api/v1/subtask/create", json={"todo_item_id": todo.id, "title": "a"})
    sub2_resp = await client.post("/api/v1/subtask/create", json={"todo_item_id": todo.id, "title": "b"})
    await client.post("/api/v1/subtask/update", json={"id": sub2_resp.json()["data"]["id"], "is_completed": True})

    resp = await client.get("/api/v1/todo/list")
    item = next(t for t in resp.json()["data"] if t["title"] == "带子任务")
    assert item["subtask_total"] == 2
    assert item["subtask_completed"] == 1
```

- [ ] **Step 2: 跑测试确认现象**

Run: `pytest tests/test_todo_list_extension.py -vv`
Expected: 全部失败（`project_id`/`subtask_total` 字段还不存在于响应里，`inbox_only`/`sort_by` 等参数还没接上过滤逻辑）。

- [ ] **Step 3: 修改 `app/schemas/todo.py`**

```python
from datetime import date, datetime
from typing import Optional, Dict, List

from pydantic import BaseModel, Field

from app.models.todo import QuadrantType


class TodoItemBase(BaseModel):
    """待办事项基础模型"""

    title: str = Field(..., description="待办事项标题")
    quadrant_type: QuadrantType = Field(..., description="象限类型")
    due_date: Optional[datetime] = Field(None, description="截止时间")
    notes: Optional[str] = Field(None, description="备注信息")
    project_id: Optional[int] = Field(None, description="所属项目ID，为空则属于收件箱")
    reminder_at: Optional[datetime] = Field(None, description="提醒时间，仅存储与展示，不做推送")

    class Config:
        json_encoders = {date: lambda v: v.isoformat() if v else None}


class TodoItemCreate(TodoItemBase):
    """创建待办事项的请求体"""

    pass


class TodoItemUpdate(BaseModel):
    """更新待办事项的请求体"""

    id: int = Field(..., description="待办事项ID")
    title: Optional[str] = Field(None, description="待办事项标题")
    quadrant_type: Optional[QuadrantType] = Field(None, description="象限类型")
    due_date: Optional[datetime] = Field(None, description="截止时间")
    notes: Optional[str] = Field(None, description="备注信息")
    is_completed: Optional[bool] = Field(None, description="是否已完成")
    project_id: Optional[int] = Field(None, description="所属项目ID，传 null 可退回收件箱")
    reminder_at: Optional[datetime] = Field(None, description="提醒时间")


class TodoItemOut(TodoItemBase):
    """待办事项的响应体"""

    id: int
    is_completed: bool = Field(False, description="是否已完成")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    created_at: datetime
    updated_at: datetime
    subtask_total: int = Field(0, description="子任务总数")
    subtask_completed: int = Field(0, description="已完成子任务数")

    class Config:
        from_attributes = True


class TodoStatisticsByDate(BaseModel):
    """按日期统计的待办事项数量"""

    date: date
    urgent_important: int = Field(0, description="紧急且重要的待办事项数量")
    urgent_not_important: int = Field(0, description="紧急但不重要的待办事项数量")
    important_not_urgent: int = Field(0, description="重要但不紧急的待办事项数量")
    not_urgent_not_important: int = Field(0, description="不紧急也不重要的待办事项数量")
    total: int = Field(0, description="总待办事项数量")


class QuadrantStatistics(BaseModel):
    """按象限统计的待办事项数量"""

    urgent_important: int = Field(0, description="紧急且重要的待办事项数量")
    urgent_not_important: int = Field(0, description="紧急但不重要的待办事项数量")
    important_not_urgent: int = Field(0, description="重要但不紧急的待办事项数量")
    not_urgent_not_important: int = Field(0, description="不紧急也不重要的待办事项数量")
    total: int = Field(0, description="总待办事项数量")
```

- [ ] **Step 4: 修改 `app/controllers/todo.py` 的 `get_todos_by_user`**

用下面的版本整体替换现有的 `get_todos_by_user` 方法：

```python
    async def get_todos_by_user(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        quadrant_type: Optional[str] = None,
        is_completed: Optional[bool] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        project_id: Optional[int] = None,
        inbox_only: Optional[bool] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Tuple[int, List[TodoItem]]:
        """获取用户的待办事项列表"""
        query = Q(user_id=user_id)

        if quadrant_type:
            quadrants = [q.strip() for q in quadrant_type.split(",") if q.strip()]
            if quadrants:
                query &= Q(quadrant_type__in=quadrants)

        if is_completed is not None:
            query &= Q(is_completed=is_completed)

        if start_date:
            query &= Q(created_at__gte=datetime.combine(start_date, datetime.min.time()))

        if end_date:
            query &= Q(created_at__lte=datetime.combine(end_date, datetime.max.time()))

        if inbox_only:
            query &= Q(project_id__isnull=True)
        elif project_id is not None:
            query &= Q(project_id=project_id)

        if sort_by is None:
            order = ["-created_at"]
        else:
            field = sort_by if sort_by in ("due_date", "quadrant_type", "created_at") else "created_at"
            direction = "-" if sort_order == "desc" else ""
            order = [f"{direction}{field}"]

        return await self.list(page=page, page_size=page_size, search=query, order=order)
```

（方法签名和逻辑变了，但调用方不变——原有的 `quadrant_type: Optional[QuadrantType]` 参数类型改成了 `Optional[str]`，因为要接受逗号分隔的多选值。）

- [ ] **Step 5: 修改 `app/api/v1/todos/route.py`**

在文件顶部 import 区新增：

```python
from app.controllers.subtask import subtask_controller
```

用下面的版本整体替换 `list_todos`：

```python
@router.get("/list", summary="获取待办事项列表")
async def list_todos(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    quadrant_type: Optional[str] = Query(None, description="象限类型，多个用逗号分隔"),
    is_completed: Optional[bool] = Query(None, description="是否已完成"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    project_id: Optional[int] = Query(None, description="项目ID"),
    inbox_only: Optional[bool] = Query(None, description="是否只看收件箱（project_id 为空），优先于 project_id"),
    sort_by: Optional[str] = Query(None, description="排序字段: due_date/quadrant_type/created_at"),
    sort_order: Optional[str] = Query("asc", description="排序方向: asc/desc"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    获取当前用户的待办事项列表，支持按象限（可多选）、完成状态、项目/收件箱筛选，支持排序
    """
    total, todos = await todo_controller.get_todos_by_user(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        quadrant_type=quadrant_type,
        is_completed=is_completed,
        start_date=start_date,
        end_date=end_date,
        project_id=project_id,
        inbox_only=inbox_only,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    todo_ids = [todo.id for todo in todos]
    counts = await subtask_controller.get_counts_by_todo_ids(todo_ids)

    result = []
    for todo in todos:
        todo_dict = await todo.to_dict()
        total_sub, completed_sub = counts.get(todo.id, (0, 0))
        todo_out = TodoItemOut(**todo_dict, subtask_total=total_sub, subtask_completed=completed_sub)
        result.append(todo_out.model_dump())

    return SuccessExtra(data=result, total=total, page=page, page_size=page_size)
```

用下面的版本整体替换 `get_todo`：

```python
@router.get("/get", summary="获取指定ID的待办事项")
async def get_todo(
    todo_id: int = Query(..., description="待办事项ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    获取指定ID的待办事项
    """
    try:
        todo = await TodoItem.get(id=todo_id, user_id=current_user.id)
        todo_dict = await todo.to_dict()
        counts = await subtask_controller.get_counts_by_todo_ids([todo.id])
        total_sub, completed_sub = counts.get(todo.id, (0, 0))
        todo_out = TodoItemOut(**todo_dict, subtask_total=total_sub, subtask_completed=completed_sub)
        return Success(data=todo_out.model_dump())
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="待办事项不存在")
```

用下面的版本整体替换 `update_todo`：

```python
@router.post("/update", summary="更新指定ID的待办事项")
async def update_todo(
    todo_in: TodoItemUpdate,
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    更新指定ID的待办事项
    """
    todo = await todo_controller.update_todo(todo_in.id, todo_in, current_user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="待办事项不存在")

    todo_dict = await todo.to_dict()
    counts = await subtask_controller.get_counts_by_todo_ids([todo.id])
    total_sub, completed_sub = counts.get(todo.id, (0, 0))
    todo_out = TodoItemOut(**todo_dict, subtask_total=total_sub, subtask_completed=completed_sub)
    return Success(data=todo_out.model_dump())
```

（`create_todo` 不用改：`TodoItemOut` 的 `subtask_total`/`subtask_completed` 有默认值 0，新建任务本来就没有子任务。）

- [ ] **Step 6: 跑测试确认通过**

Run: `pytest tests/test_todo_list_extension.py -vv`
Expected: `6 passed`

Run: `pytest -vv` （跑全量，确认之前几个任务的测试没被这次改动破坏）
Expected: 全部 passed

- [ ] **Step 7: 提交**

```bash
git add app/schemas/todo.py app/controllers/todo.py app/api/v1/todos/route.py \
        tests/test_todo_list_extension.py
git commit -m "feat: extend todo list with project filter, multi-quadrant filter, sort, subtask counts"
```

---

## Task 6: "任务" 菜单记录

**Files:**
- Modify: `app/core/init_app.py`

**Interfaces:**
- Consumes：无（纯配置）。
- Produces：`Menu` 表里新增一条 `name="任务"`、`component="/todo/TaskList"`、`parent_id=<"待办事项"目录的id>` 的记录，供 Task 10 的 `TaskList/index.vue` 被路由到。

- [ ] **Step 1: 修改 `app/core/init_app.py`**

在 `init_menus()` 函数内，紧跟在现有的"待办事项菜单"代码块（`await Menu.bulk_create(todo_children_menu)` 那一行）之后，新增一段**不嵌套在 `if not menus:` 或 `if not todo_menu:` 判断里**的独立逻辑（和现有的 `todo_menu = await Menu.filter(...)` 一样是函数体顶层缩进，这样即使"待办事项"目录早就存在，这段代码每次启动也会自己检查、自愈式补上"任务"这条子菜单）：

```python
    # 一期任务体系升级：任务列表页菜单。独立于上面的判断，保证已经部署过的环境重启后也能自动补上
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        task_menu = await Menu.filter(name="任务", parent_id=todo_parent_menu.id).first()
        if not task_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="任务",
                path="tasks",
                order=0,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:task-outline",
                is_hidden=False,
                component="/todo/TaskList",
                keepalive=True,
            )
```

- [ ] **Step 2: 手动验证**

Run: `python run.py`

打开 `http://localhost:9999/docs` 确认应用正常启动无报错；用 `admin`/`123456` 登录前端（Task 10 完成前页面还是空的没关系，这一步只验证菜单记录本身），或者直接查库确认：

Run: `sqlite3 db.sqlite3 "select id,name,path,component,parent_id from menu where name='任务';"` （如果本地用的是 MySQL，换成对应的 MySQL 客户端命令，或者去"系统管理 → 菜单管理"页面里肉眼确认多了一条"任务"）

Expected: 能查到一条 `name=任务, component=/todo/TaskList` 的记录，`parent_id` 等于"待办事项"目录的 id。

- [ ] **Step 3: 提交**

```bash
git add app/core/init_app.py
git commit -m "feat: register 任务 menu entry under 待办事项"
```

---

## Task 7: 前端 API 客户端模块（project / category / subtask）

**Files:**
- Create: `web/src/api/category.js`
- Create: `web/src/api/project.js`
- Create: `web/src/api/subtask.js`
- Modify: `web/src/api/index.js`

**Interfaces:**
- Consumes：Task 3/4/5 的后端接口路径（`/category/list`、`/project/list|create|update|delete`、`/subtask/list|create|update|delete`）；`web/src/api/todo.js` 的 `getTodos`/`createTodo`/`updateTodo` 已经是透传 `params`/`data` 对象的通用签名，本任务不需要改它。
- Produces：`import api from '@/api'` 之后可直接调用 `api.getCategories()`、`api.getProjects()`、`api.createProject(data)`、`api.updateProject(id, data)`、`api.deleteProject(id)`、`api.getSubtasks(todoItemId)`、`api.createSubtask(data)`、`api.updateSubtask(id, data)`、`api.deleteSubtask(id)`。Task 8/9/10 的组件直接用这些方法名。

- [ ] **Step 1: 写 `web/src/api/category.js`**

```js
import { request } from '@/utils'

/**
 * 分类API接口（只读，分类只能在创建项目时顺带生成）
 */
export default {
  /**
   * 获取当前用户可用的分类列表
   * @returns {Promise}
   */
  getCategories: (params = {}) => request.get('/category/list', { params })
}
```

- [ ] **Step 2: 写 `web/src/api/project.js`**

```js
import { request } from '@/utils'

/**
 * 项目/清单API接口
 */
export default {
  /**
   * 获取当前用户的项目/清单列表
   * @returns {Promise}
   */
  getProjects: (params = {}) => request.get('/project/list', { params }),

  /**
   * 创建项目/清单
   * @param {Object} data
   * @param {String} data.name - 名称
   * @param {String} data.type - 类型，project 或 list
   * @param {Number} [data.category_id] - 已有分类ID
   * @param {String} [data.category_name] - 新分类名称，与 category_id 二选一
   * @param {String} [data.color_hex] - 颜色代码
   * @returns {Promise}
   */
  createProject: (data = {}) => request.post('/project/create', data),

  /**
   * 更新项目/清单
   * @param {Number} id
   * @param {Object} data
   * @returns {Promise}
   */
  updateProject: (id, data = {}) => request.post('/project/update', { ...data, id }),

  /**
   * 删除项目/清单（关联任务会保留，project_id 置空退回收件箱）
   * @param {Number} id
   * @returns {Promise}
   */
  deleteProject: (id) => request.delete('/project/delete', { params: { project_id: id } })
}
```

- [ ] **Step 3: 写 `web/src/api/subtask.js`**

```js
import { request } from '@/utils'

/**
 * 子任务API接口
 */
export default {
  /**
   * 获取指定待办事项下的子任务列表
   * @param {Number} todoItemId
   * @returns {Promise}
   */
  getSubtasks: (todoItemId) => request.get('/subtask/list', { params: { todo_item_id: todoItemId } }),

  /**
   * 创建子任务
   * @param {Object} data
   * @param {Number} data.todo_item_id
   * @param {String} data.title
   * @returns {Promise}
   */
  createSubtask: (data = {}) => request.post('/subtask/create', data),

  /**
   * 更新子任务（改标题或勾选状态）
   * @param {Number} id
   * @param {Object} data
   * @returns {Promise}
   */
  updateSubtask: (id, data = {}) => request.post('/subtask/update', { ...data, id }),

  /**
   * 删除子任务
   * @param {Number} id
   * @returns {Promise}
   */
  deleteSubtask: (id) => request.delete('/subtask/delete', { params: { subtask_id: id } })
}
```

- [ ] **Step 4: 修改 `web/src/api/index.js`**

```js
import { request } from '@/utils'
import todoApi from './todo'
import projectApi from './project'
import categoryApi from './category'
import subtaskApi from './subtask'

export default {
  login: (data) => request.post('/base/access_token', data, { noNeedToken: true }),
  getUserInfo: () => request.get('/base/userinfo'),
  getUserMenu: () => request.get('/base/usermenu'),
  getUserApi: () => request.get('/base/userapi'),
  // profile
  updatePassword: (data = {}) => request.post('/base/update_password', data),
  // users
  getUserList: (params = {}) => request.get('/user/list', { params }),
  getUserById: (params = {}) => request.get('/user/get', { params }),
  createUser: (data = {}) => request.post('/user/create', data),
  updateUser: (data = {}) => request.post('/user/update', data),
  deleteUser: (params = {}) => request.delete(`/user/delete`, { params }),
  resetPassword: (data = {}) => request.post(`/user/reset_password`, data),
  // role
  getRoleList: (params = {}) => request.get('/role/list', { params }),
  createRole: (data = {}) => request.post('/role/create', data),
  updateRole: (data = {}) => request.post('/role/update', data),
  deleteRole: (params = {}) => request.delete('/role/delete', { params }),
  updateRoleAuthorized: (data = {}) => request.post('/role/authorized', data),
  getRoleAuthorized: (params = {}) => request.get('/role/authorized', { params }),
  // menus
  getMenus: (params = {}) => request.get('/menu/list', { params }),
  createMenu: (data = {}) => request.post('/menu/create', data),
  updateMenu: (data = {}) => request.post('/menu/update', data),
  deleteMenu: (params = {}) => request.delete('/menu/delete', { params }),
  // apis
  getApis: (params = {}) => request.get('/api/list', { params }),
  createApi: (data = {}) => request.post('/api/create', data),
  updateApi: (data = {}) => request.post('/api/update', data),
  deleteApi: (params = {}) => request.delete('/api/delete', { params }),
  refreshApi: (data = {}) => request.post('/api/refresh', data),
  // depts
  getDepts: (params = {}) => request.get('/dept/list', { params }),
  createDept: (data = {}) => request.post('/dept/create', data),
  updateDept: (data = {}) => request.post('/dept/update', data),
  deleteDept: (params = {}) => request.delete('/dept/delete', { params }),
  // auditlog
  getAuditLogList: (params = {}) => request.get('/auditlog/list', { params }),
  // todo
  ...todoApi,
  // project / category / subtask（一期任务体系）
  ...projectApi,
  ...categoryApi,
  ...subtaskApi
}
```

- [ ] **Step 5: 手动验证**

Run: `cd web && pnpm i && pnpm dev`

在浏览器打开开发服务器地址，登录后打开控制台，执行 `await window.$vueApp` 不是必须的——直接跳过，因为还没有页面调用这些方法。改成跑一次 lint 确认没有语法错误即可：

Run: `cd web && pnpm lint`
Expected: 无新增报错（尤其是新建的三个文件）。

- [ ] **Step 6: 提交**

```bash
git add web/src/api/category.js web/src/api/project.js web/src/api/subtask.js web/src/api/index.js
git commit -m "feat(web): add project/category/subtask API client modules"
```

---

## Task 8: `ProjectNav.vue` + `NewProjectModal.vue`

**Files:**
- Create: `web/src/views/todo/TaskList/NewProjectModal.vue`
- Create: `web/src/views/todo/TaskList/ProjectNav.vue`

**Interfaces:**
- Consumes：Task 7 的 `api.getProjects()`、`api.getCategories()`、`api.createProject(data)`。
- Produces：`ProjectNav` 组件，emits `select`（payload `{ type: 'inbox' } | { type: 'project', id, name }`，挂载时默认触发一次 `{ type: 'inbox' }`）、`changed`（新建项目成功后触发，无 payload）；对外暴露 `defineExpose({ refresh })` 供父组件在别处改了项目数据后主动刷新。Task 10 的 `TaskList/index.vue` 直接引入并监听这两个事件。

- [ ] **Step 1: 写 `NewProjectModal.vue`**

```vue
<template>
  <n-modal :show="show" preset="card" title="新建项目/清单" style="width: 420px" @update:show="onUpdateShow">
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="80">
      <n-form-item label="名称" path="name">
        <n-input v-model:value="form.name" placeholder="请输入名称" />
      </n-form-item>
      <n-form-item label="类型" path="type">
        <n-radio-group v-model:value="form.type">
          <n-radio value="project">项目</n-radio>
          <n-radio value="list">清单</n-radio>
        </n-radio-group>
      </n-form-item>
      <n-form-item label="分类" path="category_id">
        <n-select
          v-model:value="form.category_id"
          :options="categoryOptions"
          placeholder="选择已有分类（可留空）"
          clearable
        />
      </n-form-item>
      <n-form-item label="新分类">
        <n-input v-model:value="form.new_category_name" placeholder="或输入新分类名称（留空则用上面的选择）" />
      </n-form-item>
      <n-form-item label="颜色">
        <n-color-picker v-model:value="form.color_hex" :show-alpha="false" />
      </n-form-item>
    </n-form>
    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5em">
        <n-button @click="onUpdateShow(false)">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="handleSubmit">创建</n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false }
})
const emit = defineEmits(['update:show', 'created'])

const message = useMessage()
const formRef = ref(null)
const submitting = ref(false)
const categories = ref([])

const defaultForm = () => ({
  name: '',
  type: 'project',
  category_id: null,
  new_category_name: '',
  color_hex: '#1890FF'
})
const form = ref(defaultForm())

const rules = {
  name: { required: true, message: '请输入名称', trigger: 'blur' }
}

const categoryOptions = computed(() => categories.value.map((c) => ({ label: c.name, value: c.id })))

const fetchCategories = async () => {
  const res = await api.getCategories()
  categories.value = res.data || []
}

const onUpdateShow = (value) => {
  emit('update:show', value)
}

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      form.value = defaultForm()
      fetchCategories()
    }
  }
)

const handleSubmit = async () => {
  await formRef.value?.validate()
  submitting.value = true
  try {
    const payload = {
      name: form.value.name,
      type: form.value.type,
      color_hex: form.value.color_hex
    }
    if (form.value.new_category_name.trim()) {
      payload.category_name = form.value.new_category_name.trim()
    } else if (form.value.category_id) {
      payload.category_id = form.value.category_id
    }
    const res = await api.createProject(payload)
    message.success('创建成功')
    emit('created', res.data)
    onUpdateShow(false)
  } finally {
    submitting.value = false
  }
}
</script>
```

- [ ] **Step 2: 写 `ProjectNav.vue`**

```vue
<template>
  <nav class="project-nav">
    <ul class="nav-list">
      <li>
        <a href="javascript:;" :class="{ active: isInboxActive }" @click="selectInbox">收件箱</a>
      </li>
    </ul>

    <template v-for="group in groupedProjects" :key="group.name">
      <div class="nav-group">{{ group.name }}</div>
      <ul class="nav-list">
        <li v-for="project in group.projects" :key="project.id">
          <a href="javascript:;" :class="{ active: isProjectActive(project.id) }" @click="selectProject(project)">
            {{ project.name }}
          </a>
        </li>
      </ul>
    </template>

    <n-collapse v-if="archivedProjects.length" class="archived-collapse">
      <n-collapse-item title="已归档" name="archived">
        <ul class="nav-list">
          <li v-for="project in archivedProjects" :key="project.id">
            <a href="javascript:;" :class="{ active: isProjectActive(project.id) }" @click="selectProject(project)">
              {{ project.name }}
            </a>
          </li>
        </ul>
      </n-collapse-item>
    </n-collapse>

    <ul class="nav-list create-entry">
      <li>
        <a href="javascript:;" @click="showCreateModal = true">+ 新建项目/清单</a>
      </li>
    </ul>

    <NewProjectModal v-model:show="showCreateModal" @created="handleCreated" />
  </nav>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/api'
import NewProjectModal from './NewProjectModal.vue'

const emit = defineEmits(['select', 'changed'])

const projects = ref([])
const activeSelection = ref({ type: 'inbox' })
const showCreateModal = ref(false)

const activeProjects = computed(() => projects.value.filter((p) => !p.is_archived))
const archivedProjects = computed(() => projects.value.filter((p) => p.is_archived))

const groupedProjects = computed(() => {
  const groups = new Map()
  for (const project of activeProjects.value) {
    const key = project.category_name || '未分组'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(project)
  }
  return Array.from(groups.entries()).map(([name, list]) => ({ name, projects: list }))
})

const isInboxActive = computed(() => activeSelection.value.type === 'inbox')
const isProjectActive = (id) => activeSelection.value.type === 'project' && activeSelection.value.id === id

const fetchProjects = async () => {
  const res = await api.getProjects()
  projects.value = res.data || []
}

const selectInbox = () => {
  activeSelection.value = { type: 'inbox' }
  emit('select', { type: 'inbox' })
}

const selectProject = (project) => {
  activeSelection.value = { type: 'project', id: project.id }
  emit('select', { type: 'project', id: project.id, name: project.name })
}

const handleCreated = async (project) => {
  await fetchProjects()
  emit('changed')
  selectProject(project)
}

defineExpose({ refresh: fetchProjects })

onMounted(async () => {
  await fetchProjects()
  selectInbox()
})
</script>

<style scoped>
.project-nav {
  width: 200px;
  flex-shrink: 0;
}
.nav-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.nav-list a {
  display: block;
  padding: 0.45em 1em;
  text-decoration: none;
  font-size: 0.92em;
  border-radius: 4px;
  color: inherit;
}
.nav-list a.active {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
  font-weight: 500;
}
.nav-group {
  font-size: 0.8em;
  font-weight: 600;
  padding: 0.8em 1em 0.3em;
  opacity: 0.7;
}
.create-entry {
  margin-top: 0.6em;
  border-top: 1px solid rgba(128, 128, 128, 0.2);
  padding-top: 0.6em;
}
.archived-collapse {
  margin: 0.6em 0.4em;
}
</style>
```

- [ ] **Step 3: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开开发地址，手动导航到（这一步页面还没接进路由，可以临时在任意已有页面里 `import ProjectNav from '@/views/todo/TaskList/ProjectNav.vue'` 塞进 template 里跑一下，验证完再删掉这段临时代码）；或者跳过肉眼验证，先跑 `pnpm lint` 确认无语法错误，实际交互验证放到 Task 10 页面组装完之后一起做。

Run: `cd web && pnpm lint`
Expected: 无报错。

- [ ] **Step 4: 提交**

```bash
git add web/src/views/todo/TaskList/NewProjectModal.vue web/src/views/todo/TaskList/ProjectNav.vue
git commit -m "feat(web): add ProjectNav and NewProjectModal components"
```

---

## Task 9: `TaskDetailModal.vue`

**Files:**
- Create: `web/src/views/todo/TaskList/TaskDetailModal.vue`

**Interfaces:**
- Consumes：Task 7 的 `api.getTodoById`、`api.updateTodo`、`api.deleteTodo`、`api.getSubtasks`、`api.createSubtask`、`api.updateSubtask`、`api.deleteSubtask`。
- Produces：组件 props `show`（v-model）、`todoId`（Number\|null）、`projects`（Array，父组件传入的项目列表，用于下拉选项）；emits `update:show`、`saved`（payload 更新后的 todo）、`deleted`（payload todoId）。Task 10 引入并传入当前 `projectList`。

- [ ] **Step 1: 写 `TaskDetailModal.vue`**

```vue
<template>
  <n-modal :show="show" preset="card" title="任务详情" style="width: 640px" @update:show="onUpdateShow">
    <n-spin :show="loading">
      <n-form label-placement="left" label-width="70">
        <n-form-item label="标题">
          <n-input v-model:value="form.title" placeholder="标题" />
        </n-form-item>
        <n-form-item label="备注">
          <n-input
            v-model:value="form.notes"
            type="textarea"
            :rows="2"
            placeholder="添加备注...（可记录完成方法、收获、注意事项等）"
          />
        </n-form-item>

        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5em 1em">
          <n-form-item label="项目">
            <n-select v-model:value="form.project_id" :options="projectOptions" clearable placeholder="收件箱" />
          </n-form-item>
          <n-form-item label="截止日期">
            <n-date-picker v-model:value="form.due_date" type="date" clearable style="width: 100%" />
          </n-form-item>
          <n-form-item label="提醒时间">
            <n-date-picker v-model:value="form.reminder_at" type="datetime" clearable style="width: 100%" />
          </n-form-item>
        </div>

        <n-form-item label="象限">
          <n-radio-group v-model:value="form.quadrant_type">
            <n-space>
              <n-radio v-for="opt in quadrantOptions" :key="opt.value" :value="opt.value">
                <span class="quadrant-dot" :style="{ background: opt.color }"></span>
                {{ opt.label }}
              </n-radio>
            </n-space>
          </n-radio-group>
        </n-form-item>
      </n-form>

      <n-divider />

      <section>
        <h4 style="font-size: 1em; font-weight: 600; margin-bottom: 0.6em">子任务</h4>
        <div v-for="sub in subtasks" :key="sub.id" class="subtask-row">
          <n-checkbox :checked="sub.is_completed" @update:checked="(v) => toggleSubtask(sub, v)" />
          <n-input
            v-model:value="sub.title"
            size="small"
            style="flex: 1; margin: 0 0.5em"
            @blur="renameSubtask(sub)"
          />
          <n-button text type="error" @click="removeSubtask(sub)">删除</n-button>
        </div>
        <div style="display: flex; margin-top: 0.5em">
          <n-input v-model:value="newSubtaskTitle" placeholder="添加子任务..." @keyup.enter="addSubtask" />
          <n-button type="primary" style="margin-left: 0.5em" @click="addSubtask">添加</n-button>
        </div>
      </section>
    </n-spin>

    <template #footer>
      <div style="display: flex; justify-content: space-between">
        <n-button type="error" ghost @click="handleDelete">删除任务</n-button>
        <div style="display: flex; gap: 0.5em">
          <n-button @click="onUpdateShow(false)">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleSave">保存更改</n-button>
        </div>
      </div>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false },
  todoId: { type: Number, default: null },
  projects: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:show', 'saved', 'deleted'])

const message = useMessage()
const dialog = useDialog()

const loading = ref(false)
const saving = ref(false)
const subtasks = ref([])
const newSubtaskTitle = ref('')

const form = ref({
  title: '',
  notes: '',
  project_id: null,
  due_date: null,
  reminder_at: null,
  quadrant_type: 'not_urgent_not_important'
})

const quadrantOptions = [
  { label: '重要且紧急', value: 'urgent_important', color: '#f5222d' },
  { label: '紧急不重要', value: 'urgent_not_important', color: '#faad14' },
  { label: '重要不紧急', value: 'important_not_urgent', color: '#1890ff' },
  { label: '不紧急不重要', value: 'not_urgent_not_important', color: '#909399' }
]

const projectOptions = computed(() => {
  const options = props.projects
    .filter((p) => !p.is_archived)
    .map((p) => ({ label: p.name, value: p.id }))
  const current = props.projects.find((p) => p.id === form.value.project_id)
  if (current && current.is_archived) {
    options.push({ label: `${current.name}（已归档）`, value: current.id })
  }
  return options
})

const onUpdateShow = (value) => {
  emit('update:show', value)
}

const toDateValue = (isoString) => (isoString ? new Date(isoString).getTime() : null)

const loadDetail = async () => {
  if (!props.todoId) return
  loading.value = true
  try {
    const [todoRes, subtaskRes] = await Promise.all([
      api.getTodoById(props.todoId),
      api.getSubtasks(props.todoId)
    ])
    const todo = todoRes.data
    form.value = {
      title: todo.title,
      notes: todo.notes || '',
      project_id: todo.project_id,
      due_date: toDateValue(todo.due_date),
      reminder_at: toDateValue(todo.reminder_at),
      quadrant_type: todo.quadrant_type
    }
    subtasks.value = subtaskRes.data || []
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.show, props.todoId],
  ([visible]) => {
    if (visible) loadDetail()
  }
)

const handleSave = async () => {
  saving.value = true
  try {
    const payload = {
      title: form.value.title,
      notes: form.value.notes,
      project_id: form.value.project_id,
      due_date: form.value.due_date ? new Date(form.value.due_date).toISOString() : null,
      reminder_at: form.value.reminder_at ? new Date(form.value.reminder_at).toISOString() : null,
      quadrant_type: form.value.quadrant_type
    }
    const res = await api.updateTodo(props.todoId, payload)
    message.success('保存成功')
    emit('saved', res.data)
    onUpdateShow(false)
  } finally {
    saving.value = false
  }
}

const handleDelete = () => {
  dialog.warning({
    title: '确认删除',
    content: '确定要删除这条任务吗？',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      await api.deleteTodo(props.todoId)
      message.success('删除成功')
      emit('deleted', props.todoId)
      onUpdateShow(false)
    }
  })
}

const toggleSubtask = async (sub, checked) => {
  sub.is_completed = checked
  await api.updateSubtask(sub.id, { is_completed: checked })
}

const renameSubtask = async (sub) => {
  await api.updateSubtask(sub.id, { title: sub.title })
}

const removeSubtask = async (sub) => {
  await api.deleteSubtask(sub.id)
  subtasks.value = subtasks.value.filter((s) => s.id !== sub.id)
}

const addSubtask = async () => {
  const title = newSubtaskTitle.value.trim()
  if (!title) return
  const res = await api.createSubtask({ todo_item_id: props.todoId, title })
  subtasks.value.push(res.data)
  newSubtaskTitle.value = ''
}
</script>

<style scoped>
.subtask-row {
  display: flex;
  align-items: center;
  padding: 0.3em 0;
}
.quadrant-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.4em;
}
</style>
```

- [ ] **Step 2: 手动验证**

Run: `cd web && pnpm lint`
Expected: 无报错。（完整的打开-编辑-保存交互验证放在 Task 10 页面组装完之后一起做，因为这个组件需要 `todoId` 才能拉到数据。）

- [ ] **Step 3: 提交**

```bash
git add web/src/views/todo/TaskList/TaskDetailModal.vue
git commit -m "feat(web): add TaskDetailModal component"
```

---

## Task 10: `TaskList/index.vue`（页面组装：quick-add + 排序/过滤 + 分组列表）

**Files:**
- Create: `web/src/views/todo/TaskList/index.vue`

**Interfaces:**
- Consumes：Task 7 的 API 客户端；Task 8 的 `ProjectNav`（`select`/`changed` 事件）；Task 9 的 `TaskDetailModal`（`show`/`todoId`/`projects` props，`saved`/`deleted` 事件）；Task 6 的 Menu 记录（`component: "/todo/TaskList"` 会被 `import.meta.glob('@/views/**/index.vue')` 解析到这个文件）。
- Produces：页面级组件，无对外接口（叶子节点）。

- [ ] **Step 1: 写 `index.vue`**

```vue
<template>
  <div class="task-list-page">
    <div class="tasks-layout">
      <ProjectNav ref="projectNavRef" @select="handleSelect" @changed="fetchProjectList" />

      <div class="task-area">
        <div class="task-area-header">
          <h2>{{ headerTitle }}</h2>
          <div class="toolbar">
            <n-select
              v-model:value="sortBy"
              :options="sortOptions"
              size="small"
              style="width: 140px"
              @update:value="fetchTodos"
            />
            <n-select
              v-model:value="filterStatus"
              :options="statusOptions"
              size="small"
              style="width: 110px"
              @update:value="fetchTodos"
            />
            <n-select
              v-model:value="filterQuadrants"
              :options="quadrantOptions"
              multiple
              clearable
              size="small"
              placeholder="全部象限"
              style="width: 180px"
              @update:value="fetchTodos"
            />
          </div>
        </div>

        <div class="quick-add">
          <n-input
            v-model:value="quickAddTitle"
            :placeholder="quickAddPlaceholder"
            @keyup.enter="handleQuickAdd"
          />
          <n-button type="primary" @click="handleQuickAdd">添加</n-button>
        </div>

        <div v-for="group in groupedTodos" :key="group.key" class="task-group">
          <h4 v-if="group.items.length" class="group-title" :style="{ color: group.color }">{{ group.label }}</h4>
          <div
            v-for="todo in group.items"
            :key="todo.id"
            class="task-item"
            :class="{ completed: todo.is_completed }"
          >
            <n-checkbox :checked="todo.is_completed" @update:checked="(v) => toggleComplete(todo, v)" />
            <div class="task-content" @click="openDetail(todo.id)">
              <span class="task-title">{{ todo.title }}</span>
              <div class="task-meta">
                <span v-if="todo.due_date" :class="{ overdue: isOverdue(todo) }">
                  {{ formatDueDate(todo.due_date) }}
                </span>
                <span v-else>无截止时间</span>
                <span>
                  <span class="quadrant-dot" :style="{ background: quadrantColor(todo.quadrant_type) }"></span>
                  {{ quadrantLabel(todo.quadrant_type) }}
                </span>
                <span v-if="todo.subtask_total">{{ todo.subtask_completed }}/{{ todo.subtask_total }} 子任务</span>
              </div>
            </div>
          </div>
        </div>

        <n-empty v-if="!todos.length" description="暂无任务" />
      </div>
    </div>

    <TaskDetailModal
      v-model:show="detailShow"
      :todo-id="detailTodoId"
      :projects="projectList"
      @saved="fetchTodos"
      @deleted="fetchTodos"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import api from '@/api'
import ProjectNav from './ProjectNav.vue'
import TaskDetailModal from './TaskDetailModal.vue'

const message = useMessage()

const projectNavRef = ref(null)
const selection = ref({ type: 'inbox' })
const projectList = ref([])
const todos = ref([])
const quickAddTitle = ref('')
const detailShow = ref(false)
const detailTodoId = ref(null)

const sortBy = ref('created_at')
const filterStatus = ref('incomplete')
const filterQuadrants = ref([])

const sortOptions = [
  { label: '按截止时间', value: 'due_date' },
  { label: '按象限', value: 'quadrant_type' },
  { label: '按创建时间', value: 'created_at' }
]
const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '未完成', value: 'incomplete' },
  { label: '已完成', value: 'completed' }
]
const quadrantMeta = {
  urgent_important: { label: '重要且紧急', color: '#f5222d' },
  urgent_not_important: { label: '紧急不重要', color: '#faad14' },
  important_not_urgent: { label: '重要不紧急', color: '#1890ff' },
  not_urgent_not_important: { label: '不紧急不重要', color: '#909399' }
}
const quadrantOptions = Object.entries(quadrantMeta).map(([value, meta]) => ({ label: meta.label, value }))
const quadrantLabel = (type) => quadrantMeta[type]?.label || type
const quadrantColor = (type) => quadrantMeta[type]?.color || '#909399'

const headerTitle = computed(() => (selection.value.type === 'inbox' ? '收件箱' : selection.value.name))
const quickAddPlaceholder = computed(() =>
  selection.value.type === 'inbox' ? '添加任务到收件箱 (按 Enter 保存)' : '添加任务到当前项目 (按 Enter 保存)'
)

const fetchProjectList = async () => {
  const res = await api.getProjects()
  projectList.value = res.data || []
}

const fetchTodos = async () => {
  const params = {
    page: 1,
    page_size: 200,
    sort_by: sortBy.value,
    sort_order: sortBy.value === 'created_at' ? 'desc' : 'asc'
  }
  if (selection.value.type === 'inbox') {
    params.inbox_only = true
  } else {
    params.project_id = selection.value.id
  }
  if (filterStatus.value === 'incomplete') params.is_completed = false
  if (filterStatus.value === 'completed') params.is_completed = true
  if (filterQuadrants.value.length) params.quadrant_type = filterQuadrants.value.join(',')

  const res = await api.getTodos(params)
  todos.value = res.data || []
}

const handleSelect = (payload) => {
  selection.value = payload
  fetchTodos()
}

const handleQuickAdd = async () => {
  const title = quickAddTitle.value.trim()
  if (!title) return
  const payload = { title, quadrant_type: 'not_urgent_not_important' }
  if (selection.value.type === 'project') payload.project_id = selection.value.id
  await api.createTodo(payload)
  quickAddTitle.value = ''
  message.success('已添加')
  fetchTodos()
}

const toggleComplete = async (todo, checked) => {
  await api.updateTodo(todo.id, { is_completed: checked })
  fetchTodos()
}

const openDetail = (todoId) => {
  detailTodoId.value = todoId
  detailShow.value = true
}

const isOverdue = (todo) => {
  if (todo.is_completed || !todo.due_date) return false
  return new Date(todo.due_date).getTime() < startOfToday()
}

const startOfToday = () => {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

const formatDueDate = (dueDate) => {
  const date = new Date(dueDate)
  return date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const groupedTodos = computed(() => {
  const today = startOfToday()
  const tomorrow = today + 24 * 60 * 60 * 1000
  const overdue = []
  const todayItems = []
  const later = []

  for (const todo of todos.value) {
    if (!todo.due_date) {
      later.push(todo)
      continue
    }
    const due = new Date(todo.due_date).getTime()
    if (due < today && !todo.is_completed) {
      overdue.push(todo)
    } else if (due >= today && due < tomorrow) {
      todayItems.push(todo)
    } else {
      later.push(todo)
    }
  }

  return [
    { key: 'overdue', label: '已过期', color: '#f5222d', items: overdue },
    { key: 'today', label: '今天', color: '#1890ff', items: todayItems },
    { key: 'later', label: '稍后', color: '', items: later }
  ]
})

onMounted(() => {
  fetchProjectList()
})
</script>

<style scoped>
.tasks-layout {
  display: flex;
  gap: 1.5em;
  align-items: flex-start;
}
.task-area {
  flex: 1;
  min-width: 0;
}
.task-area-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1em;
}
.toolbar {
  display: flex;
  gap: 0.5em;
}
.quick-add {
  display: flex;
  gap: 0.5em;
  margin-bottom: 1em;
}
.group-title {
  margin: 1em 0 0.5em 0.2em;
  font-size: 0.9em;
  font-weight: 600;
}
.task-item {
  display: flex;
  align-items: center;
  gap: 0.6em;
  padding: 0.5em 0.2em;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
}
.task-item.completed .task-title {
  text-decoration: line-through;
  opacity: 0.5;
}
.task-content {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}
.task-title {
  display: block;
}
.task-meta {
  display: flex;
  gap: 1em;
  font-size: 0.82em;
  opacity: 0.7;
  margin-top: 0.2em;
}
.task-meta .overdue {
  color: #f5222d;
  opacity: 1;
}
.quadrant-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.3em;
}
</style>
```

- [ ] **Step 2: 手动验证（端到端走一遍验收标准）**

Run: `cd web && pnpm dev`（同时确认后端 `python run.py` 在跑）

1. 登录后左侧菜单能看到"待办事项 → 任务"，点进去能打开任务列表页，左侧显示"收件箱"+按分类分组的项目/清单+折叠的归档分组。
2. 在 quick-add 输入框里输入标题回车，任务出现在收件箱的"今天"或"稍后"分组里（因为没设截止日期）。
3. 点这条任务标题，弹出详情弹窗，能看到标题/备注/项目/截止日期/提醒/象限/子任务区；加一条子任务、勾选、改标题、删除都生效；改象限/项目/截止日期后点"保存更改"，列表页对应更新。
4. 用"新建项目/清单"创建一个新项目（输入新分类名），左侧导航栏出现对应分组和项目；点这个项目，quick-add 新建的任务落在这个项目下而不是收件箱。
5. 把这个项目删除，原来挂在它下面的任务应该退回收件箱可见，而不是被删掉。
6. 切换排序（截止时间/象限/创建时间）、过滤（状态/象限多选），列表按预期变化；把"状态"切到"已完成"能看到之前勾选过的任务（划线样式）。

Expected: 以上步骤全部符合预期，控制台无报错。

Run: `cd web && pnpm lint`
Expected: 无报错。

- [ ] **Step 3: 提交**

```bash
git add web/src/views/todo/TaskList/index.vue
git commit -m "feat(web): assemble TaskList page with quick-add, sort/filter, grouped list"
```

---

## Self-Review Notes

- **Spec 覆盖检查**：数据模型变更（Task 2）、API 端点设计（Task 3/4/5）、前端页面与交互（Task 8/9/10）、Menu 与权限（Task 6，`dependencies=[DependPermission]` 在 Task 3/4/5 挂路由时一并完成）、已知边缘情况（迁移历史在 Task 2 Step 4 说明；FK on_delete 显式处理在 Task 3 `delete_project` 里落实；过滤参数组合 `inbox_only` 优先级在 Task 5 controller 里实现；子任务计数聚合在 Task 4 `get_counts_by_todo_ids` 里实现）——spec 里的每一节都能对应到具体任务。
- **占位符扫描**：全文没有 "TBD"/"实现类似逻辑" 之类的占位，每个 Step 都是可直接执行的完整代码或明确的验证命令。
- **类型一致性**：`TodoItemOut.subtask_total/subtask_completed` 在 Task 5 定义，Task 5 的路由和 Task 10 的前端 `todo.subtask_total` 用的是同一个字段名；`ProjectOut.category_name` 在 Task 3 的 controller `to_out_dict` 里生成，Task 8 的 `ProjectNav` 按 `category_name` 分组用的是同一字段；`SubTaskController.get_counts_by_todo_ids` 返回 `Dict[int, Tuple[int, int]]`（total, completed）的顺序在 Task 4 定义、Task 5 消费时保持一致（`total_sub, completed_sub = counts.get(...)`）。
