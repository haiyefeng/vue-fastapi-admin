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
    "password": os.getenv("DB_PASSWORD", "chRDW=2021"),
}


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _connect():
    import asyncmy

    return await asyncmy.connect(**DB_CONFIG)


def _mysql_unavailable_reason() -> str | None:
    """MySQL 可达返回 None，否则返回不可达的原因（用于 skip 时说明）"""
    try:
        conn = _run(_connect())
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {e}"
    conn.close()
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
        pytest.skip(f"需要可达的 MySQL 才能验证迁移路径（本测试不能用 SQLite 代替）：{reason}")

    suffix = uuid.uuid4().hex[:10]
    db_mig = f"migcheck_mig_{suffix}"
    db_mod = f"migcheck_mod_{suffix}"
    for name in (db_mig, db_mod):
        assert not name.startswith("plan"), "一次性库名不得与开发库混淆"

    before = _fingerprint(MIGRATIONS_DIR)

    _exec(f"CREATE DATABASE `{db_mig}` CHARACTER SET utf8mb4")
    _exec(f"CREATE DATABASE `{db_mod}` CHARACTER SET utf8mb4")
    try:
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

    assert _fingerprint(MIGRATIONS_DIR) == before, "迁移目录在检查过程中被改写"
