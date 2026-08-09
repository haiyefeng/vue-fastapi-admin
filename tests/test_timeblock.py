from datetime import datetime

from app.models.todo import QuadrantType, TimeBlock, TodoItem


async def _create_todo(user_id, title="项目评审会议"):
    return await TodoItem.create(title=title, quadrant_type=QuadrantType.URGENT_IMPORTANT, user_id=user_id)


async def test_create_time_block(client, test_user):
    todo = await _create_todo(test_user.id)
    resp = await client.post(
        "/api/v1/timeblock/create",
        json={
            "todo_item_id": todo.id,
            "start_time": "2026-08-10T09:00:00",
            "end_time": "2026-08-10T10:30:00",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["todo_item_id"] == todo.id
    assert data["title"] == "项目评审会议"
    assert data["quadrant_type"] == "urgent_important"


async def test_create_time_block_rejects_end_before_start(client, test_user):
    todo = await _create_todo(test_user.id)
    resp = await client.post(
        "/api/v1/timeblock/create",
        json={"todo_item_id": todo.id, "start_time": "2026-08-10T10:00:00", "end_time": "2026-08-10T09:00:00"},
    )
    assert resp.status_code == 400


async def test_create_time_block_rejects_crossing_midnight(client, test_user):
    todo = await _create_todo(test_user.id)
    resp = await client.post(
        "/api/v1/timeblock/create",
        json={"todo_item_id": todo.id, "start_time": "2026-08-10T23:30:00", "end_time": "2026-08-11T00:30:00"},
    )
    assert resp.status_code == 400


async def test_create_time_block_for_missing_todo_returns_404(client):
    resp = await client.post(
        "/api/v1/timeblock/create",
        json={"todo_item_id": 99999, "start_time": "2026-08-10T09:00:00", "end_time": "2026-08-10T10:00:00"},
    )
    assert resp.status_code == 404


async def test_list_by_date_range(client, test_user):
    todo = await _create_todo(test_user.id)
    await TimeBlock.create(
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )
    await TimeBlock.create(
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime(2026, 9, 1, 9, 0),
        end_time=datetime(2026, 9, 1, 10, 0),
    )

    resp = await client.get("/api/v1/timeblock/list", params={"start_date": "2026-08-03", "end_date": "2026-08-09"})
    assert resp.json()["data"] == []

    resp = await client.get("/api/v1/timeblock/list", params={"start_date": "2026-08-10", "end_date": "2026-08-10"})
    assert len(resp.json()["data"]) == 1


async def test_list_by_todo_item_id(client, test_user):
    todo = await _create_todo(test_user.id)
    await TimeBlock.create(
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )
    resp = await client.get("/api/v1/timeblock/list", params={"todo_item_id": todo.id})
    assert len(resp.json()["data"]) == 1


async def test_list_requires_todo_id_or_date_range(client):
    resp = await client.get("/api/v1/timeblock/list")
    assert resp.status_code == 400


async def test_delete_time_block(client, test_user):
    todo = await _create_todo(test_user.id)
    block = await TimeBlock.create(
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )
    resp = await client.delete("/api/v1/timeblock/delete", params={"time_block_id": block.id})
    assert resp.status_code == 200
    assert await TimeBlock.filter(id=block.id).count() == 0


async def test_deleting_todo_cascades_to_time_blocks(client, test_user):
    todo = await _create_todo(test_user.id)
    await TimeBlock.create(
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )
    resp = await client.delete("/api/v1/todo/delete", params={"todo_id": todo.id})
    assert resp.status_code == 200
    assert await TimeBlock.filter(todo_item_id=todo.id).count() == 0


async def test_create_time_block_for_other_user_todo_returns_404(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_todo = await _create_todo(other_user.id, title="别人的会议")

    resp = await client.post(
        "/api/v1/timeblock/create",
        json={"todo_item_id": other_todo.id, "start_time": "2026-08-10T09:00:00", "end_time": "2026-08-10T10:00:00"},
    )
    assert resp.status_code == 404


async def test_delete_time_block_owned_by_other_user_returns_404(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_todo = await _create_todo(other_user.id, title="别人的会议")
    other_block = await TimeBlock.create(
        todo_item_id=other_todo.id,
        user_id=other_user.id,
        start_time=datetime(2026, 8, 10, 9, 0),
        end_time=datetime(2026, 8, 10, 10, 0),
    )

    resp = await client.delete("/api/v1/timeblock/delete", params={"time_block_id": other_block.id})
    assert resp.status_code == 404
    assert await TimeBlock.filter(id=other_block.id).count() == 1


async def test_list_by_todo_item_id_for_other_user_returns_404(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x", is_superuser=True)
    other_todo = await _create_todo(other_user.id, title="别人的会议")

    resp = await client.get("/api/v1/timeblock/list", params={"todo_item_id": other_todo.id})
    assert resp.status_code == 404
