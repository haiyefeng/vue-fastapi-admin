# 四期（下）：今日概览落地设计

## 背景

`docs/superpowers/specs/2026-08-04-productivity-app-blueprint-design.md` 是"个人效率应用"总体蓝图，四期是"回顾总结 + 今日概览"。四期（上）已经落地了回顾总结（`docs/superpowers/specs/2026-08-13-task-system-phase4-review-design.md`），本设计是四期（下）——今日概览（Dashboard），从 `feat-task` 分支 fork（一至四期上均已合并）。这是蓝图规划的最后一块。

`public/design/dashboard.html` 是这个模块唯一的静态原型，是纯展示稿（勾选框、打卡按钮、快速添加框均无实际功能），本设计重新设计交互细节与数据来源。

## 范围

- 覆盖蓝图"四期：回顾总结 + 今日概览"里属于今日概览的部分：`GET /dashboard/today` 聚合接口（今日日程/今日待办/今日习惯）、今日概览页、快速添加入口、"待办事项"模块内默认首页调整、新增"今日" Menu 记录。
- **"设为默认首页"的范围仅限待办事项模块内部**：只调整"待办事项"父菜单的 `redirect`（从 `/todo/quadrant` 改为 `/todo/dashboard`），不改动整个平台登录后的全局落地页（`/` 仍然重定向到 `/workbench`，与效率模块无关的管理员用户体验不受影响）。
- 快速添加入口在任务列表页（`TaskList/index.vue`）和今日概览页两处都保留，不做迁移，也不抽公共组件（与本仓库既有的"小块交互逻辑各页面各写一份"的做法一致）。
- 不做：今日概览页的时间轴/日历可视化（时间块只按时间顺序列成一行一条，不做 `calendar-day.html` 那种带纵轴的视图，那是日历页已有的功能）、待办事项模块之外的全局首页替换、任务列表页快速添加入口的移除。
- 后端先行（含 pytest 单测），前端随后。

## 数据模型

不新增表，纯聚合查询，复用一至三期已有的 `TodoItem`、`TimeBlock`、`Habit` 及其 controller 方法。

## API 端点设计

新增独立模块 `app/api/v1/dashboard/`，沿用 `goal`/`review` 模块的组织方式：`app/schemas/dashboard.py` + `app/controllers/dashboard.py` + `app/api/v1/dashboard/route.py`。路由挂 `dependencies=[DependPermission]`，处理函数内 `Depends(AuthControl.is_authed)` 取当前用户，所有查询按 `user_id` 过滤。

### `GET /dashboard/today`

单一聚合接口，`today` 固定为服务器本地时区的 `date.today()`（与一至四期其余模块的时区处理方式一致，不做用户时区），返回：

- `schedule`：今天的时间块列表，复用 `time_block_controller.list_by_date_range(user_id, today, today)`，按 `start_time` 排序，每条附带对应待办的标题（`select_related("todo_item")` 已经带上）。**不过滤已完成状态**——今日日程是纯时间视图，即使对应的待办已经勾完，这段时间块本来发生过/将要发生，仍然展示（与日历日/周视图的既有展示逻辑一致，不引入新例外）。
- `tasks`：今日待办——`due_date` 落在今天 **或** 存在今天的时间块（两者取并集），且 `is_completed=False`、`habit_id__isnull=True`（排除习惯生成的打卡待办，避免和 `habits` 字段重复展示同一件事——习惯待办已经在下面的 `habits` 区块里以"打卡"的形式出现）。按 `due_date` 排序（无 `due_date` 但有今日时间块的排在后面）。
- `habits`：今日习惯——复用 `habit_controller.list_active_with_status(user_id)`（这一步会顺带触发当天该生成而未生成的习惯待办——蓝图原文明确把"读取今天相关数据的接口（待办列表、**今日概览**、习惯页）"列为惰性生成的触发点，今日概览页不是这个副作用的例外，这是唯一一个与 Goal 详情、Review 数据回顾"明确不触发生成"相反的聚合类接口，因为它本身就代表"今天要做的事情"这个语境），从结果里过滤出 `today_todo_id` 不为空的——即今天真正需要打卡的习惯（暂停的、或按频率规则今天不该打卡的习惯不出现在这里，即使它们出现在习惯页的"进行中"列表里）。

### 一期已有接口的复用

- 快速添加复用 `POST /todo/create`，不新增接口。
- 待办勾选完成复用 `POST /todo/update`（`is_completed: true`）。
- 习惯打卡复用 `POST /todo/update`（对 `habit.today_todo_id` 设置 `is_completed: true`），与 `Habit/index.vue::checkIn` 完全一致的调用方式。

## Menu 与默认页调整

- 新增 Menu 记录：`name="今日"`，`path="dashboard"`，`component="/todo/Dashboard"`，`order=-1`，`parent_id` 为"待办事项"父菜单 id，`keepalive=True`。`order=-1` 让它在侧边栏排在"任务"（`order=0`）之前，匹配原型图的菜单顺序；前端排序（`SideMenu.vue`）是纯数字比较，负数合法，不需要为了插队去重新编号其余 5 条已有 Menu 记录。
- "待办事项"父菜单的 `redirect` 从 `/todo/quadrant` 改为 `/todo/dashboard`。既有代码里这个字段只在**首次创建**父菜单时写入（`init_menus()` 里 `if not todo_menu:` 分支内），对已经跑过初始化的数据库（包括当前开发环境）不会自动生效。因此额外补一段幂等的更新逻辑：若父菜单已存在但 `redirect` 不是 `/todo/dashboard`，则更新它——保证已部署环境重启后也能拿到新的默认页，不只是全新建库时才对。

## 前端页面与交互

新页面 `web/src/views/todo/Dashboard/index.vue`：

- **顶部**：标题"今日概览" + 当前日期（格式"星期X，YYYY年M月D日"，本地日期，不涉及跨时区问题）+ 快速添加输入框（`n-input` + 回车/按钮触发，创建到收件箱：`{ title, quadrant_type: 'not_urgent_not_important' }`，不带 `project_id`/`due_date`——与 `TaskList/index.vue::handleQuickAdd` 收件箱场景的默认值一致）。创建成功后清空输入框、重新加载整个今日概览数据（因为新建的任务如果恰好设了今天到期可能要出现在"今日待办"里，但由于快速添加不设置 `due_date`，实际不会立即出现在任何一栏——这是预期行为，新任务默认落在收件箱，用户需要另外去任务详情弹窗设置截止日期或在日历页拖拽排程，快速添加本身不是"添加到今天"的捷径）。
- **三栏网格布局**（对应原型 `dashboard-grid`，`display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))`）：
  - **今日日程**：按 `start_time` 排序展示时间块，每条 `"HH:MM–HH:MM 任务标题"`；点击整行打开 `TaskDetailModal.vue`（复用，传 `todo_item_id`）。空状态：`n-empty` + "查看完整日历"链接跳转 `/todo/schedule`。
  - **今日待办**：未完成的今日待办列表，`n-checkbox` + 象限色点（复用 `TaskList/index.vue` 的 `quadrantMeta`/`quadrantColor` 配色映射）+ 标题；勾选后调用 `api.updateTodo(id, { is_completed: true })`，成功后从本地数组移除（乐观更新，失败回滚，参照 `TaskList/index.vue::toggleComplete` 的写法）；点击标题打开 `TaskDetailModal.vue`。空状态：`n-empty` + "查看所有任务"链接跳转 `/todo/tasks`。
  - **今日习惯**：习惯名 + 频率/连续天数文案（复用 `Habit/index.vue` 的 `frequencyLabel` 格式化函数，在本文件里再写一份，不抽公共模块，与 `GoalDetailModal.vue` 已经复制一份 `frequencyLabel` 的先例一致）+ "打卡"按钮（点击后 `api.updateTodo(habit.today_todo_id, { is_completed: true })`，成功后本地把该条 `today_completed` 置为 `true`，按钮态切换为"已打卡 ✓"禁用，与 `Habit/index.vue::checkIn` 的展示逻辑一致）。空状态：`n-empty` + "管理习惯"链接跳转 `/todo/habit`。
- **数据加载**：`onActivated(loadToday)` 单一触发，`defineOptions({ name: '今日' })`——这个仓库在三/四期（上）都踩过"`index.vue` 文件名导致组件推断名为 `'index'`、与 `KeepAlive` 的 `:include` 按组件名匹配对不上"的坑（`Goal/index.vue`、`Habit/index.vue` 都是在最终评审阶段才补上 `defineOptions`），本页面从一开始就按正确方式写，不再重复踩坑。
- `TaskDetailModal.vue` 关闭后（无论保存/删除）需要刷新今日概览数据——沿用 `Schedule/index.vue` 已经建立的 `watch(detailShow, (v) => { if (!v) loadToday() })` 模式，保证任务详情弹窗里的改动（比如把今天到期的任务改到别的日期）能反映到"今日待办"列表。

`web/src/api/dashboard.js` 新增 `getTodayOverview`。

## 已知边缘情况

- **今日待办与今日习惯不重复展示**：习惯生成的打卡待办（`habit_id` 非空）永远不出现在"今日待办"区块，只会以"打卡"按钮的形式出现在"今日习惯"区块——这是一个明确的展示分流决策，不是遗漏。
- **今日概览是习惯惰性生成的合法触发点**：与 Goal 详情、Review 数据回顾"明确不触发生成"的边界规则相反，今日概览页调用 `list_active_with_status` 会顺带触发当天的习惯待办生成检查——这是蓝图原文就明确规定的行为，不是这次新引入的例外。
- **快速添加不等于"添加到今天"**：快速添加创建的任务默认无 `due_date`、无时间块，不会立即出现在"今日待办"或"今日日程"里；这是收件箱任务的正常状态，用户需要额外操作（设置截止日期或拖拽排程）才会让它出现在今日概览的对应区块。
- **待办事项父菜单 redirect 的升级路径**：见上文"Menu 与默认页调整"一节，需要显式的幂等补丁逻辑，不能只改初次建库分支。

## 验收标准

- "待办事项"菜单下第一项是"今日"入口（排在"任务"之前）。
- 点击侧边栏"待办事项"父级菜单，默认进入今日概览页（而不是四象限待办）；全局登录后落地页仍然是 `/workbench`，不受影响。
- 今日概览页顶部显示当天日期，快速添加框能成功创建任务到收件箱（输入框清空，任务出现在任务列表页的收件箱里，但不出现在今日概览的任何区块）。
- 有今天时间块的任务出现在"今日日程"，按时间排序；点击能打开任务详情弹窗。
- 有今天到期或今天排程、未完成、非习惯生成的任务出现在"今日待办"；勾选后从列表消失。
- 今天需要打卡的习惯（未暂停且按频率规则今天该做）出现在"今日习惯"；点击打卡后按钮变为已打卡态。
- 三个区块为空时分别展示到对应完整页面（日历/任务列表/习惯页）的引导链接。
- 在任务详情弹窗里修改一个今天到期的任务的截止日期为其他日期后关闭弹窗，该任务从"今日待办"消失。
- 离开今日概览页再切回来（KeepAlive 场景），数据正确重新加载，不是空白/陈旧数据。
