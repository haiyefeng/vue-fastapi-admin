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
