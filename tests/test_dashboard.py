from datetime import date, datetime, time, timedelta

from app.models.admin import User
from app.models.todo import Habit, HabitFrequencyType, QuadrantType, TimeBlock, TodoItem


async def test_today_overview_schedule_from_time_blocks(client, test_user):
    todo = await TodoItem.create(title="团队会议", user_id=test_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT)
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
        title="今天到期",
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
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
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime.combine(today, time(14, 0)),
        end_time=datetime.combine(today, time(15, 0)),
    )

    resp = await client.get("/api/v1/dashboard/today")
    tasks = resp.json()["data"]["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "今天有时间块但无截止日期"


async def test_today_overview_tasks_excludes_completed(client, test_user):
    today = date.today()
    await TodoItem.create(
        title="已完成",
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
        due_date=datetime.combine(today, time(18, 0)),
        is_completed=True,
    )

    resp = await client.get("/api/v1/dashboard/today")
    assert resp.json()["data"]["tasks"] == []


async def test_today_overview_tasks_excludes_habit_generated(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="打卡", frequency_type=HabitFrequencyType.DAILY)
    today = date.today()
    await TodoItem.create(
        title="习惯待办",
        user_id=test_user.id,
        habit_id=habit.id,
        quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT,
        due_date=datetime.combine(today, time(18, 0)),
        generated_date=today,
    )

    resp = await client.get("/api/v1/dashboard/today")
    assert resp.json()["data"]["tasks"] == []


async def test_today_overview_tasks_excludes_habit_generated_via_time_block(client, test_user):
    """习惯生成的待办即使排了今天的时间块（没有 due_date），也不该出现在"今日待办"里——
    否则会和"今日习惯"区块里的同一件事重复展示，违反设计规范的展示分流规则"""
    habit = await Habit.create(user_id=test_user.id, name="打卡", frequency_type=HabitFrequencyType.DAILY)
    today = date.today()
    todo = await TodoItem.create(
        title="习惯待办排了时间块",
        user_id=test_user.id,
        habit_id=habit.id,
        quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT,
        generated_date=today,
    )
    await TimeBlock.create(
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime.combine(today, time(7, 0)),
        end_time=datetime.combine(today, time(8, 0)),
    )

    resp = await client.get("/api/v1/dashboard/today")
    assert resp.json()["data"]["tasks"] == []


async def test_today_overview_tasks_excludes_due_tomorrow(client, test_user):
    tomorrow = date.today() + timedelta(days=1)
    await TodoItem.create(
        title="明天到期",
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
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
        todo_item_id=todo_no_due.id,
        user_id=test_user.id,
        start_time=datetime.combine(today, time(8, 0)),
        end_time=datetime.combine(today, time(9, 0)),
    )
    await TodoItem.create(
        title="下午到期",
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
        due_date=datetime.combine(today, time(18, 0)),
    )
    await TodoItem.create(
        title="上午到期",
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
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
        user_id=test_user.id,
        name="固定某天",
        frequency_type=HabitFrequencyType.WEEKLY_DAYS,
        frequency_config={"days": [other_weekday]},
    )

    resp = await client.get("/api/v1/dashboard/today")
    habits = resp.json()["data"]["habits"]
    assert len(habits) == 1
    assert habits[0]["name"] == "每天"
    assert habits[0]["today_todo_id"] is not None


async def test_today_overview_habits_excludes_paused(client, test_user):
    await Habit.create(user_id=test_user.id, name="已暂停", frequency_type=HabitFrequencyType.DAILY, is_paused=True)

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
        title="别人的任务",
        user_id=other_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
        due_date=datetime.combine(today, time(18, 0)),
    )
    await Habit.create(user_id=other_user.id, name="别人的习惯", frequency_type=HabitFrequencyType.DAILY)

    resp = await client.get("/api/v1/dashboard/today")
    data = resp.json()["data"]
    assert data["tasks"] == []
    assert data["habits"] == []


async def test_today_overview_isolated_per_user_via_time_block(client, test_user):
    """别人的待办即使排了今天的时间块，也不该出现在当前用户的今日待办里——
    验证 _get_today_tasks 最终查询的 user_id 过滤对 scheduled_today_ids 这条分支也生效，
    不能只依赖 TimeBlock 归属校验的传递性保证"""
    other_user = await User.create(username="other2", email="other2@example.com", password="x")
    other_todo = await TodoItem.create(
        title="别人排了时间块的任务", user_id=other_user.id, quadrant_type=QuadrantType.URGENT_IMPORTANT
    )
    today = date.today()
    await TimeBlock.create(
        todo_item_id=other_todo.id,
        user_id=other_user.id,
        start_time=datetime.combine(today, time(10, 0)),
        end_time=datetime.combine(today, time(11, 0)),
    )

    resp = await client.get("/api/v1/dashboard/today")
    assert resp.json()["data"]["tasks"] == []
