# 容器化部署与迁移体系收归版本控制 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让后端能在本机以容器方式跑起来（与开发者本机 MySQL 完全隔离），并把数据库 schema 的来源从「运行时的模型代码」收归到「版本控制里的迁移文件」。

**Architecture:** 分两条线。一条是迁移体系：squash 出一个干净基线替换掉现有残缺且**已损坏**的历史，迁移文件入 git，启动流程从「自动生成 + 应用」改为「只应用」，并用一项跑在真实 MySQL 上的测试守住一致性。另一条是容器配置：修正 `.dockerignore` 的失效规则、容器改用生产方式启动、凭据外置到 `.env`、把现有编排拆成本机版与 NAS 版两份。两条线在「容器首跑时 schema 从哪来」这一点上汇合。

**Tech Stack:** FastAPI · Tortoise ORM · aerich 0.8.1 · MySQL 8.1 · Docker / docker compose · nginx · pytest

**Spec:** `openspec/changes/containerize-backend/`（`proposal.md` / `design.md` / `specs/container-deployment/spec.md` / `specs/schema-migration/spec.md` / `tasks.md`）

## Global Constraints

- **中文注释、中文 commit message、中文文档**。
- 行宽 120；black（py310/py311）+ isort（profile=black）。
- 虚拟环境在 `.venv`，先 `source .venv/bin/activate`。
- **测试命令：`python -m pytest tests/ -q`**。不要用 `make test`——它依赖仓库里不存在的 `.env` 文件，必然失败。
- **不要跑 `black ./` 或 `isort ./`**：全仓有 11 个文件历史遗留不过 black，跑全仓会把 diff 撑爆。只对自己动过的文件跑检查。
- **全程不得启动 `python run.py`**。它开了 `reload=True`，而启动流程会碰数据库；本次改造前该组合已两次把开发库弄成半途状态。
- **开发者的工作数据库是 `plan`，任何步骤都不得改动它的数据**。允许改动的只有它的 `aerich` 记账表，且仅在 Task 2 中、按明确步骤进行。
- 所有一次性数据库必须以 `migcheck_` 或 `probe_` 前缀命名，**不得**用 `plan` 或 `plan_` 前缀（避免与工作库混淆），且必须在 `finally` 中 DROP。

## 已核实的现状（这些是实测结论，不是推测，实施时可直接依赖）

1. **现有的三个迁移文件是坏的。** 对一个全新库跑 `aerich upgrade`，会在第二个文件上失败：
   ```
   0_20260808014956_init.py            → 建出 15 张表 ✓
   5_20260826083209_add_user_openid.py → ✗ (1061, "Duplicate key name 'openid'")
   ```
   原因：该文件里 `ALTER TABLE user ADD openid VARCHAR(64) UNIQUE` 已经建了名为 `openid` 的唯一索引，紧接着的 `ADD UNIQUE INDEX openid` 又建一次。它在开发库上「生效」过，是因为当时第一条成功、第二条失败，而记账是人工补的——失败被掩盖了。
2. **`0_init` 只建 15 张表**，缺 `habit` / `goal` / `review` / `time_block` 与 pet 三张表。磁盘上缺失的 1~4 号文件无法恢复。
3. **`aerich migrate` 生成不了基线**：迁移目录不存在时它报 `You need to run 'aerich init-db' first to initialize the database.`。生成基线只能用 `aerich init-db`。
4. **`aerich init-db` 生成的基线是正确的**：22 条 `CREATE TABLE`、0 处反斜杠转义、关键表齐全；把它应用到另一个全新库 `aerich upgrade` 成功，之后 `aerich migrate` 报 `No changes detected`。
5. **`aerich init-db` 会污染默认库。** 即使 `DB_NAME` 环境变量指向临时库，它**同时**也会往 `plan` 库的 `aerich` 表插一行。已受控复现：执行前 8 行 → 执行后 9 行，而临时库里也有对应记录。**`aerich upgrade` 没有这个问题**（同样受控验证过，行数不变）。
6. `plan` 库当前状态：22 张表、`aerich` 7 行、`user` 1 行、`todo_item` 33 行；`aerich migrate` 与 `aerich upgrade` 均报无事可做。

---

## File Structure

**新建**

| 文件 | 职责 |
|---|---|
| `tests/_migration_check_worker.py` | 子进程 worker：在 `DB_NAME` 指定的库上应用迁移并比对模型快照。下划线开头，pytest 不收集 |
| `tests/test_migration_consistency.py` | 调起上面的 worker，管理一次性数据库的生命周期，断言迁移目录未被改写 |
| `.env.example` | 凭据占位模板，入 git |
| `docker-compose.yml` | 本机编排（app + mysql，mysql 用独立 named volume；app 不挂卷） |

**改名**

| 原 | 新 |
|---|---|
| `docker-compose.yml` | `docker-compose.nas.yml`（内容不变，保留 `/volume2/...` 绑定挂载） |

**修改**

| 文件 | 改动 |
|---|---|
| `app/core/init_app.py:339-354` | `init_db()` 只保留 `init()` + `upgrade()` |
| `app/core/init_app.py:1` | 移除不再使用的 `import shutil` |
| `app/__init__.py` | `lifespan` 中补微信凭据缺失告警 |
| `.dockerignore` | `venv` → `.venv`，补充排除项 |
| `.gitignore` | 移除 `migrations/`，确认忽略 `.env` |
| `deploy/entrypoint.sh` | `python run.py` → 直接起 uvicorn |
| `migrations/models/` | 删除三个旧文件，换成单一新基线；首次入 git |
| `CLAUDE.md` | 迁移新契约、两套编排的用途 |

**边界说明**：迁移一致性检查拆成 worker + 测试两个文件，是因为它们运行在不同进程里——worker 必须在干净的解释器中导入 `settings`，测试进程负责建库/清库/指纹比对。合成一个文件就没法保证隔离。

---

### Task 1: 重建迁移基线

**Files:**
- Delete: `migrations/models/0_20260808014956_init.py`、`migrations/models/5_20260826083209_add_user_openid.py`、`migrations/models/6_20260826233448_add_pet_tables_and_fix_comments.py`
- Create: `migrations/models/0_<新时间戳>_init.py`（由 `aerich init-db` 生成）

**Interfaces:**
- Produces: 单一基线迁移文件，文件名形如 `0_<14位时间戳>_init.py`。后续 Task 2 需要这个**确切文件名**填进 `aerich` 记账的 `version` 字段。

- [ ] **Step 1: 确认环境安全**

```bash
nc -z -G 2 localhost 9999 && echo "!!! dev server 在跑，停止后再继续" || echo "9999 无监听 ✓"
ps aux | grep -E "[r]un\.py|[u]vicorn" || echo "无 run.py 进程 ✓"
```

必须两条都通过才往下走。

- [ ] **Step 2: 记录改动前基线**

```bash
source .venv/bin/activate
python -m pytest tests/ -q 2>&1 | tail -2          # 记下通过数
aerich migrate 2>&1 | tail -1                       # 应为 No changes detected
```

把这两个数字记下来，Task 2 和 Task 9 要用它们对照。

- [ ] **Step 3: 备份**

```bash
cp -r migrations /tmp/mig_backup_$(date +%s)
```

`migrations/` 目前还没入 git，删错了就找不回来。记下备份路径。

同时导出 `plan` 库的 aerich 记账，Task 2 出问题时用于查证：

```bash
source .venv/bin/activate && python - <<'PY'
import asyncio, io, json
from tortoise import Tortoise
from app.settings.config import settings

async def m():
    await Tortoise.init(config=settings.TORTOISE_ORM)
    c = Tortoise.get_connection("mysql")
    rows = await c.execute_query_dict("SELECT id, app, version, content FROM aerich ORDER BY id")
    io.open("/tmp/aerich_backup.json", "w", encoding="utf-8").write(json.dumps(rows, ensure_ascii=False))
    print("已备份", len(rows), "行到 /tmp/aerich_backup.json")
    await Tortoise.close_connections()

asyncio.run(m())
PY
```

- [ ] **Step 4: 建一次性数据库用于生成基线**

```bash
source .venv/bin/activate && python - <<'PY'
import asyncio, asyncmy

DB = "probe_baseline_gen"

async def m():
    c = await asyncmy.connect(host="localhost", port=3306, user="root", password="chRDW=2021")
    async with c.cursor() as cur:
        await cur.execute(f"DROP DATABASE IF EXISTS `{DB}`")
        await cur.execute(f"CREATE DATABASE `{DB}` CHARACTER SET utf8mb4")
    c.close()
    print("已建", DB)

asyncio.run(m())
PY
```

- [ ] **Step 5: 删除旧迁移并生成新基线**

```bash
source .venv/bin/activate
rm -rf migrations
DB_NAME=probe_baseline_gen aerich init-db
ls migrations/models/
```

Expected: `Success generating initial migration file for app "models"`，目录下出现一个 `0_<时间戳>_init.py`。

> `aerich init-db` 要求迁移目录**不存在**，所以必须先 `rm -rf migrations`（Step 3 已备份）。
> 也不能用 `aerich migrate` 代替——迁移目录不存在时它会直接报错要求先 `init-db`。

- [ ] **Step 6: 检查生成的基线内容**

```bash
M=$(ls migrations/models/0_*_init.py)
echo "文件: $M"
echo -n "CREATE TABLE 条数（应为 22）: "; grep -c "CREATE TABLE" $M
echo -n "反斜杠转义残留（应为 0）: "; grep -c "\\\\'" $M || echo 0
grep -oE 'CREATE TABLE IF NOT EXISTS `[a-z_]+`' $M | sed 's/.*`\(.*\)`/  \1/' | sort
```

Expected: 22 条 CREATE TABLE；0 处 `\'`；表清单里 `habit` / `goal` / `review` / `time_block` / `pet_cat` / `pet_line` / `pet_profile` 都在。

任何一项不符就停下——反斜杠转义会在 MySQL 上产生语法错误（本次改造已因此让应用启动崩溃过一次）。

- [ ] **Step 7: 在另一个全新库上真实执行这个基线**

```bash
source .venv/bin/activate && python - <<'PY'
import asyncio, asyncmy

DB = "probe_baseline_apply"

async def m():
    c = await asyncmy.connect(host="localhost", port=3306, user="root", password="chRDW=2021")
    async with c.cursor() as cur:
        await cur.execute(f"DROP DATABASE IF EXISTS `{DB}`")
        await cur.execute(f"CREATE DATABASE `{DB}` CHARACTER SET utf8mb4")
    c.close()

asyncio.run(m())
PY
DB_NAME=probe_baseline_apply aerich upgrade
DB_NAME=probe_baseline_apply aerich migrate
```

Expected:
- `aerich upgrade` → `Success upgrading to 0_<时间戳>_init.py`
- `aerich migrate` → `No changes detected`

这两条一起证明：基线能在真实 MySQL 上跑通，且跑完之后模型没有待生成的变更。

- [ ] **Step 8: 清理一次性数据库**

```bash
source .venv/bin/activate && python - <<'PY'
import asyncio, asyncmy

async def m():
    c = await asyncmy.connect(host="localhost", port=3306, user="root", password="chRDW=2021")
    async with c.cursor() as cur:
        for db in ("probe_baseline_gen", "probe_baseline_apply"):
            await cur.execute(f"DROP DATABASE IF EXISTS `{db}`")
        await cur.execute("SHOW DATABASES LIKE 'probe_%'")
        left = [list(r)[0] for r in await cur.fetchall()]
    c.close()
    print("剩余 probe_* 库:", left or "无")

asyncio.run(m())
PY
```

- [ ] **Step 9: 确认 `plan` 库被 `init-db` 污染了几行**

```bash
source .venv/bin/activate && python - <<'PY'
import asyncio
from tortoise import Tortoise
from app.settings.config import settings

async def m():
    await Tortoise.init(config=settings.TORTOISE_ORM)
    c = Tortoise.get_connection("mysql")
    rows = await c.execute_query_dict("SELECT id, version FROM aerich ORDER BY id")
    print("plan 库的 aerich 记账（预计比 Step 3 备份多 1 行，来自 init-db 的污染）:")
    for r in rows:
        print("   ", r["id"], r["version"])
    await Tortoise.close_connections()

asyncio.run(m())
PY
```

**这是已知且预期的行为**（见「已核实的现状」第 5 条）：`aerich init-db` 即使 `DB_NAME` 指向别处，也会往 `plan` 的 `aerich` 表插一行。不用现在处理——Task 2 会清空整张表。这一步只是让你确认污染的规模符合预期（多 1 行），如果多了更多行，说明有别的东西也在写库，停下来查清楚。

- [ ] **Step 10: 提交（此时只提交迁移文件本身，入 git 在 Task 2）**

先不提交。基线文件和 `.gitignore` 的改动一起在 Task 2 提交，避免出现「文件在但仍被忽略」的中间状态。

---

### Task 2: 重置本机库记账并把迁移文件纳入 git

**Files:**
- Modify: `.gitignore`
- Add to git: `migrations/`

**Interfaces:**
- Consumes: Task 1 生成的基线文件名
- Produces: `plan` 库的 `aerich` 表只剩一行、指向新基线；`migrations/` 进入版本控制

- [ ] **Step 1: 执行前验证 schema 已经一致**

```bash
source .venv/bin/activate && aerich migrate 2>&1 | tail -1
```

Expected: `No changes detected`

这一条证明 `plan` 的 schema 已经与当前模型一致，**所以重置只需要改记账、不需要执行任何 DDL**。如果这里不是 "No changes detected"，停下——说明前提不成立，继续下去会让记账与实际 schema 错位。

- [ ] **Step 2: 重置记账**

```bash
source .venv/bin/activate && python - <<'PY'
import asyncio
import glob
import os
from tortoise import Tortoise
from app.settings.config import settings

async def m():
    baseline = os.path.basename(glob.glob("migrations/models/0_*_init.py")[0])
    print("将把记账重置为:", baseline)

    await Tortoise.init(config=settings.TORTOISE_ORM)
    from aerich.models import Aerich
    from aerich.utils import get_models_describe

    before = await Aerich.all().count()
    await Aerich.all().delete()
    await Aerich.create(version=baseline, app="models", content=get_models_describe("models"))
    after = await Aerich.all().values("id", "version")

    print(f"清空 {before} 行，写入 1 行")
    print("现在:", after)
    await Tortoise.close_connections()

asyncio.run(m())
PY
```

三个字段都必须正确，各自的作用：

- `version`：必须与 `migrations/models/` 下的实际文件名**逐字一致**。不一致的话 `upgrade()` 会把基线当成未应用的迁移重新执行，撞上「表已存在」。
- `app`：`"models"`，与 `pyproject.toml` 的 `[tool.aerich]` 一致。
- `content`：`get_models_describe("models")` 的返回值——完整的模型快照（当前约 82KB）。**这一项最容易漏**：`aerich migrate` 靠它做 diff，填空或填错会让下次 migrate 认为「所有模型都变了」，生成一个巨大的伪迁移。

- [ ] **Step 3: 执行后验证**

```bash
source .venv/bin/activate
aerich migrate 2>&1 | tail -1      # 期望 No changes detected —— 证明 content 填对了
aerich upgrade 2>&1 | tail -1      # 期望 No upgrade items found —— 证明 version 与文件名对得上
```

两条都符合才算成功。

- [ ] **Step 4: 验证数据未受影响**

```bash
source .venv/bin/activate && python - <<'PY'
import asyncio
from tortoise import Tortoise
from app.settings.config import settings

async def m():
    await Tortoise.init(config=settings.TORTOISE_ORM)
    c = Tortoise.get_connection("mysql")
    t = await c.execute_query_dict("SHOW TABLES")
    u = await c.execute_query_dict("SELECT COUNT(*) c FROM user")
    d = await c.execute_query_dict("SELECT COUNT(*) c FROM todo_item")
    p = await c.execute_query_dict("SELECT COUNT(*) c FROM pet_profile")
    print(f"表数:{len(t)} user:{u[0]['c']} todo_item:{d[0]['c']} pet_profile:{p[0]['c']}")
    print("期望: 22 / 1 / 33 / 1")
    await Tortoise.close_connections()

asyncio.run(m())
PY
```

- [ ] **Step 5: 让 `migrations/` 进入版本控制**

`.gitignore` 里删掉 `migrations/` 那一行（当前在第 8 行），并确认 `.env` 被忽略（没有就补上）：

```
.env
```

- [ ] **Step 6: 确认跟踪状态**

```bash
git add migrations/ .gitignore
git status --short migrations/ | head
git check-ignore -v migrations/models/*.py || echo "migrations 不再被忽略 ✓"
```

Expected: 基线文件出现在待提交列表里；`__pycache__` 不在（`.gitignore` 里已有 `__pycache__` 规则覆盖）。

- [ ] **Step 7: 全量测试**

```bash
source .venv/bin/activate && python -m pytest tests/ -q 2>&1 | tail -2
```

Expected: 与 Task 1 Step 2 记录的通过数一致（这一步没改代码，只改了迁移文件和 git 配置）。

- [ ] **Step 8: 提交**

```bash
git add migrations/ .gitignore
git commit -m "chore(db): 重建迁移基线并纳入版本控制

现有迁移历史既残缺（1~4 号文件已丢失，0_init 只建 15 张表）又损坏
（5_add_user_openid 里 ADD COLUMN ... UNIQUE 之后又 ADD UNIQUE INDEX，
对全新库执行会报 Duplicate key name 'openid'）。squash 成单一基线，
并把 migrations/ 从 .gitignore 移除，让 schema 可从版本控制重建。

本机库的 schema 已与模型一致，因此重置只重写 aerich 记账、不执行任何 DDL。"
```

---

### Task 3: 启动流程改为只应用不生成

**Files:**
- Modify: `app/core/init_app.py:339-354`（`init_db`）
- Modify: `app/core/init_app.py:1`（移除 `import shutil`）

**Interfaces:**
- Produces: `init_db()` 不再写文件、不再删目录，只应用已入库的迁移。Task 4 的一致性测试建立在这个前提上。

- [ ] **Step 1: 改写 `init_db()`**

把 `app/core/init_app.py` 第 339-354 行整个替换为：

```python
async def init_db():
    """应用版本库中的迁移。

    只应用（upgrade），不生成（migrate），也不删除迁移目录。原先这里会在取不到
    模型历史时 rmtree("migrations") 再从当前模型重建——那让 schema 的来源在
    「评审过的迁移文件」与「此刻的模型代码」之间摇摆，且因为往被监听的目录写文件，
    与 run.py 的 reload=True 叠加会形成重启循环（已两次把开发库弄成半途状态）。

    模型变更后由开发者显式执行 `make migrate` 生成迁移并随代码提交；
    模型与迁移是否一致，由 tests/test_migration_consistency.py 在提交前拦截。
    """
    command = Command(tortoise_config=settings.TORTOISE_ORM)
    await command.init()
    await command.upgrade(run_in_transaction=True)
```

- [ ] **Step 2: 移除不再使用的 import**

`app/core/init_app.py` 第 1 行的 `import shutil` 删掉——`rmtree` 是它在本文件里的唯一用途。

```bash
grep -n "shutil" app/core/init_app.py || echo "已无 shutil 引用 ✓"
```

- [ ] **Step 3: 确认应用仍能启动**

不要用 `python run.py`。用下面这段直接驱动 ASGI lifespan，跑完即退出、不留常驻进程：

```bash
source .venv/bin/activate && PYTHONPATH=. python - <<'PY'
import asyncio
from app import app

async def main():
    events = [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]
    sent = []

    async def receive():
        await asyncio.sleep(0)
        return events.pop(0)

    async def send(msg):
        sent.append(msg)

    await app({"type": "lifespan"}, receive, send)
    for m in sent:
        print("  ", m.get("type"), m.get("message", ""))
    assert all("failed" not in m["type"] for m in sent), "启动失败"
    print("启动流程通过 ✓")

asyncio.run(main())
PY
```

Expected: `lifespan.startup.complete` 与 `lifespan.shutdown.complete`，无 `failed`。

- [ ] **Step 4: 确认启动没有改写迁移目录**

```bash
ls -la migrations/models/
git status --short migrations/
```

Expected: 仍是那一个基线文件；`git status` 对 `migrations/` 无输出（没有新增/修改）。

改动前这里会多出一个自动生成的文件——那正是 reload 循环的成因。

- [ ] **Step 5: 全量测试**

```bash
source .venv/bin/activate && python -m pytest tests/ -q 2>&1 | tail -2
```

Expected: 与基线一致。

- [ ] **Step 6: 格式检查并提交**

```bash
source .venv/bin/activate
black --check app/core/init_app.py
isort --check app/core/init_app.py --profile black
git add app/core/init_app.py
git commit -m "refactor(db): 启动只应用迁移，不再自动生成或删除迁移目录

移除 command.migrate() 与 rmtree 兜底。兜底的本质是「取不到模型历史就按当前
模型重建」，它让 schema 的来源不确定；且因为往被 reload 监听的目录写文件，
与 dev server 叠加会形成重启循环。

模型与迁移的一致性改由测试在提交前拦截。"
```

---

### Task 4: 迁移一致性测试

**Files:**
- Create: `tests/_migration_check_worker.py`
- Create: `tests/test_migration_consistency.py`

**Interfaces:**
- Consumes: Task 2 的基线文件、Task 3 改造后的启动契约
- Produces: 一项测试，同时守住三件事——迁移 SQL 能在 MySQL 上执行、应用后模型无待生成变更、过程中迁移目录未被改写

**为什么必须用真实 MySQL**：迁移 SQL 是 MySQL 方言，而 `tests/conftest.py` 用的是内存 SQLite + `generate_schemas()`——**那条路径完全绕开迁移文件**。本次改造已因此漏过一个让应用启动崩溃的缺陷（模型 `description` 里的单引号被 aerich 转义成 `\'` 写进迁移文件，Python 求值后变成裸单引号，MySQL 语法错误），当时「MySQL 上验证过」的结论也是错的，因为验的是 `generate_schemas()` 而不是 `aerich upgrade`。

**为什么必须用子进程**：`settings` 是模块级单例，在进程内改它来切库已经失败过。而且 `aerich init-db` 会污染默认库（见「已核实的现状」第 5 条）——虽然本测试只用 `upgrade`（已验证不污染），子进程 + 环境变量仍是唯一可靠的隔离方式，且 worker 会自己校验隔离是否真的生效。

- [ ] **Step 1: 写 worker**

新建 `tests/_migration_check_worker.py`（下划线开头，pytest 不会收集它）：

```python
"""子进程 worker：在 DB_NAME 指定的库上应用版本库中的迁移，并比对模型快照。

用法：DB_NAME=<一次性库名> python tests/_migration_check_worker.py

为什么是子进程：settings 是模块级单例，在进程内修改它来切库曾经失败过并污染了
开发库。独立进程 + DB_NAME 环境变量是唯一可靠的隔离方式，本 worker 启动时还会
自校验隔离是否真的生效。

退出码：
  0 一致
  2 隔离校验失败（settings 指向的库不是期望的一次性库）
  3 迁移应用失败
  4 存在未生成迁移的模型变更
"""

import asyncio
import os
import sys


async def main() -> int:
    from aerich import Command
    from aerich.models import Aerich
    from aerich.utils import get_models_describe

    from app.settings.config import settings

    expected = os.environ.get("DB_NAME")
    actual = settings.TORTOISE_ORM["connections"]["mysql"]["credentials"]["database"]
    if not expected or actual != expected:
        print(f"隔离校验失败：settings 指向 {actual!r}，期望 {expected!r}", file=sys.stderr)
        return 2
    if actual == "plan" or actual.startswith("plan"):
        print(f"拒绝在疑似开发库上运行：{actual!r}", file=sys.stderr)
        return 2

    command = Command(tortoise_config=settings.TORTOISE_ORM)
    await command.init()

    try:
        await command.upgrade(run_in_transaction=True)
    except Exception as e:  # noqa: BLE001 —— 任何失败都要原样报给调用方
        print(f"迁移应用失败：{type(e).__name__}: {e}", file=sys.stderr)
        return 3

    # 比对模型快照而不是调 migrate()：migrate() 会往 migrations/ 写文件，
    # 而本检查的断言之一正是「过程中迁移目录未被改写」
    recorded = await Aerich.filter(app="models").order_by("-id").first()
    if recorded is None:
        print("迁移应用后 aerich 表里没有任何记录", file=sys.stderr)
        return 4

    current = get_models_describe("models")
    drifted = sorted(
        key for key in set(recorded.content) | set(current) if recorded.content.get(key) != current.get(key)
    )
    if drifted:
        print("以下模型有未生成迁移的变更：\n  " + "\n  ".join(drifted), file=sys.stderr)
        return 4

    print(f"一致：{len(current)} 个模型，迁移已应用到 {actual}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 2: 写测试**

新建 `tests/test_migration_consistency.py`：

```python
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

    db_name = f"migcheck_{uuid.uuid4().hex[:10]}"
    assert not db_name.startswith("plan"), "一次性库名不得与开发库混淆"

    before = _fingerprint(MIGRATIONS_DIR)

    _exec(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4")
    try:
        result = subprocess.run(
            [sys.executable, str(WORKER)],
            env={**os.environ, "DB_NAME": db_name},
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
        _exec(f"DROP DATABASE IF EXISTS `{db_name}`")

    assert _fingerprint(MIGRATIONS_DIR) == before, "迁移目录在检查过程中被改写"
```

- [ ] **Step 3: 跑这条测试，确认通过**

```bash
source .venv/bin/activate && python -m pytest tests/test_migration_consistency.py -v 2>&1 | tail -5
```

Expected: PASS。若 MySQL 不可达，应看到 skip 且原因清晰可读（不是静默通过）。

- [ ] **Step 4: 反向验证——确认这条测试真的有牙齿**

临时给某个模型加一个字段但**不生成迁移**：

```bash
source .venv/bin/activate && python - <<'PY'
import io
p = "app/models/pet.py"
s = io.open(p, encoding="utf-8").read()
anchor = '    visit_streak = fields.IntField(default=1, description="连续来访天数")'
assert anchor in s
io.open(p, "w", encoding="utf-8").write(
    s.replace(anchor, anchor + '\n    _drift_probe = fields.IntField(default=0, description="临时字段，用于验证一致性测试")')
)
print("已加入临时字段")
PY
python -m pytest tests/test_migration_consistency.py -q 2>&1 | tail -6
```

Expected: **FAIL**，且失败信息里能看到 `models.PetProfile`（或等价的模型名）出现在「有未生成迁移的变更」列表里。

如果这一步是 PASS，说明测试是空的，停下来修——一个抓不到漂移的一致性测试没有价值。

- [ ] **Step 5: 撤销临时字段，确认恢复通过**

```bash
source .venv/bin/activate && python - <<'PY'
import io
p = "app/models/pet.py"
s = io.open(p, encoding="utf-8").read()
line = '\n    _drift_probe = fields.IntField(default=0, description="临时字段，用于验证一致性测试")'
assert line in s
io.open(p, "w", encoding="utf-8").write(s.replace(line, ""))
print("已撤销临时字段")
PY
git diff --stat app/models/pet.py    # 应无输出
python -m pytest tests/test_migration_consistency.py -q 2>&1 | tail -3
```

Expected: `git diff` 无输出（文件恢复原样）；测试 PASS。

- [ ] **Step 6: 全量测试并确认无残留一次性数据库**

```bash
source .venv/bin/activate
python -m pytest tests/ -q 2>&1 | tail -2
python - <<'PY'
import asyncio, asyncmy

async def m():
    c = await asyncmy.connect(host="localhost", port=3306, user="root", password="chRDW=2021")
    async with c.cursor() as cur:
        await cur.execute("SHOW DATABASES LIKE 'migcheck_%'")
        left = [list(r)[0] for r in await cur.fetchall()]
    c.close()
    print("残留的一次性库:", left or "无 ✓")

asyncio.run(m())
PY
```

Expected: 测试数比基线多 1；无残留 `migcheck_*` 库。

- [ ] **Step 7: 格式检查并提交**

```bash
source .venv/bin/activate
black --check tests/_migration_check_worker.py tests/test_migration_consistency.py
isort --check tests/_migration_check_worker.py tests/test_migration_consistency.py --profile black
ruff check tests/_migration_check_worker.py tests/test_migration_consistency.py
git add tests/_migration_check_worker.py tests/test_migration_consistency.py
git commit -m "test(db): 新增迁移一致性检查，在真实 MySQL 上验证迁移路径

同时守住三件事：迁移 SQL 能在 MySQL 上执行、应用后模型无待生成变更、
过程中迁移目录未被改写。

其余测试用内存 SQLite + generate_schemas() 建表，绕开了迁移文件这条路径，
所以测试全绿也发现不了迁移本身的问题——本次改造已因此漏过一个会让应用
启动崩溃的缺陷。检查在独立子进程中运行、靠 DB_NAME 隔离，worker 会自校验
隔离是否生效并拒绝在疑似开发库上执行。"
```

---

### Task 5: 收敛镜像构建输入

**Files:**
- Modify: `.dockerignore`

**Interfaces:**
- Produces: 构建上下文只含运行所需内容；`migrations/` 明确保留在上下文里（Task 2 之后它是镜像必需品）

- [ ] **Step 1: 记录改动前的构建上下文体积**

```bash
du -sh . 2>/dev/null
du -sh .venv weapp docs openspec tests 2>/dev/null
```

改动前约 2.6GB。

- [ ] **Step 2: 改写 `.dockerignore`**

整个文件替换为：

```
# 依赖与虚拟环境（注意：Docker 的 ignore 不做前缀模糊匹配，
# 写 venv 匹配不到 .venv —— 原先正是这个规则失效，导致 128MB
# 本机虚拟环境（含 macOS 二进制）被打进镜像）
.venv
venv
web/node_modules

# 版本控制与编辑器
.git
.gitignore
.vscode
.claude

# Python 产物
__pycache__
*.pyc
*.pyo
*.pyd
.Python
.pytest_cache

# 本地数据库
db.sqlite3

# 后端镜像用不到的目录
weapp
docs
openspec
tests
.superpowers

# 凭据绝不进镜像
.env

# 注意：migrations/ 必须保留在构建上下文里。
# 启动流程只应用迁移、不再自动生成，镜像里没有迁移文件的话
# 容器会带着空 schema 正常启动，直到第一次查询才失败。
```

- [ ] **Step 3: 验证排除规则确实生效**

```bash
docker build -t ctx-probe --target web -f Dockerfile . 2>&1 | head -3
```

Expected: 第一行的 `transferring context` 体积远小于 2.6GB（预计几十 MB 量级）。

若 Docker 版本不支持 `--target web` 单独构建，改用：

```bash
tar --exclude-from=<(grep -v '^#' .dockerignore | grep -v '^$') -cf - . 2>/dev/null | wc -c | awk '{printf "上下文约 %.1f MB\n", $1/1024/1024}'
```

- [ ] **Step 4: 确认 `migrations/` 没被排除**

```bash
grep -n "migrations" .dockerignore
```

Expected: 只出现在注释里，没有作为排除规则。

- [ ] **Step 5: 提交**

```bash
git add .dockerignore
git commit -m "fix(docker): 修正 .dockerignore 失效规则并收敛构建上下文

原规则写的是 venv，实际目录是 .venv —— Docker 的 ignore 不做前缀模糊匹配，
该规则完全失效，128MB 本机虚拟环境（含 macOS 二进制，在 linux 容器里是死重）
被打进镜像，构建上下文达 2.6GB。

同时排除后端镜像用不到的 weapp/docs/openspec/tests，并明确注明
migrations/ 必须保留 —— 启动流程已改为只应用不生成，镜像里没有迁移文件
会让容器带着空 schema 启动。"
```

---

### Task 6: 容器以生产方式运行

**Files:**
- Modify: `deploy/entrypoint.sh`

**Interfaces:**
- Produces: 容器内不再有文件监听进程；`run.py` 保持不变，本机开发的热重载不受影响

- [ ] **Step 1: 改写 `deploy/entrypoint.sh`**

```sh
#!/bin/sh
set -e

# nginx 后台跑，uvicorn 前台阻塞 —— 保持与改动前一致的进程形态，不引入进程管理器
nginx

# 不用 python run.py：它写死了 reload=True，容器里开文件监听没有意义，
# 还会多一个 reloader 进程；叠加启动期的数据库初始化更是本项目已知的事故源。
exec uvicorn app:app --host 0.0.0.0 --port 9999
```

`exec` 让 uvicorn 接管 PID 1，容器的停止信号能直达应用。

- [ ] **Step 2: 确认 `run.py` 未被改动**

```bash
git diff --stat run.py
grep -n "reload" run.py
```

Expected: `git diff` 无输出；`run.py` 里 `reload=True` 仍在——那是本机开发入口，热重载必须保留。

- [ ] **Step 3: 确认 uvicorn 的入口路径正确**

```bash
source .venv/bin/activate && python -c "
import importlib
m = importlib.import_module('app')
assert hasattr(m, 'app'), 'app:app 这个入口不存在'
print('入口 app:app 可用 ✓')
"
```

- [ ] **Step 4: 提交**

```bash
git add deploy/entrypoint.sh
git commit -m "fix(docker): 容器改用生产方式启动 uvicorn

原先执行 python run.py，而 run.py 写死 reload=True —— 容器里开文件监听
没有意义，还多一个 reloader 进程。改为直接 exec uvicorn，让它接管 PID 1
以便停止信号直达应用。run.py 保持不变，本机开发的热重载不受影响。"
```

---

### Task 7: 凭据外置与缺失告警

**Files:**
- Create: `.env.example`
- Modify: `app/__init__.py`
- Modify: `.gitignore`（若 Task 2 未加 `.env` 则在此补）

**Interfaces:**
- Produces: `.env.example` 模板；启动时缺失微信凭据会记录告警但不阻止启动

- [ ] **Step 1: 写 `.env.example`**

```
# 复制为 .env 后填入真实值。.env 已被 .gitignore 忽略，不要提交。

# ---- 数据库（docker compose 会把这些注入 app 与 mysql 两个容器）----
DB_HOST=mysql
DB_PORT=3306
DB_USER=root
DB_PASSWORD=改成你的密码
DB_NAME=vue_fastapi_admin

# ---- 微信小程序凭据 ----
# 在微信公众平台 → 你的小程序 → 开发管理 → 开发设置 里获取。
# 后端用它们调 sns/jscode2session，把小程序 wx.login() 拿到的 code 换成 openid。
# AppSecret 必须只存在于服务端：小程序代码包可以被解出来，secret 一旦进客户端，
# 任何人都能冒充你的服务器解析别人的 code。
# 不填的话后端能正常启动，但微信登录会返回 40013 invalid appid。
WX_APPID=
WX_SECRET=
```

- [ ] **Step 2: 确认 `.env` 被 git 忽略**

```bash
grep -n "^\.env$" .gitignore || echo "需要补一行 .env"
echo "x" > .env && git check-ignore -v .env && rm .env
```

Expected: `git check-ignore` 命中 `.gitignore` 的 `.env` 规则。

- [ ] **Step 3: 在启动流程里加缺失告警**

`app/__init__.py` 的 `lifespan` 改为：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    _warn_missing_wechat_credentials()
    await init_data()
    yield
    await Tortoise.close_connections()
```

并在文件里补上这个函数（放在 `lifespan` 之前）：

```python
def _warn_missing_wechat_credentials() -> None:
    """微信凭据缺失时在启动阶段就告警。

    不阻止启动 —— 后端其余功能都不依赖它。但如果不在这里说一声，
    这个配置遗漏要等到第一个用户尝试微信登录、拿到 40013 才会暴露。
    """
    missing = [name for name in ("WX_APPID", "WX_SECRET") if not getattr(settings, name)]
    if missing:
        logger.warning(
            "微信小程序凭据缺失：%s。后端可正常启动，但 /api/v1/base/wx_login 会返回微信的 "
            "40013 invalid appid，小程序无法登录。在 .env 中配置后重启即可。",
            "、".join(missing),
        )
```

文件顶部补 import（放在现有 import 区）：

```python
from app.log import logger
```

- [ ] **Step 4: 验证告警出现**

```bash
source .venv/bin/activate && PYTHONPATH=. python - <<'PY' 2>&1 | grep -i "微信小程序凭据缺失" && echo "告警已出现 ✓" || echo "✗ 没看到告警"
import asyncio
from app import app

async def main():
    events = [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]

    async def receive():
        await asyncio.sleep(0)
        return events.pop(0)

    async def send(msg):
        pass

    await app({"type": "lifespan"}, receive, send)

asyncio.run(main())
PY
```

Expected: 看到告警（当前 `WX_APPID` / `WX_SECRET` 都是空）。

- [ ] **Step 5: 验证配上之后告警消失**

```bash
source .venv/bin/activate && WX_APPID=wxtest WX_SECRET=secrettest PYTHONPATH=. python - <<'PY' 2>&1 | grep -ci "微信小程序凭据缺失" | xargs -I{} sh -c 'test {} -eq 0 && echo "告警已消失 ✓" || echo "✗ 仍有告警"'
import asyncio
from app import app

async def main():
    events = [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]

    async def receive():
        await asyncio.sleep(0)
        return events.pop(0)

    async def send(msg):
        pass

    await app({"type": "lifespan"}, receive, send)

asyncio.run(main())
PY
```

- [ ] **Step 6: 全量测试、格式检查并提交**

```bash
source .venv/bin/activate
python -m pytest tests/ -q 2>&1 | tail -2
black --check app/__init__.py
isort --check app/__init__.py --profile black
git add .env.example app/__init__.py .gitignore
git commit -m "feat(config): 凭据外置到 .env，缺失微信凭据时启动告警

新增 .env.example 模板。启动时若 WX_APPID/WX_SECRET 为空则告警但不阻止启动 ——
后端其余功能不依赖它，但不说一声的话这个遗漏要等第一个用户登录拿到 40013
才会暴露。DB_PASSWORD 不需要同等待遇：配错会导致连不上库、启动直接失败。"
```

---

### Task 8: 拆分编排文件

**Files:**
- Rename: `docker-compose.yml` → `docker-compose.nas.yml`
- Create: `docker-compose.yml`
- Modify: `build-image.sh`（若引用了编排文件名）

**Interfaces:**
- Consumes: Task 7 的 `.env` 变量名
- Produces: 本机编排（app + mysql，独立 named volume，与宿主机 MySQL 完全隔离）

- [ ] **Step 1: 把现有编排改名保留**

```bash
git mv docker-compose.yml docker-compose.nas.yml
head -3 docker-compose.nas.yml
grep -n "volume2" docker-compose.nas.yml
```

内容一个字都不改——那些 `/volume2/docker/life_plan/` 绑定挂载是给群晖用的。

- [ ] **Step 2: 写本机编排**

新建 `docker-compose.yml`：

```yaml
# 本机开发/验证用。数据库跑在容器里、用独立的 named volume，
# 与开发者本机已有的 MySQL 完全隔离 —— 容器里怎么折腾都碰不到 plan 库的数据。
# 代价：容器里是一套空数据，admin/123456 由 init_superuser() 重新创建。
#
# NAS 部署用 docker-compose.nas.yml（那份保留了 /volume2/... 的绑定挂载）。
#
# 用法：cp .env.example .env 并填好，然后 docker compose up --build

services:
  app:
    build: .
    image: vue-fastapi-admin-app
    container_name: vue-fastapi-admin
    restart: unless-stopped
    ports:
      - "7777:80"
    depends_on:
      mysql:
        condition: service_healthy
    environment:
      - DB_HOST=mysql
      - DB_PORT=3306
      - DB_USER=root
      - DB_PASSWORD=${DB_PASSWORD}
      - DB_NAME=${DB_NAME}
      - WX_APPID=${WX_APPID}
      - WX_SECRET=${WX_SECRET}
    # 不挂数据卷：本应用只往 stdout 写日志（app/log/log.py 里的文件 sink 是注释掉的，
    # settings.LOGS_ROOT 全仓无人使用），日志交给容器运行时收集即可。
    # 原编排挂的 app_data:/opt/vue-fastapi-admin/data 同样没有任何代码写入，一并去掉。
    networks:
      - app-network

  mysql:
    image: mysql:8.1
    container_name: vue-fastapi-admin-mysql
    restart: unless-stopped
    ports:
      - "3380:3306"
    environment:
      - MYSQL_ROOT_PASSWORD=${DB_PASSWORD}
      - MYSQL_DATABASE=${DB_NAME}
    volumes:
      - mysql_data:/var/lib/mysql
    networks:
      - app-network
    command: >
      --default-authentication-plugin=mysql_native_password
      --character-set-server=utf8mb4
      --collation-server=utf8mb4_unicode_ci
      --log-error-suppression-list="MY-013360"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "root", "-p${DB_PASSWORD}"]
      interval: 10s
      timeout: 10s
      retries: 15
      start_period: 30s

networks:
  app-network:
    driver: bridge

volumes:
  mysql_data:
```

- [ ] **Step 3: 确认编排里没有指向宿主机数据库**

```bash
grep -nE "host\.docker\.internal|DB_HOST=(localhost|127)" docker-compose.yml && echo "✗ 指向了宿主机" || echo "未指向宿主机 ✓"
grep -n "DB_HOST" docker-compose.yml
```

Expected: `DB_HOST=mysql`，没有 `host.docker.internal`。

- [ ] **Step 4: 确认没有明文凭据**

```bash
grep -nE "password123|MYSQL_ROOT_PASSWORD=[^$]" docker-compose.yml && echo "✗ 有明文" || echo "无明文凭据 ✓"
```

- [ ] **Step 5: 确认没有声明无人写入的数据卷**

```bash
grep -n "volumes:" -A 4 docker-compose.yml
grep -rn "LOGS_ROOT" app/ | grep -v "config.py"   # 应无输出，证明没有代码用它
grep -n "add(sink" app/log/log.py                  # 应只有 sys.stdout 一个 sink
```

Expected: `app` 服务下没有 `volumes:`；`LOGS_ROOT` 除定义处外无人引用；日志只有 stdout 一个 sink。

这一步是防止把 `app_data` 那个错误换个挂载点再犯一遍——原来那个卷挂在 `/opt/vue-fastapi-admin/data`，没有任何代码往那儿写。

- [ ] **Step 6: 校验编排文件语法**

```bash
cp .env.example .env
sed -i '' 's/^DB_PASSWORD=.*/DB_PASSWORD=localdev123/' .env
docker compose config >/dev/null && echo "docker-compose.yml 语法通过 ✓"
docker compose -f docker-compose.nas.yml config >/dev/null && echo "docker-compose.nas.yml 语法通过 ✓"
```

- [ ] **Step 7: 检查 `build-image.sh`**

```bash
grep -n "docker-compose\|compose" build-image.sh || echo "build-image.sh 未引用编排文件，无需改动 ✓"
```

若有引用旧文件名，按用途改成对应的那一份。

- [ ] **Step 8: 提交**

```bash
git add docker-compose.yml docker-compose.nas.yml build-image.sh
git commit -m "feat(docker): 拆分本机与 NAS 两套编排

现有编排（含 /volume2/... 群晖绑定挂载）改名为 docker-compose.nas.yml 保留；
新建的 docker-compose.yml 面向本机，app + mysql 用独立 named volume，
与开发者本机已有的 MySQL 完全隔离 —— 不用 host.docker.internal，因为那意味着
让容器里的代码去 upgrade 开发者赖以工作的数据库。

同时去掉无效的 app_data 卷：它挂在 /opt/vue-fastapi-admin/data，没有任何代码
写那个路径；而本应用只往 stdout 写日志（文件 sink 是注释掉的，LOGS_ROOT 无人使用），
所以不需要任何日志卷，交给容器运行时收集即可。凭据改走 .env。"
```

---

### Task 9: 端到端验证与收尾

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`（若有容器相关说明）

**Interfaces:** 无新增

- [ ] **Step 1: 构建镜像**

```bash
docker compose build 2>&1 | tail -5
```

Expected: 构建成功。留意首行 `transferring context` 的体积——应远小于改动前的 2.6GB。

- [ ] **Step 2: 首次启动，观察是否有多余重启**

```bash
docker compose up -d
sleep 45
docker compose logs app | grep -c "Started server process" 
```

Expected: **1**。改动前因启动期写迁移文件会触发 reload，这里会是 2 或更多。

```bash
docker compose logs app | tail -20
```

Expected: 看到 `init_miniprogram_role` 的授权日志、`Application startup complete`，无 traceback。

- [ ] **Step 3: 确认容器内迁移目录未被改写**

```bash
docker compose exec app ls -la /opt/vue-fastapi-admin/migrations/models/
```

Expected: 只有一个基线文件，与镜像里烤进去的一致——没有容器启动时新生成的文件。

- [ ] **Step 4: 确认容器内 schema 完整**

```bash
docker compose exec mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "SHOW TABLES" "$MYSQL_DATABASE"' | sort | tr '\n' ' '
docker compose exec mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=\"$MYSQL_DATABASE\"" '
```

Expected: 22 张表；`habit` / `goal` / `review` / `time_block` / `pet_cat` / `pet_line` / `pet_profile` 都在。

- [ ] **Step 5: 接口可用**

```bash
TOKEN=$(curl -s -X POST http://localhost:7777/api/v1/base/access_token \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"123456"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
echo "token 长度: ${#TOKEN}"
curl -s http://localhost:7777/api/v1/todo/list -H "token: $TOKEN" | head -c 200; echo
```

Expected: 取到 token；`/todo/list` 返回 `{"code":200,...}`。

- [ ] **Step 6: 日志可通过容器运行时查看**

```bash
docker compose logs app --tail 30 | grep -E "Application startup complete|小程序用户角色" | head -3
```

Expected: 能看到启动日志。本应用只往 stdout 写日志（`app/log/log.py` 里的文件 sink 是注释掉的），所以日志由容器运行时收集，不需要挂任何卷——这也是编排里 `app` 服务没有 `volumes:` 的原因。

- [ ] **Step 7: 前端页面可访问**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:7777/
```

Expected: `200`。

- [ ] **Step 8: 可整体重置**

```bash
docker compose down -v
docker compose up -d
sleep 45
docker compose logs app | grep -c "Started server process"
docker compose exec mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=\"$MYSQL_DATABASE\""'
```

Expected: 仍是 1 次启动、22 张表——证明从空库重建的路径可重复。

- [ ] **Step 9: 确认宿主机 `plan` 库全程未被触碰**

```bash
source .venv/bin/activate && python - <<'PY'
import asyncio
from tortoise import Tortoise
from app.settings.config import settings

async def m():
    await Tortoise.init(config=settings.TORTOISE_ORM)
    c = Tortoise.get_connection("mysql")
    t = await c.execute_query_dict("SHOW TABLES")
    a = await c.execute_query_dict("SELECT COUNT(*) c FROM aerich")
    u = await c.execute_query_dict("SELECT COUNT(*) c FROM user")
    d = await c.execute_query_dict("SELECT COUNT(*) c FROM todo_item")
    print(f"表数:{len(t)} aerich:{a[0]['c']} user:{u[0]['c']} todo_item:{d[0]['c']}")
    print("期望: 22 / 1 / 1 / 33")
    await Tortoise.close_connections()

asyncio.run(m())
PY
```

`aerich` 应为 **1**（Task 2 重置后的单条基线记录），其余与 Task 1 Step 2 记录一致。

- [ ] **Step 10: 停掉容器**

```bash
docker compose down
```

不带 `-v`，保留数据卷。

- [ ] **Step 11: 更新 `CLAUDE.md`**

在后端章节里补上（放在「常用命令」之后）：

```markdown
### 数据库迁移

`migrations/` **已纳入版本控制**。schema 的唯一来源是这些被评审过的迁移文件，不是运行时的模型代码。

- 改了模型 → 必须跑 `make migrate` 生成迁移文件，并与模型变更**放进同一次提交**
- 应用启动只会**应用**迁移（`upgrade`），不会生成，也不会删除迁移目录
- 模型与迁移是否一致由 `tests/test_migration_consistency.py` 拦截。它是本仓库唯一需要真实 MySQL 的测试——其余测试用内存 SQLite + `generate_schemas()` 建表，那条路径绕开迁移文件，测试全绿也发现不了迁移本身的问题

### 容器部署

两套编排，用途不同：

| 文件 | 用途 |
|---|---|
| `docker-compose.yml` | 本机。app + mysql 跑在容器里，用独立 named volume，与本机已有的 MySQL 完全隔离（容器里是空数据） |
| `docker-compose.nas.yml` | 群晖 NAS。保留 `/volume2/docker/life_plan/` 的绑定挂载 |

跑之前先 `cp .env.example .env` 并填好，其中 `WX_APPID` / `WX_SECRET` 不填不影响启动，但微信登录会返回 40013。

容器里以 `uvicorn app:app` 生产方式运行（不开 reload）；`run.py` 是本机开发入口，热重载保留在那里。
```

- [ ] **Step 12: 检查 `README.md`**

```bash
grep -n "docker-compose\|docker compose" README.md | head
```

若有引用编排文件的地方，按新的两份文件更新说明。

- [ ] **Step 13: 最后一次全量测试与格式检查**

```bash
source .venv/bin/activate
python -m pytest tests/ -q 2>&1 | tail -2

# 本计划改动过的 Python 文件就这四个，显式列出比按提交数回溯可靠
FILES="app/core/init_app.py app/__init__.py tests/_migration_check_worker.py tests/test_migration_consistency.py"
black --check $FILES
isort --check $FILES --profile black
ruff check $FILES
```

Expected: 测试全绿；三项检查都通过。

**不要跑 `black ./`**——全仓有 11 个文件历史遗留不过 black，跑全仓会把 diff 撑爆。

- [ ] **Step 14: 提交**

```bash
git add CLAUDE.md README.md
git commit -m "docs: 补充迁移新契约与两套容器编排的说明"
```

---

## 验收清单

全部 Task 完成后逐条确认：

- [ ] `migrations/models/` 只有一个基线文件，且已被 git 跟踪
- [ ] `plan` 库的 `aerich` 表只有 1 行，指向该基线；`user`=1、`todo_item`=33、22 张表
- [ ] `aerich migrate` → `No changes detected`；`aerich upgrade` → `No upgrade items found`
- [ ] `app/core/init_app.py` 里没有 `shutil`、没有 `command.migrate()`
- [ ] `python -m pytest tests/ -q` 全绿，比改动前多 1 条（迁移一致性测试）
- [ ] 迁移一致性测试经过反向验证——加字段不生成迁移时它会 FAIL
- [ ] `.dockerignore` 里是 `.venv` 不是 `venv`；`migrations` 不在排除列表
- [ ] `deploy/entrypoint.sh` 用 `exec uvicorn`，`run.py` 未被改动
- [ ] `docker-compose.yml`（本机）与 `docker-compose.nas.yml`（NAS）都能通过 `docker compose config`
- [ ] 编排文件里没有明文密码，没有 `host.docker.internal`
- [ ] `.env.example` 已入 git，`.env` 被忽略
- [ ] `docker compose up` 首次启动只有 **1 次** `Started server process`
- [ ] 容器内 22 张表；`admin`/`123456` 能取 token 并调通受保护接口；前端页面 200
- [ ] `docker compose down -v` 后重新 up 仍能从空库重建
- [ ] 无残留的 `probe_*` / `migcheck_*` 数据库

## 不在本计划范围

以下几项在 spec 的 Non-Goals 里，明确不做：

- HTTPS、证书、域名备案（小程序正式版必需，与「服务能在容器里跑起来」正交）
- 多副本部署下的迁移竞态（当前单实例）
- 审计日志中间件对小程序热路径的放大（需产品判断排除哪些路径）
- `init_miniprogram_role` 的 `clear()` + `add()` 语义（会清掉管理员手工加授，需产品判断）
- 生产级镜像瘦身（非 root 用户、裁剪 apt 依赖等）
