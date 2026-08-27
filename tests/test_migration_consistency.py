"""验证版本库里的迁移文件能在真实 MySQL 上建出与模型一致的 schema。

这是本仓库唯一需要外部服务的测试。理由：其余测试用内存 SQLite + generate_schemas()
建表，那条路径绕开迁移文件，因此测试全绿也发现不了迁移本身的问题。
"""

import asyncio
import hashlib
import os
import pathlib
import subprocess
import sys
import uuid

import pytest

MIGRATIONS_DIR = pathlib.Path("migrations")
WORKER = pathlib.Path("tests/_migration_check_worker.py")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
}


def _run(coro):
    """每次用一个全新的事件循环跑一段协程，跑完就关掉（不关会一次测试泄好几个 loop）。

    注意：连接的 close() 必须发生在协程内部、loop 还活着的时候——loop 关掉之后再 close，
    asyncmy 的 transport 会抛 RuntimeError: Event loop is closed。
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(asyncio.sleep(0))  # 让 transport 的清理回调跑完
        loop.close()


async def _connect():
    import asyncmy

    return await asyncmy.connect(**DB_CONFIG)


def _mysql_unavailable_reason() -> str | None:
    """MySQL 可达返回 None，否则返回不可达的原因（用于 skip / fail 时说明）"""

    async def go():
        conn = await _connect()
        conn.close()

    try:
        _run(go())
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {e}"
    return None


def _exec(sql: str) -> None:
    async def go():
        conn = await _connect()
        try:
            async with conn.cursor() as cur:
                await cur.execute(sql)
        finally:
            conn.close()

    _run(go())


def _fingerprint(directory: pathlib.Path) -> str:
    """目录下所有 .py 文件的路径与内容指纹，用于检测是否被改写"""
    h = hashlib.sha256()
    for path in sorted(directory.rglob("*.py")):
        h.update(str(path).encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def test_committed_migrations_build_schema_matching_models():
    reason = _mysql_unavailable_reason()
    if reason is not None:
        # 「本机根本没配 MySQL」与「显式配了却连不上」是两回事，只有前者该 skip。
        # 后者往往是 .env 填错（例如把容器内的 DB_HOST=mysql 抄到了本机），
        # 若也 skip，这道唯一的迁移一致性闸门就会在开发者机器上静默失效。
        configured = os.getenv("DB_HOST")
        if configured:
            pytest.fail(
                f"DB_HOST 被显式配置为 {configured!r}，但连不上——这是配置错误，不是「本机没有 MySQL」。\n"
                f"本机开发请把 .env 里的 DB_HOST 填成本机地址（见 .env.example）；"
                f"`mysql` 这个主机名只在 docker compose 的内部网络里解析得了。\n"
                f"原始错误：{reason}"
            )
        pytest.skip(f"需要可达的 MySQL 才能验证迁移路径（本测试不能用 SQLite 代替）：{reason}")

    suffix = uuid.uuid4().hex[:10]
    db_mig = f"migcheck_mig_{suffix}"
    db_mod = f"migcheck_mod_{suffix}"
    for name in (db_mig, db_mod):
        assert not name.startswith("plan"), "一次性库名不得与开发库混淆"

    before = _fingerprint(MIGRATIONS_DIR)

    try:
        # 两条 CREATE 都在 try 之内：若第二条失败（重名/权限/连接抖动），
        # finally 仍会把第一条建出来的库删掉，不会在服务器上留残骸。
        _exec(f"CREATE DATABASE `{db_mig}` CHARACTER SET utf8mb4")
        _exec(f"CREATE DATABASE `{db_mod}` CHARACTER SET utf8mb4")
        result = subprocess.run(
            [sys.executable, str(WORKER)],
            env={**os.environ, "DB_MIGRATIONS": db_mig, "DB_MODELS": db_mod},
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, (
            f"worker 退出码 {result.returncode}\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
    finally:
        for name in (db_mig, db_mod):
            _exec(f"DROP DATABASE IF EXISTS `{name}`")

    # 意图声明，不是闸门：worker 只调 Command.init() + Command.upgrade()，两者都不写
    # migrations/（会写的是 migrate() / init_db()，worker 一个都不碰），所以在当前实现下
    # 这条断言结构上不可能失败。留着是为了让「检查过程不得改写版本控制里的迁移文件」这条
    # 约束在代码里有个落点——真正有牙的闸门是 worker 的 exit 3（迁移 SQL 跑不通）
    # 与 exit 4（两个库的 schema 不一致）。
    assert _fingerprint(MIGRATIONS_DIR) == before, "迁移目录在检查过程中被改写"
