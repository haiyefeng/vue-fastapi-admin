# 一期：任务体系升级落地设计

## 背景

`docs/superpowers/specs/2026-08-04-productivity-app-blueprint-design.md` 是"个人效率应用"总体蓝图，划分了四期路线。一期是任务体系升级：激活 `Category`/`Project`、新增 `SubTask`、给 `TodoItem` 加 `project_id`/`reminder_at`，落地任务列表页 + 收件箱 + 任务详情弹窗。

UI 已经在 `public/design/tasks.html` 定稿（含内嵌的 `task-detail-modal`），本设计**不重新设计界面**，只产出"怎么落地"：数据模型、API 端点、交互细节、边缘情况——性质上对应 `2026-08-04-schedule-week-design.md` 之于二期的角色。

## 范围

- 覆盖蓝图"一期：任务体系升级"整节列出的内容：Category/Project 激活、SubTask、TodoItem 增量字段、收件箱、任务列表页、任务详情弹窗、Menu 记录。
- 不做：Category 独立管理页/CRUD 入口（只能通过创建项目时顺带产生）、子任务拖拽重排、任务列表"按项目跨项目聚合"视图（导航栏只能二选一：收件箱或某个具体项目）、mockup 里属于三期的"关联计划"字段。
- 后端先行，前端随后，沿用 `todo-development-steps.md` 验证过的顺序。

## 数据模型变更

### Category / Project（激活已有模型）

模型已定义在 `app/models/todo.py`，本期补齐 `app/controllers/category.py`、`app/controllers/project.py`、对应 schema、路由。

- `Project` 创建/更新入参同时接受 `category_id`（选已有分类）或 `category_name`（新名称）：controller 内按 `(user_id, category_name)` get-or-create，新建的分类一律 `type=user_custom`。本期不预置系统分类，`unique_together(user, name)` 不会撞上 `user=NULL` 的系统预设记录。
- `Project` 删除：`ProjectController.delete` 里显式把关联 `TodoItem.project_id` 批量置空后再删除项目本身，不依赖 Tortoise FK 的默认级联行为（`Project` 模型上的外键未声明 `on_delete`，需要检查/显式改成不级联，避免默认行为把任务一起删掉）。
- 归档（`is_archived`）：归档后的项目在导航栏单独成一栏，默认折叠、可展开；"新建/编辑任务"的项目下拉选项默认不包含归档项目，但如果任务当前挂在某个已归档项目下，编辑该任务时下拉里要把这个归档项目也列出来（带"(已归档)"后缀），否则选中值会在下拉里找不到对应项。

### TodoItem（增量字段）

新增两个可空字段，走一次 aerich 迁移：

| 字段 | 类型 | 说明 |
|---|---|---|
| `project_id` | FK → Project，可空 | 可空 = 收件箱任务；`on_delete` 见上，实际置空由 controller 显式处理 |
| `reminder_at` | datetime，可空 | 仅存储 + 详情弹窗展示，不做推送。任务列表页不展示提醒图标（mockup 未设计这个视觉元素，本期不额外加） |

### SubTask（新表）

对应 `task-detail.html` 内嵌的子任务清单。

| 字段 | 类型 | 说明 |
|---|---|---|
| `todo_item` | FK → TodoItem，级联删除 | 父任务删除时子任务一并删除 |
| `title` | CharField | |
| `is_completed` | bool | 独立勾选，不与父任务完成状态互相约束（mockup 未设计联动，父任务可以在子任务未全部完成时直接勾选完成） |
| `order` | int | 创建时按序递增赋值，本期不支持拖拽重排（mockup 无拖拽手柄） |

## API 端点设计

沿用 `app/api/v1/todos` 现有风格：`/list` `/create` `/get` `/update` `/delete` + query 参数，非嵌套 REST；controller 继承 `CRUDBase`。

### `app/api/v1/project/`

- `GET /list`：当前用户的项目列表（含 `category_id`/`category_name` 展开），按分类分组交给前端做，不在接口层做分组。
- `POST /create` / `POST /update`：入参 `name`、`type`（project/list）、`category_id` 或 `category_name`（二选一，可都不传）、`color_hex`。
- `DELETE /delete`：如上，先置空关联任务的 `project_id` 再删除。

### `app/api/v1/category/`

- `GET /list`：仅用于"新建项目"弹窗的下拉选项，不提供 create/update/delete 路由。

### `app/api/v1/subtask/`

- `GET /list?todo_item_id=`
- `POST /create`（`todo_item_id` + `title`）
- `POST /update`（改标题 / 勾选状态）
- `DELETE /delete`

### `app/api/v1/todos/list` 扩展

在现有 `TodoController.get_todos_by_user` 基础上新增：

- `project_id: Optional[int]`：筛选具体项目。
- `inbox_only: Optional[bool]`：`true` 时筛选 `project_id IS NULL`（收件箱），与 `project_id` 同传时 `inbox_only` 优先、忽略 `project_id`（避免语义冲突，不用 `-1`/`0` 这类魔法值表达"收件箱"）。
- `quadrant_type` 从单值改为 `Optional[List[QuadrantType]]`（多选过滤，Query 多值）。
- `is_completed` 沿用现有三态（不传/true/false），已满足"状态过滤"需求，不用改。
- `sort_by: Optional[Literal["due_date", "quadrant_type", "created_at"]]` + `sort_order: Optional[Literal["asc", "desc"]]`。

`TodoItemOut` 增加 `project_id`、`reminder_at`、`subtask_total`、`subtask_completed`（后两个在 controller 层用一次聚合查询算好，列表页不产生 N+1）。

`TodoItemCreate`/`TodoItemUpdate` 增加可选的 `project_id`、`reminder_at`；`quadrant_type` 维持现有必填约束，不改 schema。quick-add（任务列表页顶部快速添加框）只暴露标题输入框，前端组装请求时固定填 `quadrant_type=not_urgent_not_important`（默认不重要不紧急），用户看不到这个字段，事后可在任务详情弹窗里改。

## 前端页面与交互

- 新页面：`web/src/views/todo/TaskList/index.vue`（沿用 `views/todo/` 目录风格），由新 `Menu` 记录"任务"驱动路由。
- 左侧 `ProjectNav` 子组件：收件箱固定项（默认选中）+ 按 `category_name` 分组的项目/清单列表（`category` 为空的项目归入"未分组"）+ 归档项目单独一栏、默认折叠 + "新建项目/清单"入口（打开新建项目弹窗）。
- 右侧任务区：quick-add 输入框（仅标题，回车提交）+ 排序下拉（截止时间/象限/创建时间）+ 过滤下拉（状态：全部/未完成/已完成；四象限：可多选）+ 按"已过期/今天/稍后"分组的任务列表。已完成任务保留显示在原分组，加划线/变淡样式，不提供隐藏开关（隐藏靠"状态"过滤器里选"未完成"实现）。
- 任务详情弹窗：标题、备注(notes)、项目下拉（含板块一的归档项目特例）、截止日期、提醒时间、象限单选、子任务清单（增删改勾选，无拖拽）。mockup 里的"关联计划"字段属于三期 Goal，本期弹窗**不渲染**。
- 新建项目/清单弹窗（mockup 只有链接、无配套弹窗，本期新增）：名称、类型单选（项目/清单）、分类（下拉 + 可输入新值，可留空）、颜色选择。
- 所有接口调用统一加进 `web/src/api/index.js` 具名方法对象，组件内不散落裸 axios 调用。

## Menu 与权限

- 新增一条 `Menu` 记录"任务"（`path` 如 `/todo/tasks`），单一入口——收件箱不单独开菜单/路由，是任务页内 `ProjectNav` 的默认选中项（组件内状态切换，不跳转路由）。
- 新增的 `project`/`category`/`subtask` 路由仍挂 `dependencies=[DependPermission]`（保持"受保护路由自动进 `Api` 表"的一致性），路由处理函数内部用 `Depends(AuthControl.is_authed)` 取当前用户、所有查询按 `user_id` 过滤，不做细粒度 RBAC——和 `todos` 模块现状一致。
- 新路由需要走一次 `refresh_api()`（应用重启或后台手动"刷新 API"）后，由管理员把新增 API 分配给角色（沿用现有流程；普通用户默认角色需要补上这批新增 API 才能正常使用任务页）。

## 已知边缘情况与迁移风险

- **迁移历史**：`Category`/`Project` 模型早已定义在 `app/models/todo.py` 但从未激活过对应路由，需要确认 `migrations/` 目录下是否已经建过这两张表——如果没有，本期迁移会一并创建表结构（而不是新增字段）。
- **FK on_delete**：`Project.category`、`TodoItem.project`（新增）需要检查 Tortoise 外键默认行为（默认 `CASCADE`）。`Category` 删除本期没有入口（Category 无独立 CRUD），暂不构成风险；`Project` 删除必须在 controller 里显式处理任务置空，不能依赖模型层默认级联。
- **过滤参数组合**：`inbox_only=true` 与 `project_id` 同传时以 `inbox_only` 为准。
- **子任务计数**：`subtask_total`/`subtask_completed` 需要在任务列表批量查询时一次性聚合，避免逐条任务单独查子任务表。

## 验收标准

- 任务列表页可从新增的"任务"菜单进入；左侧能看到收件箱 + 按分类分组的项目/清单 + 折叠的归档分组。
- quick-add 能在收件箱创建标题任务，默认象限为"不重要不紧急"。
- 任务列表按已过期/今天/稍后正确分组；排序（截止时间/象限/创建时间）、过滤（状态/多选象限）生效；已完成任务保留显示并有划线样式。
- 点击任务能打开详情弹窗，编辑并保存标题/备注/项目/截止日期/提醒/象限/子任务后，列表页对应更新（含子任务计数 "x/y"）。
- 新建项目/清单弹窗能创建新分类（输入新名称）或复用已有分类，创建后立即出现在左侧导航对应分组下。
- 删除项目后，原挂在其下的任务保留、退回收件箱可见；不会被一并删除。
- 归档项目从默认导航列表消失、出现在折叠的归档分组里；若某任务挂在归档项目下，任务详情弹窗的项目下拉仍能看到并选中该项目（带"(已归档)"标记）。
