from app.models.todo import Category, Project, QuadrantType, TodoItem


async def test_project_create_with_new_category_name(client, test_user):
    resp = await client.post(
        "/api/v1/project/create",
        json={"name": "Q4 营销活动", "type": "project", "category_name": "工作"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["name"] == "Q4 营销活动"
    assert body["category_name"] == "工作"
    assert await Category.filter(name="工作", user_id=test_user.id).count() == 1


async def test_project_create_reuses_existing_category(client, test_user):
    await client.post("/api/v1/project/create", json={"name": "官网改版", "category_name": "工作"})
    await client.post("/api/v1/project/create", json={"name": "Q4 营销活动", "category_name": "工作"})

    assert await Category.filter(name="工作", user_id=test_user.id).count() == 1


async def test_category_list_returns_created_categories(client):
    await client.post("/api/v1/project/create", json={"name": "React 进阶", "category_name": "学习"})

    resp = await client.get("/api/v1/category/list")
    names = [c["name"] for c in resp.json()["data"]]
    assert "学习" in names


async def test_delete_project_moves_tasks_to_inbox_instead_of_deleting(client, test_user):
    create_resp = await client.post("/api/v1/project/create", json={"name": "临时项目"})
    project_id = create_resp.json()["data"]["id"]

    todo = await TodoItem.create(
        title="挂在临时项目下的任务",
        quadrant_type=QuadrantType.NOT_URGENT_NOT_IMPORTANT,
        user_id=test_user.id,
        project_id=project_id,
    )

    resp = await client.delete("/api/v1/project/delete", params={"project_id": project_id})
    assert resp.status_code == 200
    assert await Project.filter(id=project_id).count() == 0

    await todo.refresh_from_db()
    assert todo.project_id is None


async def test_project_update_can_clear_category(client):
    create_resp = await client.post("/api/v1/project/create", json={"name": "本周购物清单", "category_name": "清单"})
    project_id = create_resp.json()["data"]["id"]

    resp = await client.post("/api/v1/project/update", json={"id": project_id, "category_id": None})
    assert resp.status_code == 200
    assert resp.json()["data"]["category_name"] is None


async def test_delete_nonexistent_project_returns_404(client):
    resp = await client.delete("/api/v1/project/delete", params={"project_id": 99999})
    assert resp.status_code == 404


async def test_project_create_cannot_use_another_user_category_id(client, test_user):
    """创建项目时，不能用另一个用户的私有分类 ID"""
    from app.models.admin import User

    # Create a second user and their category
    other_user = await User.create(username="other_user", email="other@example.com", password="123456")
    other_category = await Category.create(user_id=other_user.id, name="Other's Private")

    # Try to create a project as test_user with other_user's category_id
    resp = await client.post(
        "/api/v1/project/create",
        json={"name": "My Project", "type": "project", "category_id": other_category.id},
    )

    assert resp.status_code == 200
    body = resp.json()["data"]

    # Should NOT have the category linked (should fall back to None since no category_name provided)
    assert body["category_id"] is None or body["category_name"] is None

    # Verify the project exists but isn't linked to other_user's category
    project = await Project.filter(id=body["id"], user_id=test_user.id).first()
    assert project is not None
    assert project.category_id is None


async def test_project_update_cannot_use_another_user_category_id(client, test_user):
    """更新项目时，不能改为另一个用户的私有分类 ID"""
    from app.models.admin import User

    # Create a project
    create_resp = await client.post("/api/v1/project/create", json={"name": "My Project", "type": "project"})
    project_id = create_resp.json()["data"]["id"]

    # Create a second user and their category
    other_user = await User.create(username="other_user2", email="other2@example.com", password="123456")
    other_category = await Category.create(user_id=other_user.id, name="Other's Private 2")

    # Try to update the project with other_user's category_id
    update_resp = await client.post(
        "/api/v1/project/update",
        json={"id": project_id, "category_id": other_category.id},
    )

    assert update_resp.status_code == 200
    body = update_resp.json()["data"]

    # Should NOT have the category linked to other_user's category
    assert body["category_id"] is None or body["category_name"] is None

    # Verify the project exists but isn't linked to other_user's category
    project = await Project.filter(id=project_id, user_id=test_user.id).first()
    assert project is not None
    assert project.category_id is None
