from datetime import datetime, time, timedelta
from typing import Optional, Union


def to_naive_time(value: Optional[Union[time, timedelta]]) -> Optional[time]:
    """归一化 Tortoise TimeField 读回的 python 值为不带 tzinfo 的 time。

    同一个 TimeField 在不同 DB 后端下读回的类型不一致：MySQL（asyncmy 驱动）的 TIME 列
    固定读回 datetime.timedelta（因为 MySQL TIME 值域可超出 datetime.time 能表示的
    [00:00:00, 24:00:00) 范围，驱动统一用 timedelta 表示，Tortoise 原样透传）；SQLite
    等后端则读回 datetime.time，但在非 UTC 时区配置下 tortoise 会用 pytz 的 LMT 兜底
    附上一个虚假 tzinfo（历史时区，如 Asia/Shanghai 为 +8:06 而非 +8:00），需要剥离。
    """
    if value is None:
        return None
    if isinstance(value, timedelta):
        return (datetime.min + value).time()
    return value.replace(tzinfo=None)
