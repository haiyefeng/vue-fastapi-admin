# 三期（上）：习惯打卡落地设计

## 背景

`docs/superpowers/specs/2026-08-04-productivity-app-blueprint-design.md` 是"个人效率应用"总体蓝图，三期是"习惯 + 计划目标"。三期内部又分两个相对独立的子系统：习惯打卡（Habit，核心是频率规则、惰性生成待办、连续天数/达标率统计——概念上比一期/二期都更算法化）和计划目标（Goal，相对简单的 CRUD + 进度计算，但需要关联已有的习惯）。本设计只覆盖前者——习惯打卡；计划目标作为三期（下）单独走一轮 spec → plan → 实现，届时再给 `Habit`/`TodoItem` 补 `goal_id` 外键。

`public/design/habits.html` 是这个模块唯一的静态原型，但它是纯展示稿（频率下拉框不联动、"今日打卡"按钮不做任何事），不像二期的 `schedule-week.html`/`calendar-day.html` 那样已经把交互钉死。本设计因此需要重新设计交互细节，而不只是"把已验证的 JS 转成 Vue"。

## 范围

- 覆盖蓝图"三期：习惯 + 计划目标"里属于习惯打卡的部分：`Habit` 模型 + 接口、习惯待办的惰性生成、习惯页（列表/连续天数/进度条/暂停/归档/恢复/新建编辑弹窗）、现有统计接口排除习惯待办、新增"习惯" Menu 记录。
- 不做：计划目标（`Goal` 模型、`goal_id` 关联、"关联到计划"下拉）——留给三期（下）。习惯详情的打卡历史图表（mockup 里的"统计"图标按钮无落地页面，YAGNI 不实现）。习惯的拖拽排序（mockup 无此设计）。
- 后端先行（含 pytest 单测），前端随后。

## 数据模型变更

### Habit（新表）

```python
class HabitFrequencyType(StrEnum):
    DAILY = "daily"
    WEEKLY_DAYS = "weekly_days"        # 每周固定几天，如周一三五
    WEEKLY_COUNT = "weekly_count"      # 每周任意 N 次（弹性型）
    INTERVAL_DAYS = "interval_days"    # 每隔 N 天一次


class Habit(BaseModel, TimestampMixin):
    user = fields.ForeignKeyField("models.User", related_name="habits")
    name = fields.CharField(max_length=100, description="习惯名称")
    icon = fields.CharField(max_length=50, null=True, description="图标，emoji 或简短文本")
    color_hex = fields.CharField(max_length=7, null=True, description="颜色代码")
    frequency_type = fields.CharEnumField(HabitFrequencyType, description="频率类型")
    frequency_config = fields.JSONField(
        null=True,
        description="weekly_days: {\"days\": [1,3,5]}（ISO 星期一=1）；weekly_count: {\"count\": 3}；interval_days: {\"interval\": 2}；daily 不需要配置",
    )
    default_quadrant = fields.CharEnumField(
        QuadrantType, default=QuadrantType.IMPORTANT_NOT_URGENT, description="生成待办的默认象限"
    )
    goal_desc = fields.CharField(max_length=100, null=True, description="目标描述，如'30分钟'，仅展示")
    reminder_time = fields.TimeField(null=True, description="每日提醒时间，写入生成待办的 reminder_at")
    is_paused = fields.BooleanField(default=False, description="暂停后停止生成新待办，历史保留")
    is_archived = fields.BooleanField(default=False, description="归档后从主列表隐藏，历史保留")

    class Meta:
        table = "habit"

    def __str__(self):
        return self.name
```

### TodoItem（增量字段）

```python
habit = fields.ForeignKeyField(
    "models.Habit", related_name="todos", null=True, on_delete=fields.CASCADE, description="所属习惯，非空表示是习惯生成的打卡待办"
)
generated_date = fields.DateField(
    null=True, description="习惯待办的所属日期，仅习惯生成的待办有值；用于幂等判断'今天是否已生成'和'是否属于本周'，与用户可自行修改的 due_date 语义分离"
)
```

`on_delete=fields.CASCADE`：真删除一个习惯时，其历史生成的所有打卡待办一并删除（真删除即彻底不要，历史归档诉求走"归档习惯"而不是删除）。

`generated_date` 单独建字段而不复用 `due_date`：`due_date` 用户可以在任务详情弹窗里改（一期已有交互），如果幂等判断依赖它，用户一改日期就会导致重复生成；`generated_date` 是系统内部记账字段，不在任何编辑表单里暴露。

## 惰性生成算法

**触发点**：只在 `GET /habit/list` 里触发（不改动一期已有的 `/todo/list`，改动面小）。习惯页每次加载/刷新都会先跑一次生成检查，再返回列表。这意味着用户如果从不打开习惯页，历史缺口不会自动补——这是可接受的设计，习惯页本身就是"惰性生成"这个模式认领的唯一入口。

`HabitController.ensure_today_generated(user_id)`，在 `list_habits` 内部先调用：

```python
today = date.today()
for habit in Habit.filter(user_id=user_id, is_paused=False, is_archived=False):
    should_generate = _should_generate_today(habit, today)

    if habit.frequency_type == HabitFrequencyType.WEEKLY_COUNT and not should_generate:
        # 额度已满：清理本周所有该习惯尚未完成的旧实例（弹性型不算错过，直接删除）
        week_start, week_end = _week_range(today)
        await TodoItem.filter(
            habit_id=habit.id, is_completed=False,
            generated_date__gte=week_start, generated_date__lte=week_end,
        ).delete()

    if should_generate:
        exists = await TodoItem.filter(habit_id=habit.id, generated_date=today).exists()
        if not exists:
            await TodoItem.create(
                title=habit.name,
                habit_id=habit.id,
                user_id=user_id,
                quadrant_type=habit.default_quadrant,
                generated_date=today,
                due_date=datetime.combine(today, time(23, 59, 59)),
                reminder_at=datetime.combine(today, habit.reminder_time) if habit.reminder_time else None,
            )
```

`_should_generate_today(habit, today)` 按类型分支：

- `daily`：恒 `True`。
- `weekly_days`：`today.isoweekday() in habit.frequency_config["days"]`。
- `interval_days`：以创建日为锚点，`(today - habit.created_at.date()).days % habit.frequency_config["interval"] == 0`。
- `weekly_count`：本周（周一到周日）已完成数 `< habit.frequency_config["count"]`。已完成数按 `generated_date` 落在本周范围内 + `is_completed=True` 统计，不看 `completed_at`（避免跨周补打卡的边界问题——只要是本周生成的实例，在本周内完成就算数）。

不建数据库唯一约束防重（`(habit_id, generated_date)` 组合），改用"生成前先查是否已存在"的应用层幂等检查——个人应用场景下并发写入概率极低，唯一约束会让迁移复杂度上升但收益很小。

**幂等语义**：定日型（daily/weekly_days/interval_days）该生成的日子如果没打开习惯页，那天永远不会补生成——不追溯补录，只影响"连续天数"统计（断掉的那天记为未完成）。弹性型（weekly_count）同理，本周没打开习惯页就不会生成新实例，但已生成的实例依然可以在之后某天打开习惯页时看到并打卡。

## 连续天数（streak）与本周进度

**定日型（daily/weekly_days/interval_days）**：从"最近一个应该生成的日期"开始倒着数，遇到第一个未完成（或未生成）的日子就断开：

```python
async def _calc_streak(habit: Habit, today: date) -> int:
    streak = 0
    cursor = today
    while True:
        if not _should_generate_today(habit, cursor):
            cursor -= timedelta(days=1)
            continue
        todo = await TodoItem.filter(habit_id=habit.id, generated_date=cursor).first()
        if todo and todo.is_completed:
            streak += 1
            cursor -= timedelta(days=1)
        else:
            break
    return streak
```

（`today` 当天如果还没打卡，不计入 streak，也不算断——从 `cursor = today` 起遇到"今天未完成"直接 `break`，streak 从昨天及之前累计的结果原样返回；这是"中断重新计数"规则在"今天还没来得及打卡"这个常见场景下的自然结果，不需要特判。）

**弹性型（weekly_count）**：mockup 展示的是"最长连续 N 周"达标，但这个统计需要遍历历史所有周、判断每周是否达标，属于本阶段的加分项而非核心需求。本阶段弹性型只展示"本周 x/y"进度条（`week_progress`），不做"连续 N 周"这个更复杂的统计，避免过度设计。

## API 端点设计

沿用 `app/api/v1/subtask` 的扁平路由风格，路由挂 `dependencies=[DependPermission]`，处理函数内 `Depends(AuthControl.is_authed)` 取当前用户，所有查询按 `user_id` 过滤。

### `app/api/v1/habit/`

- `GET /list`：先跑 `ensure_today_generated`，再返回当前用户 `is_archived=False` 的习惯列表（含暂停的，暂停的习惯前端置灰展示但不单独分区——mockup 只有"归档/暂停"合并成一个区块）。每条附加：
  - `today_todo_id: Optional[int]`：今天对应的待办 ID（`is_paused` 为真时恒为 `null`），前端"今日打卡"按钮直接对它调用一期已有的 `PUT /todo/update`，不新增打卡专用接口。
  - `streak: Optional[int]`：定日型才有值。
  - `week_progress: Optional[str]`：弹性型才有值，格式 `"1/3"`。
- `GET /archived`：返回 `is_archived=True` 的习惯，不跑生成检查。
- `POST /create` / `POST /update`：`name`、`icon`、`color_hex`、`frequency_type`、`frequency_config`、`default_quadrant`、`goal_desc`、`reminder_time`、`is_paused`、`is_archived`。
- `DELETE /delete`：真删除，级联删除历史待办（模型层 `on_delete=CASCADE` 已保证，controller 不需要手动清理）。

### 一期 `/todo` 现有接口的兼容性

`TodoItemOut` 增加 `habit_id: Optional[int]`（只读展示，任务列表页可以据此显示一个小图标区分"这是习惯待办"，本阶段不强制做这个 UI，只是接口层面不遗漏这个字段）。`TodoItemUpdate`/`TodoItemCreate` **不**暴露 `habit_id`——习惯待办只能由生成算法创建，用户不能手动把一个普通待办"过继"给某个习惯，避免破坏幂等语义。

### 统计接口排除习惯待办

`TodoController.get_statistics_by_date` 和 `get_quadrant_statistics` 的查询各加一个 `habit_id__isnull=True` 条件，排除习惯待办对四象限统计/每日完成统计的干扰（与蓝图"避免自动生成灌水"的要求一致）。

## 前端页面与交互

新页面 `web/src/views/todo/Habit/index.vue`：

- **进行中习惯列表**：图标 + 名称、频率文案（`daily`→"每天"；`weekly_days`→"每周一三五"这样按 `frequency_config.days` 拼；`weekly_count`→"每周N次"；`interval_days`→"每隔N天"）、连续天数（定日型，"连续坚持 N 天"）或本周进度条（弹性型，`week_progress` 直接展示 + 一个百分比进度条）、"今日打卡"按钮（`today_todo_id` 为空时禁用；`is_paused` 为真时整行置灰且按钮禁用）、编辑/暂停/归档/删除的下拉菜单（`n-dropdown`，参照 `ProjectNav.vue` 的用法）。
- **已归档/暂停区块**：`n-collapse` 折叠，默认收起（参照 `ProjectNav.vue` 归档项目的做法），列出 `is_archived=True` 的习惯（来自 `/habit/archived`），提供"恢复"（`update({is_archived: false})`）和"删除"操作。`is_paused=True` 但未归档的习惯留在主列表里置灰展示，不挪到这个区块（暂停是"先歇一阵还想看到它"，归档是"暂时不想看到但不删"，两者语义不同，UI 也应该分开）。
- **新建/编辑习惯弹窗** `HabitFormModal.vue`：
  - 名称（必填）、图标（一个纯文本输入框接受任意 emoji，不引入 icon picker 组件库）、颜色（`n-color-picker`，复用一期 `NewProjectModal.vue` 的做法）。
  - 频率类型 `n-radio-group` 四选一；选中 `weekly_days` 时展示周一到周日的多选按钮组（`n-checkbox-group`，值存 ISO 星期数字 1-7）；选中 `weekly_count` 时展示一个 `n-input-number`（"每周"+ 数字 + "次"）；选中 `interval_days` 时展示一个 `n-input-number`（"每隔"+ 数字 + "天"）；`daily` 不展示额外配置。
  - 默认象限：单选，样式复用 `TaskDetailModal.vue` 的象限单选（四色圆点 + label）。
  - 目标描述（选填文本）、提醒时间（`n-time-picker`，选填）。
- Menu：在"待办事项"父菜单下新增"习惯"子菜单，`component: "/todo/Habit"`。

`web/src/api/habit.js` 新增 `getHabits`、`getArchivedHabits`、`createHabit`、`updateHabit`、`deleteHabit`；"今日打卡"复用已有的 `api.updateTodo`。

## 已知边缘情况

- **习惯创建当天**：`interval_days` 的锚点是 `created_at.date()`，创建当天 `(today - anchor).days == 0`，`0 % interval == 0` 恒成立，所以创建当天就会生成第一条待办——符合直觉（"我今天设了个每隔3天的习惯，那今天就先来一次"）。
- **`weekly_count` 精确到"本周"的边界**：本设计统一用 ISO 周（周一到周日），与二期 `WeekView.vue` 的周视图（同样周一开始）保持一致，不会出现"日历页的周"和"习惯页的周"定义不一样的情况。
- **暂停/归档不清理未来待办**：暂停或归档一个习惯，不会删除它已经生成、当前未完成的打卡待办（比如今天已经生成了但用户下午才暂停），这些待办保留在任务列表里，用户可以照常完成或忽略；只是从这一刻起不再生成新的。
- **暂停会打断连续天数**：`_calc_streak` 只看"某天是否应该生成"和"是否生成了且完成"，不感知"当时是不是被暂停的"——暂停期间 `ensure_today_generated` 跳过该习惯，不生成待办，倒推计算 streak 时会在这些天遇到"应生成但没有对应待办"，视同未完成，streak 在此中断。也就是说主动暂停和错过打卡对连续天数的影响是一样的，这是本阶段的既定行为（不引入暂停时间段记录来豁免这段时间，避免为一个次要场景增加模型复杂度）。
- **`weekly_count` 弹性清理只在生成检查时触发**：如果用户这周已经达标、但从不再打开习惯页，那些"多余"的未完成旧实例不会被清理，会一直挂在任务列表里。这是"只在 `/habit/list` 触发"这个范围决策的自然结果，等到下次打开习惯页触发生成检查时才会补上清理。

## 验收标准

- "待办事项"菜单下新增"习惯"入口，能看到进行中习惯列表 + 折叠的归档/暂停区块。
- 新建一个 `daily` 习惯，打开习惯页后立即看到今天的打卡按钮可点；点击后按钮变为已完成状态（或按钮消失，视最终 UI 实现），任务列表页也能看到对应的已完成待办。
- 新建一个 `weekly_count=3` 的习惯，连续三天打开习惯页并打卡，第三次打卡后第四天打开习惯页，不再生成新的待办（本周额度已满）；本周进度条显示 3/3。
- 新建一个 `weekly_days=[1,3,5]`（周一三五）的习惯，在非周一三五打开习惯页，不生成待办；连续两周的周一三五都打卡，第三周任意一天错过后再打卡，连续天数从 1 重新算起。
- 暂停一个习惯后，习惯页不再为它生成新待办，历史记录保留；连续天数会在暂停期间被打断（与错过打卡的效果一致，见"已知边缘情况"）。
- 归档一个习惯后从主列表消失，出现在折叠的归档区块；点击"恢复"后回到主列表且能继续生成。
- 真删除一个习惯后，它历史生成的所有打卡待办从任务列表/四象限里消失。
- 一期四象限统计、待办统计（`TodoHistory`）的数字不包含任何习惯待办。
