## ADDED Requirements

### Requirement: 镜像只包含运行所需内容

镜像构建的输入 MUST 排除运行时用不到的内容，包括开发者本机的虚拟环境、前端依赖目录、小程序源码、文档与规格目录、测试代码。

#### Scenario: 排除规则与实际目录名匹配

- **WHEN** 构建上下文中存在名为 `.venv` 的本机虚拟环境
- **THEN** 该目录 MUST 被排除，不得进入构建上下文或镜像

#### Scenario: 后端镜像不含无关源码

- **WHEN** 构建后端镜像
- **THEN** `weapp/`、`docs/`、`openspec/`、`tests/` MUST NOT 出现在镜像中

### Requirement: 容器以生产方式运行服务

容器 MUST NOT 以带文件监听（`reload`）的开发服务器方式运行应用。本机开发入口 `run.py` MUST 保持原样不受影响。

#### Scenario: 容器内进程模型

- **WHEN** 容器启动
- **THEN** 应用 MUST 以不开启 reload 的方式监听 `0.0.0.0:9999`
- **AND** MUST NOT 存在文件监听器进程

#### Scenario: 本机开发不受影响

- **WHEN** 开发者在本机执行 `python run.py`
- **THEN** 热重载 MUST 仍然可用

### Requirement: 凭据通过环境注入而非写死在编排文件

数据库密码、微信小程序凭据等敏感配置 MUST 通过环境变量注入，MUST NOT 明文写在纳入版本控制的编排文件里。版本库 MUST 提供一份不含真实值的示例文件。

> 适用范围：本要求由 `docker-compose.yml` 满足。`docker-compose.nas.yml` 的明文口令是**已记录的例外**，见下文「`docker-compose.nas.yml` 的已记录例外」。

#### Scenario: 编排文件不含真实凭据

- **WHEN** 检查纳入版本控制的编排文件
- **THEN** 其中 MUST NOT 出现真实的数据库密码或微信 AppSecret

#### Scenario: 微信凭据可达容器

- **WHEN** 在环境中配置了 `WX_APPID` 与 `WX_SECRET` 并启动容器
- **THEN** 容器内的应用 MUST 能读到这两个值
- **AND** 未配置时 MUST 以可诊断的方式提示，而不是只在调用登录接口时返回微信的 40013

### Requirement: 本机编排与 NAS 编排相互独立

项目 MUST 提供两套独立的编排文件：面向本机的默认编排，以及面向群晖 NAS 的编排。两者 MUST NOT 互相干扰。

> 适用范围：compose 的 project 名默认取目录名、与 `-f` 参数无关，因此两套编排 MUST 各自显式声明 `name:`，否则会共用 project / 网络 / 数据卷。容器名与宿主端口仍然相同，属**已记录的例外**，见下文。

#### Scenario: 本机编排自带数据库且与本机既有实例隔离

- **WHEN** 使用默认编排启动
- **THEN** MUST 启动独立的 MySQL 容器并使用独立的数据卷
- **AND** MUST NOT 连接或修改开发者本机已有的 MySQL 实例及其数据

#### Scenario: 本机编排可整体重置

- **WHEN** 执行 `docker compose down -v`
- **THEN** 容器内的数据 MUST 被清除
- **AND** 开发者本机 MySQL 中的数据 MUST 不受影响

#### Scenario: NAS 编排保留其绑定挂载

- **WHEN** 查看 NAS 编排文件
- **THEN** 其中面向 NAS 宿主路径的挂载配置 MUST 被保留

### Requirement: 日志输出到标准输出，交由容器运行时收集

应用 MUST 把日志写到标准输出，由容器运行时收集，MUST NOT 依赖挂载数据卷来保存日志文件。编排文件 MUST NOT 声明没有任何代码写入的数据卷。

> 适用范围：本要求由 `docker-compose.yml` 满足。`docker-compose.nas.yml` 保留的 `app_data` 卷是**已记录的例外**，见下文。

> 背景：本应用当前只有 stdout 一个 sink（`app/log/log.py` 里的文件 sink 是注释掉的），`settings.LOGS_ROOT` 定义了但全仓无人使用。原编排挂在 `/opt/vue-fastapi-admin/data` 的 `app_data` 卷同样没有任何代码写入。把日志当作事件流输出到 stdout 本就是容器的标准做法；若将来确需落盘日志，那是一项独立的功能改动（启用文件 sink + 挂卷），不属于本次范围。

#### Scenario: 日志可通过容器运行时查看

- **WHEN** 容器运行期间产生日志
- **THEN** `docker compose logs` MUST 能看到应用的启动日志与请求日志

#### Scenario: 编排文件不含无效数据卷

- **WHEN** 检查编排文件里声明的每个数据卷
- **THEN** 每个卷的挂载点 MUST 确实有代码向其写入

### Requirement: `docker-compose.nas.yml` 的已记录例外

上面三条要求（凭据通过环境注入、编排文件不得声明无效数据卷、两套编排互不干扰）
由 `docker-compose.yml` 完整满足。`docker-compose.nas.yml` 按用户明确要求**保留原样**，
以下三点是**已知且已被接受的例外**，不是遗漏。未记录的例外比例外本身更危险，故在此逐条落账。

#### Scenario: 例外一——NAS 编排里的明文口令保留

- **WHEN** 检查 `docker-compose.nas.yml`
- **THEN** 其中 `DB_PASSWORD=password123`、`MYSQL_ROOT_PASSWORD=password123`、`MYSQL_PASSWORD=app_password`、healthcheck 里的 `-ppassword123` MUST 保持原样
- **AND** 理由：这些值已核实**不是**活跃凭据（既非开发者 `.env` 的当前值、也非 `config.py` 里的默认值），且自 `233479f` 起就在 git 历史里——现在改掉，历史里那份也收不回，真要处理必须重写历史或轮换 NAS 上的口令，两者都超出本次范围
- **AND** 更要紧的是：若 NAS 已用该文件部署过，MySQL 数据卷里**已落盘**的 root 口令不会跟着环境变量变，改了只会让应用连不上库
- **AND** 若将来要轮换，MUST 同时处理「改编排 + 改 MySQL 卷里的口令 + 处理 git 历史」，MUST NOT 只改编排文件

#### Scenario: 例外二——NAS 编排保留 `app_data` 卷

- **WHEN** 检查 `docker-compose.nas.yml` 声明的数据卷
- **THEN** `app_data:/opt/vue-fastapi-admin/data` MUST 保持原样，尽管当前没有任何代码向该挂载点写入
- **AND** 理由：从一套**已部署**的编排里摘掉数据卷属于需要用户确认的动作，不在本次范围内。本机编排（`docker-compose.yml`）已按要求删掉该卷

#### Scenario: 例外三——两套编排的容器名与宿主端口仍然相同

- **WHEN** 在同一台机器上同时启动两套编排
- **THEN** `container_name`（`vue-fastapi-admin` / `vue-fastapi-admin-mysql`）与宿主端口（7777、3380）MUST 视为仍然冲突
- **AND** 已修复的部分：`docker-compose.nas.yml` 增加了 `name: vue-fastapi-admin-nas`，两套编排不再共用 compose project、网络与数据卷——**破坏性**的那一半（本机 `docker compose down -v` 删掉 NAS 编排声明的同名卷）已经消除
- **AND** 剩余冲突是**响亮**失败（容器名被占用 / 端口被占用），不会静默毁数据；文档中 MUST 写明不要在同一台机器上同时起这两套

#### Scenario: 微信凭据可达 NAS 容器（本轮已修，不属于例外）

- **WHEN** 在 NAS 上配置 `WX_APPID` / `WX_SECRET` 并用 `docker-compose.nas.yml` 启动
- **THEN** 容器内 MUST 能读到这两个值
- **AND** 说明：这一条原先在 NAS 路径上不成立（`environment:` 里根本没列这两个变量，compose 只传列出的变量，于是容器内恒为空、微信登录必然 40013）。它是功能缺陷而非安全权衡，已在本轮补上 passthrough，不作为例外

### Requirement: 容器化服务可端到端验证

容器启动后 MUST 能被验证为真正可用，而不仅是进程未退出。

#### Scenario: 首次启动完成初始化

- **WHEN** 对空数据库首次启动整套编排
- **THEN** 启动 MUST 成功完成，且 MUST NOT 产生多余的重启
- **AND** 数据库中 MUST 建出完整 schema

#### Scenario: 服务存活可被容器运行时观察

- **WHEN** 应用容器正在运行
- **THEN** 编排 MUST 为 app 服务声明 healthcheck，走 nginx → uvicorn 的完整链路
- **AND** 理由：容器里 nginx 是后台 daemon、uvicorn 是 PID 1；nginx 单独挂掉时进程没退出、容器状态仍是 `Up`，但映射端口已经全黑——「进程未退出」不等于「服务可用」
- **AND** 注意 docker 不会因 `unhealthy` 自动重启容器，该 healthcheck 提供的是可观察性，不是自愈

#### Scenario: 接口可访问

- **WHEN** 容器启动完成后访问后端接口
- **THEN** MUST 能以预置管理员账号取得 token 并调用受保护接口
- **AND** 前端静态页面 MUST 可通过映射端口访问
