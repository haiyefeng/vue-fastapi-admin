from datetime import date, datetime

from app.controllers.habit import habit_controller
from app.models.todo import Habit, HabitFrequencyType, QuadrantType, TodoItem


async def test_is_scheduled_day_daily(db, test_user):
    habit = await Habit.create(user_id=test_user.id, name="每天", frequency_type=HabitFrequencyType.DAILY)
    assert habit_controller.is_scheduled_day(habit, date(2026, 8, 24)) is True


async def test_is_scheduled_day_weekly_days(db, test_user):
    habit = await Habit.create(
        user_id=test_user.id,
        name="周一三五",
        frequency_type=HabitFrequencyType.WEEKLY_DAYS,
        frequency_config={"days": [1, 3, 5]},
    )
    assert habit_controller.is_scheduled_day(habit, date(2026, 8, 24)) is True  # 周一
    assert habit_controller.is_scheduled_day(habit, date(2026, 8, 25)) is False  # 周二


async def test_summary_counts_expected_and_completed(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="晨读", frequency_type=HabitFrequencyType.DAILY)
    # created_at 由 auto_now_add 写入的是真实墙钟时间，早于测试用固定日期窗口（2026-08-21~23）；
    # 回拨到窗口之前，避免 summary() 里 max(created_day, start) 的夹取把整个统计窗口夹没了
    habit.created_at = datetime(2026, 8, 20)
    await habit.save()
    for day, done in [(21, True), (22, True), (23, False)]:
        await TodoItem.create(
            title="晨读",
            user_id=test_user.id,
            habit_id=habit.id,
            quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT,
            generated_date=date(2026, 8, day),
            is_completed=done,
        )

    result = await habit_controller.summary(
        user_id=test_user.id, start=date(2026, 8, 21), end=date(2026, 8, 23), today=date(2026, 8, 23)
    )
    assert len(result) == 1
    assert result[0]["name"] == "晨读"
    assert result[0]["expected"] == 3
    assert result[0]["completed"] == 2


async def test_summary_excludes_paused_and_archived(client, test_user):
    await Habit.create(user_id=test_user.id, name="暂停的", frequency_type=HabitFrequencyType.DAILY, is_paused=True)
    await Habit.create(user_id=test_user.id, name="归档的", frequency_type=HabitFrequencyType.DAILY, is_archived=True)
    await Habit.create(user_id=test_user.id, name="正常的", frequency_type=HabitFrequencyType.DAILY)

    result = await habit_controller.summary(
        user_id=test_user.id, start=date(2026, 8, 21), end=date(2026, 8, 23), today=date(2026, 8, 23)
    )
    assert [r["name"] for r in result] == ["正常的"]


async def test_summary_weekly_count_uses_weekly_formula(client, test_user):
    habit = await Habit.create(
        user_id=test_user.id,
        name="每周三次",
        frequency_type=HabitFrequencyType.WEEKLY_COUNT,
        frequency_config={"count": 3},
    )
    await TodoItem.create(
        title="每周三次",
        user_id=test_user.id,
        habit_id=habit.id,
        quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT,
        generated_date=date(2026, 8, 24),
        is_completed=True,
    )

    # 8/17 ~ 8/30 共 14 天 = 2 周，期望 2*3 = 6 次
    result = await habit_controller.summary(
        user_id=test_user.id, start=date(2026, 8, 17), end=date(2026, 8, 30), today=date(2026, 8, 30)
    )
    assert result[0]["expected"] == 6
    assert result[0]["completed"] == 1
    assert result[0]["streak"] is None


async def test_summary_endpoint_returns_list(client, test_user):
    await Habit.create(user_id=test_user.id, name="喝水", frequency_type=HabitFrequencyType.DAILY)

    resp = await client.get("/api/v1/habit/summary", params={"start_date": "2026-08-21", "end_date": "2026-08-23"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert data[0]["name"] == "喝水"
