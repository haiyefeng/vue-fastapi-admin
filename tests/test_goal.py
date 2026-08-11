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
