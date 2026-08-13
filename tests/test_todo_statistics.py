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
