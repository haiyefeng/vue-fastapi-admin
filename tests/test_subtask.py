from app.models.todo import QuadrantType, SubTask, TodoItem


async def _create_todo(user_id):
    return await TodoItem.create(
        title="完成项目报告初稿",
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
        user_id=user_id,
    )


async def test_create_and_list_subtasks_in_order(client, test_user):
    todo = await _create_todo(test_user.id)

    resp1 = await client.post("/api/v1/subtask/create", json={"todo_item_id": todo.id, "title": "收集数据"})
    assert resp1.status_code == 200
    assert resp1.json()["data"]["order"] == 0

    resp2 = await client.post("/api/v1/subtask/create", json={"todo_item_id": todo.id, "title": "撰写第一部分"})
    assert resp2.json()["data"]["order"] == 1

    list_resp = await client.get("/api/v1/subtask/list", params={"todo_item_id": todo.id})
    titles = [s["title"] for s in list_resp.json()["data"]]
    assert titles == ["收集数据", "撰写第一部分"]


async def test_update_subtask_completion(client, test_user):
    todo = await _create_todo(test_user.id)
    subtask = await SubTask.create(todo_item_id=todo.id, title="图表制作", order=0)

    resp = await client.post("/api/v1/subtask/update", json={"id": subtask.id, "is_completed": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["is_completed"] is True


async def test_delete_subtask(client, test_user):
    todo = await _create_todo(test_user.id)
    subtask = await SubTask.create(todo_item_id=todo.id, title="待删除", order=0)

    resp = await client.delete("/api/v1/subtask/delete", params={"subtask_id": subtask.id})
    assert resp.status_code == 200
    assert await SubTask.filter(id=subtask.id).count() == 0


async def test_create_subtask_for_missing_todo_returns_404(client):
    resp = await client.post("/api/v1/subtask/create", json={"todo_item_id": 99999, "title": "x"})
    assert resp.status_code == 404


async def test_deleting_todo_cascades_to_subtasks(client, test_user):
    todo = await _create_todo(test_user.id)
    await SubTask.create(todo_item_id=todo.id, title="子任务", order=0)

    resp = await client.delete("/api/v1/todo/delete", params={"todo_id": todo.id})
    assert resp.status_code == 200
    assert await SubTask.filter(todo_item_id=todo.id).count() == 0
