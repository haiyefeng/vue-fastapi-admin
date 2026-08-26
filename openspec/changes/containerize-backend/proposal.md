## Why

小程序改造的阶段一（后端接口就位）已完成，下一步要让小程序真正连上后端，需要一个能自己跑起来、不依赖开发者本机环境的服务。仓库里虽然已有 `Dockerfile` / `docker-compose.yml`，但它们从未随本次改造更新，且存在几处会静默生效的缺陷。

更要紧的是：**这个项目的数据库 schema 目前无法从版本控制里重建**。`migrations/` 被 `.gitignore` 忽略，磁盘上只剩 3 个迁移文件（1~4 号已丢失），`0_init` 只能建出 15 张表，缺 `habit` / `goal` / `review` / `time_block`。现在之所以还能工作，全靠 `init_db()` 里一个「遇到空库就删掉迁移目录重新生成」的兜底分支。这个兜底在容器里同样生效，但它意味着 schema 的来源是「当时的模型代码」而非「被评审过的迁移文件」，且该分支已两次把本机开发库弄成半途状态。

## What Changes

### 容器配置修复

- **`.dockerignore` 的失效规则**：写的是 `venv`，实际目录是 `.venv`，Docker 不做前缀模糊匹配，导致 128MB 的本机虚拟环境（内含 macOS 二进制）被打进镜像，构建上下文达 2.6GB。修正并补充排除 `weapp/`、`docs/`、`openspec/`、`tests/` 等后端镜像用不到的目录。
- **容器里跑的是开发服务器**：`deploy/entrypoint.sh` 执行 `python run.py`，而 `run.py` 写死 `reload=True`。改为直接以生产方式启动 uvicorn，`run.py` 保持不变（它是本机开发入口）。
- **凭据裸奔**：`docker-compose.yml` 明文写死 `DB_PASSWORD`，且缺少本次新增的 `WX_APPID` / `WX_SECRET`（缺失时微信登录返回 40013）。改为从 `.env` 读取，并提供 `.env.example`。
- **无效的数据卷**：`app_data` 挂载在 `/opt/vue-fastapi-admin/data`，但没有任何代码写入该路径；真正的日志写在 `app/logs` 且未持久化，容器重建即丢失。

### 编排文件拆分

- 现有 `docker-compose.yml`（含 `/volume2/docker/life_plan/` 群晖绑定挂载）重命名为 `docker-compose.nas.yml` 保留备用。
- 新建面向本机的 `docker-compose.yml`：app + mysql 两个容器，使用独立的 named volume，**与开发者本机已有的 MySQL 完全隔离**。

### 迁移体系收归版本控制

- **BREAKING**：`migrations/` 纳入 git，从 `.gitignore` 移除。
- squash 出一个能建出完整 schema 的干净基线，替代当前残缺的历史。
- **BREAKING**：`init_db()` 不再自动生成迁移（移除 `command.migrate()` 与 `rmtree` 兜底），只应用已入库的迁移。模型变更后由开发者显式执行 `make migrate` 并提交迁移文件。
- 为已存在的开发库提供一次性的基线重置说明（schema 已一致，仅重写 aerich 记账）。

## Capabilities

### New Capabilities

- `container-deployment`: 后端服务的容器化交付——镜像构建的输入边界、运行时进程模型、配置与凭据的注入方式、本机与 NAS 两套编排的差异。
- `schema-migration`: 数据库 schema 变更的管理方式——迁移文件的产生、评审、分发与应用时机，以及应用启动时允许对 schema 做什么。

### Modified Capabilities

（无既有 spec）

## Impact

**配置与部署**
- `.dockerignore`、`Dockerfile`、`deploy/entrypoint.sh`
- `docker-compose.yml`（新建）、`docker-compose.nas.yml`（由现有文件重命名）
- 新增 `.env.example`；`.gitignore` 移除 `migrations/`、确保忽略 `.env`

**应用代码**
- `app/core/init_app.py::init_db()` —— 移除自动 migrate 与 rmtree 兜底

**迁移文件**
- `migrations/models/` 重建基线并首次纳入版本控制

**一次性人工操作**
- 开发者本机的 `plan` 库需要重置 aerich 记账以对齐新基线（schema 不变，仅改记账）

**不在本次范围**
- HTTPS / 证书 / 域名备案（小程序正式版所需，但与「服务能在容器里跑起来」正交）
- 审计日志中间件对小程序热路径的放大问题（需产品判断排除哪些路径）
- 多副本部署下的迁移竞态（当前为单实例）
