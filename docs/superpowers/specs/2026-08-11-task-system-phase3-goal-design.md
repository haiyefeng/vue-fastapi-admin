# 三期（下）：计划目标落地设计

## 背景

`docs/superpowers/specs/2026-08-04-productivity-app-blueprint-design.md` 是"个人效率应用"总体蓝图，三期是"习惯 + 计划目标"。三期（上）已经落地了习惯打卡（`docs/superpowers/specs/2026-08-10-task-system-phase3-habit-design.md`），本设计是三期（下）——计划目标（Goal），本分支从三期（上）的分支尖端 fork，`Habit` 模型已经存在。

`public/design/goals.html` 是这个模块唯一的静态原型，和 `habits.html` 一样是纯展示稿（"添加关联任务"/"关联现有习惯"按钮无实际功能，"查看习惯"按钮无跳转），本设计需要重新设计交互细节。

## 范围

- 覆盖蓝图"三期：习惯 + 计划目标"里属于计划目标的部分：`Goal` 模型 + 接口、计划页（列表/进度条/归档/新建编辑弹窗/详情弹窗）、任务详情弹窗与习惯弹窗里的"关联计划"下拉、新增"计划" Menu 记录。
- 关联任务/关联习惯**只做单向**：只能从任务详情弹窗、习惯弹窗里选"这个任务/习惯属于哪个计划"，计划详情弹窗不提供反向的"添加关联任务/关联习惯"选择器（mockup 里这两个按钮本来就是装饰性的，未接功能）。
- 计划详情弹窗里的关联习惯列表只显示名称+频率文案，不计算连续天数/本周进度——避免为一个次要展示位耦合习惯模块的生成逻辑。
- 不做：习惯打卡历史图表、拖拽排序、计划的子任务/清单式拆分（一个计划下的"关联任务"就是普通 `TodoItem`，不是新的子结构）。
- 后端先行（含 pytest 单测），前端随后。

## 数据模型变更

### Goal（新表）

```python
class Goal(BaseModel, TimestampMixin):
    user = fields.ForeignKeyField("models.User", related_name="goals", description="所属用户")
    name = fields.CharField(max_length=100, description="计划/目标名称")
    description = fields.TextField(null=True, description="描述")
    target_date = fields.DateField(null=True, description="目标完成日期")
    category = fields.ForeignKeyField(
        "models.Category", related_name="goals", null=True, description="归属分类"
    )
    is_archived = fields.BooleanField(default=False, description="归档后从主列表隐藏，历史保留")

    class Meta:
        table = "goal"

    def __str__(self):
        return self.name
```

`category` 复用一期已有的 `Category` 模型，创建/更新计划时按 `category_id`（选已有）或 `category_name`（get-or-create 新建）二选一，与 `Project` 创建时的分类交互完全一致。

### TodoItem / Habit（增量字段）

```python
goal = fields.ForeignKeyField(
    "models.Goal", related_name="todos", null=True, on_delete=fields.SET_NULL, description="关联的计划，为空表示未关联"
)
```

`Habit` 同样新增 `goal`（`related_name="habits"`）。

`on_delete=SET_NULL`：删除一个计划，已关联的任务/习惯本身保留、只是解除关联——与一期删除项目时任务退回收件箱是同一个设计思路，不是新模式。

## API 端点设计

沿用 `habit`/`project` 的扁平路由风格，路由挂 `dependencies=[DependPermission]`，处理函数内 `Depends(AuthControl.is_authed)` 取当前用户，所有查询按 `user_id` 过滤。

### `app/api/v1/goal/`

- `GET /list`：当前用户 `is_archived=False` 的计划列表，每条附带：
  - `task_total: int` / `task_completed: int`：关联任务的总数/已完成数，一次聚合查询算好（复用 `subtask_controller.get_counts_by_todo_ids` 按 `todo_item_id` 分组计数的写法，这里按 `goal_id` 分组），避免列表页 N+1。
  - `habit_count: int`：关联习惯数量，同样一次聚合查询。
- `GET /archived`：`is_archived=True` 的计划列表，不附带 `task_total`/`task_completed`/`habit_count`（归档区块的展示比进行中简单，mockup 也没有为归档项展示进度）。
- `GET /detail?goal_id=`：单个计划详情，返回计划字段 + `tasks: List[{id, title, is_completed}]`（该计划关联的全部 `TodoItem`，按 `created_at` 排序）+ `habits: List[{id, name, frequency_type, frequency_config}]`（该计划关联的全部 `Habit`，前端自行拼频率文案，不返回 streak/week_progress）。校验 `goal_id` 属于当前用户，否则 404。
- `POST /create` / `POST /update`：`name`、`description`、`target_date`、`category_id`/`category_name`（二选一，可都不传）、`is_archived`。
- `DELETE /delete`：真删除；`TodoItem.goal_id`/`Habit.goal_id` 因模型层 `on_delete=SET_NULL` 自动置空，controller 不需要手动清理（与 `TimeBlock`/`SubTask` 级联删除是模型层保证、controller 不用手动处理是同一个模式，只是这里的方向是"置空"不是"级联删除"）。

### 一期/三期（上）现有接口的扩展

- `app/schemas/todo.py`：`TodoItemCreate`/`TodoItemUpdate` 新增可选 `goal_id: Optional[int]`（与 `habit_id` 不同——`habit_id` 禁止用户直接设置以保护生成算法的幂等语义，但 `goal_id` 是用户主动选择的关联，创建/更新任务时可以直接传）。`TodoItemOut` 新增 `goal_id: Optional[int]` 只读展示字段。`TodoController.create_todo`/`update_todo` 新增 `goal_id` 的归属校验（校验该 `goal_id` 属于当前用户，仿照现有 `_validate_project` 的写法）。
- `app/schemas/habit.py`：`HabitCreate`/`HabitUpdate`/`HabitOut` 同理新增 `goal_id`，`HabitController.create_habit`/`update_habit` 新增同样的归属校验。

## 前端页面与交互

新页面 `web/src/views/todo/Goal/`：

- **`index.vue`**：进行中计划列表（复用 `Habit/index.vue` 的整体结构：图标/名称、meta 行、进度条、操作区）+ 已归档计划折叠区块（`n-collapse`，同 `Habit/index.vue` 的归档区块写法）。每条计划展示：名称、目标日期（有则显示，无则"无目标日期"）、`task_completed/task_total` 文案（如"3/8"）、`habit_count`（如"关联习惯 1 个"）、进度条（`task_total` 为 0 时显示 0%，不做"无进度"的特殊态，与"新建习惯默认 0/N"是一致的简单处理）。操作：查看详情（打开 `GoalDetailModal`）、编辑（打开 `GoalFormModal`）、归档、删除（确认弹窗）。
- **`GoalFormModal.vue`**：新建/编辑表单——名称（必填）、描述（多行文本）、目标日期（`n-date-picker`）、分类（下拉 + 可输入新值，复用 `NewProjectModal.vue` 的 `category_id`/`category_name` 二选一逻辑和现成的 `api.getCategories()`）。
- **`GoalDetailModal.vue`**：只读信息展示（名称、描述、目标日期）+ 关联任务列表（`id`/`title`/`is_completed`，勾选框直接调用 `api.updateTodo(id, { is_completed: v })`，成功后本地更新，不整体刷新弹窗）+ 关联习惯列表（名称 + 频率文案）。`frequencyLabel` 格式化函数在 `GoalDetailModal.vue` 里再写一份（和 `Habit/index.vue` 里的实现逻辑一致，但不抽公共模块）——这是本仓库对这类几行代码的小格式化函数的既定做法（象限颜色映射表已经在 `TaskDetailModal.vue`/`CreateTodoWithSlotsModal.vue`/`DayView.vue`/`WeekView.vue`/`TaskList/index.vue`/`TodoHistory/index.vue` 里各自重复了一份，没有抽公共常量文件），保持一致，不在这个设计里引入新的共享模块。这个弹窗不提供任何"添加关联"的入口（见范围一节）。

已有组件的改动：

- **`TaskDetailModal.vue`**：在"项目"下拉旁边新增"关联计划"下拉（`n-select`，`clearable`，选项来自新增的 `api.getGoals()`），与"项目"下拉并列展示，保存时把 `goal_id` 一起提交。
- **`HabitFormModal.vue`**：同样新增"关联计划"下拉，位置放在"目标描述"和"提醒时间"之间。

`web/src/api/goal.js` 新增 `getGoals`、`getArchivedGoals`、`getGoalDetail`、`createGoal`、`updateGoal`、`deleteGoal`。Menu 新增"计划"子菜单，`component: "/todo/Goal"`。

## 已知边缘情况

- **计划详情弹窗打开时不触发习惯生成检查**：`GET /goal/detail` 只读查询 `Habit` 表本身的字段，不调用 `habit_controller.ensure_today_generated`——打开一个计划的详情不应该有"顺带生成了今天的习惯待办"这种隐藏副作用，只有打开习惯页（`GET /habit/list`）才会触发生成检查，这个边界从三期（上）延续下来，不因为新增了 Goal 而打破。
- **归档计划的关联任务/习惯不受影响**：归档只是 `is_archived=True`，不会修改任何 `TodoItem.goal_id`/`Habit.goal_id`——一个已归档计划仍然能在归档区块里打开详情看到它关联的任务/习惯（只是主列表看不到这个计划了）。
- **分类与一期共享同一张表**：`Goal.category` 和 `Project.category` 指向同一个 `Category` 模型，创建计划时选"工作"分类和创建项目时选"工作"分类是同一条记录——这是刻意的设计，蓝图里分类本来就是跨项目/计划的通用维度。

## 验收标准

- "待办事项"菜单下新增"计划"入口，能看到进行中计划列表 + 折叠的归档区块。
- 新建一个计划（可选目标日期、分类），列表里出现，进度条显示 0%（"0/0"）。
- 在任务详情弹窗里把一个任务关联到该计划并保存，回到计划列表，该计划的 `task_total` 变成 1；把该任务勾选完成后，计划的 `task_completed` 变成 1，进度条相应变化。
- 在习惯弹窗里把一个习惯关联到该计划并保存，计划列表的 `habit_count` 相应增加。
- 点击"查看详情"，弹窗里能看到关联的任务列表（可直接勾选完成）和关联的习惯列表（仅名称+频率文案，不显示连续天数）。
- 归档一个计划后从主列表消失，出现在折叠的归档区块；点击"恢复"后回到主列表。
- 删除一个计划后，之前关联到它的任务在任务详情弹窗里"关联计划"变回未选中，任务本身没有被删除；关联到它的习惯同理。
