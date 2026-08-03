# 个人效率应用总体设计蓝图

## 背景与定位

`public/design/` 目录下的 13 个原型页面描绘了一个类滴答清单（TickTick）的个人效率应用："我的效率应用"，涵盖任务、项目/清单、日历排程、四象限、习惯打卡、计划目标、周期回顾、今日概览等模块。目前只有四象限待办（TodoQuadrant/TodoHistory）真正落地。

本文档是**落地蓝图**：面向当前 vue-fastapi-admin 代码库，统一数据模型、划分模块边界、排定四期开发路线。每期开工前再单独产出该期的详细 spec（本目录下），本文档只钉住全局决策，避免各期各自为政。

已有子 spec：
- [2026-08-04-schedule-week-design.md](./2026-08-04-schedule-week-design.md) — 二期日历排程的周视图交互 mockup 设计（已完成设计，mockup 待实现）

## 总体原则

1. **嵌入现有后台，不做独立应用**。所有新页面由 `Menu` 记录驱动、挂在现有 admin 侧边栏下，复用现有 JWT 登录、鉴权、个人资料。原型中的 `login.html` / `signup.html` / `settings.html` **不实现**（平台已有等价功能；settings 里的主题偏好由现有 app store 覆盖）。
2. **四象限是唯一的优先级模型**。废弃原型中并存的"高/中/低"旗标体系，不新增 priority 字段。列表页需要显示优先级标识时，由 `quadrant_type` 映射颜色：红（紧急且重要）/ 橙（紧急不重要）/ 蓝（重要不紧急）/ 灰（不紧急不重要），沿用 `TodoQuadrant/index.vue` 已有配色（`#f5222d` / `#faad14` / `#1890ff` / `#909399`）。`matrix.html` 原型里不一致的黄/青配色以已实现配色为准。
3. **数据按用户隔离，不走细粒度 RBAC**。延续 todos 模块的既有模式：路由挂在 `dependencies=[DependPermisson]` 下，处理函数内用 `Depends(AuthControl.is_authed)` 取当前用户，所有查询按 `user_id` 过滤。效率模块的数据是个人数据，角色间无共享需求。
4. **原型侧边栏拆两半**。静态模块入口（今日 / 收件箱 / 日历 / 四象限 / 习惯 / 计划 / 回顾）做成 `Menu` 记录进 admin 侧边栏；原型侧边栏里的"分类/项目"（工作 / 学习 / 我的清单…）是**用户数据**而非系统菜单，不进 `Menu` 表，由任务页面内部渲染自己的项目导航栏。
5. **接口与代码组织沿用既有约定**。新资源按 `app/api/v1/<resource>/` + `app/controllers/<resource>.py` + `app/schemas/<resource>.py` 组织；路由风格沿用 todos 模块（`/list` `/create` `/update` `/delete` + query 参数）；新路由由 `refresh_api()` 自动注册，管理员分配给角色后生效。
6. **YAGNI**。提醒（任务提醒、习惯提醒）只存字段并在页面内呈现（如今日概览高亮、过期标红），**不做**推送/通知基础设施。原型中未在本蓝图列出的细节（如任务标签 tag、位置字段）不实现。

## 核心概念区分：待办 / 日程 / 习惯

三者不是三种平行的"任务"，而是两个实体 + 一个视角：

| | 待办（TodoItem） | 日程（TimeBlock） | 习惯（Habit） |
|---|---|---|---|
| 回答的问题 | 要干什么 | 什么时候干 | 要长期坚持什么 |
| 独立存在？ | 是 | 否——必须挂在某个待办下 | 是 |
| 完成语义 | 勾选一次即完成 | 无完成态，只是时间安排 | 永不"完成"，按周期打卡 |
| 时间属性 | `due_date` 截止时间（可无） | start–end 具体时段，可多段 | 频率规则（每天/每周N次/隔N天） |
| 出现在哪 | 四象限、任务列表、收件箱 | 日历日/周视图、今日日程 | 习惯页、今日习惯 |
| 度量方式 | 完成/未完成 | —（依附于待办） | 连续天数、周期达标率 |

判断规则：做完一次就了结 → 待办；给待办定了具体时段 → 加时间块进日程（同一实体的两面）；无终点、反复坚持、在意连续记录 → 习惯。

边界约定：

- **不引入独立的"日历事件"模型**。会议等"事件"就是带时间块的待办（如"团队会议 9:00–10:30"），保持单一模型。
- **习惯打卡不生成待办**。两条线独立，仅在"今日概览"并列展示（今日日程 / 今日待办 / 今日习惯 三栏）。
- **不做"重复待办"**（YAGNI）。周期性产出类事务由用户手动建待办，或改建为习惯；确有强需求时再评估重复规则。

## 数据模型全景

```
User ─┬─ TodoItem      已有；一期 +project_id +reminder_at；三期 +goal_id
      │    ├─ SubTask   新表（一期）
      │    └─ TimeBlock 新表（二期）
      ├─ Category       已有模型，一期激活
      │    └─ Project   已有模型，一期激活
      ├─ Habit          新表（三期）
      │    └─ HabitLog  新表（三期）
      ├─ Goal           新表（三期）
      └─ Review         新表（四期）
```

### TodoItem（已有，增量修改）

| 新增字段 | 类型 | 期次 | 说明 |
|---|---|---|---|
| `project_id` | FK → Project，可空 | 一期 | 可空 = 收件箱任务 |
| `reminder_at` | datetime，可空 | 一期 | 仅存储与页面呈现，无推送 |
| `goal_id` | FK → Goal，可空 | 三期 | 任务关联到计划目标 |

既有字段（title / quadrant_type / due_date / notes / is_completed / completed_at / user_id）不变。`due_date` 语义为"最晚必须完成的截止时间"；"计划几点到几点做"由 TimeBlock 表达，两者分离。

已知不一致：`TodoItem.user_id` 是裸 IntField，而 Category/Project 用真外键。为避免无谓迁移风险，本蓝图**保持现状**，新表统一用真外键。

### SubTask（新表，一期）

对应 `task-detail.html` 的子任务/清单项。

| 字段 | 类型 | 说明 |
|---|---|---|
| `todo_item` | FK → TodoItem | 级联删除 |
| `title` | CharField | |
| `is_completed` | bool | |
| `order` | int | 手动排序 |

### TimeBlock（新表，二期）

一个任务可有**多个**时间块——支撑周视图多选不连续时段创建同一件事（见 schedule-week spec），也是"今日日程"（dashboard）的数据来源。

| 字段 | 类型 | 说明 |
|---|---|---|
| `todo_item` | FK → TodoItem | 级联删除 |
| `start_time` | datetime | |
| `end_time` | datetime | 同一天内，晚于 start_time |
| `user_id` | FK → User | 冗余存储，方便按用户+日期范围直查 |

### Category / Project（已有模型，一期激活）

模型已定义于 `app/models/todo.py`，缺 controller/schema/route/页面。一期补齐 CRUD 与任务页内的项目导航。`Project.type` 区分"项目"与"清单"（对应原型侧边栏的两类条目）；`Category` 是项目的分组（工作 / 学习…）。归档字段已有，直接使用。

### Habit / HabitLog（新表，三期）

对应 `habits.html`。

| Habit 字段 | 类型 | 说明 |
|---|---|---|
| `user` | FK → User | |
| `name` / `icon` / `color_hex` | CharField | 图标用 emoji 或 icon class |
| `frequency_type` | 枚举 | daily / weekly_days / weekly_count / interval_days |
| `frequency_config` | JSON | 如 weekly_days 存 [1,3,5]，weekly_count 存 3 |
| `goal_desc` | CharField，可空 | 如"30分钟"，仅展示 |
| `reminder_time` | time，可空 | 仅存储与展示 |
| `goal_id` | FK → Goal，可空 | 习惯关联到计划 |
| `is_paused` / `is_archived` | bool | 对应原型的暂停/归档 |

HabitLog：`habit` FK + `log_date`（date，与 habit 联合唯一）。连续天数、本周完成次数等均由查询计算，不冗余存储。

### Goal（新表，三期）

对应 `goals.html` 的计划与目标。

| 字段 | 类型 | 说明 |
|---|---|---|
| `user` | FK → User | |
| `name` / `description` | CharField / TextField | |
| `target_date` | date，可空 | |
| `category` | FK → Category，可空 | 归属分类 |
| `is_archived` | bool | |

进度 = 关联任务完成数 / 关联任务总数，查询计算。关联任务与关联习惯分别通过 `TodoItem.goal_id`、`Habit.goal_id` 反查。

### Review（新表，四期）

对应 `summary.html` 的周期回顾。

| 字段 | 类型 | 说明 |
|---|---|---|
| `user` | FK → User | |
| `period_type` | 枚举 | week / month / quarter / year |
| `period_start` / `period_end` | date | |
| `answers` | JSON | 七步提问法的七段答案 |
| `status` | 枚举 | draft / completed |

数据回顾区（任务完成率、习惯打卡率、计划进展）实时聚合计算，不落库。

## 分期路线图

每期独立走 spec → plan → 实现的完整周期；期内先后端（模型/迁移/接口）后前端，沿用 `todo-development-steps.md` 验证过的顺序。

### 一期：任务体系升级

- 激活 Category / Project：controller + schema + route + 任务页内的项目导航栏（增删改、归档、排序）
- SubTask 子任务：模型 + 接口 + 任务详情弹窗内的清单交互
- TodoItem 增加 `project_id` / `reminder_at`，aerich 迁移
- 收件箱：`project_id` 为空的任务集合；快速添加输入框（原型 dashboard 顶部的 quick-add）先落在任务列表页
- 任务列表页（参照 `tasks.html`）：按"已过期 / 今天 / 稍后"分组，支持按项目筛选、按截止时间/象限排序
- 任务详情弹窗（参照 `task-detail.html`）：标题、描述(notes)、所属项目、截止日期、象限、提醒时间、子任务
- 新增 Menu 记录：收件箱、任务列表

### 二期：日历排程

- TimeBlock 模型 + 接口（按用户 + 日期范围查询；创建待办时可同时提交多个时间块）
- 完成 `public/design/schedule-week.html` mockup（spec 已提交，见子 spec）
- 周视图 Vue 页面：mockup 的拖拽/多选交互 + 真实接口对接
- 日视图 Vue 页面（参照 `calendar-day.html`）：纵轴 0–23 点时间轴 + 底部"未安排的任务"面板，任务可拖入时间轴生成 TimeBlock
- 新增 Menu 记录：日历

### 三期：习惯 + 计划目标

- Habit / HabitLog / Goal 模型 + 接口，aerich 迁移
- 习惯页（参照 `habits.html`）：习惯列表、今日打卡、连续天数、进度条、暂停/归档/恢复、添加习惯弹窗（频率配置）
- 计划页（参照 `goals.html`）：计划列表 + 进度条、计划详情（关联任务清单、关联习惯）、添加计划弹窗
- TodoItem / Habit 增加 `goal_id`，任务详情弹窗与习惯弹窗中可选关联计划
- 新增 Menu 记录：习惯、计划

### 四期：回顾总结 + 今日概览

- Review 模型 + 接口（草稿保存 / 完成回顾）
- 回顾页（参照 `summary.html`）：数据回顾（聚合任务完成率、习惯打卡率、计划进展）→ 七步提问法逐段填写 → 从回顾直接创建新计划（复用三期的计划弹窗）
- 统计接口优化：现有 `get_statistics_by_date` 按天×象限逐次 count（30 天 = 120 次查询），改为分组聚合一次查询；回顾页所需的新统计（按项目完成率、习惯达标率）一并实现
- 今日概览页（参照 `dashboard.html`）：聚合今日日程（TimeBlock）、今日待办（今天截止或今天排程）、今日习惯（今日应打卡项），设为效率模块默认首页
- 新增 Menu 记录：今日、回顾

## 原型图 → 落地差异对照

| 原型内容 | 落地决策 |
|---|---|
| login / signup / settings 页 | 不实现，复用平台登录与个人资料；主题偏好已有 |
| 高/中/低优先级旗标 | 废弃，由四象限映射颜色 |
| matrix.html 的黄/青象限配色 | 统一为已实现的红/橙/蓝/灰 |
| 侧边栏"分类/项目"动态条目 | 不进 Menu 表，任务页内部渲染 |
| 任务提醒 / 习惯提醒推送 | 只存字段 + 页面呈现，不做推送 |
| 任务标签（tag）、位置等零散字段 | 不实现 |
| tasks / task-detail / calendar-* 为 HTML 片段 | 落地时均为完整 Vue 页面/组件 |
| dashboard 快速添加"到收件箱" | 一期先落在任务列表页，四期随今日概览回归首页 |

## 风险与依赖

- **迁移链路**：每期都有 aerich 迁移，注意 `make migrate && make upgrade` 顺序；一期激活 Category/Project 时留意 `unique_together (user, name)` 对系统预设分类（user 为空）的影响。
- **期间依赖**：二期 TimeBlock 依赖一期的任务详情弹窗（排程块点击后打开详情）；三期 Goal 关联依赖一期任务弹窗加字段；四期聚合依赖前三期全部数据。顺序不可调换。
- **Menu 初始化**：新页面的 Menu 记录通过菜单管理页手工添加即可生效（前端路由由菜单数据驱动，无需改静态路由）；若要开箱即用，可在 `init_menus()` 里追加默认菜单，但这只影响全新部署的数据库。
