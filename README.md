<p align="center">
  <img alt="Logo" width="200" src="./deploy/sample-picture/logo.svg">
</p>

<h1 align="center">vue-fastapi-admin</h1>

[English](./README-en.md) | 简体中文

基于 FastAPI + Vue3 + Naive UI 的前后端分离平台，含 RBAC 权限管理、动态路由与 JWT 鉴权。

在此基础上扩展了个人效率管理相关的模块：四象限待办、习惯打卡、目标与复盘、时间块、以及配套的微信小程序端。

### 特性

- **技术栈**：后端 Python 3.11 + FastAPI + Tortoise ORM，前端 Vue3 + Vite + Naive UI，包管理用 pnpm
- **动态路由**：菜单由后端下发，结合 RBAC 权限模型控制到菜单级
- **细粒度权限**：按钮与接口级别的权限控制，前端 `v-permission` 指令与后端 `DependPermission` 一一对应
- **JWT 鉴权**：使用 JSON Web Token 进行身份验证与授权
- **迁移入库**：`migrations/` 纳入版本控制，schema 的唯一来源是评审过的迁移文件；模型与迁移是否一致由测试拦截

### 截图

| | |
|---|---|
| 登录页 | ![登录页](./deploy/sample-picture/login.jpg) |
| 工作台 | ![工作台](./deploy/sample-picture/workbench.jpg) |
| 用户管理 | ![用户管理](./deploy/sample-picture/user.jpg) |
| 角色管理 | ![角色管理](./deploy/sample-picture/role.jpg) |
| 菜单管理 | ![菜单管理](./deploy/sample-picture/menu.jpg) |
| API 管理 | ![API管理](./deploy/sample-picture/api.jpg) |

### 快速开始

> 数据库是 MySQL（`app/settings/config.py` 里只有 mysql 连接是活的），**没有可用的 SQLite 回退**。
> 所以 `docker run` 单起一个应用容器是跑不起来的——启动时 `init_db()` 连不上数据库会直接失败，
> 配上 `--restart=always` 还会被反复拉起。请用下面的 docker compose 方式，它会一并起一个独立的 MySQL 容器。
>
> 完整部署说明（开发环境 / 本机容器 / NAS 三种跑法、`.env` 各变量分别被谁消费、排障）见
> [`docs/deployment.md`](docs/deployment.md)。下面是最短路径。

```sh
git clone https://github.com/haiyefeng/vue-fastapi-admin.git
cd vue-fastapi-admin

# 填好数据库口令等配置；WX_APPID / WX_SECRET 不填不影响启动，只是微信登录会返回 40013
cp .env.example .env

docker compose up -d --build
```

访问 <http://localhost:7777>，默认账号 `admin` / `123456`。

```sh
docker compose logs -f app     # 看应用日志（日志走 stdout，不落盘）
docker compose ps              # 看健康状态
docker compose down            # 停止
docker compose down -v         # 停止并清空容器里的数据库数据
```

部署到 NAS 等外部环境时，在开发机上打包镜像再传过去：

```sh
./build-image.sh v1.0.0        # 构建并导出 vue-fastapi-admin-v1.0.0.tar
```

目标机器上 `docker load -i vue-fastapi-admin-v1.0.0.tar`，再用 `docker-compose.nas.yml` 启动。

### 本地开发

需要 Python 3.11+、Node、以及一个本机 MySQL 8。

#### 后端

依赖由 `pyproject.toml` + `uv.lock` 声明，用 [uv](https://github.com/astral-sh/uv) 安装：

```sh
pip install uv                 # 已安装可跳过
uv sync                        # 自动建 .venv 并按 uv.lock 精确还原依赖
source .venv/bin/activate      # Windows: .\.venv\Scripts\activate

cp .env.example .env           # 按本机 MySQL 的实际情况填
python run.py
```

接口文档在 <http://localhost:9999/docs>。

镜像里装的是 `uv sync --no-dev`，比开发环境少 black / isort / ruff / pytest 这几个工具。

#### 前端

```sh
cd web
npm i -g pnpm                  # 已安装可跳过
pnpm i
pnpm dev
```

起在 <http://localhost:3100>，开发模式下 `/api/v1` 由 Vite 代理转给后端。

#### 常用命令

```sh
make test           # 跑测试
make check          # 格式与 lint 检查（不修改）
make format         # 格式化
make migrate        # 模型改了之后生成迁移文件
make upgrade        # 应用迁移
```

### 目录说明

```
├── app                     // 后端
│   ├── api/v1              // 路由层（薄），按资源分目录：
│   │                       //   apis / auditlog / base / category / dashboard / depts
│   │                       //   goal / habit / menus / pet / project / review
│   │                       //   roles / subtask / timeblock / todos / users
│   ├── controllers         // 业务逻辑，继承 core/crud.py 的 CRUDBase
│   ├── core                // 中间件、鉴权依赖、通用 CRUD、启动初始化
│   ├── models              // Tortoise ORM 模型：admin.py / todo.py / pet.py
│   ├── schemas             // Pydantic 请求响应模型
│   ├── settings            // 配置
│   └── utils               // 工具（密码、JWT、微信接口等）
├── web                     // 前端（Vue3 + Vite）
│   └── src
│       ├── api             // 后端调用统一出口
│       ├── components      // 共享组件
│       ├── router          // 路由与守卫（动态路由由后端菜单派生）
│       ├── store           // Pinia：user / permission / app / tags
│       └── views           // 页面：login / workbench / system / todo / profile
├── weapp                   // 微信小程序端
├── migrations              // 数据库迁移（已纳入版本控制）
├── tests                   // 后端测试
├── deploy                  // Dockerfile 用的 nginx 配置、entrypoint、截图
└── docs                    // 部署与设计文档
```

### 致谢

本项目 fork 自 [mizhexiaoxiao/vue-fastapi-admin](https://github.com/mizhexiaoxiao/vue-fastapi-admin)，RBAC 与动态路由的基础框架来自该项目。
