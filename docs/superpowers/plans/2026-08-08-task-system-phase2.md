# 二期：日历排程 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 `docs/superpowers/specs/2026-08-08-task-system-phase2-design.md` 描述的二期日历排程：新增 `TimeBlock` 模型 + 接口，把 `public/design/schedule-week.html`（周视图）和 `public/design/calendar-day.html`（日视图）两个已完成的静态 mockup 转成真正接后端的 Vue 页面，并新增"日历"菜单入口。

**Architecture:** 后端沿用 `app/api/v1/subtask` 现有的扁平 `/list /create /delete` 路由风格 + `CRUDBase` 继承模式，新增 `timeblock` 资源模块，并扩展 `todos` 模块（`TodoItemCreate` 支持批量提交 `time_blocks`、`/todo/list` 支持 `unscheduled_only` 过滤）。前端新增 `web/src/views/todo/Schedule/` 页面（`index.vue` 页面壳 + `WeekView.vue` 周视图 + `DayView.vue` 日视图 + `CreateTodoWithSlotsModal.vue` 周视图创建弹窗），由新的 Menu 记录驱动路由，复用一期已有的 `TaskDetailModal.vue` 处理"点击日历色块编辑任务"。先后端（含 pytest 单测）后前端。

**Tech Stack:** FastAPI + Tortoise ORM（后端），Vue 3 `<script setup>` + Naive UI（前端），pytest + pytest-asyncio + httpx（后端测试，沿用一期搭好的 `tests/conftest.py`）。

## Global Constraints

- 路由风格：`/list` `/create` `/delete` + query 参数，不做嵌套 REST，路由文件放在 `app/api/v1/<resource>/route.py` + `__init__.py`。
- 所有新路由挂 `dependencies=[DependPermission]`；处理函数内部用 `Depends(AuthControl.is_authed)` 取当前用户，所有查询按 `user_id` 过滤，不做细粒度 RBAC（沿用 `todos`/`subtask` 模块现状）。
- 象限配色（前端展示用）：`urgent_important` = `#f5222d`，`urgent_not_important` = `#faad14`，`important_not_urgent` = `#1890ff`，`not_urgent_not_important` = `#909399`。
- 不做：事件块拖拽移动/调整时长、月视图、`TaskDetailModal.vue` 里手动新增时间块的入口（新增只走日历页拖拽/多选）。
- 前端所有接口调用统一加进 `web/src/api/` 下的具名方法模块（`web/src/api/index.js` 汇总导出），组件内不写裸 `axios`/`request` 调用。
- 后端每个任务遵循"写测试→跑测试确认现象→写实现→跑测试确认通过→提交"的顺序，复用一期的 `tests/conftest.py` 三个 fixture（`db`/`test_user`/`client`），不重新声明。前端本仓库未配置测试运行器（`pnpm lint` 是唯一自动化检查），前端任务改为"实现→`pnpm lint`→手动在浏览器里验证→提交"，最终 Task 10 做一次端到端浏览器走查。

---

## Task 1: TimeBlock 模型

**Files:**
- Modify: `app/models/todo.py`
- Modify: `app/models/__init__.py`

**Interfaces:**
- Produces：`app.models.todo.TimeBlock`（字段：`todo_item`(FK→TodoItem，级联删除，`related_name="time_blocks"`)、`user`(FK→User)、`start_time`、`end_time`）。这是 Task 2/3 的直接依赖。

- [ ] **Step 1: 修改 `app/models/todo.py`，在文件末尾（`SubTask` 类之后）新增**

```python
class TimeBlock(BaseModel, TimestampMixin):
    """时间块模型：一个待办事项可以有多个时间块，用于日历排程"""

    todo_item = fields.ForeignKeyField(
        "models.TodoItem", related_name="time_blocks", on_delete=fields.CASCADE, description="所属待办事项"
    )
    user = fields.ForeignKeyField(
        "models.User", related_name="time_blocks", description="所属用户，冗余存储，按用户+日期范围直查"
    )
    start_time = fields.DatetimeField(description="开始时间")
    end_time = fields.DatetimeField(description="结束时间")

    class Meta:
        table = "time_block"

    def __str__(self):
        return f"{self.start_time} - {self.end_time}"
```

- [ ] **Step 2: 修改 `app/models/__init__.py`**

```python
# 新增model需要在这里导入
from .admin import *
from .todo import Category, Project, QuadrantType, SubTask, TimeBlock, TodoItem
```

- [ ] **Step 3: 跑一次冒烟测试确认模型改动没有语法/引用错误**

Run: `pytest tests/test_smoke.py -vv`
Expected: `1 passed`（顺带验证 `Tortoise.generate_schemas()` 能正确建出 `TimeBlock` 表结构）。

- [ ] **Step 4: 生成并应用 aerich 迁移**

`migrations/` 目录被 gitignore，本地已有迁移历史的情况下，启动应用会自动检测模型变更并生成新的迁移文件：

Run: `python run.py`（等到控制台打出启动完成的日志后 Ctrl+C 停掉）

Expected: 无报错退出；若报连接数据库失败，说明当前生效的数据库连接配置在本机不可达，需要先配好本地可访问的数据库再继续。

- [ ] **Step 5: 提交**

```bash
git add app/models/todo.py app/models/__init__.py
git commit -m "feat: add TimeBlock model"
```

---

## Task 2: TimeBlock 资源接口

**Files:**
- Create: `app/schemas/timeblock.py`
- Create: `app/controllers/timeblock.py`
- Create: `app/api/v1/timeblock/__init__.py`
- Create: `app/api/v1/timeblock/route.py`
- Modify: `app/api/v1/__init__.py`
- Create: `tests/test_timeblock.py`

**Interfaces:**
- Consumes：Task 1 的 `TimeBlock` 模型。
- Produces：`app.controllers.timeblock.time_block_controller`（方法 `create_time_block(obj_in, user_id) -> Optional[TimeBlock]`，校验失败抛 `ValueError`；`list_by_date_range(user_id, start_date, end_date) -> List[TimeBlock]`；`list_by_todo(todo_item_id, user_id) -> Optional[List[TimeBlock]]`；`delete_time_block(time_block_id, user_id) -> bool`；`get_scheduled_todo_ids(user_id) -> List[int]`）。`get_scheduled_todo_ids` 是 Task 3 的直接依赖。`GET/POST/DELETE /api/v1/timeblock/*` 供 Task 6（TaskDetailModal）、Task 8/9（WeekView/DayView）前端调用。

- [ ] **Step 1: 写测试（先写，此时对应路由还不存在，预期 404）**

```python
# tests/test_timeblock.py
from datetime import datetime

from app.models.todo import QuadrantType, TimeBlock, TodoItem


async def _create_todo(user_id, title="项目评审会议"):
    return await TodoItem.create(title=title, quadrant_type=QuadrantType.URGENT_IMPORTANT, user_id=user_id)


async def test_create_time_block(client, test_user):
    todo = await _create_todo(test_user.id)
    resp = await client.post(
        "/api/v1/timeblock/create",
        json={
            "todo_item_id": todo.id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T10:30:00",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["todo_item_id"] == todo.id
    assert data["title"] == "项目评审会议"
    assert data["quadrant_type"] == "urgent_important"


async def test_create_time_block_rejects_end_before_start(client, test_user):
    todo = await _create_todo(test_user.id)
    resp = await client.post(
        "/api/v1/timeblock/create",
        json={"todo_item_id": todo.id, "start_time": "2026-08-10T10:00:00", "end_time": "2026-08-10T09:00:00"},
    )
    assert resp.status_code == 400


async def test_create_time_block_rejects_crossing_midnight(client, test_user):
    todo = await _create_todo(test_user.id)
    resp = await client.post(
        "/api/v1/timeblock/create",
        json={"todo_item_id": todo.id, "start_time": "2026-08-10T23:30:00", "end_time": "2026-08-11T00:30:00"},
    )
    assert resp.status_code == 400


async def test_create_time_block_for_missing_todo_returns_404(client):
    resp = await client.post(
        "/api/v1/timeblock/create",
        json={"todo_item_id": 99999, "start_time": "2026-08-10T09:00:00", "end_time": "2026-08-10T10:00:00"},
    )
    assert resp.status_code == 404


async def test_list_by_date_range(client, test_user):
    todo = await _create_todo(test_user.id)
    await TimeBlock.create(
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )
    await TimeBlock.create(
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime(2026, 9, 1, 9, 0),
        end_time=datetime(2026, 9, 1, 10, 0),
    )

    resp = await client.get("/api/v1/timeblock/list", params={"start_date": "2026-08-03", "end_date": "2026-08-09"})
    assert resp.json()["data"] == []

    resp = await client.get("/api/v1/timeblock/list", params={"start_date": "2026-08-10", "end_date": "2026-08-10"})
    assert len(resp.json()["data"]) == 1


async def test_list_by_todo_item_id(client, test_user):
    todo = await _create_todo(test_user.id)
    await TimeBlock.create(
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )
    resp = await client.get("/api/v1/timeblock/list", params={"todo_item_id": todo.id})
    assert len(resp.json()["data"]) == 1


async def test_list_requires_todo_id_or_date_range(client):
    resp = await client.get("/api/v1/timeblock/list")
    assert resp.status_code == 400


async def test_delete_time_block(client, test_user):
    todo = await _create_todo(test_user.id)
    block = await TimeBlock.create(
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )
    resp = await client.delete("/api/v1/timeblock/delete", params={"time_block_id": block.id})
    assert resp.status_code == 200
    assert await TimeBlock.filter(id=block.id).count() == 0


async def test_deleting_todo_cascades_to_time_blocks(client, test_user):
    todo = await _create_todo(test_user.id)
    await TimeBlock.create(
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )
    resp = await client.delete("/api/v1/todo/delete", params={"todo_id": todo.id})
    assert resp.status_code == 200
    assert await TimeBlock.filter(todo_item_id=todo.id).count() == 0


async def test_create_time_block_for_other_user_todo_returns_404(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_todo = await _create_todo(other_user.id, title="别人的会议")

    resp = await client.post(
        "/api/v1/timeblock/create",
        json={"todo_item_id": other_todo.id, "start_time": "2026-08-10T09:00:00", "end_time": "2026-08-10T10:00:00"},
    )
    assert resp.status_code == 404


async def test_delete_time_block_owned_by_other_user_returns_404(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_todo = await _create_todo(other_user.id, title="别人的会议")
    other_block = await TimeBlock.create(
        todo_item_id=other_todo.id,
        user_id=other_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )

    resp = await client.delete("/api/v1/timeblock/delete", params={"time_block_id": other_block.id})
    assert resp.status_code == 404
    assert await TimeBlock.filter(id=other_block.id).count() == 1


async def test_list_by_todo_item_id_for_other_user_returns_404(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_todo = await _create_todo(other_user.id, title="别人的会议")

    resp = await client.get("/api/v1/timeblock/list", params={"todo_item_id": other_todo.id})
    assert resp.status_code == 404
```

- [ ] **Step 2: 跑测试确认现象**

Run: `pytest tests/test_timeblock.py -vv`
Expected: 全部失败（`404 Not Found`，因为 `/api/v1/timeblock/*` 还没注册）。

- [ ] **Step 3: 写 `app/schemas/timeblock.py`**

```python
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.todo import QuadrantType


class TimeBlockCreate(BaseModel):
    todo_item_id: int = Field(..., description="所属待办事项ID")
    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")


class TimeBlockOut(BaseModel):
    id: int
    todo_item_id: int
    start_time: datetime
    end_time: datetime
    title: str = Field(..., description="所属待办事项标题")
    quadrant_type: QuadrantType = Field(..., description="所属待办事项象限")

    class Config:
        from_attributes = True
```

- [ ] **Step 4: 写 `app/controllers/timeblock.py`**

```python
from datetime import date, datetime, time
from typing import List, Optional

from app.core.crud import CRUDBase
from app.models.todo import TimeBlock, TodoItem
from app.schemas.timeblock import TimeBlockCreate


class TimeBlockController(CRUDBase[TimeBlock, TimeBlockCreate, TimeBlockCreate]):
    def __init__(self):
        super().__init__(model=TimeBlock)

    async def create_time_block(self, obj_in: TimeBlockCreate, user_id: int) -> Optional[TimeBlock]:
        todo = await TodoItem.filter(id=obj_in.todo_item_id, user_id=user_id).first()
        if not todo:
            return None
        if obj_in.end_time <= obj_in.start_time:
            raise ValueError("end_time 必须晚于 start_time")
        if obj_in.start_time.date() != obj_in.end_time.date():
            raise ValueError("时间块不能跨天")
        return await TimeBlock.create(
            todo_item_id=obj_in.todo_item_id,
            user_id=user_id,
            start_time=obj_in.start_time,
            end_time=obj_in.end_time,
        )

    async def list_by_date_range(self, user_id: int, start_date: date, end_date: date) -> List[TimeBlock]:
        return (
            await TimeBlock.filter(
                user_id=user_id,
                start_time__gte=datetime.combine(start_date, time.min),
                start_time__lte=datetime.combine(end_date, time.max),
            )
            .select_related("todo_item")
            .order_by("start_time")
        )

    async def list_by_todo(self, todo_item_id: int, user_id: int) -> Optional[List[TimeBlock]]:
        todo = await TodoItem.filter(id=todo_item_id, user_id=user_id).first()
        if not todo:
            return None
        return await TimeBlock.filter(todo_item_id=todo_item_id).select_related("todo_item").order_by("start_time")

    async def delete_time_block(self, time_block_id: int, user_id: int) -> bool:
        deleted_count = await TimeBlock.filter(id=time_block_id, user_id=user_id).delete()
        return deleted_count > 0

    async def get_scheduled_todo_ids(self, user_id: int) -> List[int]:
        """已有任意时间块的待办事项ID，供 /todo/list?unscheduled_only 排除用"""
        return await TimeBlock.filter(user_id=user_id).distinct().values_list("todo_item_id", flat=True)


time_block_controller = TimeBlockController()
```

- [ ] **Step 5: 写 `app/api/v1/timeblock/route.py`**

```python
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.controllers.timeblock import time_block_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.todo import TimeBlock
from app.schemas.base import Success
from app.schemas.timeblock import TimeBlockCreate, TimeBlockOut

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_out_dict(block: TimeBlock) -> dict:
    return {
        "id": block.id,
        "todo_item_id": block.todo_item_id,
        "start_time": block.start_time,
        "end_time": block.end_time,
        "title": block.todo_item.title,
        "quadrant_type": block.todo_item.quadrant_type,
    }


@router.get("/list", summary="获取时间块列表（按日期范围或按待办事项二选一）")
async def list_time_blocks(
    start_date: Optional[date] = Query(None, description="开始日期，与 end_date 搭配使用"),
    end_date: Optional[date] = Query(None, description="结束日期，与 start_date 搭配使用"),
    todo_item_id: Optional[int] = Query(None, description="待办事项ID，与日期范围二选一"),
    current_user: User = Depends(AuthControl.is_authed),
):
    if todo_item_id is not None:
        blocks = await time_block_controller.list_by_todo(todo_item_id, current_user.id)
        if blocks is None:
            raise HTTPException(status_code=404, detail="待办事项不存在")
    elif start_date is not None and end_date is not None:
        blocks = await time_block_controller.list_by_date_range(current_user.id, start_date, end_date)
    else:
        raise HTTPException(status_code=400, detail="必须传 todo_item_id，或同时传 start_date 和 end_date")

    result = [TimeBlockOut(**_to_out_dict(b)).model_dump() for b in blocks]
    return Success(data=result)


@router.post("/create", summary="为待办事项新增一个时间块")
async def create_time_block(time_block_in: TimeBlockCreate, current_user: User = Depends(AuthControl.is_authed)):
    try:
        block = await time_block_controller.create_time_block(time_block_in, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not block:
        raise HTTPException(status_code=404, detail="待办事项不存在")
    await block.fetch_related("todo_item")
    return Success(data=TimeBlockOut(**_to_out_dict(block)).model_dump())


@router.delete("/delete", summary="删除时间块")
async def delete_time_block(
    time_block_id: int = Query(..., description="时间块ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    success = await time_block_controller.delete_time_block(time_block_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="时间块不存在")
    return Success(msg="删除成功")
```

- [ ] **Step 6: 写 `app/api/v1/timeblock/__init__.py`**

```python
from fastapi import APIRouter

from .route import router

timeblock_router = APIRouter()
timeblock_router.include_router(router, tags=["时间块"])

__all__ = ["timeblock_router"]
```

- [ ] **Step 7: 挂载到 `app/api/v1/__init__.py`**

在现有 import 列表里按字母序插入一行，并在 `v1_router.include_router(...)` 列表末尾新增一行：

```python
from .subtask import subtask_router
from .timeblock import timeblock_router
from .todos import todos_router
```

```python
v1_router.include_router(subtask_router, prefix="/subtask", dependencies=[DependPermission])
v1_router.include_router(timeblock_router, prefix="/timeblock", dependencies=[DependPermission])
```

- [ ] **Step 8: 跑测试确认通过**

Run: `pytest tests/test_timeblock.py -vv`
Expected: `12 passed`

- [ ] **Step 9: 提交**

```bash
git add app/schemas/timeblock.py app/controllers/timeblock.py app/api/v1/timeblock \
        app/api/v1/__init__.py tests/test_timeblock.py
git commit -m "feat: add TimeBlock resource (create/list/delete)"
```

---

## Task 3: `/todo` 接口扩展（批量时间块创建 + 未排程过滤）

**Files:**
- Modify: `app/schemas/todo.py`
- Modify: `app/controllers/todo.py`
- Modify: `app/api/v1/todos/route.py`
- Modify: `tests/test_todo_list_extension.py`

**Interfaces:**
- Consumes：Task 2 的 `TimeBlock` 模型、`time_block_controller.get_scheduled_todo_ids`。
- Produces：`TodoItemCreate.time_blocks: Optional[List[TimeBlockInput]]`；`todo_controller.get_todos_by_user(..., unscheduled_only: Optional[bool] = None)`。Task 8（WeekView 创建待办）依赖 `time_blocks` 字段；Task 9（DayView 未安排面板）依赖 `unscheduled_only`。

- [ ] **Step 1: 写测试（先写，此时字段/参数还不存在，预期创建成功但不产生时间块、`unscheduled_only` 参数被忽略）**

在 `tests/test_todo_list_extension.py` 顶部的 import 行里加入 `TimeBlock`：

```python
from datetime import datetime

from app.models.todo import Project, QuadrantType, TimeBlock, TodoItem
```

在文件末尾追加：

```python
async def test_create_todo_with_time_blocks(client, test_user):
    resp = await client.post(
        "/api/v1/todo/create",
        json={
            "title": "团队周会",
            "quadrant_type": "urgent_important",
            "time_blocks": [
                {"start_time": "2026-08-10T09:00:00", "end_time": "2026-08-10T10:00:00"},
                {"start_time": "2026-08-12T09:00:00", "end_time": "2026-08-12T10:00:00"},
            ],
        },
    )
    assert resp.status_code == 200
    todo_id = resp.json()["data"]["id"]

    list_resp = await client.get("/api/v1/timeblock/list", params={"todo_item_id": todo_id})
    assert len(list_resp.json()["data"]) == 2


async def test_create_todo_rejects_time_block_crossing_midnight(client):
    resp = await client.post(
        "/api/v1/todo/create",
        json={
            "title": "跨天任务",
            "quadrant_type": "urgent_important",
            "time_blocks": [{"start_time": "2026-08-10T23:30:00", "end_time": "2026-08-11T00:30:00"}],
        },
    )
    assert resp.status_code == 400


async def test_list_unscheduled_only_excludes_scheduled_and_completed(client, test_user):
    unscheduled = await TodoItem.create(
        title="未排程任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id
    )
    scheduled = await TodoItem.create(
        title="已排程任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id
    )
    await TimeBlock.create(
        todo_item_id=scheduled.id,
        user_id=test_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )
    await TodoItem.create(
        title="已完成任务",
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        user_id=test_user.id,
        is_completed=True,
    )
    del unscheduled  # 仅用于建库，断言走标题比较

    resp = await client.get("/api/v1/todo/list", params={"unscheduled_only": True})
    titles = [t["title"] for t in resp.json()["data"]]
    assert titles == ["未排程任务"]
```

- [ ] **Step 2: 跑测试确认现象**

Run: `pytest tests/test_todo_list_extension.py -vv`
Expected: `test_create_todo_with_time_blocks` 失败（`time_blocks` 字段被 pydantic 忽略，`/timeblock/list` 返回空列表，断言 `len(...) == 2` 不成立）；`test_create_todo_rejects_time_block_crossing_midnight` 失败（返回 200 而非 400）；`test_list_unscheduled_only_excludes_scheduled_and_completed` 失败（`unscheduled_only` 未生效，返回全部三条）。

- [ ] **Step 3: 修改 `app/schemas/todo.py`，在 `TodoItemBase` 类之前新增 `TimeBlockInput`，并给 `TodoItemCreate` 加字段**

```python
class TimeBlockInput(BaseModel):
    """创建待办事项时可选提交的时间块（不含 todo_item_id，归属由外层待办事项决定）"""

    start_time: datetime = Field(..., description="开始时间")
    end_time: datetime = Field(..., description="结束时间")


class TodoItemBase(BaseModel):
    ...
```

`TodoItemCreate` 改成：

```python
class TodoItemCreate(TodoItemBase):
    """创建待办事项的请求体"""

    time_blocks: Optional[List[TimeBlockInput]] = Field(None, description="可选：创建待办的同时提交多个时间块")
```

- [ ] **Step 4: 修改 `app/controllers/todo.py`**

顶部 import 加入 `TimeBlock`：

```python
from app.models.todo import Project, QuadrantType, TimeBlock, TodoItem
```

`create_todo` 方法改成：

```python
    async def create_todo(self, obj_in: TodoItemCreate, user_id: int) -> TodoItem:
        """创建待办事项，可同时提交多个时间块（周视图拖拽/多选创建）"""
        await self._validate_project(obj_in.project_id, user_id)
        if obj_in.time_blocks:
            for block in obj_in.time_blocks:
                if block.end_time <= block.start_time:
                    raise HTTPException(status_code=400, detail="time_blocks 中 end_time 必须晚于 start_time")
                if block.start_time.date() != block.end_time.date():
                    raise HTTPException(status_code=400, detail="time_blocks 不能跨天")

        todo_dict = obj_in.model_dump(exclude={"time_blocks"})
        todo = TodoItem(**todo_dict, user_id=user_id)
        await todo.save()

        if obj_in.time_blocks:
            await TimeBlock.bulk_create(
                [
                    TimeBlock(todo_item_id=todo.id, user_id=user_id, start_time=b.start_time, end_time=b.end_time)
                    for b in obj_in.time_blocks
                ]
            )
        return todo
```

`get_todos_by_user` 方法签名新增一个参数（放在 `inbox_only` 之后）：

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
        unscheduled_only: Optional[bool] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Tuple[int, List[TodoItem]]:
```

在方法体内 `if inbox_only: ... elif project_id is not None: ...` 这段之后新增：

```python
        if unscheduled_only:
            from app.controllers.timeblock import time_block_controller

            scheduled_ids = await time_block_controller.get_scheduled_todo_ids(user_id)
            query &= Q(is_completed=False)
            if scheduled_ids:
                query &= ~Q(id__in=scheduled_ids)
```

（局部 import 是为了避免 `app/controllers/todo.py` 和 `app/controllers/timeblock.py` 之间产生模块级循环 import——两者都可能被对方引用。）

- [ ] **Step 5: 修改 `app/api/v1/todos/route.py`，`list_todos` 函数新增一个 query 参数并透传**

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
    unscheduled_only: Optional[bool] = Query(
        None, description="是否只看未排程任务（无任何时间块的未完成任务），用于日历页未安排面板"
    ),
    sort_by: Optional[str] = Query(None, description="排序字段: due_date/quadrant_type/created_at"),
    sort_order: Optional[str] = Query("asc", description="排序方向: asc/desc"),
    current_user: User = Depends(AuthControl.is_authed),
):
    """
    获取当前用户的待办事项列表，支持按象限（可多选）、完成状态、项目/收件箱/未排程筛选，支持排序
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
        unscheduled_only=unscheduled_only,
        sort_by=sort_by,
        sort_order=sort_order,
    )
```

（函数体其余部分不变。）

- [ ] **Step 6: 跑测试确认通过**

Run: `pytest tests/test_todo_list_extension.py tests/test_timeblock.py -vv`
Expected: 全部通过。

- [ ] **Step 7: 跑一次全量后端测试，确认没有破坏已有功能**

Run: `pytest -vv`
Expected: 全部通过。

- [ ] **Step 8: 提交**

```bash
git add app/schemas/todo.py app/controllers/todo.py app/api/v1/todos/route.py tests/test_todo_list_extension.py
git commit -m "feat: support batch time_blocks on todo create and unscheduled_only filter"
```

---

## Task 4: "日历" Menu 记录

**Files:**
- Modify: `app/core/init_app.py`

**Interfaces:**
- Consumes：无（纯数据初始化）。
- Produces：菜单记录 `component="/todo/Schedule"`，Task 7 的 `Schedule/index.vue` 依赖这条记录才能被路由到。

- [ ] **Step 1: 修改 `app/core/init_app.py`**

在"一期任务体系升级：任务列表页菜单"那个独立判断块（`todo_parent_menu = await Menu.filter(name="待办事项").first()` ... 创建"任务"菜单）之后，紧接着新增一个同样风格、同样独立的判断块：

```python
    # 二期日历排程：日历页菜单。独立于上面的判断，保证已经部署过的环境重启后也能自动补上
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        schedule_menu = await Menu.filter(name="日历", parent_id=todo_parent_menu.id).first()
        if not schedule_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="日历",
                path="schedule",
                order=1,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:calendar-month-outline",
                is_hidden=False,
                component="/todo/Schedule",
                keepalive=True,
            )
```

- [ ] **Step 2: 手动验证菜单初始化逻辑无语法错误**

Run: `python -c "import app.core.init_app"`
Expected: 无报错（只是语法/导入检查，不会真的连接数据库执行）。

- [ ] **Step 3: 提交**

```bash
git add app/core/init_app.py
git commit -m "feat: add Schedule (calendar) menu entry"
```

---

## Task 5: 前端 API 客户端（timeblock）

**Files:**
- Create: `web/src/api/timeblock.js`
- Modify: `web/src/api/index.js`

**Interfaces:**
- Consumes：Task 2/3 的 `/timeblock/*`、`/todo/list?unscheduled_only`、`/todo/create` 的 `time_blocks` 字段（后两者已有的 `getTodos`/`createTodo` 方法透传 params/body，不用改）。
- Produces：`api.getTimeBlocks(params)`、`api.createTimeBlock(data)`、`api.deleteTimeBlock(id)`。Task 6/8/9 的组件直接调用。

- [ ] **Step 1: 写 `web/src/api/timeblock.js`**

```js
import { request } from '@/utils'

/**
 * 时间块API接口
 */
export default {
  /**
   * 获取时间块列表（按日期范围或按待办事项二选一）
   * @param {Object} params
   * @param {String} [params.start_date]
   * @param {String} [params.end_date]
   * @param {Number} [params.todo_item_id]
   * @returns {Promise}
   */
  getTimeBlocks: (params = {}) => request.get('/timeblock/list', { params }),

  /**
   * 为待办事项新增一个时间块
   * @param {Object} data
   * @param {Number} data.todo_item_id
   * @param {String} data.start_time
   * @param {String} data.end_time
   * @returns {Promise}
   */
  createTimeBlock: (data = {}) => request.post('/timeblock/create', data),

  /**
   * 删除时间块
   * @param {Number} id
   * @returns {Promise}
   */
  deleteTimeBlock: (id) => request.delete('/timeblock/delete', { params: { time_block_id: id } })
}
```

- [ ] **Step 2: 修改 `web/src/api/index.js`**

在顶部 import 区加入：

```js
import timeblockApi from './timeblock'
```

在导出对象的 `...subtaskApi` 之后加入：

```js
  ...subtaskApi,
  // timeblock（二期日历排程）
  ...timeblockApi
```

- [ ] **Step 3: lint 检查**

Run: `cd web && pnpm lint`
Expected: 无报错。

- [ ] **Step 4: 提交**

```bash
git add web/src/api/timeblock.js web/src/api/index.js
git commit -m "feat(web): add timeblock API client"
```

---

## Task 6: `TaskDetailModal.vue` 新增"已排程时间"小节

**Files:**
- Modify: `web/src/views/todo/TaskList/TaskDetailModal.vue`

**Interfaces:**
- Consumes：Task 5 的 `api.getTimeBlocks`、`api.deleteTimeBlock`。
- Produces：无新的对外接口——这是已有组件的增量修改，Task 7 直接复用整个 `TaskDetailModal.vue`（原样引入，不用改调用方式）。

- [ ] **Step 1: 在"子任务"小节之后、`</n-spin>` 之前新增"已排程时间"小节**

找到这段（当前在子任务 `<div style="display: flex; margin-top: 0.5em">...</div>` 结束之后、`</section>` 和 `</n-spin>` 之间）：

```html
        <div style="display: flex; margin-top: 0.5em">
          <n-input v-model:value="newSubtaskTitle" placeholder="添加子任务..." @keyup.enter="addSubtask" />
          <n-button type="primary" style="margin-left: 0.5em" @click="addSubtask">添加</n-button>
        </div>
      </section>
    </n-spin>
```

改成：

```html
        <div style="display: flex; margin-top: 0.5em">
          <n-input v-model:value="newSubtaskTitle" placeholder="添加子任务..." @keyup.enter="addSubtask" />
          <n-button type="primary" style="margin-left: 0.5em" @click="addSubtask">添加</n-button>
        </div>
      </section>

      <n-divider />

      <section>
        <h4 style="font-size: 1em; font-weight: 600; margin-bottom: 0.6em">已排程时间</h4>
        <div v-if="!timeBlocks.length" style="font-size: 0.85em; opacity: 0.6">暂无排程，可在日历页拖拽安排时间</div>
        <div v-for="block in timeBlocks" :key="block.id" class="timeblock-row">
          <span>{{ formatTimeBlock(block) }}</span>
          <n-button text type="error" @click="removeTimeBlock(block)">删除</n-button>
        </div>
      </section>
    </n-spin>
```

- [ ] **Step 2: 新增 `timeBlocks` 状态**

找到：

```js
const loading = ref(false)
const saving = ref(false)
const subtasks = ref([])
const newSubtaskTitle = ref('')
```

改成：

```js
const loading = ref(false)
const saving = ref(false)
const subtasks = ref([])
const newSubtaskTitle = ref('')
const timeBlocks = ref([])
```

- [ ] **Step 3: `loadDetail` 里一并拉取时间块**

找到：

```js
const loadDetail = async () => {
  if (!props.todoId) return
  loading.value = true
  try {
    const [todoRes, subtaskRes] = await Promise.all([api.getTodoById(props.todoId), api.getSubtasks(props.todoId)])
    const todo = todoRes.data
    form.value = {
      title: todo.title,
      notes: todo.notes || '',
      project_id: todo.project_id,
      due_date: toDateValue(todo.due_date),
      reminder_at: toDateValue(todo.reminder_at),
      quadrant_type: todo.quadrant_type
    }
    subtasks.value = (subtaskRes.data || []).map((sub) => ({ ...sub, _originalTitle: sub.title }))
  } catch (error) {
    console.error('获取任务详情失败:', error)
    message.error('获取任务详情失败')
  } finally {
    loading.value = false
  }
}
```

改成：

```js
const loadDetail = async () => {
  if (!props.todoId) return
  loading.value = true
  try {
    const [todoRes, subtaskRes, timeBlockRes] = await Promise.all([
      api.getTodoById(props.todoId),
      api.getSubtasks(props.todoId),
      api.getTimeBlocks({ todo_item_id: props.todoId })
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
    subtasks.value = (subtaskRes.data || []).map((sub) => ({ ...sub, _originalTitle: sub.title }))
    timeBlocks.value = timeBlockRes.data || []
  } catch (error) {
    console.error('获取任务详情失败:', error)
    message.error('获取任务详情失败')
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 4: 新增格式化/删除方法**

找到 `addSubtask` 方法结束处（`</script>` 之前那一段）：

```js
const addSubtask = async () => {
  const title = newSubtaskTitle.value.trim()
  if (!title) return
  try {
    const res = await api.createSubtask({ todo_item_id: props.todoId, title })
    subtasks.value.push({ ...res.data, _originalTitle: res.data.title })
    newSubtaskTitle.value = ''
  } catch (error) {
    console.error('添加子任务失败:', error)
    message.error('添加子任务失败')
  }
}
</script>
```

改成：

```js
const addSubtask = async () => {
  const title = newSubtaskTitle.value.trim()
  if (!title) return
  try {
    const res = await api.createSubtask({ todo_item_id: props.todoId, title })
    subtasks.value.push({ ...res.data, _originalTitle: res.data.title })
    newSubtaskTitle.value = ''
  } catch (error) {
    console.error('添加子任务失败:', error)
    message.error('添加子任务失败')
  }
}

const formatTimeBlock = (block) => {
  const start = new Date(block.start_time)
  const end = new Date(block.end_time)
  const pad = (n) => String(n).padStart(2, '0')
  const dateLabel = `${start.getMonth() + 1}月${start.getDate()}日`
  const timeLabel = `${pad(start.getHours())}:${pad(start.getMinutes())}–${pad(end.getHours())}:${pad(end.getMinutes())}`
  return `${dateLabel} ${timeLabel}`
}

const removeTimeBlock = async (block) => {
  try {
    await api.deleteTimeBlock(block.id)
    timeBlocks.value = timeBlocks.value.filter((b) => b.id !== block.id)
  } catch (error) {
    console.error('删除时间块失败:', error)
    message.error('删除时间块失败')
  }
}
</script>
```

- [ ] **Step 5: 新增 CSS**

找到：

```css
<style scoped>
.subtask-row {
  display: flex;
  align-items: center;
  padding: 0.3em 0;
}
```

改成：

```css
<style scoped>
.subtask-row,
.timeblock-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.3em 0;
}
```

- [ ] **Step 6: lint 检查**

Run: `cd web && pnpm lint`
Expected: 无报错。

- [ ] **Step 7: 提交**

```bash
git add web/src/views/todo/TaskList/TaskDetailModal.vue
git commit -m "feat(web): show scheduled time blocks in TaskDetailModal"
```

---

## Task 7: `Schedule/index.vue` 页面壳 + 日/周切换

**Files:**
- Create: `web/src/views/todo/Schedule/index.vue`

**Interfaces:**
- Consumes：Task 6 的 `TaskDetailModal.vue`（原样复用，路径 `../TaskList/TaskDetailModal.vue`）、`api.getProjects()`。
- Produces：`viewMode` 切换容器，渲染 `WeekView`/`DayView`（Task 8/9 创建，此任务先占位）。这是 Menu 记录 `component="/todo/Schedule"` 指向的入口文件（对应 Task 4）。点击日历色块时触发的 `edit-todo` 事件在这里被消费，打开 `TaskDetailModal`。

- [ ] **Step 1: 先创建占位的 `WeekView.vue`/`DayView.vue`，让本任务可以独立跑起来**

`web/src/views/todo/Schedule/WeekView.vue`（占位，Task 8 会整体替换）：

```vue
<template>
  <div>周视图开发中</div>
</template>

<script setup>
import { defineExpose } from 'vue'

defineEmits(['edit-todo'])
defineExpose({ refresh: () => {} })
</script>
```

`web/src/views/todo/Schedule/DayView.vue`（占位，Task 9 会整体替换）：

```vue
<template>
  <div>日视图开发中</div>
</template>

<script setup>
import { defineExpose } from 'vue'

defineEmits(['edit-todo'])
defineExpose({ refresh: () => {} })
</script>
```

- [ ] **Step 2: 写 `web/src/views/todo/Schedule/index.vue`**

```vue
<template>
  <div class="schedule-page">
    <div class="schedule-view-toggle">
      <button class="toggle-btn" :class="{ active: viewMode === 'day' }" @click="viewMode = 'day'">日</button>
      <button class="toggle-btn" :class="{ active: viewMode === 'week' }" @click="viewMode = 'week'">周</button>
    </div>

    <WeekView v-if="viewMode === 'week'" ref="weekViewRef" @edit-todo="openDetail" />
    <DayView v-else ref="dayViewRef" @edit-todo="openDetail" />

    <TaskDetailModal
      v-model:show="detailShow"
      :todo-id="detailTodoId"
      :projects="projectList"
      @saved="handleTodoChanged"
      @deleted="handleTodoChanged"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/api'
import WeekView from './WeekView.vue'
import DayView from './DayView.vue'
import TaskDetailModal from '../TaskList/TaskDetailModal.vue'

const viewMode = ref('week')
const weekViewRef = ref(null)
const dayViewRef = ref(null)
const detailShow = ref(false)
const detailTodoId = ref(null)
const projectList = ref([])

const openDetail = (todoId) => {
  detailTodoId.value = todoId
  detailShow.value = true
}

const handleTodoChanged = () => {
  weekViewRef.value?.refresh()
  dayViewRef.value?.refresh()
}

onMounted(async () => {
  const res = await api.getProjects()
  projectList.value = res.data || []
})
</script>

<style scoped>
.schedule-view-toggle {
  display: flex;
  gap: 0.4em;
  margin-bottom: 1em;
}
.toggle-btn {
  padding: 0.4em 1em;
  border: 1px solid rgba(128, 128, 128, 0.3);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  color: inherit;
}
.toggle-btn.active {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
  border-color: #1890ff;
}
</style>
```

- [ ] **Step 3: lint 检查**

Run: `cd web && pnpm lint`
Expected: 无报错。

- [ ] **Step 4: 手动验证页面骨架能跑起来**

Run: `cd web && pnpm dev`，浏览器打开开发地址，登录后手动把地址栏改成 `<dev地址>/todo/schedule`（此时后端 Menu 表还没有这条记录，直接改地址栏访问路由本身不受菜单可见性限制，只要路由已经在 `web/src/router` 动态生成里存在——若打开是空白/404，说明还需要先跑一次 `python run.py` 让 Task 4 的菜单初始化逻辑生效，并让当前登录用户的角色拥有这条新菜单的可见权限，或直接用超级管理员账号 `admin`/`123456` 登录，超级管理员默认可见所有菜单）。

Expected: 能看到"日/周"切换按钮，切换后分别显示"周视图开发中"/"日视图开发中"占位文字。

- [ ] **Step 5: 提交**

```bash
git add web/src/views/todo/Schedule/index.vue web/src/views/todo/Schedule/WeekView.vue web/src/views/todo/Schedule/DayView.vue
git commit -m "feat(web): add Schedule page shell with day/week toggle"
```

---

## Task 8: `WeekView.vue` + `CreateTodoWithSlotsModal.vue`

**Files:**
- Modify: `web/src/views/todo/Schedule/WeekView.vue`（整体替换 Task 7 的占位内容）
- Create: `web/src/views/todo/Schedule/CreateTodoWithSlotsModal.vue`

**Interfaces:**
- Consumes：Task 5 的 `api.getTimeBlocks`、`api.createTodo`（透传 `time_blocks`）；Task 7 的 `edit-todo` 事件出口、`defineExpose({ refresh })` 约定。
- Produces：完整的周视图交互（对应 `public/design/schedule-week.html`）。`defineExpose({ refresh: fetchBlocks })` 供 Task 7 的 `index.vue` 在 `handleTodoChanged` 里调用。

- [ ] **Step 1: 写 `CreateTodoWithSlotsModal.vue`**

```vue
<template>
  <n-modal :show="show" preset="card" title="创建待办事项" style="width: 480px" @update:show="onUpdateShow">
    <n-form label-placement="left" label-width="70">
      <n-form-item label="标题">
        <n-input v-model:value="form.title" placeholder="要做什么？" />
      </n-form-item>
      <n-form-item label="象限">
        <n-radio-group v-model:value="form.quadrant_type">
          <n-space vertical>
            <n-radio v-for="opt in quadrantOptions" :key="opt.value" :value="opt.value">
              <span class="quadrant-dot" :style="{ background: opt.color }"></span>
              {{ opt.label }}
            </n-radio>
          </n-space>
        </n-radio-group>
      </n-form-item>
      <n-form-item label="备注">
        <n-input v-model:value="form.notes" type="textarea" :rows="2" placeholder="可选" />
      </n-form-item>
      <n-form-item label="已选时间段">
        <ul class="slot-list">
          <li v-for="(r, idx) in ranges" :key="idx">{{ formatRange(r) }}</li>
        </ul>
      </n-form-item>
    </n-form>
    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5em">
        <n-button @click="onUpdateShow(false)">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="handleSubmit">确定</n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false },
  ranges: { type: Array, default: () => [] } // [{ date: Date, start: Number(分钟), end: Number(分钟) }]
})
const emit = defineEmits(['update:show', 'created'])

const message = useMessage()
const submitting = ref(false)

const defaultForm = () => ({ title: '', quadrant_type: '', notes: '' })
const form = ref(defaultForm())

const quadrantOptions = [
  { label: '重要且紧急', value: 'urgent_important', color: '#f5222d' },
  { label: '紧急不重要', value: 'urgent_not_important', color: '#faad14' },
  { label: '重要不紧急', value: 'important_not_urgent', color: '#1890ff' },
  { label: '不紧急不重要', value: 'not_urgent_not_important', color: '#909399' }
]

const onUpdateShow = (value) => emit('update:show', value)

watch(
  () => props.show,
  (visible) => {
    if (visible) form.value = defaultForm()
  }
)

const pad = (n) => String(n).padStart(2, '0')
const formatMin = (min) => `${pad(Math.floor(min / 60))}:${pad(min % 60)}`
const formatRange = (r) => {
  const label = r.date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric', weekday: 'short' })
  return `${label} ${formatMin(r.start)}–${formatMin(r.end)}`
}

const minutesToDate = (baseDate, minutes) => {
  const d = new Date(baseDate)
  d.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0)
  return d
}

const handleSubmit = async () => {
  const title = form.value.title.trim()
  if (!title) {
    message.error('请输入标题')
    return
  }
  if (!form.value.quadrant_type) {
    message.error('请选择象限')
    return
  }
  submitting.value = true
  try {
    const payload = {
      title,
      quadrant_type: form.value.quadrant_type,
      notes: form.value.notes || null,
      time_blocks: props.ranges.map((r) => ({
        start_time: minutesToDate(r.date, r.start).toISOString(),
        end_time: minutesToDate(r.date, r.end).toISOString()
      }))
    }
    const res = await api.createTodo(payload)
    message.success('创建成功')
    emit('created', res.data)
    onUpdateShow(false)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.quadrant-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.4em;
}
.slot-list {
  font-size: 0.9em;
  opacity: 0.75;
  padding-left: 1.2em;
  margin: 0;
}
</style>
```

- [ ] **Step 2: 整体替换 `WeekView.vue`**

```vue
<template>
  <div class="week-view">
    <div class="schedule-toolbar">
      <button class="button" @click="shiftWeek(-1)">‹</button>
      <span class="week-label">{{ weekLabel }}</span>
      <button class="button" @click="shiftWeek(1)">›</button>
      <select v-model.number="granularity" class="form-control" @change="onGranularityChange">
        <option :value="15">15 分钟</option>
        <option :value="30">30 分钟</option>
        <option :value="60">1 小时</option>
      </select>
      <span class="mode-toggle">
        <button class="button" :class="{ active: mode === 'drag' }" @click="setMode('drag')">拖拽选择</button>
        <button class="button" :class="{ active: mode === 'multi' }" @click="setMode('multi')">多选格子</button>
      </span>
      <button v-if="mode === 'multi' && selected.size" class="button button-primary" @click="openCreateModal">
        完成选择
      </button>
      <button v-if="selected.size" class="button" @click="clearSelection">清空选择</button>
    </div>
    <div class="selection-summary">{{ selectionSummary }}</div>

    <div class="schedule-grid">
      <div class="time-gutter">
        <div class="day-head"></div>
        <div class="col-body">
          <div v-for="row in rowCount" :key="row" class="gutter-cell" :style="{ height: rowHeight + 'px' }">
            <span v-if="gutterLabel(row - 1)">{{ gutterLabel(row - 1) }}</span>
          </div>
        </div>
      </div>

      <div v-for="(day, dIdx) in weekDays" :key="dIdx" class="day-col" :class="{ today: isToday(day) }">
        <div class="day-head">{{ dayLabel(day) }}</div>
        <div
          class="col-body"
          :style="{ height: rowCount * rowHeight + 'px' }"
          @mousedown="onColumnMouseDown(dIdx, $event)"
          @mousemove="onColumnMouseMove(dIdx, $event)"
          @click="onColumnClick(dIdx, $event)"
        >
          <div
            v-for="row in rowCount"
            :key="row"
            class="slot-cell"
            :class="{ selected: isSelected(dIdx, (row - 1) * granularity), 'hour-end': isHourEnd(row - 1) }"
            :style="{ height: rowHeight + 'px' }"
          ></div>
          <div
            v-for="block in blocksForDay(dIdx)"
            :key="block.id"
            class="event-block"
            :style="eventBlockStyle(block)"
            :title="eventBlockTitle(block)"
            @click.stop="$emit('edit-todo', block.todo_item_id)"
          >
            {{ formatMin(block.startMin) }} {{ block.title }}
          </div>
          <div v-if="isToday(day)" class="now-line" :style="{ top: nowLineTop + 'px' }"></div>
        </div>
      </div>
    </div>

    <CreateTodoWithSlotsModal v-model:show="showCreateModal" :ranges="mergedRanges" @created="handleCreated" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '@/api'
import CreateTodoWithSlotsModal from './CreateTodoWithSlotsModal.vue'

defineEmits(['edit-todo'])

const QUADRANT_COLORS = {
  urgent_important: '#f5222d',
  urgent_not_important: '#faad14',
  important_not_urgent: '#1890ff',
  not_urgent_not_important: '#909399'
}

const granularity = ref(30)
const mode = ref('drag')
const selected = ref(new Set()) // "day-min"
const dragging = ref(false)
const dragDay = ref(null)
const dragAnchor = ref(null)
const showCreateModal = ref(false)
const rawBlocks = ref([])

const startOfWeek = (date) => {
  const d = new Date(date)
  const dow = (d.getDay() + 6) % 7 // 周一 = 0
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() - dow)
  return d
}

const weekStart = ref(startOfWeek(new Date()))

const weekDays = computed(() => {
  const days = []
  for (let i = 0; i < 7; i++) {
    const d = new Date(weekStart.value)
    d.setDate(d.getDate() + i)
    days.push(d)
  }
  return days
})

const weekLabel = computed(() => {
  const start = weekDays.value[0]
  const end = weekDays.value[6]
  const fmt = (d) => `${d.getMonth() + 1}月${d.getDate()}日`
  return `${start.getFullYear()}年 ${fmt(start)} - ${fmt(end)}`
})

const dayLabel = (date) => {
  const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const dow = (date.getDay() + 6) % 7
  return `${weekdays[dow]} ${date.getMonth() + 1}/${date.getDate()}`
}

const isToday = (date) => {
  const now = new Date()
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  )
}

const rowCount = computed(() => 1440 / granularity.value)
const rowHeight = computed(() => ({ 15: 16, 30: 26, 60: 44 })[granularity.value])
const isHourEnd = (rowIdx) => (rowIdx * granularity.value + granularity.value) % 60 === 0

const pad = (n) => String(n).padStart(2, '0')
const formatMin = (min) => `${pad(Math.floor(min / 60))}:${pad(min % 60)}`
const gutterLabel = (rowIdx) => {
  const min = rowIdx * granularity.value
  return min > 0 && min % 60 === 0 ? formatMin(min) : ''
}

const selectionKey = (day, min) => `${day}-${min}`
const isSelected = (day, min) => selected.value.has(selectionKey(day, min))

const mergedRanges = computed(() => {
  const byDay = new Map()
  selected.value.forEach((key) => {
    const [d, m] = key.split('-').map(Number)
    if (!byDay.has(d)) byDay.set(d, [])
    byDay.get(d).push(m)
  })
  const out = []
  Array.from(byDay.keys())
    .sort((a, b) => a - b)
    .forEach((d) => {
      const mins = byDay.get(d).sort((a, b) => a - b)
      let start = mins[0]
      let prev = mins[0]
      for (let i = 1; i <= mins.length; i++) {
        if (i === mins.length || mins[i] !== prev + granularity.value) {
          out.push({ date: weekDays.value[d], start, end: prev + granularity.value })
          start = mins[i]
        }
        prev = mins[i]
      }
    })
  return out
})

const selectionSummary = computed(() => {
  if (selected.value.size === 0) return ''
  const hours = ((selected.value.size * granularity.value) / 60).toFixed(2).replace(/\.?0+$/, '')
  return `已选 ${mergedRanges.value.length} 个时间段，合计 ${hours} 小时`
})

const clearSelection = () => {
  selected.value = new Set()
}

const setMode = (next) => {
  mode.value = next
  clearSelection()
}

const onGranularityChange = () => {
  clearSelection()
}

const applyDragRange = (day, cur) => {
  const lo = Math.min(dragAnchor.value, cur)
  const hi = Math.max(dragAnchor.value, cur)
  const next = new Set()
  for (let m = lo; m <= hi; m += granularity.value) next.add(selectionKey(day, m))
  selected.value = next
}

const minuteFromEvent = (evt) => {
  const rect = evt.currentTarget.getBoundingClientRect()
  const offsetY = evt.clientY - rect.top
  const row = Math.max(0, Math.min(rowCount.value - 1, Math.floor(offsetY / rowHeight.value)))
  return row * granularity.value
}

const onColumnMouseDown = (day, evt) => {
  if (mode.value !== 'drag') return
  dragging.value = true
  dragDay.value = day
  dragAnchor.value = minuteFromEvent(evt)
  applyDragRange(day, dragAnchor.value)
}

const onColumnMouseMove = (day, evt) => {
  if (!dragging.value || mode.value !== 'drag' || day !== dragDay.value) return
  applyDragRange(day, minuteFromEvent(evt))
}

const onColumnClick = (day, evt) => {
  if (mode.value !== 'multi') return
  const min = minuteFromEvent(evt)
  const key = selectionKey(day, min)
  const next = new Set(selected.value)
  next.has(key) ? next.delete(key) : next.add(key)
  selected.value = next
}

const stopDragging = () => {
  if (!dragging.value) return
  dragging.value = false
  if (selected.value.size) openCreateModal()
}

const openCreateModal = () => {
  showCreateModal.value = true
}

const handleCreated = () => {
  clearSelection()
  fetchBlocks()
}

const blocksForDay = (dIdx) => {
  const dayKey = weekDays.value[dIdx].toDateString()
  return rawBlocks.value
    .filter((b) => new Date(b.start_time).toDateString() === dayKey)
    .map((b) => {
      const start = new Date(b.start_time)
      const end = new Date(b.end_time)
      return {
        id: b.id,
        todo_item_id: b.todo_item_id,
        title: b.title,
        quadrant_type: b.quadrant_type,
        startMin: start.getHours() * 60 + start.getMinutes(),
        endMin: end.getHours() * 60 + end.getMinutes()
      }
    })
}

const eventBlockStyle = (block) => ({
  top: `${(block.startMin * rowHeight.value) / granularity.value}px`,
  height: `${((block.endMin - block.startMin) * rowHeight.value) / granularity.value - 2}px`,
  backgroundColor: QUADRANT_COLORS[block.quadrant_type] || '#909399'
})

const eventBlockTitle = (block) => `${block.title} ${formatMin(block.startMin)}–${formatMin(block.endMin)}`

const nowLineTop = computed(() => {
  const now = new Date()
  const min = now.getHours() * 60 + now.getMinutes()
  return (min * rowHeight.value) / granularity.value
})

const shiftWeek = (delta) => {
  const d = new Date(weekStart.value)
  d.setDate(d.getDate() + delta * 7)
  weekStart.value = d
  fetchBlocks()
}

const fetchBlocks = async () => {
  const start = weekDays.value[0]
  const end = weekDays.value[6]
  const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  const res = await api.getTimeBlocks({ start_date: fmt(start), end_date: fmt(end) })
  rawBlocks.value = res.data || []
}

defineExpose({ refresh: fetchBlocks })

onMounted(() => {
  document.addEventListener('mouseup', stopDragging)
  document.addEventListener('mouseleave', stopDragging)
  fetchBlocks()
})

onUnmounted(() => {
  document.removeEventListener('mouseup', stopDragging)
  document.removeEventListener('mouseleave', stopDragging)
})
</script>

<style scoped>
.schedule-toolbar {
  display: flex;
  align-items: center;
  gap: 0.8em;
  margin-bottom: 0.8em;
  flex-wrap: wrap;
}
.week-label {
  font-size: 1.1em;
  font-weight: 500;
}
.button {
  padding: 0.4em 0.9em;
  border: 1px solid rgba(128, 128, 128, 0.3);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  color: inherit;
}
.form-control {
  padding: 0.4em 0.6em;
  border: 1px solid rgba(128, 128, 128, 0.3);
  border-radius: 4px;
  background: transparent;
  color: inherit;
}
.mode-toggle .button.active,
.button-primary {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
  border-color: #1890ff;
}
.selection-summary {
  min-height: 1.5em;
  margin-bottom: 0.6em;
  font-size: 0.9em;
  opacity: 0.7;
}
.schedule-grid {
  display: flex;
  border: 1px solid rgba(128, 128, 128, 0.3);
  user-select: none;
}
.time-gutter {
  width: 56px;
  flex-shrink: 0;
  border-right: 1px solid rgba(128, 128, 128, 0.3);
}
.day-col {
  flex: 1;
  min-width: 0;
  border-right: 1px solid rgba(128, 128, 128, 0.15);
}
.day-col:last-child {
  border-right: none;
}
.day-head {
  height: 2.2em;
  line-height: 2.2em;
  text-align: center;
  font-size: 0.88em;
  font-weight: 500;
  border-bottom: 1px solid rgba(128, 128, 128, 0.3);
  white-space: nowrap;
  overflow: hidden;
}
.day-col.today .day-head {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
}
.col-body {
  position: relative;
}
.slot-cell {
  border-bottom: 1px dashed rgba(128, 128, 128, 0.15);
  box-sizing: border-box;
}
.slot-cell.hour-end {
  border-bottom: 1px solid rgba(128, 128, 128, 0.3);
}
.slot-cell:hover {
  background: rgba(128, 128, 128, 0.08);
}
.slot-cell.selected {
  background: rgba(24, 144, 255, 0.12);
  box-shadow: inset 0 0 0 1px #1890ff;
}
.gutter-cell {
  position: relative;
  box-sizing: border-box;
}
.gutter-cell span {
  position: absolute;
  top: -0.55em;
  right: 6px;
  font-size: 0.72em;
  opacity: 0.6;
}
.now-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: #f5222d;
  z-index: 3;
  pointer-events: none;
}
.event-block {
  position: absolute;
  left: 2px;
  right: 2px;
  border-radius: 4px;
  padding: 1px 4px;
  font-size: 0.76em;
  color: #fff;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  z-index: 2;
  box-sizing: border-box;
  cursor: pointer;
}
</style>
```

关键点：拖拽/多选/点击的鼠标事件挂在 `.col-body`（每天一整列）上而不是每个 `.slot-cell` 上，用 `getBoundingClientRect()` + `clientY` 算出所在的分钟数——这是为了修掉 mockup 评审时记录的已知问题（事件块盖住格子后，挂在格子上的 `mouseover` 侦测不到，导致拖拽选区在色块处断掉）；列级委托后，不管鼠标当前压在空白格子还是已有色块上，`.col-body` 的 `mousemove`/`mousedown`/`click` 始终能拿到正确的坐标。

- [ ] **Step 3: lint 检查**

Run: `cd web && pnpm lint`
Expected: 无报错。

- [ ] **Step 4: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开开发地址，导航到日历页（默认周视图）。

验证清单：
- 切换 15/30/60 分钟粒度，网格重新渲染，行高变化。
- 拖拽模式下，在某一天列内按下鼠标拖动，能连续选中一段时间（跨到相邻列不生效），松开后弹出"创建待办事项"弹窗，"已选时间段"里显示正确的日期+时间范围。
- 多选模式下，可以在不同天分别点选多个不连续格子，点击"完成选择"弹出同一个创建弹窗，"已选时间段"按天分组列出多段。
- 填写标题+选象限后点"确定"，网格上对应位置出现按象限配色的色块；刷新页面后色块仍在（说明真的写进了后端）。
- 点击已有色块，打开 `TaskDetailModal`，"已排程时间"小节能看到对应记录。
- 点"‹"/"›"切换到前后一周，网格显示对应周的色块（没有的周应该是空网格）。

Expected: 以上行为均符合预期，浏览器控制台无报错。

- [ ] **Step 5: 提交**

```bash
git add web/src/views/todo/Schedule/WeekView.vue web/src/views/todo/Schedule/CreateTodoWithSlotsModal.vue
git commit -m "feat(web): implement WeekView drag/multi-select scheduling"
```

---

## Task 9: `DayView.vue`

**Files:**
- Modify: `web/src/views/todo/Schedule/DayView.vue`（整体替换 Task 7 的占位内容）

**Interfaces:**
- Consumes：Task 5 的 `api.getTimeBlocks`、`api.createTimeBlock`；`api.getTodos({ unscheduled_only: true })`（Task 3 扩展）。
- Produces：完整的日视图交互（对应 `public/design/calendar-day.html`）。`defineExpose({ refresh: fetchAll })` 供 Task 7 的 `index.vue` 在 `handleTodoChanged` 里调用。

- [ ] **Step 1: 整体替换 `DayView.vue`**

```vue
<template>
  <div class="day-view">
    <div class="calendar-controls">
      <button class="button" @click="shiftDay(-1)">‹</button>
      <span>{{ dateLabel }}</span>
      <button class="button" @click="shiftDay(1)">›</button>
      <input type="date" class="form-control" :value="dateInputValue" @change="onDateInput" />
    </div>

    <div
      class="day-timeline"
      :style="{ height: 24 * HOUR_PX + 'px' }"
      @dragover.prevent="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
    >
      <div v-for="hh in 24" :key="hh" class="hour-slot" :class="{ 'drop-hint': dropHintHour === hh - 1 }">
        <span class="hour-label">{{ pad(hh - 1) }}:00</span>
      </div>
      <div
        v-for="block in blocks"
        :key="block.id"
        class="day-event"
        :style="eventStyle(block)"
        :title="eventTitle(block)"
        @click="$emit('edit-todo', block.todo_item_id)"
      >
        <strong>{{ formatMin(block.startMin) }}</strong> {{ block.title }}
      </div>
      <div v-if="nowLineTop >= 0" class="now-line" :style="{ top: nowLineTop + 'px' }"></div>
    </div>

    <section class="unscheduled-section">
      <h3>未安排的任务（拖到时间轴上排程）</h3>
      <ul class="task-list">
        <li
          v-for="todo in unscheduledTodos"
          :key="todo.id"
          class="unscheduled-item"
          draggable="true"
          @dragstart="onDragStart(todo, $event)"
          @dragend="onDragEnd"
        >
          <span class="quadrant-dot" :style="{ background: quadrantColor(todo.quadrant_type) }"></span>
          {{ todo.title }}
          <span class="task-meta">{{ dueLabel(todo) }}</span>
        </li>
      </ul>
      <n-empty v-if="!unscheduledTodos.length" description="没有未安排的任务" />
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/api'

defineEmits(['edit-todo'])

const HOUR_PX = 48
const QUADRANT_COLORS = {
  urgent_important: '#f5222d',
  urgent_not_important: '#faad14',
  important_not_urgent: '#1890ff',
  not_urgent_not_important: '#909399'
}

function startOfDay(date) {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  return d
}

const currentDate = ref(startOfDay(new Date()))
const rawBlocks = ref([])
const unscheduledTodos = ref([])
const dragged = ref(null)
const dropHintHour = ref(null)

const pad = (n) => String(n).padStart(2, '0')
const formatMin = (min) => `${pad(Math.floor(min / 60))}:${pad(min % 60)}`

const dateLabel = computed(() => {
  const d = currentDate.value
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日, ${weekdays[d.getDay()]}`
})

const dateInputValue = computed(() => {
  const d = currentDate.value
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
})

const quadrantColor = (type) => QUADRANT_COLORS[type] || '#909399'

const dueLabel = (todo) => {
  if (!todo.due_date) return '无截止时间'
  const due = new Date(todo.due_date)
  const today = startOfDay(new Date())
  if (startOfDay(due).getTime() === today.getTime()) return '今天截止'
  return `${due.getMonth() + 1}月${due.getDate()}日截止`
}

const blocks = computed(() =>
  rawBlocks.value.map((b) => {
    const start = new Date(b.start_time)
    const end = new Date(b.end_time)
    return {
      id: b.id,
      todo_item_id: b.todo_item_id,
      title: b.title,
      quadrant_type: b.quadrant_type,
      startMin: start.getHours() * 60 + start.getMinutes(),
      endMin: end.getHours() * 60 + end.getMinutes()
    }
  })
)

const eventStyle = (block) => ({
  top: `${(block.startMin / 60) * HOUR_PX}px`,
  height: `${((block.endMin - block.startMin) / 60) * HOUR_PX - 2}px`,
  backgroundColor: QUADRANT_COLORS[block.quadrant_type] || '#909399'
})
const eventTitle = (block) => `${block.title} ${formatMin(block.startMin)}–${formatMin(block.endMin)}`

const nowLineTop = computed(() => {
  const now = new Date()
  if (startOfDay(now).getTime() !== currentDate.value.getTime()) return -100
  return ((now.getHours() * 60 + now.getMinutes()) / 60) * HOUR_PX
})

const shiftDay = (delta) => {
  const d = new Date(currentDate.value)
  d.setDate(d.getDate() + delta)
  currentDate.value = d
  fetchAll()
}

const onDateInput = (evt) => {
  const [y, m, day] = evt.target.value.split('-').map(Number)
  currentDate.value = new Date(y, m - 1, day)
  fetchAll()
}

const onDragStart = (todo, evt) => {
  dragged.value = todo
  evt.dataTransfer.effectAllowed = 'move'
}

const onDragOver = (evt) => {
  if (!dragged.value) return
  const rect = evt.currentTarget.getBoundingClientRect()
  const y = evt.clientY - rect.top
  dropHintHour.value = Math.max(0, Math.min(23, Math.floor(y / HOUR_PX)))
}

const onDragLeave = () => {
  dropHintHour.value = null
}

const onDragEnd = () => {
  // 兜底清理：拖拽被取消（松手在时间轴之外、按 Esc 等）时 drop 不会触发，
  // 但 dragend 总会触发，避免 dragged 状态残留到下一次拖拽
  dragged.value = null
  dropHintHour.value = null
}

const onDrop = async (evt) => {
  dropHintHour.value = null
  if (!dragged.value) return
  const rect = evt.currentTarget.getBoundingClientRect()
  const y = evt.clientY - rect.top
  let startMin = Math.floor(y / (HOUR_PX / 2)) * 30 // 30 分钟吸附
  startMin = Math.max(0, Math.min(1380, startMin)) // 钳制到 23:00，避免跨零点
  const endMinRaw = startMin + 60

  const start = new Date(currentDate.value)
  start.setHours(0, startMin, 0, 0)
  const end = new Date(currentDate.value)
  if (endMinRaw >= 1440) {
    end.setHours(23, 59, 59, 999)
  } else {
    end.setHours(0, endMinRaw, 0, 0)
  }

  const todo = dragged.value
  dragged.value = null
  try {
    await api.createTimeBlock({
      todo_item_id: todo.id,
      start_time: start.toISOString(),
      end_time: end.toISOString()
    })
    await fetchAll()
  } catch (error) {
    console.error('创建时间块失败:', error)
  }
}

const fetchBlocks = async () => {
  const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  const res = await api.getTimeBlocks({ start_date: fmt(currentDate.value), end_date: fmt(currentDate.value) })
  rawBlocks.value = res.data || []
}

const fetchUnscheduled = async () => {
  const res = await api.getTodos({ unscheduled_only: true, page: 1, page_size: 200 })
  unscheduledTodos.value = res.data || []
}

const fetchAll = () => Promise.all([fetchBlocks(), fetchUnscheduled()])

defineExpose({ refresh: fetchAll })

onMounted(fetchAll)
</script>

<style scoped>
.calendar-controls {
  display: flex;
  align-items: center;
  gap: 0.8em;
  margin-bottom: 0.8em;
}
.button {
  padding: 0.4em 0.9em;
  border: 1px solid rgba(128, 128, 128, 0.3);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  color: inherit;
}
.form-control {
  padding: 0.4em 0.6em;
  border: 1px solid rgba(128, 128, 128, 0.3);
  border-radius: 4px;
  background: transparent;
  color: inherit;
}
.day-timeline {
  position: relative;
  border: 1px solid rgba(128, 128, 128, 0.3);
  user-select: none;
}
.hour-slot {
  height: 48px;
  border-bottom: 1px solid rgba(128, 128, 128, 0.15);
  position: relative;
  box-sizing: border-box;
}
.hour-slot.drop-hint {
  background: rgba(24, 144, 255, 0.12);
}
.hour-label {
  position: absolute;
  left: 6px;
  top: -0.55em;
  font-size: 0.75em;
  opacity: 0.6;
}
.day-event {
  position: absolute;
  left: 56px;
  right: 10px;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 0.85em;
  color: #fff;
  overflow: hidden;
  z-index: 2;
  box-sizing: border-box;
  cursor: pointer;
}
.now-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: #f5222d;
  z-index: 3;
  pointer-events: none;
}
.unscheduled-section {
  margin-top: 2em;
}
.unscheduled-section h3 {
  font-size: 1em;
  margin-bottom: 0.6em;
}
.task-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.unscheduled-item {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.5em 0.2em;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
  cursor: grab;
}
.unscheduled-item:active {
  cursor: grabbing;
}
.quadrant-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.task-meta {
  margin-left: auto;
  font-size: 0.8em;
  opacity: 0.6;
}
</style>
```

关键点：`startMin` 钳制到 `[0, 1380]`（最晚 23:00 起排），且当 `startMin + 60 >= 1440` 时把结束时间显式设为当天 `23:59:59` 而不是让 `setHours` 进位到次日 `00:00`——这是 mockup 评审记录的"拖到 23:30 之后生成越过午夜的事件块"问题的修法，同时也满足后端 `end_time`/`start_time` 必须同一天的校验（Task 2）。

- [ ] **Step 2: lint 检查**

Run: `cd web && pnpm lint`
Expected: 无报错。

- [ ] **Step 3: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开开发地址，导航到日历页，切到日视图。

验证清单：
- 底部"未安排的任务"面板只显示无时间块的未完成任务（可以先去任务列表页新建一个任务、不排程，确认它出现在这里；再去周视图给它排个时间块，回日视图确认它从面板消失）。
- 把面板里的任务拖到时间轴的某个小时格子上，松手后对应位置出现色块，任务从面板移除；刷新页面色块仍在。
- 把任务拖到接近 23:30 的位置，生成的色块不应跨越到第二天（用浏览器开发者工具或直接检查 network 面板里 `/timeblock/create` 请求体的 `start_time`/`end_time` 日期部分一致）。
- 点击已有色块，打开 `TaskDetailModal`。
- 用日期选择器/"‹""›"切换到其它日期，时间轴和面板数据相应更新。
- 当前日期是今天时，时间轴上有一条红色"现在"参考线；切到其它日期后这条线消失。
- 拖起一个未安排任务后，在时间轴之外的地方松手（取消这次拖拽），再重新拖拽同一个任务到时间轴上，能正常排程（验证 `dragend` 兜底清理生效，没有残留上一次的拖拽状态）。

Expected: 以上行为均符合预期，浏览器控制台无报错。

- [ ] **Step 4: 提交**

```bash
git add web/src/views/todo/Schedule/DayView.vue
git commit -m "feat(web): implement DayView drag-to-schedule from unscheduled panel"
```

---

## Task 10: 端到端验证 + 收尾

**Files:**
- 无新增/修改文件（除非验证中发现问题，需要回到对应 Task 修复）。

**Interfaces:**
- Consumes：全部前序 Task 的产出。
- Produces：无——本任务是对整个二期功能的最终确认，对照 `docs/superpowers/specs/2026-08-08-task-system-phase2-design.md` 的验收标准逐条过一遍。

- [ ] **Step 1: 跑全量后端测试**

Run: `pytest -vv`
Expected: 全部通过（含一期遗留测试 + 本期新增的 `test_timeblock.py` 及 `test_todo_list_extension.py` 新增用例）。

- [ ] **Step 2: 跑前端 lint**

Run: `cd web && pnpm lint`
Expected: 无报错。

- [ ] **Step 3: 用管理后台把新增 API 分配给角色**

启动后端（`python run.py`）后，用 `admin`/`123456` 登录管理后台，进入"系统管理 → API 管理"点击"刷新 API"（对应 `POST /api/v1/api/refresh`），确认新增的 `/api/v1/timeblock/*` 三个接口和 `/api/v1/todo/list`/`/api/v1/todo/create` 出现在列表里；进入"角色管理"，把这些接口分配给测试要用的角色（超级管理员本身会跳过 API 校验，不受影响；如果只用超级管理员账号验证可跳过这步）。

- [ ] **Step 4: 浏览器端到端走查，对照 spec 验收标准**

Run: `cd web && pnpm dev`，浏览器登录后依次验证 `docs/superpowers/specs/2026-08-08-task-system-phase2-design.md` 的"验收标准"一节：

- "待办事项"菜单下能看到"日历"入口，进入后默认周视图，可切换到日视图。
- 周视图粒度切换、拖拽/多选选时间段、创建待办后色块正确出现（含跨天多段的情况）。
- 日视图"未安排的任务"面板筛选正确，拖拽排程后色块正确出现，23:30 之后的边界不产生跨零点时间块。
- 点击任一视图的色块能打开 `TaskDetailModal`，"已排程时间"小节列出全部时间块，删除后色块消失、其余时间块不受影响。
- 删除任务后其所有时间块级联消失，日历页刷新后色块全部清空。

Expected: 全部符合预期。若发现偏差，回到对应 Task 定位问题、修复、重新跑一遍该 Task 的测试/验证步骤，再继续。

- [ ] **Step 5: 如果验证过程中做了修复，提交**

```bash
git add -A
git commit -m "fix: address issues found during phase2 end-to-end verification"
```

（如果 Step 4 全部一次通过、没有任何修改，跳过本步。）
