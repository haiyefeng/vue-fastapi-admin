# 三期（上）：习惯打卡 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 `docs/superpowers/specs/2026-08-10-task-system-phase3-habit-design.md` 描述的习惯打卡子系统：新增 `Habit` 模型 + 惰性生成算法，`TodoItem` 增加 `habit`/`generated_date` 字段，交付习惯页（列表 + 归档区块 + 今日打卡 + 新建编辑弹窗），并让一期已有的统计接口排除习惯待办。

**Architecture:** 后端沿用 `app/api/v1/subtask`/`app/api/v1/timeblock` 现有的扁平 `/list /create /update /delete` 路由风格 + `CRUDBase` 继承模式，新增 `habit` 资源模块；核心复杂度在 `HabitController` 内的惰性生成/连续天数/本周进度计算，只在 `GET /habit/list` 里触发，不改动一期的 `/todo/list`。前端新增 `web/src/views/todo/Habit/`（`index.vue` 页面壳 + `HabitFormModal.vue` 新建编辑弹窗），由新的 Menu 记录驱动路由，复用一期/二期已建立的交互模式（`ProjectNav.vue` 的归档折叠区块、`TaskDetailModal.vue` 的象限单选样式、`NewProjectModal.vue` 的颜色选择器）。先后端（含 pytest 单测）后前端。

**Tech Stack:** FastAPI + Tortoise ORM（后端），Vue 3 `<script setup>` + Naive UI（前端），pytest + pytest-asyncio + httpx（后端测试，沿用一期搭好的 `tests/conftest.py`）。

## Global Constraints

- 路由风格：`/list` `/create` `/update` `/delete`（+ `/archived` 这个专用查询端点）+ query 参数，不做嵌套 REST，路由文件放在 `app/api/v1/<resource>/route.py` + `__init__.py`。
- 所有新路由挂 `dependencies=[DependPermission]`；处理函数内部用 `Depends(AuthControl.is_authed)` 取当前用户，所有查询按 `user_id` 过滤，不做细粒度 RBAC（沿用 `todos`/`subtask`/`timeblock` 模块现状）。
- 象限配色（前端展示用）：`urgent_important` = `#f5222d`，`urgent_not_important` = `#faad14`，`important_not_urgent` = `#1890ff`，`not_urgent_not_important` = `#909399`。
- 惰性生成只在 `GET /habit/list` 里触发，不改动 `/todo/list`；`(habit_id, generated_date)` 幂等判断走应用层"生成前先查"，不建数据库唯一约束。
- 不做：计划目标（`Goal`、`goal_id` 关联）——留给三期（下）单独一轮 spec/plan。习惯详情的打卡历史图表（无落地页面，YAGNI）。习惯拖拽排序。弹性型习惯的"连续 N 周"统计（本阶段弹性型只做"本周 x/y"进度）。
- 后端每个任务遵循"写测试→跑测试确认现象→写实现→跑测试确认通过→提交"的顺序，复用 `tests/conftest.py` 的三个 fixture（`db`/`test_user`/`client`），不重新声明。日期相关测试一律用相对当前日期计算（`date.today()` 及其偏移），不写死具体日期，避免测试跑在不同的星期几时行为不一致。前端本仓库未配置测试运行器（`pnpm lint`/`pnpm exec eslint` 是唯一自动化检查），前端任务改为"实现→`pnpm exec eslint` 检查改动文件→提交"，最终 Task 9 做一次端到端确认。

---

## Task 1: Habit 模型 + TodoItem 增量字段

**Files:**
- Modify: `app/models/todo.py`
- Modify: `app/models/__init__.py`

**Interfaces:**
- Produces：`app.models.todo.Habit`（字段：`user`、`name`、`icon`、`color_hex`、`frequency_type`、`frequency_config`、`default_quadrant`、`goal_desc`、`reminder_time`、`is_paused`、`is_archived`）、`app.models.todo.HabitFrequencyType`（枚举 `DAILY`/`WEEKLY_DAYS`/`WEEKLY_COUNT`/`INTERVAL_DAYS`）；`TodoItem.habit`（FK→Habit，可空，`on_delete=CASCADE`，`related_name="todos"`）、`TodoItem.generated_date`（可空 DateField）。这些是 Task 2/3/4 的直接依赖。

- [ ] **Step 1: 修改 `app/models/todo.py`，在 `TodoItem` 类里 `reminder_at` 字段后面新增两行**

```python
    reminder_at = fields.DatetimeField(null=True, description="提醒时间，仅存储与展示，不做推送")
    habit = fields.ForeignKeyField(
        "models.Habit", related_name="todos", null=True, on_delete=fields.CASCADE,
        description="所属习惯，非空表示是习惯生成的打卡待办",
    )
    generated_date = fields.DateField(
        null=True,
        description="习惯待办的所属日期，仅习惯生成的待办有值；用于幂等判断，与用户可改的 due_date 语义分离",
    )
```

- [ ] **Step 2: 在文件末尾（`TimeBlock` 类之后）新增 `HabitFrequencyType` 和 `Habit`**

```python
class HabitFrequencyType(StrEnum):
    DAILY = "daily"
    WEEKLY_DAYS = "weekly_days"  # 每周固定几天，如周一三五
    WEEKLY_COUNT = "weekly_count"  # 每周任意 N 次（弹性型）
    INTERVAL_DAYS = "interval_days"  # 每隔 N 天一次


class Habit(BaseModel, TimestampMixin):
    """习惯模型：按频率规则惰性生成带 habit_id 的 TodoItem，勾掉即打卡"""

    user = fields.ForeignKeyField("models.User", related_name="habits", description="所属用户")
    name = fields.CharField(max_length=100, description="习惯名称")
    icon = fields.CharField(max_length=50, null=True, description="图标，emoji 或简短文本")
    color_hex = fields.CharField(max_length=7, null=True, description="颜色代码")
    frequency_type = fields.CharEnumField(HabitFrequencyType, description="频率类型")
    frequency_config = fields.JSONField(
        null=True,
        description=(
            'weekly_days: {"days": [1,3,5]}（ISO 星期一=1）；'
            'weekly_count: {"count": 3}；interval_days: {"interval": 2}；daily 不需要配置'
        ),
    )
    default_quadrant = fields.CharEnumField(
        QuadrantType, default=QuadrantType.IMPORTANT_NOT_URGENT, description="生成待办的默认象限"
    )
    goal_desc = fields.CharField(max_length=100, null=True, description="目标描述，如'30分钟'，仅展示")
    reminder_time = fields.TimeField(null=True, description="每日提醒时间，写入生成待办的 reminder_at")
    is_paused = fields.BooleanField(default=False, description="暂停后停止生成新待办，历史保留")
    is_archived = fields.BooleanField(default=False, description="归档后从主列表隐藏，历史保留")

    class Meta:
        table = "habit"

    def __str__(self):
        return self.name
```

- [ ] **Step 3: 修改 `app/models/__init__.py`**

```python
# 新增model需要在这里导入
from .admin import *
from .todo import Category, Habit, HabitFrequencyType, Project, QuadrantType, SubTask, TimeBlock, TodoItem
```

- [ ] **Step 4: 跑一次冒烟测试确认模型改动没有语法/引用错误**

Run: `pytest tests/test_smoke.py -vv`
Expected: `1 passed`。

- [ ] **Step 5: 生成并应用 aerich 迁移**

Run: `python run.py`（等到控制台打出启动完成的日志后 Ctrl+C 停掉）
Expected: 无报错退出；若报连接数据库失败，说明当前生效的数据库连接配置在本机不可达，需要先配好本地可访问的数据库再继续。

- [ ] **Step 6: 提交**

```bash
git add app/models/todo.py app/models/__init__.py
git commit -m "feat: add Habit model and TodoItem.habit/generated_date fields"
```

---

## Task 2: Habit CRUD 资源接口

**Files:**
- Create: `app/schemas/habit.py`
- Create: `app/controllers/habit.py`
- Create: `app/api/v1/habit/__init__.py`
- Create: `app/api/v1/habit/route.py`
- Modify: `app/api/v1/__init__.py`
- Create: `tests/test_habit.py`

**Interfaces:**
- Consumes：Task 1 的 `Habit`/`HabitFrequencyType` 模型。
- Produces：`app.controllers.habit.habit_controller`（方法 `create_habit(obj_in, user_id) -> Habit`，`frequency_config` 校验失败抛 `HTTPException(400)`；`update_habit(habit_id, obj_in, user_id) -> Optional[Habit]`；`delete_habit(habit_id, user_id) -> bool`；`get_archived_habits(user_id) -> List[Habit]`）。本任务先不实现生成/统计相关方法（`list_active_with_status`），那是 Task 3 的产出——本任务的 `GET /habit/list` 先返回不含生成检查的简单列表，Task 3 会整体替换这个路由处理函数的实现（但不改路径/方法）。

- [ ] **Step 1: 写测试（先写，此时对应路由还不存在，预期 404）**

```python
# tests/test_habit.py
from app.models.todo import Habit, HabitFrequencyType


async def test_create_daily_habit(client, test_user):
    resp = await client.post(
        "/api/v1/habit/create",
        json={"name": "晨间阅读", "frequency_type": "daily"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "晨间阅读"
    assert data["frequency_type"] == "daily"
    assert data["is_paused"] is False
    assert data["is_archived"] is False


async def test_create_weekly_days_habit_with_valid_config(client):
    resp = await client.post(
        "/api/v1/habit/create",
        json={"name": "健身", "frequency_type": "weekly_days", "frequency_config": {"days": [1, 3, 5]}},
    )
    assert resp.status_code == 200


async def test_create_weekly_days_habit_without_days_returns_400(client):
    resp = await client.post(
        "/api/v1/habit/create",
        json={"name": "健身", "frequency_type": "weekly_days"},
    )
    assert resp.status_code == 400


async def test_create_weekly_count_habit_without_count_returns_400(client):
    resp = await client.post(
        "/api/v1/habit/create",
        json={"name": "运动", "frequency_type": "weekly_count"},
    )
    assert resp.status_code == 400


async def test_create_interval_days_habit_without_interval_returns_400(client):
    resp = await client.post(
        "/api/v1/habit/create",
        json={"name": "打扫", "frequency_type": "interval_days"},
    )
    assert resp.status_code == 400


async def test_update_habit_can_pause_and_archive(client, test_user):
    create_resp = await client.post("/api/v1/habit/create", json={"name": "喝水", "frequency_type": "daily"})
    habit_id = create_resp.json()["data"]["id"]

    resp = await client.post("/api/v1/habit/update", json={"id": habit_id, "is_paused": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["is_paused"] is True

    resp = await client.post("/api/v1/habit/update", json={"id": habit_id, "is_archived": True})
    assert resp.json()["data"]["is_archived"] is True


async def test_update_habit_changing_frequency_type_revalidates_config(client):
    create_resp = await client.post("/api/v1/habit/create", json={"name": "喝水", "frequency_type": "daily"})
    habit_id = create_resp.json()["data"]["id"]

    resp = await client.post(
        "/api/v1/habit/update", json={"id": habit_id, "frequency_type": "weekly_count"}
    )
    assert resp.status_code == 400


async def test_delete_habit(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="待删除", frequency_type=HabitFrequencyType.DAILY)
    resp = await client.delete("/api/v1/habit/delete", params={"habit_id": habit.id})
    assert resp.status_code == 200
    assert await Habit.filter(id=habit.id).count() == 0


async def test_delete_nonexistent_habit_returns_404(client):
    resp = await client.delete("/api/v1/habit/delete", params={"habit_id": 99999})
    assert resp.status_code == 404


async def test_list_archived_habits(client, test_user):
    await Habit.create(
        user_id=test_user.id, name="已归档", frequency_type=HabitFrequencyType.DAILY, is_archived=True
    )
    await Habit.create(user_id=test_user.id, name="进行中", frequency_type=HabitFrequencyType.DAILY)

    resp = await client.get("/api/v1/habit/archived")
    names = [h["name"] for h in resp.json()["data"]]
    assert names == ["已归档"]


async def test_update_habit_owned_by_other_user_returns_404(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_habit = await Habit.create(user_id=other_user.id, name="别人的习惯", frequency_type=HabitFrequencyType.DAILY)

    resp = await client.post("/api/v1/habit/update", json={"id": other_habit.id, "is_paused": True})
    assert resp.status_code == 404


async def test_delete_habit_owned_by_other_user_returns_404(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_habit = await Habit.create(user_id=other_user.id, name="别人的习惯", frequency_type=HabitFrequencyType.DAILY)

    resp = await client.delete("/api/v1/habit/delete", params={"habit_id": other_habit.id})
    assert resp.status_code == 404
    assert await Habit.filter(id=other_habit.id).count() == 1
```

- [ ] **Step 2: 跑测试确认现象**

Run: `pytest tests/test_habit.py -vv`
Expected: 全部失败（`404 Not Found`，因为 `/api/v1/habit/*` 还没注册）。

- [ ] **Step 3: 写 `app/schemas/habit.py`**

```python
from datetime import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.models.todo import HabitFrequencyType, QuadrantType


class HabitCreate(BaseModel):
    name: str = Field(..., description="习惯名称")
    icon: Optional[str] = Field(None, description="图标，emoji 或简短文本")
    color_hex: Optional[str] = Field(None, description="颜色代码")
    frequency_type: HabitFrequencyType = Field(..., description="频率类型")
    frequency_config: Optional[Dict[str, Any]] = Field(None, description="频率配置，随类型不同结构不同")
    default_quadrant: QuadrantType = Field(QuadrantType.IMPORTANT_NOT_URGENT, description="生成待办的默认象限")
    goal_desc: Optional[str] = Field(None, description="目标描述，仅展示")
    reminder_time: Optional[time] = Field(None, description="每日提醒时间")


class HabitUpdate(BaseModel):
    id: int = Field(..., description="习惯ID")
    name: Optional[str] = None
    icon: Optional[str] = None
    color_hex: Optional[str] = None
    frequency_type: Optional[HabitFrequencyType] = None
    frequency_config: Optional[Dict[str, Any]] = None
    default_quadrant: Optional[QuadrantType] = None
    goal_desc: Optional[str] = None
    reminder_time: Optional[time] = None
    is_paused: Optional[bool] = None
    is_archived: Optional[bool] = None


class HabitOut(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    color_hex: Optional[str] = None
    frequency_type: HabitFrequencyType
    frequency_config: Optional[Dict[str, Any]] = None
    default_quadrant: QuadrantType
    goal_desc: Optional[str] = None
    reminder_time: Optional[time] = None
    is_paused: bool
    is_archived: bool
    today_todo_id: Optional[int] = Field(None, description="今天对应的待办ID，Task 3 补上生成检查后才会有值")
    streak: Optional[int] = Field(None, description="连续天数，定日型才有值，Task 3 补上")
    week_progress: Optional[str] = Field(None, description="本周进度如'1/3'，弹性型才有值，Task 3 补上")

    class Config:
        from_attributes = True
```

- [ ] **Step 4: 写 `app/controllers/habit.py`**

```python
from typing import List, Optional

from fastapi import HTTPException

from app.core.crud import CRUDBase
from app.models.todo import Habit, HabitFrequencyType
from app.schemas.habit import HabitCreate, HabitUpdate


class HabitController(CRUDBase[Habit, HabitCreate, HabitUpdate]):
    def __init__(self):
        super().__init__(model=Habit)

    def _validate_frequency_config(self, frequency_type: HabitFrequencyType, frequency_config: Optional[dict]) -> None:
        config = frequency_config or {}
        if frequency_type == HabitFrequencyType.WEEKLY_DAYS:
            days = config.get("days")
            if not days or not isinstance(days, list) or not all(isinstance(d, int) and 1 <= d <= 7 for d in days):
                raise HTTPException(status_code=400, detail="weekly_days 类型需要 frequency_config.days 为 1-7 的整数列表")
        elif frequency_type == HabitFrequencyType.WEEKLY_COUNT:
            count = config.get("count")
            if not isinstance(count, int) or count < 1:
                raise HTTPException(status_code=400, detail="weekly_count 类型需要 frequency_config.count 为正整数")
        elif frequency_type == HabitFrequencyType.INTERVAL_DAYS:
            interval = config.get("interval")
            if not isinstance(interval, int) or interval < 1:
                raise HTTPException(status_code=400, detail="interval_days 类型需要 frequency_config.interval 为正整数")

    async def create_habit(self, obj_in: HabitCreate, user_id: int) -> Habit:
        self._validate_frequency_config(obj_in.frequency_type, obj_in.frequency_config)
        return await Habit.create(user_id=user_id, **obj_in.model_dump())

    async def update_habit(self, habit_id: int, obj_in: HabitUpdate, user_id: int) -> Optional[Habit]:
        habit = await Habit.filter(id=habit_id, user_id=user_id).first()
        if not habit:
            return None

        update_data = obj_in.model_dump(exclude_unset=True, exclude={"id"})
        if "frequency_type" in update_data or "frequency_config" in update_data:
            frequency_type = update_data.get("frequency_type", habit.frequency_type)
            frequency_config = update_data.get("frequency_config", habit.frequency_config)
            self._validate_frequency_config(frequency_type, frequency_config)

        await habit.update_from_dict(update_data).save()
        return habit

    async def delete_habit(self, habit_id: int, user_id: int) -> bool:
        deleted_count = await Habit.filter(id=habit_id, user_id=user_id).delete()
        return deleted_count > 0

    async def get_archived_habits(self, user_id: int) -> List[Habit]:
        return await Habit.filter(user_id=user_id, is_archived=True).order_by("-updated_at")


habit_controller = HabitController()
```

- [ ] **Step 5: 写 `app/api/v1/habit/route.py`**

```python
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.controllers.habit import habit_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.todo import Habit
from app.schemas.base import Success
from app.schemas.habit import HabitCreate, HabitOut, HabitUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="获取当前用户进行中的习惯列表")
async def list_habits(current_user: User = Depends(AuthControl.is_authed)):
    habits = await Habit.filter(user_id=current_user.id, is_archived=False).order_by("-created_at")
    result = [HabitOut(**(await h.to_dict())).model_dump() for h in habits]
    return Success(data=result)


@router.get("/archived", summary="获取已归档的习惯列表")
async def list_archived_habits(current_user: User = Depends(AuthControl.is_authed)):
    habits = await habit_controller.get_archived_habits(current_user.id)
    result = [HabitOut(**(await h.to_dict())).model_dump() for h in habits]
    return Success(data=result)


@router.post("/create", summary="创建习惯")
async def create_habit(habit_in: HabitCreate, current_user: User = Depends(AuthControl.is_authed)):
    habit = await habit_controller.create_habit(habit_in, current_user.id)
    return Success(data=HabitOut(**(await habit.to_dict())).model_dump())


@router.post("/update", summary="更新习惯")
async def update_habit(habit_in: HabitUpdate, current_user: User = Depends(AuthControl.is_authed)):
    habit = await habit_controller.update_habit(habit_in.id, habit_in, current_user.id)
    if not habit:
        raise HTTPException(status_code=404, detail="习惯不存在")
    return Success(data=HabitOut(**(await habit.to_dict())).model_dump())


@router.delete("/delete", summary="删除习惯（级联删除历史打卡待办）")
async def delete_habit(
    habit_id: int = Query(..., description="习惯ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    success = await habit_controller.delete_habit(habit_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="习惯不存在")
    return Success(msg="删除成功")
```

（`list_habits` 这里先直接查库，不含生成检查——Task 3 会把这个函数体整体替换成调用 `habit_controller.list_active_with_status`。）

- [ ] **Step 6: 写 `app/api/v1/habit/__init__.py`**

```python
from fastapi import APIRouter

from .route import router

habit_router = APIRouter()
habit_router.include_router(router, tags=["习惯"])

__all__ = ["habit_router"]
```

- [ ] **Step 7: 挂载到 `app/api/v1/__init__.py`**

在现有 import 列表里按字母序插入一行，并在 `v1_router.include_router(...)` 列表末尾新增一行：

```python
from .habit import habit_router
```

```python
v1_router.include_router(habit_router, prefix="/habit", dependencies=[DependPermission])
```

- [ ] **Step 8: 跑测试确认通过**

Run: `pytest tests/test_habit.py -vv`
Expected: `12 passed`

- [ ] **Step 9: 提交**

```bash
git add app/schemas/habit.py app/controllers/habit.py app/api/v1/habit \
        app/api/v1/__init__.py tests/test_habit.py
git commit -m "feat: add Habit CRUD resource (create/update/delete/list/archived)"
```

---

## Task 3: 惰性生成算法 + 连续天数/本周进度

**Files:**
- Modify: `app/controllers/habit.py`
- Modify: `app/api/v1/habit/route.py`
- Modify: `tests/test_habit.py`

**Interfaces:**
- Consumes：Task 1 的 `TodoItem.habit`/`generated_date`；Task 2 的 `Habit`/`HabitOut`。
- Produces：`habit_controller.list_active_with_status(user_id) -> List[dict]`（含 `today_todo_id`/`streak`/`week_progress`），`habit_controller.ensure_today_generated(user_id) -> None`。Task 4 的统计排除依赖 `TodoItem.habit_id` 已经在这里被正确写入（不是新接口，是确认既有字段被用对）。

- [ ] **Step 1: 写测试（先写，此时字段有默认 `None`，预期生成/streak/week_progress 相关断言失败）**

在 `tests/test_habit.py` 顶部的 import 行改成（本任务的测试只用得到 `Habit`/`HabitFrequencyType`/`TodoItem`，`QuadrantType` 留给 Task 4 再加，避免中间状态出现未使用的导入）：

```python
from datetime import date, datetime, timedelta

from app.models.todo import Habit, HabitFrequencyType, TodoItem
```

在文件末尾追加：

```python
async def test_daily_habit_generates_and_is_idempotent(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="喝水", frequency_type=HabitFrequencyType.DAILY)

    resp1 = await client.get("/api/v1/habit/list")
    data1 = resp1.json()["data"][0]
    assert data1["today_todo_id"] is not None
    assert data1["streak"] == 0

    resp2 = await client.get("/api/v1/habit/list")
    data2 = resp2.json()["data"][0]
    assert data2["today_todo_id"] == data1["today_todo_id"]

    assert await TodoItem.filter(habit_id=habit.id).count() == 1


async def test_paused_habit_does_not_generate(client, test_user):
    habit = await Habit.create(
        user_id=test_user.id, name="暂停中", frequency_type=HabitFrequencyType.DAILY, is_paused=True
    )
    resp = await client.get("/api/v1/habit/list")
    data = resp.json()["data"][0]
    assert data["today_todo_id"] is None
    assert await TodoItem.filter(habit_id=habit.id).count() == 0


async def test_weekly_days_only_generates_on_matching_weekday(client, test_user):
    today_weekday = date.today().isoweekday()
    other_weekday = 1 if today_weekday != 1 else 2

    matching_habit = await Habit.create(
        user_id=test_user.id,
        name="今天该做",
        frequency_type=HabitFrequencyType.WEEKLY_DAYS,
        frequency_config={"days": [today_weekday]},
    )
    non_matching_habit = await Habit.create(
        user_id=test_user.id,
        name="今天不该做",
        frequency_type=HabitFrequencyType.WEEKLY_DAYS,
        frequency_config={"days": [other_weekday]},
    )

    await client.get("/api/v1/habit/list")

    assert await TodoItem.filter(habit_id=matching_habit.id).count() == 1
    assert await TodoItem.filter(habit_id=non_matching_habit.id).count() == 0


async def test_interval_days_generates_on_creation_day(client, test_user):
    habit = await Habit.create(
        user_id=test_user.id,
        name="隔天",
        frequency_type=HabitFrequencyType.INTERVAL_DAYS,
        frequency_config={"interval": 3},
    )

    await client.get("/api/v1/habit/list")

    assert await TodoItem.filter(habit_id=habit.id).count() == 1


async def test_weekly_count_stops_generating_and_cleans_up_after_quota_met(client, test_user):
    today = date.today()
    week_start = today - timedelta(days=today.isoweekday() - 1)
    week_days = [week_start + timedelta(days=i) for i in range(7)]
    # 本周内挑三个不是"今天"的日子模拟历史记录——若直接用 week_start/+1/+2，
    # 当测试恰好跑在周一时 week_start 就等于 today，会跟"今天"的待办撞在一起，测试变得不稳定
    seed_days = [d for d in week_days if d != today][:3]

    habit = await Habit.create(
        user_id=test_user.id,
        name="运动",
        frequency_type=HabitFrequencyType.WEEKLY_COUNT,
        frequency_config={"count": 2},
    )
    await TodoItem.create(
        title=habit.name,
        habit_id=habit.id,
        user_id=test_user.id,
        quadrant_type=habit.default_quadrant,
        generated_date=seed_days[0],
        is_completed=True,
    )
    await TodoItem.create(
        title=habit.name,
        habit_id=habit.id,
        user_id=test_user.id,
        quadrant_type=habit.default_quadrant,
        generated_date=seed_days[1],
        is_completed=True,
    )
    stale = await TodoItem.create(
        title=habit.name,
        habit_id=habit.id,
        user_id=test_user.id,
        quadrant_type=habit.default_quadrant,
        generated_date=seed_days[2],
        is_completed=False,
    )

    resp = await client.get("/api/v1/habit/list")
    data = resp.json()["data"][0]
    assert data["week_progress"] == "2/2"
    assert data["today_todo_id"] is None

    assert await TodoItem.filter(id=stale.id).count() == 0


async def test_weekly_count_generates_when_quota_not_met(client, test_user):
    habit = await Habit.create(
        user_id=test_user.id,
        name="运动",
        frequency_type=HabitFrequencyType.WEEKLY_COUNT,
        frequency_config={"count": 3},
    )

    resp = await client.get("/api/v1/habit/list")
    data = resp.json()["data"][0]
    assert data["week_progress"] == "0/3"
    assert data["today_todo_id"] is not None


async def test_streak_counts_consecutive_completed_days_and_breaks_on_miss(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="阅读", frequency_type=HabitFrequencyType.DAILY)
    today = date.today()

    await TodoItem.create(
        title=habit.name,
        habit_id=habit.id,
        user_id=test_user.id,
        quadrant_type=habit.default_quadrant,
        generated_date=today - timedelta(days=1),
        is_completed=True,
    )
    await TodoItem.create(
        title=habit.name,
        habit_id=habit.id,
        user_id=test_user.id,
        quadrant_type=habit.default_quadrant,
        generated_date=today - timedelta(days=2),
        is_completed=True,
    )
    await TodoItem.create(
        title=habit.name,
        habit_id=habit.id,
        user_id=test_user.id,
        quadrant_type=habit.default_quadrant,
        generated_date=today - timedelta(days=3),
        is_completed=False,
    )

    resp = await client.get("/api/v1/habit/list")
    data = resp.json()["data"][0]
    assert data["streak"] == 2


async def test_reminder_time_written_into_generated_todo(client, test_user):
    from datetime import time

    habit = await Habit.create(
        user_id=test_user.id,
        name="早起",
        frequency_type=HabitFrequencyType.DAILY,
        reminder_time=time(7, 30),
    )
    resp = await client.get("/api/v1/habit/list")
    todo_id = resp.json()["data"][0]["today_todo_id"]

    todo = await TodoItem.get(id=todo_id)
    assert todo.reminder_at is not None
    assert todo.reminder_at.hour == 7
    assert todo.reminder_at.minute == 30
```

- [ ] **Step 2: 跑测试确认现象**

Run: `pytest tests/test_habit.py -vv`
Expected: 新增的这几个测试失败（`today_todo_id`/`streak`/`week_progress` 恒为 `None`，因为 `list_habits` 还没接生成检查）。

- [ ] **Step 3: 修改 `app/controllers/habit.py`，顶部 import 改成，并在 `get_archived_habits` 方法后新增生成/统计相关方法**

```python
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.core.crud import CRUDBase
from app.models.todo import Habit, HabitFrequencyType, TodoItem
from app.schemas.habit import HabitCreate, HabitUpdate
```

在 `get_archived_habits` 方法之后（`habit_controller = HabitController()` 之前）新增：

```python
    async def list_active_with_status(self, user_id: int) -> List[Dict[str, Any]]:
        """进行中习惯列表，附带今日生成检查、今日待办ID、连续天数/本周进度"""
        await self.ensure_today_generated(user_id)

        habits = await Habit.filter(user_id=user_id, is_archived=False).order_by("-created_at")
        today = date.today()
        result = []
        for habit in habits:
            data = await habit.to_dict()

            if habit.is_paused:
                data["today_todo_id"] = None
            else:
                todo = await TodoItem.filter(habit_id=habit.id, generated_date=today).first()
                data["today_todo_id"] = todo.id if todo else None

            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT:
                data["streak"] = None
                count = (habit.frequency_config or {}).get("count", 0)
                completed = await self._completed_this_week(habit.id, today)
                data["week_progress"] = f"{completed}/{count}"
            else:
                data["streak"] = await self._calc_streak(habit, today)
                data["week_progress"] = None

            result.append(data)
        return result

    async def ensure_today_generated(self, user_id: int) -> None:
        """惰性生成检查：为该用户所有生效中的习惯，补上今天该生成但还没生成的打卡待办"""
        today = date.today()
        habits = await Habit.filter(user_id=user_id, is_paused=False, is_archived=False)

        for habit in habits:
            should_generate = await self._should_generate_today(habit, today)

            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT and not should_generate:
                week_start, week_end = self._week_range(today)
                await TodoItem.filter(
                    habit_id=habit.id,
                    is_completed=False,
                    generated_date__gte=week_start,
                    generated_date__lte=week_end,
                ).delete()

            if should_generate:
                exists = await TodoItem.filter(habit_id=habit.id, generated_date=today).exists()
                if not exists:
                    reminder_at = datetime.combine(today, habit.reminder_time) if habit.reminder_time else None
                    await TodoItem.create(
                        title=habit.name,
                        habit_id=habit.id,
                        user_id=user_id,
                        quadrant_type=habit.default_quadrant,
                        generated_date=today,
                        due_date=datetime.combine(today, time(23, 59, 59)),
                        reminder_at=reminder_at,
                    )

    async def _should_generate_today(self, habit: Habit, today: date) -> bool:
        config = habit.frequency_config or {}
        if habit.frequency_type == HabitFrequencyType.DAILY:
            return True
        if habit.frequency_type == HabitFrequencyType.WEEKLY_DAYS:
            return today.isoweekday() in config.get("days", [])
        if habit.frequency_type == HabitFrequencyType.INTERVAL_DAYS:
            interval = config.get("interval", 1)
            anchor = habit.created_at.date()
            return (today - anchor).days % interval == 0
        if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT:
            count = config.get("count", 0)
            completed = await self._completed_this_week(habit.id, today)
            return completed < count
        return False

    async def _completed_this_week(self, habit_id: int, today: date) -> int:
        week_start, week_end = self._week_range(today)
        return await TodoItem.filter(
            habit_id=habit_id, is_completed=True, generated_date__gte=week_start, generated_date__lte=week_end
        ).count()

    async def _calc_streak(self, habit: Habit, today: date) -> int:
        streak = 0
        cursor = today
        for _ in range(3650):  # 防止极端配置导致死循环，最多回看 10 年
            if not await self._should_generate_today(habit, cursor):
                cursor -= timedelta(days=1)
                continue
            todo = await TodoItem.filter(habit_id=habit.id, generated_date=cursor).first()
            if todo and todo.is_completed:
                streak += 1
                cursor -= timedelta(days=1)
            else:
                break
        return streak

    @staticmethod
    def _week_range(today: date) -> Tuple[date, date]:
        week_start = today - timedelta(days=today.isoweekday() - 1)
        week_end = week_start + timedelta(days=6)
        return week_start, week_end
```

- [ ] **Step 4: 修改 `app/api/v1/habit/route.py`，把 `list_habits` 函数体换成调用新方法，并删掉现在用不到的 `Habit` 导入**

把顶部的：

```python
from app.models.todo import Habit
```

这一行整行删掉——`list_habits` 改成调用 controller 方法后不再直接查询 `Habit` 模型，`list_archived_habits` 也一直走的是 `habit_controller.get_archived_habits`，本来就没有直接用到 `Habit`。不删的话这行会变成未使用的导入，`make lint`（ruff）会报 F401。

`list_habits` 函数体改成：

```python
@router.get("/list", summary="获取当前用户进行中的习惯列表（含今日生成检查）")
async def list_habits(current_user: User = Depends(AuthControl.is_authed)):
    habits = await habit_controller.list_active_with_status(current_user.id)
    result = [HabitOut(**h).model_dump() for h in habits]
    return Success(data=result)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest tests/test_habit.py -vv`
Expected: 全部通过（原有 12 个 + 新增 8 个 = 20 个）。

- [ ] **Step 6: 跑一次全量后端测试，确认没有破坏已有功能**

Run: `pytest -vv`
Expected: 全部通过。

- [ ] **Step 7: 提交**

```bash
git add app/controllers/habit.py app/api/v1/habit/route.py tests/test_habit.py
git commit -m "feat: implement habit lazy-generation, streak, and weekly progress"
```

---

## Task 4: `/todo` 统计接口排除习惯待办

**Files:**
- Modify: `app/schemas/todo.py`
- Modify: `app/controllers/todo.py`
- Modify: `tests/test_habit.py`

**Interfaces:**
- Consumes：Task 1 的 `TodoItem.habit_id`。
- Produces：`TodoItemOut.habit_id: Optional[int]`（只读展示字段）；`TodoController.get_statistics_by_date`/`get_quadrant_statistics` 排除 `habit_id` 非空的待办。

- [ ] **Step 1: 写测试（先写，此时统计接口还没排除习惯待办，预期计数偏高）**

`tests/test_habit.py` 顶部的 import 行，把（Task 3 留下的状态）：

```python
from app.models.todo import Habit, HabitFrequencyType, TodoItem
```

改成（本任务的测试需要用到 `QuadrantType`）：

```python
from app.models.todo import Habit, HabitFrequencyType, QuadrantType, TodoItem
```

`from datetime import date, datetime, timedelta` 这一行不用改。在文件末尾追加：

```python
async def test_quadrant_statistics_exclude_habit_todos(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="打卡", frequency_type=HabitFrequencyType.DAILY)
    await TodoItem.create(
        title="习惯待办",
        habit_id=habit.id,
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
    )
    await TodoItem.create(
        title="普通待办",
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
    )

    resp = await client.get("/api/v1/todo/statistics/quadrant")
    assert resp.json()["data"]["urgent_important"] == 1


async def test_daily_statistics_exclude_habit_todos(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="打卡", frequency_type=HabitFrequencyType.DAILY)
    now = datetime.now()
    await TodoItem.create(
        title="习惯待办",
        habit_id=habit.id,
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
        is_completed=True,
        completed_at=now,
    )
    await TodoItem.create(
        title="普通待办",
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
        is_completed=True,
        completed_at=now,
    )

    resp = await client.get("/api/v1/todo/statistics/daily")
    today_str = date.today().isoformat()
    today_stat = next(s for s in resp.json()["data"] if s["date"] == today_str)
    assert today_stat["urgent_important"] == 1


async def test_todo_list_includes_habit_id(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="打卡", frequency_type=HabitFrequencyType.DAILY)
    await TodoItem.create(
        title="习惯待办", habit_id=habit.id, user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT
    )

    resp = await client.get("/api/v1/todo/list")
    item = next(t for t in resp.json()["data"] if t["title"] == "习惯待办")
    assert item["habit_id"] == habit.id
```

- [ ] **Step 2: 跑测试确认现象**

Run: `pytest tests/test_habit.py -vv`
Expected: 这三个新测试失败（统计接口把习惯待办也算进去了；`habit_id` 字段在响应里缺失）。

- [ ] **Step 3: 修改 `app/schemas/todo.py`，`TodoItemOut` 类里 `subtask_completed` 字段后面新增一行**

```python
    subtask_total: int = Field(0, description="子任务总数")
    subtask_completed: int = Field(0, description="已完成子任务数")
    habit_id: Optional[int] = Field(None, description="所属习惯ID，非空表示是习惯生成的打卡待办")
```

- [ ] **Step 4: 修改 `app/controllers/todo.py`，`get_statistics_by_date` 和 `get_quadrant_statistics` 的查询各加一个过滤条件**

`get_statistics_by_date` 里：

```python
                count = await TodoItem.filter(
                    user_id=user_id, quadrant_type=quadrant, completed_at__gte=day_start, completed_at__lte=day_end,
                    habit_id__isnull=True,
                ).count()
```

`get_quadrant_statistics` 里：

```python
            count = await TodoItem.filter(user_id=user_id, quadrant_type=quadrant, habit_id__isnull=True).count()
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest tests/test_habit.py -vv`
Expected: 全部通过（20 + 3 = 23 个）。

- [ ] **Step 6: 跑一次全量后端测试**

Run: `pytest -vv`
Expected: 全部通过。

- [ ] **Step 7: 提交**

```bash
git add app/schemas/todo.py app/controllers/todo.py tests/test_habit.py
git commit -m "feat: exclude habit-generated todos from quadrant/daily statistics"
```

---

## Task 5: "习惯" Menu 记录

**Files:**
- Modify: `app/core/init_app.py`

**Interfaces:**
- Consumes：无。
- Produces：菜单记录 `component="/todo/Habit"`，Task 8 的 `Habit/index.vue` 依赖这条记录才能被路由到。

- [ ] **Step 1: 修改 `app/core/init_app.py`**

在"二期日历排程：日历页菜单"那个独立判断块之后，紧接着新增一个同样风格的独立判断块：

```python
    # 三期习惯打卡：习惯页菜单。独立于上面的判断，保证已经部署过的环境重启后也能自动补上
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        habit_menu = await Menu.filter(name="习惯", parent_id=todo_parent_menu.id).first()
        if not habit_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="习惯",
                path="habit",
                order=2,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:sync-outline",
                is_hidden=False,
                component="/todo/Habit",
                keepalive=True,
            )
```

- [ ] **Step 2: 手动验证菜单初始化逻辑无语法错误**

Run: `python -c "import app.core.init_app"`
Expected: 无报错。

- [ ] **Step 3: 提交**

```bash
git add app/core/init_app.py
git commit -m "feat: add Habit menu entry"
```

---

## Task 6: 前端 API 客户端（habit）

**Files:**
- Create: `web/src/api/habit.js`
- Modify: `web/src/api/index.js`

**Interfaces:**
- Consumes：Task 2/3/4 的 `/habit/*`。
- Produces：`api.getHabits()`、`api.getArchivedHabits()`、`api.createHabit(data)`、`api.updateHabit(id, data)`、`api.deleteHabit(id)`。Task 7/8 的组件直接调用。

- [ ] **Step 1: 写 `web/src/api/habit.js`**

```js
import { request } from '@/utils'

/**
 * 习惯API接口
 */
export default {
  /**
   * 获取当前用户进行中的习惯列表（含今日生成检查）
   * @returns {Promise}
   */
  getHabits: () => request.get('/habit/list'),

  /**
   * 获取已归档的习惯列表
   * @returns {Promise}
   */
  getArchivedHabits: () => request.get('/habit/archived'),

  /**
   * 创建习惯
   * @param {Object} data
   * @returns {Promise}
   */
  createHabit: (data = {}) => request.post('/habit/create', data),

  /**
   * 更新习惯
   * @param {Number} id
   * @param {Object} data
   * @returns {Promise}
   */
  updateHabit: (id, data = {}) => request.post('/habit/update', { ...data, id }),

  /**
   * 删除习惯（级联删除历史打卡待办）
   * @param {Number} id
   * @returns {Promise}
   */
  deleteHabit: (id) => request.delete('/habit/delete', { params: { habit_id: id } })
}
```

- [ ] **Step 2: 修改 `web/src/api/index.js`**

在顶部 import 区加入：

```js
import habitApi from './habit'
```

在导出对象的 `...timeblockApi,` 之后加入：

```js
  ...timeblockApi,
  // habit（三期习惯打卡）
  ...habitApi
```

- [ ] **Step 3: lint 检查**

Run: `cd web && pnpm exec eslint src/api/habit.js src/api/index.js`
Expected: 只有 `prettier/prettier` 格式类提示（本仓库已知的 ~495 条历史遗留格式问题的一部分），没有逻辑/语法错误。

- [ ] **Step 4: 提交**

```bash
git add web/src/api/habit.js web/src/api/index.js
git commit -m "feat(web): add habit API client"
```

---

## Task 7: `HabitFormModal.vue`

**Files:**
- Create: `web/src/views/todo/Habit/HabitFormModal.vue`

**Interfaces:**
- Consumes：Task 6 的 `api.createHabit`/`api.updateHabit`。
- Produces：`HabitFormModal` 组件，props `show`（v-model）、`habit`（非空表示编辑模式，传入 `/habit/list` 或 `/habit/archived` 返回的单条习惯对象），emits `update:show`、`saved`（保存成功后触发，无 payload，由父组件重新拉取列表）。Task 8 的 `Habit/index.vue` 直接引入。

- [ ] **Step 1: 写 `HabitFormModal.vue`**

```vue
<template>
  <n-modal :show="show" preset="card" :title="isEdit ? '编辑习惯' : '添加新习惯'" style="width: 480px" @update:show="onUpdateShow">
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="80">
      <n-form-item label="名称" path="name">
        <n-input v-model:value="form.name" placeholder="例如：每天阅读" />
      </n-form-item>
      <div style="display: flex; gap: 1em">
        <n-form-item label="图标" style="flex: 1">
          <n-input v-model:value="form.icon" placeholder="emoji，如 📖" maxlength="10" />
        </n-form-item>
        <n-form-item label="颜色" style="flex: 1">
          <n-color-picker v-model:value="form.color_hex" :show-alpha="false" />
        </n-form-item>
      </div>
      <n-form-item label="频率" path="frequency_type">
        <n-radio-group v-model:value="form.frequency_type">
          <n-space>
            <n-radio value="daily">每天</n-radio>
            <n-radio value="weekly_days">每周固定几天</n-radio>
            <n-radio value="weekly_count">每周N次</n-radio>
            <n-radio value="interval_days">每隔N天</n-radio>
          </n-space>
        </n-radio-group>
      </n-form-item>
      <n-form-item v-if="form.frequency_type === 'weekly_days'" label="星期">
        <n-checkbox-group v-model:value="form.weekly_days">
          <n-checkbox v-for="opt in weekdayOptions" :key="opt.value" :value="opt.value" :label="opt.label" />
        </n-checkbox-group>
      </n-form-item>
      <n-form-item v-if="form.frequency_type === 'weekly_count'" label="每周次数">
        <n-input-number v-model:value="form.weekly_count" :min="1" style="width: 100%" />
      </n-form-item>
      <n-form-item v-if="form.frequency_type === 'interval_days'" label="间隔天数">
        <n-input-number v-model:value="form.interval_days" :min="1" style="width: 100%" />
      </n-form-item>
      <n-form-item label="默认象限">
        <n-radio-group v-model:value="form.default_quadrant">
          <n-space>
            <n-radio v-for="opt in quadrantOptions" :key="opt.value" :value="opt.value">
              <span class="quadrant-dot" :style="{ background: opt.color }"></span>
              {{ opt.label }}
            </n-radio>
          </n-space>
        </n-radio-group>
      </n-form-item>
      <n-form-item label="目标描述">
        <n-input v-model:value="form.goal_desc" placeholder="例如：30分钟（可选）" />
      </n-form-item>
      <n-form-item label="提醒时间">
        <n-time-picker
          v-model:formatted-value="form.reminder_time"
          value-format="HH:mm:ss"
          clearable
          style="width: 100%"
        />
      </n-form-item>
    </n-form>
    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5em">
        <n-button @click="onUpdateShow(false)">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="handleSubmit">保存习惯</n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false },
  habit: { type: Object, default: null }
})
const emit = defineEmits(['update:show', 'saved'])

const message = useMessage()
const formRef = ref(null)
const submitting = ref(false)

const isEdit = computed(() => !!props.habit)

const weekdayOptions = [
  { label: '一', value: 1 },
  { label: '二', value: 2 },
  { label: '三', value: 3 },
  { label: '四', value: 4 },
  { label: '五', value: 5 },
  { label: '六', value: 6 },
  { label: '日', value: 7 }
]

const quadrantOptions = [
  { label: '重要且紧急', value: 'urgent_important', color: '#f5222d' },
  { label: '紧急不重要', value: 'urgent_not_important', color: '#faad14' },
  { label: '重要不紧急', value: 'important_not_urgent', color: '#1890ff' },
  { label: '不紧急不重要', value: 'not_urgent_not_important', color: '#909399' }
]

const defaultForm = () => ({
  name: '',
  icon: '',
  color_hex: '#1890FF',
  frequency_type: 'daily',
  weekly_days: [],
  weekly_count: 3,
  interval_days: 2,
  default_quadrant: 'important_not_urgent',
  goal_desc: '',
  reminder_time: null
})
const form = ref(defaultForm())

const rules = {
  name: { required: true, message: '请输入名称', trigger: 'blur' }
}

const onUpdateShow = (value) => emit('update:show', value)

const fillFormFromHabit = (habit) => {
  const config = habit.frequency_config || {}
  form.value = {
    name: habit.name,
    icon: habit.icon || '',
    color_hex: habit.color_hex || '#1890FF',
    frequency_type: habit.frequency_type,
    weekly_days: config.days || [],
    weekly_count: config.count || 3,
    interval_days: config.interval || 2,
    default_quadrant: habit.default_quadrant,
    goal_desc: habit.goal_desc || '',
    reminder_time: habit.reminder_time || null
  }
}

watch(
  () => props.show,
  (visible) => {
    if (!visible) return
    if (props.habit) {
      fillFormFromHabit(props.habit)
    } else {
      form.value = defaultForm()
    }
  }
)

const buildFrequencyConfig = () => {
  if (form.value.frequency_type === 'weekly_days') return { days: form.value.weekly_days }
  if (form.value.frequency_type === 'weekly_count') return { count: form.value.weekly_count }
  if (form.value.frequency_type === 'interval_days') return { interval: form.value.interval_days }
  return null
}

const handleSubmit = async () => {
  await formRef.value?.validate()
  if (form.value.frequency_type === 'weekly_days' && !form.value.weekly_days.length) {
    message.error('请至少选择一天')
    return
  }
  submitting.value = true
  try {
    const payload = {
      name: form.value.name,
      icon: form.value.icon || null,
      color_hex: form.value.color_hex,
      frequency_type: form.value.frequency_type,
      frequency_config: buildFrequencyConfig(),
      default_quadrant: form.value.default_quadrant,
      goal_desc: form.value.goal_desc || null,
      reminder_time: form.value.reminder_time || null
    }
    if (isEdit.value) {
      await api.updateHabit(props.habit.id, payload)
    } else {
      await api.createHabit(payload)
    }
    message.success('保存成功')
    emit('saved')
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
</style>
```

- [ ] **Step 2: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/Habit/HabitFormModal.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 提交**

```bash
git add web/src/views/todo/Habit/HabitFormModal.vue
git commit -m "feat(web): add HabitFormModal component"
```

---

## Task 8: `Habit/index.vue` 页面组装

**Files:**
- Create: `web/src/views/todo/Habit/index.vue`

**Interfaces:**
- Consumes：Task 6 的 `api.getHabits`/`api.getArchivedHabits`/`api.updateHabit`/`api.deleteHabit`、一期已有的 `api.updateTodo`（"今日打卡"直接调用）；Task 7 的 `HabitFormModal.vue`。
- Produces：Menu 记录 `component="/todo/Habit"`（Task 5 已创建）指向的页面入口。

- [ ] **Step 1: 写 `web/src/views/todo/Habit/index.vue`**

```vue
<template>
  <div class="habit-page">
    <div class="habit-header">
      <h2>习惯追踪</h2>
      <n-button type="primary" @click="openCreateModal">+ 添加习惯</n-button>
    </div>

    <section>
      <h3>进行中的习惯</h3>
      <div v-for="habit in habits" :key="habit.id" class="habit-item" :class="{ paused: habit.is_paused }">
        <div class="habit-content">
          <span class="habit-title">
            <span v-if="habit.icon" class="habit-icon">{{ habit.icon }}</span>
            {{ habit.name }}
            <span v-if="habit.is_paused" class="paused-tag">(已暂停)</span>
          </span>
          <div class="habit-meta">
            <span>{{ frequencyLabel(habit) }}</span>
            <span v-if="habit.goal_desc">目标: {{ habit.goal_desc }}</span>
            <span v-if="habit.streak !== null">连续坚持 {{ habit.streak }} 天</span>
            <span v-if="habit.week_progress">本周 {{ habit.week_progress }}</span>
          </div>
          <div v-if="habit.week_progress" class="progress-bar">
            <div
              class="progress-bar-inner"
              :style="{ width: progressPercent(habit) + '%', background: habit.color_hex || '#1890ff' }"
            ></div>
          </div>
        </div>
        <div class="habit-actions">
          <n-button size="small" type="primary" :disabled="!habit.today_todo_id" @click="checkIn(habit)">
            今日打卡
          </n-button>
          <n-dropdown trigger="click" :options="activeHabitOptions" @select="(key) => handleAction(key, habit)">
            <button class="habit-more-btn" @click.stop>⋯</button>
          </n-dropdown>
        </div>
      </div>
      <n-empty v-if="!habits.length" description="还没有习惯，点右上角添加一个" />
    </section>

    <n-collapse v-if="archivedHabits.length" class="archived-collapse">
      <n-collapse-item title="已归档习惯" name="archived">
        <div v-for="habit in archivedHabits" :key="habit.id" class="habit-item archived">
          <div class="habit-content">
            <span class="habit-title">{{ habit.name }}</span>
          </div>
          <div class="habit-actions">
            <n-button size="small" @click="handleAction('unarchive', habit)">恢复</n-button>
            <n-button size="small" quaternary type="error" @click="handleAction('delete', habit)">删除</n-button>
          </div>
        </div>
      </n-collapse-item>
    </n-collapse>

    <HabitFormModal v-model:show="showFormModal" :habit="editingHabit" @saved="fetchAll" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import api from '@/api'
import HabitFormModal from './HabitFormModal.vue'

const message = useMessage()
const dialog = useDialog()

const habits = ref([])
const archivedHabits = ref([])
const showFormModal = ref(false)
const editingHabit = ref(null)

const activeHabitOptions = [
  { label: '编辑', key: 'edit' },
  { label: '暂停/恢复', key: 'toggle-pause' },
  { label: '归档', key: 'archive' },
  { label: '删除', key: 'delete' }
]

const frequencyLabel = (habit) => {
  const config = habit.frequency_config || {}
  if (habit.frequency_type === 'daily') return '每天'
  if (habit.frequency_type === 'weekly_days') {
    const names = ['一', '二', '三', '四', '五', '六', '日']
    return '每周' + (config.days || []).map((d) => names[d - 1]).join('')
  }
  if (habit.frequency_type === 'weekly_count') return `每周${config.count}次`
  if (habit.frequency_type === 'interval_days') return `每隔${config.interval}天`
  return ''
}

const progressPercent = (habit) => {
  if (!habit.week_progress) return 0
  const [done, total] = habit.week_progress.split('/').map(Number)
  return total ? Math.min(100, (done / total) * 100) : 0
}

const fetchHabits = async () => {
  try {
    const res = await api.getHabits()
    habits.value = res.data || []
  } catch (error) {
    console.error('获取习惯列表失败:', error)
    message.error('获取习惯列表失败')
  }
}

const fetchArchivedHabits = async () => {
  try {
    const res = await api.getArchivedHabits()
    archivedHabits.value = res.data || []
  } catch (error) {
    console.error('获取归档习惯失败:', error)
    message.error('获取归档习惯失败')
  }
}

const fetchAll = () => Promise.all([fetchHabits(), fetchArchivedHabits()])

const openCreateModal = () => {
  editingHabit.value = null
  showFormModal.value = true
}

const checkIn = async (habit) => {
  if (!habit.today_todo_id) return
  try {
    await api.updateTodo(habit.today_todo_id, { is_completed: true })
    message.success('打卡成功')
    fetchHabits()
  } catch (error) {
    console.error('打卡失败:', error)
    message.error('打卡失败')
  }
}

const updateHabitField = async (habit, data) => {
  try {
    await api.updateHabit(habit.id, data)
    fetchAll()
  } catch (error) {
    console.error('更新习惯失败:', error)
    message.error('更新习惯失败')
  }
}

const confirmDelete = (habit) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除习惯「${habit.name}」吗？它的所有历史打卡记录也会被一并删除，且不可恢复。`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.deleteHabit(habit.id)
        message.success('删除成功')
        fetchAll()
      } catch (error) {
        console.error('删除习惯失败:', error)
        message.error('删除失败')
      }
    }
  })
}

const handleAction = (key, habit) => {
  if (key === 'edit') {
    editingHabit.value = habit
    showFormModal.value = true
  } else if (key === 'toggle-pause') {
    updateHabitField(habit, { is_paused: !habit.is_paused })
  } else if (key === 'archive') {
    updateHabitField(habit, { is_archived: true })
  } else if (key === 'unarchive') {
    updateHabitField(habit, { is_archived: false })
  } else if (key === 'delete') {
    confirmDelete(habit)
  }
}

onMounted(fetchAll)
</script>

<style scoped>
.habit-page {
  max-width: 900px;
}
.habit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5em;
}
.habit-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.8em 0.2em;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
}
.habit-item.paused {
  opacity: 0.5;
}
.habit-item.archived {
  opacity: 0.7;
}
.habit-content {
  flex: 1;
  min-width: 0;
}
.habit-title {
  font-size: 1em;
  font-weight: 500;
}
.habit-icon {
  margin-right: 0.4em;
}
.paused-tag {
  font-size: 0.8em;
  opacity: 0.6;
  margin-left: 0.4em;
}
.habit-meta {
  display: flex;
  gap: 1em;
  font-size: 0.82em;
  opacity: 0.7;
  margin-top: 0.2em;
}
.progress-bar {
  height: 6px;
  border-radius: 3px;
  background: rgba(128, 128, 128, 0.15);
  margin-top: 0.5em;
  overflow: hidden;
}
.progress-bar-inner {
  height: 100%;
  transition: width 0.2s;
}
.habit-actions {
  display: flex;
  align-items: center;
  gap: 0.5em;
  flex-shrink: 0;
}
.habit-more-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0.2em 0.5em;
  border-radius: 4px;
  color: inherit;
  opacity: 0.6;
  line-height: 1;
}
.habit-more-btn:hover {
  opacity: 1;
  background: rgba(128, 128, 128, 0.15);
}
.archived-collapse {
  margin-top: 2em;
}
</style>
```

- [ ] **Step 2: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/Habit/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开开发地址，用 `admin`/`123456` 登录（超级管理员默认可见所有菜单，不受 API 权限分配影响）。

验证清单：
- "待办事项"菜单下能看到"习惯"入口。
- 点"+ 添加习惯"，选不同频率类型时下面的配置项正确切换（`weekly_days` 出现星期多选，`weekly_count`/`interval_days` 出现数字输入）。
- 创建一个 `daily` 习惯后，列表里出现该习惯，"今日打卡"按钮可点；点击后打卡成功，去任务列表页能看到对应的已完成待办。
- 创建一个 `weekly_count=3` 的习惯，"本周 0/3" 展示正确，打卡一次后变成"本周 1/3"。
- 归档一个习惯后从主列表消失，出现在折叠的"已归档习惯"区块；点击"恢复"后回到主列表。
- 删除一个习惯后确认弹窗正确展示；确认删除后从列表消失。

Expected: 以上行为均符合预期，浏览器控制台无报错。

- [ ] **Step 4: 提交**

```bash
git add web/src/views/todo/Habit/index.vue
git commit -m "feat(web): assemble Habit page with list, archive, and form modal"
```

---

## Task 9: 端到端验证 + 收尾

**Files:**
- 无新增/修改文件（除非验证中发现问题，需要回到对应 Task 修复）。

**Interfaces:**
- Consumes：全部前序 Task 的产出。
- Produces：无——本任务是对整个习惯打卡子系统的最终确认，对照 `docs/superpowers/specs/2026-08-10-task-system-phase3-habit-design.md` 的验收标准逐条过一遍。

- [ ] **Step 1: 跑全量后端测试**

Run: `pytest -vv`
Expected: 全部通过（含一期/二期遗留测试 + 本阶段新增的 `test_habit.py`）。

- [ ] **Step 2: 跑前端 lint（限定改动文件）**

Run: `cd web && pnpm exec eslint src/api/habit.js src/api/index.js src/views/todo/Habit/HabitFormModal.vue src/views/todo/Habit/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 用管理后台把新增 API 分配给角色**

启动后端（`python run.py`）后，用 `admin`/`123456` 登录管理后台，进入"系统管理 → API 管理"点击"刷新 API"，确认新增的 `/api/v1/habit/*` 四个接口出现在列表里；进入"角色管理"，把这些接口分配给测试要用的角色（超级管理员本身跳过 API 校验，不受影响）。

- [ ] **Step 4: 浏览器端到端走查，对照 spec 验收标准**

Run: `cd web && pnpm dev`，浏览器登录后依次验证 `docs/superpowers/specs/2026-08-10-task-system-phase3-habit-design.md` 的"验收标准"一节（daily 习惯打卡、weekly_count 额度耗尽后停止生成、weekly_days 非指定日不生成、连续天数中断重算、暂停/归档/删除的联动、一期统计接口不受习惯待办干扰）。

Expected: 全部符合预期。若发现偏差，回到对应 Task 定位问题、修复、重新跑一遍该 Task 的测试/验证步骤，再继续。

- [ ] **Step 5: 如果验证过程中做了修复，提交**

```bash
git add -A
git commit -m "fix: address issues found during phase3-habit end-to-end verification"
```

（如果 Step 4 全部一次通过、没有任何修改，跳过本步。）
