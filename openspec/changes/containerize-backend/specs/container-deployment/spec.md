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

#### Scenario: 编排文件不含真实凭据

- **WHEN** 检查纳入版本控制的编排文件
- **THEN** 其中 MUST NOT 出现真实的数据库密码或微信 AppSecret

#### Scenario: 微信凭据可达容器

- **WHEN** 在环境中配置了 `WX_APPID` 与 `WX_SECRET` 并启动容器
- **THEN** 容器内的应用 MUST 能读到这两个值
- **AND** 未配置时 MUST 以可诊断的方式提示，而不是只在调用登录接口时返回微信的 40013

### Requirement: 本机编排与 NAS 编排相互独立

项目 MUST 提供两套独立的编排文件：面向本机的默认编排，以及面向群晖 NAS 的编排。两者 MUST NOT 互相干扰。

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

> 背景：本应用当前只有 stdout 一个 sink（`app/log/log.py` 里的文件 sink 是注释掉的），`settings.LOGS_ROOT` 定义了但全仓无人使用。原编排挂在 `/opt/vue-fastapi-admin/data` 的 `app_data` 卷同样没有任何代码写入。把日志当作事件流输出到 stdout 本就是容器的标准做法；若将来确需落盘日志，那是一项独立的功能改动（启用文件 sink + 挂卷），不属于本次范围。

#### Scenario: 日志可通过容器运行时查看

- **WHEN** 容器运行期间产生日志
- **THEN** `docker compose logs` MUST 能看到应用的启动日志与请求日志

#### Scenario: 编排文件不含无效数据卷

- **WHEN** 检查编排文件里声明的每个数据卷
- **THEN** 每个卷的挂载点 MUST 确实有代码向其写入

### Requirement: 容器化服务可端到端验证

容器启动后 MUST 能被验证为真正可用，而不仅是进程未退出。

#### Scenario: 首次启动完成初始化

- **WHEN** 对空数据库首次启动整套编排
- **THEN** 启动 MUST 成功完成，且 MUST NOT 产生多余的重启
- **AND** 数据库中 MUST 建出完整 schema

#### Scenario: 接口可访问

- **WHEN** 容器启动完成后访问后端接口
- **THEN** MUST 能以预置管理员账号取得 token 并调用受保护接口
- **AND** 前端静态页面 MUST 可通过映射端口访问
