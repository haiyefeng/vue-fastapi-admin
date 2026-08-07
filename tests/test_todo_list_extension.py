from datetime import datetime

from app.models.todo import Project, QuadrantType, TodoItem


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
