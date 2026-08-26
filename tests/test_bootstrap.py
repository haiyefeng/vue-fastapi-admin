from app.models.todo import Habit, HabitFrequencyType


async def test_habit_bootstrap_returns_active_and_archived(client, test_user):
    await Habit.create(user_id=test_user.id, name="晨跑", frequency_type=HabitFrequencyType.DAILY)
    await Habit.create(user_id=test_user.id, name="旧习惯", frequency_type=HabitFrequencyType.DAILY, is_archived=True)

    resp = await client.get("/api/v1/habit/bootstrap")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert [h["name"] for h in data["list"]] == ["晨跑"]
    assert [h["name"] for h in data["archived"]] == ["旧习惯"]
    # 与 /habit/list 同构：带今日打卡状态字段
    assert "today_todo_id" in data["list"][0]
    assert "streak" in data["list"][0]


async def test_habit_bootstrap_matches_separate_endpoints(client, test_user):
    await Habit.create(user_id=test_user.id, name="读书", frequency_type=HabitFrequencyType.DAILY)

    merged = (await client.get("/api/v1/habit/bootstrap")).json()["data"]
    listed = (await client.get("/api/v1/habit/list")).json()["data"]
    archived = (await client.get("/api/v1/habit/archived")).json()["data"]

    assert merged["list"] == listed
    assert merged["archived"] == archived
