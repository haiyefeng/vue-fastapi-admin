# 二期：日历排程落地设计

## 背景

`docs/superpowers/specs/2026-08-04-productivity-app-blueprint-design.md` 是"个人效率应用"总体蓝图，划分了四期路线。二期是日历排程：新增 `TimeBlock` 模型，把 `public/design/schedule-week.html`（周视图）和 `public/design/calendar-day.html`（日视图）两个静态 mockup Vue 化并接入真实后端。

两个 mockup 均已完成并可独立打开预览（`2026-08-04-schedule-week-design.md` 记录了周视图的设计过程），交互细节已经钉死。本设计**不重新设计交互**，只产出"怎么落地"：数据模型、API 端点、组件拆分、与一期已有代码（`TodoItem`、`TaskDetailModal.vue`）的接口，性质上对应一期设计文档之于一期的角色。

## 范围

- 覆盖蓝图"二期：日历排程"整节：`TimeBlock` 模型 + 接口、周视图 Vue 化、日视图 Vue 化、"日历"Menu 记录。
- 周视图和日视图一次性一起做完（不拆分成两个子阶段），因为两者共享同一个 `TimeBlock` 模型和接口，拆开会导致后端任务和评审内容在两份计划里重复。
- 补上两个 mockup 均未设计的交互缺口：点击已排程的事件块（周视图/日视图上的色块）打开一期已有的 `TaskDetailModal.vue` 编辑；`TaskDetailModal.vue` 内新增"已排程时间"小节，展示该任务的时间块列表并支持删除单条时间块（不改动开始/结束时间、不支持拖拽调整——mockup 未设计这些，留给以后按需再做）。
- 不做：事件块本身的拖拽移动/调整时长（mockup 未设计）、月视图（蓝图已明确排除）、TimeBlock 的手动新增入口写在 `TaskDetailModal.vue` 里（新增只走日历页拖拽/多选这一条路径，避免两处入口维护两套时间选择 UI）。
- 后端先行（含 pytest 单测），前端随后，沿用 `todo-development-steps.md` 验证过的顺序。

## 数据模型变更

### TimeBlock（新表）

对应两个 mockup 里"色块"这个概念——一个任务可以有多个时间块（周视图多选可跨天为同一个新建任务生成多条）。

| 字段 | 类型 | 说明 |
|---|---|---|
| `todo_item` | FK → TodoItem，级联删除 | 父任务删除时时间块一并删除；`related_name="time_blocks"` |
| `user` | FK → User | 冗余存储，按用户 + 日期范围直查，不用二次 join 到 `todo_item`；与 `Project`/`Category` 一致用真外键（`TodoItem.user_id` 是历史遗留的裸 IntField，新表不跟随这个不一致） |
| `start_time` | datetime | |
| `end_time` | datetime | 同一天内，晚于 `start_time`，controller 层校验（不用 DB 层 CHECK 约束，沿用本项目现状） |

`TodoItem` 新增反向关系 `time_blocks: fields.ReverseRelation["TimeBlock"]`，不新增字段——`due_date`（截止时间）与时间块是两个独立概念，继续分离。

## API 端点设计

沿用 `app/api/v1/subtask` 现有风格：扁平 `/list /create /delete`，非嵌套 REST；controller 继承 `CRUDBase`；路由挂 `dependencies=[DependPermission]`，处理函数内部用 `Depends(AuthControl.is_authed)` 取当前用户，所有查询按 `user_id` 过滤。

### `app/api/v1/timeblock/`

- `GET /list`：互斥的两种查询模式（用 query 参数区分，controller 层校验二选一）：
  - `start_date` + `end_date`：按用户 + 日期范围查，供周视图/日视图渲染网格用；返回体内联展开 `todo_item_id`、`title`、`quadrant_type`（前端渲染色块需要这三个字段，不用为了拿标题再单独请求任务列表）。
  - `todo_item_id`：查某一个任务的所有时间块，供 `TaskDetailModal.vue` 的"已排程时间"小节用。
- `POST /create`：入参 `todo_item_id`、`start_time`、`end_time`。校验 `todo_item` 属于当前用户（模式同 `TodoController._validate_project`），校验 `end_time > start_time` 且同一天。日视图"拖已有未排程任务到时间轴"这个流程用这个端点。
- `DELETE /delete?id=`：按 `user_id` 校验归属后删除（`TaskDetailModal.vue` 删除时间块用）。

### `app/api/v1/todos` 扩展

- `TodoItemCreate` 新增可选字段 `time_blocks: Optional[List[TimeBlockInput]]`（`TimeBlockInput` = `{start_time, end_time}`）。`todo_controller.create_todo` 在创建 `TodoItem` 之后，同一个方法内紧接着为每个元素创建 `TimeBlock`（不强求单一 DB 事务——SQLite/当前项目里其它多步写入也未显式包事务，保持一致，失败概率极低且 `TodoItem` 创建失败会先于此终止）。这是周视图"拖拽/多选时间段 → 创建待办"一次性提交的路径。
- `get_todos_by_user` 新增 `unscheduled_only: Optional[bool]` 参数：`true` 时排除已有任意 `time_blocks` 的任务，且隐含 `is_completed=False`（未完成 + 无时间块才算"未排程"，不做日期范围限制——收件箱里躺很久的任务和今天新建的任务同等对待，都会出现在日视图的"未安排的任务"面板里）。实现上先查出已有时间块的 `todo_item_id` 集合（`TimeBlock.filter(user_id=...).values_list("todo_item_id", flat=True)`），再用 `~Q(id__in=...)` 排除，避免 join + distinct。
- `TodoItemOut` 不新增字段（时间块通过 `/timeblock/list?todo_item_id=` 单独查，不在任务详情里内联，和子任务的做法保持一致）。

## 前端页面与交互

### 页面结构

新增 `web/src/views/todo/Schedule/index.vue` 作为页面壳：顶部日期导航 + "日/周"切换按钮组（对应两个 mockup 右上角的 `.view-toggle`，在 Vue 里做成同一页面内的模式切换，不是两个路由），根据模式渲染：

- `Schedule/WeekView.vue`（对应 `schedule-week.html`）：周导航、粒度选择器（15/30/60 分钟，纯前端渲染参数，不落库）、拖拽/多选两态模式切换、时间网格、选中态小结。选中后打开 `Schedule/CreateTodoWithSlotsModal.vue`（标题 + 象限单选 + 备注 + 只读的已选时间段列表），确定后组装 `time_blocks` 数组调用 `api.createTodo({...,  time_blocks})`。
- `Schedule/DayView.vue`（对应 `calendar-day.html`）：日期导航、0–23 点纵轴时间轴、底部"未安排的任务"面板（`api.getTodos({ unscheduled_only: true })`）。面板任务可拖拽到时间轴：按 mockup 用 30 分钟吸附、默认时长 60 分钟；对拖到 23:30 之后的位置做 `[0, 1380]` 分钟钳制（避免生成跨零点的时间块，这是 mockup 评审时记录的已知边缘问题，Vue 化时一并解决）；`dragend` 时清理拖拽状态（同样是 mockup 记录的已知问题）。松手后直接调 `api.createTimeBlock({ todo_item_id, start_time, end_time })`，成功后把该任务从"未安排"面板移除、在时间轴对应位置渲染色块。

两个视图渲染出的已排程事件块，点击后打开一期已有的 `TaskDetailModal.vue`（复用，传入 `todoId`），不新建组件。

### `TaskDetailModal.vue` 改动

仿照现有"子任务"小节的写法（`TaskDetailModal.vue:43-59`），在其后新增"已排程时间"小节：`show`/`todoId` 变化时一并拉取 `api.getTimeBlocks({ todo_item_id: props.todoId })`，逐条展示"开始–结束"文本 + 删除按钮，删除调用 `api.deleteTimeBlock(id)` 后从本地列表移除。不提供新增/编辑入口。

### API 客户端

`web/src/api/index.js` 新增 `getTimeBlocks(params)`、`createTimeBlock(data)`、`deleteTimeBlock(id)` 三个具名方法；`createTodo` 的 payload 透传 `time_blocks` 字段即可，不用改函数签名；`getTodos` 透传 `unscheduled_only` 同理。

## Menu 与权限

- 在 `app/core/init_app.py` 里仿照"任务"菜单的写法（`init_menus()` 中独立于早期判断之外的追加块），在"待办事项"父菜单下追加一条"日历"子菜单，`component: "/todo/Schedule"`，保证已部署环境重启后也能自动补上。
- 新增的 `timeblock` 路由与 `/todo/create` 的字段扩展仍挂 `dependencies=[DependPermission]`，`refresh_api()` 下次运行时自动登记；管理员需要把新增 API 分配给角色（沿用一期流程）。

## 已知边缘情况

延续 `2026-08-04-schedule-week-design.md` 里"评审已确认、留给 Vue 化处理"的清单，本次一并解决：

- `schedule-week.html`：事件块未设 `pointer-events: none` 导致拖拽经过已有色块处选区停止扩展 → Vue 化用列级事件委托（`mouseover` 判断 `.slot-cell` 而非事件块）规避。
- `schedule-week.html`：鼠标移出浏览器窗口松开时 `mouseup` 不触发，拖拽状态粘滞 → 全局 `mouseup`/`mouseleave` 兜底清理。
- `schedule-week.html`：选区小结 `toFixed(1)` 在 15 分钟粒度下把 0.25 小时显示成 0.3 → 改成按粒度选择小数位数或直接展示分钟数。
- `calendar-day.html`：拖放到 23:30 之后生成越过午夜的时间块 → 起始分钟 `[0, 1380]` 钳制（见上）。
- `calendar-day.html`：无 `dragend` 清理，取消的拖拽残留待放置状态 → 补 `dragend` 监听。

新增（后端接入后才会出现的情况）：

- 周视图多选模式下选中的时间段可能跨天但同一段连续区间必须落在同一天内（`mergedRanges()` 已经按天分组，不会产生跨天的单个 range），`TimeBlock.start_time`/`end_time` 校验"同一天"时直接按此前提实现，不需要额外处理跨天 range。
- 日历页两种视图都可能与一期任务列表页的数据同时展示同一个任务（比如收件箱里的任务被排上日程后，任务列表页仍然看得到它），这是预期行为，不做"排程后从任务列表隐藏"这类联动（mockup 未设计，YAGNI）。

## 验收标准

- "待办事项"菜单下新增"日历"入口，进入后默认周视图，可切换到日视图。
- 周视图：能切换 15/30/60 分钟粒度、拖拽模式下单日列内连续选中、多选模式下跨天勾选；选中后弹窗创建任务，成功后网格上出现对应象限配色的色块，色块与选中区域一致（含跨天多段的情况）。
- 日视图：底部"未安排的任务"面板只显示无时间块的未完成任务；拖到时间轴后生成对应时间块，色块颜色随象限，任务从面板消失；拖到 23:30 之后的位置不会生成跨零点的时间块。
- 点击周视图或日视图上的任一色块，打开该任务的 `TaskDetailModal.vue`；弹窗内"已排程时间"小节列出该任务全部时间块，删除某条后色块从日历上消失、其余时间块不受影响。
- 删除任务（在 `TaskDetailModal.vue` 里"删除任务"）会级联删除其所有时间块，日历页刷新后对应色块全部消失。
