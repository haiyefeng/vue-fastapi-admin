# 部署文档

本项目有三种跑法，用途和取舍各不相同：

| | 用途 | 数据库 | 入口 |
|---|---|---|---|
| **开发环境** | 本机写代码，前后端分别热重载 | 本机 MySQL 的 `plan` 库 | `python run.py` + `pnpm dev` |
| **本机容器** | 验证「打包出来的东西真的能跑」 | 容器自带 MySQL，独立数据卷 | `docker compose up` |
| **NAS 容器** | 群晖上的实际部署 | 容器自带 MySQL（可选绑定挂载） | `docker-compose.nas.yml` |

三者互不干扰：本机容器里是一套空数据，碰不到你本机 MySQL 的 `plan` 库。

---

## 先说 `.env`，它是最容易踩的地方

仓库根目录的 `.env`（从 `.env.example` 复制而来，已被 gitignore）**同时服务两个消费者，而它们的需求不一样**。搞不清这点，本机测试和容器会轮流失败：

| 变量 | `make test` / 本机开发 | `docker compose` |
|---|---|---|
| `DB_HOST` | **读**，连本机 MySQL | 不读（编排里写死成 `mysql`） |
| `DB_PORT` | **读** | 不读（写死 `3306`） |
| `DB_USER` | **读** | 不读（写死 `root`） |
| `DB_PASSWORD` | **读**，用来认证本机 MySQL | **读**，用来初始化容器里 MySQL 的 root 口令 |
| `DB_NAME` | **读**，本机开发用哪个库 | **读**，容器里创建哪个库 |
| `WX_APPID` / `WX_SECRET` | 读 | 读 |

关键在于 `DB_HOST` / `DB_PORT` / `DB_USER` 这三行**编排根本不看**——`docker-compose.yml` 的 app 服务把它们写成了容器内的字面量。所以把 `DB_HOST` 填成 `mysql` 不会让容器更正确，只会让本机测试连不上库。

后两行 `DB_PASSWORD` / `DB_NAME` 是两边共用的，但含义不同：本机是「拿这个口令去认证已有的 MySQL」，容器是「用这个口令去创建一个新的 MySQL」。因为容器那套是全新初始化的，填什么它就是什么，所以**按本机的实际情况填就行**，两边都能满足：

```sh
DB_HOST=localhost          # 本机 MySQL 地址
DB_PORT=3306
DB_USER=root
DB_PASSWORD=<你本机 MySQL 的 root 口令>
DB_NAME=plan               # 本机的开发库；容器会另建一个同名的空库，互不影响

WX_APPID=<微信小程序 AppID>
WX_SECRET=<微信小程序 AppSecret>
```

> **微信凭据不填也能启动**，但小程序登录会返回 `40013 invalid appid`。`WX_SECRET` 必须只存在于服务端——小程序代码包可以被解出来，secret 一旦进客户端，任何人都能冒充你的服务器去解析别人的 code。

---

## 一、开发环境

### 依赖

- Python ≥ 3.11（`pyproject.toml` 里的 `requires-python`；推荐用 [uv](https://github.com/astral-sh/uv) 管依赖）
- Node + pnpm（`web/package.json` 没声明 `engines`；镜像里用的是 node 20，本机跟着它走最省事）
- 本机 MySQL 8（库名见上面的 `DB_NAME`）

### 后端

```sh
uv sync                          # 或：make install —— 会自动建 .venv 并按 uv.lock 装齐
source .venv/bin/activate
cp .env.example .env             # 然后按上一节填好

python run.py                    # 或：make run
```

起在 `:9999`，接口文档 <http://localhost:9999/docs>。

`run.py` 写死了 `reload=True`，改后端代码会自动重启——**这是本机开发专用的入口，容器里不走它**（原因见「为什么容器不用 run.py」）。

首次启动会自动跑一遍初始化：应用迁移 → 建超级管理员 `admin` / `123456` → 建默认菜单树 → 同步 API 表 → 建「管理员」「普通用户」两个角色并预分配权限。

### 前端

```sh
cd web
pnpm i
pnpm dev
```

起在 `:3100`（`web/.env` 里的 `VITE_PORT`）。开发模式下 `VITE_USE_PROXY=true`，`/api/v1` 的请求由 Vite 代理转给后端，所以前后端可以各跑各的、互不阻塞。

### 常用命令

```sh
make check          # check-format + lint，只检查不改
make format         # black . && isort . --profile black
make lint           # ruff check ./app
make test           # 加载 .env 后跑 pytest

make migrate        # 模型改了之后生成迁移文件
make upgrade        # 应用迁移
```

前端在 `web/` 下：`pnpm lint` / `pnpm lint:fix` / `pnpm prettier`。前端没有配测试运行器。

---

## 二、本机容器

用来验证「构建产物真的能跑」。它自带一套 MySQL，跑在独立的 named volume 里，**与你本机已有的 MySQL 完全隔离**——容器里怎么折腾都碰不到 `plan` 库的数据，代价是容器里是一套空数据，`admin` / `123456` 会被重新创建一遍。

```sh
cp .env.example .env             # 填好，尤其是 DB_PASSWORD / DB_NAME
docker compose up --build -d

docker compose logs -f app       # 看启动日志
docker compose ps                # 看健康状态
```

| | 地址 |
|---|---|
| 前端 + 接口 | <http://localhost:7777> |
| 容器里的 MySQL | `localhost:3380`（映射自容器 `3306`） |

容器内部是 nginx 监听 `:80` 提供前端静态文件，并把 `/api/v1` 反代给同容器里的 uvicorn `127.0.0.1:9999`。宿主只暴露 `7777 → 80` 一个口。

### 重置

```sh
docker compose down -v           # 连数据卷一起删，下次启动是全新的空库
```

`-v` 删的是 `vue-fastapi-admin_mysql_data` 这个 named volume。**你本机 MySQL 里的数据不受影响。**

### 为什么容器不用 `run.py`

`deploy/entrypoint.sh` 里是：

```sh
nginx                                              # 后台
exec uvicorn app:app --host 0.0.0.0 --port 9999    # 前台，成为 PID 1
```

不走 `python run.py`，因为它写死了 `reload=True`——容器里开文件监听没有意义，还会多一个 reloader 进程；叠加启动期的数据库初始化更是本项目已知的事故源（见下一节）。

`exec` 让 uvicorn 成为 PID 1，`docker compose stop` 的 SIGTERM 能直接送到它，优雅退出正常走完。

**已知局限**：nginx 是后台 daemon，如果它单独挂掉，uvicorn 还活着、容器状态仍是 `Up`，但宿主 `:7777` 已经全黑。app 服务配了一条 `curl -fsS http://localhost/` 的 healthcheck 让这种状态变得可见（`docker compose ps` 会显示 `unhealthy`），但**docker 不会因为 unhealthy 自动重启容器**，它只负责让你看得出来。

---

## 三、NAS（群晖）

NAS 上不构建镜像，而是在开发机上打包成 tar 传过去。

### 1. 开发机上构建

```sh
./build-image.sh v1.0.0
```

会构建 `vue-fastapi-admin:v1.0.0`，额外打上 `vue-fastapi-admin-app:latest`（`docker-compose.nas.yml` 引用的就是这个名字），然后一起存成 `vue-fastapi-admin-v1.0.0.tar`。两个 tag 指向同一个镜像，tar 里只存一份层。

### 2. NAS 上加载并启动

```sh
docker load -i vue-fastapi-admin-v1.0.0.tar
docker compose -f docker-compose.nas.yml up -d
```

### NAS 编排与本机编排的差别

- **`name: vue-fastapi-admin-nas`** —— 必须有。compose 的 project 名默认取目录名、与 `-f` 参数无关，不显式声明的话两套编排会共用 project / 网络 / 数据卷 / 容器名。那意味着在同一台机器上对本机编排跑一次 `docker compose down -v`，删掉的正是 NAS 编排声明的同名卷。
- **绑定挂载默认是关的** —— `/volume2/docker/life_plan/` 那两行在文件里是**注释状态**，默认走 named volume。要落到 NAS 的实际路径上，需要在部署前手动取消注释。
- **没有 `build:` 段** —— 镜像只能靠上面的 `docker load` 来。

### 已知例外（有意保留，不是遗漏）

`docker-compose.nas.yml` 有三点不满足本项目其他地方的规范，都是权衡后保留的：

1. **明文口令**（`DB_PASSWORD=password123` 等）。它自 `233479f` 就在 git 历史里，现在改也收不回；且如果 NAS 已经用这份编排部署过，MySQL 数据卷里落盘的 root 口令不会跟着环境变量变，改了只会让应用连不上库。真要处理必须轮换 NAS 上的口令，那是一次独立的运维操作。
2. **`app_data` 卷**没有任何代码往里写。从已部署系统的编排里摘卷有风险，保留。
3. **容器名与宿主端口**（`7777` / `3380`）与本机编排相同。在同一台机器上同时起两套会被 docker 直接拒绝——是响亮的失败，不会静默毁数据，所以接受。**但不要在同一台机器上同时起这两套。**

完整记录见 `openspec/changes/containerize-backend/specs/container-deployment/spec.md` 的「已记录例外」一节。

---

## 四、数据库迁移

这一节跨所有环境，也是本项目最容易出事的地方。

**`migrations/` 已纳入版本控制。schema 的唯一来源是这些被评审过的迁移文件，不是运行时的模型代码。**

- 改了模型 → 必须跑 `make migrate` 生成迁移文件，并与模型变更**放进同一次提交**
- 应用启动只会**应用**迁移（`upgrade`），不会生成，也不会删除迁移目录
- 模型与迁移是否一致由 `tests/test_migration_consistency.py` 拦截

### 为什么启动时不再自动生成迁移

原先 `init_db()` 在取不到模型历史时会 `rmtree("migrations")` 再从当前模型重建。那让 schema 的来源在「评审过的迁移文件」和「此刻的模型代码」之间摇摆；又因为它往 `run.py` 监听的目录里写文件，叠加 `reload=True` 会形成重启循环——已经两次把开发库弄成半途状态。现在这条路径被彻底移除了。

同理，`make clean-db` 里那行递归删 `migrations/` 的命令也已移除。确实要重建基线时请显式手工删除并走评审，不要藏在一个 make 目标背后。

### 一致性检查

`tests/test_migration_consistency.py` 是本仓库**唯一需要真实 MySQL** 的测试。它建两个临时库（`migcheck_mig_*` 走迁移文件、`migcheck_mod_*` 走 `generate_schemas()`），比对两边的 `information_schema`，用完即删。

其余测试用内存 SQLite + `generate_schemas()` 建表，**那条路径完全绕开迁移文件**——测试全绿也发现不了迁移本身的问题。这不是理论风险：aerich 会把 description 里的 `'` 转义成 `\'` 写进迁移 `.py`，而 Python 求值时又把反斜杠吃掉，于是 `COMMENT '...'` 的 SQL 被引号截断、MySQL 报 1064。只有这个测试拦得住。

---

## 五、排障

### `make test` 报 `DB_HOST 被显式配置为 ... 但连不上`

配置错了，不是「本机没有 MySQL」。看错误码：

- **`2003`（解析不了主机名）** —— `DB_HOST` 填成了 `mysql`。那个主机名只在 docker compose 的内部网络里解析得了，本机要填 `localhost`。
- **`1045`（认证失败）** —— 服务器通了但口令不对。常见成因是把容器那套口令抄进了 `.env`：编排是用 `DB_PASSWORD` 去**初始化**容器里的 root，与本机 MySQL 是两台服务器。

`DB_HOST` 完全不设置且本机没有 MySQL 时，这个测试会 skip 而不是 fail——那是正常的。

### `docker compose up` 报 `缺少 DB_PASSWORD` / `缺少 DB_NAME`

没有 `.env`，或者里面这两行是空的。`cp .env.example .env` 然后填。

### 微信登录返回 `40013 invalid appid`

`WX_APPID` / `WX_SECRET` 没配。后端启动时会打一条告警提示缺哪个。注意 `docker-compose.nas.yml` 直到最近才补上这两个变量的透传——compose 只把 `environment:` 里列出的变量传进容器，早期版本的 NAS 部署无论怎么配环境变量，容器里都是空值。

### 容器 `Up` 但 `:7777` 打不开

大概率是 nginx 挂了而 uvicorn 还活着。`docker compose ps` 看健康状态，`docker compose restart app` 恢复。

### 启动时报 `FileNotFoundError: 'migrations/models'`

镜像里没有迁移文件。`migrations/` 必须留在构建上下文里——启动流程只应用迁移、不再自动生成。检查 `.dockerignore` 有没有误排除它。

---

## 附：依赖怎么管

`pyproject.toml` + `uv.lock` 是唯一来源，没有第二份清单。

```sh
uv sync              # 开发环境：装全部，含 black / isort / ruff / pytest
uv sync --no-dev     # 镜像里装的：只装运行时依赖
uv add <包名>        # 加依赖，会同时更新 pyproject.toml 和 uv.lock
```

镜像走的是 `uv sync --frozen --no-dev`：`--frozen` 表示严格按 `uv.lock` 装、不重新解析，`uv.lock` 与 `pyproject.toml` 对不上时**直接报错**，而不是悄悄装出一套与开发环境不同的依赖。所以加依赖之后 `uv.lock` 必须跟着提交，否则镜像构建会失败——这是有意的，失败比漂移好。

`dependencies` 里只列**直接依赖**，传递依赖交给 `uv.lock` 锁定，不要手工摊平进去。有几个包代码里不 import 但必需，删之前先看清楚注释：

| 包 | 为什么必需 |
|---|---|
| `asyncmy` | MySQL 驱动，由 tortoise 按 engine 名动态加载，删了会在连库那一刻才失败 |
| `email-validator` | `app/schemas/users.py` 用了 pydantic 的 `EmailStr`，缺了导入 schema 就崩 |
| `argon2-cffi` | passlib 的 argon2 后端（`app/utils/password.py` 指定了 `schemes=["argon2"]`） |
| `httpx` | **不是测试依赖**——`app/utils/wechat.py` 用它调微信的 `sns/jscode2session` |

测试用的 sqlite 驱动 `aiosqlite` 没有单独声明，因为 `tortoise-orm` 本身就依赖它。
