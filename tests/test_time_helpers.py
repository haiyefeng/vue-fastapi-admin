from datetime import time, timedelta, timezone

from app.utils.time_helpers import to_naive_time


def test_to_naive_time_returns_none_for_none():
    assert to_naive_time(None) is None


def test_to_naive_time_converts_timedelta_to_time():
    assert to_naive_time(timedelta(hours=7, minutes=30)) == time(7, 30)


def test_to_naive_time_converts_zero_timedelta_to_midnight():
    assert to_naive_time(timedelta(0)) == time(0, 0)


def test_to_naive_time_strips_tzinfo_from_time():
    aware = time(7, 30, tzinfo=timezone.utc)
    assert to_naive_time(aware) == time(7, 30)


def test_to_naive_time_leaves_naive_time_unchanged():
    assert to_naive_time(time(7, 30)) == time(7, 30)
