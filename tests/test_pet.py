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
