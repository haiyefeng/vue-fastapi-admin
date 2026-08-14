# 四期（下）：今日概览（Dashboard）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地蓝图四期（下）——今日概览（Dashboard）：聚合今日日程/今日待办/今日习惯的只读接口、今日概览页、快速添加入口、待办事项模块内默认首页调整。这是蓝图规划的最后一块。

**Architecture:** 后端先行（聚合接口，无新表，复用一至三期已有的 `TodoItem`/`TimeBlock`/`Habit` controller 方法），前端随后（api 客户端 → 单文件今日概览页）。沿用 `goal`/`review` 模块已确立的扁平路由风格、`user_id` 数据隔离、`Menu` 驱动前端路由的既有约定。

**Tech Stack:** FastAPI + Tortoise ORM（后端），Vue 3 `<script setup>` + Naive UI（前端），pytest + httpx（后端测试）。

## Global Constraints

- 本分支从 `feat-task`（已含一至三期、四期上/回顾总结全部内容）fork。
- 新路由挂 `dependencies=[DependPermission]`，处理函数内 `Depends(AuthControl.is_authed)` 取当前用户，所有查询按 `user_id` 过滤——与 `goal`/`habit`/`review` 模块完全一致。
- **"默认首页"只调整待办事项模块内部**：只改"待办事项"父菜单的 `redirect`（从 `/todo/quadrant` 改为 `/todo/dashboard`），不改动整个平台登录后的全局落地页（`/` 仍然重定向到 `/workbench`）。
- **今日待办排除习惯生成的待办**（`habit_id__isnull=True`），避免和"今日习惯"区块重复展示同一件事——习惯待办已经在"今日习惯"区块里以打卡按钮的形式出现。
- **今日概览是习惯惰性生成的合法触发点**，与 Goal 详情、Review 数据回顾"明确不触发生成"的既有边界规则相反——调用 `habit_controller.list_active_with_status` 会顺带触发当天该生成而未生成的习惯待办，这是蓝图原文就规定的行为（"读取今天相关数据的接口：待办列表、今日概览、习惯页"），不是新引入的例外，实现时不要"修正"成不触发。
- **今日待办的排序**：`due_date` 非空的排前面（按 `due_date` 升序），`due_date` 为空但靠今日时间块入选的排最后。**不能用 `TodoItem.filter(...).order_by("due_date")` 直接返回**——SQLite 和 MySQL 对 `ORDER BY` 中 `NULL` 值默认排序位置不同且都不满足"排最后"的要求（已实测 SQLite 默认把 `NULL` 排最前），必须在 Python 侧用 `sorted(tasks, key=lambda t: (t.due_date is None, t.due_date))` 重排，这样可移植且已验证正确（`None` 之间比较不会因为 tuple 比较短路而抛异常）。
- 新建的 Vue 页面文件名为 `index.vue` 时必须显式 `defineOptions({ name: '<菜单名称>' })`——这个仓库在三/四期上都踩过"`index.vue` 文件名导致 `KeepAlive` 组件名对不上"的坑，这次从一开始就写对，不再重复踩坑。
- 前端不写 `<router-link>`（这个仓库里几乎不用这个写法，只有一处历史遗留），统一用 `useRouter()` + `router.push(...)`，与 `views/error-page/*.vue` 的既有导航写法一致。

---

### Task 1: `GET /dashboard/today` 聚合接口

**Files:**
- Create: `app/schemas/dashboard.py`
- Create: `app/controllers/dashboard.py`
- Create: `app/api/v1/dashboard/route.py`
- Create: `app/api/v1/dashboard/__init__.py`
- Modify: `app/api/v1/__init__.py`
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes：`time_block_controller.list_by_date_range(user_id, start_date, end_date)`（二期已有）、`habit_controller.list_active_with_status(user_id)`（三期已有，内部会触发 `ensure_today_generated`）。
- Produces：`dashboard_controller.get_today_overview(user_id) -> dict`；`GET /dashboard/today` 路由，返回 `{date, schedule, tasks, habits}`。Task 3 的前端 api 客户端直接消费这个接口。

- [ ] **Step 1: 写 `app/schemas/dashboard.py`**

```python
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.timeblock import TimeBlockOut


class TodayTaskItem(BaseModel):
    id: int
    title: str
    due_date: Optional[datetime] = None
    quadrant_type: str
    project_id: Optional[int] = None

    class Config:
        from_attributes = True


class TodayHabitItem(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    color_hex: Optional[str] = None
    frequency_type: str
    frequency_config: Optional[dict] = None
    today_todo_id: int
    today_completed: bool
    streak: Optional[int] = None
    week_progress: Optional[str] = None


class TodayOverviewOut(BaseModel):
    date: date
    schedule: List[TimeBlockOut] = Field(default_factory=list)
    tasks: List[TodayTaskItem] = Field(default_factory=list)
    habits: List[TodayHabitItem] = Field(default_factory=list)
```

`schedule` 字段直接复用二期已有的 `TimeBlockOut`（`id`/`todo_item_id`/`start_time`/`end_time`/`title`/`quadrant_type`），不新建重复的 schema。

- [ ] **Step 2: 写 `app/controllers/dashboard.py`**

```python
from datetime import date, datetime, time
from typing import Any, Dict, List

from app.controllers.habit import habit_controller
from app.controllers.timeblock import time_block_controller
from app.models.todo import TimeBlock, TodoItem


class DashboardController:
    async def get_today_overview(self, user_id: int) -> dict:
        today = date.today()
        return {
            "date": today,
            "schedule": await self._get_today_schedule(user_id, today),
            "tasks": await self._get_today_tasks(user_id, today),
            "habits": await self._get_today_habits(user_id),
        }

    async def _get_today_schedule(self, user_id: int, today: date) -> List[dict]:
        blocks = await time_block_controller.list_by_date_range(user_id, today, today)
        return [
            {
                "id": b.id,
                "todo_item_id": b.todo_item_id,
                "start_time": b.start_time,
                "end_time": b.end_time,
                "title": b.todo_item.title,
                "quadrant_type": b.todo_item.quadrant_type,
            }
            for b in blocks
        ]

    async def _get_today_tasks(self, user_id: int, today: date) -> List[TodoItem]:
        """今日待办：due_date 落在今天，或存在今天的时间块（取并集），排除已完成、排除习惯生成的待办。
        due_date 非空的按时间升序排前面，due_date 为空但靠时间块入选的排最后——用 Python 侧排序，
        不依赖数据库 ORDER BY 对 NULL 的默认位置（SQLite/MySQL 行为不一致，且都不满足这里的排序要求）"""
        day_start = datetime.combine(today, time.min)
        day_end = datetime.combine(today, time.max)

        due_today_ids = await TodoItem.filter(
            user_id=user_id,
            habit_id__isnull=True,
            is_completed=False,
            due_date__gte=day_start,
            due_date__lte=day_end,
        ).values_list("id", flat=True)

        scheduled_today_ids = await TimeBlock.filter(
            user_id=user_id, start_time__gte=day_start, start_time__lte=day_end,
        ).values_list("todo_item_id", flat=True)

        combined_ids = set(due_today_ids) | set(scheduled_today_ids)
        if not combined_ids:
            return []

        tasks = await TodoItem.filter(id__in=combined_ids, is_completed=False, habit_id__isnull=True)
        return sorted(tasks, key=lambda t: (t.due_date is None, t.due_date))

    async def _get_today_habits(self, user_id: int) -> List[Dict[str, Any]]:
        """今日习惯：today_todo_id 非空的（暂停中的、或按频率规则今天不该做的habit会是 None，排除）。
        list_active_with_status 内部会触发 ensure_today_generated——今日概览是这个惰性生成检查
        的合法触发点之一，不是需要规避的副作用"""
        habits = await habit_controller.list_active_with_status(user_id)
        return [h for h in habits if h.get("today_todo_id") is not None]


dashboard_controller = DashboardController()
```

- [ ] **Step 3: 写 `app/api/v1/dashboard/route.py`**

```python
import logging

from fastapi import APIRouter, Depends

from app.controllers.dashboard import dashboard_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.schemas.base import Success
from app.schemas.dashboard import TodayOverviewOut

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/today", summary="获取今日概览（今日日程/今日待办/今日习惯）")
async def get_today_overview(current_user: User = Depends(AuthControl.is_authed)):
    data = await dashboard_controller.get_today_overview(current_user.id)
    return Success(data=TodayOverviewOut(**data).model_dump())
```

- [ ] **Step 4: 写 `app/api/v1/dashboard/__init__.py`**

```python
from fastapi import APIRouter

from .route import router

dashboard_router = APIRouter()
dashboard_router.include_router(router, tags=["今日概览"])

__all__ = ["dashboard_router"]
```

- [ ] **Step 5: 注册路由，修改 `app/api/v1/__init__.py`**

找到：

```python
from .category import category_router
from .depts import depts_router
```

改成：

```python
from .category import category_router
from .dashboard import dashboard_router
from .depts import depts_router
```

找到：

```python
v1_router.include_router(review_router, prefix="/review", dependencies=[DependPermission])
```

改成：

```python
v1_router.include_router(review_router, prefix="/review", dependencies=[DependPermission])
v1_router.include_router(dashboard_router, prefix="/dashboard", dependencies=[DependPermission])
```

- [ ] **Step 6: 写测试 `tests/test_dashboard.py`**

```python
from datetime import date, datetime, time, timedelta

from app.models.admin import User
from app.models.todo import Habit, HabitFrequencyType, QuadrantType, TimeBlock, TodoItem


async def test_today_overview_schedule_from_time_blocks(client, test_user):
    todo = await TodoItem.create(
        title="团队会议", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT
    )
    today = date.today()
    start = datetime.combine(today, time(9, 0))
    end = datetime.combine(today, time(10, 30))
    await TimeBlock.create(todo_item_id=todo.id, user_id=test_user.id, start_time=start, end_time=end)

    resp = await client.get("/api/v1/dashboard/today")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["date"] == today.isoformat()
    assert len(data["schedule"]) == 1
    assert data["schedule"][0]["title"] == "团队会议"
    assert data["schedule"][0]["todo_item_id"] == todo.id


async def test_today_overview_tasks_due_today(client, test_user):
    today = date.today()
    await TodoItem.create(
        title="今天到期", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT,
        due_date=datetime.combine(today, time(18, 0)),
    )

    resp = await client.get("/api/v1/dashboard/today")
    tasks = resp.json()["data"]["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "今天到期"


async def test_today_overview_tasks_scheduled_today_without_due_date(client, test_user):
    todo = await TodoItem.create(
        title="今天有时间块但无截止日期", user_id=test_user.id, quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT
    )
    today = date.today()
    await TimeBlock.create(
        todo_item_id=todo.id, user_id=test_user.id,
        start_time=datetime.combine(today, time(14, 0)), end_time=datetime.combine(today, time(15, 0)),
    )

    resp = await client.get("/api/v1/dashboard/today")
    tasks = resp.json()["data"]["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "今天有时间块但无截止日期"


async def test_today_overview_tasks_excludes_completed(client, test_user):
    today = date.today()
    await TodoItem.create(
        title="已完成", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT,
        due_date=datetime.combine(today, time(18, 0)), is_completed=True,
    )

    resp = await client.get("/api/v1/dashboard/today")
    assert resp.json()["data"]["tasks"] == []


async def test_today_overview_tasks_excludes_habit_generated(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="打卡", frequency_type=HabitFrequencyType.DAILY)
    today = date.today()
    await TodoItem.create(
        title="习惯待办", user_id=test_user.id, habit_id=habit.id, quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT,
        due_date=datetime.combine(today, time(18, 0)), generated_date=today,
    )

    resp = await client.get("/api/v1/dashboard/today")
    assert resp.json()["data"]["tasks"] == []


async def test_today_overview_tasks_excludes_due_tomorrow(client, test_user):
    tomorrow = date.today() + timedelta(days=1)
    await TodoItem.create(
        title="明天到期", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT,
        due_date=datetime.combine(tomorrow, time(9, 0)),
    )

    resp = await client.get("/api/v1/dashboard/today")
    assert resp.json()["data"]["tasks"] == []


async def test_today_overview_tasks_ordered_due_date_first_no_due_date_last(client, test_user):
    today = date.today()
    todo_no_due = await TodoItem.create(
        title="无截止日期但有时间块", user_id=test_user.id, quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT
    )
    await TimeBlock.create(
        todo_item_id=todo_no_due.id, user_id=test_user.id,
        start_time=datetime.combine(today, time(8, 0)), end_time=datetime.combine(today, time(9, 0)),
    )
    await TodoItem.create(
        title="下午到期", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT,
        due_date=datetime.combine(today, time(18, 0)),
    )
    await TodoItem.create(
        title="上午到期", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT,
        due_date=datetime.combine(today, time(9, 0)),
    )

    resp = await client.get("/api/v1/dashboard/today")
    titles = [t["title"] for t in resp.json()["data"]["tasks"]]
    assert titles == ["上午到期", "下午到期", "无截止日期但有时间块"]


async def test_today_overview_habits_only_includes_scheduled_today(client, test_user):
    await Habit.create(user_id=test_user.id, name="每天", frequency_type=HabitFrequencyType.DAILY)
    today_weekday = date.today().isoweekday()
    other_weekday = (today_weekday % 7) + 1  # 保证不等于今天的 ISO 星期几
    await Habit.create(
        user_id=test_user.id, name="固定某天", frequency_type=HabitFrequencyType.WEEKLY_DAYS,
        frequency_config={"days": [other_weekday]},
    )

    resp = await client.get("/api/v1/dashboard/today")
    habits = resp.json()["data"]["habits"]
    assert len(habits) == 1
    assert habits[0]["name"] == "每天"
    assert habits[0]["today_todo_id"] is not None


async def test_today_overview_habits_excludes_paused(client, test_user):
    await Habit.create(
        user_id=test_user.id, name="已暂停", frequency_type=HabitFrequencyType.DAILY, is_paused=True
    )

    resp = await client.get("/api/v1/dashboard/today")
    assert resp.json()["data"]["habits"] == []


async def test_today_overview_triggers_habit_generation(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="打卡", frequency_type=HabitFrequencyType.DAILY)

    await client.get("/api/v1/dashboard/today")

    assert await TodoItem.filter(habit_id=habit.id, generated_date=date.today()).count() == 1


async def test_today_overview_isolated_per_user(client, test_user):
    other_user = await User.create(username="other", email="other@example.com", password="x")
    today = date.today()
    await TodoItem.create(
        title="别人的任务", user_id=other_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT,
        due_date=datetime.combine(today, time(18, 0)),
    )
    await Habit.create(user_id=other_user.id, name="别人的习惯", frequency_type=HabitFrequencyType.DAILY)

    resp = await client.get("/api/v1/dashboard/today")
    data = resp.json()["data"]
    assert data["tasks"] == []
    assert data["habits"] == []
```

- [ ] **Step 7: 运行测试**

Run: `make test`

Expected: 全部通过，129 passed（118 + 本任务新增 11 个）。

- [ ] **Step 8: 提交**

```bash
git add app/schemas/dashboard.py app/controllers/dashboard.py app/api/v1/dashboard/ app/api/v1/__init__.py tests/test_dashboard.py
git commit -m "feat: add today-overview aggregation endpoint"
```

---

### Task 2: "今日" Menu 记录 + 待办事项默认页调整

**Files:**
- Modify: `app/core/init_app.py`

**Interfaces:**
- Consumes：无。
- Produces：Menu 记录 `name="今日"`，`component="/todo/Dashboard"`，Task 4 的页面组件挂载点；"待办事项"父菜单 `redirect` 更新为 `/todo/dashboard`。

- [ ] **Step 1: 修改初次建库时的默认 redirect**

找到：

```python
        todo_parent_menu = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="待办事项",
            path="/todo",
            order=3,
            parent_id=0,
            icon="material-symbols:featured-play-list-outline",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/todo/quadrant",
        )
```

改成：

```python
        todo_parent_menu = await Menu.create(
            menu_type=MenuType.CATALOG,
            name="待办事项",
            path="/todo",
            order=3,
            parent_id=0,
            icon="material-symbols:featured-play-list-outline",
            is_hidden=False,
            component="Layout",
            keepalive=False,
            redirect="/todo/dashboard",
        )
```

- [ ] **Step 2: 新增"今日"菜单记录 + 已存在数据库的 redirect 补丁**

找到：

```python
    # 四期回顾总结：回顾页菜单。独立于上面的判断，保证已经部署过的环境重启后也能自动补上
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        review_menu = await Menu.filter(name="回顾总结", parent_id=todo_parent_menu.id).first()
        if not review_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="回顾总结",
                path="review",
                order=4,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:rate-review-outline",
                is_hidden=False,
                component="/todo/Review",
                keepalive=True,
            )


async def init_apis():
```

改成：

```python
    # 四期回顾总结：回顾页菜单。独立于上面的判断，保证已经部署过的环境重启后也能自动补上
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        review_menu = await Menu.filter(name="回顾总结", parent_id=todo_parent_menu.id).first()
        if not review_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="回顾总结",
                path="review",
                order=4,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:rate-review-outline",
                is_hidden=False,
                component="/todo/Review",
                keepalive=True,
            )

    # 四期今日概览：今日页菜单 + 把待办事项父菜单默认页从四象限切到今日概览。
    # 独立于上面的判断，保证已经部署过的环境重启后也能自动补上；redirect 的更新对已经存在的
    # 父菜单记录也生效，不只是全新建库时走 Step 1 的初始值。
    todo_parent_menu = await Menu.filter(name="待办事项").first()
    if todo_parent_menu:
        dashboard_menu = await Menu.filter(name="今日", parent_id=todo_parent_menu.id).first()
        if not dashboard_menu:
            await Menu.create(
                menu_type=MenuType.MENU,
                name="今日",
                path="dashboard",
                order=-1,
                parent_id=todo_parent_menu.id,
                icon="material-symbols:today-outline",
                is_hidden=False,
                component="/todo/Dashboard",
                keepalive=True,
            )
        if todo_parent_menu.redirect != "/todo/dashboard":
            todo_parent_menu.redirect = "/todo/dashboard"
            await todo_parent_menu.save()


async def init_apis():
```

`order=-1` 让"今日"在侧边栏排在"任务"（`order=0`）之前，匹配原型图的菜单顺序；不需要为了插队去重新编号"任务/日历/习惯/计划/回顾总结"这 5 条已有记录的 `order` 值——前端排序（`SideMenu.vue`）是纯数字比较，负数完全合法。

- [ ] **Step 3: 运行测试确认无回归**

Run: `make test`

Expected: 129 passed（Menu 初始化逻辑没有专门的单测覆盖，这一步只确认改动没有引入语法错误或破坏其他初始化流程）。

- [ ] **Step 4: 提交**

```bash
git add app/core/init_app.py
git commit -m "feat: add 今日 menu entry and switch todo module default page to dashboard"
```

---

### Task 3: 前端 API 客户端（dashboard）

**Files:**
- Create: `web/src/api/dashboard.js`
- Modify: `web/src/api/index.js`

**Interfaces:**
- Consumes：Task 1 的 `GET /dashboard/today`。
- Produces：`api.getTodayOverview`，Task 4 直接使用。

- [ ] **Step 1: 写 `web/src/api/dashboard.js`**

```js
import { request } from '@/utils'

/**
 * 今日概览API接口
 */
export default {
  /**
   * 获取今日概览（今日日程/今日待办/今日习惯）
   * @returns {Promise}
   */
  getTodayOverview: () => request.get('/dashboard/today')
}
```

- [ ] **Step 2: 注册到 `web/src/api/index.js`**

找到：

```js
import reviewApi from './review'
```

改成：

```js
import reviewApi from './review'
import dashboardApi from './dashboard'
```

找到：

```js
  // review（四期回顾总结）
  ...reviewApi,
}
```

改成：

```js
  // review（四期回顾总结）
  ...reviewApi,
  // dashboard（四期今日概览）
  ...dashboardApi,
}
```

- [ ] **Step 3: lint 检查**

Run: `cd web && pnpm exec eslint src/api/dashboard.js src/api/index.js`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 4: 提交**

```bash
git add web/src/api/dashboard.js web/src/api/index.js
git commit -m "feat(web): add dashboard api client"
```

---

### Task 4: `Dashboard/index.vue` 今日概览页

**Files:**
- Create: `web/src/views/todo/Dashboard/index.vue`

**Interfaces:**
- Consumes：Task 3 的 `api.getTodayOverview`；一期已有的 `api.getProjects`/`api.createTodo`/`api.updateTodo`；`TaskList/TaskDetailModal.vue`（复用，props `show`/`todoId`/`projects`，emits `update:show`/`saved`/`deleted`）。
- Produces：Menu 记录 `component="/todo/Dashboard"`（Task 2 已创建）指向的页面入口。

- [ ] **Step 1: 写 `web/src/views/todo/Dashboard/index.vue`**

```vue
<template>
  <div class="dashboard-page">
    <div class="dashboard-header">
      <h2>今日概览</h2>
      <p class="dashboard-date">{{ todayLabel }}</p>
    </div>

    <section class="quick-add">
      <n-input
        v-model:value="quickAddTitle"
        placeholder="添加任务到收件箱 (按 Enter 保存)"
        @keyup.enter="handleQuickAdd"
      />
      <n-button type="primary" @click="handleQuickAdd">添加</n-button>
    </section>

    <div class="dashboard-grid">
      <section class="dashboard-card">
        <h3>今日日程</h3>
        <div
          v-for="block in schedule"
          :key="block.id"
          class="schedule-row"
          @click="openDetail(block.todo_item_id)"
        >
          <span class="quadrant-dot" :style="{ background: quadrantColor(block.quadrant_type) }"></span>
          <span>{{ formatTimeRange(block.start_time, block.end_time) }} {{ block.title }}</span>
        </div>
        <n-empty v-if="!schedule.length" description="今天还没有安排" size="small">
          <template #extra>
            <n-button text type="primary" @click="router.push('/todo/schedule')">查看完整日历</n-button>
          </template>
        </n-empty>
      </section>

      <section class="dashboard-card">
        <h3>今日待办</h3>
        <div v-for="task in tasks" :key="task.id" class="task-row">
          <n-checkbox :checked="false" @update:checked="() => toggleTaskComplete(task)" />
          <span class="quadrant-dot" :style="{ background: quadrantColor(task.quadrant_type) }"></span>
          <span class="task-title" @click="openDetail(task.id)">{{ task.title }}</span>
        </div>
        <n-empty v-if="!tasks.length" description="今天没有待办事项" size="small">
          <template #extra>
            <n-button text type="primary" @click="router.push('/todo/tasks')">查看所有任务</n-button>
          </template>
        </n-empty>
      </section>

      <section class="dashboard-card">
        <h3>今日习惯</h3>
        <div v-for="habit in habits" :key="habit.id" class="habit-row">
          <div class="habit-content">
            <span class="habit-name">{{ habit.name }}</span>
            <span class="habit-meta">{{ habitMetaLabel(habit) }}</span>
          </div>
          <n-button
            size="small"
            :type="habit.today_completed ? 'default' : 'primary'"
            :disabled="habit.today_completed"
            @click="checkInHabit(habit)"
          >
            {{ habit.today_completed ? '已打卡 ✓' : '打卡' }}
          </n-button>
        </div>
        <n-empty v-if="!habits.length" description="今天没有需要打卡的习惯" size="small">
          <template #extra>
            <n-button text type="primary" @click="router.push('/todo/habit')">管理习惯</n-button>
          </template>
        </n-empty>
      </section>
    </div>

    <TaskDetailModal
      v-model:show="detailShow"
      :todo-id="detailTodoId"
      :projects="projectList"
      @saved="loadToday"
      @deleted="loadToday"
    />
  </div>
</template>

<script setup>
import { ref, computed, onActivated, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import api from '@/api'
import TaskDetailModal from '../TaskList/TaskDetailModal.vue'

defineOptions({ name: '今日' })

const router = useRouter()
const message = useMessage()

const schedule = ref([])
const tasks = ref([])
const habits = ref([])
const quickAddTitle = ref('')
const detailShow = ref(false)
const detailTodoId = ref(null)
const projectList = ref([])

const quadrantMeta = {
  urgent_important: '#f5222d',
  urgent_not_important: '#faad14',
  important_not_urgent: '#1890ff',
  not_urgent_not_important: '#909399'
}
const quadrantColor = (type) => quadrantMeta[type] || '#909399'

const todayLabel = computed(() => {
  const now = new Date()
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  return `${weekdays[now.getDay()]}，${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日`
})

const formatTimeRange = (start, end) => {
  const pad = (n) => String(n).padStart(2, '0')
  const s = new Date(start)
  const e = new Date(end)
  return `${pad(s.getHours())}:${pad(s.getMinutes())}–${pad(e.getHours())}:${pad(e.getMinutes())}`
}

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

const habitMetaLabel = (habit) => {
  const parts = [frequencyLabel(habit)]
  if (habit.streak !== null && habit.streak !== undefined) parts.push(`连续坚持 ${habit.streak} 天`)
  if (habit.week_progress) parts.push(`本周 ${habit.week_progress}`)
  return parts.join(' · ')
}

const loadToday = async () => {
  try {
    const res = await api.getTodayOverview()
    schedule.value = res.data.schedule || []
    tasks.value = res.data.tasks || []
    habits.value = res.data.habits || []
  } catch (error) {
    console.error('加载今日概览失败:', error)
    message.error('加载今日概览失败')
  }
}

const fetchProjects = async () => {
  try {
    const res = await api.getProjects()
    projectList.value = res.data || []
  } catch (error) {
    console.error('获取项目列表失败:', error)
  }
}

const handleQuickAdd = async () => {
  const title = quickAddTitle.value.trim()
  if (!title) return
  try {
    await api.createTodo({ title, quadrant_type: 'not_urgent_not_important' })
    quickAddTitle.value = ''
    message.success('已添加')
    loadToday()
  } catch (error) {
    console.error('添加任务失败:', error)
    message.error('添加任务失败')
  }
}

const toggleTaskComplete = async (task) => {
  try {
    await api.updateTodo(task.id, { is_completed: true })
    tasks.value = tasks.value.filter((t) => t.id !== task.id)
  } catch (error) {
    console.error('更新任务状态失败:', error)
    message.error('更新任务状态失败')
  }
}

const checkInHabit = async (habit) => {
  try {
    await api.updateTodo(habit.today_todo_id, { is_completed: true })
    habit.today_completed = true
  } catch (error) {
    console.error('打卡失败:', error)
    message.error('打卡失败')
  }
}

const openDetail = (todoId) => {
  detailTodoId.value = todoId
  detailShow.value = true
}

// 关闭详情弹窗时也刷新今日概览，覆盖弹窗内的局部修改（如把截止日期改到别的日期、删除时间块）
// 未必会触发 @saved/@deleted 的情况，与 Schedule/index.vue 的既有写法一致
watch(detailShow, (visible) => {
  if (!visible) loadToday()
})

onActivated(() => {
  loadToday()
  fetchProjects()
})
</script>

<style scoped>
.dashboard-page {
  max-width: 1100px;
}
.dashboard-header {
  margin-bottom: 1em;
}
.dashboard-header h2 {
  margin: 0;
}
.dashboard-date {
  opacity: 0.6;
  margin: 0.2em 0 0;
}
.quick-add {
  display: flex;
  gap: 0.5em;
  margin-bottom: 1.5em;
}
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5em;
}
.dashboard-card h3 {
  margin: 0 0 0.8em;
  font-size: 1em;
}
.schedule-row {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.4em 0;
  cursor: pointer;
}
.task-row {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.4em 0;
}
.task-title {
  cursor: pointer;
}
.quadrant-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.habit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.5em 0;
}
.habit-content {
  display: flex;
  flex-direction: column;
  gap: 0.2em;
}
.habit-meta {
  font-size: 0.82em;
  opacity: 0.7;
}
</style>
```

- [ ] **Step 2: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/Dashboard/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开开发地址，用 `admin`/`123456` 登录。

验证清单：
- 点击侧边栏"待办事项"菜单，默认进入今日概览页（不是四象限）；"今日"是待办事项子菜单里的第一项。
- 快速添加框输入标题回车，任务创建成功（去任务列表页收件箱能看到），今日概览三个区块不受影响（因为没设截止日期/时间块）。
- 在日历页给一个任务拖拽排一个今天的时间块，回到今日概览，"今日日程"能看到这条；点击能打开任务详情弹窗。
- 在任务详情弹窗把某个任务的截止日期设为今天，保存后回到今日概览，"今日待办"能看到它；勾选后从列表消失。
- 有一个今天该打卡的习惯时，"今日习惯"能看到它；点击"打卡"后按钮变为"已打卡 ✓"禁用态。
- 三个区块都为空时，分别显示"查看完整日历"/"查看所有任务"/"管理习惯"链接，点击能跳转到对应页面。
- 离开今日概览切到其他菜单再切回来（KeepAlive 场景），数据正确重新加载。
- 浏览器控制台无报错。

Expected: 以上行为均符合预期。

- [ ] **Step 4: 提交**

```bash
git add web/src/views/todo/Dashboard/index.vue
git commit -m "feat(web): add today overview dashboard page"
```

---

### Task 5: 端到端验证 + 收尾

**Files:**
- 无新增/修改文件（除非验证中发现问题，需要回到对应 Task 修复）。

**Interfaces:**
- Consumes：全部前序 Task 的产出。
- Produces：无——本任务是对整个今日概览子系统、以及蓝图四期整体的最终确认，对照 `docs/superpowers/specs/2026-08-15-task-system-phase4-dashboard-design.md` 的验收标准逐条过一遍。

- [ ] **Step 1: 跑全量后端测试**

Run: `pytest -vv`
Expected: 全部通过（含一至四期上遗留测试 + 本阶段新增的 `test_dashboard.py`，共 129 个）。

- [ ] **Step 2: 跑前端 lint（限定改动文件）**

Run: `cd web && pnpm exec eslint src/api/dashboard.js src/api/index.js src/views/todo/Dashboard/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 用管理后台把新增 API 分配给角色**

启动后端（`python run.py`）后，用 `admin`/`123456` 登录管理后台，进入"系统管理 → API 管理"点击"刷新 API"，确认新增的 `/api/v1/dashboard/today` 接口出现在列表里；进入"角色管理"，把这个接口分配给测试要用的角色（超级管理员本身跳过 API 校验，不受影响）。

- [ ] **Step 4: 浏览器端到端走查，对照 spec 验收标准**

Run: `cd web && pnpm dev`，浏览器登录后依次验证 `docs/superpowers/specs/2026-08-15-task-system-phase4-dashboard-design.md` 的"验收标准"一节（与 Task 4 Step 3 的手动验证清单重叠，此处是最终整体确认）。

Expected: 全部符合预期。若发现偏差，回到对应 Task 定位问题、修复、重新跑一遍该 Task 的测试/验证步骤，再继续。

- [ ] **Step 5: 如果验证过程中做了修复，提交**

```bash
git add -A
git commit -m "fix: address issues found during phase4-dashboard end-to-end verification"
```

（如果 Step 4 全部一次通过、没有任何修改，跳过本步。）
