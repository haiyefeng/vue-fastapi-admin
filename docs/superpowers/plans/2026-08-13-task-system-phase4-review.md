# 四期（上）：回顾总结（Review）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地蓝图四期（上）——回顾总结（Review）模块：周期回顾数据模型、数据回顾聚合接口、七步引导式反思、`get_statistics_by_date` 性能优化，以及对应的回顾页面。

**Architecture:** 后端先行（模型 → schema/controller/route → 统计优化），前端随后（api 客户端 → 单文件回顾页）。沿用 `goal`/`habit` 模块已确立的扁平路由风格、`user_id` 数据隔离、`Menu` 驱动前端路由的既有约定。

**Tech Stack:** FastAPI + Tortoise ORM（后端），Vue 3 `<script setup>` + Naive UI（前端），pytest + httpx（后端测试）。

## Global Constraints

- 本分支从 `feat-task`（已含一/二/三期全部内容）fork。
- 所有新路由挂 `dependencies=[DependPermission]`，处理函数内 `Depends(AuthControl.is_authed)` 取当前用户，所有查询按 `user_id` 过滤——与 `goal`/`habit` 模块完全一致。
- **`GET /review/detail` 在未找到记录时返回 `200` + `data: null`，不是 `404`**：这是本计划相对于已批准 spec 文本的一处修正——spec 原文写"不存在返回 404"，但 `web/src/utils/http/interceptors.js::resReject` 对任何非 2xx 响应都会无条件弹出全局错误提示（`window.$message?.error(...)`），而"这个周期还没有回顾记录"是首次打开任意周期时的默认状态、不是错误，用 404 会导致用户每次切换到未回顾过的周期都看到一条刺眼的红色错误提示。改为 `200 + null` 后，前端用 `if (res.data)` 正常分支，不触发全局错误提示。`GET /goal/detail` 的 404（`goal_id` 不存在/不属于当前用户）是真错误场景，不受此修正影响，两者语义不同。
- Review 的 `answers` 字段每次 `POST /review/save` 都是前端提交当前七个文本框的完整状态（覆盖写入，不做增量合并）——前端设计里保存只在点按钮时整体提交一次，不存在多次调用合并同一份 answers 的场景。
- 复用 `HabitController` 的连续天数/本周进度计算逻辑时，本计划会把 `_should_generate_today`、`_completed_this_week`、`_calc_streak`、`_week_range` 四个方法去掉前导下划线改为公开方法（Task 3）——这是一个刻意的、有明确理由的微重构：这四个方法现在有了 `review.py` 这个新调用方，不再是 `HabitController` 内部实现细节。除了改名，逻辑本身不变。
- `get_statistics_by_date` 优化只改内部查询实现，不改函数签名和返回类型（`List[TodoStatisticsByDate]`），确保 `TodoHistory` 页面和 `tests/test_habit.py` 里已有的 `test_daily_statistics_exclude_habit_todos`/`test_quadrant_statistics_exclude_habit_todos` 两个回归测试继续通过。
- 新建的 Vue 页面文件名为 `index.vue` 时必须显式 `defineOptions({ name: '<菜单名称>' })`——`<script setup>` 的 `index.vue` 文件永远推断出 `__name: 'index'`（取自文件名，与父目录名无关），而 `KeepAlive` 的 `:include` 是按组件名匹配、不是按路由名匹配；三期计划目标最终评审时才发现并修复了这个坑（`Goal/index.vue`、`Habit/index.vue` 都因此在合并前才补上 `defineOptions`），本计划从一开始就按正确方式写，不重蹈覆辙。
- 纯日期字符串（`"YYYY-MM-DD"`）的读写一律使用本地年月日拼接/解析（`GoalFormModal.vue` 已有的 `parseLocalDateString`/`formatLocalDateString` 模式），禁止对纯日期使用 `.toISOString()` 或 `new Date(dateString)`——这两种写法都按 UTC 解读/输出，在东八区会把日期错移一天，这个坑在二/三期都踩过。
- 若开发过程中需要新建独立 worktree，测试阶段应通过环境变量把数据库指向独立测试库（或临时改用 SQLite），不要与其他 worktree/主仓库共享同一个 MySQL 库——三期计划目标阶段因为多个 worktree 共用同一个物理 MySQL 库，导致 aerich 迁移记录和实际表结构脱节，事后手工修复过一次。pytest 套件本身用的是每个用例独立的内存 SQLite（`tests/conftest.py`），不受此风险影响；这条约束只针对手工/`python run.py` 级别的联调测试。

---

### Task 1: Review 模型 + 迁移

**Files:**
- Modify: `app/models/todo.py`
- Modify: `app/models/__init__.py`

**Interfaces:**
- Produces：`Review` 模型（`app/models/todo.py`），`ReviewPeriodType`（`week`/`month`/`quarter`/`year`）、`ReviewStatus`（`draft`/`completed`）两个枚举。后续所有任务依赖这三个符号。

- [ ] **Step 1: 在 `app/models/todo.py` 末尾追加 Review 相关定义**

在文件末尾（`Goal` 类定义之后）追加：

```python
class ReviewPeriodType(StrEnum):
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    COMPLETED = "completed"


class Review(BaseModel, TimestampMixin):
    """周期回顾模型：数据回顾区实时聚合计算不落库，这里只存七步反思答案与状态"""

    user = fields.ForeignKeyField("models.User", related_name="reviews", description="所属用户")
    period_type = fields.CharEnumField(ReviewPeriodType, description="回顾周期类型")
    period_start = fields.DateField(description="周期开始日期")
    period_end = fields.DateField(description="周期结束日期")
    answers = fields.JSONField(default=dict, description="七步提问法答案，key 为 step1~step7")
    status = fields.CharEnumField(ReviewStatus, default=ReviewStatus.DRAFT, description="草稿/已完成")

    class Meta:
        table = "review"
        unique_together = (("user", "period_type", "period_start"),)

    def __str__(self):
        return f"{self.period_type} {self.period_start}"
```

- [ ] **Step 2: 更新 `app/models/__init__.py`**

找到：

```python
from .todo import Category, Goal, Habit, HabitFrequencyType, Project, QuadrantType, SubTask, TimeBlock, TodoItem
```

改成：

```python
from .todo import (
    Category,
    Goal,
    Habit,
    HabitFrequencyType,
    Project,
    QuadrantType,
    Review,
    ReviewPeriodType,
    ReviewStatus,
    SubTask,
    TimeBlock,
    TodoItem,
)
```

- [ ] **Step 3: 生成迁移并升级本地库**

Run: `make migrate && make upgrade`

Expected: `migrations/models/` 下生成新的迁移文件，内容包含 `CREATE TABLE review` 以及 `user_id`/`period_type`/`period_start`/`period_end`/`answers`/`status` 列。本地默认 SQLite 库（`db.sqlite3`）成功升级，无报错。

如果本地开发环境实际指向的是共享 MySQL 库（`app/settings/config.py` 里注释掉的 SQLite 配置块之外的 mysql 连接），执行前确认没有其他 worktree/进程同时对同一个库跑迁移（参见 Global Constraints 最后一条）。

- [ ] **Step 4: 跑现有全量测试确认无回归**

Run: `make test`

Expected: 91 passed（新增模型不影响任何现有测试，Review 表本身此时还没有任何读写入口）。

- [ ] **Step 5: 提交**

```bash
git add app/models/todo.py app/models/__init__.py
git commit -m "feat: add Review model for phase4 periodic review"
```

---

### Task 2: Review 保存/详情/历史列表接口

**Files:**
- Create: `app/schemas/review.py`
- Create: `app/controllers/review.py`
- Create: `app/api/v1/review/route.py`
- Create: `app/api/v1/review/__init__.py`
- Modify: `app/api/v1/__init__.py`
- Test: `tests/test_review.py`

**Interfaces:**
- Consumes：Task 1 的 `Review`/`ReviewPeriodType`/`ReviewStatus`。
- Produces：`review_controller`（`app/controllers/review.py`），公开方法 `calc_period_range(period_type, anchor_date) -> Tuple[date, date]`（静态方法）、`save_review(obj_in, user_id) -> Review`、`get_review_detail(period_type, anchor_date, user_id) -> Optional[Review]`、`get_review_list(user_id, period_type=None) -> List[Review]`。`POST /review/save`、`GET /review/detail`、`GET /review/list` 三个路由。Task 3 会在同一批文件基础上追加数据回顾聚合的 schema/方法/路由。

- [ ] **Step 1: 写 `app/schemas/review.py`**

```python
from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.todo import ReviewPeriodType, ReviewStatus


class ReviewSaveIn(BaseModel):
    period_type: ReviewPeriodType = Field(..., description="回顾周期类型")
    anchor_date: date = Field(..., description="周期内任意一天，用于定位周期起止")
    answers: Dict[str, str] = Field(
        default_factory=dict, description="七步提问法答案，key 为 step1~step7，前端一次性提交当前完整表单状态"
    )
    status: ReviewStatus = Field(ReviewStatus.DRAFT, description="草稿/已完成")


class ReviewOut(BaseModel):
    id: int
    period_type: ReviewPeriodType
    period_start: date
    period_end: date
    answers: Dict[str, str] = Field(default_factory=dict)
    status: ReviewStatus

    class Config:
        from_attributes = True


class ReviewListItem(BaseModel):
    id: int
    period_type: ReviewPeriodType
    period_start: date
    period_end: date
    status: ReviewStatus

    class Config:
        from_attributes = True
```

- [ ] **Step 2: 写 `app/controllers/review.py`**

```python
from datetime import date, timedelta
from typing import List, Optional, Tuple

from app.core.crud import CRUDBase
from app.models.todo import Review, ReviewPeriodType, ReviewStatus
from app.schemas.review import ReviewSaveIn


def _add_months(d: date, months: int) -> date:
    """按月数偏移，返回该月 1 号；用于计算月/季度周期的结束边界（下个周期起点减一天）"""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


class ReviewController(CRUDBase[Review, ReviewSaveIn, ReviewSaveIn]):
    def __init__(self):
        super().__init__(model=Review)

    @staticmethod
    def calc_period_range(period_type: ReviewPeriodType, anchor_date: date) -> Tuple[date, date]:
        """根据周期类型和锚点日期（周期内任意一天）计算周期起止日期"""
        if period_type == ReviewPeriodType.WEEK:
            start = anchor_date - timedelta(days=anchor_date.isoweekday() - 1)
            end = start + timedelta(days=6)
        elif period_type == ReviewPeriodType.MONTH:
            start = anchor_date.replace(day=1)
            end = _add_months(start, 1) - timedelta(days=1)
        elif period_type == ReviewPeriodType.QUARTER:
            quarter_start_month = ((anchor_date.month - 1) // 3) * 3 + 1
            start = anchor_date.replace(month=quarter_start_month, day=1)
            end = _add_months(start, 3) - timedelta(days=1)
        else:  # ReviewPeriodType.YEAR
            start = anchor_date.replace(month=1, day=1)
            end = anchor_date.replace(month=12, day=31)
        return start, end

    async def save_review(self, obj_in: ReviewSaveIn, user_id: int) -> Review:
        """同一用户同一周期类型同一起始日只保留一条记录：存在则覆盖更新，不存在则创建"""
        period_start, period_end = self.calc_period_range(obj_in.period_type, obj_in.anchor_date)
        review = await Review.filter(
            user_id=user_id, period_type=obj_in.period_type, period_start=period_start
        ).first()
        if review:
            await review.update_from_dict(
                {"period_end": period_end, "answers": obj_in.answers, "status": obj_in.status}
            ).save()
            return review
        return await Review.create(
            user_id=user_id,
            period_type=obj_in.period_type,
            period_start=period_start,
            period_end=period_end,
            answers=obj_in.answers,
            status=obj_in.status,
        )

    async def get_review_detail(
        self, period_type: ReviewPeriodType, anchor_date: date, user_id: int
    ) -> Optional[Review]:
        period_start, _ = self.calc_period_range(period_type, anchor_date)
        return await Review.filter(user_id=user_id, period_type=period_type, period_start=period_start).first()

    async def get_review_list(
        self, user_id: int, period_type: Optional[ReviewPeriodType] = None
    ) -> List[Review]:
        query = Review.filter(user_id=user_id)
        if period_type:
            query = query.filter(period_type=period_type)
        return await query.order_by("-period_start")


review_controller = ReviewController()
```

- [ ] **Step 3: 写 `app/api/v1/review/route.py`**

```python
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.controllers.review import review_controller
from app.core.dependency import AuthControl
from app.models.admin import User
from app.models.todo import ReviewPeriodType
from app.schemas.base import Success
from app.schemas.review import ReviewListItem, ReviewOut, ReviewSaveIn

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/save", summary="保存回顾（草稿或完成），同周期已存在则覆盖更新")
async def save_review(review_in: ReviewSaveIn, current_user: User = Depends(AuthControl.is_authed)):
    review = await review_controller.save_review(review_in, current_user.id)
    return Success(data=ReviewOut(**(await review.to_dict())).model_dump())


@router.get("/detail", summary="获取指定周期的回顾详情；不存在时 data 为 null（不是 404）")
async def get_review_detail(
    period_type: ReviewPeriodType = Query(..., description="回顾周期类型"),
    anchor_date: date = Query(..., description="周期内任意一天"),
    current_user: User = Depends(AuthControl.is_authed),
):
    review = await review_controller.get_review_detail(period_type, anchor_date, current_user.id)
    if not review:
        return Success(data=None)
    return Success(data=ReviewOut(**(await review.to_dict())).model_dump())


@router.get("/list", summary="获取历史回顾列表，按周期开始日期倒序")
async def list_reviews(
    period_type: Optional[ReviewPeriodType] = Query(None, description="按周期类型筛选，留空返回全部"),
    current_user: User = Depends(AuthControl.is_authed),
):
    reviews = await review_controller.get_review_list(current_user.id, period_type)
    result = [ReviewListItem(**(await r.to_dict())).model_dump() for r in reviews]
    return Success(data=result)
```

- [ ] **Step 4: 写 `app/api/v1/review/__init__.py`**

```python
from fastapi import APIRouter

from .route import router

review_router = APIRouter()
review_router.include_router(router, tags=["回顾总结"])

__all__ = ["review_router"]
```

- [ ] **Step 5: 注册路由，修改 `app/api/v1/__init__.py`**

找到：

```python
from .project import project_router
from .roles import roles_router
```

改成：

```python
from .project import project_router
from .review import review_router
from .roles import roles_router
```

找到：

```python
v1_router.include_router(habit_router, prefix="/habit", dependencies=[DependPermission])
```

改成：

```python
v1_router.include_router(habit_router, prefix="/habit", dependencies=[DependPermission])
v1_router.include_router(review_router, prefix="/review", dependencies=[DependPermission])
```

- [ ] **Step 6: 写测试 `tests/test_review.py`**

```python
from datetime import date

from app.controllers.review import ReviewController
from app.models.todo import Review, ReviewPeriodType


def test_calc_period_range_week():
    start, end = ReviewController.calc_period_range(ReviewPeriodType.WEEK, date(2026, 8, 13))
    assert start == date(2026, 8, 10)
    assert end == date(2026, 8, 16)


def test_calc_period_range_month():
    start, end = ReviewController.calc_period_range(ReviewPeriodType.MONTH, date(2026, 8, 13))
    assert start == date(2026, 8, 1)
    assert end == date(2026, 8, 31)


def test_calc_period_range_quarter():
    start, end = ReviewController.calc_period_range(ReviewPeriodType.QUARTER, date(2026, 8, 13))
    assert start == date(2026, 7, 1)
    assert end == date(2026, 9, 30)


def test_calc_period_range_year():
    start, end = ReviewController.calc_period_range(ReviewPeriodType.YEAR, date(2026, 8, 13))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 12, 31)


async def test_save_review_creates_draft(client, test_user):
    resp = await client.post(
        "/api/v1/review/save",
        json={"period_type": "week", "anchor_date": "2026-08-13", "answers": {"step1": "挑战是论文进展缓慢"}},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["period_start"] == "2026-08-10"
    assert data["period_end"] == "2026-08-16"
    assert data["status"] == "draft"
    assert data["answers"]["step1"] == "挑战是论文进展缓慢"


async def test_save_review_same_period_overwrites_existing(client, test_user):
    await client.post(
        "/api/v1/review/save",
        json={"period_type": "week", "anchor_date": "2026-08-13", "answers": {"step1": "第一版"}},
    )
    resp = await client.post(
        "/api/v1/review/save",
        json={"period_type": "week", "anchor_date": "2026-08-15", "answers": {"step1": "第二版"}},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["answers"]["step1"] == "第二版"
    assert await Review.filter(user_id=test_user.id, period_type=ReviewPeriodType.WEEK).count() == 1


async def test_save_review_completed_status(client, test_user):
    resp = await client.post(
        "/api/v1/review/save",
        json={"period_type": "week", "anchor_date": "2026-08-13", "answers": {}, "status": "completed"},
    )
    assert resp.json()["data"]["status"] == "completed"


async def test_get_review_detail_returns_null_when_not_found(client, test_user):
    resp = await client.get(
        "/api/v1/review/detail", params={"period_type": "week", "anchor_date": "2026-08-13"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"] is None


async def test_get_review_detail_returns_existing(client, test_user):
    await client.post(
        "/api/v1/review/save",
        json={"period_type": "month", "anchor_date": "2026-08-13", "answers": {"step7": "调整作息"}},
    )
    resp = await client.get(
        "/api/v1/review/detail", params={"period_type": "month", "anchor_date": "2026-08-20"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["answers"]["step7"] == "调整作息"


async def test_get_review_list_ordered_by_period_start_desc(client, test_user):
    await client.post("/api/v1/review/save", json={"period_type": "week", "anchor_date": "2026-08-06"})
    await client.post("/api/v1/review/save", json={"period_type": "week", "anchor_date": "2026-08-13"})

    resp = await client.get("/api/v1/review/list")
    data = resp.json()["data"]
    assert len(data) == 2
    assert data[0]["period_start"] == "2026-08-10"
    assert data[1]["period_start"] == "2026-08-03"


async def test_get_review_list_filter_by_period_type(client, test_user):
    await client.post("/api/v1/review/save", json={"period_type": "week", "anchor_date": "2026-08-13"})
    await client.post("/api/v1/review/save", json={"period_type": "month", "anchor_date": "2026-08-13"})

    resp = await client.get("/api/v1/review/list", params={"period_type": "month"})
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["period_type"] == "month"


async def test_reviews_are_isolated_per_user(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x")
    await Review.create(
        user_id=other_user.id, period_type=ReviewPeriodType.WEEK, period_start="2026-08-10", period_end="2026-08-16"
    )

    resp = await client.get("/api/v1/review/list")
    assert resp.json()["data"] == []
```

- [ ] **Step 7: 运行测试**

Run: `make test`

Expected: 全部通过，103 passed（91 + 本任务新增 12 个）。

- [ ] **Step 8: 提交**

```bash
git add app/schemas/review.py app/controllers/review.py app/api/v1/review/ app/api/v1/__init__.py tests/test_review.py
git commit -m "feat: add review save/detail/list endpoints"
```

---

### Task 3: 数据回顾聚合接口

**Files:**
- Modify: `app/schemas/review.py`
- Modify: `app/controllers/review.py`
- Modify: `app/controllers/habit.py`
- Modify: `app/api/v1/review/route.py`
- Test: `tests/test_review.py`

**Interfaces:**
- Consumes：`HabitController` 改名后的 `should_generate_today`、`completed_this_week`、`calc_streak`、`week_range`。
- Produces：`review_controller.get_data_summary(user_id, period_type, anchor_date) -> dict`，`GET /review/data-summary` 路由。

- [ ] **Step 1: 修改 `app/controllers/habit.py`，四个方法去掉前导下划线**

找到：

```python
            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT:
                data["streak"] = None
                count = (habit.frequency_config or {}).get("count", 0)
                completed = await self._completed_this_week(habit.id, today)
                data["week_progress"] = f"{completed}/{count}"
            else:
                data["streak"] = await self._calc_streak(habit, today)
                data["week_progress"] = None
```

改成：

```python
            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT:
                data["streak"] = None
                count = (habit.frequency_config or {}).get("count", 0)
                completed = await self.completed_this_week(habit.id, today)
                data["week_progress"] = f"{completed}/{count}"
            else:
                data["streak"] = await self.calc_streak(habit, today)
                data["week_progress"] = None
```

找到：

```python
        for habit in habits:
            should_generate = await self._should_generate_today(habit, today)

            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT and not should_generate:
                week_start, week_end = self._week_range(today)
```

改成：

```python
        for habit in habits:
            should_generate = await self.should_generate_today(habit, today)

            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT and not should_generate:
                week_start, week_end = self.week_range(today)
```

找到：

```python
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
        # 从昨天开始回看：今天的打卡待办可能刚生成、还未完成，不能算作"断签"，
        # 连续天数只统计已经完整过去的天数
        cursor = today - timedelta(days=1)
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

改成：

```python
    async def should_generate_today(self, habit: Habit, today: date) -> bool:
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
            completed = await self.completed_this_week(habit.id, today)
            return completed < count
        return False

    async def completed_this_week(self, habit_id: int, today: date) -> int:
        week_start, week_end = self.week_range(today)
        return await TodoItem.filter(
            habit_id=habit_id, is_completed=True, generated_date__gte=week_start, generated_date__lte=week_end
        ).count()

    async def calc_streak(self, habit: Habit, today: date) -> int:
        streak = 0
        # 从昨天开始回看：今天的打卡待办可能刚生成、还未完成，不能算作"断签"，
        # 连续天数只统计已经完整过去的天数
        cursor = today - timedelta(days=1)
        for _ in range(3650):  # 防止极端配置导致死循环，最多回看 10 年
            if not await self.should_generate_today(habit, cursor):
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
    def week_range(today: date) -> Tuple[date, date]:
        week_start = today - timedelta(days=today.isoweekday() - 1)
        week_end = week_start + timedelta(days=6)
        return week_start, week_end
```

（这四个方法此前只在 `habit.py` 内部相互调用，去掉下划线前缀不影响任何路由行为，`tests/test_habit.py` 里没有直接引用这几个方法名，无需同步修改测试文件。）

- [ ] **Step 2: 在 `app/schemas/review.py` 末尾追加数据回顾聚合的 schema**

```python
class TaskCompletionByCategory(BaseModel):
    category_id: int
    category_name: str
    total: int
    completed: int


class TaskCompletionSummary(BaseModel):
    total: int = Field(0, description="周期内到期的任务总数")
    completed: int = Field(0, description="其中已完成数")
    urgent_important_total: int = Field(0, description="周期内到期的高优先级（紧急且重要）任务总数")
    urgent_important_completed: int = Field(0, description="其中已完成数")
    by_category: List[TaskCompletionByCategory] = Field(default_factory=list)


class HabitCheckInSummary(BaseModel):
    habit_id: int
    name: str
    frequency_type: str
    completed: int = Field(0, description="周期内完成天数（定日型）或完成次数（弹性型）")
    expected: int = Field(0, description="周期内应完成天数（定日型）或配额总数（弹性型）")
    streak: Optional[int] = Field(None, description="当前连续天数，仅定日型有意义，弹性型为 null")


class GoalProgressSummary(BaseModel):
    goal_id: int
    name: str
    newly_completed: int = Field(0, description="周期内新完成的关联任务数")
    total_linked_tasks: int = Field(0, description="计划关联任务总数")
    progress_percent: Optional[float] = Field(None, description="newly_completed/total_linked_tasks 的百分比，无关联任务时为 null（对应“无明显进展”）")


class ReviewDataSummaryOut(BaseModel):
    period_start: date
    period_end: date
    task_completion: TaskCompletionSummary
    habits: List[HabitCheckInSummary] = Field(default_factory=list)
    goals: List[GoalProgressSummary] = Field(default_factory=list)
```

- [ ] **Step 3: 修改 `app/controllers/review.py` 的 import，并追加聚合方法**

找到：

```python
from datetime import date, timedelta
from typing import List, Optional, Tuple

from app.core.crud import CRUDBase
from app.models.todo import Review, ReviewPeriodType, ReviewStatus
from app.schemas.review import ReviewSaveIn
```

改成：

```python
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

from tortoise.functions import Count

from app.core.crud import CRUDBase
from app.models.todo import (
    Category,
    Goal,
    Habit,
    HabitFrequencyType,
    QuadrantType,
    Review,
    ReviewPeriodType,
    ReviewStatus,
    TodoItem,
)
from app.schemas.review import ReviewSaveIn
```

在 `review_controller = ReviewController()` 这一行之前（`ReviewController` 类内部，`get_review_list` 方法之后）追加：

```python
    async def get_data_summary(self, user_id: int, period_type: ReviewPeriodType, anchor_date: date) -> dict:
        """数据回顾聚合：不依赖 Review 记录是否存在，纯只读查询，可重复调用"""
        period_start, period_end = self.calc_period_range(period_type, anchor_date)
        return {
            "period_start": period_start,
            "period_end": period_end,
            "task_completion": await self._get_task_completion_summary(user_id, period_start, period_end),
            "habits": await self._get_habit_checkin_summary(user_id, period_start, period_end),
            "goals": await self._get_goal_progress_summary(user_id, period_start, period_end),
        }

    async def _get_task_completion_summary(self, user_id: int, period_start: date, period_end: date) -> dict:
        day_start = datetime.combine(period_start, time.min)
        day_end = datetime.combine(period_end, time.max)
        common_filter = dict(
            user_id=user_id, habit_id__isnull=True, due_date__gte=day_start, due_date__lte=day_end
        )

        total = await TodoItem.filter(**common_filter).count()
        completed = await TodoItem.filter(**common_filter, is_completed=True).count()
        urgent_important_total = await TodoItem.filter(
            **common_filter, quadrant_type=QuadrantType.URGENT_IMPORTANT
        ).count()
        urgent_important_completed = await TodoItem.filter(
            **common_filter, quadrant_type=QuadrantType.URGENT_IMPORTANT, is_completed=True
        ).count()

        category_totals = (
            await TodoItem.filter(**common_filter, project__category_id__isnull=False)
            .annotate(cnt=Count("id"))
            .group_by("project__category_id")
            .values("project__category_id", "cnt")
        )
        category_completed_rows = (
            await TodoItem.filter(**common_filter, project__category_id__isnull=False, is_completed=True)
            .annotate(cnt=Count("id"))
            .group_by("project__category_id")
            .values("project__category_id", "cnt")
        )
        completed_map = {row["project__category_id"]: row["cnt"] for row in category_completed_rows}

        category_ids = [row["project__category_id"] for row in category_totals]
        categories = await Category.filter(id__in=category_ids).values("id", "name")
        name_map = {c["id"]: c["name"] for c in categories}

        by_category = [
            {
                "category_id": row["project__category_id"],
                "category_name": name_map.get(row["project__category_id"], ""),
                "total": row["cnt"],
                "completed": completed_map.get(row["project__category_id"], 0),
            }
            for row in category_totals
        ]

        return {
            "total": total,
            "completed": completed,
            "urgent_important_total": urgent_important_total,
            "urgent_important_completed": urgent_important_completed,
            "by_category": by_category,
        }

    async def _get_habit_checkin_summary(self, user_id: int, period_start: date, period_end: date) -> List[dict]:
        from app.controllers.habit import habit_controller

        habits = await Habit.filter(user_id=user_id, is_archived=False, is_paused=False)
        today = date.today()
        result = []
        for habit in habits:
            if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT:
                count = (habit.frequency_config or {}).get("count", 0)
                total_days = (period_end - period_start).days + 1
                full_weeks = total_days // 7
                expected = full_weeks * count
                completed = await TodoItem.filter(
                    habit_id=habit.id,
                    is_completed=True,
                    generated_date__gte=period_start,
                    generated_date__lte=period_end,
                ).count()
                streak = None
            else:
                expected = 0
                completed = 0
                cursor = period_start
                while cursor <= period_end:
                    if await habit_controller.should_generate_today(habit, cursor):
                        expected += 1
                        todo = await TodoItem.filter(habit_id=habit.id, generated_date=cursor).first()
                        if todo and todo.is_completed:
                            completed += 1
                    cursor += timedelta(days=1)
                streak = await habit_controller.calc_streak(habit, today)

            result.append(
                {
                    "habit_id": habit.id,
                    "name": habit.name,
                    "frequency_type": habit.frequency_type,
                    "completed": completed,
                    "expected": expected,
                    "streak": streak,
                }
            )
        return result

    async def _get_goal_progress_summary(self, user_id: int, period_start: date, period_end: date) -> List[dict]:
        goals = await Goal.filter(user_id=user_id, is_archived=False)
        day_start = datetime.combine(period_start, time.min)
        day_end = datetime.combine(period_end, time.max)
        result = []
        for goal in goals:
            total_linked = await TodoItem.filter(goal_id=goal.id).count()
            newly_completed = await TodoItem.filter(
                goal_id=goal.id, is_completed=True, completed_at__gte=day_start, completed_at__lte=day_end
            ).count()
            progress_percent = round(newly_completed / total_linked * 100, 1) if total_linked else None
            result.append(
                {
                    "goal_id": goal.id,
                    "name": goal.name,
                    "newly_completed": newly_completed,
                    "total_linked_tasks": total_linked,
                    "progress_percent": progress_percent,
                }
            )
        return result
```

`_get_habit_checkin_summary` 内部延迟导入 `habit_controller`（而不是放在文件顶部）是为了避免和 `app/controllers/habit.py` 产生模块级循环导入——`habit.py` 本身不导入 `review.py`，两者目前没有真正的循环依赖，这里用延迟导入只是防御性写法，与本仓库其他跨 controller 调用（如 `goal.py` 顶部直接 `from app.controllers.category import category_controller`）保持的即时导入方式不同，因为 `category.py` 不会反过来导入 `goal.py`，而这里为了完全避免未来产生循环导入风险，选择延迟导入。

- [ ] **Step 4: 在 `app/api/v1/review/route.py` 追加路由**

找到：

```python
from app.schemas.review import ReviewListItem, ReviewOut, ReviewSaveIn
```

改成：

```python
from app.schemas.review import ReviewDataSummaryOut, ReviewListItem, ReviewOut, ReviewSaveIn
```

在 `router = APIRouter()` 之后、`@router.post("/save"...)` 之前追加：

```python
@router.get("/data-summary", summary="获取指定周期的数据回顾聚合（任务完成情况/习惯打卡情况/计划进展）")
async def get_data_summary(
    period_type: ReviewPeriodType = Query(..., description="回顾周期类型"),
    anchor_date: date = Query(..., description="周期内任意一天"),
    current_user: User = Depends(AuthControl.is_authed),
):
    data = await review_controller.get_data_summary(current_user.id, period_type, anchor_date)
    return Success(data=ReviewDataSummaryOut(**data).model_dump())
```

- [ ] **Step 5: 在 `tests/test_review.py` 末尾追加测试**

```python
from datetime import datetime, timedelta

from app.models.todo import (
    Category,
    Goal,
    Habit,
    HabitFrequencyType,
    Project,
    QuadrantType,
    TodoItem,
)


async def test_data_summary_task_completion_overall(client, test_user):
    week_tuesday = datetime(2026, 8, 11, 12, 0, 0)
    await TodoItem.create(
        title="任务A", user_id=test_user.id, quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        due_date=week_tuesday, is_completed=True,
    )
    await TodoItem.create(
        title="任务B", user_id=test_user.id, quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        due_date=week_tuesday, is_completed=False,
    )

    resp = await client.get(
        "/api/v1/review/data-summary", params={"period_type": "week", "anchor_date": "2026-08-13"}
    )
    assert resp.status_code == 200
    task_completion = resp.json()["data"]["task_completion"]
    assert task_completion["total"] == 2
    assert task_completion["completed"] == 1


async def test_data_summary_task_completion_excludes_habit_todos(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="打卡", frequency_type=HabitFrequencyType.DAILY)
    await TodoItem.create(
        title="习惯待办", user_id=test_user.id, habit_id=habit.id,
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        due_date=datetime(2026, 8, 11, 12, 0, 0), is_completed=True,
    )

    resp = await client.get(
        "/api/v1/review/data-summary", params={"period_type": "week", "anchor_date": "2026-08-13"}
    )
    assert resp.json()["data"]["task_completion"]["total"] == 0


async def test_data_summary_task_completion_by_category(client, test_user):
    cat = await Category.create(user_id=test_user.id, name="工作")
    project = await Project.create(user_id=test_user.id, category_id=cat.id, name="Q4")
    await TodoItem.create(
        title="任务A", user_id=test_user.id, project_id=project.id,
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        due_date=datetime(2026, 8, 11, 12, 0, 0), is_completed=True,
    )

    resp = await client.get(
        "/api/v1/review/data-summary", params={"period_type": "week", "anchor_date": "2026-08-13"}
    )
    by_category = resp.json()["data"]["task_completion"]["by_category"]
    assert len(by_category) == 1
    assert by_category[0]["category_name"] == "工作"
    assert by_category[0]["total"] == 1
    assert by_category[0]["completed"] == 1


async def test_data_summary_urgent_important_breakdown(client, test_user):
    await TodoItem.create(
        title="高优先级", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT,
        due_date=datetime(2026, 8, 11, 12, 0, 0), is_completed=True,
    )
    await TodoItem.create(
        title="其他象限", user_id=test_user.id, quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        due_date=datetime(2026, 8, 11, 12, 0, 0), is_completed=True,
    )

    resp = await client.get(
        "/api/v1/review/data-summary", params={"period_type": "week", "anchor_date": "2026-08-13"}
    )
    task_completion = resp.json()["data"]["task_completion"]
    assert task_completion["urgent_important_total"] == 1
    assert task_completion["urgent_important_completed"] == 1


async def test_data_summary_habit_checkin_daily_type(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="晨间阅读", frequency_type=HabitFrequencyType.DAILY)
    await TodoItem.create(
        title="晨间阅读", user_id=test_user.id, habit_id=habit.id,
        quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT, generated_date="2026-08-11", is_completed=True,
    )

    resp = await client.get(
        "/api/v1/review/data-summary", params={"period_type": "week", "anchor_date": "2026-08-13"}
    )
    habits = resp.json()["data"]["habits"]
    assert len(habits) == 1
    assert habits[0]["expected"] == 7
    assert habits[0]["completed"] == 1
    assert habits[0]["streak"] is not None


async def test_data_summary_habit_checkin_weekly_count_type(client, test_user):
    habit = await Habit.create(
        user_id=test_user.id, name="运动", frequency_type=HabitFrequencyType.WEEKLY_COUNT,
        frequency_config={"count": 3},
    )
    await TodoItem.create(
        title="运动", user_id=test_user.id, habit_id=habit.id,
        quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT, generated_date="2026-08-11", is_completed=True,
    )

    resp = await client.get(
        "/api/v1/review/data-summary", params={"period_type": "week", "anchor_date": "2026-08-13"}
    )
    habits = resp.json()["data"]["habits"]
    assert habits[0]["expected"] == 3
    assert habits[0]["completed"] == 1
    assert habits[0]["streak"] is None


async def test_data_summary_habit_checkin_excludes_paused_and_archived(client, test_user):
    await Habit.create(
        user_id=test_user.id, name="已暂停", frequency_type=HabitFrequencyType.DAILY, is_paused=True
    )
    await Habit.create(
        user_id=test_user.id, name="已归档", frequency_type=HabitFrequencyType.DAILY, is_archived=True
    )

    resp = await client.get(
        "/api/v1/review/data-summary", params={"period_type": "week", "anchor_date": "2026-08-13"}
    )
    assert resp.json()["data"]["habits"] == []


async def test_data_summary_goal_progress_with_linked_tasks(client, test_user):
    goal = await Goal.create(user_id=test_user.id, name="学习计划")
    await TodoItem.create(
        title="任务A", user_id=test_user.id, goal_id=goal.id,
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        is_completed=True, completed_at=datetime(2026, 8, 11, 12, 0, 0),
    )
    await TodoItem.create(
        title="任务B", user_id=test_user.id, goal_id=goal.id,
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, is_completed=False,
    )

    resp = await client.get(
        "/api/v1/review/data-summary", params={"period_type": "week", "anchor_date": "2026-08-13"}
    )
    goals = resp.json()["data"]["goals"]
    assert len(goals) == 1
    assert goals[0]["newly_completed"] == 1
    assert goals[0]["total_linked_tasks"] == 2
    assert goals[0]["progress_percent"] == 50.0


async def test_data_summary_goal_progress_no_linked_tasks_returns_null_percent(client, test_user):
    await Goal.create(user_id=test_user.id, name="无关联计划")

    resp = await client.get(
        "/api/v1/review/data-summary", params={"period_type": "week", "anchor_date": "2026-08-13"}
    )
    goals = resp.json()["data"]["goals"]
    assert goals[0]["total_linked_tasks"] == 0
    assert goals[0]["progress_percent"] is None


async def test_data_summary_never_triggers_habit_generation(client, test_user):
    """数据回顾聚合是只读查询，打开回顾页不应该像打开习惯页那样顺带生成今天的习惯待办"""
    await Habit.create(user_id=test_user.id, name="晨间阅读", frequency_type=HabitFrequencyType.DAILY)

    await client.get(
        "/api/v1/review/data-summary", params={"period_type": "week", "anchor_date": "2026-08-13"}
    )

    assert await TodoItem.filter(habit_id__isnull=False).count() == 0
```

- [ ] **Step 6: 运行测试**

Run: `make test`

Expected: 全部通过，113 passed（103 + 本任务新增 10 个）。

- [ ] **Step 7: 提交**

```bash
git add app/schemas/review.py app/controllers/review.py app/controllers/habit.py app/api/v1/review/route.py tests/test_review.py
git commit -m "feat: add review data-summary aggregation endpoint"
```

---

### Task 4: `get_statistics_by_date` 性能优化

**Files:**
- Modify: `app/controllers/todo.py`
- Test: `tests/test_todo_statistics.py`

**Interfaces:**
- Consumes：无新依赖。
- Produces：`TodoController.get_statistics_by_date` 函数签名和返回类型不变，仅内部实现改变。

- [ ] **Step 1: 修改 `app/controllers/todo.py`**

找到：

```python
    async def get_statistics_by_date(
        self, user_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[TodoStatisticsByDate]:
        """获取按日期统计的待办事项数量"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        result = []
        current_date = start_date
        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date, datetime.max.time())

            stats = TodoStatisticsByDate(date=current_date)

            # 统计各象限的已完成数量
            for quadrant in QuadrantType:
                count = await TodoItem.filter(
                    user_id=user_id,
                    quadrant_type=quadrant,
                    completed_at__gte=day_start,
                    completed_at__lte=day_end,
                    habit_id__isnull=True,
                ).count()

                # 根据象限类型设置相应的字段
                if quadrant == QuadrantType.URGENT_IMPORTANT:
                    stats.urgent_important = count
                elif quadrant == QuadrantType.URGENT_NOT_IMPORTANT:
                    stats.urgent_not_important = count
                elif quadrant == QuadrantType.IMPORTANT_NOT_URGENT:
                    stats.important_not_urgent = count
                elif quadrant == QuadrantType.NOT_URGENT_NOT_IMPORTANT:
                    stats.not_urgent_not_important = count

            stats.total = (
                stats.urgent_important
                + stats.urgent_not_important
                + stats.important_not_urgent
                + stats.not_urgent_not_important
            )

            result.append(stats)
            current_date += timedelta(days=1)

        return result
```

改成：

```python
    async def get_statistics_by_date(
        self, user_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> List[TodoStatisticsByDate]:
        """获取按日期统计的待办事项数量：一次查询取出范围内所有已完成待办的 (完成日期, 象限)，
        在内存中按天/象限归位，避免按天 x 象限循环发起 count() 查询（30 天 x 4 象限 = 120 次独立查询）"""
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        day_start = datetime.combine(start_date, datetime.min.time())
        day_end = datetime.combine(end_date, datetime.max.time())

        rows = await TodoItem.filter(
            user_id=user_id,
            habit_id__isnull=True,
            completed_at__gte=day_start,
            completed_at__lte=day_end,
        ).values("completed_at", "quadrant_type")

        counts: Dict[Tuple[date, str], int] = {}
        for row in rows:
            key = (row["completed_at"].date(), row["quadrant_type"])
            counts[key] = counts.get(key, 0) + 1

        result = []
        current_date = start_date
        while current_date <= end_date:
            stats = TodoStatisticsByDate(date=current_date)
            stats.urgent_important = counts.get((current_date, QuadrantType.URGENT_IMPORTANT), 0)
            stats.urgent_not_important = counts.get((current_date, QuadrantType.URGENT_NOT_IMPORTANT), 0)
            stats.important_not_urgent = counts.get((current_date, QuadrantType.IMPORTANT_NOT_URGENT), 0)
            stats.not_urgent_not_important = counts.get(
                (current_date, QuadrantType.NOT_URGENT_NOT_IMPORTANT), 0
            )
            stats.total = (
                stats.urgent_important
                + stats.urgent_not_important
                + stats.important_not_urgent
                + stats.not_urgent_not_important
            )
            result.append(stats)
            current_date += timedelta(days=1)

        return result
```

- [ ] **Step 2: 写测试 `tests/test_todo_statistics.py`**

```python
from datetime import date, datetime, timedelta

from app.models.todo import Habit, HabitFrequencyType, QuadrantType, TodoItem


async def test_daily_statistics_per_day_per_quadrant_counts_correct(client, test_user):
    day1 = datetime(2026, 8, 10, 9, 0, 0)
    day2 = datetime(2026, 8, 11, 9, 0, 0)
    await TodoItem.create(
        title="t1", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT,
        is_completed=True, completed_at=day1,
    )
    await TodoItem.create(
        title="t2", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT,
        is_completed=True, completed_at=day1,
    )
    await TodoItem.create(
        title="t3", user_id=test_user.id, quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT,
        is_completed=True, completed_at=day2,
    )

    resp = await client.get(
        "/api/v1/todo/statistics/daily",
        params={"start_date": "2026-08-10", "end_date": "2026-08-11"},
    )
    data = {row["date"]: row for row in resp.json()["data"]}
    assert data["2026-08-10"]["urgent_important"] == 2
    assert data["2026-08-10"]["total"] == 2
    assert data["2026-08-11"]["important_not_urgent"] == 1
    assert data["2026-08-11"]["total"] == 1


async def test_daily_statistics_default_range_is_30_days_ending_today(client, test_user):
    resp = await client.get("/api/v1/todo/statistics/daily")
    data = resp.json()["data"]
    assert len(data) == 31  # 含首尾两端，today - 30 天 到 today 共 31 天
    assert data[-1]["date"] == date.today().isoformat()
    assert data[0]["date"] == (date.today() - timedelta(days=30)).isoformat()


async def test_daily_statistics_boundary_dates_inclusive(client, test_user):
    await TodoItem.create(
        title="边界任务", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT,
        is_completed=True, completed_at=datetime(2026, 8, 10, 23, 59, 59),
    )

    resp = await client.get(
        "/api/v1/todo/statistics/daily",
        params={"start_date": "2026-08-10", "end_date": "2026-08-10"},
    )
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["urgent_important"] == 1


async def test_daily_statistics_excludes_habit_todos_after_optimization(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="打卡", frequency_type=HabitFrequencyType.DAILY)
    await TodoItem.create(
        title="习惯待办", user_id=test_user.id, habit_id=habit.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
        is_completed=True, completed_at=datetime(2026, 8, 10, 9, 0, 0),
    )

    resp = await client.get(
        "/api/v1/todo/statistics/daily",
        params={"start_date": "2026-08-10", "end_date": "2026-08-10"},
    )
    assert resp.json()["data"][0]["urgent_important"] == 0
```

- [ ] **Step 3: 运行测试**

Run: `make test`

Expected: 全部通过，117 passed（113 + 本任务新增 4 个）。同时确认 `tests/test_habit.py::test_daily_statistics_exclude_habit_todos` 和 `test_quadrant_statistics_exclude_habit_todos` 仍在通过列表里（`get_quadrant_statistics` 本任务未改动）。

- [ ] **Step 4: 提交**

```bash
git add app/controllers/todo.py tests/test_todo_statistics.py
git commit -m "perf: optimize get_statistics_by_date from 120 queries to 1"
```

---

### Task 5: "回顾总结" Menu 记录

**Files:**
- Modify: `app/core/init_app.py`

**Interfaces:**
- Consumes：无。
- Produces：Menu 记录 `name="回顾总结"`，`component="/todo/Review"`，Task 7 的页面组件挂载点。

- [ ] **Step 1: 修改 `app/core/init_app.py`**

找到：

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


async def init_apis():
```

改成：

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

- [ ] **Step 2: 运行测试确认无回归**

Run: `make test`

Expected: 117 passed（Menu 初始化逻辑没有现成测试覆盖，这一步只是确认改动没有引入语法错误或破坏其他初始化流程）。

- [ ] **Step 3: 提交**

```bash
git add app/core/init_app.py
git commit -m "feat: add 回顾总结 menu entry"
```

---

### Task 6: 前端 API 客户端（review）

**Files:**
- Create: `web/src/api/review.js`
- Modify: `web/src/api/index.js`

**Interfaces:**
- Consumes：Task 2/3 的 `/review/*` 接口。
- Produces：`api.getReviewDataSummary`、`api.getReviewDetail`、`api.saveReview`、`api.getReviewList`，Task 7 直接使用。

- [ ] **Step 1: 写 `web/src/api/review.js`**

```js
import { request } from '@/utils'

/**
 * 回顾总结API接口
 */
export default {
  /**
   * 获取指定周期的数据回顾聚合（任务完成情况/习惯打卡情况/计划进展）
   * @param {String} periodType week/month/quarter/year
   * @param {String} anchorDate 周期内任意一天，格式 YYYY-MM-DD
   * @returns {Promise}
   */
  getReviewDataSummary: (periodType, anchorDate) =>
    request.get('/review/data-summary', { params: { period_type: periodType, anchor_date: anchorDate } }),

  /**
   * 获取指定周期的回顾详情；不存在时 data 为 null（不是错误，调用方按 res.data 是否为 null 分支即可）
   * @param {String} periodType
   * @param {String} anchorDate
   * @returns {Promise}
   */
  getReviewDetail: (periodType, anchorDate) =>
    request.get('/review/detail', { params: { period_type: periodType, anchor_date: anchorDate } }),

  /**
   * 保存回顾（草稿或完成），同周期已存在则覆盖更新
   * @param {Object} data { period_type, anchor_date, answers, status }
   * @returns {Promise}
   */
  saveReview: (data = {}) => request.post('/review/save', data),

  /**
   * 获取历史回顾列表
   * @param {String} periodType 可选，按周期类型筛选，不传返回全部
   * @returns {Promise}
   */
  getReviewList: (periodType) =>
    request.get('/review/list', { params: periodType ? { period_type: periodType } : {} })
}
```

- [ ] **Step 2: 注册到 `web/src/api/index.js`**

找到：

```js
import habitApi from './habit'
import goalApi from './goal'
```

改成：

```js
import habitApi from './habit'
import goalApi from './goal'
import reviewApi from './review'
```

找到：

```js
  // goal（三期计划目标）
  ...goalApi,
}
```

改成：

```js
  // goal（三期计划目标）
  ...goalApi,
  // review（四期回顾总结）
  ...reviewApi,
}
```

- [ ] **Step 3: lint 检查**

Run: `cd web && pnpm exec eslint src/api/review.js src/api/index.js`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 4: 提交**

```bash
git add web/src/api/review.js web/src/api/index.js
git commit -m "feat(web): add review api client"
```

---

### Task 7: `Review/index.vue` 回顾页

**Files:**
- Modify: `web/src/views/todo/Goal/GoalFormModal.vue`
- Create: `web/src/views/todo/Review/index.vue`

**Interfaces:**
- Consumes：Task 6 的 `api.getReviewDataSummary`/`api.getReviewDetail`/`api.saveReview`/`api.getReviewList`；三期已有的 `web/src/views/todo/Goal/GoalFormModal.vue`（复用，props `show`/`goal`，emits `update:show`/`saved`）。
- Produces：Menu 记录 `component="/todo/Review"`（Task 5 已创建）指向的页面入口。

- [ ] **Step 1: 修改 `GoalFormModal.vue`，`saved` 事件携带保存后的计划数据**

`GoalFormModal.vue` 目前 `emit('saved')` 不带任何参数——三期唯一的调用方 `Goal/index.vue` 用 `@saved="fetchAll"` 直接整体刷新列表，从不需要拿到具体是哪个计划。但本页面"生成改进计划"区块需要知道刚创建的是哪个计划（展示到"本次回顾新建的计划"列表里），所以要把创建/更新接口的响应数据带出来。这个改动向后兼容——`fetchAll` 是零参函数，被多传一个参数不受影响。

找到：

```js
    if (isEdit.value) {
      await api.updateGoal(props.goal.id, payload)
    } else {
      await api.createGoal(payload)
    }
    message.success('保存成功')
    emit('saved')
    onUpdateShow(false)
```

改成：

```js
    const res = isEdit.value ? await api.updateGoal(props.goal.id, payload) : await api.createGoal(payload)
    message.success('保存成功')
    emit('saved', res.data)
    onUpdateShow(false)
```

- [ ] **Step 2: 写 `web/src/views/todo/Review/index.vue`**

```vue
<template>
  <div class="review-page">
    <n-spin :show="loading">
      <div class="review-header">
        <h2>回顾总结</h2>
        <n-button @click="openHistoryModal">查看历史回顾</n-button>
      </div>

      <section class="period-switcher">
        <n-radio-group v-model:value="periodType">
          <n-space>
            <n-radio v-for="opt in periodTypeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </n-radio>
          </n-space>
        </n-radio-group>
        <n-date-picker v-model:value="anchorDateMs" type="date" style="width: 160px" />
        <span v-if="summary" class="period-range-label">
          周期: {{ summary.period_start }} ~ {{ summary.period_end }}
        </span>
      </section>

      <section v-if="summary" id="data-review" class="metrics-section">
        <h3>数据回顾</h3>
        <div class="metrics-grid">
          <div class="metric-card">
            <h4>任务完成情况</h4>
            <p>
              <strong>总任务完成:</strong>
              {{ summary.task_completion.completed }} / {{ summary.task_completion.total }}
            </p>
            <p v-for="cat in summary.task_completion.by_category" :key="cat.category_id">
              <strong>{{ cat.category_name }}类完成:</strong> {{ cat.completed }} / {{ cat.total }}
            </p>
            <p>
              <strong>高优先级完成:</strong>
              {{ summary.task_completion.urgent_important_completed }} /
              {{ summary.task_completion.urgent_important_total }}
            </p>
          </div>
          <div class="metric-card">
            <h4>习惯打卡情况</h4>
            <p v-for="habit in summary.habits" :key="habit.habit_id">
              <strong>{{ habit.name }}:</strong>
              <template v-if="habit.streak !== null">
                完成 {{ habit.completed }} / {{ habit.expected }} 天（连续 {{ habit.streak }} 天）
              </template>
              <template v-else> 完成 {{ habit.completed }} / {{ habit.expected }} 次 </template>
            </p>
            <n-empty v-if="!summary.habits.length" description="还没有进行中的习惯" size="small" />
          </div>
          <div class="metric-card">
            <h4>计划进展</h4>
            <p v-for="goal in summary.goals" :key="goal.goal_id">
              <strong>{{ goal.name }}:</strong>
              <template v-if="goal.progress_percent !== null">
                +{{ goal.progress_percent }}%（完成 {{ goal.newly_completed }} 个关联任务）
              </template>
              <template v-else> 无明显进展 </template>
            </p>
            <n-empty v-if="!summary.goals.length" description="还没有进行中的计划" size="small" />
          </div>
        </div>
      </section>

      <n-divider />

      <section id="guided-reflection">
        <h3>引导式反思（七步提问法）</h3>
        <div v-for="step in reflectionSteps" :key="step.key" class="reflection-step">
          <h4>{{ step.title }}</h4>
          <p class="step-guidance">{{ step.guidance }}</p>
          <n-input
            v-model:value="answers[step.key]"
            type="textarea"
            :rows="4"
            :placeholder="step.placeholder"
          />
        </div>
      </section>

      <section id="action-plan">
        <h3>生成改进计划</h3>
        <p class="section-hint">根据你的反思，特别是第六、七步的思考，将具体的行动步骤转化为下阶段的计划/目标。</p>
        <ul v-if="sessionCreatedGoals.length" class="session-goal-list">
          <li v-for="goal in sessionCreatedGoals" :key="goal.id">{{ goal.name }}</li>
        </ul>
        <p v-else class="section-hint" style="text-align: center">暂无新计划</p>
        <n-button @click="showFormModal = true"><span>+ 添加新计划/目标...</span></n-button>
      </section>

      <div class="review-footer">
        <n-button :loading="saving" @click="handleSave('draft')">保存草稿</n-button>
        <n-button type="primary" :loading="saving" @click="handleSave('completed')">完成本次回顾</n-button>
      </div>
    </n-spin>

    <GoalFormModal v-model:show="showFormModal" :goal="null" @saved="handleGoalCreated" />

    <n-modal v-model:show="showHistoryModal" preset="card" title="历史回顾" style="width: 480px">
      <div v-for="item in historyList" :key="item.id" class="history-item" @click="jumpToReview(item)">
        <span>{{ periodTypeLabel(item.period_type) }}回顾: {{ item.period_start }} ~ {{ item.period_end }}</span>
        <span class="history-status">{{ item.status === 'completed' ? '已完成' : '草稿' }}</span>
      </div>
      <n-empty v-if="!historyList.length" description="还没有历史回顾" />
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, watch, onActivated } from 'vue'
import { useMessage } from 'naive-ui'
import api from '@/api'
import GoalFormModal from '../Goal/GoalFormModal.vue'

defineOptions({ name: '回顾总结' })

const message = useMessage()

const periodTypeOptions = [
  { label: '周', value: 'week' },
  { label: '月', value: 'month' },
  { label: '季度', value: 'quarter' },
  { label: '年', value: 'year' }
]

const reflectionSteps = [
  {
    key: 'step1',
    title: '第一步：负面 -> 正面',
    guidance:
      '回顾本周期，有哪些方面让你感觉不满意、效率不高或遇到了挑战？从这些挑战中，你观察到了哪些积极的信号、学习到的经验或值得肯定的地方？',
    placeholder: '例如：挑战是论文进展缓慢，感觉无从下手。但积极的是，我坚持完成了所有的日常习惯...'
  },
  {
    key: 'step2',
    title: '第二步：封闭 -> 开放',
    guidance: '针对你提到的某个亮点，具体是什么关键因素促成了它？除了这个因素，还有哪些其他可能的原因或条件帮助了你？',
    placeholder: '例如：关键因素是提前规划了任务优先级。其他原因可能包括本周期会议较少，干扰少...'
  },
  {
    key: 'step3',
    title: '第三步：单一 -> 复数',
    guidance:
      '为了在下个周期继续保持这个亮点，或者改进某个挑战，有哪些不同的方法、策略或途径可以尝试？（至少想出2-3种）',
    placeholder: '例如：保持任务完成度：1. 继续提前规划；2. 尝试番茄工作法；3. 预留特定时间处理邮件...'
  },
  {
    key: 'step4',
    title: '第四步：现实 -> 可能性',
    guidance: '想象一下，如果某个挑战完全不成问题，或者某个亮点能发挥到极致，未来可能会出现哪些令人兴奋的新机会或可能性？',
    placeholder: '例如：如果论文顺利，可以提前开始找实习，或者有更多时间学习新技术...'
  },
  {
    key: 'step5',
    title: '第五步：发散 -> 聚焦',
    guidance:
      '在所有这些可能性和你想改进的方面中，下个周期你最想集中精力去突破或改进的一个具体领域是什么？明确你的核心焦点。',
    placeholder: '例如：下个周期的核心焦点是：切实推进毕业论文的写作进度...'
  },
  {
    key: 'step6',
    title: '第六步：静态 -> 动态',
    guidance:
      '为了在你选择的核心焦点上取得看得见的、持续的进步，下个周期你可以采取哪些非常具体的、可衡量的行动步骤？（将它们转化为计划或任务）',
    placeholder: '例如：1. 与导师预约时间讨论论文框架；2. 每天固定时段为论文写作时间；3. 完成文献综述初稿...'
  },
  {
    key: 'step7',
    title: '第七步：个体 -> 系统',
    guidance:
      '从更宏观或系统的角度思考，改进核心焦点将如何影响你的其他目标（工作/学习）、习惯或整体生活状态？为了更好地支持这项改进，你是否需要调整外部环境、内部流程或其他相关系统？',
    placeholder: '例如：推进论文能减轻焦虑，提升整体幸福感。为支持写作，需要保证充足睡眠...'
  }
]

const defaultAnswers = () => ({
  step1: '',
  step2: '',
  step3: '',
  step4: '',
  step5: '',
  step6: '',
  step7: ''
})

const loading = ref(false)
const saving = ref(false)
const periodType = ref('week')
const anchorDateMs = ref(Date.now())
const summary = ref(null)
const answers = ref(defaultAnswers())
const sessionCreatedGoals = ref([])
const showFormModal = ref(false)
const showHistoryModal = ref(false)
const historyList = ref([])

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

const anchorDateStr = computed(() => formatLocalDateString(anchorDateMs.value))

const periodTypeLabel = (pt) => periodTypeOptions.find((opt) => opt.value === pt)?.label || pt

const loadAll = async () => {
  loading.value = true
  sessionCreatedGoals.value = []
  try {
    const [summaryRes, detailRes] = await Promise.all([
      api.getReviewDataSummary(periodType.value, anchorDateStr.value),
      api.getReviewDetail(periodType.value, anchorDateStr.value)
    ])
    summary.value = summaryRes.data
    if (detailRes.data) {
      answers.value = { ...defaultAnswers(), ...detailRes.data.answers }
    } else {
      answers.value = defaultAnswers()
    }
  } catch (error) {
    console.error('加载回顾数据失败:', error)
    message.error('加载回顾数据失败')
  } finally {
    loading.value = false
  }
}

watch([periodType, anchorDateStr], loadAll)

const handleSave = async (status) => {
  saving.value = true
  try {
    await api.saveReview({
      period_type: periodType.value,
      anchor_date: anchorDateStr.value,
      answers: answers.value,
      status
    })
    message.success(status === 'completed' ? '回顾已完成' : '草稿已保存')
  } catch (error) {
    console.error('保存回顾失败:', error)
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleGoalCreated = async (goal) => {
  if (goal) {
    sessionCreatedGoals.value.push(goal)
  }
  message.success('计划创建成功')
}

const openHistoryModal = async () => {
  showHistoryModal.value = true
  try {
    const res = await api.getReviewList()
    historyList.value = res.data || []
  } catch (error) {
    console.error('获取历史回顾失败:', error)
    message.error('获取历史回顾失败')
  }
}

const jumpToReview = (item) => {
  periodType.value = item.period_type
  anchorDateMs.value = parseLocalDateString(item.period_start)
  showHistoryModal.value = false
}

// onActivated 同时覆盖首次挂载和每次 KeepAlive 重新激活（Vue 首次挂载也会触发 onActivated），
// 不需要再额外写 onMounted，否则首次进入页面会重复请求两次
onActivated(loadAll)
</script>

<style scoped>
.review-page {
  max-width: 960px;
}
.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1em;
}
.period-switcher {
  display: flex;
  align-items: center;
  gap: 1em;
  margin-bottom: 1.5em;
}
.period-range-label {
  opacity: 0.6;
  font-size: 0.9em;
}
.metrics-section {
  margin-bottom: 1.5em;
}
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5em;
}
.metric-card p {
  margin: 0.4em 0;
  font-size: 0.92em;
}
.reflection-step {
  margin-bottom: 1.5em;
  padding: 1em 1.2em;
  background-color: rgba(128, 128, 128, 0.06);
  border-radius: 8px;
}
.reflection-step h4 {
  margin: 0 0 0.5em;
}
.step-guidance {
  opacity: 0.65;
  font-size: 0.85em;
  margin-bottom: 0.8em;
  line-height: 1.6;
}
.section-hint {
  opacity: 0.6;
  font-size: 0.9em;
}
.session-goal-list {
  margin: 0 0 1em;
  padding-left: 1.2em;
}
.review-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.8em;
  margin-top: 2em;
}
.history-item {
  display: flex;
  justify-content: space-between;
  padding: 0.6em 0;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
  cursor: pointer;
}
.history-status {
  opacity: 0.6;
  font-size: 0.85em;
}
</style>
```

- [ ] **Step 3: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/Goal/GoalFormModal.vue src/views/todo/Review/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 4: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开开发地址，用 `admin`/`123456` 登录。

验证清单：
- "待办事项"菜单下能看到"回顾总结"入口。
- 默认打开本周回顾，数据回顾三个区块能看到与实际数据吻合的内容。
- 切换周期类型为月/季/年，锚点日期变化，数据回顾区相应刷新。
- 填写七步反思任意几步后点"保存草稿"，刷新页面重新进入同一周期，草稿内容能回填。
- 点"完成本次回顾"后再打开"查看历史回顾"，能看到这条记录且状态为"已完成"。
- 点"添加新计划/目标"能打开计划创建弹窗并成功创建，创建后的计划出现在本页面的"新建计划"列表里；刷新页面后该列表清空（不持久化，符合设计）。
- 在三期已有的"计划"页面里，"+ 添加计划"仍能正常创建（确认 Step 1 对 `GoalFormModal.vue` 的改动没有破坏原有调用方）。
- 浏览器控制台无报错。

Expected: 以上行为均符合预期。

- [ ] **Step 5: 提交**

```bash
git add web/src/views/todo/Goal/GoalFormModal.vue web/src/views/todo/Review/index.vue
git commit -m "feat(web): add Review page with data summary, reflection, and history"
```

---

### Task 8: 端到端验证 + 收尾

**Files:**
- 无新增/修改文件（除非验证中发现问题，需要回到对应 Task 修复）。

**Interfaces:**
- Consumes：全部前序 Task 的产出。
- Produces：无——本任务是对整个回顾总结子系统的最终确认，对照 `docs/superpowers/specs/2026-08-13-task-system-phase4-review-design.md` 的验收标准逐条过一遍。

- [ ] **Step 1: 跑全量后端测试**

Run: `pytest -vv`
Expected: 全部通过（含一/二/三期遗留测试 + 本阶段新增的 `test_review.py` + `test_todo_statistics.py`，共 117 个）。

- [ ] **Step 2: 跑前端 lint（限定改动文件）**

Run: `cd web && pnpm exec eslint src/api/review.js src/api/index.js src/views/todo/Goal/GoalFormModal.vue src/views/todo/Review/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 用管理后台把新增 API 分配给角色**

启动后端（`python run.py`）后，用 `admin`/`123456` 登录管理后台，进入"系统管理 → API 管理"点击"刷新 API"，确认新增的 `/api/v1/review/*` 四个接口出现在列表里；进入"角色管理"，把这些接口分配给测试要用的角色（超级管理员本身跳过 API 校验，不受影响）。

- [ ] **Step 4: 浏览器端到端走查，对照 spec 验收标准**

Run: `cd web && pnpm dev`，浏览器登录后依次验证 `docs/superpowers/specs/2026-08-13-task-system-phase4-review-design.md` 的"验收标准"一节（与 Task 7 Step 3 的手动验证清单重叠，此处是最终整体确认，包含 `TodoHistory` 页面数据与优化前一致的检查）。

Expected: 全部符合预期。若发现偏差，回到对应 Task 定位问题、修复、重新跑一遍该 Task 的测试/验证步骤，再继续。

- [ ] **Step 5: 如果验证过程中做了修复，提交**

```bash
git add -A
git commit -m "fix: address issues found during phase4-review end-to-end verification"
```

（如果 Step 4 全部一次通过、没有任何修改，跳过本步。）
