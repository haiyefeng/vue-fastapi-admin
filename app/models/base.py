import asyncio
from datetime import datetime, timedelta

from tortoise import fields, models

from app.settings import settings
from app.utils.time_helpers import to_naive_time


class BaseModel(models.Model):
    id = fields.BigIntField(pk=True, index=True)

    async def to_dict(self, m2m: bool = False, exclude_fields: list[str] | None = None):
        if exclude_fields is None:
            exclude_fields = []

        d = {}
        for field in self._meta.db_fields:
            if field not in exclude_fields:
                value = getattr(self, field)
                if isinstance(value, datetime):
                    value = value.strftime(settings.DATETIME_FORMAT)
                elif isinstance(value, timedelta):
                    # MySQL 下 TimeField 读回的是 timedelta（无 isoformat 方法），归一化成
                    # time 后再序列化，详见 to_naive_time 的说明
                    value = to_naive_time(value).isoformat()
                elif hasattr(value, "isoformat"):  # 处理 date 和其他有 isoformat 方法的类型
                    value = value.isoformat()
                d[field] = value

        if m2m:
            tasks = [
                self.__fetch_m2m_field(field, exclude_fields)
                for field in self._meta.m2m_fields
                if field not in exclude_fields
            ]
            results = await asyncio.gather(*tasks)
            for field, values in results:
                d[field] = values

        return d

    async def __fetch_m2m_field(self, field, exclude_fields):
        values = await getattr(self, field).all().values()
        formatted_values = []

        for value in values:
            formatted_value = {}
            for k, v in value.items():
                if k not in exclude_fields:
                    if isinstance(v, datetime):
                        formatted_value[k] = v.strftime(settings.DATETIME_FORMAT)
                    elif hasattr(v, "isoformat"):  # 处理 date 和其他有 isoformat 方法的类型
                        formatted_value[k] = v.isoformat()
                    else:
                        formatted_value[k] = v
            formatted_values.append(formatted_value)

        return field, formatted_values

    class Meta:
        abstract = True


class UUIDModel:
    uuid = fields.UUIDField(unique=True, pk=False, index=True)


class TimestampMixin:
    created_at = fields.DatetimeField(auto_now_add=True, index=True)
    updated_at = fields.DatetimeField(auto_now=True, index=True)
