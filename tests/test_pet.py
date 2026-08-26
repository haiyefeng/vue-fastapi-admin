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
