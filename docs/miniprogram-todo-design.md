# 待办事项小程序重做方案（微信云开发版）

> 目标：把当前 Web 端「待办事项」模块的 8 个功能，用微信小程序完整重做一版。
> 约束：**不依赖现有 FastAPI 后端**，全部由小程序 + 微信云开发（云数据库 + 云函数）完成。
> 现状代码参考：`app/models/todo.py`、`app/controllers/todo.py`、`app/controllers/{habit,review,dashboard,timeblock,goal}.py`、`web/src/views/todo/**`。

---

## 1. 功能范围（8 个功能）

对应现有侧边栏「待办事项」下的 8 个页面：

| # | 小程序页面 | 对应 Web 页面 | 核心能力 |
|---|-----------|--------------|----------|
| 1 | 今日 | `Dashboard` | 问候语、今日完成度圆环、快捷添加收件箱、今日日程（时间块）、今日待办、今日习惯打卡 |
| 2 | 任务 | `TaskList` | 收件箱 + 项目/清单导航、排序/筛选、按「已过期/今天/稍后」分组、勾选完成、任务详情（子任务 + 时间块 + 关联项目/计划 + 提醒） |
| 3 | 四象限 | `TodoQuadrant` | 四象限卡片、改象限、增删改、勾选完成、截止时间、备注 |
| 4 | 日历 | `Schedule` | 日/周视图、时间块排程、创建多时间块、点开任务详情 |
| 5 | 计划 | `Goal` | 进行中/归档计划、进度条、关联任务与习惯、详情 |
| 6 | 习惯 | `Habit` | 四种频率（每天/每周几天/每周 N 次/每 N 天）、打卡、连续天数、周进度、暂停/归档 |
| 7 | 回顾总结 | `Review` | 周期（周/月/季/年）数据聚合 + 七步反思法问答、草稿/完成、历史回顾 |
| 8 | 待办统计 | `TodoHistory` | 每日完成柱状图、四象限饼图、已完成列表（分页/排序/删除） |

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────┐
│                    微信小程序（客户端）                 │
│  pages/ + components/ + services/ + utils/          │
│  • 只通过 wx.cloud.callFunction 调云函数             │
│  • 不直接读写云数据库（由安全规则兜底）                 │
└───────────────────────┬─────────────────────────────┘
                        │ wx.cloud.callFunction({name, data:{action, ...}})
┌───────────────────────▼─────────────────────────────┐
│                  云函数（服务端逻辑，Node.js）           │
│  todo / project / habit / goal / review / dashboard │
│  • 所有聚合/统计/惰性生成逻辑放这里                     │
│  • 以管理员权限读写云数据库                             │
└───────────────────────┬─────────────────────────────┘
                        │ cloud.database()（管理员权限）
┌───────────────────────▼─────────────────────────────┐
│                  云数据库（8 个集合）                   │
│  todos / projects / categories / subtasks /         │
│  time_blocks / habits / goals / reviews             │
└─────────────────────────────────────────────────────┘
```

**要点**
- 客户端只调云函数，不直接碰数据库；云函数统一做鉴权（用 `cloud.getWXContext().OPENID` 定位当前用户）和业务校验。
- 云数据库所有集合开启「仅创建者可读写」安全规则，云函数以管理员身份绕过，防止越权。
- 所有时间点字段存 `Date`；所有「纯日期」字段存 `"YYYY-MM-DD"` 字符串（详见第 7 节日期坑）。

---

## 3. 目录结构

```
miniprogram/
├─ project.config.json            # 项目配置（含 cloudfunctionRoot）
├─ miniprogram/                   # 小程序前端
│  ├─ app.js / app.json / app.wxss
│  ├─ pages/
│  │  ├─ today/                   # 1 今日
│  │  ├─ tasks/                   # 2 任务（含项目/清单导航、任务详情）
│  │  ├─ quadrant/                # 3 四象限
│  │  ├─ calendar/                # 4 日历（日/周视图）
│  │  ├─ goals/                   # 5 计划
│  │  ├─ habits/                  # 6 习惯
│  │  ├─ review/                  # 7 回顾总结
│  │  └─ stats/                   # 8 待办统计
│  ├─ components/
│  │  ├─ task-detail/             # 任务详情弹层（子任务+时间块+关联+提醒）
│  │  ├─ project-nav/             # 项目/清单侧边抽屉
│  │  ├─ goal-form/ goal-detail/
│  │  ├─ habit-form/
│  │  └─ ec-canvas/               # ECharts 小程序组件（统计页用）
│  ├─ services/
│  │  ├─ cloud.js                 # callFunction 统一封装
│  │  ├─ todo.js project.js habit.js goal.js review.js dashboard.js
│  └─ utils/
│     ├─ date.js                  # 本地日期/周期边界工具（关键）
│     ├─ quadrant.js              # 四象限枚举与颜色常量
│     └─ id.js / format.js
└─ cloudfunctions/                # 云函数（每个一个目录）
   ├─ todo/
   ├─ project/
   ├─ habit/
   ├─ goal/
   ├─ review/
   └─ dashboard/
```

**导航**：8 个功能超过 tabBar 上限（5 个），建议 `tabBar` 放「今日 / 任务 / 四象限 / 日历」4 个高频页，其余「计划 / 习惯 / 回顾 / 统计」从首页九宫格或「更多」入口进入；也可以全部用自定义 tabBar。

---

## 4. 数据模型（云数据库集合）

> 集合名用复数；外键用字符串存目标集合的 `_id`；时间点用 `Date`，纯日期用 `"YYYY-MM-DD"`。

### 4.1 todos（对应 TodoItem）
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `_id` | string | 自动 | 主键 |
| `_openid` | string | 自动 | 归属用户 |
| `title` | string | 是 | 标题（≤200） |
| `quadrant_type` | string | 是 | `urgent_important` / `urgent_not_important` / `important_not_urgent` / `not_urgent_not_important` |
| `due_date` | Date | 否 | 截止时间 |
| `notes` | string | 否 | 备注 |
| `project_id` | string | 否 | 关联 projects._id；空 = 收件箱 |
| `goal_id` | string | 否 | 关联 goals._id |
| `habit_id` | string | 否 | 非空 = 习惯生成的打卡待办 |
| `generated_date` | string | 否 | `YYYY-MM-DD`，仅习惯待办有值（幂等关键） |
| `reminder_at` | Date | 否 | 提醒时间 |
| `is_completed` | bool | 是 | 默认 false |
| `completed_at` | Date | 否 | 完成时间 |
| `created_at` / `updated_at` | Date | 是 | 创建/更新时间 |

**索引**：`_openid+is_completed`、`_openid+quadrant_type`、`_openid+project_id`、`_openid+completed_at`、`_openid+due_date`、`_openid+habit_id+generated_date`（唯一，用于打卡待办幂等）。

### 4.2 projects（对应 Project）
| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 名称 |
| `type` | string | `project` / `list` |
| `category_id` | string? | 关联 categories._id |
| `color_hex` | string? | `#RRGGBB` |
| `is_archived` | bool | 归档 |
| `created_at` / `updated_at` | Date | |

### 4.3 categories（对应 Category）
| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 名称 |
| `icon` | string? | emoji 或图标名 |
| `type` | string | `system_predefined` / `user_custom` |
| `display_order` | number | 排序 |
| `is_archived` | bool | 归档 |
| `created_at` / `updated_at` | Date | |

### 4.4 subtasks（对应 SubTask）
| 字段 | 类型 | 说明 |
|------|------|------|
| `todo_id` | string | 关联 todos._id |
| `title` | string | 标题 |
| `is_completed` | bool | |
| `order` | number | 排序（创建时递增） |
| `created_at` / `updated_at` | Date | |

### 4.5 time_blocks（对应 TimeBlock）
| 字段 | 类型 | 说明 |
|------|------|------|
| `todo_id` | string | 关联 todos._id |
| `title` | string | **冗余**标题（日历直读免 JOIN） |
| `quadrant_type` | string | **冗余**象限（日历着色） |
| `start_time` | Date | 开始（不可跨天，与 end 同一天） |
| `end_time` | Date | 结束（必须 > start） |
| `created_at` / `updated_at` | Date | |

**索引**：`_openid+start_time`。

### 4.6 habits（对应 Habit）
| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 名称 |
| `icon` | string? | emoji |
| `color_hex` | string? | 颜色 |
| `frequency_type` | string | `daily` / `weekly_days` / `weekly_count` / `interval_days` |
| `frequency_config` | object | `weekly_days: {days:[1,3,5]}`（ISO 周一=1）/ `weekly_count: {count:3}` / `interval_days: {interval:2}` |
| `default_quadrant` | string | 生成待办的默认象限，默认 `important_not_urgent` |
| `goal_desc` | string? | 目标描述（仅展示） |
| `reminder_time` | string? | `HH:mm`，写入生成待办的 reminder_at |
| `goal_id` | string? | 关联 goals._id |
| `is_paused` | bool | 暂停后不再生成新待办 |
| `is_archived` | bool | 归档 |
| `created_at` / `updated_at` | Date | |

### 4.7 goals（对应 Goal）
| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 名称 |
| `description` | string? | 描述 |
| `target_date` | string? | `YYYY-MM-DD` 目标日期 |
| `category_id` | string? | 关联分类 |
| `is_archived` | bool | 归档 |
| `created_at` / `updated_at` | Date | |

### 4.8 reviews（对应 Review）
| 字段 | 类型 | 说明 |
|------|------|------|
| `period_type` | string | `week` / `month` / `quarter` / `year` |
| `period_start` | string | `YYYY-MM-DD` 周期开始 |
| `period_end` | string | `YYYY-MM-DD` 周期结束 |
| `answers` | object | `{step1..step7}` 七步反思答案 |
| `status` | string | `draft` / `completed` |
| `created_at` / `updated_at` | Date | |

**唯一索引**：`_openid+period_type+period_start`（同周期只存一条，save 时 upsert）。

---

## 5. 云函数清单

> 统一约定：每个云函数入参 `event = { action, ...payload }`，出参 `{ code: 0, data } / { code: 非0, message }`。内部用 `cloud.getWXContext().OPENID` 定位用户，所有写操作都带 openid 过滤校验（单用户隔离）。

### 5.1 todo（任务 + 子任务 + 时间块 + 统计）
| action | 入参 | 出参 | 核心逻辑 |
|--------|------|------|----------|
| `list` | `{page, pageSize, quadrant_type?, is_completed?, start_date?, end_date?, project_id?, inbox_only?, sort_by?, sort_order?}` | `{list, total}` | 等价 `TodoController.get_todos_by_user`；`inbox_only` → project_id 为空；按 `due_date/quadrant_type/created_at` 排序 |
| `create` | `{title, quadrant_type, due_date?, notes?, project_id?, goal_id?, reminder_at?, time_blocks?[]}` | 新 todo | 校验 project/goal 存在；time_blocks 校验 `end>start` 且同一天；同时建时间块 |
| `get` | `{todo_id}` | todo + subtasks + time_blocks | 详情聚合 |
| `update` | `{id, title?, quadrant_type?, due_date?, notes?, is_completed?, project_id?, goal_id?, reminder_at?}` | 更新后 todo | 完成时补 `completed_at`，取消完成时清空 |
| `remove` | `{id}` | `{ok}` | 级联删子任务/时间块 |
| `subtask` 增删改 | `{action:'subtaskCreate/Update/Remove'}` | | 子任务 CRUD，更新时可改标题/勾选 |
| `timeblock` 增删 | `{action:'timeblockCreate/Remove'}` | | 时间块增删，校验同 `create` |
| `statisticsDaily` | `{start_date?, end_date?}` | 按日期数组 | 等价 `get_statistics_by_date`：只统计 `habit_id` 为空的已完成待办，按 completed_at 落天归象限 |
| `statisticsQuadrant` | 无 | 四象限计数 | 等价 `get_quadrant_statistics`：排除习惯待办 |

### 5.2 project（项目/清单 + 分类）
| action | 说明 |
|--------|------|
| `listCategories` | 返回当前用户分类 |
| `list` | 返回项目/清单（含未归档；筛选参数透传） |
| `create` | `{name, type, category_id?/category_name?, color_hex?}`；`category_name` 不存在则 `get_or_create` |
| `update` / `remove` | 更新/删除；删除项目时关联任务 project_id 置空（退回收件箱） |

### 5.3 habit（习惯）
| action | 说明 |
|--------|------|
| `list` | 等价 `list_active_with_status`：先触发 `ensureTodayGenerated`，返回进行中习惯 + 今日待办 id/完成态 + streak/week_progress |
| `archived` | 已归档习惯 |
| `create` | 校验 frequency_config 合法；校验 goal 存在 |
| `update` | 改字段；改频率时重新校验 config；支持 is_paused/is_archived 切换 |
| `remove` | 级联删该习惯的打卡待办 |

**核心算法（从 `habit.py` 移植，云函数里用 Node 实现）**
```
shouldGenerateToday(habit, today):
  daily        -> true
  weekly_days  -> today.isoweekday() in config.days
  interval_days-> (today - habit.createdAt.date).days % interval == 0
  weekly_count -> completedThisWeek < config.count

ensureTodayGenerated():
  对每个 is_paused=false && is_archived=false 的习惯：
    若 shouldGenerateToday 且今天无 generated_date=today 的待办，则创建：
      { title: habit.name, habit_id, quadrant_type: default_quadrant,
        generated_date: today, due_date: 今日 23:59:59, reminder_at: 由 reminder_time 合成 }

calcStreak(habit, today):
  从 today-1 往前逐日回看（最多 3650 天）：
    跳过 shouldGenerateToday=false 的日子；
    该日打卡待办已完成 -> streak++ 继续；否则 break

weekRange(today): ISO 周一为一周起点
```

### 5.4 goal（计划）
| action | 说明 |
|--------|------|
| `list` | 进行中计划 + 每个计划的 `task_completed/task_total`、`habit_count`（等价 `get_task_counts` + `get_habit_counts` 聚合） |
| `archived` | 已归档 |
| `detail` | `{goal}` + 关联 tasks 列表 + 关联 habits 列表 |
| `create` / `update` / `remove` | 增删改；删除只解除关联（任务/习惯保留） |

### 5.5 review（回顾总结）
| action | 说明 |
|--------|------|
| `dataSummary` | `{period_type, anchor_date}` → 任务完成 / 习惯打卡 / 计划进展三块聚合（纯只读） |
| `detail` | 返回该周期回顾；不存在则 data 为 null |
| `save` | `{period_type, anchor_date, answers, status}` → 同周期 upsert |
| `list` | 历史回顾列表（按 period_start 倒序） |

**核心算法**
```
calcPeriodRange(type, anchor):
  week    -> 本周一 ~ 周日
  month   -> 1 号 ~ 月末（用「下月 1 号减一天」算）
  quarter -> 所在季度首月 1 号 ~ 季末
  year    -> 1/1 ~ 12/31

dataSummary 三块：
  taskCompletion: 周期内 due_date 落范围的普通任务 total/completed，
                  urgent_important 子集，按项目分类 by_category
  habits: 每个习惯的 expected/completed/streak（expected 按 shouldGenerateToday 逐日累加）
  goals:  每个计划的 total_linked_tasks / newly_completed / progress_percent
```

### 5.6 dashboard（今日概览）
| action | 说明 |
|--------|------|
| `today` | 返回 `{date, schedule[], tasks[], habits[], completed_task_count, total_task_count}` |

**核心算法（等价 `dashboard.py`）**
```
今日日程 schedule: 今日 start_time 落当天的时间块（含冗余 title/quadrant）
今日待办 tasks:  (due_date 在今天) ∪ (今天有时间块)，且 habit_id 为空、未完成，
               due_date 非空的按时间升序在前，空排后
完成度口径:    同上并集（不过滤 is_completed），算 completed/total
今日习惯 habits: 触发 habit 云函数 ensureTodayGenerated 后，
               取 today_todo_id 非空的习惯（暂停/今天不该做的排除）
```

---

## 6. 页面与组件清单

| 页面/组件 | 说明 | 关键交互 |
|-----------|------|----------|
| 今日 | 聚合页 | 快捷添加输入框 + 三张卡片（日程/待办/习惯）+ 完成度圆环（`canvas` 或 CSS 圆环） |
| 任务 | 列表 + 项目导航 | 顶部排序/筛选 picker，任务按「已过期/今天/稍后」分组，点任务开详情弹层 |
| 四象限 | 2×2 网格 | 长按任务弹「移动到象限」菜单（替代 HTML5 拖拽） |
| 日历 | 日/周视图 | 点击日期/时间段 → 创建任务+时间块表单 |
| 计划 | 列表 + 详情 | 进度条（CSS）、详情弹层展示关联任务/习惯 |
| 习惯 | 列表 + 表单 | 频率选择器（picker）、打卡按钮、连续天数 |
| 回顾总结 | 表单页 | 周期切换 + 七步反思文本框 + 保存草稿/完成 + 历史回顾列表 |
| 待办统计 | 图表页 | 柱状图 + 饼图（`ec-canvas`），已完成列表分页 |
| task-detail | 共享组件 | 子任务增删勾选、时间块增删、关联项目/计划、提醒时间、删除任务 |

---

## 7. 关键坑与约定（务必遵守）

1. **日期/时区（最容易出错）**
   - 纯日期字段（`generated_date`、`target_date`、`period_start/end`）一律存 `"YYYY-MM-DD"` 字符串，用 `new Date(y, m-1, d)` 解析，**禁止 `toISOString()` / `new Date("YYYY-MM-DD")`**（东八区会错一天）。
   - 时间点字段存 `Date`，展示用本地时区 `getHours()/getMinutes()` 拼 `HH:mm`，不用 `toLocaleString` 的默认行为。
   - `utils/date.js` 提供：`todayStr()`、`parseLocal(str)`、`formatLocal(ms)`、`isoweekday`、`weekRange`、`calcPeriodRange`。

2. **拖拽 → 长按/点击**：小程序无原生 HTML5 drag。四象限改象限用「长按弹 ActionSheet」；日历创建时间块用「点击格子」。

3. **图表**：引入官方 `echarts-for-weixin` 的 `ec-canvas` 组件；四象限饼图颜色沿用 `#f5222d/#faad14/#1890ff/#909399`（与 `design-tokens.scss` 同源）。

4. **单用户隔离**：小程序天然单用户（openid），不需要后端 RBAC；但云数据库安全规则必须设「仅创建者可读写」，防止客户端绕过云函数越权。

5. **聚合放云函数**：习惯连续天数、回顾聚合、今日概览这些不能用客户端遍历实现（数据量大了会慢、且逻辑分散），统一放云函数。

6. **习惯打卡的幂等**：靠 `(openid, habit_id, generated_date)` 唯一；勾掉打卡待办 = 打卡，不做单独打卡记录表。

7. **提醒升级**：后端 `reminder_at` 仅存储不推送；小程序可用「订阅消息 + 云函数定时触发器」做真提醒（可选，阶段 4）。

---

## 8. 云数据库安全规则（示例）

每个集合统一设置为「仅创建者可读写」，云函数用管理员权限访问：

```json
{
  "read": "doc._openid == auth.openid",
  "write": "doc._openid == auth.openid"
}
```

客户端不直接调用 `wx.cloud.database()` 写库，统一走云函数。

---

## 9. 分阶段实施计划

| 阶段 | 内容 | 验收标准 |
|------|------|----------|
| 0 | 建工程、开通云开发、建 8 集合与索引、写 `cloud.js` 与 `date.js` | 云函数可调通，集合可读写 |
| 1 | `todo` 云函数 + 四象限页 + 任务页（先不做项目/子任务） | 增删改、勾选完成、截止时间可用 |
| 2 | Project/Category、SubTask、TimeBlock、Goal、Habit 实体与页面 | 6 个数据实体闭环 |
| 3 | 聚合逻辑：今日概览、习惯惰性生成/连续天数、回顾聚合、统计图表 | 8 个页面功能 1:1 对齐 |
| 4 | 订阅消息提醒、数据导入导出、空状态/动效打磨 | 体验完善 |
```

---

## 10. 与现有代码的映射速查

| 现有文件 | 小程序落点 |
|----------|-----------|
| `app/models/todo.py` | 第 4 节 8 个集合 schema |
| `app/controllers/todo.py` | `todo` 云函数（list/create/update/statistics） |
| `app/controllers/habit.py` | `habit` 云函数（ensureTodayGenerated / streak / weekProgress） |
| `app/controllers/review.py` | `review` 云函数（calcPeriodRange / dataSummary） |
| `app/controllers/dashboard.py` | `dashboard` 云函数（today） |
| `app/controllers/timeblock.py` | `todo` 云函数 timeblock action |
| `app/controllers/goal.py` | `goal` 云函数 |
| `web/src/views/todo/**` | `miniprogram/pages/**` |
```
