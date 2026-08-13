from datetime import date, datetime

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


from datetime import timedelta

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
    # A week safely in the past (2020), well after the habit's creation and well before
    # "today" — keeps the expected==7 assertion independent of when this test actually
    # runs, since neither clamp bound (creation date, today) falls inside this week.
    habit = await Habit.create(
        user_id=test_user.id, name="晨间阅读", frequency_type=HabitFrequencyType.DAILY,
        created_at=datetime(2019, 1, 1),
    )
    await TodoItem.create(
        title="晨间阅读", user_id=test_user.id, habit_id=habit.id,
        quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT, generated_date="2020-01-08", is_completed=True,
    )

    resp = await client.get(
        "/api/v1/review/data-summary", params={"period_type": "week", "anchor_date": "2020-01-06"}
    )
    habits = resp.json()["data"]["habits"]
    assert len(habits) == 1
    assert habits[0]["expected"] == 7
    assert habits[0]["completed"] == 1
    assert habits[0]["streak"] is not None


async def test_data_summary_habit_checkin_expected_clamped_to_creation_date(client, test_user):
    """created mid-week, in a week safely in the past: expected should only count days
    from creation date onward, not the full week before creation. Using a past week
    (not "this week") keeps the assertion independent of whatever "today" actually is
    when the test runs — only the creation-date lower clamp is exercised here, never
    the today upper clamp."""
    habit = await Habit.create(
        user_id=test_user.id, name="新习惯", frequency_type=HabitFrequencyType.DAILY,
        created_at=datetime(2020, 1, 8),  # Wednesday of the week 2020-01-06 (Mon) ~ 2020-01-12 (Sun)
    )

    resp = await client.get(
        "/api/v1/review/data-summary", params={"period_type": "week", "anchor_date": "2020-01-06"}
    )
    habits = resp.json()["data"]["habits"]
    # week is 2020-01-06 (Mon) to 2020-01-12 (Sun); habit created 2020-01-08 (Wed):
    # [max(01-06, 01-08), min(01-12, today)] = [01-08, 01-12] = 5 days
    assert habits[0]["expected"] == 5


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
