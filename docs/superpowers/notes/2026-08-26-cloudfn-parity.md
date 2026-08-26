# 云函数 vs FastAPI controller 行为差异校对

对每一项：读云函数实现 → 读 controller 实现 → 判断是否等价 → 不等价则记录差异与处理方式（改后端 / 改小程序 / 接受差异）。

- 云函数：`weapp/cloudfunctions/<模块>/index.js`
- 后端：`app/controllers/<模块>.py` + `app/api/v1/<模块>/route.py`
- 小程序调用方：`weapp/miniprogram/services/*.js` + `weapp/miniprogram/pages/*/index.js`

结论分布：**8 行等价 / 2 行改后端（已修）/ 2 行改小程序 / 5 行接受差异**（第 1、8 行同时含「改后端」与「改小程序/接受差异」两部分，按主结论各计一次）。

| # | 模块 | 校对项 | 云函数行为 | 后端行为 | 结论 |
|---|---|---|---|---|---|
| 1 | todo | 分页参数与上限 | `pageArgs`（todo/index.js:21-25）：`page = max(1, parseInt||1)`，`pageSize = min(200, max(1, parseInt||20))` | route.py:29-30 默认 `page=1`/`page_size=10`，无上下界；controller todo.py:63-129 原样透传给 `CRUDBase.list` | **改后端（已修）**：补了 `page`/`page_size` 的下界钳制（`page=0` 原本让 Tortoise 抛 `ParamsError` → 500）。上限 200 **不加** → 接受差异（后端更宽松是超集，小程序最大只发 200；强加上限反而可能截断 Web 现有请求）。默认值 10 vs 20 与参数名 `pageSize`→`page_size` → 改小程序 |
| 2 | todo | 排序白名单 | `SORTABLE = ['due_date','quadrant_type','created_at','completed_at']`，非法值回落 `created_at`（todo/index.js:75-76） | todo.py:125 同样四字段白名单，非法值同样回落 `created_at` | **等价** |
| 3 | todo | 默认排序方向 | todo/index.js:78-79：`created_at`/`completed_at` 默认 `desc`，`due_date`/`quadrant_type` 默认 `asc`；显式 `sort_order` 覆盖默认 | route.py:41 `sort_order` 默认 `"asc"`；todo.py:122-127：`sort_by` 未传 → `["-created_at"]`（与云函数一致），`sort_by` 传了而 `sort_order` 未传 → 一律 `asc` | **接受差异**：小程序 4 处调用点全部显式传 `sort_order`，且取值与云函数默认一致——tasks/index.js:50（due_date/asc）、calendar/index.js:122（due_date/asc）、quadrant/index.js:35（created_at/desc）、stats/index.js:33-34（completed_at/desc）。Web 端 `web/src/views/todo/TaskList/index.vue:148` 也在前端自己复刻了同一条规则。**阶段二 `services/*.js` 必须继续显式传 `sort_order`** |
| 4 | todo | `inbox_only` 语义 | todo/index.js:58-59：`project_id` 优先，只有没传 `project_id` 时 `inbox_only` 才生效（`project_id = _.exists(false)`） | todo.py:109-112：`inbox_only` 优先（route.py:36 的参数说明也明确写了「优先于 project_id」） | **接受差异**：优先级相反，但只有两者同传时才可观测；唯一调用点 tasks/index.js:51-52 是 `if/else`，二者天然互斥 |
| 5 | todo | `habit_only` 筛选 | todo/index.js:60：`habit_only` → `habit_id = _.exists(true)` | 后端 `get_todos_by_user` 没有该参数 | **接受差异**：`grep -rn habit_only weapp/` 只命中云函数自身那一行——小程序侧没有任何调用点，是云函数里的死代码。阶段二若确有需要再补 |
| 6 | todo | `unscheduled_only` | todo/index.js:62-68：**覆盖**写 `is_completed=false`，再排除所有已有时间块的 todo（时间块查询 `limit(1000)`） | todo.py:114-120：`query &= Q(is_completed=False)`（与调用方传的 `is_completed` 取**交集**而非覆盖）；已排程 id 由 timeblock.py:49-51 `distinct()` 全量取，无 1000 条上限 | **接受差异**：仅在同时传 `unscheduled_only` + `is_completed=true` 时结果不同（云函数返回未完成项，后端返回空）；唯一调用点 calendar/index.js:122 只传 `unscheduled_only`。后端不设 1000 上限是更正确的超集 |
| 7 | todo | 日期范围筛选字段 | `due_start`/`due_end` 筛 `due_date`；`completed_start`/`completed_end` 筛 `completed_at`，两组独立（todo/index.js:70-73） | **已解决（Task 8）**：todo.py:72-73、99-107 新增 `completed_start`/`completed_end`（筛 `completed_at`），`completed_at` 也已加入排序白名单 | **已解决（Task 8）**，本轮无需改动。补充两点：① `due_start`/`due_end` 与 `habit_only` 一样在小程序侧无调用点，属云函数死代码，故未映射；② `completed_start`/`completed_end` 目前只由 `/todo/stats-bootstrap` 内部使用（route.py:196-197），`/todo/list` 未把它们暴露为 query 参数——与小程序 stats 页只走 `statsBootstrap`（stats/index.js:32-34）的用法一致 |
| 8 | habit | 惰性生成时机 | habit/index.js:87-124 `ensureTodayGenerated`：先用 `last_generated_date !== todayStr` 过滤掉当天已处理过的习惯，处理完写回 `last_generated_date`；「今天」的三个边界由客户端按本地时区算好后传入（`today_str`/`today_start_ms`/`today_end_ms`） | habit.py:99-132：没有 `last_generated_date` 短路，每次调用都全量重算；「今天」用服务端 `date.today()`；生成的待办 `due_date = combine(today, 23:59:59)`、`reminder_at` 由 `reminder_time` 拼出 | **改后端（已修）+ 接受差异 + 改小程序**，三部分：<br>① **改后端**：`is_scheduled_day` 的 `interval_days` 分支缺 `diff >= 0` 守卫（云函数 habit/index.js:37-38 有）。Python 负数取模归一到非负（`(-2) % 2 == 0`），导致「创建日之前、间隔整数倍」的天被误判成计划日。已补守卫 + 回归测试。当前调用方都夹过区间（`summary` 的 `range_start = max(created_day, start)`、`calc_streak` 遇到没打卡的计划日即 break），所以这是**潜伏**缺陷、暂无对外可见影响，但 `is_scheduled_day` 是公开的纯函数契约，必须与云函数一致。<br>② **接受差异**：`last_generated_date` 短路只是省查询，生成本身幂等（habit.py:117 先查 `exists`）。唯一可观测差异是 weekly_count 配额当天刚被满足时，后端会**立即**清掉本周未完成的打卡待办，云函数要等到第二天——后端更及时。<br>③ **改小程序**：时区口径。阶段二不再传 `today_*` 参数，改由服务端 `date.today()` 定「今天」，需接受服务端时区口径（`interval_days` 的锚点也从客户端 `created_date` 变成服务端 `created_at.date()`） |
| 9 | habit | weekly_count 达标后清理 | habit/index.js:94-100：`should === false`（即本周已完成数 >= count）时，删除本周所有**未完成**的打卡待办 | habit.py:107-114：触发条件（`WEEKLY_COUNT and not should_generate`）、删除过滤（`is_completed=False` + 本周 `generated_date` 区间）完全一致；周范围同为 ISO 周一起点（habit.py:171-174 vs habit/index.js:25） | **等价** |
| 10 | habit | streak 缓存 | habit/index.js:132-166：streak 缓存在习惯文档的 `streak`/`streak_date` 上，同一天命中即复用；频率变更时显式失效（update:250-253）；`summary` 也复用这份缓存（268-296） | 后端无缓存，`list_active_with_status`（habit.py:93）与 `summary`（habit.py:255）每次都跑 `calc_streak` | **接受差异**：纯性能优化，结果一致。回看算法逐行对齐——从昨天起、跳过非计划日、遇到「计划日但没打卡完成」立即 break、最多回看 3650 天（habit.py:153-168 vs habit/index.js:74-85）。后端没有缓存也就不存在缓存失效 bug |
| 11 | goal | 详情返回的关联数据 | goal/index.js:71-83 `detail`：goal 文档 + `tasks[{_id,title,is_completed}]` + `habits[{_id,name,frequency_type,frequency_config}]`，两者都按 `created_at asc` | goal.py:111-123 `get_goal_detail`：同样两块、同样字段、同样 `created_at` 升序，额外多一个 `category_name` | **等价**（后端是超集）。`_id` → `id` 属全局字段名适配，见第 16 行 |
| 12 | project | 删除项目时任务如何处理 | project/index.js:89-96 `remove`：先把该项目下所有 todos 的 `project_id` 移除（退回收件箱），再删项目——**不级联删任务** | project.py:38-45 `delete_project`：`TodoItem.filter(project_id=…).update(project_id=None)` 后删项目；模型层还有 `on_delete=SET_NULL` 兜底（models/todo.py:23-29） | **等价**。顺带核实了 goal 侧：云函数显式清 todos/habits 的 `goal_id`（goal/index.js:117-127），后端 `delete_goal`（goal.py:40-42）只删记录、靠 FK `SET_NULL`——实测删除后 `todo.goal_id` 与 `habit.goal_id` 均为 `None`，等价 |
| 13 | review | 周期聚合口径 | review/index.js:93-100 `dataSummary` 返回 `{period_start, period_end, task_completion, goals}`（**不含 habits**，习惯由客户端另调 habit 云函数的 `summary`）。`taskSummary`(14-30)：`due_date` 落在周期内 + `habit_id` 不存在；`byCategorySummary`(32-55)：todo→project→category 归并（`limit(1000)`）；`goalSummary`(62-91)：`total` 为计划关联任务全量（不带周期过滤）、`newly` 为周期内完成数、`progress_percent` 保留一位小数 | review.py:85-219：三块口径逐条对齐——`due_date` 范围 + `habit_id__isnull=True`（96-110）、按 `project__category_id` 分组且无 1000 条上限（112-138）、goal 的 `total_linked` 不带周期过滤 / `newly_completed` 带 `completed_at` 范围 / `round(x,1)`（199-219）；并把 habits 直接并进同一个响应（92） | **等价**（后端多返回 `habits`，是超集，阶段二可省掉一次 `habitApi.summary` 请求）。周期边界来源不同：云函数信任客户端算好的 `start_ms`/`end_ms`，后端由 `period_type` + `anchor_date` 服务端推导（review.py:33-49）；小程序 utils/date.js:51-70 `calcPeriodRange` 与之逐分支对齐（自注释即写「等价 review.calc_period_range」），且 services/review.js 已经在传 `anchor_date` |
| 14 | review | 草稿/完成状态流转 | review/index.js:122-136 `save`：按 `(period_type, period_start)` upsert；`answers` 整体覆盖；`status` 缺省 `'draft'`；**无任何流转限制**（completed 可改回 draft） | review.py:51-69 `save_review`：按 `(user, period_type, period_start)` upsert；`answers` 整体覆盖（schemas/review.py:12-15 默认 `{}`）；`status` 默认 `DRAFT`；同样无流转限制 | **等价**。差异只在周期边界来源：云函数用客户端传的 `period_start`/`period_end`，后端由 `anchor_date` 推导并强制覆盖 `period_end` → **改小程序**：pages/review/index.js:83 已经在同时传 `anchor_date`，阶段二删掉冗余的 `period_start`/`period_end` 即可；`detail` 同理由 `period_start` 改传 `anchor_date` |
| 15 | dashboard | today 返回的字段集合 | dashboard/index.js:42-48：`{date, schedule[{_id,todo_item_id,title,quadrant_type,start_time,end_time}], tasks, completed_task_count, total_task_count}`；`tasks` 是**完整 todo 文档**，仅未完成，按「有 due_date 的在前，再按 due_date 升序」排；**不含 habits**（客户端另调 habit 云函数的 `list`） | dashboard.py:10-20 + schemas/dashboard.py：`{date, schedule(TimeBlockOut，同样 6 个字段), tasks(TodayTaskItem 仅 id/title/due_date/quadrant_type/project_id), habits, completed_task_count, total_task_count}`。并集口径（`due_date` 今天 ∪ 今天有时间块、排除习惯待办）与排序规则（dashboard.py:62）逐条一致 | **接受差异**：`tasks` 字段被裁剪成 5 个，但 pages/today/index.wxml:35-37 与 index.js:60,63 实际只用到 `_id`/`title`/`quadrant_type`/`due_date`，全部在内。`habits` 后端内联返回是超集（阶段二可省掉 `habitApi.list()` 那一次并发请求） |
| 16 | 全局 | 可空关联字段语义 | 约定「空值不写字段」，查询用 `_.exists(false)`/`_.exists(true)`，清空用 `_.remove()`（todo/index.js:6-7、117-123、188-198） | 关系库统一 `NULL`，查询用 `__isnull=True`；`TodoItemUpdate` 靠 `exclude_unset=True` 区分「没传」与「显式传 null」（todo.py:142、schemas/todo.py:37-48） | **等价**。逐条核过所有相关过滤：`inbox_only` ↔ `project_id exists(false)`、`habit_only` ↔ `habit_id exists(true)`（后端未实现，见第 5 行）、`statisticsDaily`/`statisticsQuadrant`/`review.taskSummary` 的 `habit_id exists(false)` ↔ `habit_id__isnull=True`，一一对应。云函数从不写字面 `null`（MongoDB 语义下 `$exists:false` 不匹配显式 null），所以不存在「字段缺失 vs 字段为 null」的第三种状态 |

## 关于「每日统计排除习惯待办、列表不排除」的独立复核

控制方提示这可能是有意的产品行为。独立核对结论：**这不是差异，两侧完全一致，无需处理。**

- 云函数 `statisticsDaily`（todo/index.js:290）与 `statisticsQuadrant`（304）都带 `habit_id: _.exists(false)`；`list`（47-85）不带。
- 云函数 `statsBootstrap`（323-333）把这三者拼进同一个响应，也没有统一口径。
- 后端 `get_statistics_by_date`（todo.py:180）/`get_quadrant_statistics`（todo.py:215）带 `habit_id__isnull=True`，`get_todos_by_user` 不带；`/todo/stats-bootstrap`（route.py:187-200）同样把三者拼在一起。

即后端的这处「不对称」恰好就是云函数的行为，也与 Web 端既有行为一致。

## 本轮实际改了后端的两处

| 位置 | 改动 | 回归测试 |
|---|---|---|
| `app/controllers/habit.py::is_scheduled_day` | `interval_days` 分支补 `diff >= 0` 守卫，对齐云函数 `isScheduledDay`（habit/index.js:37-38） | `tests/test_habit_summary.py::test_is_scheduled_day_interval_days_before_creation_is_false` |
| `app/controllers/todo.py::get_todos_by_user` | 入口处 `page = max(1, page)` / `page_size = max(1, page_size)`，对齐云函数 `pageArgs`（todo/index.js:21-25）；此前 `page=0` 会因负 offset 抛 `ParamsError` 变成 500 | `tests/test_todo_list_extension.py::test_list_page_below_one_falls_back_to_first_page`、`::test_list_page_size_below_one_falls_back_to_one` |

## 阶段二（小程序切 service 层）必须照办的清单

1. **分页参数改名**：`pageSize` → `page_size`；不要依赖默认值（后端默认 10、云函数默认 20），列表请求一律显式传。
2. **排序方向必须显式传**：后端不实现「`created_at`/`completed_at` 默认 desc」这条规则，`sort_by` 与 `sort_order` 要成对传。
3. **`inbox_only` 与 `project_id` 不要同传**（两侧优先级相反）。
4. **`unscheduled_only` 不要与 `is_completed=true` 同传**（后端是交集，会返回空）。
5. **review 改传 `anchor_date`**：`save`/`detail`/`data-summary` 都由 `period_type` + `anchor_date` 定位周期，删掉 `period_start`/`period_end`/`start_ms`/`end_ms`/`start_str`/`end_str`。
6. **habit 请求不再传 `today_str`/`today_start_ms`/`today_end_ms`**：「今天」由服务端 `date.today()` 决定，需接受服务端时区口径。
7. **可以少发两次请求**：`/dashboard/today` 已内联 `habits`（不必再调 habit list）、`/review/data-summary` 已内联 `habits`（不必再调 habit summary）。
8. **全局字段名 `_id` → `id`**（含 `schedule[].id`、`tasks[].id`、`goal.tasks[].id` 等）。
9. **`daily` 的返回形状完全不同**：云函数 `statisticsDaily` 返回原始文档列表 `[{completed_at, quadrant_type}]`，小程序自己在 `weapp/miniprogram/pages/stats/index.js:38-42` 按日 group；后端 `/todo/statistics/daily` 返回的是**已聚合**的 `TodoStatisticsByDate` 列表（`{date, urgent_important, ..., total}`）。阶段二必须删掉客户端那段 `byDate` 分组循环，改成直接读 `d.total`。
10. **日期参数单位变了**：stats 页现在传 `start_ms`/`end_ms`/`completed_start`/`completed_end` 四个**毫秒时间戳**；后端 `stats-bootstrap` 收的是 `start_date`/`end_date` 两个 `YYYY-MM-DD`。（第 6 条只提了 habit 的 `today_*`，没提这一组，一并列入。）
11. **分页字段的位置不同**：`/todo/list` 走 `SuccessExtra`，`total`/`page`/`page_size` 在**顶层**（与 `data` 平级）；`/todo/stats-bootstrap` 的同名字段嵌在 `data.completed` 里面。两种都对（前者是仓库既有约定，后者对齐云函数 `statsBootstrap`），但客户端 http 层要分别处理。

## 校对中注意到但**未改**的事（供后续判断，本轮不动）

- 云函数 `todo` 的 `habit_only`、`due_start`/`due_end` 三个入参在小程序里没有任何调用点，属死代码；后端未映射它们是有意的。
- `app/controllers/review.py::_get_habit_checkin_summary`（148-197）与 `app/controllers/habit.py::summary`（194-259）是两份几乎相同的实现（前者用 `should_generate_today`、后者用 `is_scheduled_day`，对非 weekly_count 频率等价）。属重构范畴，不在本任务范围内。
- 云函数多处 `limit(1000)`（统计、按类目聚合、streak 回看取历史打卡）后端都没有对应上限，后端是更正确的超集。
