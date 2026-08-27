# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指导。

## 项目概览

vue-fastapi-admin 是一个前后端分离的 RBAC 管理平台：后端为 FastAPI + Tortoise ORM（`app/`），前端为 Vue3 + Naive UI（`web/`），通过根路径为 `/api/v1` 的 REST API 通信。前后端开发和运行相互独立。

## 后端（`app/`）

### 常用命令

在仓库根目录执行（推荐使用 `uv` 管理依赖）：

```sh
uv sync                                # 安装依赖（或：make install）——自动建 .venv 并按 uv.lock 还原
source .venv/bin/activate
python run.py                          # 启动开发服务器，:9999，http://localhost:9999/docs
make run                               # 同上

make check          # check-format + lint（只检查，不修改）
make check-format    # black --check && isort --check（profile=black）
make format          # black . && isort . --profile black
make lint            # ruff check ./app

make test            # 加载 .env 后执行：pytest -vv -s --cache-clear ./（.env 里的 DB_* 要指向**本机** MySQL）
pytest path/to/test_file.py::test_name -vv   # 运行单个测试

make migrate          # aerich migrate（根据模型变更生成迁移文件）
make upgrade           # aerich upgrade（应用迁移）
make clean-db         # 删除本地 sqlite 数据库文件（不动 migrations/——迁移已入库）
```

格式化/lint 配置见 `pyproject.toml`：行宽 120，black 目标版本 py310/py311，ruff 忽略 `F403`/`F405`（因为 schema 模块中大量使用 `from x import *`）。

### 数据库迁移

`migrations/` **已纳入版本控制**。schema 的唯一来源是这些被评审过的迁移文件，不是运行时的模型代码。

- 改了模型 → 必须跑 `make migrate` 生成迁移文件，并与模型变更**放进同一次提交**
- 应用启动只会**应用**迁移（`upgrade`），不会生成，也不会删除迁移目录
- **不要用任何脚本批量删除 `migrations/`**。`make clean-db` 只删本地 sqlite 文件，已不再碰迁移目录
- 模型与迁移是否一致由 `tests/test_migration_consistency.py` 拦截。它是本仓库唯一需要真实 MySQL 的测试——其余测试用内存 SQLite + `generate_schemas()` 建表，那条路径绕开迁移文件，测试全绿也发现不了迁移本身的问题

### 容器部署

两套编排，用途不同：

| 文件 | 用途 |
|---|---|
| `docker-compose.yml` | 本机。app + mysql 跑在容器里，用独立 named volume，与本机已有的 MySQL 完全隔离（容器里是空数据） |
| `docker-compose.nas.yml` | 群晖 NAS。默认同样是 named volume，文件里保留着 `/volume2/docker/life_plan/` 绑定挂载的注释行，部署前需手动取消注释启用 |

两套编排的 compose project 名是分开的（本机 `vue-fastapi-admin`，NAS `vue-fastapi-admin-nas`），
所以网络 / 卷不会互相覆盖；但两边的 `container_name` 与宿主端口（7777 / 3380）仍然相同，
不要在同一台机器上同时起这两套。

开发环境 / 本机容器 / NAS 三种跑法的完整步骤、`.env` 各变量分别被谁消费、以及排障，
见 `docs/deployment.md`。

NAS 侧不在本地构建镜像：`./build-image.sh <版本号>` 会构建并同时打上 `vue-fastapi-admin:<版本号>`
与 `vue-fastapi-admin-app:latest`（后者正是 `docker-compose.nas.yml` 引用的名字），
导出成 tar；传到 NAS 后 `docker load -i <tar>`，再 `docker compose -f docker-compose.nas.yml up -d`。

跑之前先 `cp .env.example .env` 并填好，其中 `WX_APPID` / `WX_SECRET` 不填不影响启动，但微信登录会返回 40013。

容器里以 `uvicorn app:app` 生产方式运行（不开 reload）；`run.py` 是本机开发入口，热重载保留在那里。

### 架构

请求流程：`app/api/v1/<resource>/<resource>.py`（FastAPI 路由，薄层）→ `app/controllers/<resource>.py`（业务逻辑，继承 `CRUDBase`）→ `app/models/admin.py`（Tortoise ORM 模型）。

- **`app/__init__.py`** — `create_app()` 负责组装中间件、异常处理器和路由，并在启动时运行 `init_data()`（见下文）。
- **`app/api/v1/__init__.py`** — 将各资源路由挂载到 `/api/v1/<resource>` 下。除 `base` 外的所有路由都注册了 `dependencies=[DependPermission]`，即默认对每个路由都做鉴权+RBAC 校验；只有明确要公开的接口才应放在这个机制之外。
- **`app/core/crud.py`** — 通用的 `CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]`，提供 `get`/`list`/`create`/`update`/`remove`。各 controller 继承它并添加特定业务方法（如 `UserController.authenticate`、`update_roles`）。
- **`app/core/dependency.py`** — `AuthControl.is_authed` 从 `token` 请求头解码 JWT（或接受字面量字符串 `"dev"`，以第一个用户身份认证，仅用于本地开发），并设置 `CTX_USER_ID`。`PermissionControl.has_permission`（暴露为 `DependPermission`）会根据当前用户的角色关联的 API，校验请求的 `(method, path)` 是否在权限范围内；超级管理员跳过该检查。
- **待办事项（`app/api/v1/todos`）** — 四象限待办事项模块，与其余资源路由一样挂载在 `dependencies=[DependPermission]` 之下，但路由处理函数内部直接用 `Depends(AuthControl.is_authed)` 取当前用户，不依赖 RBAC 细分权限，且所有查询都以 `user_id` 过滤，天然按用户隔离数据。核心模型 `TodoItem`（`app/models/todo.py`）按 `QuadrantType` 枚举（紧急/重要的四种组合）分类，`app/controllers/todo.py::TodoController` 提供按象限、完成状态、日期范围筛选，以及按日期/象限的完成数统计（供 `GET /todo/statistics/daily`、`GET /todo/statistics/quadrant` 使用）。前端对应 `web/src/views/todo/TodoQuadrant`（四象限看板）与 `web/src/views/todo/TodoHistory`（历史统计），同样由 `Menu` 记录驱动路由，无需手改静态路由文件。`app/models/todo.py` 中还定义了 `Category`、`Project` 模型，但目前没有对应的 schema/controller/路由，是尚未接入的预留结构。
- **RBAC 数据模型**（`app/models/admin.py`）：`User` ↔ `Role`（多对多）↔ `Api`/`Menu`（多对多）。权限校验以 `Api` 表中存储的 `(http_method, path)` 元组为键，而不是按角色/权限名称。
- **动态 API 注册表** — `app/controllers/api.py::ApiController.refresh_api()` 在运行时反射 `app.routes`，将 `Api` 表与所有带 `dependencies`（即所有受保护路由）的路由同步，删除过时条目、创建新条目。这使得"API 管理"后台页面和权限校验表始终与代码中的实际路由保持一致。首次启动时通过 `init_apis()` 自动运行一次；也可以从前端手动触发（"刷新 API" 按钮 → `POST /api/v1/api/refresh`）。
- **`app/core/init_app.py`** — 通过 `init_data()` 运行的启动流程：`init_db`（只应用 `migrations/` 里已有的迁移，不生成新文件）→ `init_superuser`（若无用户则创建 admin/123456）→ `init_menus`（初始化默认菜单树）→ `init_apis`（见上文）→ `init_roles`（初始化"管理员"/"普通用户"角色并预分配 API/菜单权限）。
- **`app/core/middlewares.py`** — `HttpAuditLogMiddleware` 会将匹配指定方法（默认 GET/POST/PUT/DELETE，排除 `exclude_paths`）的每个请求记录到 `AuditLog` 模型，包含请求参数和大小受限的响应体。`BackGroundTaskMiddleware` + `app/core/bgtask.py` 提供响应后的后台任务队列（`BgTasks`）。
- **`app/schemas/`** — 各资源对应的 Pydantic 请求/响应模型，在路由模块中以 `from app.schemas.<x> import *` 方式导入（因此需要 ruff 的 `F403`/`F405` 豁免）。
- **Menu 与 Dept 的区别** — `Menu` 驱动前端的动态侧边栏/路由（`menu_type`、`component`、`path`、`parent_id`）；`Dept` 是独立的组织架构层级（配合 `DeptClosure` 做祖先/后代查询），与路由无关。
- **数据库是 MySQL，不是 SQLite。** `app/settings/config.py` 里唯一活着的连接是 `mysql`（凭据从 `DB_HOST`/`DB_PORT`/`DB_USER`/`DB_PASSWORD`/`DB_NAME` 环境变量读，见 `.env.example`），`apps.models.default_connection` 也写死 `"mysql"`；SQLite / PostgreSQL / MSSQL 的配置块都是注释掉的。不配 MySQL 应用起不来。仓库根目录可能残留的 `db.sqlite3` 是历史产物，当前代码不使用。

## 前端（`web/`）

### 常用命令

在 `web/` 目录下执行：

```sh
pnpm i              # 安装依赖（推荐 pnpm；npm 也可以）
pnpm dev            # 启动 Vite 开发服务器（端口见 .env，默认 3100）
pnpm build          # 生产环境构建
pnpm preview        # 预览生产构建

pnpm lint           # eslint --ext .js,.vue .
pnpm lint:fix       # eslint --fix
pnpm prettier       # npx prettier --write .
```

前端未配置测试运行器。

环境文件：`.env`（基础配置）、`.env.development`、`.env.production` 控制 `VITE_BASE_API`（默认 `/api/v1`）、`VITE_PORT`、代理及压缩相关配置——具体消费这些变量的 Vite 插件/代理配置见 `web/build/`。

### 架构

- **由后端驱动的动态路由** — 登录后，`web/src/router/index.js::addDynamicRoutes()` 调用 `permissionStore.generateRoutes()`，该方法从 `GET /base/usermenu` 获取当前用户的菜单树并转换为 Vue Router 路由，叠加在 `basicRoutes`（`web/src/router/routes/index.js`）之上。若没有有效 token，则只注册 `EMPTY_ROUTE`，并由路由守卫（`web/src/router/guard/`）重定向到登录页。
- **API 级别的权限控制** — `permissionStore.getAccessApis()` 从 `GET /base/userapi` 获取当前用户可访问的 `(method, path)` 列表并存储。`v-permission="'get/api/v1/user/list'"` 指令（`web/src/directives/permission.js`）会在当前用户（超级管理员除外）没有对应 API 权限时将元素从 DOM 中移除——这是按角色隐藏按钮/操作的方式，与后端的 `DependPermission` 检查相呼应。
- **HTTP 层** — `web/src/utils/http/index.js` 创建了一个 axios 实例（`request`），并在 `interceptors.js` 中配置拦截器，用于附加 `token` 请求头及处理鉴权错误/token 刷新。所有后端调用都统一走 `web/src/api/index.js` 这一个模块（扁平的具名方法对象），而不是在组件中散落 `axios` 调用。
- **状态管理** — Pinia store 位于 `web/src/store/modules/`：`user`（鉴权/个人信息）、`permission`（动态路由 + API 访问列表）、`app`（UI/主题状态）、`tags`（标签页历史）。
- **目录结构** 遵循 `views/`（路由级页面，与后端资源一一对应：system/user、system/role、system/menu、system/api、system/dept、system/auditlog；此外还有 `todo/TodoQuadrant`、`todo/TodoHistory` 对应待办事项模块）、`components/`（共享 UI）、`composables/` 等，与 `README.md` 中记录的目录树一致。

## 跨端注意事项

- 新增受保护的后端路由时无需手动注册权限——只要设置了 `dependencies`，`refresh_api()` 下次运行（应用启动，或通过后台"刷新 API"操作）时就会自动识别。新路由生成对应的 `Api` 记录后，还需由管理员将其分配给某个角色才能真正被使用。
- 新增由 `Menu` 记录驱动的后台页面时，前端路由完全由菜单管理页面中维护的菜单数据派生而来——除 `basicRoutes` 外，不存在需要手动编辑的静态路由文件来控制角色可见页面。
- 默认预置超级管理员账号为 `admin` / `123456`（`init_superuser()` 及 Docker 快速启动方式均如此）——`reset_password` 重置密码后也使用同样的凭据。
