# 待办事项模块视觉优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把待办事项模块 8 个页面（今日概览、四象限待办、待办统计、任务列表、日历、习惯、计划、回顾总结）从"Naive UI 默认组件堆叠"升级为"清新现代、有精致细节"的统一视觉语言，纯前端视觉层改动（唯一例外：今日概览完成度圆环需要后端追加两个只读汇总字段）。

**Architecture:** 先搭共享基础设施（CSS 设计 token、暗色模式适配、共享空状态组件），再落地已有 mockup 精确指导的今日概览页，最后按spec 里定的优先级逐页做视觉打磨。每个页面的改动严格限定在"视觉"范畴——不改查询逻辑、不改交互行为、不改路由。

**Tech Stack:** Vue 3 `<script setup>` + Naive UI（前端），FastAPI + Tortoise ORM（后端，仅 Task 3 涉及）。

## Global Constraints

- 本分支从 `feat-task`（已含一至四期全部内容）fork。
- **只做视觉改动**：配色、圆角、阴影、图标、空状态、间距、hover/过渡效果。不改变任何业务逻辑、数据结构、路由；唯一的后端改动是 Task 3（今日概览完成度圆环需要的两个只读汇总字段）。
- **Naive UI 组件视觉覆盖一律走页面级 `<style scoped>` 的 `:deep()` 选择器，绝不写进 `web/settings/theme.json` 的全局 `naiveThemeOverrides`**——后者通过应用里唯一的一个 `<n-config-provider>` 全局生效，任何 `Card`/`Button` 组件级 override 都会连带影响系统管理模块（用户/角色/菜单/API/部门/审计日志），这是写计划阶段核实 Naive UI 源码后发现并已经改正的坑，实现时不要图省事又绕回全局 theme override 这条路。
- **日历页（`Schedule/WeekView.vue`/`DayView.vue`）严禁改动任何脚本逻辑**——只改 `<style scoped>` 里的数值（圆角、阴影、颜色引用改成 token 变量），拖拽/多选/时间轴计算/`toLocalIsoString` 等代码原样保留，一行不动。
- 四象限语义色的十六进制值（`#f5222d`/`#faad14`/`#1890ff`/`#909399`）本身**不改变**，只是把散落在各文件里的重复硬编码，在各自触碰到的地方替换成 `var(--dt-quadrant-*)` 引用；不属于本次改动范围的文件即使还有硬编码值也不用去改。**唯一例外**：`TodoHistory/index.vue` 的四象限分布饼图里，`urgent_important`/`urgent_not_important` 两个扇区用的是 `#d03050`/`#f0a020`——与同一文件里表格列渲染函数、其他三个页面用的 `#f5222d`/`#faad14` 不一致（历史遗留的复制粘贴漂移），Task 6 会把这两个扇区的颜色一并归一到规范值，这是本次改动里**唯一一处真正改变"四象限语义色"色值**（而非仅替换引用方式）的地方，目的是让"待办统计"页的饼图和同一页的表格、以及其余页面视觉上说同一种语言。**另有一处不受此约束的色值变化**：Task 10 把"计划"页进度条的填充色从硬编码的 `#1890ff`（在那个位置只是恰好复用了这个蓝色字面量，并不代表"重要不紧急"象限语义）改成了 `var(--dt-habit, #10b981)`（绿色，与"习惯"页的进度语义统一）——这不属于四象限语义色范畴，不受本条约束限制，但字面量恰好与 `important_not_urgent` 象限色相同，容易被误读，特此说明避免混淆。
- 不引入新的前端依赖，图标统一用项目已有的 `web/src/components/icon/TheIcon.vue`（`<TheIcon icon="material-symbols:xxx" :size="16" />`），这个组件内部走 `@iconify/vue` 的运行时图标渲染，和 Menu 记录的图标是完全一样的机制（已经在生产环境跑了四期，机制本身不是新东西）。
- 每个页面改动完，跑一遍该页面既有的手动交互（不需要全量回归，但涉及交互的页面——尤其日历——要点开验证拖拽/勾选没有被破坏）。

---

### Task 1: 设计 Token 基础设施

**Files:**
- Create: `web/src/styles/design-tokens.scss`
- Modify: `web/src/styles/global.scss`
- Modify: `web/src/components/common/AppProvider.vue`

**Interfaces:**
- Produces：一套 CSS 自定义属性（`--dt-radius-*`/`--dt-shadow-*`/`--dt-quadrant-*`/`--dt-schedule*`/`--dt-habit*`/`--dt-ink*`/`--dt-card-bg`/`--dt-page-bg`/`--dt-border`），后续每个页面任务直接引用这些变量名，不重新定义。`document.documentElement.dataset.theme` 会被同步为 `'dark'`/`'light'`，供 `[data-theme='dark']` 选择器使用。

- [ ] **Step 1: 写 `web/src/styles/design-tokens.scss`**

```scss
:root {
  // 圆角
  --dt-radius-sm: 10px;
  --dt-radius-md: 14px;
  --dt-radius-lg: 20px;

  // 阴影（浅色主题）
  --dt-shadow-sm: 0 1px 2px rgba(28, 25, 23, 0.04), 0 1px 1px rgba(28, 25, 23, 0.03);
  --dt-shadow-md: 0 4px 16px rgba(28, 25, 23, 0.06), 0 1px 4px rgba(28, 25, 23, 0.04);
  --dt-shadow-lg: 0 12px 32px rgba(28, 25, 23, 0.08), 0 2px 8px rgba(28, 25, 23, 0.04);

  // 四象限语义色——数值照抄现有代码里反复出现的十六进制，只是集中定义，不改变任何一个色值
  --dt-quadrant-urgent-important: #f5222d;
  --dt-quadrant-urgent-not-important: #faad14;
  --dt-quadrant-important-not-urgent: #1890ff;
  --dt-quadrant-not-urgent-not-important: #909399;

  // 板块辅助色（日程/习惯专属，四象限之外全新引入的语义色）
  --dt-schedule: #6366f1;
  --dt-schedule-soft: #eef2ff;
  --dt-habit: #10b981;
  --dt-habit-soft: #ecfdf5;

  // 中性色阶（浅色主题）
  --dt-ink: #1c1917;
  --dt-ink-muted: #78716c;
  --dt-ink-faint: #a8a29e;
  --dt-card-bg: #ffffff;
  --dt-page-bg: #faf9f7;
  --dt-border: #efece8;
}

[data-theme='dark'] {
  --dt-shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.24), 0 1px 1px rgba(0, 0, 0, 0.18);
  --dt-shadow-md: 0 4px 16px rgba(0, 0, 0, 0.32), 0 1px 4px rgba(0, 0, 0, 0.24);
  --dt-shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.4), 0 2px 8px rgba(0, 0, 0, 0.28);
  --dt-ink: #e7e5e4;
  --dt-ink-muted: #a8a29e;
  --dt-ink-faint: #6b6560;
  --dt-card-bg: #232120;
  --dt-page-bg: #1a1817;
  --dt-border: #322f2d;
  --dt-schedule-soft: #23264a;
  --dt-habit-soft: #0f2e24;
}
```

- [ ] **Step 2: 在 `web/src/styles/global.scss` 顶部引入**

找到（文件第一行）：

```scss
html,
body {
```

改成：

```scss
@import './design-tokens.scss';

html,
body {
```

- [ ] **Step 3: 修改 `web/src/components/common/AppProvider.vue`，同步暗色模式 attribute**

找到：

```js
import { defineComponent, h } from 'vue'
```

改成：

```js
import { defineComponent, h, watch } from 'vue'
```

找到：

```js
function setupCssVar() {
  const common = naiveThemeOverrides.common
  for (const key in common) {
    useCssVar(`--${kebabCase(key)}`, document.documentElement).value = common[key] || ''
    if (key === 'primaryColor') window.localStorage.setItem('__THEME_COLOR__', common[key] || '')
  }
}
```

改成：

```js
function setupCssVar() {
  const common = naiveThemeOverrides.common
  for (const key in common) {
    useCssVar(`--${kebabCase(key)}`, document.documentElement).value = common[key] || ''
    if (key === 'primaryColor') window.localStorage.setItem('__THEME_COLOR__', common[key] || '')
  }
}

// design-tokens.scss 里的 [data-theme='dark'] 选择器依赖这个 attribute，用来在暗色模式下
// 切换中性色阶/阴影透明度；immediate 确保首次渲染就同步，不用等用户手动切一次主题
function setupDesignTokenTheme() {
  watch(
    () => appStore.isDark,
    (isDark) => {
      document.documentElement.dataset.theme = isDark ? 'dark' : 'light'
    },
    { immediate: true }
  )
}
```

找到：

```js
const NaiveProviderContent = defineComponent({
  setup() {
    setupCssVar()
    setupNaiveTools()
  },
```

改成：

```js
const NaiveProviderContent = defineComponent({
  setup() {
    setupCssVar()
    setupNaiveTools()
    setupDesignTokenTheme()
  },
```

- [ ] **Step 4: lint 检查**

Run: `cd web && pnpm exec eslint src/components/common/AppProvider.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 5: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开，切换右上角的深色/浅色模式开关，用浏览器 devtools 确认 `<html>` 标签上的 `data-theme` attribute 正确跟着切换成 `dark`/`light`。

- [ ] **Step 6: 提交**

```bash
git add web/src/styles/design-tokens.scss web/src/styles/global.scss web/src/components/common/AppProvider.vue
git commit -m "feat(web): add design token infrastructure with dark mode support"
```

---

### Task 2: 共享空状态组件 `EmptyState.vue`

**Files:**
- Create: `web/src/components/common/EmptyState.vue`

**Interfaces:**
- Consumes：Task 1 的 design token（`--dt-radius-md`/`--dt-page-bg`/`--dt-border`/`--dt-ink-faint`）、已有的 `TheIcon.vue`。
- Produces：`<EmptyState icon="material-symbols:xxx" text="..." link-text="..." to="/todo/xxx" />`，Task 4/5 直接使用。

- [ ] **Step 1: 写 `web/src/components/common/EmptyState.vue`**

```vue
<template>
  <div class="empty-state">
    <div class="empty-state-icon"><TheIcon :icon="icon" :size="18" /></div>
    <div class="empty-state-text">{{ text }}</div>
    <n-button v-if="linkText && to" text type="primary" class="empty-state-link" @click="router.push(to)">
      {{ linkText }}
      <template #icon><TheIcon icon="material-symbols:arrow-forward" :size="12" /></template>
    </n-button>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import TheIcon from '@/components/icon/TheIcon.vue'

defineProps({
  icon: { type: String, required: true },
  text: { type: String, required: true },
  linkText: { type: String, default: '' },
  to: { type: String, default: '' }
})

const router = useRouter()
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 28px 10px 14px;
  color: var(--dt-ink-faint);
}
.empty-state-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--dt-radius-md);
  background: var(--dt-page-bg);
  border: 1px dashed var(--dt-border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dt-ink-faint);
  margin-bottom: 10px;
}
.empty-state-text {
  font-size: 12.5px;
  margin-bottom: 10px;
}
.empty-state-link {
  font-size: 12px;
}
</style>
```

- [ ] **Step 2: lint 检查**

Run: `cd web && pnpm exec eslint src/components/common/EmptyState.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 提交**

```bash
git add web/src/components/common/EmptyState.vue
git commit -m "feat(web): add shared EmptyState component"
```

---

### Task 3: 后端——今日概览完成度统计字段

**Files:**
- Modify: `app/schemas/dashboard.py`
- Modify: `app/controllers/dashboard.py`
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes：无新依赖，复用 `_get_today_tasks` 已有的 due-today-or-scheduled-today 判定口径。
- Produces：`TodayOverviewOut` 新增 `completed_task_count`/`total_task_count` 两个只读字段，Task 4 的今日概览完成度圆环直接消费。

- [ ] **Step 1: 修改 `app/schemas/dashboard.py`**

找到：

```python
class TodayOverviewOut(BaseModel):
    date: date
    schedule: List[TimeBlockOut] = Field(default_factory=list)
    tasks: List[TodayTaskItem] = Field(default_factory=list)
    habits: List[TodayHabitItem] = Field(default_factory=list)
```

改成：

```python
class TodayOverviewOut(BaseModel):
    date: date
    schedule: List[TimeBlockOut] = Field(default_factory=list)
    tasks: List[TodayTaskItem] = Field(default_factory=list)
    habits: List[TodayHabitItem] = Field(default_factory=list)
    completed_task_count: int = Field(0, description="今日待办已完成数（含已完成，用于完成度统计）")
    total_task_count: int = Field(0, description="今日待办总数（含已完成，与 completed_task_count 同口径）")
```

- [ ] **Step 2: 修改 `app/controllers/dashboard.py`**

找到：

```python
    async def get_today_overview(self, user_id: int) -> dict:
        today = date.today()
        return {
            "date": today,
            "schedule": await self._get_today_schedule(user_id, today),
            "tasks": await self._get_today_tasks(user_id, today),
            "habits": await self._get_today_habits(user_id),
        }
```

改成：

```python
    async def get_today_overview(self, user_id: int) -> dict:
        today = date.today()
        task_counts = await self._get_today_task_counts(user_id, today)
        return {
            "date": today,
            "schedule": await self._get_today_schedule(user_id, today),
            "tasks": await self._get_today_tasks(user_id, today),
            "habits": await self._get_today_habits(user_id),
            "completed_task_count": task_counts["completed_task_count"],
            "total_task_count": task_counts["total_task_count"],
        }
```

在 `_get_today_tasks` 方法定义结束之后（`_get_today_habits` 方法定义之前）追加一个新方法。找到：

```python
    async def _get_today_habits(self, user_id: int) -> List[Dict[str, Any]]:
```

改成：

```python
    async def _get_today_task_counts(self, user_id: int, today: date) -> Dict[str, int]:
        """今日待办完成度统计：口径与 _get_today_tasks 一致（due_date 今天或今天排了时间块，
        排除习惯生成的待办），但这里不过滤 is_completed——用于今日概览页顶部的完成度圆环。
        这里独立重新计算 due_today_ids/scheduled_today_ids 的并集，没有复用 _get_today_tasks
        内部已经算过的同一份并集（那个方法只返回过滤后的 List[TodoItem]，没有把并集暴露出来）——
        对个人应用的数据量级，多跑两次这个量级的查询可以忽略不计，不值得为了省这几次查询去改动
        _get_today_tasks 已经过测试验证的返回契约"""
        day_start = datetime.combine(today, time.min)
        day_end = datetime.combine(today, time.max)

        due_today_ids = await TodoItem.filter(
            user_id=user_id,
            habit_id__isnull=True,
            due_date__gte=day_start,
            due_date__lte=day_end,
        ).values_list("id", flat=True)

        scheduled_today_ids = await TimeBlock.filter(
            user_id=user_id, start_time__gte=day_start, start_time__lte=day_end
        ).values_list("todo_item_id", flat=True)

        combined_ids = set(due_today_ids) | set(scheduled_today_ids)
        if not combined_ids:
            return {"completed_task_count": 0, "total_task_count": 0}

        total = await TodoItem.filter(id__in=combined_ids, user_id=user_id, habit_id__isnull=True).count()
        completed = await TodoItem.filter(
            id__in=combined_ids, user_id=user_id, habit_id__isnull=True, is_completed=True
        ).count()
        return {"completed_task_count": completed, "total_task_count": total}

    async def _get_today_habits(self, user_id: int) -> List[Dict[str, Any]]:
```

- [ ] **Step 3: 追加测试到 `tests/test_dashboard.py`**

找到文件末尾的最后一个测试函数（`test_today_overview_isolated_per_user_via_time_block`，在文件最后），在其后追加：

```python
async def test_today_overview_task_counts_include_completed_and_incomplete(client, test_user):
    today = date.today()
    await TodoItem.create(
        title="已完成的今日任务",
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
        due_date=datetime.combine(today, time(18, 0)),
        is_completed=True,
    )
    await TodoItem.create(
        title="未完成的今日任务",
        user_id=test_user.id,
        quadrant_type=QuadrantType.URGENT_IMPORTANT,
        due_date=datetime.combine(today, time(9, 0)),
    )

    resp = await client.get("/api/v1/dashboard/today")
    data = resp.json()["data"]
    assert data["total_task_count"] == 2
    assert data["completed_task_count"] == 1


async def test_today_overview_task_counts_zero_when_no_tasks(client, test_user):
    resp = await client.get("/api/v1/dashboard/today")
    data = resp.json()["data"]
    assert data["total_task_count"] == 0
    assert data["completed_task_count"] == 0


async def test_today_overview_task_counts_exclude_habit_generated(client, test_user):
    habit = await Habit.create(user_id=test_user.id, name="打卡", frequency_type=HabitFrequencyType.DAILY)
    today = date.today()
    await TodoItem.create(
        title="习惯待办",
        user_id=test_user.id,
        habit_id=habit.id,
        quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT,
        due_date=datetime.combine(today, time(18, 0)),
        generated_date=today,
        is_completed=True,
    )

    resp = await client.get("/api/v1/dashboard/today")
    data = resp.json()["data"]
    assert data["total_task_count"] == 0
    assert data["completed_task_count"] == 0


async def test_today_overview_task_counts_include_scheduled_today_without_due_date(client, test_user):
    todo = await TodoItem.create(
        title="只排了时间块", user_id=test_user.id, quadrant_type=QuadrantType.IMPORTANT_NOT_URGENT
    )
    today = date.today()
    await TimeBlock.create(
        todo_item_id=todo.id,
        user_id=test_user.id,
        start_time=datetime.combine(today, time(8, 0)),
        end_time=datetime.combine(today, time(9, 0)),
    )

    resp = await client.get("/api/v1/dashboard/today")
    data = resp.json()["data"]
    assert data["total_task_count"] == 1
    assert data["completed_task_count"] == 0
```

- [ ] **Step 4: 运行测试**

Run: `source .venv/bin/activate && make test`
Expected: 全部通过，135 passed（131 + 本任务新增 4 个）。

- [ ] **Step 5: 提交**

```bash
git add app/schemas/dashboard.py app/controllers/dashboard.py tests/test_dashboard.py
git commit -m "feat: add completed/total task count fields to today-overview endpoint"
```

---

### Task 4: 今日概览页视觉重做

**Files:**
- Modify: `web/src/views/todo/Dashboard/index.vue`

**Interfaces:**
- Consumes：Task 1 的设计 token、Task 2 的 `EmptyState.vue`、Task 3 的 `completed_task_count`/`total_task_count`。
- Produces：无新对外接口，本任务是 mockup 方向在真实页面上的落地。

这是本次视觉优化里改动最大的一个页面——已经通过静态 HTML mockup 和用户确认过方向，直接对照 mockup 落地，但图标改用项目已有的 `TheIcon` + Material Symbols（不是 mockup 里演示用的 Font Awesome），空状态改用 `EmptyState.vue`。

- [ ] **Step 1: 用下面的完整内容替换 `web/src/views/todo/Dashboard/index.vue`**

```vue
<template>
  <div class="dashboard-page">
    <div class="dashboard-header">
      <div>
        <div class="greeting-eyebrow">{{ dateEyebrow }}</div>
        <div class="greeting-title"><span class="wave">👋</span> {{ greetingText }}</div>
        <div class="greeting-sub">{{ summarySubtitle }}</div>
      </div>
      <div v-if="totalTaskCount > 0" class="progress-hero">
        <div class="progress-ring">
          <svg width="52" height="52" viewBox="0 0 52 52">
            <circle class="ring-bg" cx="26" cy="26" r="22" />
            <circle
              class="ring-fg"
              cx="26"
              cy="26"
              r="22"
              :stroke-dasharray="ringCircumference"
              :stroke-dashoffset="ringOffset"
            />
          </svg>
          <div class="ring-label">{{ completionPercent }}%</div>
        </div>
        <div class="progress-copy">
          <div class="num">{{ completedTaskCount }} / {{ totalTaskCount }}</div>
          <div class="label">今日完成</div>
        </div>
      </div>
    </div>

    <section class="quick-add">
      <TheIcon icon="material-symbols:auto-awesome-outline" :size="14" class="quick-add-icon" />
      <n-input
        v-model:value="quickAddTitle"
        placeholder="随手记一件事，回车加入收件箱…"
        @keyup.enter="handleQuickAdd"
      />
      <n-button type="primary" round @click="handleQuickAdd">
        <template #icon><TheIcon icon="material-symbols:add" :size="14" /></template>
        添加
      </n-button>
    </section>

    <div class="dashboard-grid">
      <section class="dashboard-card">
        <div class="card-head">
          <div class="card-head-left">
            <div class="card-icon-badge schedule"><TheIcon icon="material-symbols:schedule-outline" :size="15" /></div>
            <h3>今日日程</h3>
          </div>
          <span v-if="schedule.length" class="card-count">{{ schedule.length }} 项</span>
        </div>
        <div
          v-for="block in schedule"
          :key="block.id"
          class="schedule-row"
          @click="openDetail(block.todo_item_id)"
        >
          <span class="schedule-time">{{ formatTimeRange(block.start_time, block.end_time) }}</span>
          <span class="schedule-title">{{ block.title }}</span>
        </div>
        <EmptyState
          v-if="!schedule.length"
          icon="material-symbols:calendar-month-outline"
          text="今天还没有安排"
          link-text="查看完整日历"
          to="/todo/schedule"
        />
      </section>

      <section class="dashboard-card">
        <div class="card-head">
          <div class="card-head-left">
            <div class="card-icon-badge tasks"><TheIcon icon="material-symbols:check-circle-outline" :size="15" /></div>
            <h3>今日待办</h3>
          </div>
          <span v-if="tasks.length" class="card-count">{{ tasks.length }} 项</span>
        </div>
        <div v-for="task in tasks" :key="task.id" class="task-row">
          <n-checkbox :checked="false" @update:checked="() => toggleTaskComplete(task)" />
          <span class="quadrant-bar" :style="{ background: quadrantColor(task.quadrant_type) }"></span>
          <span class="task-title" @click="openDetail(task.id)">{{ task.title }}</span>
        </div>
        <EmptyState
          v-if="!tasks.length"
          icon="material-symbols:sentiment-satisfied-outline"
          text="今天的待办都清空啦"
          link-text="查看所有任务"
          to="/todo/tasks"
        />
      </section>

      <section class="dashboard-card">
        <div class="card-head">
          <div class="card-head-left">
            <div class="card-icon-badge habits"><TheIcon icon="material-symbols:sync" :size="15" /></div>
            <h3>今日习惯</h3>
          </div>
          <span v-if="habits.length" class="card-count">{{ habits.length }} 项</span>
        </div>
        <div v-for="habit in habits" :key="habit.id" class="habit-row">
          <div class="habit-left">
            <div class="habit-emoji">{{ habit.icon || '⭐' }}</div>
            <div>
              <div class="habit-name">{{ habit.name }}</div>
              <div class="habit-streak">
                <TheIcon
                  v-if="habit.streak !== null && habit.streak !== undefined"
                  icon="material-symbols:local-fire-department-outline"
                  :size="11"
                  class="streak-icon"
                />
                {{ habitMetaLabel(habit) }}
              </div>
            </div>
          </div>
          <n-button
            size="small"
            round
            :type="habit.today_completed ? 'default' : 'primary'"
            :disabled="habit.today_completed"
            class="habit-btn"
            :class="{ done: habit.today_completed }"
            @click="checkInHabit(habit)"
          >
            {{ habit.today_completed ? '已打卡 ✓' : '打卡' }}
          </n-button>
        </div>
        <EmptyState
          v-if="!habits.length"
          icon="material-symbols:eco-outline"
          text="今天没有需要打卡的习惯"
          link-text="管理习惯"
          to="/todo/habit"
        />
      </section>
    </div>

    <TaskDetailModal
      v-model:show="detailShow"
      :todo-id="detailTodoId"
      :projects="projectList"
      @saved="loadToday"
      @deleted="loadToday"
    />
  </div>
</template>

<script setup>
import { ref, computed, onActivated, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import api from '@/api'
import TaskDetailModal from '../TaskList/TaskDetailModal.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import EmptyState from '@/components/common/EmptyState.vue'

defineOptions({ name: '今日' })

const router = useRouter()
const message = useMessage()

const schedule = ref([])
const tasks = ref([])
const habits = ref([])
const completedTaskCount = ref(0)
const totalTaskCount = ref(0)
const quickAddTitle = ref('')
const detailShow = ref(false)
const detailTodoId = ref(null)
const projectList = ref([])

const quadrantMeta = {
  urgent_important: '#f5222d',
  urgent_not_important: '#faad14',
  important_not_urgent: '#1890ff',
  not_urgent_not_important: '#909399'
}
const quadrantColor = (type) => quadrantMeta[type] || '#909399'

const dateEyebrow = computed(() => {
  const now = new Date()
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  return `${weekdays[now.getDay()]} · ${now.getMonth() + 1}月${now.getDate()}日`
})

const greetingText = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了，注意休息'
  if (hour < 12) return '早上好，欢迎回来'
  if (hour < 18) return '下午好，欢迎回来'
  return '晚上好，欢迎回来'
})

const summarySubtitle = computed(() => {
  const pendingHabits = habits.value.filter((h) => !h.today_completed).length
  return `今天有 ${tasks.value.length} 件事等着你，${pendingHabits} 个习惯待打卡`
})

const completionPercent = computed(() =>
  totalTaskCount.value ? Math.round((completedTaskCount.value / totalTaskCount.value) * 100) : 0
)
const ringCircumference = 2 * Math.PI * 22
const ringOffset = computed(() => ringCircumference * (1 - completionPercent.value / 100))

const formatTimeRange = (start, end) => {
  const pad = (n) => String(n).padStart(2, '0')
  const s = new Date(start)
  const e = new Date(end)
  return `${pad(s.getHours())}:${pad(s.getMinutes())}–${pad(e.getHours())}:${pad(e.getMinutes())}`
}

const frequencyLabel = (habit) => {
  const config = habit.frequency_config || {}
  if (habit.frequency_type === 'daily') return '每天'
  if (habit.frequency_type === 'weekly_days') {
    const names = ['一', '二', '三', '四', '五', '六', '日']
    return '每周' + (config.days || []).map((d) => names[d - 1]).join('')
  }
  if (habit.frequency_type === 'weekly_count') return `每周${config.count}次`
  if (habit.frequency_type === 'interval_days') return `每隔${config.interval}天`
  return ''
}

const habitMetaLabel = (habit) => {
  const parts = [frequencyLabel(habit)]
  if (habit.streak !== null && habit.streak !== undefined) parts.push(`连续 ${habit.streak} 天`)
  if (habit.week_progress) parts.push(`本周 ${habit.week_progress}`)
  return parts.join(' · ')
}

const loadToday = async () => {
  try {
    const res = await api.getTodayOverview()
    schedule.value = res.data.schedule || []
    tasks.value = res.data.tasks || []
    habits.value = res.data.habits || []
    completedTaskCount.value = res.data.completed_task_count || 0
    totalTaskCount.value = res.data.total_task_count || 0
  } catch (error) {
    console.error('加载今日概览失败:', error)
    message.error('加载今日概览失败')
  }
}

const fetchProjects = async () => {
  try {
    const res = await api.getProjects()
    projectList.value = res.data || []
  } catch (error) {
    console.error('获取项目列表失败:', error)
  }
}

const handleQuickAdd = async () => {
  const title = quickAddTitle.value.trim()
  if (!title) return
  try {
    await api.createTodo({ title, quadrant_type: 'not_urgent_not_important' })
    quickAddTitle.value = ''
    message.success('已添加')
    loadToday()
  } catch (error) {
    console.error('添加任务失败:', error)
    message.error('添加任务失败')
  }
}

const toggleTaskComplete = async (task) => {
  try {
    await api.updateTodo(task.id, { is_completed: true })
    tasks.value = tasks.value.filter((t) => t.id !== task.id)
    completedTaskCount.value += 1
  } catch (error) {
    console.error('更新任务状态失败:', error)
    message.error('更新任务状态失败')
  }
}

const checkInHabit = async (habit) => {
  try {
    await api.updateTodo(habit.today_todo_id, { is_completed: true })
    habit.today_completed = true
  } catch (error) {
    console.error('打卡失败:', error)
    message.error('打卡失败')
  }
}

const openDetail = (todoId) => {
  detailTodoId.value = todoId
  detailShow.value = true
}

// 关闭详情弹窗时也刷新今日概览，覆盖弹窗内的局部修改（如把截止日期改到别的日期、删除时间块）
// 未必会触发 @saved/@deleted 的情况，与 Schedule/index.vue 的既有写法一致
watch(detailShow, (visible) => {
  if (!visible) loadToday()
})

onActivated(() => {
  loadToday()
  fetchProjects()
})
</script>

<style scoped>
.dashboard-page {
  max-width: 1100px;
}
.dashboard-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 28px;
}
.greeting-eyebrow {
  font-size: 12.5px;
  color: var(--dt-ink-faint);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  margin-bottom: 6px;
}
.greeting-title {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  display: flex;
  align-items: center;
  gap: 10px;
}
.wave {
  display: inline-block;
  animation: wave 2.2s ease-in-out infinite;
  transform-origin: 70% 70%;
}
@keyframes wave {
  0%,
  60%,
  100% {
    transform: rotate(0deg);
  }
  10%,
  30% {
    transform: rotate(14deg);
  }
  20% {
    transform: rotate(-8deg);
  }
  40% {
    transform: rotate(10deg);
  }
}
.greeting-sub {
  color: var(--dt-ink-muted);
  font-size: 13.5px;
  margin-top: 4px;
}
.progress-hero {
  display: flex;
  align-items: center;
  gap: 14px;
  background: var(--dt-card-bg);
  border: 1px solid var(--dt-border);
  border-radius: var(--dt-radius-md);
  padding: 10px 18px 10px 12px;
  box-shadow: var(--dt-shadow-sm);
}
.progress-ring {
  position: relative;
  width: 52px;
  height: 52px;
}
.progress-ring svg {
  transform: rotate(-90deg);
}
.progress-ring .ring-bg {
  stroke: var(--dt-border);
  stroke-width: 5;
  fill: none;
}
.progress-ring .ring-fg {
  stroke: var(--primary-color, #f4511e);
  stroke-width: 5;
  fill: none;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.6s ease;
}
.progress-ring .ring-label {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: var(--primary-color, #f4511e);
}
.progress-copy .num {
  font-size: 15px;
  font-weight: 700;
}
.progress-copy .label {
  font-size: 12px;
  color: var(--dt-ink-muted);
}
.quick-add {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--dt-card-bg);
  border: 1px solid var(--dt-border);
  border-radius: 999px;
  padding: 6px 8px 6px 18px;
  box-shadow: var(--dt-shadow-sm);
  margin-bottom: 28px;
  transition:
    box-shadow 0.2s ease,
    border-color 0.2s ease;
}
.quick-add:focus-within {
  border-color: var(--primary-color, #f4511e);
}
.quick-add-icon {
  color: var(--primary-color, #f4511e);
  flex-shrink: 0;
}
.quick-add :deep(.n-input) {
  --n-border: none !important;
  --n-border-hover: none !important;
  --n-border-focus: none !important;
  --n-box-shadow-focus: none !important;
  background: transparent;
}
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
}
.dashboard-card {
  background: var(--dt-card-bg);
  border: 1px solid var(--dt-border);
  border-radius: var(--dt-radius-lg);
  padding: 22px 20px 18px;
  box-shadow: var(--dt-shadow-sm);
  transition:
    box-shadow 0.25s ease,
    transform 0.25s ease;
}
.dashboard-card:hover {
  box-shadow: var(--dt-shadow-md);
  transform: translateY(-2px);
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.card-head-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.card-head-left h3 {
  margin: 0;
  font-size: 14.5px;
  font-weight: 700;
  letter-spacing: -0.01em;
}
.card-icon-badge {
  width: 30px;
  height: 30px;
  border-radius: var(--dt-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
}
.card-icon-badge.schedule {
  background: var(--dt-schedule-soft);
  color: var(--dt-schedule);
}
.card-icon-badge.tasks {
  background: color-mix(in srgb, var(--primary-color, #f4511e) 12%, transparent);
  color: var(--primary-color, #f4511e);
}
.card-icon-badge.habits {
  background: var(--dt-habit-soft);
  color: var(--dt-habit);
}
.card-count {
  font-size: 11px;
  font-weight: 700;
  color: var(--dt-ink-faint);
  background: var(--dt-page-bg);
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--dt-border);
}
.schedule-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 6px;
  border-radius: var(--dt-radius-sm);
  cursor: pointer;
  transition: background 0.15s ease;
}
.schedule-row:hover {
  background: var(--dt-page-bg);
}
.schedule-time {
  font-size: 11.5px;
  font-weight: 700;
  color: var(--dt-schedule);
  background: var(--dt-schedule-soft);
  padding: 4px 8px;
  border-radius: 8px;
  white-space: nowrap;
}
.schedule-title {
  font-size: 13.5px;
  font-weight: 500;
}
.task-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 6px;
  border-radius: var(--dt-radius-sm);
  transition: background 0.15s ease;
}
.task-row:hover {
  background: var(--dt-page-bg);
}
.quadrant-bar {
  width: 3px;
  height: 20px;
  border-radius: 3px;
  flex-shrink: 0;
}
.task-title {
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
}
.habit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 6px;
  border-radius: var(--dt-radius-sm);
  transition: background 0.15s ease;
}
.habit-row:hover {
  background: var(--dt-page-bg);
}
.habit-left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.habit-emoji {
  width: 30px;
  height: 30px;
  border-radius: var(--dt-radius-sm);
  background: var(--dt-habit-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
}
.habit-name {
  font-size: 13.5px;
  font-weight: 600;
}
.habit-streak {
  font-size: 11px;
  color: var(--dt-ink-muted);
  display: flex;
  align-items: center;
  gap: 3px;
  margin-top: 1px;
}
.streak-icon {
  color: #f59e0b;
}
.habit-btn.done {
  background: var(--dt-habit-soft);
  color: var(--dt-habit);
}
</style>
```

- [ ] **Step 2: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/Dashboard/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开今日概览页，对照 mockup 检查：问候语随时间段变化、完成度圆环数字与今日待办数量一致、三卡片图标徽标颜色正确、习惯打卡后按钮态切换、快速添加正常创建任务、空状态文案和跳转链接正常工作、深色模式下卡片/文字对比度可读。

- [ ] **Step 4: 提交**

```bash
git add web/src/views/todo/Dashboard/index.vue
git commit -m "feat(web): redesign today overview page per approved mockup"
```

---

### Task 5: 四象限待办视觉打磨

**Files:**
- Modify: `web/src/views/todo/TodoQuadrant/index.vue`

**Interfaces:**
- Consumes：Task 1 的设计 token、Task 2 的 `EmptyState.vue`。
- Produces：无新对外接口。

**只改 `<template>` 里四个 `n-card` 的 `#header-extra` 前追加图标徽标、`n-empty` 换成 `EmptyState`，以及 `<style>` 块——不改 `<script setup>` 里的任何逻辑（拖拽/表单提交等）。**

- [ ] **Step 1: 四个象限卡片标题栏加图标徽标**

找到（第一个象限，重复相同模式共 4 处，象限名/图标/CSS 类名按下表对应）：

```html
        <n-card title="重要且紧急" class="quadrant-card urgent-important">
          <template #header-extra>
            <n-button type="error" @click="handleAddTodo(1)">添加</n-button>
          </template>
```

改成：

```html
        <n-card title="重要且紧急" class="quadrant-card urgent-important">
          <template #header>
            <span class="quadrant-card-title">
              <span class="quadrant-icon-badge urgent-important"><TheIcon icon="material-symbols:priority-high" :size="13" /></span>
              重要且紧急
            </span>
          </template>
          <template #header-extra>
            <n-button type="error" @click="handleAddTodo(1)">添加</n-button>
          </template>
```

对其余三个象限做同样的改法（`#header-extra` 前插入一个 `#header` slot），象限名/图标名/CSS 类名对应关系：

| 原 `title` | 图标 class | 图标 | `handleAddTodo` 参数 |
|---|---|---|---|
| 紧急不重要 | `urgent-not-important` | `material-symbols:bolt-outline` | 2 |
| 重要不紧急 | `important-not-urgent` | `material-symbols:flag-outline` | 3 |
| 不紧急不重要 | `not-urgent-not-important` | `material-symbols:coffee-outline` | 4 |

即找到：

```html
        <n-card title="紧急不重要" class="quadrant-card urgent-not-important">
          <template #header-extra>
            <n-button type="warning" @click="handleAddTodo(2)">添加</n-button>
          </template>
```

改成：

```html
        <n-card title="紧急不重要" class="quadrant-card urgent-not-important">
          <template #header>
            <span class="quadrant-card-title">
              <span class="quadrant-icon-badge urgent-not-important"><TheIcon icon="material-symbols:bolt-outline" :size="13" /></span>
              紧急不重要
            </span>
          </template>
          <template #header-extra>
            <n-button type="warning" @click="handleAddTodo(2)">添加</n-button>
          </template>
```

找到：

```html
        <n-card title="重要不紧急" class="quadrant-card important-not-urgent">
          <template #header-extra>
            <n-button class="btn-blue" @click="handleAddTodo(3)">添加</n-button>
          </template>
```

改成：

```html
        <n-card title="重要不紧急" class="quadrant-card important-not-urgent">
          <template #header>
            <span class="quadrant-card-title">
              <span class="quadrant-icon-badge important-not-urgent"><TheIcon icon="material-symbols:flag-outline" :size="13" /></span>
              重要不紧急
            </span>
          </template>
          <template #header-extra>
            <n-button class="btn-blue" @click="handleAddTodo(3)">添加</n-button>
          </template>
```

找到：

```html
        <n-card title="不紧急不重要" class="quadrant-card not-urgent-not-important">
          <template #header-extra>
            <n-button class="btn-gray" @click="handleAddTodo(4)">添加</n-button>
          </template>
```

改成：

```html
        <n-card title="不紧急不重要" class="quadrant-card not-urgent-not-important">
          <template #header>
            <span class="quadrant-card-title">
              <span class="quadrant-icon-badge not-urgent-not-important"><TheIcon icon="material-symbols:coffee-outline" :size="13" /></span>
              不紧急不重要
            </span>
          </template>
          <template #header-extra>
            <n-button class="btn-gray" @click="handleAddTodo(4)">添加</n-button>
          </template>
```

- [ ] **Step 2: 四个空状态换成 `EmptyState`**

找到（4 处，`todoListN.length === 0` 里 N 分别是 1/2/3/4，`description` 文案统一）：

```html
            <n-empty v-if="todoList1.length === 0" description="暂无待办事项" />
```

改成：

```html
            <EmptyState v-if="todoList1.length === 0" icon="material-symbols:inbox-outline" text="这个象限暂无待办事项" />
```

其余三处同理，把 `todoList1`/`v-if` 里的数字换成 `2`/`3`/`4`：

```html
            <EmptyState v-if="todoList2.length === 0" icon="material-symbols:inbox-outline" text="这个象限暂无待办事项" />
```

```html
            <EmptyState v-if="todoList3.length === 0" icon="material-symbols:inbox-outline" text="这个象限暂无待办事项" />
```

```html
            <EmptyState v-if="todoList4.length === 0" icon="material-symbols:inbox-outline" text="这个象限暂无待办事项" />
```

- [ ] **Step 3: 引入 `TheIcon`/`EmptyState`**

找到：

```js
import { ref, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import todoApi from '@/api/todo'
```

改成：

```js
import { ref, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import todoApi from '@/api/todo'
import TheIcon from '@/components/icon/TheIcon.vue'
import EmptyState from '@/components/common/EmptyState.vue'
```

- [ ] **Step 4: 追加/调整样式**

找到：

```css
.todo-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: #f9f9f9;
  border-radius: 4px;
  transition: all 0.3s ease;
}

.todo-item:hover {
  background: #f0f0f0;
}
```

改成：

```css
.todo-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: var(--dt-page-bg, #f9f9f9);
  border-radius: var(--dt-radius-sm, 4px);
  transition: all 0.2s ease;
}

.todo-item:hover {
  background: var(--dt-border, #f0f0f0);
  transform: translateY(-1px);
  box-shadow: var(--dt-shadow-sm);
}

.quadrant-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.quadrant-icon-badge {
  width: 22px;
  height: 22px;
  border-radius: var(--dt-radius-sm, 8px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}
.quadrant-icon-badge.urgent-important {
  background: var(--dt-quadrant-urgent-important, #f5222d);
}
.quadrant-icon-badge.urgent-not-important {
  background: var(--dt-quadrant-urgent-not-important, #faad14);
}
.quadrant-icon-badge.important-not-urgent {
  background: var(--dt-quadrant-important-not-urgent, #1890ff);
}
.quadrant-icon-badge.not-urgent-not-important {
  background: var(--dt-quadrant-not-urgent-not-important, #909399);
}
```

找到（四个象限色边框，改用 token 变量，值不变）：

```css
.urgent-important .n-card__content {
  border-top: 4px solid #f5222d;
}

.urgent-not-important .n-card__content {
  border-top: 4px solid #faad14;
}

.important-not-urgent .n-card__content {
  border-top: 4px solid #1890ff;
}

.not-urgent-not-important .n-card__content {
  border-top: 4px solid #909399;
}
```

改成：

```css
.urgent-important .n-card__content {
  border-top: 4px solid var(--dt-quadrant-urgent-important, #f5222d);
}

.urgent-not-important .n-card__content {
  border-top: 4px solid var(--dt-quadrant-urgent-not-important, #faad14);
}

.important-not-urgent .n-card__content {
  border-top: 4px solid var(--dt-quadrant-important-not-urgent, #1890ff);
}

.not-urgent-not-important .n-card__content {
  border-top: 4px solid var(--dt-quadrant-not-urgent-not-important, #909399);
}

.quadrant-card {
  border-radius: var(--dt-radius-lg);
  overflow: hidden;
  box-shadow: var(--dt-shadow-sm);
}
```

- [ ] **Step 5: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/TodoQuadrant/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 6: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开四象限待办页，确认：四个卡片标题栏图标徽标颜色对应象限、拖拽待办在象限之间移动仍正常工作（这是本页面唯一的复杂交互，必须验证没有被破坏）、添加/编辑/删除待办的弹窗流程正常、空象限显示新的空状态组件。

- [ ] **Step 7: 提交**

```bash
git add web/src/views/todo/TodoQuadrant/index.vue
git commit -m "feat(web): polish TodoQuadrant visuals with design tokens"
```

---

### Task 6: 待办统计视觉打磨

**Files:**
- Modify: `web/src/views/todo/TodoHistory/index.vue`

**Interfaces:**
- Consumes：Task 1 的设计 token（四象限色变量的十六进制值，图表走 canvas 渲染不能直接用 CSS 变量，改用 JS 常量集中定义）。
- Produces：无新对外接口。

**这个页面本身已经是卡片布局（`rounded-10` 的 `n-card`），改动范围小：图表配色改用集中定义的常量、不再散落在多处字面量里；不改任何数据获取/图表初始化逻辑。**

- [ ] **Step 1: 集中定义象限色常量，替换图表里的散落字面量**

找到：

```js
// 表格列定义
const columns = ref([
  {
    title: '标题',
    key: 'title',
    sorter: true
  },
  {
    title: '象限',
    key: 'quadrant_type',
    render(row) {
      const typeMap = {
        urgent_important: { text: '重要且紧急', color: '#f5222d' },
        urgent_not_important: { text: '紧急不重要', color: '#faad14' },
        important_not_urgent: { text: '重要不紧急', color: '#1890ff' },
        not_urgent_not_important: { text: '不紧急不重要', color: '#909399' }
      };
      const config = typeMap[row.quadrant_type] || { text: row.quadrant_type, color: '#909399' };
```

改成：

```js
// 象限色沿用 design-tokens.scss 里 --dt-quadrant-* 的同一组数值——图表走 echarts canvas 渲染，
// 拿不到 CSS 自定义属性，这里用 JS 常量集中定义一份，和 CSS token 保持同源但各自维护，
// 与本仓库"小型格式化/配置各文件自己写一份"的既定做法一致
const QUADRANT_COLOR = {
  urgent_important: '#f5222d',
  urgent_not_important: '#faad14',
  important_not_urgent: '#1890ff',
  not_urgent_not_important: '#909399'
}

// 表格列定义
const columns = ref([
  {
    title: '标题',
    key: 'title',
    sorter: true
  },
  {
    title: '象限',
    key: 'quadrant_type',
    render(row) {
      const typeMap = {
        urgent_important: { text: '重要且紧急', color: QUADRANT_COLOR.urgent_important },
        urgent_not_important: { text: '紧急不重要', color: QUADRANT_COLOR.urgent_not_important },
        important_not_urgent: { text: '重要不紧急', color: QUADRANT_COLOR.important_not_urgent },
        not_urgent_not_important: { text: '不紧急不重要', color: QUADRANT_COLOR.not_urgent_not_important }
      };
      const config = typeMap[row.quadrant_type] || { text: row.quadrant_type, color: '#909399' };
```

找到：

```js
        data: [
          { value: data.urgent_important || 0, name: '重要且紧急', itemStyle: { color: '#d03050' } },
          { value: data.urgent_not_important || 0, name: '紧急不重要', itemStyle: { color: '#f0a020' } },
          { value: data.important_not_urgent || 0, name: '重要不紧急', itemStyle: { color: '#1890ff' } },
          { value: data.not_urgent_not_important || 0, name: '不紧急不重要', itemStyle: { color: '#909399' } }
        ],
```

改成：

```js
        data: [
          { value: data.urgent_important || 0, name: '重要且紧急', itemStyle: { color: QUADRANT_COLOR.urgent_important } },
          { value: data.urgent_not_important || 0, name: '紧急不重要', itemStyle: { color: QUADRANT_COLOR.urgent_not_important } },
          { value: data.important_not_urgent || 0, name: '重要不紧急', itemStyle: { color: QUADRANT_COLOR.important_not_urgent } },
          { value: data.not_urgent_not_important || 0, name: '不紧急不重要', itemStyle: { color: QUADRANT_COLOR.not_urgent_not_important } }
        ],
```

找到：

```js
const getQuadrantTypeConfig = (type) => {
  const typeMap = {
    urgent_important: { text: '重要且紧急', color: '#f5222d' },
    urgent_not_important: { text: '紧急不重要', color: '#faad14' },
    important_not_urgent: { text: '重要不紧急', color: '#1890ff' },
    not_urgent_not_important: { text: '不紧急不重要', color: '#909399' }
  };
  return typeMap[type] || { text: type || '未知', color: '#909399' };
}
```

改成：

```js
const getQuadrantTypeConfig = (type) => {
  const typeMap = {
    urgent_important: { text: '重要且紧急', color: QUADRANT_COLOR.urgent_important },
    urgent_not_important: { text: '紧急不重要', color: QUADRANT_COLOR.urgent_not_important },
    important_not_urgent: { text: '重要不紧急', color: QUADRANT_COLOR.important_not_urgent },
    not_urgent_not_important: { text: '不紧急不重要', color: QUADRANT_COLOR.not_urgent_not_important }
  };
  return typeMap[type] || { text: type || '未知', color: '#909399' };
}
```

- [ ] **Step 2: 完成待办数量柱状图颜色也对齐 token（沿用现有的绿色系完成语义，只是走常量不再是字面量）**

找到：

```js
    series: [
      {
        name: '完成数量',
        type: 'bar',
        data: completedCounts,
        itemStyle: {
          color: '#18a058'
        }
      }
    ]
```

改成：

```js
    series: [
      {
        name: '完成数量',
        type: 'bar',
        data: completedCounts,
        itemStyle: {
          color: '#10b981',
          borderRadius: [6, 6, 0, 0]
        }
      }
    ]
```

（`#10b981` 与 `design-tokens.scss` 里的 `--dt-habit` 同色，呼应"完成/达成"的语义色；`borderRadius` 是给柱状图顶部加一点圆角，纯视觉细节，不影响数据渲染逻辑。）

- [ ] **Step 3: 详情弹窗文字样式对齐 token**

找到：

```css
.detail-label {
  color: #555;
  font-size: 14px;
  font-weight: 500;
}

.detail-value {
  color: #333;
  font-size: 15px;
}
```

改成：

```css
.detail-label {
  color: var(--dt-ink-muted, #555);
  font-size: 14px;
  font-weight: 500;
}

.detail-value {
  color: var(--dt-ink, #333);
  font-size: 15px;
}
```

- [ ] **Step 4: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/TodoHistory/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 5: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开待办统计页，确认两个图表正常渲染、颜色与四象限页保持一致、日期筛选/分页/排序等既有交互不受影响、详情弹窗正常打开。

- [ ] **Step 6: 提交**

```bash
git add web/src/views/todo/TodoHistory/index.vue
git commit -m "feat(web): centralize quadrant colors in TodoHistory charts"
```

---

### Task 7: 任务列表视觉打磨

**Files:**
- Modify: `web/src/views/todo/TaskList/index.vue`

**Interfaces:**
- Consumes：Task 1 的设计 token。
- Produces：无新对外接口。

**只改快速添加框样式、任务行的圆点换色条、`<style scoped>` 块——不改 `<script setup>` 里任何数据获取/筛选/排序逻辑。**

- [ ] **Step 1: 任务行的圆点换成色条**

找到：

```html
                <span>
                  <span class="quadrant-dot" :style="{ background: quadrantColor(todo.quadrant_type) }"></span>
                  {{ quadrantLabel(todo.quadrant_type) }}
                </span>
```

改成：

```html
                <span>
                  <span class="quadrant-bar" :style="{ background: quadrantColor(todo.quadrant_type) }"></span>
                  {{ quadrantLabel(todo.quadrant_type) }}
                </span>
```

- [ ] **Step 2: 样式调整**

找到：

```css
.quick-add {
  display: flex;
  gap: 0.5em;
  margin-bottom: 1em;
}
```

改成：

```css
.quick-add {
  display: flex;
  align-items: center;
  gap: 0.5em;
  margin-bottom: 1.2em;
  background: var(--dt-card-bg, #fff);
  border: 1px solid var(--dt-border);
  border-radius: 999px;
  padding: 4px 6px 4px 16px;
  box-shadow: var(--dt-shadow-sm);
  transition: border-color 0.2s ease;
}
.quick-add:focus-within {
  border-color: var(--primary-color, #f4511e);
}
.quick-add :deep(.n-input) {
  --n-border: none !important;
  --n-border-hover: none !important;
  --n-border-focus: none !important;
  --n-box-shadow-focus: none !important;
  background: transparent;
}
.quick-add :deep(.n-button) {
  border-radius: 999px;
}
```

找到：

```css
.task-item {
  display: flex;
  align-items: center;
  gap: 0.6em;
  padding: 0.5em 0.2em;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
}
```

改成：

```css
.task-item {
  display: flex;
  align-items: center;
  gap: 0.6em;
  padding: 0.6em 0.5em;
  border-radius: var(--dt-radius-sm);
  transition: background 0.15s ease;
}
.task-item:hover {
  background: var(--dt-page-bg);
}
```

找到：

```css
.quadrant-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.3em;
}
```

改成：

```css
.quadrant-bar {
  display: inline-block;
  width: 3px;
  height: 11px;
  border-radius: 3px;
  margin-right: 0.4em;
  vertical-align: middle;
}
```

- [ ] **Step 3: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/TaskList/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 4: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开任务列表页，确认：快速添加框胶囊样式、focus 态边框变色、任务行 hover 有背景反馈、象限色条正确显示、项目导航/排序/筛选/勾选完成/打开详情弹窗等既有交互全部正常。

- [ ] **Step 5: 提交**

```bash
git add web/src/views/todo/TaskList/index.vue
git commit -m "feat(web): polish TaskList quick-add and task row visuals"
```

---

### Task 8: 日历视觉打磨（保守，只动样式）

**Files:**
- Modify: `web/src/views/todo/Schedule/WeekView.vue`
- Modify: `web/src/views/todo/Schedule/DayView.vue`

**Interfaces:**
- Consumes：Task 1 的设计 token。
- Produces：无新对外接口。

**这是全模块交互最复杂的页面（拖拽排程、多选、时间轴坐标计算）。本任务只改 `<style scoped>` 块里的数值，`<template>`/`<script setup>` 一行不动。**

- [ ] **Step 1: `WeekView.vue` 事件块与网格样式打磨**

找到：

```css
.event-block {
  position: absolute;
  left: 2px;
  right: 2px;
  border-radius: 4px;
  padding: 1px 4px;
  font-size: 0.76em;
  color: #fff;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  z-index: 2;
  box-sizing: border-box;
  cursor: pointer;
}
```

改成：

```css
.event-block {
  position: absolute;
  left: 2px;
  right: 2px;
  border-radius: var(--dt-radius-sm, 4px);
  padding: 1px 4px;
  font-size: 0.76em;
  color: #fff;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  z-index: 2;
  box-sizing: border-box;
  cursor: pointer;
  box-shadow: var(--dt-shadow-sm);
  transition: filter 0.15s ease;
}
.event-block:hover {
  filter: brightness(0.94);
}
```

找到：

```css
.now-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: #f5222d;
  z-index: 3;
  pointer-events: none;
}
```

改成：

```css
.now-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--dt-quadrant-urgent-important, #f5222d);
  z-index: 3;
  pointer-events: none;
  box-shadow: 0 0 4px rgba(245, 34, 45, 0.4);
}
```

找到：

```css
.day-col.today .day-head {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
}
```

改成：

```css
.day-col.today .day-head {
  background: var(--dt-schedule-soft);
  color: var(--dt-schedule);
  font-weight: 700;
}
```

- [ ] **Step 2: `DayView.vue` 事件块与网格样式打磨**

找到：

```css
.day-event {
  position: absolute;
  left: 56px;
  right: 10px;
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 0.85em;
  color: #fff;
  overflow: hidden;
  z-index: 2;
  box-sizing: border-box;
  cursor: pointer;
}
```

改成：

```css
.day-event {
  position: absolute;
  left: 56px;
  right: 10px;
  border-radius: var(--dt-radius-sm, 4px);
  padding: 2px 6px;
  font-size: 0.85em;
  color: #fff;
  overflow: hidden;
  z-index: 2;
  box-sizing: border-box;
  cursor: pointer;
  box-shadow: var(--dt-shadow-sm);
  transition: filter 0.15s ease;
}
.day-event:hover {
  filter: brightness(0.94);
}
```

找到：

```css
.now-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: #f5222d;
  z-index: 3;
  pointer-events: none;
}
```

改成：

```css
.now-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--dt-quadrant-urgent-important, #f5222d);
  z-index: 3;
  pointer-events: none;
  box-shadow: 0 0 4px rgba(245, 34, 45, 0.4);
}
```

找到：

```css
.hour-slot.drop-hint {
  background: rgba(24, 144, 255, 0.12);
}
```

改成：

```css
.hour-slot.drop-hint {
  background: var(--dt-schedule-soft);
}
```

找到：

```css
.unscheduled-item {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.5em 0.2em;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
  cursor: grab;
}
```

改成：

```css
.unscheduled-item {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.6em 0.5em;
  border-radius: var(--dt-radius-sm);
  cursor: grab;
  transition: background 0.15s ease;
}
.unscheduled-item:hover {
  background: var(--dt-page-bg);
}
```

- [ ] **Step 3: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/Schedule/WeekView.vue src/views/todo/Schedule/DayView.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 4: 手动验证（本任务里最重要的一步）**

Run: `cd web && pnpm dev`，浏览器打开日历页，**必须**验证以下二期已建立的交互一个不少地跑一遍：
- 周视图：拖拽选择时间段、多选格子模式、"完成选择"弹窗创建任务、切换周、切换粒度（15/30/60分钟）。
- 日视图：把"未安排的任务"拖到时间轴上创建时间块、切换日期、日期输入框直接跳转。
- 两个视图点击已有事件块都能打开任务详情弹窗。

Expected: 以上交互行为与改动前完全一致，只有视觉（圆角、阴影、hover 反馈）不同。

- [ ] **Step 5: 提交**

```bash
git add web/src/views/todo/Schedule/WeekView.vue web/src/views/todo/Schedule/DayView.vue
git commit -m "feat(web): polish Schedule calendar visuals without touching interaction logic"
```

---

### Task 9: 习惯页视觉打磨

**Files:**
- Modify: `web/src/views/todo/Habit/index.vue`

**Interfaces:**
- Consumes：Task 1 的设计 token。
- Produces：无新对外接口。

**只改 `<style scoped>` 块——不改 `<template>` 结构（沿用既有 emoji 图标展示、打卡按钮逻辑）和 `<script setup>` 任何逻辑。**

- [ ] **Step 1: 样式调整**

找到：

```css
.habit-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.8em 0.2em;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
}
```

改成：

```css
.habit-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.9em 1em;
  border-radius: var(--dt-radius-md);
  background: var(--dt-card-bg, transparent);
  border: 1px solid var(--dt-border);
  box-shadow: var(--dt-shadow-sm);
  margin-bottom: 0.6em;
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease;
}
.habit-item:hover {
  box-shadow: var(--dt-shadow-md);
  transform: translateY(-1px);
}
.habit-item.archived {
  border: none;
  box-shadow: none;
  padding: 0.6em 0.2em;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
  margin-bottom: 0;
}
```

找到：

```css
.habit-icon {
  margin-right: 0.4em;
}
```

改成：

```css
.habit-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  margin-right: 0.5em;
  border-radius: var(--dt-radius-sm);
  background: var(--dt-habit-soft);
  font-size: 0.9em;
}
```

找到：

```css
.progress-bar-inner {
  height: 100%;
  transition: width 0.2s;
}
```

改成：

```css
.progress-bar-inner {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}
```

- [ ] **Step 2: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/Habit/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开习惯页，确认：进行中习惯卡片化展示（阴影/圆角/hover 上浮）、打卡按钮点击后状态正确切换、归档/恢复/删除/编辑等既有交互不受影响、归档区块保持轻量列表样式（不卡片化，符合设计里"次要信息不需要同等视觉权重"的决定）。

- [ ] **Step 4: 提交**

```bash
git add web/src/views/todo/Habit/index.vue
git commit -m "feat(web): polish Habit page visuals with card treatment"
```

---

### Task 10: 计划页视觉打磨

**Files:**
- Modify: `web/src/views/todo/Goal/index.vue`

**Interfaces:**
- Consumes：Task 1 的设计 token。
- Produces：无新对外接口。

**只改 `<style scoped>` 块——不改 `<template>`/`<script setup>` 任何逻辑。**

- [ ] **Step 1: 样式调整**

找到：

```css
.goal-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.8em 0.2em;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
}
```

改成：

```css
.goal-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.9em 1em;
  border-radius: var(--dt-radius-md);
  background: var(--dt-card-bg, transparent);
  border: 1px solid var(--dt-border);
  box-shadow: var(--dt-shadow-sm);
  margin-bottom: 0.6em;
  transition:
    box-shadow 0.2s ease,
    transform 0.2s ease;
}
.goal-item:hover {
  box-shadow: var(--dt-shadow-md);
  transform: translateY(-1px);
}
.goal-item.archived {
  border: none;
  box-shadow: none;
  padding: 0.6em 0.2em;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
  margin-bottom: 0;
}
```

找到：

```css
.progress-bar {
  height: 6px;
  border-radius: 3px;
  background: rgba(128, 128, 128, 0.15);
  margin-top: 0.5em;
  overflow: hidden;
}
```

改成：

```css
.progress-bar {
  height: 8px;
  border-radius: 4px;
  background: var(--dt-page-bg, rgba(128, 128, 128, 0.15));
  margin-top: 0.6em;
  overflow: hidden;
}
```

找到：

```css
.progress-bar-inner {
  height: 100%;
  background: #1890ff;
  transition: width 0.2s;
}
```

改成：

```css
.progress-bar-inner {
  height: 100%;
  border-radius: 4px;
  background: var(--dt-habit, #1890ff);
  transition: width 0.3s ease;
}
```

- [ ] **Step 2: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/Goal/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开计划页，确认：进行中计划卡片化展示、进度条加粗上色（绿色系，呼应"进展"语义）、查看详情/编辑/归档/删除等既有交互不受影响。

- [ ] **Step 4: 提交**

```bash
git add web/src/views/todo/Goal/index.vue
git commit -m "feat(web): polish Goal page visuals with card treatment"
```

---

### Task 11: 回顾总结视觉打磨

**Files:**
- Modify: `web/src/views/todo/Review/index.vue`

**Interfaces:**
- Consumes：Task 1 的设计 token。
- Produces：无新对外接口。

**只改 `<style scoped>` 块——不改 `<template>`/`<script setup>` 任何逻辑。**

- [ ] **Step 1: 样式调整**

找到：

```css
.metric-card p {
  margin: 0.4em 0;
  font-size: 0.92em;
}
```

改成：

```css
.metric-card {
  background: var(--dt-card-bg, transparent);
  border: 1px solid var(--dt-border);
  border-radius: var(--dt-radius-md);
  padding: 16px 18px;
  box-shadow: var(--dt-shadow-sm);
}
.metric-card h4 {
  margin: 0 0 0.6em;
  font-size: 0.95em;
  font-weight: 700;
}
.metric-card p {
  margin: 0.4em 0;
  font-size: 0.92em;
}
```

找到：

```css
.reflection-step {
  margin-bottom: 1.5em;
  padding: 1em 1.2em;
  background-color: rgba(128, 128, 128, 0.06);
  border-radius: 8px;
}
.reflection-step h4 {
  margin: 0 0 0.5em;
}
```

改成：

```css
.reflection-step {
  margin-bottom: 1.2em;
  padding: 1.2em 1.4em;
  background-color: var(--dt-page-bg, rgba(128, 128, 128, 0.06));
  border: 1px solid var(--dt-border);
  border-radius: var(--dt-radius-md);
}
.reflection-step h4 {
  margin: 0 0 0.5em;
  font-weight: 700;
}
```

- [ ] **Step 2: lint 检查**

Run: `cd web && pnpm exec eslint src/views/todo/Review/index.vue`
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。

- [ ] **Step 3: 手动验证**

Run: `cd web && pnpm dev`，浏览器打开回顾总结页，确认：数据回顾三卡片视觉对齐今日概览的卡片规范、七步反思卡片排版精致化、保存草稿/完成本次回顾/历史回顾等既有交互不受影响。

- [ ] **Step 4: 提交**

```bash
git add web/src/views/todo/Review/index.vue
git commit -m "feat(web): polish Review page visuals with card treatment"
```

---

### Task 12: 端到端验证 + 收尾

**Files:**
- 无新增/修改文件（除非验证中发现问题，需要回到对应 Task 修复）。

**Interfaces:**
- Consumes：全部前序 Task 的产出。
- Produces：无——本任务是对整个视觉优化的最终确认，对照 `docs/superpowers/specs/2026-08-15-todo-module-visual-refresh-design.md` 的验收标准逐条过一遍。

- [ ] **Step 1: 跑全量后端测试**

Run: `pytest -vv`
Expected: 全部通过（含此前全部遗留测试 + Task 3 新增的 4 个，共 135 个）。

- [ ] **Step 2: 跑前端 lint（限定改动文件）**

Run:
```bash
cd web && pnpm exec eslint \
  src/styles/design-tokens.scss \
  src/components/common/AppProvider.vue \
  src/components/common/EmptyState.vue \
  src/views/todo/Dashboard/index.vue \
  src/views/todo/TodoQuadrant/index.vue \
  src/views/todo/TodoHistory/index.vue \
  src/views/todo/TaskList/index.vue \
  src/views/todo/Schedule/WeekView.vue \
  src/views/todo/Schedule/DayView.vue \
  src/views/todo/Habit/index.vue \
  src/views/todo/Goal/index.vue \
  src/views/todo/Review/index.vue
```
Expected: 只有 `prettier/prettier` 格式类提示，没有逻辑/语法错误。（`.scss` 文件 eslint 不处理，可能报"文件被忽略"之类的提示，属于正常情况，不是错误。）

- [ ] **Step 3: 浏览器端到端走查，对照 spec 验收标准**

Run: `cd web && pnpm dev`，浏览器登录后依次验证 `docs/superpowers/specs/2026-08-15-todo-module-visual-refresh-design.md` 的"验收标准"一节：

- 8 个页面视觉统一使用新的设计 token。
- 今日概览完整走一遍（问候语、完成度圆环、三卡片、空状态、快速添加）。
- 四象限待办拖拽功能正常。
- 日历页拖拽/多选/时间轴功能**完全正常**（这是整个优化里风险最高的验收点）。
- 习惯/计划页列表卡片化，进度条/打卡按钮态正确。
- 回顾总结数据卡片与今日概览视觉对齐。
- 切换深色模式，8 个页面均可正常查看，无不可读的文字/背景组合。

Expected: 全部符合预期。若发现偏差，回到对应 Task 定位问题、修复、重新跑一遍该 Task 的验证步骤，再继续。

- [ ] **Step 4: 如果验证过程中做了修复，提交**

```bash
git add -A
git commit -m "fix: address issues found during visual-refresh end-to-end verification"
```

（如果 Step 3 全部一次通过、没有任何修改，跳过本步。）
