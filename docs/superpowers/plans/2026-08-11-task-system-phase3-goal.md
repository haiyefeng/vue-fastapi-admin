# 三期（下）：计划目标 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 `docs/superpowers/specs/2026-08-11-task-system-phase3-goal-design.md` 描述的计划目标子系统：新增 `Goal` 模型 + 接口，`TodoItem`/`Habit` 各增加可选 `goal_id` 关联，交付计划页（列表 + 进度条 + 归档 + 新建编辑弹窗 + 详情弹窗），并在任务详情弹窗、习惯弹窗里新增"关联计划"下拉。

**Architecture:** 后端沿用 `app/api/v1/habit`/`app/api/v1/project` 现有的扁平 `/list /create /update /delete` 路由风格 + `CRUDBase` 继承模式，新增 `goal` 资源模块（含一个额外的 `/detail` 端点用于详情弹窗）。前端新增 `web/src/views/todo/Goal/`（`index.vue` 页面壳 + `GoalFormModal.vue` 新建编辑弹窗 + `GoalDetailModal.vue` 只读详情弹窗），并改动两个已有组件（`TaskDetailModal.vue`、`HabitFormModal.vue`）加一个"关联计划"下拉。先后端（含 pytest 单测）后前端。

**Tech Stack:** FastAPI + Tortoise ORM（后端），Vue 3 `<script setup>` + Naive UI（前端），pytest + pytest-asyncio + httpx（后端测试，沿用一期搭好的 `tests/conftest.py`）。

## Global Constraints

- 路由风格：`/list` `/archived` `/detail` `/create` `/update` `/delete` + query 参数，不做嵌套 REST，路由文件放在 `app/api/v1/<resource>/route.py` + `__init__.py`。
- 所有新路由挂 `dependencies=[DependPermission]`；处理函数内部用 `Depends(AuthControl.is_authed)` 取当前用户，所有查询按 `user_id` 过滤，不做细粒度 RBAC。
- 关联关系只做单向：只能从任务详情弹窗/习惯弹窗选"关联到哪个计划"，计划详情弹窗不提供反向的"添加关联任务/关联习惯"选择器。
- `TodoItem.goal`/`Habit.goal` 用 `on_delete=fields.SET_NULL`——删除计划不影响已关联的任务/习惯本身。
- 计划详情弹窗里的关联习惯列表只显示名称+频率文案，不计算连续天数/本周进度，也不触发习惯的惰性生成检查（`GET /goal/detail` 不调用 `habit_controller.ensure_today_generated`）。
- 前端所有涉及"日期"（不含时间）的字段（`target_date`）一律用本地时区的年/月/日拼接字符串，禁止用 `.toISOString()` 或 `new Date(dateString)` 处理纯日期字符串——这两种写法在非 UTC 时区下都会因为时区换算产生日期偏移（本项目二期/三期上期都因为类似问题踩过坑，这次直接按正确写法实现，不留给后续修复）。
- 后端每个任务遵循"写测试→跑测试确认现象→写实现→跑测试确认通过→提交"的顺序，复用 `tests/conftest.py` 的三个 fixture（`db`/`test_user`/`client`），不重新声明。前端本仓库未配置测试运行器，前端任务改为"实现→`pnpm exec eslint` 检查改动文件→提交"，最终 Task 11 做一次端到端确认。

---

## Task 1: Goal 模型 + TodoItem/Habit 增量字段

**Files:**
- Modify: `app/models/todo.py`
- Modify: `app/models/__init__.py`

**Interfaces:**
- Produces：`app.models.todo.Goal`（字段：`user`、`name`、`description`、`target_date`、`category`、`is_archived`）；`TodoItem.goal`（FK→Goal，可空，`on_delete=SET_NULL`，`related_name="todos"`）、`Habit.goal`（FK→Goal，可空，`on_delete=SET_NULL`，`related_name="habits"`）。这些是 Task 2/3/4 的直接依赖。

- [ ] **Step 1: 修改 `app/models/todo.py`，在 `TodoItem` 类里 `generated_date` 字段后面新增一行**

```python
    generated_date = fields.DateField(
        null=True,
        description="习惯待办的所属日期，仅习惯生成的待办有值；用于幂等判断，与用户可改的 due_date 语义分离",
    )
    goal = fields.ForeignKeyField(
        "models.Goal", related_name="todos", null=True, on_delete=fields.SET_NULL,
        description="关联的计划，为空表示未关联",
    )
```

- [ ] **Step 2: 在 `Habit` 类里 `is_archived` 字段后面新增一行**

```python
    is_archived = fields.BooleanField(default=False, description="归档后从主列表隐藏，历史保留")
    goal = fields.ForeignKeyField(
        "models.Goal", related_name="habits", null=True, on_delete=fields.SET_NULL,
        description="关联的计划，为空表示未关联",
    )
```

- [ ] **Step 3: 在文件末尾（`Habit` 类之后）新增 `Goal`**

```python
class Goal(BaseModel, TimestampMixin):
    """计划/目标模型"""

    user = fields.ForeignKeyField("models.User", related_name="goals", description="所属用户")
    name = fields.CharField(max_length=100, description="计划/目标名称")
    description = fields.TextField(null=True, description="描述")
    target_date = fields.DateField(null=True, description="目标完成日期")
    category = fields.ForeignKeyField(
        "models.Category", related_name="goals", null=True, description="归属分类"
    )
    is_archived = fields.BooleanField(default=False, description="归档后从主列表隐藏，历史保留")

    class Meta:
        table = "goal"

    def __str__(self):
        return self.name
```

- [ ] **Step 4: 修改 `app/models/__init__.py`**

```python
# 新增model需要在这里导入
from .admin import *
from .todo import Category, Goal, Habit, HabitFrequencyType, Project, QuadrantType, SubTask, TimeBlock, TodoItem
```

- [ ] **Step 5: 跑一次冒烟测试确认模型改动没有语法/引用错误**

Run: `pytest tests/test_smoke.py -vv`
Expected: `1 passed`。

- [ ] **Step 6: 生成并应用 aerich 迁移**

Run: `python run.py`（等到控制台打出启动完成的日志后 Ctrl+C 停掉）
Expected: 无报错退出；若报连接数据库失败，说明当前生效的数据库连接配置在本机不可达，需要先配好本地可访问的数据库再继续。

- [ ] **Step 7: 提交**

```bash
git add app/models/todo.py app/models/__init__.py
git commit -m "feat: add Goal model and TodoItem.goal/Habit.goal fields"
```

---

## Task 2: Goal CRUD 资源接口

**Files:**
- Create: `app/schemas/goal.py`
- Create: `app/controllers/goal.py`
- Create: `app/api/v1/goal/__init__.py`
- Create: `app/api/v1/goal/route.py`
- Modify: `app/api/v1/__init__.py`
- Create: `tests/test_goal.py`

**Interfaces:**
- Consumes：Task 1 的 `Goal` 模型；一期已有的 `app.controllers.category.category_controller.get_or_create(user_id, name)`。
- Produces：`app.controllers.goal.goal_controller`（方法 `create_goal(obj_in, user_id) -> Goal`；`update_goal(goal_id, obj_in, user_id) -> Optional[Goal]`；`delete_goal(goal_id, user_id) -> bool`；`get_active_goals(user_id) -> List[Goal]`；`get_archived_goals(user_id) -> List[Goal]`；`to_out_dict(goal) -> dict`；`get_task_counts(goal_ids) -> Dict[int, Tuple[int, int]]`；`get_habit_counts(goal_ids) -> Dict[int, int]`）。Task 3 会在这个 controller 里追加 `get_goal_detail` 方法，不改动本任务已有的方法签名。

- [ ] **Step 1: 写测试（先写，此时对应路由还不存在，预期 404）**

```python
# tests/test_goal.py
from app.models.todo import Category, Goal, Habit, HabitFrequencyType, QuadrantType, TodoItem


async def test_create_goal(client, test_user):
    resp = await client.post(
        "/api/v1/goal/create",
        json={"name": "提升 React 编程技能", "description": "熟练掌握核心概念", "target_date": "2026-12-31"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "提升 React 编程技能"
    assert data["target_date"] == "2026-12-31"
    assert data["task_total"] == 0
    assert data["task_completed"] == 0
    assert data["habit_count"] == 0


async def test_create_goal_with_new_category_name(client, test_user):
    resp = await client.post(
        "/api/v1/goal/create",
        json={"name": "完成毕业论文", "category_name": "学习"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["category_name"] == "学习"
    assert await Category.filter(name="学习", user_id=test_user.id).count() == 1


async def test_create_goal_reuses_existing_category(client, test_user):
    await client.post("/api/v1/goal/create", json={"name": "计划一", "category_name": "工作"})
    await client.post("/api/v1/goal/create", json={"name": "计划二", "category_name": "工作"})

    assert await Category.filter(name="工作", user_id=test_user.id).count() == 1


async def test_list_goals_includes_task_and_habit_counts(client, test_user):
    goal = await Goal.create(user_id=test_user.id, name="学习计划")
    await TodoItem.create(
        title="任务A", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id,
        goal_id=goal.id, is_completed=True,
    )
    await TodoItem.create(
        title="任务B", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id, goal_id=goal.id,
    )
    await Habit.create(user_id=test_user.id, name="每日阅读", frequency_type=HabitFrequencyType.DAILY, goal_id=goal.id)

    resp = await client.get("/api/v1/goal/list")
    data = resp.json()["data"][0]
    assert data["task_total"] == 2
    assert data["task_completed"] == 1
    assert data["habit_count"] == 1


async def test_update_goal_can_archive(client, test_user):
    create_resp = await client.post("/api/v1/goal/create", json={"name": "旧计划"})
    goal_id = create_resp.json()["data"]["id"]

    resp = await client.post("/api/v1/goal/update", json={"id": goal_id, "is_archived": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["is_archived"] is True


async def test_update_goal_can_clear_category(client, test_user):
    create_resp = await client.post("/api/v1/goal/create", json={"name": "计划", "category_name": "工作"})
    goal_id = create_resp.json()["data"]["id"]

    resp = await client.post("/api/v1/goal/update", json={"id": goal_id, "category_id": None})
    assert resp.status_code == 200
    assert resp.json()["data"]["category_name"] is None


async def test_list_archived_goals(client, test_user):
    await Goal.create(user_id=test_user.id, name="已归档计划", is_archived=True)
    await Goal.create(user_id=test_user.id, name="进行中计划")

    resp = await client.get("/api/v1/goal/archived")
    names = [g["name"] for g in resp.json()["data"]]
    assert names == ["已归档计划"]


async def test_delete_goal_sets_null_on_linked_task_and_habit(client, test_user):
    goal = await Goal.create(user_id=test_user.id, name="待删除计划")
    todo = await TodoItem.create(
        title="任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id, goal_id=goal.id,
    )
    habit = await Habit.create(
        user_id=test_user.id, name="习惯", frequency_type=HabitFrequencyType.DAILY, goal_id=goal.id,
    )

    resp = await client.delete("/api/v1/goal/delete", params={"goal_id": goal.id})
    assert resp.status_code == 200
    assert await Goal.filter(id=goal.id).count() == 0

    await todo.refresh_from_db()
    await habit.refresh_from_db()
    assert todo.goal_id is None
    assert habit.goal_id is None


async def test_delete_nonexistent_goal_returns_404(client):
    resp = await client.delete("/api/v1/goal/delete", params={"goal_id": 99999})
    assert resp.status_code == 404


async def test_update_goal_owned_by_other_user_returns_404(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_goal = await Goal.create(user_id=other_user.id, name="别人的计划")

    resp = await client.post("/api/v1/goal/update", json={"id": other_goal.id, "is_archived": True})
    assert resp.status_code == 404


async def test_delete_goal_owned_by_other_user_returns_404(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_goal = await Goal.create(user_id=other_user.id, name="别人的计划")

    resp = await client.delete("/api/v1/goal/delete", params={"goal_id": other_goal.id})
    assert resp.status_code == 404
    assert await Goal.filter(id=other_goal.id).count() == 1
```

- [ ] **Step 2: 跑测试确认现象**

Run: `pytest tests/test_goal.py -vv`
Expected: 全部失败（`404 Not Found`，因为 `/api/v1/goal/*` 还没注册）。

- [ ] **Step 3: 写 `app/schemas/goal.py`**

```python
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    name: str = Field(..., description="计划/目标名称")
    description: Optional[str] = Field(None, description="描述")
    target_date: Optional[date] = Field(None, description="目标完成日期")
    category_id: Optional[int] = Field(None, description="已有分类ID")
    category_name: Optional[str] = Field(None, description="新分类名称，与 category_id 二选一")


class GoalUpdate(BaseModel):
    id: int = Field(..., description="计划ID")
    name: Optional[str] = None
    description: Optional[str] = None
    target_date: Optional[date] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    is_archived: Optional[bool] = None


class GoalOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    target_date: Optional[date] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    is_archived: bool
    task_total: int = Field(0, description="关联任务总数")
    task_completed: int = Field(0, description="关联任务已完成数")
    habit_count: int = Field(0, description="关联习惯数量")

    class Config:
        from_attributes = True
```

- [ ] **Step 4: 写 `app/controllers/goal.py`**

```python
from typing import Dict, List, Optional, Tuple

from tortoise.expressions import Q
from tortoise.functions import Count

from app.controllers.category import category_controller
from app.core.crud import CRUDBase
from app.models.todo import Category, Goal, Habit, TodoItem
from app.schemas.goal import GoalCreate, GoalUpdate


class GoalController(CRUDBase[Goal, GoalCreate, GoalUpdate]):
    def __init__(self):
        super().__init__(model=Goal)

    async def create_goal(self, obj_in: GoalCreate, user_id: int) -> Goal:
        category_id = await self._resolve_category(user_id, obj_in.category_id, obj_in.category_name)
        return await Goal.create(
            user_id=user_id,
            name=obj_in.name,
            description=obj_in.description,
            target_date=obj_in.target_date,
            category_id=category_id,
        )

    async def update_goal(self, goal_id: int, obj_in: GoalUpdate, user_id: int) -> Optional[Goal]:
        goal = await Goal.filter(id=goal_id, user_id=user_id).first()
        if not goal:
            return None

        update_data = obj_in.model_dump(exclude_unset=True, exclude={"id", "category_id", "category_name"})
        if "category_id" in obj_in.model_fields_set or "category_name" in obj_in.model_fields_set:
            update_data["category_id"] = await self._resolve_category(
                user_id, obj_in.category_id, obj_in.category_name
            )

        await goal.update_from_dict(update_data).save()
        return goal

    async def delete_goal(self, goal_id: int, user_id: int) -> bool:
        deleted_count = await Goal.filter(id=goal_id, user_id=user_id).delete()
        return deleted_count > 0

    async def get_active_goals(self, user_id: int) -> List[Goal]:
        return await Goal.filter(user_id=user_id, is_archived=False).order_by("-created_at")

    async def get_archived_goals(self, user_id: int) -> List[Goal]:
        return await Goal.filter(user_id=user_id, is_archived=True).order_by("-updated_at")

    async def to_out_dict(self, goal: Goal) -> dict:
        data = await goal.to_dict()
        category_name = None
        if goal.category_id:
            category = await goal.category
            category_name = category.name if category else None
        data["category_name"] = category_name
        return data

    async def get_task_counts(self, goal_ids: List[int]) -> Dict[int, Tuple[int, int]]:
        """一次聚合查询算出每个计划关联任务的总数/已完成数，避免列表页 N+1"""
        if not goal_ids:
            return {}
        totals = (
            await TodoItem.filter(goal_id__in=goal_ids)
            .annotate(cnt=Count("id"))
            .group_by("goal_id")
            .values("goal_id", "cnt")
        )
        completed = (
            await TodoItem.filter(goal_id__in=goal_ids, is_completed=True)
            .annotate(cnt=Count("id"))
            .group_by("goal_id")
            .values("goal_id", "cnt")
        )
        total_map = {row["goal_id"]: row["cnt"] for row in totals}
        completed_map = {row["goal_id"]: row["cnt"] for row in completed}
        return {gid: (total_map.get(gid, 0), completed_map.get(gid, 0)) for gid in goal_ids}

    async def get_habit_counts(self, goal_ids: List[int]) -> Dict[int, int]:
        """一次聚合查询算出每个计划关联的习惯数量"""
        if not goal_ids:
            return {}
        rows = (
            await Habit.filter(goal_id__in=goal_ids)
            .annotate(cnt=Count("id"))
            .group_by("goal_id")
            .values("goal_id", "cnt")
        )
        return {row["goal_id"]: row["cnt"] for row in rows}

    async def _resolve_category(
        self, user_id: int, category_id: Optional[int], category_name: Optional[str]
    ) -> Optional[int]:
        if category_id is not None:
            category = await Category.filter(
                Q(id=category_id, user_id=user_id) | Q(id=category_id, user_id__isnull=True)
            ).first()
            if category:
                return category_id
        if category_name:
            category = await category_controller.get_or_create(user_id, category_name)
            return category.id
        return None


goal_controller = GoalController()
```

- [ ] **Step 5: 写 `app/api/v1/goal/route.py`**

```python
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from app.controllers.goal import goal_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.schemas.base import Success
from app.schemas.goal import GoalCreate, GoalOut, GoalUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", summary="获取当前用户进行中的计划列表")
async def list_goals(current_user: User = Depends(AuthControl.is_authed)):
    goals = await goal_controller.get_active_goals(current_user.id)
    goal_ids = [g.id for g in goals]
    task_counts = await goal_controller.get_task_counts(goal_ids)
    habit_counts = await goal_controller.get_habit_counts(goal_ids)

    result = []
    for goal in goals:
        data = await goal_controller.to_out_dict(goal)
        task_total, task_completed = task_counts.get(goal.id, (0, 0))
        data["task_total"] = task_total
        data["task_completed"] = task_completed
        data["habit_count"] = habit_counts.get(goal.id, 0)
        result.append(GoalOut(**data).model_dump())
    return Success(data=result)


@router.get("/archived", summary="获取已归档的计划列表")
async def list_archived_goals(current_user: User = Depends(AuthControl.is_authed)):
    goals = await goal_controller.get_archived_goals(current_user.id)
    result = [GoalOut(**(await goal_controller.to_out_dict(g))).model_dump() for g in goals]
    return Success(data=result)


@router.post("/create", summary="创建计划")
async def create_goal(goal_in: GoalCreate, current_user: User = Depends(AuthControl.is_authed)):
    goal = await goal_controller.create_goal(goal_in, current_user.id)
    return Success(data=GoalOut(**(await goal_controller.to_out_dict(goal))).model_dump())


@router.post("/update", summary="更新计划")
async def update_goal(goal_in: GoalUpdate, current_user: User = Depends(AuthControl.is_authed)):
    goal = await goal_controller.update_goal(goal_in.id, goal_in, current_user.id)
    if not goal:
        raise HTTPException(status_code=404, detail="计划不存在")
    return Success(data=GoalOut(**(await goal_controller.to_out_dict(goal))).model_dump())


@router.delete("/delete", summary="删除计划（关联任务/习惯自动解除关联，本身不受影响）")
async def delete_goal(
    goal_id: int = Query(..., description="计划ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    success = await goal_controller.delete_goal(goal_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="计划不存在")
    return Success(msg="删除成功")
```

- [ ] **Step 6: 写 `app/api/v1/goal/__init__.py`**

```python
from fastapi import APIRouter

from .route import router

goal_router = APIRouter()
goal_router.include_router(router, tags=["计划"])

__all__ = ["goal_router"]
```

- [ ] **Step 7: 挂载到 `app/api/v1/__init__.py`**

在现有 import 列表里按字母序插入一行，并在 `v1_router.include_router(...)` 列表末尾新增一行：

```python
from .goal import goal_router
```

```python
v1_router.include_router(goal_router, prefix="/goal", dependencies=[DependPermission])
```

- [ ] **Step 8: 跑测试确认通过**

Run: `pytest tests/test_goal.py -vv`
Expected: `11 passed`

- [ ] **Step 9: 提交**

```bash
git add app/schemas/goal.py app/controllers/goal.py app/api/v1/goal \
        app/api/v1/__init__.py tests/test_goal.py
git commit -m "feat: add Goal CRUD resource (create/update/delete/list/archived)"
```

---

## Task 3: Goal detail 接口

**Files:**
- Modify: `app/schemas/goal.py`
- Modify: `app/controllers/goal.py`
- Modify: `app/api/v1/goal/route.py`
- Modify: `tests/test_goal.py`

**Interfaces:**
- Consumes：Task 2 的 `goal_controller.to_out_dict`。
- Produces：`goal_controller.get_goal_detail(goal_id, user_id) -> Optional[dict]`；`GET /goal/detail?goal_id=` 返回 `GoalDetailOut`（含 `tasks`/`habits` 列表）。Task 8 的 `GoalDetailModal.vue` 直接消费这个端点。

- [ ] **Step 1: 写测试（先写，此时端点还不存在，预期 404）**

在 `tests/test_goal.py` 文件末尾追加：

```python
async def test_get_goal_detail_returns_linked_tasks_and_habits(client, test_user):
    goal = await Goal.create(user_id=test_user.id, name="React 学习计划")
    await TodoItem.create(
        title="完成基础课程", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id,
        goal_id=goal.id, is_completed=True,
    )
    await TodoItem.create(
        title="搭建实践项目", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id,
        goal_id=goal.id,
    )
    await Habit.create(
        user_id=test_user.id, name="每日练习 LeetCode", frequency_type=HabitFrequencyType.WEEKLY_DAYS,
        frequency_config={"days": [1, 3, 5]}, goal_id=goal.id,
    )

    resp = await client.get("/api/v1/goal/detail", params={"goal_id": goal.id})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "React 学习计划"
    task_titles = {t["title"] for t in data["tasks"]}
    assert task_titles == {"完成基础课程", "搭建实践项目"}
    completed_map = {t["title"]: t["is_completed"] for t in data["tasks"]}
    assert completed_map["完成基础课程"] is True
    assert completed_map["搭建实践项目"] is False
    assert len(data["habits"]) == 1
    assert data["habits"][0]["name"] == "每日练习 LeetCode"
    assert data["habits"][0]["frequency_type"] == "weekly_days"
    assert data["habits"][0]["frequency_config"] == {"days": [1, 3, 5]}


async def test_get_goal_detail_with_no_linked_items_returns_empty_lists(client, test_user):
    goal = await Goal.create(user_id=test_user.id, name="空计划")

    resp = await client.get("/api/v1/goal/detail", params={"goal_id": goal.id})
    data = resp.json()["data"]
    assert data["tasks"] == []
    assert data["habits"] == []


async def test_get_goal_detail_for_nonexistent_goal_returns_404(client):
    resp = await client.get("/api/v1/goal/detail", params={"goal_id": 99999})
    assert resp.status_code == 404


async def test_get_goal_detail_owned_by_other_user_returns_404(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_goal = await Goal.create(user_id=other_user.id, name="别人的计划")

    resp = await client.get("/api/v1/goal/detail", params={"goal_id": other_goal.id})
    assert resp.status_code == 404
```

- [ ] **Step 2: 跑测试确认现象**

Run: `pytest tests/test_goal.py -vv`
Expected: 这 4 个新测试失败（`404 Not Found`，因为 `/api/v1/goal/detail` 还没注册）。

- [ ] **Step 3: 修改 `app/schemas/goal.py`，在文件末尾新增**

```python
class GoalTaskItem(BaseModel):
    id: int
    title: str
    is_completed: bool

    class Config:
        from_attributes = True


class GoalHabitItem(BaseModel):
    id: int
    name: str
    frequency_type: str
    frequency_config: Optional[dict] = None

    class Config:
        from_attributes = True


class GoalDetailOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    target_date: Optional[date] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    is_archived: bool
    tasks: List[GoalTaskItem] = Field(default_factory=list)
    habits: List[GoalHabitItem] = Field(default_factory=list)

    class Config:
        from_attributes = True
```

顶部 import 行需要加 `List`：

```python
from datetime import date
from typing import List, Optional
```

- [ ] **Step 4: 修改 `app/controllers/goal.py`，在 `get_habit_counts` 方法之后（`_resolve_category` 之前）新增**

```python
    async def get_goal_detail(self, goal_id: int, user_id: int) -> Optional[dict]:
        goal = await Goal.filter(id=goal_id, user_id=user_id).first()
        if not goal:
            return None
        data = await self.to_out_dict(goal)
        tasks = await TodoItem.filter(goal_id=goal_id).order_by("created_at")
        habits = await Habit.filter(goal_id=goal_id).order_by("created_at")
        data["tasks"] = [{"id": t.id, "title": t.title, "is_completed": t.is_completed} for t in tasks]
        data["habits"] = [
            {"id": h.id, "name": h.name, "frequency_type": h.frequency_type, "frequency_config": h.frequency_config}
            for h in habits
        ]
        return data
```

- [ ] **Step 5: 修改 `app/api/v1/goal/route.py`**

顶部 import 改成：

```python
from app.schemas.goal import GoalCreate, GoalDetailOut, GoalOut, GoalUpdate
```

在 `list_archived_goals` 函数之后（`create_goal` 之前）新增：

```python
@router.get("/detail", summary="获取计划详情（含关联任务/习惯列表）")
async def get_goal_detail(
    goal_id: int = Query(..., description="计划ID"),
    current_user: User = Depends(AuthControl.is_authed),
):
    data = await goal_controller.get_goal_detail(goal_id, current_user.id)
    if not data:
        raise HTTPException(status_code=404, detail="计划不存在")
    return Success(data=GoalDetailOut(**data).model_dump())
```

- [ ] **Step 6: 跑测试确认通过**

Run: `pytest tests/test_goal.py -vv`
Expected: `15 passed`

- [ ] **Step 7: 跑一次全量后端测试，确认没有破坏已有功能**

Run: `pytest -vv`
Expected: 全部通过。

- [ ] **Step 8: 提交**

```bash
git add app/schemas/goal.py app/controllers/goal.py app/api/v1/goal/route.py tests/test_goal.py
git commit -m "feat: add Goal detail endpoint with linked tasks and habits"
```

---

## Task 4: `/todo` 和 `/habit` 接口的 `goal_id` 扩展

**Files:**
- Modify: `app/schemas/todo.py`
- Modify: `app/controllers/todo.py`
- Modify: `app/schemas/habit.py`
- Modify: `app/controllers/habit.py`
- Modify: `tests/test_todo_list_extension.py`
- Modify: `tests/test_habit.py`

**Interfaces:**
- Consumes：Task 1 的 `Goal` 模型。
- Produces：`TodoItemCreate`/`TodoItemUpdate`/`TodoItemOut` 新增 `goal_id`；`HabitCreate`/`HabitUpdate`/`HabitOut` 新增 `goal_id`。Task 10 的 `TaskDetailModal.vue`/`HabitFormModal.vue` 直接读写这个字段。

- [ ] **Step 1: 写测试（先写，此时 `goal_id` 字段还不存在，预期创建成功但请求体里的 `goal_id` 被忽略、跨用户校验测试因为拿不到 404 而失败）**

在 `tests/test_todo_list_extension.py` 顶部的 import 行改成：

```python
from datetime import datetime

from app.models.todo import Goal, Project, QuadrantType, TimeBlock, TodoItem
```

在文件末尾追加：

```python
async def test_create_todo_with_other_user_goal_id_returns_404(client, test_user):
    """cross-user ownership check: create todo with a goal_id owned by another user"""
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_goal = await Goal.create(user_id=other_user.id, name="他人的计划")

    resp = await client.post(
        "/api/v1/todo/create",
        json={
            "title": "越权任务",
            "quadrant_type": "not_urgent_not_important",
            "goal_id": other_goal.id,
        },
    )
    assert resp.status_code == 404


async def test_update_todo_with_other_user_goal_id_returns_404(client, test_user):
    """cross-user ownership check: update todo to link a goal_id owned by another user"""
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_goal = await Goal.create(user_id=other_user.id, name="他人的计划")
    todo = await TodoItem.create(
        title="正常任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id
    )

    resp = await client.post(
        "/api/v1/todo/update",
        json={"id": todo.id, "goal_id": other_goal.id},
    )
    assert resp.status_code == 404


async def test_create_todo_with_own_goal_id_succeeds(client, test_user):
    goal = await Goal.create(user_id=test_user.id, name="我的计划")

    resp = await client.post(
        "/api/v1/todo/create",
        json={"title": "关联任务", "quadrant_type": "not_urgent_not_important", "goal_id": goal.id},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["goal_id"] == goal.id
```

在 `tests/test_habit.py` 文件末尾追加：

```python
async def test_create_habit_with_other_user_goal_id_returns_404(client, test_user):
    from app.models.admin import User
    from app.models.todo import Goal

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_goal = await Goal.create(user_id=other_user.id, name="他人的计划")

    resp = await client.post(
        "/api/v1/habit/create",
        json={"name": "越权习惯", "frequency_type": "daily", "goal_id": other_goal.id},
    )
    assert resp.status_code == 404


async def test_update_habit_with_other_user_goal_id_returns_404(client, test_user):
    from app.models.admin import User
    from app.models.todo import Goal

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_goal = await Goal.create(user_id=other_user.id, name="他人的计划")
    create_resp = await client.post("/api/v1/habit/create", json={"name": "正常习惯", "frequency_type": "daily"})
    habit_id = create_resp.json()["data"]["id"]

    resp = await client.post("/api/v1/habit/update", json={"id": habit_id, "goal_id": other_goal.id})
    assert resp.status_code == 404


async def test_create_habit_with_own_goal_id_succeeds(client, test_user):
    from app.models.todo import Goal

    goal = await Goal.create(user_id=test_user.id, name="我的计划")

    resp = await client.post(
        "/api/v1/habit/create",
        json={"name": "关联习惯", "frequency_type": "daily", "goal_id": goal.id},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["goal_id"] == goal.id
```

- [ ] **Step 2: 跑测试确认现象**

Run: `pytest tests/test_todo_list_extension.py tests/test_habit.py -vv`
Expected: 新增的这几个测试失败（`goal_id` 字段被 pydantic 忽略，跨用户校验测试因为请求成功返回 200 而不是预期的 404 而失败）。

- [ ] **Step 3: 修改 `app/schemas/todo.py`**

`TodoItemBase` 类里 `project_id` 字段后面新增一行：

```python
    project_id: Optional[int] = Field(None, description="所属项目ID，为空则属于收件箱")
    goal_id: Optional[int] = Field(None, description="关联的计划ID，为空表示未关联")
```

`TodoItemUpdate` 类里 `project_id` 字段后面新增一行：

```python
    project_id: Optional[int] = Field(None, description="所属项目ID，传 null 可退回收件箱")
    goal_id: Optional[int] = Field(None, description="关联的计划ID，传 null 可解除关联")
```

（`TodoItemOut` 继承自 `TodoItemBase`，`goal_id` 已经通过继承自动包含，不用重复声明。）

- [ ] **Step 4: 修改 `app/controllers/todo.py`**

顶部 import 加入 `Goal`：

```python
from app.models.todo import Goal, Project, QuadrantType, TimeBlock, TodoItem
```

在 `_validate_project` 方法之后新增：

```python
    async def _validate_goal(self, goal_id: Optional[int], user_id: int) -> None:
        """确保 goal_id 存在且属于当前用户，否则拒绝而不是让外键约束在 DB 层报错"""
        if goal_id is None:
            return
        exists = await Goal.filter(id=goal_id, user_id=user_id).exists()
        if not exists:
            raise HTTPException(status_code=404, detail="计划不存在")
```

`create_todo` 方法里 `await self._validate_project(obj_in.project_id, user_id)` 后面新增一行：

```python
        await self._validate_project(obj_in.project_id, user_id)
        await self._validate_goal(obj_in.goal_id, user_id)
```

`update_todo` 方法里 `if "project_id" in obj_in.model_fields_set: ...` 之后新增：

```python
        if "project_id" in obj_in.model_fields_set:
            await self._validate_project(obj_in.project_id, user_id)
        if "goal_id" in obj_in.model_fields_set:
            await self._validate_goal(obj_in.goal_id, user_id)
```

- [ ] **Step 5: 修改 `app/schemas/habit.py`**

`HabitCreate` 类里 `reminder_time` 字段后面新增一行：

```python
    reminder_time: Optional[time] = Field(None, description="每日提醒时间")
    goal_id: Optional[int] = Field(None, description="关联的计划ID，为空表示未关联")
```

`HabitUpdate` 类里 `reminder_time` 字段后面新增一行：

```python
    reminder_time: Optional[time] = None
    goal_id: Optional[int] = None
```

`HabitOut` 类里 `reminder_time` 字段后面新增一行：

```python
    reminder_time: Optional[time] = None
    goal_id: Optional[int] = None
```

- [ ] **Step 6: 修改 `app/controllers/habit.py`**

顶部 import 加入 `Goal`：

```python
from app.models.todo import Goal, Habit, HabitFrequencyType, TodoItem
```

在 `_validate_frequency_config` 方法之后新增：

```python
    async def _validate_goal(self, goal_id: Optional[int], user_id: int) -> None:
        """确保 goal_id 存在且属于当前用户，否则拒绝而不是让外键约束在 DB 层报错"""
        if goal_id is None:
            return
        exists = await Goal.filter(id=goal_id, user_id=user_id).exists()
        if not exists:
            raise HTTPException(status_code=404, detail="计划不存在")
```

`create_habit` 方法改成：

```python
    async def create_habit(self, obj_in: HabitCreate, user_id: int) -> Habit:
        self._validate_frequency_config(obj_in.frequency_type, obj_in.frequency_config)
        await self._validate_goal(obj_in.goal_id, user_id)
        return await Habit.create(user_id=user_id, **obj_in.model_dump())
```

`update_habit` 方法里，`if "frequency_type" in update_data or "frequency_config" in update_data: ...` 那段之后新增：

```python
        if "frequency_type" in update_data or "frequency_config" in update_data:
            frequency_type = update_data.get("frequency_type", habit.frequency_type)
            frequency_config = update_data.get("frequency_config", habit.frequency_config)
            self._validate_frequency_config(frequency_type, frequency_config)
        if "goal_id" in update_data:
            await self._validate_goal(update_data["goal_id"], user_id)
```

- [ ] **Step 7: 跑测试确认通过**

Run: `pytest tests/test_todo_list_extension.py tests/test_habit.py -vv`
Expected: 全部通过。

- [ ] **Step 8: 跑一次全量后端测试**

Run: `pytest -vv`
Expected: 全部通过。

- [ ] **Step 9: 提交**

```bash
git add app/schemas/todo.py app/controllers/todo.py app/schemas/habit.py app/controllers/habit.py \
        tests/test_todo_list_extension.py tests/test_habit.py
git commit -m "feat: support linking todos and habits to a goal"
```

---

## Task 5: "计划" Menu 记录

**Files:**
- Modify: `app/core/init_app.py`

**Interfaces:**
- Consumes：无。
- Produces：菜单记录 `component="/todo/Goal"`，Task 9 的 `Goal/index.vue` 依赖这条记录才能被路由到。

- [ ] **Step 1: 修改 `app/core/init_app.py`**

在"三期习惯打卡：习惯页菜单"那个独立判断块之后，紧接着新增一个同样风格的独立判断块：

```python
    # 三期计划目标：计划页菜单。独立于上面的判断，保证已经部署过的环境重启后也能自动补上
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        goal_menu = await Menu.filter(name="计划", parent_id=todo_parent_menu.id).first()
        if not goal_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="计划",
                path="goal",
                order=3,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:flag-outline",
                is_hidden=False,
                component="/todo/Goal",
                keepalive=True,
            )
```

- [ ] **Step 2: 手动验证菜单初始化逻辑无语法错误**

Run: `python -c "import app.core.init_app"`
Expected: 无报错。

- [ ] **Step 3: 提交**

```bash
git add app/core/init_app.py
git commit -m "feat: add Goal menu entry"
```

---

## Task 6: 前端 API 客户端（goal）

**Files:**
- Create: `web/src/api/goal.js`
- Modify: `web/src/api/index.js`

**Interfaces:**
- Consumes：Task 2/3/4 的 `/goal/*`。
- Produces：`api.getGoals()`、`api.getArchivedGoals()`、`api.getGoalDetail(id)`、`api.createGoal(data)`、`api.updateGoal(id, data)`、`api.deleteGoal(id)`。Task 7/8/9/10 的组件直接调用。

- [ ] **Step 1: 写 `web/src/api/goal.js`**

```js
import { request } from '@/utils'

/**
 * 计划/目标API接口
 */
export default {
  /**
   * 获取当前用户进行中的计划列表
   * @returns {Promise}
   */
  getGoals: () => request.get('/goal/list'),

  /**
   * 获取已归档的计划列表
   * @returns {Promise}
   */
  getArchivedGoals: () => request.get('/goal/archived'),

  /**
   * 获取计划详情（含关联任务/习惯列表）
   * @param {Number} id
   * @returns {Promise}
   */
  getGoalDetail: (id) => request.get('/goal/detail', { params: { goal_id: id } }),

  /**
   * 创建计划
   * @param {Object} data
   * @returns {Promise}
   */
  createGoal: (data = {}) => request.post('/goal/create', data),

  /**
   * 更新计划
   * @param {Number} id
   * @param {Object} data
   * @returns {Promise}
   */
  updateGoal: (id, data = {}) => request.post('/goal/update', { ...data, id }),

  /**
   * 删除计划（关联任务/习惯自动解除关联，本身不受影响）
   * @param {Number} id
   * @returns {Promise}
   */
  deleteGoal: (id) => request.delete('/goal/delete', { params: { goal_id: id } })
}
```

- [ ] **Step 2: 修改 `web/src/api/index.js`**

在顶部 import 区加入：

```js
import goalApi from './goal'
```

在导出对象的 `...habitApi,` 之后加入：

```js
  ...habitApi,
  // goal（三期计划目标）
  ...goalApi
```

- [ ] **Step 3: lint 检查**

Run: `cd web && pnpm exec eslint src/api/goal.js src/api/index.js`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 4: 提交**

```bash
git add web/src/api/goal.js web/src/api/index.js
git commit -m "feat(web): add goal API client"
```

---

## Task 7: `GoalFormModal.vue`

**Files:**
- Create: `web/src/views/todo/Goal/GoalFormModal.vue`

**Interfaces:**
- Consumes：Task 6 的 `api.createGoal`/`api.updateGoal`；一期已有的 `api.getCategories()`。
- Produces：`GoalFormModal` 组件，props `show`（v-model）、`goal`（非空表示编辑模式），emits `update:show`、`saved`（保存成功后触发，无 payload）。Task 9 的 `Goal/index.vue` 直接引入。

- [ ] **Step 1: 写 `GoalFormModal.vue`**

```vue
<template>
  <n-modal :show="show" preset="card" :title="isEdit ? '编辑计划' : '添加新计划'" style="width: 480px" @update:show="onUpdateShow">
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="80">
      <n-form-item label="名称" path="name">
        <n-input v-model:value="form.name" placeholder="例如：学习新语言，完成XX项目" />
      </n-form-item>
      <n-form-item label="描述">
        <n-input
          v-model:value="form.description"
          type="textarea"
          :rows="3"
          placeholder="简要说明这个计划的目标和意义（可选）"
        />
      </n-form-item>
      <n-form-item label="目标日期">
        <n-date-picker v-model:value="form.target_date" type="date" clearable style="width: 100%" />
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
    </n-form>
    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5em">
        <n-button @click="onUpdateShow(false)">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="handleSubmit">保存计划</n-button>
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
  goal: { type: Object, default: null }
})
const emit = defineEmits(['update:show', 'saved'])

const message = useMessage()
const formRef = ref(null)
const submitting = ref(false)
const categories = ref([])

const isEdit = computed(() => !!props.goal)

const defaultForm = () => ({
  name: '',
  description: '',
  target_date: null,
  category_id: null,
  new_category_name: ''
})
const form = ref(defaultForm())

const rules = {
  name: { required: true, message: '请输入名称', trigger: 'blur' }
}

const categoryOptions = computed(() => categories.value.map((c) => ({ label: c.name, value: c.id })))

const fetchCategories = async () => {
  try {
    const res = await api.getCategories()
    categories.value = res.data || []
  } catch (error) {
    console.error('获取分类列表失败:', error)
    message.error('获取分类列表失败')
  }
}

const onUpdateShow = (value) => emit('update:show', value)

// 纯日期字符串（"YYYY-MM-DD"）不带时间/时区信息，用本地年月日拼接和解析，
// 不能用 new Date(dateString) / toISOString()——那两种写法都会按 UTC 解读/输出，
// 在东八区这类正时区下会把日期往前错移一天
const parseLocalDateString = (dateStr) => {
  if (!dateStr) return null
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d).getTime()
}

const formatLocalDateString = (ms) => {
  if (!ms) return null
  const d = new Date(ms)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const fillFormFromGoal = (goal) => {
  form.value = {
    name: goal.name,
    description: goal.description || '',
    target_date: parseLocalDateString(goal.target_date),
    category_id: goal.category_id,
    new_category_name: ''
  }
}

watch(
  () => props.show,
  (visible) => {
    if (!visible) return
    fetchCategories()
    if (props.goal) {
      fillFormFromGoal(props.goal)
    } else {
      form.value = defaultForm()
    }
  }
)

const handleSubmit = async () => {
  await formRef.value?.validate()
  submitting.value = true
  try {
    const payload = {
      name: form.value.name,
      description: form.value.description || null,
      target_date: formatLocalDateString(form.value.target_date)
    }
    if (form.value.new_category_name.trim()) {
      payload.category_name = form.value.new_category_name.trim()
    } else if (form.value.category_id) {
      payload.category_id = form.value.category_id
    }
    if (isEdit.value) {
      await api.updateGoal(props.goal.id, payload)
    } else {
      await api.createGoal(payload)
    }
    message.success('保存成功')
    emit('saved')
    onUpdateShow(false)
  } finally {
    submitting.value = false
  }
}
</script>
```

- [ ] **Step 2: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/Goal/GoalFormModal.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 提交**

```bash
git add web/src/views/todo/Goal/GoalFormModal.vue
git commit -m "feat(web): add GoalFormModal component"
```

---

## Task 8: `GoalDetailModal.vue`

**Files:**
- Create: `web/src/views/todo/Goal/GoalDetailModal.vue`

**Interfaces:**
- Consumes：Task 6 的 `api.getGoalDetail`；一期已有的 `api.updateTodo`。
- Produces：`GoalDetailModal` 组件，props `show`（v-model）、`goalId`，emits `update:show`。Task 9 的 `Goal/index.vue` 直接引入，只读展示，不需要 `saved` 事件（这个弹窗本身不修改计划字段，只允许勾选关联任务的完成状态）。

- [ ] **Step 1: 写 `GoalDetailModal.vue`**

```vue
<template>
  <n-modal :show="show" preset="card" title="计划详情" style="width: 560px" @update:show="onUpdateShow">
    <n-spin :show="loading">
      <template v-if="detail">
        <h3 style="margin: 0 0 0.3em">{{ detail.name }}</h3>
        <p v-if="detail.target_date" style="opacity: 0.6; font-size: 0.9em; margin: 0 0 0.8em">
          目标日期: {{ detail.target_date }}
        </p>
        <p v-if="detail.description" style="margin: 0 0 1em">{{ detail.description }}</p>

        <n-divider />

        <section>
          <h4 style="font-size: 1em; font-weight: 600; margin-bottom: 0.6em">
            关联任务（{{ completedTaskCount }}/{{ detail.tasks.length }} 完成）
          </h4>
          <div v-for="task in detail.tasks" :key="task.id" class="goal-task-row">
            <n-checkbox :checked="task.is_completed" @update:checked="(v) => toggleTask(task, v)" />
            <span :class="{ 'task-completed': task.is_completed }">{{ task.title }}</span>
          </div>
          <n-empty v-if="!detail.tasks.length" description="还没有关联任务" size="small" />
        </section>

        <n-divider />

        <section>
          <h4 style="font-size: 1em; font-weight: 600; margin-bottom: 0.6em">关联习惯</h4>
          <div v-for="habit in detail.habits" :key="habit.id" class="goal-habit-row">
            <span>{{ habit.name }}</span>
            <span class="habit-frequency">{{ frequencyLabel(habit) }}</span>
          </div>
          <n-empty v-if="!detail.habits.length" description="还没有关联习惯" size="small" />
        </section>
      </template>
    </n-spin>
    <template #footer>
      <n-button @click="onUpdateShow(false)">关闭</n-button>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false },
  goalId: { type: Number, default: null }
})
const emit = defineEmits(['update:show'])

const message = useMessage()
const loading = ref(false)
const detail = ref(null)

const completedTaskCount = computed(() =>
  detail.value ? detail.value.tasks.filter((t) => t.is_completed).length : 0
)

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

const onUpdateShow = (value) => emit('update:show', value)

const loadDetail = async () => {
  if (!props.goalId) return
  loading.value = true
  try {
    const res = await api.getGoalDetail(props.goalId)
    detail.value = res.data
  } catch (error) {
    console.error('获取计划详情失败:', error)
    message.error('获取计划详情失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.show, props.goalId],
  ([visible]) => {
    if (visible) loadDetail()
  }
)

const toggleTask = async (task, checked) => {
  const previous = task.is_completed
  task.is_completed = checked
  try {
    await api.updateTodo(task.id, { is_completed: checked })
  } catch (error) {
    console.error('更新任务状态失败:', error)
    message.error('更新任务状态失败')
    task.is_completed = previous
  }
}
</script>

<style scoped>
.goal-task-row,
.goal-habit-row {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.3em 0;
}
.goal-habit-row {
  justify-content: space-between;
}
.task-completed {
  text-decoration: line-through;
  opacity: 0.5;
}
.habit-frequency {
  font-size: 0.85em;
  opacity: 0.6;
}
</style>
```

- [ ] **Step 2: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/Goal/GoalDetailModal.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 提交**

```bash
git add web/src/views/todo/Goal/GoalDetailModal.vue
git commit -m "feat(web): add GoalDetailModal component"
```

---

## Task 9: `Goal/index.vue` 页面组装

**Files:**
- Create: `web/src/views/todo/Goal/index.vue`

**Interfaces:**
- Consumes：Task 6 的 `api.getGoals`/`api.getArchivedGoals`/`api.updateGoal`/`api.deleteGoal`；Task 7 的 `GoalFormModal.vue`；Task 8 的 `GoalDetailModal.vue`。
- Produces：Menu 记录 `component="/todo/Goal"`（Task 5 已创建）指向的页面入口。

- [ ] **Step 1: 写 `web/src/views/todo/Goal/index.vue`**

```vue
<template>
  <div class="goal-page">
    <div class="goal-header">
      <h2>计划与目标</h2>
      <n-button type="primary" @click="openCreateModal">+ 添加计划</n-button>
    </div>

    <section>
      <h3>进行中的计划</h3>
      <div v-for="goal in goals" :key="goal.id" class="goal-item">
        <div class="goal-content">
          <span class="goal-title">{{ goal.name }}</span>
          <div class="goal-meta">
            <span v-if="goal.target_date">目标日期: {{ goal.target_date }}</span>
            <span v-else>无目标日期</span>
            <span>关联任务: {{ goal.task_completed }}/{{ goal.task_total }}</span>
            <span v-if="goal.habit_count">关联习惯: {{ goal.habit_count }} 个</span>
          </div>
          <div class="progress-bar">
            <div class="progress-bar-inner" :style="{ width: progressPercent(goal) + '%' }"></div>
          </div>
        </div>
        <div class="goal-actions">
          <n-button size="small" @click="openDetail(goal)">查看详情</n-button>
          <n-dropdown trigger="click" :options="activeGoalOptions" @select="(key) => handleAction(key, goal)">
            <button class="goal-more-btn" @click.stop>⋯</button>
          </n-dropdown>
        </div>
      </div>
      <n-empty v-if="!goals.length" description="还没有计划，点右上角添加一个" />
    </section>

    <n-collapse v-if="archivedGoals.length" class="archived-collapse">
      <n-collapse-item title="已归档计划" name="archived">
        <div v-for="goal in archivedGoals" :key="goal.id" class="goal-item archived">
          <div class="goal-content">
            <span class="goal-title">{{ goal.name }}</span>
          </div>
          <div class="goal-actions">
            <n-button size="small" @click="openDetail(goal)">查看详情</n-button>
            <n-button size="small" @click="handleAction('unarchive', goal)">恢复</n-button>
            <n-button size="small" quaternary type="error" @click="handleAction('delete', goal)">删除</n-button>
          </div>
        </div>
      </n-collapse-item>
    </n-collapse>

    <GoalFormModal v-model:show="showFormModal" :goal="editingGoal" @saved="fetchAll" />
    <GoalDetailModal v-model:show="showDetailModal" :goal-id="detailGoalId" />
  </div>
</template>

<script setup>
import { ref, onActivated } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import api from '@/api'
import GoalFormModal from './GoalFormModal.vue'
import GoalDetailModal from './GoalDetailModal.vue'

const message = useMessage()
const dialog = useDialog()

const goals = ref([])
const archivedGoals = ref([])
const showFormModal = ref(false)
const editingGoal = ref(null)
const showDetailModal = ref(false)
const detailGoalId = ref(null)

const activeGoalOptions = [
  { label: '编辑', key: 'edit' },
  { label: '归档', key: 'archive' },
  { label: '删除', key: 'delete' }
]

const progressPercent = (goal) =>
  goal.task_total ? Math.min(100, (goal.task_completed / goal.task_total) * 100) : 0

const fetchGoals = async () => {
  try {
    const res = await api.getGoals()
    goals.value = res.data || []
  } catch (error) {
    console.error('获取计划列表失败:', error)
    message.error('获取计划列表失败')
  }
}

const fetchArchivedGoals = async () => {
  try {
    const res = await api.getArchivedGoals()
    archivedGoals.value = res.data || []
  } catch (error) {
    console.error('获取归档计划失败:', error)
    message.error('获取归档计划失败')
  }
}

const fetchAll = () => Promise.all([fetchGoals(), fetchArchivedGoals()])

const openCreateModal = () => {
  editingGoal.value = null
  showFormModal.value = true
}

const openDetail = (goal) => {
  detailGoalId.value = goal.id
  showDetailModal.value = true
}

const updateGoalField = async (goal, data) => {
  try {
    await api.updateGoal(goal.id, data)
    fetchAll()
  } catch (error) {
    console.error('更新计划失败:', error)
    message.error('更新计划失败')
  }
}

const confirmDelete = (goal) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除计划「${goal.name}」吗？关联的任务和习惯会保留，只是解除关联。`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.deleteGoal(goal.id)
        message.success('删除成功')
        fetchAll()
      } catch (error) {
        console.error('删除计划失败:', error)
        message.error('删除失败')
      }
    }
  })
}

const handleAction = (key, goal) => {
  if (key === 'edit') {
    editingGoal.value = goal
    showFormModal.value = true
  } else if (key === 'archive') {
    updateGoalField(goal, { is_archived: true })
  } else if (key === 'unarchive') {
    updateGoalField(goal, { is_archived: false })
  } else if (key === 'delete') {
    confirmDelete(goal)
  }
}

// onActivated 同时覆盖首次挂载和每次 KeepAlive 重新激活（Vue 首次挂载也会触发 onActivated），
// 不需要再额外写 onMounted，否则首次进入页面会重复请求两次
onActivated(fetchAll)
</script>

<style scoped>
.goal-page {
  max-width: 900px;
}
.goal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5em;
}
.goal-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.8em 0.2em;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
}
.goal-item.archived {
  opacity: 0.7;
}
.goal-content {
  flex: 1;
  min-width: 0;
}
.goal-title {
  font-size: 1em;
  font-weight: 500;
}
.goal-meta {
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
  background: #1890ff;
  transition: width 0.2s;
}
.goal-actions {
  display: flex;
  align-items: center;
  gap: 0.5em;
  flex-shrink: 0;
}
.goal-more-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0.2em 0.5em;
  border-radius: 4px;
  color: inherit;
  opacity: 0.6;
  line-height: 1;
}
.goal-more-btn:hover {
  opacity: 1;
  background: rgba(128, 128, 128, 0.15);
}
.archived-collapse {
  margin-top: 2em;
}
</style>
```

- [ ] **Step 2: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/Goal/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开开发地址，用 `admin`/`123456` 登录。

验证清单：
- "待办事项"菜单下能看到"计划"入口。
- 点"+ 添加计划"，填名称/描述/目标日期/分类后保存，列表里出现该计划，进度条显示 0%（0/0）。
- 点"查看详情"，弹窗展示描述/目标日期，关联任务/习惯列表为空。
- 归档一个计划后从主列表消失，出现在折叠的"已归档计划"区块；点击"恢复"后回到主列表。
- 删除一个计划后确认弹窗正确展示；确认删除后从列表消失。

Expected: 以上行为均符合预期，浏览器控制台无报错。

- [ ] **Step 4: 提交**

```bash
git add web/src/views/todo/Goal/index.vue
git commit -m "feat(web): assemble Goal page with list, archive, and detail modal"
```

---

## Task 10: `TaskDetailModal.vue` + `HabitFormModal.vue` 新增"关联计划"下拉

**Files:**
- Modify: `web/src/views/todo/TaskList/TaskDetailModal.vue`
- Modify: `web/src/views/todo/Habit/HabitFormModal.vue`

**Interfaces:**
- Consumes：Task 6 的 `api.getGoals`/`api.getArchivedGoals`。
- Produces：无新的对外接口——这是两个已有组件的增量修改。

- [ ] **Step 1: 修改 `TaskDetailModal.vue`，在"项目"下拉所在的 grid 容器里新增"关联计划"下拉**

找到：

```html
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
```

改成：

```html
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
          <n-form-item label="关联计划">
            <n-select v-model:value="form.goal_id" :options="goalOptions" clearable placeholder="未关联" />
          </n-form-item>
        </div>
```

- [ ] **Step 2: 新增 `goalOptions` 状态**

找到：

```js
const loading = ref(false)
const saving = ref(false)
const subtasks = ref([])
const newSubtaskTitle = ref('')
const timeBlocks = ref([])
```

改成：

```js
const loading = ref(false)
const saving = ref(false)
const subtasks = ref([])
const newSubtaskTitle = ref('')
const timeBlocks = ref([])
const goalOptions = ref([])
```

- [ ] **Step 3: 表单默认值新增 `goal_id`**

找到：

```js
const form = ref({
  title: '',
  notes: '',
  project_id: null,
  due_date: null,
  reminder_at: null,
  quadrant_type: 'not_urgent_not_important'
})
```

改成：

```js
const form = ref({
  title: '',
  notes: '',
  project_id: null,
  due_date: null,
  reminder_at: null,
  quadrant_type: 'not_urgent_not_important',
  goal_id: null
})
```

- [ ] **Step 4: `loadDetail` 里一并拉取计划下拉选项，并回填 `goal_id`**

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
    timeBlocks.value = await api
      .getTimeBlocks({ todo_item_id: props.todoId })
      .then((res) => res.data || [])
      .catch(() => [])
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
    const [todoRes, subtaskRes] = await Promise.all([api.getTodoById(props.todoId), api.getSubtasks(props.todoId)])
    const todo = todoRes.data
    form.value = {
      title: todo.title,
      notes: todo.notes || '',
      project_id: todo.project_id,
      due_date: toDateValue(todo.due_date),
      reminder_at: toDateValue(todo.reminder_at),
      quadrant_type: todo.quadrant_type,
      goal_id: todo.goal_id
    }
    subtasks.value = (subtaskRes.data || []).map((sub) => ({ ...sub, _originalTitle: sub.title }))
    timeBlocks.value = await api
      .getTimeBlocks({ todo_item_id: props.todoId })
      .then((res) => res.data || [])
      .catch(() => [])
    goalOptions.value = await fetchGoalOptions()
  } catch (error) {
    console.error('获取任务详情失败:', error)
    message.error('获取任务详情失败')
  } finally {
    loading.value = false
  }
}

const fetchGoalOptions = async () => {
  try {
    const [activeRes, archivedRes] = await Promise.all([api.getGoals(), api.getArchivedGoals()])
    const active = (activeRes.data || []).map((g) => ({ label: g.name, value: g.id }))
    const archived = (archivedRes.data || []).map((g) => ({ label: `${g.name}（已归档）`, value: g.id }))
    return [...active, ...archived]
  } catch (error) {
    console.error('获取计划列表失败:', error)
    return []
  }
}
```

- [ ] **Step 5: `handleSave` 提交时带上 `goal_id`**

找到：

```js
    const payload = {
      title: form.value.title,
      notes: form.value.notes,
      project_id: form.value.project_id,
      due_date: form.value.due_date ? new Date(form.value.due_date).toISOString() : null,
      reminder_at: form.value.reminder_at ? new Date(form.value.reminder_at).toISOString() : null,
      quadrant_type: form.value.quadrant_type
    }
```

改成：

```js
    const payload = {
      title: form.value.title,
      notes: form.value.notes,
      project_id: form.value.project_id,
      due_date: form.value.due_date ? new Date(form.value.due_date).toISOString() : null,
      reminder_at: form.value.reminder_at ? new Date(form.value.reminder_at).toISOString() : null,
      quadrant_type: form.value.quadrant_type,
      goal_id: form.value.goal_id
    }
```

- [ ] **Step 6: 修改 `HabitFormModal.vue`，新增"关联计划"下拉**

找到：

```html
      <n-form-item label="目标描述">
        <n-input v-model:value="form.goal_desc" placeholder="例如：30分钟（可选）" />
      </n-form-item>
      <n-form-item label="提醒时间">
```

改成：

```html
      <n-form-item label="目标描述">
        <n-input v-model:value="form.goal_desc" placeholder="例如：30分钟（可选）" />
      </n-form-item>
      <n-form-item label="关联计划">
        <n-select v-model:value="form.goal_id" :options="goalOptions" clearable placeholder="未关联" />
      </n-form-item>
      <n-form-item label="提醒时间">
```

- [ ] **Step 7: 新增 `goalOptions` 状态、`defaultForm`/`fillFormFromHabit` 里新增 `goal_id`、`watch` 里拉取选项、`handleSubmit` 里带上 `goal_id`**

找到：

```js
const message = useMessage()
const formRef = ref(null)
const submitting = ref(false)
```

改成：

```js
const message = useMessage()
const formRef = ref(null)
const submitting = ref(false)
const goalOptions = ref([])
```

找到：

```js
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
```

改成：

```js
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
  reminder_time: null,
  goal_id: null
})
```

找到：

```js
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
```

改成：

```js
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
    reminder_time: habit.reminder_time || null,
    goal_id: habit.goal_id || null
  }
}

const fetchGoalOptions = async () => {
  try {
    const [activeRes, archivedRes] = await Promise.all([api.getGoals(), api.getArchivedGoals()])
    const active = (activeRes.data || []).map((g) => ({ label: g.name, value: g.id }))
    const archived = (archivedRes.data || []).map((g) => ({ label: `${g.name}（已归档）`, value: g.id }))
    goalOptions.value = [...active, ...archived]
  } catch (error) {
    console.error('获取计划列表失败:', error)
  }
}
```

找到：

```js
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
```

改成：

```js
watch(
  () => props.show,
  (visible) => {
    if (!visible) return
    fetchGoalOptions()
    if (props.habit) {
      fillFormFromHabit(props.habit)
    } else {
      form.value = defaultForm()
    }
  }
)
```

找到：

```js
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
```

改成：

```js
    const payload = {
      name: form.value.name,
      icon: form.value.icon || null,
      color_hex: form.value.color_hex,
      frequency_type: form.value.frequency_type,
      frequency_config: buildFrequencyConfig(),
      default_quadrant: form.value.default_quadrant,
      goal_desc: form.value.goal_desc || null,
      reminder_time: form.value.reminder_time || null,
      goal_id: form.value.goal_id
    }
```

- [ ] **Step 8: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/TaskList/TaskDetailModal.vue src/views/todo/Habit/HabitFormModal.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 9: 提交**

```bash
git add web/src/views/todo/TaskList/TaskDetailModal.vue web/src/views/todo/Habit/HabitFormModal.vue
git commit -m "feat(web): add goal association dropdown to task detail and habit form"
```

---

## Task 11: 端到端验证 + 收尾

**Files:**
- 无新增/修改文件（除非验证中发现问题，需要回到对应 Task 修复）。

**Interfaces:**
- Consumes：全部前序 Task 的产出。
- Produces：无——本任务是对整个计划目标子系统的最终确认，对照 `docs/superpowers/specs/2026-08-11-task-system-phase3-goal-design.md` 的验收标准逐条过一遍。

- [ ] **Step 1: 跑全量后端测试**

Run: `pytest -vv`
Expected: 全部通过（含一期/二期/三期上遗留测试 + 本阶段新增的 `test_goal.py` + `test_todo_list_extension.py`/`test_habit.py` 的新增用例）。

- [ ] **Step 2: 跑前端 lint（限定改动文件）**

Run: `cd web && pnpm exec eslint src/api/goal.js src/api/index.js src/views/todo/Goal/GoalFormModal.vue src/views/todo/Goal/GoalDetailModal.vue src/views/todo/Goal/index.vue src/views/todo/TaskList/TaskDetailModal.vue src/views/todo/Habit/HabitFormModal.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 用管理后台把新增 API 分配给角色**

启动后端（`python run.py`）后，用 `admin`/`123456` 登录管理后台，进入"系统管理 → API 管理"点击"刷新 API"，确认新增的 `/api/v1/goal/*` 六个接口出现在列表里；进入"角色管理"，把这些接口分配给测试要用的角色（超级管理员本身跳过 API 校验，不受影响）。

- [ ] **Step 4: 浏览器端到端走查，对照 spec 验收标准**

Run: `cd web && pnpm dev`，浏览器登录后依次验证 `docs/superpowers/specs/2026-08-11-task-system-phase3-goal-design.md` 的"验收标准"一节：新建计划、任务详情弹窗关联计划后进度更新、习惯弹窗关联计划后 `habit_count` 更新、计划详情弹窗的任务勾选联动、归档/恢复、删除后关联解除但任务/习惯本身保留。

Expected: 全部符合预期。若发现偏差，回到对应 Task 定位问题、修复、重新跑一遍该 Task 的测试/验证步骤，再继续。

- [ ] **Step 5: 如果验证过程中做了修复，提交**

```bash
git add -A
git commit -m "fix: address issues found during phase3-goal end-to-end verification"
```

（如果 Step 4 全部一次通过、没有任何修改，跳过本步。）
