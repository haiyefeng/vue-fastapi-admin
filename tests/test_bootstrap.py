from app.models.todo import Category, Goal, Habit, HabitFrequencyType, Project


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


async def test_goal_bootstrap_returns_active_and_archived(client, test_user):
    await Goal.create(user_id=test_user.id, name="学英语")
    await Goal.create(user_id=test_user.id, name="旧目标", is_archived=True)

    data = (await client.get("/api/v1/goal/bootstrap")).json()["data"]
    assert [g["name"] for g in data["list"]] == ["学英语"]
    assert [g["name"] for g in data["archived"]] == ["旧目标"]


async def test_goal_bootstrap_matches_separate_endpoints(client, test_user):
    await Goal.create(user_id=test_user.id, name="健身")

    merged = (await client.get("/api/v1/goal/bootstrap")).json()["data"]
    listed = (await client.get("/api/v1/goal/list")).json()["data"]
    archived = (await client.get("/api/v1/goal/archived")).json()["data"]

    assert merged["list"] == listed
    assert merged["archived"] == archived


async def test_project_bootstrap_returns_projects_and_categories(client, test_user):
    category = await Category.create(user_id=test_user.id, name="工作")
    await Project.create(user_id=test_user.id, name="上线计划", category_id=category.id)

    data = (await client.get("/api/v1/project/bootstrap")).json()["data"]
    assert [p["name"] for p in data["list"]] == ["上线计划"]
    assert [c["name"] for c in data["categories"]] == ["工作"]


async def test_project_bootstrap_matches_separate_endpoints(client, test_user):
    await Category.create(user_id=test_user.id, name="生活")
    await Project.create(user_id=test_user.id, name="搬家")

    merged = (await client.get("/api/v1/project/bootstrap")).json()["data"]
    projects = (await client.get("/api/v1/project/list")).json()["data"]
    categories = (await client.get("/api/v1/category/list")).json()["data"]

    assert merged["list"] == projects
    assert merged["categories"] == categories
