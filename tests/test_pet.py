from app.core.init_app import init_pet_config
from app.models.pet import PetCat, PetLine, PetProfile


async def test_pet_profile_defaults(db, test_user):
    profile = await PetProfile.create(user_id=test_user.id)
    assert profile.active_cat_code == "orange"
    assert profile.stats == {}
    assert profile.owned_cats == []
    assert profile.visit_streak == 1


async def test_pet_cat_stores_unlock_rules(db):
    cat = await PetCat.create(
        code="cow",
        name="奶牛猫",
        persona="毒舌",
        order=2,
        unlock=[{"field": "_total", "op": "gte", "value": 50}],
    )
    reloaded = await PetCat.get(code="cow")
    assert reloaded.unlock[0]["value"] == 50
    assert cat.is_active is True


async def test_pet_line_cat_code_nullable_means_universal(db):
    line = await PetLine.create(
        code="t_clear",
        cat_code=None,
        page="today",
        priority=10,
        conditions=[{"field": "pending", "op": "eq", "value": 0}],
        texts=["今天的事都做完了，好好歇会儿喵～"],
        unlock=[],
    )
    assert line.cat_code is None
    assert len(line.texts) == 1


async def test_init_pet_config_is_idempotent(db):
    await init_pet_config()
    first_count = await PetCat.all().count()
    await init_pet_config()
    assert await PetCat.all().count() == first_count
    assert first_count == 3


async def test_init_pet_config_seeds_lines(db):
    await init_pet_config()
    assert await PetLine.all().count() == 13
    universal = await PetLine.filter(cat_code=None).count()
    assert universal == 13, "移植阶段所有台词都是通用的（云函数里 cat_id 全是 '*'）"


async def test_init_pet_config_updates_changed_text(db):
    await init_pet_config()
    line = await PetLine.get(code="p_idle")
    await PetLine.filter(code="p_idle").update(texts=["被改坏了"])
    await init_pet_config()
    reloaded = await PetLine.get(code="p_idle")
    assert reloaded.texts != ["被改坏了"], "重跑初始化应把配置改回种子里的内容"


async def test_init_pet_config_does_not_bump_updated_at_when_unchanged(db):
    """内容没变时重跑初始化不应推进 updated_at —— 客户端的 config_version 依赖这一点

    回归用：曾用 update_or_create 无条件 save()，导致每次应用启动都刷新时间戳，
    客户端每次服务重启都要白拉一份配置。
    """
    await init_pet_config()
    before = {c.code: c.updated_at for c in await PetCat.all()}

    await init_pet_config()
    after = {c.code: c.updated_at for c in await PetCat.all()}

    assert after == before


async def test_pet_bootstrap_creates_profile_on_first_call(client, test_user):
    await init_pet_config()
    resp = await client.get("/api/v1/pet/bootstrap")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["pet"]["active_cat_id"] == "orange"
    assert data["pet"]["owned_cats"] == [{"cat_id": "orange", "at": data["pet"]["owned_cats"][0]["at"]}]
    assert data["total"] == 0
    assert await PetProfile.filter(user_id=test_user.id).count() == 1


async def test_pet_bootstrap_returns_config_in_client_shape(client, test_user):
    await init_pet_config()
    data = (await client.get("/api/v1/pet/bootstrap")).json()["data"]

    config = data["config"]
    assert config["version"] == data["config_version"]
    assert {c["_id"] for c in config["cats"]} == {"orange", "cow", "calico"}
    # 通用台词的 cat_id 必须是 "*"，cat.js 的过滤逻辑依赖这个字面量
    assert all(line["cat_id"] == "*" for line in config["lines"])
    assert all("_id" in line for line in config["lines"])


async def test_pet_bootstrap_omits_config_when_version_matches(client, test_user):
    await init_pet_config()
    first = (await client.get("/api/v1/pet/bootstrap")).json()["data"]
    version = first["config_version"]

    second = (await client.get("/api/v1/pet/bootstrap", params={"config_version": version})).json()["data"]
    assert "config" not in second, "版本一致时不应回传配置体，这是热页面零流量的前提"
    assert second["config_version"] == version


async def test_pet_bootstrap_unlocks_cat_when_total_reaches_threshold(client, test_user):
    await init_pet_config()
    await PetProfile.create(
        user_id=test_user.id, stats={"todo_completed": 60}, owned_cats=[{"cat_id": "orange", "at": 0}]
    )

    data = (await client.get("/api/v1/pet/bootstrap")).json()["data"]
    assert data["total"] == 60
    assert "cow" in data["newly_unlocked"]
    assert {o["cat_id"] for o in data["pet"]["owned_cats"]} == {"orange", "cow"}
    assert "calico" not in data["newly_unlocked"], "150 的门槛还没到"


async def test_pet_bootstrap_touch_false_does_not_update_visit(client, test_user):
    await init_pet_config()
    await client.get("/api/v1/pet/bootstrap")
    profile = await PetProfile.get(user_id=test_user.id)
    before = profile.last_seen_at

    await client.get("/api/v1/pet/bootstrap", params={"touch": "false"})
    profile = await PetProfile.get(user_id=test_user.id)
    assert profile.last_seen_at == before


async def test_pet_update_switches_to_owned_cat(client, test_user):
    await init_pet_config()
    await PetProfile.create(
        user_id=test_user.id,
        owned_cats=[{"cat_id": "orange", "at": 0}, {"cat_id": "cow", "at": 0}],
    )

    resp = await client.post("/api/v1/pet/update", json={"active_cat_id": "cow"})
    assert resp.status_code == 200
    assert resp.json()["data"]["active_cat_id"] == "cow"

    profile = await PetProfile.get(user_id=test_user.id)
    assert profile.active_cat_code == "cow"


async def test_pet_update_rejects_locked_cat(client, test_user):
    await init_pet_config()
    await PetProfile.create(user_id=test_user.id, owned_cats=[{"cat_id": "orange", "at": 0}])

    resp = await client.post("/api/v1/pet/update", json={"active_cat_id": "calico"})
    assert resp.json()["code"] == 400
    assert "解锁" in resp.json()["msg"]

    profile = await PetProfile.get(user_id=test_user.id)
    assert profile.active_cat_code == "orange"


async def test_pet_update_truncates_long_name(client, test_user):
    await init_pet_config()
    await PetProfile.create(user_id=test_user.id, owned_cats=[{"cat_id": "orange", "at": 0}])

    long_name = "喵" * 30
    resp = await client.post("/api/v1/pet/update", json={"pet_name": long_name})
    assert resp.json()["data"]["pet_name"] == "喵" * 20


async def test_pet_update_creates_profile_if_missing(client, test_user):
    await init_pet_config()
    resp = await client.post("/api/v1/pet/update", json={"pet_name": "小橘"})
    assert resp.json()["data"]["pet_name"] == "小橘"
    assert await PetProfile.filter(user_id=test_user.id).count() == 1
