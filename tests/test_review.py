from datetime import date

from app.controllers.review import ReviewController
from app.models.todo import Review, ReviewPeriodType


def test_calc_period_range_week():
    start, end = ReviewController.calc_period_range(ReviewPeriodType.WEEK, date(2026, 8, 13))
    assert start == date(2026, 8, 10)
    assert end == date(2026, 8, 16)


def test_calc_period_range_month():
    start, end = ReviewController.calc_period_range(ReviewPeriodType.MONTH, date(2026, 8, 13))
    assert start == date(2026, 8, 1)
    assert end == date(2026, 8, 31)


def test_calc_period_range_quarter():
    start, end = ReviewController.calc_period_range(ReviewPeriodType.QUARTER, date(2026, 8, 13))
    assert start == date(2026, 7, 1)
    assert end == date(2026, 9, 30)


def test_calc_period_range_year():
    start, end = ReviewController.calc_period_range(ReviewPeriodType.YEAR, date(2026, 8, 13))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 12, 31)


async def test_save_review_creates_draft(client, test_user):
    resp = await client.post(
        "/api/v1/review/save",
        json={"period_type": "week", "anchor_date": "2026-08-13", "answers": {"step1": "挑战是论文进展缓慢"}},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["period_start"] == "2026-08-10"
    assert data["period_end"] == "2026-08-16"
    assert data["status"] == "draft"
    assert data["answers"]["step1"] == "挑战是论文进展缓慢"


async def test_save_review_same_period_overwrites_existing(client, test_user):
    await client.post(
        "/api/v1/review/save",
        json={"period_type": "week", "anchor_date": "2026-08-13", "answers": {"step1": "第一版"}},
    )
    resp = await client.post(
        "/api/v1/review/save",
        json={"period_type": "week", "anchor_date": "2026-08-15", "answers": {"step1": "第二版"}},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["answers"]["step1"] == "第二版"
    assert await Review.filter(user_id=test_user.id, period_type=ReviewPeriodType.WEEK).count() == 1


async def test_save_review_completed_status(client, test_user):
    resp = await client.post(
        "/api/v1/review/save",
        json={"period_type": "week", "anchor_date": "2026-08-13", "answers": {}, "status": "completed"},
    )
    assert resp.json()["data"]["status"] == "completed"


async def test_get_review_detail_returns_null_when_not_found(client, test_user):
    resp = await client.get(
        "/api/v1/review/detail", params={"period_type": "week", "anchor_date": "2026-08-13"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"] is None


async def test_get_review_detail_returns_existing(client, test_user):
    await client.post(
        "/api/v1/review/save",
        json={"period_type": "month", "anchor_date": "2026-08-13", "answers": {"step7": "调整作息"}},
    )
    resp = await client.get(
        "/api/v1/review/detail", params={"period_type": "month", "anchor_date": "2026-08-20"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["answers"]["step7"] == "调整作息"


async def test_get_review_list_ordered_by_period_start_desc(client, test_user):
    await client.post("/api/v1/review/save", json={"period_type": "week", "anchor_date": "2026-08-06"})
    await client.post("/api/v1/review/save", json={"period_type": "week", "anchor_date": "2026-08-13"})

    resp = await client.get("/api/v1/review/list")
    data = resp.json()["data"]
    assert len(data) == 2
    assert data[0]["period_start"] == "2026-08-10"
    assert data[1]["period_start"] == "2026-08-03"


async def test_get_review_list_filter_by_period_type(client, test_user):
    await client.post("/api/v1/review/save", json={"period_type": "week", "anchor_date": "2026-08-13"})
    await client.post("/api/v1/review/save", json={"period_type": "month", "anchor_date": "2026-08-13"})

    resp = await client.get("/api/v1/review/list", params={"period_type": "month"})
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["period_type"] == "month"


async def test_reviews_are_isolated_per_user(client, test_user):
    from app.models.admin import User

    other_user = await User.create(username="other", email="other@example.com", password="x")
    await Review.create(
        user_id=other_user.id, period_type=ReviewPeriodType.WEEK, period_start="2026-08-10", period_end="2026-08-16"
    )

    resp = await client.get("/api/v1/review/list")
    assert resp.json()["data"] == []
