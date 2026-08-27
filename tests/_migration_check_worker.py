"""子进程 worker：比对「迁移建出的 schema」与「模型描述的 schema」是否一致。

为什么不用 aerich 的记账做判据：aerich 的 Command._upgrade 里写的是
content=get_models_describe(self.app)——即**应用迁移那一刻从当前模型现算的快照**，
而不是迁移文件生成时冻结下来的。拿它跟 get_models_describe() 比是同义反复，
无论模型是否漂移都恒等（已实测：加字段不生成迁移，比对仍然通过）。
唯一可靠的判据是比对两个库的真实 schema。

为什么是子进程：settings 是模块级单例，在进程内改它来切库失败过。

隔离防护的边界：启动时只拒绝以 "plan" 开头的库名（本仓库开发库叫 plan）。
DB_MODELS 指向的库会被 generate_schemas() 直接建表，所以**手工调用本 worker 时
务必传一次性库名**——若指向一个不叫 plan* 的重要库，这层防护拦不住。
测试入口 tests/test_migration_consistency.py 传的是 migcheck_* 前缀的一次性库，
并在 finally 里无条件 DROP。

用法：DB_MIGRATIONS=<库A> DB_MODELS=<库B> python tests/_migration_check_worker.py

退出码：
  0 一致
  2 隔离校验失败
  3 迁移应用失败（迁移 SQL 在 MySQL 上跑不通）
  4 两个库的 schema 不一致（有模型变更未生成迁移，或迁移多建了东西）
"""

import asyncio
import copy
import os
import sys

# 以子进程方式直接运行时，项目根目录不在 sys.path 上
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 比对的列。只取 (table_name, column_name, data_type, is_nullable) 是不够的：
# VARCHAR(30) 与 VARCHAR(300) 的 data_type 同为 'varchar'，改 max_length 不生成迁移会漏过去。
# 补上长度/精度/默认值/键类型后，max_length、DECIMAL 精度、默认值、唯一键四类漂移一并覆盖。
# 仍看不见的：索引名与组合、外键、列注释、表字符集（要另查 information_schema.statistics
# 等目录表，成本更高，暂不纳入）。
# 注意 asyncmy 的 dict 游标返回的键是 information_schema 目录里实际存的大写列名，
# 与 SQL 里怎么写大小写无关，所以下面统一按大写取。
SCHEMA_FIELDS = (
    "TABLE_NAME",
    "COLUMN_NAME",
    "DATA_TYPE",
    "IS_NULLABLE",
    "CHARACTER_MAXIMUM_LENGTH",
    "NUMERIC_PRECISION",
    "NUMERIC_SCALE",
    "COLUMN_DEFAULT",
    "COLUMN_KEY",
)

SCHEMA_QUERY = f"""
    SELECT {", ".join(f.lower() for f in SCHEMA_FIELDS)}
    FROM information_schema.columns
    WHERE table_schema = %s
"""


def _config_for(database: str) -> dict:
    """基于项目配置复制一份、只把库名换掉，避免改动全局 settings"""
    from app.settings.config import settings

    cfg = copy.deepcopy(settings.TORTOISE_ORM)
    cfg["connections"]["mysql"]["credentials"]["database"] = database
    return cfg


async def _introspect(database: str) -> set:
    """读该库的列结构，归一化成可比对的集合（每行一个 SCHEMA_FIELDS 顺序的元组）"""
    from tortoise import Tortoise

    conn = Tortoise.get_connection("mysql")
    rows = await conn.execute_query_dict(SCHEMA_QUERY, [database])
    return {tuple(r[field] for field in SCHEMA_FIELDS) for r in rows}


async def _schema_from_migrations(database: str) -> set:
    """库A：应用版本库里的迁移文件，返回由此得到的 schema"""
    from aerich import Command
    from tortoise import Tortoise

    cfg = _config_for(database)
    command = Command(tortoise_config=cfg)
    await command.init()
    await command.upgrade(run_in_transaction=True)
    schema = await _introspect(database)
    await Tortoise.close_connections()
    return schema


async def _schema_from_models(database: str) -> set:
    """库B：用 generate_schemas() 从当前模型建表，返回由此得到的 schema"""
    from tortoise import Tortoise

    await Tortoise.init(config=_config_for(database))
    await Tortoise.generate_schemas()
    schema = await _introspect(database)
    await Tortoise.close_connections()
    return schema


def _describe(diff: set, limit: int = 20) -> str:
    def one(row: tuple) -> str:
        attrs = ", ".join(f"{f.lower()}={v!r}" for f, v in zip(SCHEMA_FIELDS[2:], row[2:]) if v is not None)
        return f"{row[0]}.{row[1]} ({attrs})"

    items = sorted(one(row) for row in diff)
    shown = items[:limit]
    more = f"\n  ...另有 {len(items) - limit} 项" if len(items) > limit else ""
    return "\n  " + "\n  ".join(shown) + more


async def main() -> int:
    db_mig = os.environ.get("DB_MIGRATIONS")
    db_mod = os.environ.get("DB_MODELS")
    if not db_mig or not db_mod:
        print("缺少环境变量 DB_MIGRATIONS / DB_MODELS", file=sys.stderr)
        return 2
    for name in (db_mig, db_mod):
        if name.startswith("plan"):
            print(f"拒绝在疑似开发库上运行：{name!r}", file=sys.stderr)
            return 2

    try:
        from_migrations = await _schema_from_migrations(db_mig)
    except Exception as e:  # noqa: BLE001 —— 任何失败都原样报给调用方
        print(f"迁移应用失败：{type(e).__name__}: {e}", file=sys.stderr)
        return 3

    from_models = await _schema_from_models(db_mod)

    missing = from_models - from_migrations  # 模型有、迁移没建出来 → 漏生成迁移
    extra = from_migrations - from_models  # 迁移建了、模型已经没有 → 迁移过时

    if missing or extra:
        if missing:
            print("迁移未建出、但模型里存在（漏生成迁移）：" + _describe(missing), file=sys.stderr)
        if extra:
            print("迁移建出了、但模型里已不存在（迁移过时）：" + _describe(extra), file=sys.stderr)
        return 4

    print(f"一致：{len({t for t, *_ in from_models})} 张表 / {len(from_models)} 个列定义")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
