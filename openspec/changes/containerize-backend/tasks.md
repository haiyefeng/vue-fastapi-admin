## 1. 前置准备

- [ ] 1.1 确认 dev server 已停止：`nc -z localhost 9999` 无监听、`ps aux | grep run.py` 无进程。本次改造中该进程与启动期自动迁移叠加已两次造成事故，全程保持停止
- [ ] 1.2 备份本机库的 aerich 记账：导出 `plan` 库 `aerich` 表全部行到文件，供回滚查证
- [ ] 1.3 备份现有 `migrations/` 目录到临时位置（该目录尚未入库，删错就没了）
- [ ] 1.4 记录改动前基线：`python -m pytest tests/ -q` 的通过数，以及 `aerich migrate` 的输出（应为 "No changes detected"）

## 2. 重建迁移基线

- [ ] 2.1 删除 `migrations/models/` 下现有的全部迁移文件（`0_init`、`5_add_user_openid`、`6_add_pet_tables`）
- [ ] 2.2 从当前模型生成新的完整基线迁移
- [ ] 2.3 核对新基线的 `upgrade()` 覆盖全部 18 张模型表 + m2m 中间表，特别确认 `habit` / `goal` / `review` / `time_block` / `pet_*` 都在
- [ ] 2.4 核对新基线中没有 `\'` 形式的转义残留（该形态会在 MySQL 上产生语法错误）
- [ ] 2.5 在一个临时数据库上真实执行新基线的 `upgrade()` SQL，确认 MySQL 接受且建表完整；用完 DROP 该库，全程不碰 `plan` 库

## 3. 重置本机库的迁移记账

- [ ] 3.1 执行前验证：`aerich migrate` 报 "No changes detected"（证明本机 schema 已与当前模型一致，重置只需改记账）
- [ ] 3.2 清空 `plan` 库的 `aerich` 表，写入一条指向新基线的记录，**不执行任何 DDL**。三个字段都必须填对：
      - `version` = 新基线的文件名（如 `0_<时间戳>_init.py`），必须与 `migrations/models/` 下的实际文件名逐字一致，否则 `upgrade()` 会把它当成未应用的迁移重新执行
      - `app` = `"models"`（与 `pyproject.toml` 的 `[tool.aerich]` 一致）
      - `content` = `aerich.utils.get_models_describe("models")` 的返回值。**这一项最容易漏**：它存的是完整的模型快照（当前库里这个字段约 85KB），`aerich migrate` 靠它做 diff。填空或填错会让下次 migrate 认为「所有模型都变了」，生成一个巨大的伪迁移
- [ ] 3.3 确认 `aerich` 表里没有指向不存在文件的记录。（调查阶段曾有一条幽灵记账 `0_20260827000244_init.py`，源于一次隔离失败的测试，**已于讨论阶段单独清除**；此处只做复查）
- [ ] 3.4 执行后验证：`aerich migrate` 仍报 "No changes detected"（证明记账已对齐新基线）
- [ ] 3.5 执行后验证：`aerich upgrade` 报 "No upgrade items found"（证明 version 字段与磁盘文件名对得上）
- [ ] 3.6 抽查 `plan` 库数据未受影响：`user` / `todo_item` / `pet_profile` 行数与 1.4 记录一致（改动前为 1 / 33 / 1）

## 4. 迁移文件入库

- [ ] 4.1 从 `.gitignore` 移除 `migrations/`
- [ ] 4.2 确认 `.gitignore` 忽略 `.env`（凭据不得入库）
- [ ] 4.3 `git add migrations/` 并确认新基线文件被跟踪、`__pycache__` 未被跟踪

## 5. 启动流程改为只应用不生成

- [ ] 5.1 修改 `app/core/init_app.py::init_db()`：移除 `command.migrate()` 与 `AttributeError` 分支里的 `shutil.rmtree("migrations")` + `init_db(safe=True)` 兜底，只保留 `command.init()` + `command.upgrade()`
- [ ] 5.2 清理因此不再使用的 `shutil` 导入（若无其他用途）
- [ ] 5.3 在 `init_db()` 的 docstring 写明新契约：启动只应用迁移，模型变更后需显式 `make migrate` 并提交迁移文件
- [ ] 5.4 全量测试通过，且不低于 1.4 记录的基线数（对 `init_db()` 行为的验证放在第 6 组）

## 6. 迁移一致性测试（覆盖 spec「迁移与模型的一致性由测试拦截」）

这一项测试同时守住三件事：迁移 SQL 能在 MySQL 上执行、应用后模型无待生成变更、启动流程不写迁移目录。它是本次改造里唯一需要真实 MySQL 的测试——因为迁移 SQL 是 MySQL 方言，`generate_schemas()` 那条路绕开了迁移文件，**测试全绿也发现不了迁移的问题**（本次改造已因此漏过一个会导致启动崩溃的缺陷）。

- [ ] 6.1 写测试：建一个一次性数据库（名字带随机后缀，避免与任何既有库重名），把版本库中的迁移文件应用上去
- [ ] 6.2 同一测试内断言：全部迁移语句执行成功（覆盖「迁移 SQL 能在 MySQL 上执行」）
- [ ] 6.3 同一测试内断言：应用后比对当前模型与迁移记录的模型快照，报告无变更（覆盖「应用迁移后模型无待生成变更」）。失败信息要能指出是哪些模型有未生成的迁移
- [ ] 6.4 同一测试内断言：整个过程结束后 `migrations/` 目录内容与开始时逐字节一致（覆盖「启动过程不产生文件写入」）
- [ ] 6.5 测试必须在 `finally` 中 DROP 那个一次性数据库，**且全程不得连接 `plan` 库**
- [ ] 6.6 隔离方式：测试 MUST 在独立子进程中运行、靠环境变量指定库名，**不得靠在进程内修改已导入的 settings 对象来切库**。调查阶段正是这么做的，结果隔离失败、往 `plan` 库写进了一条幽灵记账
- [ ] 6.7 MySQL 不可达时该测试跳过并给出明确原因，不得静默通过
- [ ] 6.8 反向验证一次：临时在某个模型上加一个字段（不生成迁移），确认该测试**失败**；然后撤销改动，确认恢复通过

## 7. 镜像构建输入收敛

- [ ] 7.1 修正 `.dockerignore`：`venv` → `.venv`（Docker 不做前缀模糊匹配，当前规则完全失效）
- [ ] 7.2 补充排除 `weapp/`、`docs/`、`openspec/`、`tests/`、`.superpowers/`、`.claude/`
- [ ] 7.3 确认 `migrations/` **不在** 排除列表中（它现在是镜像必需内容）
- [ ] 7.4 验证构建上下文体积显著下降（改动前为 2.6GB）

## 8. 容器以生产方式运行

- [ ] 8.1 修改 `deploy/entrypoint.sh`：`python run.py` 改为直接启动 uvicorn 监听 `0.0.0.0:9999`，不开 reload；保持 nginx 后台启动、应用前台阻塞的形态
- [ ] 8.2 确认 `run.py` 未被修改（本机开发的热重载必须保留）

## 9. 凭据外置

- [ ] 9.1 新建 `.env.example`：含 `DB_PASSWORD`、`WX_APPID`、`WX_SECRET` 等键，值为占位说明，不含任何真实凭据
- [ ] 9.2 编排文件改为从 `.env` 读取上述变量，移除明文写死的 `DB_PASSWORD=password123`
- [ ] 9.3 应用启动时若 `WX_APPID` / `WX_SECRET` 为空则记录告警（覆盖 spec「微信凭据可达容器」的可诊断要求），但不阻止启动。告警要说清楚后果：微信登录会返回 40013，而这个错误只在第一个用户尝试登录时才会出现
- [ ] 9.4 验证告警：不配这两个变量启动一次，确认日志里有该告警；配上任意非空值再启动一次，确认告警消失。（`DB_PASSWORD` 不需要同等待遇——配错会导致连不上库、启动直接失败，本身已经足够响）

## 10. 编排文件拆分

- [ ] 10.1 `git mv docker-compose.yml docker-compose.nas.yml`，内容保持原样（含 `/volume2/docker/life_plan/` 绑定挂载）
- [ ] 10.2 新建面向本机的 `docker-compose.yml`：app + mysql 两个服务，mysql 使用独立 named volume，`DB_HOST=mysql`，**不得**指向 `host.docker.internal` 或宿主机的 `plan` 库
- [ ] 10.3 移除无效的 `app_data` 卷（挂在 `/opt/vue-fastapi-admin/data`，无任何代码写入），**且不新增日志卷**——本应用只往 stdout 写日志（`app/log/log.py` 的文件 sink 是注释掉的，`LOGS_ROOT` 全仓无人使用），挂到 `app/logs` 会是同一个错误换个位置
- [ ] 10.4 保留 mysql 的 healthcheck 与 `depends_on: service_healthy`，确保 app 在数据库就绪后才启动
- [ ] 10.5 更新 `build-image.sh` 中若有引用旧编排文件名之处

## 11. 端到端验证

- [ ] 11.1 `docker compose build` 成功
- [ ] 11.2 `docker compose up` 首次启动成功，且**没有多余的重启**（改动前因启动期写迁移文件会触发一次 reload 重启）
- [ ] 11.3 进容器确认 `migrations/` 内容与镜像构建时一致、未被改写
- [ ] 11.4 检查容器内数据库 schema 完整：22 张表，`habit` / `goal` / `review` / `time_block` / `pet_*` 均在
- [ ] 11.5 用 `admin` / `123456` 调 `POST /api/v1/base/access_token` 取得 token，再用该 token 调一个受保护接口（如 `GET /api/v1/todo/list`）返回 200
- [ ] 11.6 浏览器访问映射端口，前端页面能打开
- [ ] 11.7 `docker compose down -v` 后重新 `up`，确认可从空库重建且流程一致
- [ ] 11.8 确认宿主机 `plan` 库全程未被触碰：表数、`user` 行数与 1.4 / 3.6 记录一致（22 张表、user=1）

## 12. 收尾

- [ ] 12.1 对改动过的文件跑 `black --check` / `isort --check --profile black`。**不要跑 `black ./`**：全仓有 11 个文件历史遗留不过 black，跑全仓会把 diff 撑爆
- [ ] 12.2 更新 `CLAUDE.md`：迁移文件已入库、启动不再自动生成迁移、两套编排文件的用途与区别
- [ ] 12.3 更新 `README.md` 中与容器启动相关的说明（若有）
- [ ] 12.4 清理临时备份（1.2、1.3 的产物），确认已不需要
