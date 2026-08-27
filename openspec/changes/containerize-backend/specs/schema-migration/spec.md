## ADDED Requirements

### Requirement: 迁移文件纳入版本控制

`migrations/` 目录 MUST 纳入 git，与产生它的模型代码在同一个提交里分发。schema 的唯一来源 MUST 是被评审过的迁移文件，而不是运行时的模型代码。

#### Scenario: 干净 clone 能重建完整 schema

- **WHEN** 在一个不含任何本地遗留文件的干净 clone 上，对一个空数据库执行迁移
- **THEN** 建出的 schema MUST 与当前模型定义一致，包含 `user`、`todo_item`、`sub_task`、`time_block`、`habit`、`goal`、`review`、`categories`、`projects`、`pet_cat`、`pet_line`、`pet_profile` 等全部业务表

#### Scenario: 不同机器构建出的镜像行为一致

- **WHEN** 分别在开发者本机和一台没有本地迁移文件的机器上构建镜像
- **THEN** 两个镜像内的迁移文件 MUST 完全相同

### Requirement: 应用启动不得生成或删除迁移

应用启动流程 MUST 只应用已存在的迁移（`upgrade`），MUST NOT 生成新迁移（`migrate`），MUST NOT 删除 `migrations/` 目录。

#### Scenario: 模型与迁移不一致时启动

- **WHEN** 模型代码已变更但对应的迁移文件尚未生成，此时启动应用
- **THEN** 启动 MUST NOT 自行生成迁移文件
- **AND** 启动 MUST NOT 改写 schema 去迎合模型
- **AND** 启动本身 MAY 正常完成——该不一致由测试层拦截（见「迁移与模型的一致性由测试拦截」），而不是拖到启动时才发现

#### Scenario: 启动过程不产生文件写入

- **WHEN** 应用在开启文件监听（`reload=True`）的开发模式下启动
- **THEN** 启动流程 MUST NOT 向 `migrations/` 写入任何文件，以免触发监听器重启并形成循环

#### Scenario: 空数据库首次启动

- **WHEN** 对一个空数据库启动应用
- **THEN** 系统 MUST 应用版本库中的迁移文件建出完整 schema
- **AND** MUST NOT 退回到「从当前模型现场生成」的路径

### Requirement: 模型变更由开发者显式生成迁移

变更模型后，开发者 MUST 显式执行迁移生成命令，并将产生的迁移文件与模型变更一同提交。

#### Scenario: 开发者变更模型

- **WHEN** 开发者修改了模型定义
- **THEN** 开发者 MUST 运行 `make migrate` 生成迁移文件
- **AND** MUST 将该文件纳入同一次提交

#### Scenario: 迁移文件缺失在提交前被发现

- **WHEN** 提交中包含模型变更但缺少对应的迁移文件
- **THEN** 测试套件 MUST 失败，且失败信息 MUST 指出存在未生成迁移的模型变更

### Requirement: 迁移与模型的一致性由测试拦截

MUST 存在一项自动化检查，它把版本库中的迁移文件应用到一个全新的目标数据库（MySQL），并验证由此得到的 schema 与当前模型定义一致。仅通过 `generate_schemas()` 建表的测试 MUST NOT 被视为对迁移路径的验证——它绕过了迁移文件这条路径。

该检查 MUST 在一次性数据库上进行，MUST NOT 触碰开发者的工作数据库，且结束后 MUST 清理。

#### Scenario: 迁移 SQL 能在 MySQL 上执行

- **WHEN** 把版本库中的迁移文件应用到一个全新的 MySQL 数据库
- **THEN** 全部语句 MUST 执行成功

#### Scenario: 模型字段描述含 SQL 敏感字符

- **WHEN** 模型字段的 `description` 中包含单引号
- **THEN** 该情况 MUST 被自动化检查拦截，因为生成的迁移会在 MySQL 上产生语法错误

#### Scenario: 应用迁移后模型无待生成变更

> 判据必须是两个真实数据库的 schema 对比，不能用 aerich 的记账。
> `aerich.Command._upgrade` 写进 `Aerich.content` 的是**应用迁移那一刻**从当前模型现算的
> `get_models_describe(self.app)`，不是迁移生成时冻结的快照——拿它去跟 `get_models_describe()`
> 比是同义反复，无论模型是否漂移都恒等（已实测：加字段不生成迁移，这种比法仍然通过）。
> 下面这条 Scenario 描述的就是唯一非重言的做法，不要把它「简化」回记账比对。

- **WHEN** 把版本库中的迁移文件应用到一个全新数据库（库 A），再用 `generate_schemas()` 从当前模型建出另一个全新数据库（库 B）
- **THEN** 比对两个库 `information_schema` 里的真实列结构 MUST 完全相同
- **AND** 比对的维度 MUST 至少覆盖表名、列名、数据类型、可空性、字符长度、数值精度与标度、默认值、键类型——只比数据类型不够，`VARCHAR(30)` 与 `VARCHAR(300)` 的 `data_type` 同为 `varchar`，改 `max_length` 不生成迁移会漏过去
- **AND** 若有差异，检查 MUST 失败并指出是「模型有、迁移没建出来」还是「迁移建了、模型已没有」

#### Scenario: 本机缺少 MySQL 与 MySQL 配置错误必须区分

> 这项检查是「模型/迁移一致」的唯一闸门，仓库里没有 CI 作为第二道。
> 一个把两种情形都 skip 掉的实现，等于让这道闸门在配错的开发机上静默失效。

- **WHEN** 环境里没有显式配置 `DB_HOST`，且本机没有可达的 MySQL
- **THEN** 该检查 MAY 跳过，并说明跳过原因
- **WHEN** 环境里显式配置了 `DB_HOST` 但连不上
- **THEN** 该检查 MUST 失败（而不是跳过），失败信息 MUST 指出这是配置错误

### Requirement: 既有数据库的基线重置

对于已存在且 schema 已与新基线一致的数据库，MUST 提供一次性的记账重置方式，使其对齐新基线而不重建数据。

#### Scenario: 开发者本机既有库

- **WHEN** 一个既有数据库的 schema 已与新基线一致，但其迁移记账指向旧的历史
- **THEN** MUST 能只重写记账、不执行任何 DDL、不丢失数据
- **AND** 重置后再次生成迁移 MUST 报告「无变更」
