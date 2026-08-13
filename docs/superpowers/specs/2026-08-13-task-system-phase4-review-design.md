# 四期（上）：回顾总结落地设计

## 背景

`docs/superpowers/specs/2026-08-04-productivity-app-blueprint-design.md` 是"个人效率应用"总体蓝图，四期是"回顾总结 + 今日概览"。本设计是四期（上）——回顾总结（Review），从 `feat-task` 分支 fork（一/二/三期均已合并）。今日概览（Dashboard）作为四期（下）单独走设计。

`public/design/summary.html` 是这个模块唯一的静态原型，是纯展示稿（"生成改进计划"区块的新建计划无实际功能，反思步骤的引导文案是固定文案），本设计重新设计交互细节与数据来源。

## 范围

- 覆盖蓝图"四期：回顾总结 + 今日概览"里属于回顾总结的部分：`Review` 模型 + 接口、数据回顾聚合接口、回顾页（周期切换/数据展示/七步反思/生成计划/历史回顾）、新增"回顾总结" Menu 记录。
- 蓝图明确要求的统计接口优化（`get_statistics_by_date` 从 30×4=120 次独立查询改为分组聚合）在本阶段一并完成，因为数据回顾区的任务完成情况统计要复用同样的聚合方式。
- **回顾催生的计划不持久化关联**：点击"添加新计划/目标"复用三期 `GoalFormModal` 创建 Goal，不建立 `review_id` 等反向关联字段；页面上展示的"本次回顾新建的计划"列表是纯前端会话状态，刷新页面即清空。
- 不做：今日概览页（四期下）、回顾内容的富文本/图表可视化、跨周期对比趋势图。
- 后端先行（含 pytest 单测），前端随后。

## 数据模型变更

### Review（新表）

```python
class ReviewPeriodType(StrEnum):
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    COMPLETED = "completed"


class Review(BaseModel, TimestampMixin):
    user = fields.ForeignKeyField("models.User", related_name="reviews", description="所属用户")
    period_type = fields.CharEnumField(ReviewPeriodType, description="回顾周期类型")
    period_start = fields.DateField(description="周期开始日期")
    period_end = fields.DateField(description="周期结束日期")
    answers = fields.JSONField(default=dict, description="七步提问法答案，key 为 step1~step7")
    status = fields.CharEnumField(ReviewStatus, default=ReviewStatus.DRAFT, description="草稿/已完成")

    class Meta:
        table = "review"
        unique_together = (("user", "period_type", "period_start"),)

    def __str__(self):
        return f"{self.period_type} {self.period_start}"
```

`unique_together (user, period_type, period_start)` 落实"同一用户同一周期类型同一起始日只能有一条记录"——同周期重复打开就是继续编辑同一条，不管当前是 draft 还是 completed。

`period_start`/`period_end` 由后端根据 `period_type` + 前端传入的锚点日期（周期内任意一天）计算：

- `week`：锚点日期所在自然周的周一到周日。
- `month`：锚点日期所在月的 1 号到月末最后一天。
- `quarter`：锚点日期所在季度的首日到末日。
- `year`：锚点日期所在年的 1/1 到 12/31。

`answers` 结构为 `{"step1": "...", ..., "step7": "..."}`，七个问题的引导文案（原型里"负面→正面"等固定引导语）前端硬编码展示，不入库。

## API 端点设计

沿用 `goal`/`habit` 的扁平路由风格，路由挂 `dependencies=[DependPermission]`，处理函数内 `Depends(AuthControl.is_authed)` 取当前用户，所有查询按 `user_id` 过滤。

### `app/api/v1/review/`

- `GET /data-summary?period_type=&anchor_date=`：只读聚合查询，不依赖 Review 记录是否存在，可重复调用。返回：
  - 任务完成情况：总体（`due_date` 落在周期内的任务数为分母，其中 `is_completed=True` 的为分子）+ 按 `Project.category` 分组（无项目/无分类的任务不计入任何分类维度，但计入总体）+ 按象限（`urgent_important` 象限单独统计"高优先级完成"）。均排除 `habit_id__isnull=False` 的习惯生成待办，与三期已建立的统计口径一致。
  - 习惯打卡情况：所有 `is_archived=False and is_paused=False` 的习惯列表，定日型（daily/weekly_days/interval_days）展示"周期内完成天数/应生成天数" + 当前连续天数（复用 `HabitController._calc_streak`）；弹性型（weekly_count）展示"周期内完成次数/周期内配额总数"（配额按完整自然周数 × `weekly_count` 估算，首尾不满一周的部分按比例忽略，不追求绝对精确）。
  - 计划进展：所有未归档 Goal，每个展示"周期内新完成的关联任务数/计划关联任务总数"，无关联任务时展示"无明显进展"（对应原型文案）。
- `GET /detail?period_type=&anchor_date=`：查询该周期是否已有 Review 记录。存在则返回（含 `answers`/`status`），不存在返回 404，前端据此决定是"新建"还是"继续编辑"界面。
- `POST /save`：`period_type`、`anchor_date`、`answers`（七步全量或部分）、`status`（`draft`/`completed`）。后端按 `period_type`+`anchor_date` 算出 `period_start`/`period_end`，`get_or_create` 后 update——不存在则创建，存在则覆盖更新。前端只在点击"保存草稿"/"完成本次回顾"按钮时才调用（不做分步自动保存）。
- `GET /list?period_type=`：历史回顾列表（`period_type` 可选筛选），按 `period_start` 倒序，用于回顾页"查看历史回顾"入口。

### 统计接口优化

`app/controllers/todo.py::get_statistics_by_date`（当前实现：30 天循环 × 4 象限 = 120 次独立 `count()` 查询）改造为两次分组聚合查询：一次查日期范围内所有已完成待办的 `(completed_at 日期, quadrant_type)` 分组计数，在内存里按天/象限归位填充结果数组。**只改内部实现，不改函数签名/返回结构**（`List[TodoStatisticsByDate]`），现有调用方（`TodoHistory` 页面）不受影响。回顾模块的"任务完成情况"统计复用同样的分组聚合写法（维度换成分类/象限，日期范围换成周期起止）。

## 前端页面与交互

新页面 `web/src/views/todo/Review/`：

- **`index.vue`**：回顾页主体，对应 `summary.html`。
  - 顶部：周期类型切换（`n-radio-group`：周/月/季/年）+ 锚点日期选择（`n-date-picker`，默认今天）+ 显示计算出的 `period_start`–`period_end` 文案。周期类型或锚点日期变化时直接重新加载数据，不做未保存提醒（YAGNI）。
  - 数据回顾区（只读展示，`GET /data-summary` 驱动）：三栏卡片布局（参照原型 grid）——任务完成情况（总体+分类+象限）、习惯打卡情况列表、计划进展列表。
  - 引导式反思区：七个卡片，每个含固定引导语（前端硬编码，抄原型七步的标题+guidance 文案）+ `n-input type="textarea"`，`v-model` 分别绑定 `answers.step1`~`answers.step7`。
  - 生成改进计划区：`+ 添加新计划/目标...` 按钮打开 `GoalFormModal`（三期已有组件，直接复用，不做 `review_id` 关联）；保存成功后 push 进本地数组 `sessionCreatedGoals`，渲染在这个区块下方；刷新页面清空（纯前端会话状态）。
  - 底部两个按钮：`保存草稿`（`status=draft`）、`完成本次回顾`（`status=completed`），均调 `POST /review/save`。
  - "查看历史回顾"入口：按钮打开 `n-modal`，内容为 `GET /review/list` 驱动的简单列表；点击某条历史记录，关闭弹窗并将本页面的周期类型/锚点日期设为该记录对应值，重新加载。
- 页面加载时序：确定 `period_type`+`anchor_date` 后并行调用 `GET /data-summary`（数据回顾区）+ `GET /review/detail`（404 则七步区域全空、按钮态视为"新建"；存在则回填 `answers`/`status`）。

`web/src/api/review.js` 新增 `getDataSummary`、`getReviewDetail`、`saveReview`、`getReviewList`。Menu 新增"回顾总结"子菜单，`component: "/todo/Review"`。

## 已知边缘情况

- **月/季/年周期的弹性习惯配额是估算值**：按完整自然周数 × `weekly_count` 计算，首尾不满一周的部分按比例忽略，不追求绝对精确，仅用于回顾展示，不影响习惯页本身的统计逻辑。
- **同周期重复打开走 get_or_create**：`POST /review/save` 内部 `get_or_create` + `update`，`unique_together` 兜底并发创建冲突（个人应用场景基本不会真并发，但沿用防御写法）。
- **数据回顾统计口径与现有统计接口对齐**：排除 `habit_id` 非空的习惯生成待办，与三期已建立的口径一致，不引入新例外规则。
- **性能优化范围限定**：`get_statistics_by_date` 优化只改内部查询实现，不改函数签名/返回结构，`TodoHistory` 页面行为不受影响。
- **多 worktree 共用同一物理数据库的教训**：本阶段若新开 worktree 做开发，测试阶段应通过环境变量将数据库指向独立的测试库（或临时改用 SQLite），避免与其他 worktree/主仓库共享同一个 MySQL 库导致迁移状态漂移；完成后再在主仓库 `feat-task` 上与现有共享库对齐一次。

## 验收标准

- "待办事项"菜单下新增"回顾总结"入口。
- 默认打开本周回顾，能看到数据回顾三个区块（任务完成情况含总体/分类/象限、习惯打卡列表、计划进展列表）与实际数据吻合。
- 切换周期类型为月/季/年，锚点日期变化，数据回顾区相应刷新。
- 填写七步反思任意几步后点"保存草稿"，刷新页面重新进入同一周期，草稿内容能回填。
- 点"完成本次回顾"后状态变为已完成；"查看历史回顾"列表能看到这条记录。
- 点"添加新计划/目标"能打开计划创建弹窗并成功创建，创建后的计划出现在本次回顾页面的"新建计划"列表里（仅当前会话有效，刷新页面消失）。
- `get_statistics_by_date` 优化后，`TodoHistory` 页面数据与优化前一致（无行为回归）。
