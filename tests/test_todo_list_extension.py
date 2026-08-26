from datetime import datetime

from app.models.todo import Goal, Project, QuadrantType, TimeBlock, TodoItem


async def test_create_defaults_to_inbox_when_no_project_given(client):
    resp = await client.post(
        "/api/v1/todo/create",
        json={"title": "浏览行业资讯", "quadrant_type": "not_urgent_not_important"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["project_id"] is None


async def test_list_filters_by_inbox_only(client, test_user):
    project = await Project.create(user_id=test_user.id, name="工作项目")
    await TodoItem.create(title="收件箱任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id)
    await TodoItem.create(
        title="项目任务",
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        user_id=test_user.id,
        project_id=project.id,
    )

    resp = await client.get("/api/v1/todo/list", params={"inbox_only": True})
    titles = [t["title"] for t in resp.json()["data"]]
    assert titles == ["收件箱任务"]


async def test_list_filters_by_project_id(client, test_user):
    project = await Project.create(user_id=test_user.id, name="工作项目")
    await TodoItem.create(title="收件箱任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id)
    await TodoItem.create(
        title="项目任务",
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        user_id=test_user.id,
        project_id=project.id,
    )

    resp = await client.get("/api/v1/todo/list", params={"project_id": project.id})
    titles = [t["title"] for t in resp.json()["data"]]
    assert titles == ["项目任务"]


async def test_list_filters_by_multiple_quadrants(client, test_user):
    await TodoItem.create(title="A", quadrant_type=QuadrantType.URGENT_IMPORTANT, user_id=test_user.id)
    await TodoItem.create(title="B", quadrant_type=QuadrantType.URGENT_NOT_IMPORTANT, user_id=test_user.id)
    await TodoItem.create(title="C", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id)

    resp = await client.get("/api/v1/todo/list", params={"quadrant_type": "urgent_important,urgent_not_important"})
    titles = {t["title"] for t in resp.json()["data"]}
    assert titles == {"A", "B"}


async def test_list_sort_by_due_date_ascending(client, test_user):
    await TodoItem.create(
        title="晚任务",
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        user_id=test_user.id,
        due_date=datetime(2026, 8, 20),
    )
    await TodoItem.create(
        title="早任务",
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        user_id=test_user.id,
        due_date=datetime(2026, 8, 10),
    )

    resp = await client.get("/api/v1/todo/list", params={"sort_by": "due_date", "sort_order": "asc"})
    titles = [t["title"] for t in resp.json()["data"]]
    assert titles == ["早任务", "晚任务"]


async def test_list_includes_subtask_counts(client, test_user):
    todo = await TodoItem.create(title="带子任务", quadrant_type=QuadrantType.URGENT_IMPORTANT, user_id=test_user.id)
    await client.post("/api/v1/subtask/create", json={"todo_item_id": todo.id, "title": "a"})
    sub2_resp = await client.post("/api/v1/subtask/create", json={"todo_item_id": todo.id, "title": "b"})
    await client.post("/api/v1/subtask/update", json={"id": sub2_resp.json()["data"]["id"], "is_completed": True})

    resp = await client.get("/api/v1/todo/list")
    item = next(t for t in resp.json()["data"] if t["title"] == "带子任务")
    assert item["subtask_total"] == 2
    assert item["subtask_completed"] == 1


async def test_create_todo_with_other_user_project_id_returns_404(client, test_user):
    """cross-user ownership check: create todo with a project_id owned by another user"""
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_project = await Project.create(user_id=other_user.id, name="他人的项目")

    resp = await client.post(
        "/api/v1/todo/create",
        json={
            "title": "越权任务",
            "quadrant_type": "not_urgent_not_important",
            "project_id": other_project.id,
        },
    )
    assert resp.status_code == 404


async def test_update_todo_with_other_user_project_id_returns_404(client, test_user):
    """cross-user ownership check: update todo to link a project_id owned by another user"""
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_project = await Project.create(user_id=other_user.id, name="他人的项目")
    todo = await TodoItem.create(
        title="正常任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id
    )

    resp = await client.post(
        "/api/v1/todo/update",
        json={"id": todo.id, "project_id": other_project.id},
    )
    assert resp.status_code == 404


async def test_create_todo_with_time_blocks(client, test_user):
    resp = await client.post(
        "/api/v1/todo/create",
        json={
            "title": "团队周会",
            "quadrant_type": "urgent_important",
            "time_blocks": [
                {"start_time": "2026-08-10T09:00:00", "end_time": "2026-08-10T10:00:00"},
                {"start_time": "2026-08-12T09:00:00", "end_time": "2026-08-12T10:00:00"},
            ],
        },
    )
    assert resp.status_code == 200
    todo_id = resp.json()["data"]["id"]

    list_resp = await client.get("/api/v1/timeblock/list", params={"todo_item_id": todo_id})
    assert len(list_resp.json()["data"]) == 2


async def test_create_todo_rejects_time_block_crossing_midnight(client):
    resp = await client.post(
        "/api/v1/todo/create",
        json={
            "title": "跨天任务",
            "quadrant_type": "urgent_important",
            "time_blocks": [{"start_time": "2026-08-10T23:30:00", "end_time": "2026-08-11T00:30:00"}],
        },
    )
    assert resp.status_code == 400


async def test_list_unscheduled_only_excludes_scheduled_and_completed(client, test_user):
    unscheduled = await TodoItem.create(
        title="未排程任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id
    )
    scheduled = await TodoItem.create(
        title="已排程任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id
    )
    await TimeBlock.create(
        todo_item_id=scheduled.id,
        user_id=test_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )
    await TodoItem.create(
        title="已完成任务",
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        user_id=test_user.id,
        is_completed=True,
    )
    del unscheduled  # 仅用于建库，断言走标题比较

    resp = await client.get("/api/v1/todo/list", params={"unscheduled_only": True})
    titles = [t["title"] for t in resp.json()["data"]]
    assert titles == ["未排程任务"]


async def test_unscheduled_only_not_polluted_by_other_user_time_block(client, test_user):
    """cross-user isolation: another user's TimeBlock must not count as 'scheduled' for test_user's todos"""
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_todo = await TodoItem.create(
        title="别人的任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=other_user.id
    )
    await TimeBlock.create(
        todo_item_id=other_todo.id,
        user_id=other_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )

    unscheduled = await TodoItem.create(
        title="我的未排程任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id
    )
    del unscheduled  # 仅用于建库，断言走标题比较

    resp = await client.get("/api/v1/todo/list", params={"unscheduled_only": True})
    titles = [t["title"] for t in resp.json()["data"]]
    assert titles == ["我的未排程任务"]


async def test_create_todo_with_other_user_goal_id_returns_404(client, test_user):
    """cross-user ownership check: create todo with a goal_id owned by another user"""
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_goal = await Goal.create(user_id=other_user.id, name="他人的计划")

    resp = await client.post(
        "/api/v1/todo/create",
        json={
            "title": "越权任务",
            "quadrant_type": "not_urgent_not_important",
            "goal_id": other_goal.id,
        },
    )
    assert resp.status_code == 404


async def test_update_todo_with_other_user_goal_id_returns_404(client, test_user):
    """cross-user ownership check: update todo to link a goal_id owned by another user"""
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_goal = await Goal.create(user_id=other_user.id, name="他人的计划")
    todo = await TodoItem.create(
        title="正常任务", quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT, user_id=test_user.id
    )

    resp = await client.post(
        "/api/v1/todo/update",
        json={"id": todo.id, "goal_id": other_goal.id},
    )
    assert resp.status_code == 404


async def test_create_todo_with_own_goal_id_succeeds(client, test_user):
    goal = await Goal.create(user_id=test_user.id, name="我的计划")

    resp = await client.post(
        "/api/v1/todo/create",
        json={"title": "关联任务", "quadrant_type": "not_urgent_not_important", "goal_id": goal.id},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["goal_id"] == goal.id


async def test_list_page_below_one_falls_back_to_first_page(client, test_user):
    """page < 1 时回落到第一页，而不是让 Tortoise 因负 offset 抛错（对齐云函数 pageArgs 的钳制）"""
    await TodoItem.create(title="任务A", quadrant_type=QuadrantType.URGENT_IMPORTANT, user_id=test_user.id)

    resp = await client.get("/api/v1/todo/list", params={"page": 0, "page_size": 10})
    assert resp.status_code == 200
    assert [t["title"] for t in resp.json()["data"]] == ["任务A"]


async def test_list_page_size_below_one_falls_back_to_one(client, test_user):
    """page_size < 1 时回落到 1 条，而不是返回空列表（对齐云函数 pageArgs 的钳制）"""
    await TodoItem.create(title="任务A", quadrant_type=QuadrantType.URGENT_IMPORTANT, user_id=test_user.id)
    await TodoItem.create(title="任务B", quadrant_type=QuadrantType.URGENT_IMPORTANT, user_id=test_user.id)

    resp = await client.get("/api/v1/todo/list", params={"page": 1, "page_size": 0})
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1
