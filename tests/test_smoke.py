async def test_todo_list_endpoint_reachable(client):
    response = await client.get("/api/v1/todo/list", params={"page": 1, "page_size": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["data"] == []
