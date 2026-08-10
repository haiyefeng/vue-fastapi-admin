from datetime import date, datetime, timedelta

from app.models.todo import Habit, HabitFrequencyType, QuadrantType, TodoItem


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


async def test_create_habit_with_reminder_time_returns_200(client):
    resp = await client.post(
        "/api/v1/habit/create",
        json={"name": "早起", "frequency_type": "daily", "reminder_time": "07:30:00"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["reminder_time"] == "07:30:00"


async def test_update_habit_with_reminder_time_returns_200(client):
    create_resp = await client.post(
        "/api/v1/habit/create", json={"name": "喝水", "frequency_type": "daily"}
    )
    habit_id = create_resp.json()["data"]["id"]

    resp = await client.post(
        "/api/v1/habit/update", json={"id": habit_id, "reminder_time": "07:30:00"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["reminder_time"] == "07:30:00"


async def test_archived_habit_with_reminder_time_returns_200(client):
    create_resp = await client.post(
        "/api/v1/habit/create",
        json={"name": "早起", "frequency_type": "daily", "reminder_time": "07:30:00"},
    )
    habit_id = create_resp.json()["data"]["id"]

    resp = await client.post("/api/v1/habit/update", json={"id": habit_id, "is_archived": True})
    assert resp.status_code == 200

    resp = await client.get("/api/v1/habit/archived")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data[0]["reminder_time"] == "07:30:00"


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
