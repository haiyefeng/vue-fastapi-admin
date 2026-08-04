# 效率应用原型图完善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按蓝图与 schedule-week spec 完善 `public/design/` 下的静态原型页面：新建可交互的周视图排程页，重做日视图，补全任务页，统一四象限配色与侧边栏。

**Architecture:** 全部是静态 HTML mockup，共享 `public/design/style.css` 的设计 token；交互（拖拽选时间、弹窗）用原生 JS 内联在各页面中，纯内存状态、无后端调用。每个页面都是可独立用浏览器打开的完整文件。

**Tech Stack:** 原生 HTML/CSS/JS，FontAwesome 6.4.0 CDN（沿用现有页面写法），无构建步骤、无框架。

## Global Constraints

- 相关 spec：`docs/superpowers/specs/2026-08-04-schedule-week-design.md`（周视图交互）与 `docs/superpowers/specs/2026-08-04-productivity-app-blueprint-design.md`（对齐决策）。
- 四象限唯一优先级模型，配色与文案**精确**为：重要且紧急 `#f5222d`、紧急不重要 `#faad14`、重要不紧急 `#1890ff`、不紧急不重要 `#909399`（值来自 `web/src/views/todo/TodoQuadrant/index.vue`）。改造后任何页面不得再出现"高/中/低"优先级 UI。
- 所有完整页面结构一致：`<header>` + `.main-container`（`aside.sidebar` + `main.content`），`<head>` 引入 `style.css` 与 FontAwesome CDN（写法照抄 `dashboard.html`）。
- 页面必须能直接 `file://` 打开（无 fetch、无模块化 JS）。
- 示例数据统一时间背景：2026年 第32周（8月3日–8月9日），"今天"= 周二 8月4日。
- UI 文案全部中文。
- 验证方式：本项目前端无测试运行器（见 CLAUDE.md），静态 mockup 的"测试"= 用浏览器打开并核对每个任务列出的检查清单（`open <file>` 即可）。
- 提交信息末尾带 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。
- 不动的文件：`calendar-week.html`（被 schedule-week 取代但按 spec 保留原样）、`login.html`、`signup.html`、`settings.html`、`goals.html`（仅侧边栏统一任务会碰它）、`../todo-quadrant.html`、`../todo-history.html`。

## File Structure

| 文件 | 职责 | 动作 |
|---|---|---|
| `public/design/style.css` | 共享 token：新增四象限调色板与圆点/选项组件类；最后清理 priority-* | 修改 |
| `public/design/schedule-week.html` | 新建：可交互周视图排程（网格渲染、拖拽/多选、创建待办弹窗） | 新建 |
| `public/design/calendar-day.html` | 重做：完整页面、0–23 时间轴、未安排任务拖入 | 重写 |
| `public/design/tasks.html` | 重做：完整页面、页内项目导航、分组列表、内嵌任务详情弹窗 | 重写 |
| `public/design/task-detail.html` | 弹窗并入 tasks.html 后删除（避免两份拷贝漂移） | 删除 |
| `public/design/dashboard.html` | 今日待办改象限圆点；侧边栏统一 | 修改 |
| `public/design/matrix.html` | 象限顺序/命名/配色对齐已实现的 TodoQuadrant；侧边栏统一 | 修改 |
| `public/design/habits.html` | 添加习惯弹窗新增"默认象限"；侧边栏统一 | 修改 |
| `public/design/goals.html` / `summary.html` | 仅侧边栏统一 | 修改 |

---

### Task 1: style.css 新增四象限共享样式

**Files:**
- Modify: `public/design/style.css`（文件末尾追加）

**Interfaces:**
- Produces: CSS 变量 `--q-ui` `--q-uni` `--q-inu` `--q-nn`；类 `.quadrant-dot`（含修饰类 `.q-ui` `.q-uni` `.q-inu` `.q-nn`）、`.quadrant-options`。后续所有任务用这些类表示象限。

- [ ] **Step 1: 在 style.css 末尾追加以下内容**

```css
/* --- Quadrant palette (统一优先级模型，色值与 TodoQuadrant.vue 一致) --- */
:root {
    --q-ui: #f5222d;   /* 重要且紧急 */
    --q-uni: #faad14;  /* 紧急不重要 */
    --q-inu: #1890ff;  /* 重要不紧急 */
    --q-nn: #909399;   /* 不紧急不重要 */
}

.quadrant-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 5px;
    vertical-align: middle;
}

.quadrant-dot.q-ui { background-color: var(--q-ui); }
.quadrant-dot.q-uni { background-color: var(--q-uni); }
.quadrant-dot.q-inu { background-color: var(--q-inu); }
.quadrant-dot.q-nn { background-color: var(--q-nn); }

.quadrant-options label {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-right: 14px;
    cursor: pointer;
    font-size: 0.95em;
}
```

- [ ] **Step 2: 验证**

Run: `open public/design/dashboard.html`
Expected: 页面渲染与改动前完全一致（本任务只新增未被引用的类，不应有视觉变化）。

- [ ] **Step 3: Commit**

```bash
git add public/design/style.css
git commit -m "design: add shared quadrant palette to prototype stylesheet"
```

---

### Task 2: 统一现有完整页面的侧边栏

**Files:**
- Modify: `public/design/dashboard.html`、`matrix.html`、`habits.html`、`goals.html`、`summary.html`（各文件的 `<aside class="sidebar">…</aside>` 整块替换）

**Interfaces:**
- Produces: 所有页面共用的导航结构（今日/任务/日历/四象限/习惯/计划/回顾总结）。后续新建页面（Task 6/9/10）内嵌同一结构。

- [ ] **Step 1: 用以下内容整块替换上述 5 个文件中的 `<aside class="sidebar">…</aside>`**

蓝图决策：收件箱与分类/项目是任务页内部导航，不再出现在共享侧边栏；日历入口指向周视图。当前页面的 `<a>` 加 `class="active"`（dashboard.html 中"今日"active，matrix.html 中"四象限"active，依此类推；summary.html 对应"回顾总结"）。

```html
<aside class="sidebar">
    <nav>
        <ul>
            <li><a href="dashboard.html"><i class="fas fa-calendar-day"></i> 今日</a></li>
            <li><a href="tasks.html"><i class="fas fa-tasks"></i> 任务</a></li>
            <li><a href="schedule-week.html"><i class="fas fa-calendar-week"></i> 日历</a></li>
            <li><a href="matrix.html"><i class="fas fa-th-large"></i> 四象限</a></li>
            <li><a href="habits.html"><i class="fas fa-sync-alt"></i> 习惯</a></li>
            <li><a href="goals.html"><i class="fas fa-flag-checkered"></i> 计划</a></li>
            <li><a href="summary.html"><i class="fas fa-glasses"></i> 回顾总结</a></li>
        </ul>
    </nav>
</aside>
```

- [ ] **Step 2: 验证**

Run: `open public/design/dashboard.html`（再抽查 matrix.html、summary.html）
Expected: 5 个页面侧边栏一致，均为 7 项，无"收件箱/分类/项目"子树；当前页高亮正确。

- [ ] **Step 3: Commit**

```bash
git add public/design/dashboard.html public/design/matrix.html public/design/habits.html public/design/goals.html public/design/summary.html
git commit -m "design: unify prototype sidebar navigation"
```

---

### Task 3: matrix.html 象限对齐

**Files:**
- Modify: `public/design/matrix.html`（`.matrix-grid` 内 4 个 `section`）

- [ ] **Step 1: 将 4 个象限重排、重命名、换色**

目标布局与已实现的 TodoQuadrant 一致——第一行：重要且紧急、紧急不重要；第二行：重要不紧急、不紧急不重要。整块替换 `.matrix-grid` 内容为：

```html
<section class="matrix-quadrant" id="quadrant1" style="border-top: 4px solid var(--q-ui);">
    <h4><i class="fas fa-exclamation-circle" style="color: var(--q-ui);"></i> 重要且紧急 (Do)</h4>
    <ul>
        <li draggable="true">完成项目报告初稿</li>
        <li draggable="true">回复 David 的邮件</li>
        <li draggable="true">联系供应商确认物料</li>
    </ul>
</section>

<section class="matrix-quadrant" id="quadrant2" style="border-top: 4px solid var(--q-uni);">
    <h4><i class="fas fa-user-friends" style="color: var(--q-uni);"></i> 紧急不重要 (Delegate)</h4>
    <ul>
        <li draggable="true">预定会议室</li>
        <li draggable="true">回复非紧急群消息</li>
    </ul>
</section>

<section class="matrix-quadrant" id="quadrant3" style="border-top: 4px solid var(--q-inu);">
    <h4><i class="fas fa-calendar-check" style="color: var(--q-inu);"></i> 重要不紧急 (Schedule)</h4>
    <ul>
        <li draggable="true">设计宣传海报 V1</li>
        <li draggable="true">规划下季度目标</li>
        <li draggable="true">学习 React 新特性</li>
    </ul>
</section>

<section class="matrix-quadrant" id="quadrant4" style="border-top: 4px solid var(--q-nn);">
    <h4><i class="fas fa-trash-alt" style="color: var(--q-nn);"></i> 不紧急不重要 (Eliminate)</h4>
    <ul>
        <li draggable="true">整理桌面文件</li>
        <li draggable="true">浏览行业资讯（非必需）</li>
    </ul>
</section>
```

- [ ] **Step 2: 验证**

Run: `open public/design/matrix.html`
Expected: 第一行红、橙顶边框，第二行蓝、灰；象限命名为"重要且紧急/紧急不重要/重要不紧急/不紧急不重要"；无黄/青配色残留。

- [ ] **Step 3: Commit**

```bash
git add public/design/matrix.html
git commit -m "design: align matrix quadrant order and colors with TodoQuadrant"
```

---

### Task 4: dashboard.html 今日待办改象限标识

**Files:**
- Modify: `public/design/dashboard.html`（`#today-tasks` 内两处 task-meta）

- [ ] **Step 1: 替换两条待办的优先级旗标**

把 `<span><i class="fas fa-flag priority-high"></i> 高</span>` 替换为：

```html
<span><span class="quadrant-dot q-ui"></span>重要且紧急</span>
```

把 `<span><i class="fas fa-flag priority-medium"></i> 中</span>` 替换为：

```html
<span><span class="quadrant-dot q-inu"></span>重要不紧急</span>
```

- [ ] **Step 2: 验证**

Run: `open public/design/dashboard.html`
Expected: 今日待办两条分别显示红点"重要且紧急"、蓝点"重要不紧急"；页面无任何"高/中/低"字样。

- [ ] **Step 3: Commit**

```bash
git add public/design/dashboard.html
git commit -m "design: replace priority flags with quadrant dots on dashboard"
```

---

### Task 5: habits.html 添加习惯弹窗新增默认象限

**Files:**
- Modify: `public/design/habits.html`（`#add-habit-modal` 表单内，"重复频率"表单组之后插入）

- [ ] **Step 1: 在"重复频率"form-group 之后插入**

```html
<div class="form-group">
    <label>默认象限（生成待办的优先级归属）</label>
    <div class="quadrant-options">
        <label><input type="radio" name="habit-quadrant" value="urgent_important"><span class="quadrant-dot q-ui"></span>重要且紧急</label>
        <label><input type="radio" name="habit-quadrant" value="urgent_not_important"><span class="quadrant-dot q-uni"></span>紧急不重要</label>
        <label><input type="radio" name="habit-quadrant" value="important_not_urgent" checked><span class="quadrant-dot q-inu"></span>重要不紧急</label>
        <label><input type="radio" name="habit-quadrant" value="not_urgent_not_important"><span class="quadrant-dot q-nn"></span>不紧急不重要</label>
    </div>
</div>
```

- [ ] **Step 2: 验证**

Run: `open public/design/habits.html`，点"添加习惯"
Expected: 弹窗内"重复频率"下方出现 4 个带色点的象限单选，默认选中"重要不紧急"。

- [ ] **Step 3: Commit**

```bash
git add public/design/habits.html
git commit -m "design: add default quadrant selector to habit modal"
```

---

### Task 6: schedule-week.html — 页面骨架与网格渲染

**Files:**
- Create: `public/design/schedule-week.html`

**Interfaces:**
- Produces: 全局 JS 状态 `granularity`（15/30/60）、`selected`（Set，键 `"day-minute"`）、`events`（数组，元素 `{title, quadrant, notes, ranges:[{day,start,end}]}`，分钟制）；函数 `renderGrid()`、`el(tag,cls,html)`、`key(day,min)`、常量 `QUADRANTS`、`GRAN_HEIGHT`、`DAY_LABELS`、`TODAY_INDEX`。Task 7/8 在同文件 `<script>` 内扩展。

- [ ] **Step 1: 创建完整文件**

```html
<!DOCTYPE html>
<html lang="zh-CN">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>周视图排程 - 我的效率应用</title>
    <link rel="stylesheet" href="style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .schedule-toolbar { display: flex; align-items: center; gap: 0.8em; margin-bottom: 0.8em; flex-wrap: wrap; }
        .schedule-toolbar .week-label { font-size: 1.1em; font-weight: 500; }
        .schedule-toolbar select.form-control { width: auto; display: inline-block; padding: 0.4em 0.6em; }
        .mode-toggle .button.active, .view-toggle .button.active { background: var(--primary-light); color: var(--primary-color); border-color: var(--primary-color); }
        .selection-summary { min-height: 1.5em; margin-bottom: 0.6em; font-size: 0.9em; color: var(--text-muted); }
        .schedule-grid { display: flex; border: 1px solid var(--border-color); user-select: none; }
        .time-gutter { width: 56px; flex-shrink: 0; border-right: 1px solid var(--border-color); background: var(--bg-alt); }
        .day-col { flex: 1; min-width: 0; border-right: 1px solid var(--border-light); }
        .day-col:last-child { border-right: none; }
        .day-head { height: 2.2em; line-height: 2.2em; text-align: center; font-size: 0.88em; font-weight: 500; border-bottom: 1px solid var(--border-color); background: var(--bg-alt); white-space: nowrap; overflow: hidden; }
        .day-col.today .day-head { background: var(--primary-light); color: var(--primary-color); }
        .col-body { position: relative; }
        .slot-cell { border-bottom: 1px dashed var(--border-light); cursor: pointer; box-sizing: border-box; }
        .slot-cell.hour-end { border-bottom: 1px solid var(--border-color); }
        .slot-cell:hover { background: var(--hover-bg); }
        .slot-cell.selected { background: var(--primary-light); box-shadow: inset 0 0 0 1px var(--primary-color); }
        .gutter-cell { position: relative; box-sizing: border-box; }
        .gutter-cell span { position: absolute; top: -0.55em; right: 6px; font-size: 0.72em; color: var(--text-muted); background: var(--bg-alt); padding: 0 2px; }
        .now-line { position: absolute; left: 0; right: 0; height: 2px; background: var(--danger-color); z-index: 3; pointer-events: none; }
        .event-block { position: absolute; left: 2px; right: 2px; border-radius: 4px; padding: 1px 4px; font-size: 0.76em; color: #fff; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; z-index: 2; box-sizing: border-box; }
    </style>
</head>

<body>
    <header>
        <h1><a href="/"><i class="fas fa-check-double"></i> 我的效率应用</a></h1>
        <nav>
            <span><i class="fas fa-user"></i> 用户名</span>
            <a href="settings.html"><i class="fas fa-cog"></i> 设置</a>
            <a href="#"><i class="fas fa-sign-out-alt"></i> 退出</a>
        </nav>
    </header>

    <div class="main-container">
        <aside class="sidebar">
            <nav>
                <ul>
                    <li><a href="dashboard.html"><i class="fas fa-calendar-day"></i> 今日</a></li>
                    <li><a href="tasks.html"><i class="fas fa-tasks"></i> 任务</a></li>
                    <li><a href="schedule-week.html" class="active"><i class="fas fa-calendar-week"></i> 日历</a></li>
                    <li><a href="matrix.html"><i class="fas fa-th-large"></i> 四象限</a></li>
                    <li><a href="habits.html"><i class="fas fa-sync-alt"></i> 习惯</a></li>
                    <li><a href="goals.html"><i class="fas fa-flag-checkered"></i> 计划</a></li>
                    <li><a href="summary.html"><i class="fas fa-glasses"></i> 回顾总结</a></li>
                </ul>
            </nav>
        </aside>

        <main class="content">
            <div class="schedule-toolbar">
                <button class="button"><i class="fas fa-chevron-left"></i></button>
                <span class="week-label">2026年 第32周 (8月3日 - 8月9日)</span>
                <button class="button"><i class="fas fa-chevron-right"></i></button>
                <select id="granularity" class="form-control" title="时间粒度">
                    <option value="15">15 分钟</option>
                    <option value="30" selected>30 分钟</option>
                    <option value="60">1 小时</option>
                </select>
                <span class="mode-toggle">
                    <button class="button active" id="mode-drag">拖拽选择</button>
                    <button class="button" id="mode-multi">多选格子</button>
                </span>
                <button class="button button-primary" id="finish-select" style="display: none;">完成选择</button>
                <button class="button" id="clear-select" style="display: none;">清空选择</button>
                <span class="view-toggle" style="margin-left: auto;">
                    <a href="calendar-day.html" class="button">日</a>
                    <a href="schedule-week.html" class="button active">周</a>
                </span>
            </div>
            <div class="selection-summary" id="selection-summary"></div>
            <div class="schedule-grid" id="schedule-grid"></div>
        </main>
    </div>

    <script>
        const GRAN_HEIGHT = { 15: 16, 30: 26, 60: 44 };
        const DAY_LABELS = ['周一 8/3', '周二 8/4', '周三 8/5', '周四 8/6', '周五 8/7', '周六 8/8', '周日 8/9'];
        const TODAY_INDEX = 1;
        const QUADRANTS = {
            urgent_important: { color: '#f5222d', label: '重要且紧急' },
            urgent_not_important: { color: '#faad14', label: '紧急不重要' },
            important_not_urgent: { color: '#1890ff', label: '重要不紧急' },
            not_urgent_not_important: { color: '#909399', label: '不紧急不重要' },
        };

        let granularity = 30;
        let mode = 'drag'; // 'drag' | 'multi'
        let selected = new Set(); // "day-minute"
        let events = [];

        function el(tag, cls, html) {
            const node = document.createElement(tag);
            if (cls) node.className = cls;
            if (html) node.innerHTML = html;
            return node;
        }

        function key(day, min) { return day + '-' + min; }

        function fmt(min) {
            return String(Math.floor(min / 60)).padStart(2, '0') + ':' + String(min % 60).padStart(2, '0');
        }

        function renderGrid() {
            const grid = document.getElementById('schedule-grid');
            grid.innerHTML = '';
            const h = GRAN_HEIGHT[granularity];
            const rows = 1440 / granularity;

            const gutter = el('div', 'time-gutter');
            gutter.appendChild(el('div', 'day-head', ''));
            const gbody = el('div', 'col-body');
            for (let r = 0; r < rows; r++) {
                const min = r * granularity;
                const cell = el('div', 'gutter-cell');
                cell.style.height = h + 'px';
                if (min % 60 === 0 && min > 0) cell.innerHTML = '<span>' + fmt(min) + '</span>';
                gbody.appendChild(cell);
            }
            gutter.appendChild(gbody);
            grid.appendChild(gutter);

            for (let d = 0; d < 7; d++) {
                const col = el('div', 'day-col' + (d === TODAY_INDEX ? ' today' : ''));
                col.appendChild(el('div', 'day-head', DAY_LABELS[d]));
                const body = el('div', 'col-body');
                for (let r = 0; r < rows; r++) {
                    const min = r * granularity;
                    const cell = el('div', 'slot-cell');
                    cell.style.height = h + 'px';
                    if ((min + granularity) % 60 === 0) cell.classList.add('hour-end');
                    cell.dataset.day = d;
                    cell.dataset.min = min;
                    if (selected.has(key(d, min))) cell.classList.add('selected');
                    body.appendChild(cell);
                }
                renderEventsForDay(body, d, h);
                if (d === TODAY_INDEX) {
                    const now = new Date();
                    const nowMin = now.getHours() * 60 + now.getMinutes();
                    const line = el('div', 'now-line');
                    line.style.top = (nowMin * h / granularity) + 'px';
                    body.appendChild(line);
                }
                col.appendChild(body);
                grid.appendChild(col);
            }
        }

        function renderEventsForDay(body, day, h) {
            events.forEach(ev => {
                ev.ranges.filter(r => r.day === day).forEach(r => {
                    const block = el('div', 'event-block');
                    block.style.top = (r.start * h / granularity) + 'px';
                    block.style.height = ((r.end - r.start) * h / granularity - 2) + 'px';
                    block.style.backgroundColor = QUADRANTS[ev.quadrant].color;
                    block.title = ev.title + ' ' + fmt(r.start) + '–' + fmt(r.end);
                    block.textContent = fmt(r.start) + ' ' + ev.title;
                    body.appendChild(block);
                });
            });
        }

        document.getElementById('granularity').addEventListener('change', e => {
            granularity = Number(e.target.value);
            selected.clear();
            refreshSelection();
            renderGrid();
        });

        function refreshSelection() { /* Task 7 实现，此处先占位保证不报错 */ }

        renderGrid();
    </script>
</body>

</html>
```

（`refreshSelection` 的空实现是 Task 7 的接缝，本任务内必须存在以免 change 事件报错——这是唯一允许的"占位"，Task 7 会整体替换它。）

- [ ] **Step 2: 验证**

Run: `open public/design/schedule-week.html`
Expected: 完整页面（头部/侧边栏/工具栏）；默认 30min 粒度 48 行×7 列网格，整点处实线+左侧时间标签，其余虚线；周二列表头高亮；切换粒度为 15min/1小时 后行数、行高相应变化；红色"当前时间"线出现在周二列。

- [ ] **Step 3: Commit**

```bash
git add public/design/schedule-week.html
git commit -m "design: add schedule-week prototype skeleton with time grid"
```

---

### Task 7: schedule-week.html — 拖拽与多选交互

**Files:**
- Modify: `public/design/schedule-week.html`（`<script>` 内）

**Interfaces:**
- Consumes: Task 6 的 `selected`、`key()`、`renderGrid()`、`granularity`。
- Produces: `refreshSelection()`（真实实现）、`mergedRanges()`（返回 `[{day,start,end}]`，Task 8 的弹窗用它展示与保存时间段）、`openCreateModal()` 占位（Task 8 实现）。

- [ ] **Step 1: 替换空的 `refreshSelection`，并在 `renderGrid();` 调用行之前插入以下代码**

```js
function refreshSelection() {
    document.querySelectorAll('.slot-cell').forEach(c => {
        c.classList.toggle('selected', selected.has(key(Number(c.dataset.day), Number(c.dataset.min))));
    });
    const summary = document.getElementById('selection-summary');
    if (selected.size === 0) {
        summary.textContent = '';
    } else {
        const ranges = mergedRanges();
        const hours = (selected.size * granularity / 60).toFixed(1).replace(/\.0$/, '');
        summary.textContent = '已选 ' + ranges.length + ' 个时间段，合计 ' + hours + ' 小时';
    }
    document.getElementById('clear-select').style.display = selected.size ? '' : 'none';
    document.getElementById('finish-select').style.display = (mode === 'multi' && selected.size) ? '' : 'none';
}

function mergedRanges() {
    const byDay = {};
    selected.forEach(k => {
        const [d, m] = k.split('-').map(Number);
        (byDay[d] = byDay[d] || []).push(m);
    });
    const out = [];
    Object.keys(byDay).map(Number).sort((a, b) => a - b).forEach(d => {
        const mins = byDay[d].sort((a, b) => a - b);
        let start = mins[0], prev = mins[0];
        for (let i = 1; i <= mins.length; i++) {
            if (i === mins.length || mins[i] !== prev + granularity) {
                out.push({ day: d, start: start, end: prev + granularity });
                start = mins[i];
            }
            prev = mins[i];
        }
    });
    return out;
}

function openCreateModal() { /* Task 8 实现 */ }

let dragging = false, dragDay = null, dragAnchor = null;
const gridEl = document.getElementById('schedule-grid');

gridEl.addEventListener('mousedown', e => {
    if (mode !== 'drag') return;
    const c = e.target.closest('.slot-cell');
    if (!c) return;
    dragging = true;
    dragDay = Number(c.dataset.day);
    dragAnchor = Number(c.dataset.min);
    applyDragRange(dragAnchor);
    e.preventDefault();
});

gridEl.addEventListener('mouseover', e => {
    if (!dragging) return;
    const c = e.target.closest('.slot-cell');
    if (!c || Number(c.dataset.day) !== dragDay) return;
    applyDragRange(Number(c.dataset.min));
});

document.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    if (selected.size) openCreateModal();
});

function applyDragRange(cur) {
    selected.clear();
    const lo = Math.min(dragAnchor, cur), hi = Math.max(dragAnchor, cur);
    for (let m = lo; m <= hi; m += granularity) selected.add(key(dragDay, m));
    refreshSelection();
}

gridEl.addEventListener('click', e => {
    if (mode !== 'multi') return;
    const c = e.target.closest('.slot-cell');
    if (!c) return;
    const k = key(Number(c.dataset.day), Number(c.dataset.min));
    selected.has(k) ? selected.delete(k) : selected.add(k);
    refreshSelection();
});

function setMode(next) {
    mode = next;
    selected.clear();
    document.getElementById('mode-drag').classList.toggle('active', next === 'drag');
    document.getElementById('mode-multi').classList.toggle('active', next === 'multi');
    refreshSelection();
}
document.getElementById('mode-drag').addEventListener('click', () => setMode('drag'));
document.getElementById('mode-multi').addEventListener('click', () => setMode('multi'));
document.getElementById('clear-select').addEventListener('click', () => { selected.clear(); refreshSelection(); });
document.getElementById('finish-select').addEventListener('click', () => { if (selected.size) openCreateModal(); });
```

- [ ] **Step 2: 验证**

Run: `open public/design/schedule-week.html`
Expected:
1. 拖拽模式：在周三列按住拖动，蓝色高亮随鼠标扩展且不越出该列；松手后（弹窗未实现）选区保留，摘要显示"已选 1 个时间段，合计 X 小时"。
2. 切到多选格子：点周一 9:00 和周五 14:00 两格，均高亮，出现"完成选择"与"清空选择"按钮，摘要显示"已选 2 个时间段"。
3. 清空选择后摘要与按钮消失；切换模式或粒度会清空选区。

- [ ] **Step 3: Commit**

```bash
git add public/design/schedule-week.html
git commit -m "design: add drag and multi-select interactions to schedule-week"
```

---

### Task 8: schedule-week.html — 创建待办弹窗与事件块

**Files:**
- Modify: `public/design/schedule-week.html`

**Interfaces:**
- Consumes: Task 7 的 `mergedRanges()`、`refreshSelection()`；Task 6 的 `events`、`renderGrid()`、`QUADRANTS`、`DAY_LABELS`、`fmt()`。

- [ ] **Step 1: 在 `</main>` 之后、`<script>` 之前插入弹窗 HTML**

```html
<div id="create-todo-modal" class="modal">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">创建待办事项</h5>
                <button type="button" class="close" onclick="closeCreateModal()" aria-label="Close"><span aria-hidden="true">×</span></button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label for="todo-title">标题 <span style="color: var(--danger-color);">*</span></label>
                    <input type="text" id="todo-title" class="form-control" placeholder="要做什么？">
                </div>
                <div class="form-group">
                    <label>象限（优先级）<span style="color: var(--danger-color);">*</span></label>
                    <div class="quadrant-options" id="todo-quadrant">
                        <label><input type="radio" name="todo-quadrant" value="urgent_important"><span class="quadrant-dot q-ui"></span>重要且紧急</label>
                        <label><input type="radio" name="todo-quadrant" value="urgent_not_important"><span class="quadrant-dot q-uni"></span>紧急不重要</label>
                        <label><input type="radio" name="todo-quadrant" value="important_not_urgent"><span class="quadrant-dot q-inu"></span>重要不紧急</label>
                        <label><input type="radio" name="todo-quadrant" value="not_urgent_not_important"><span class="quadrant-dot q-nn"></span>不紧急不重要</label>
                    </div>
                </div>
                <div class="form-group">
                    <label for="todo-notes">备注</label>
                    <textarea id="todo-notes" class="form-control" rows="2" placeholder="可选"></textarea>
                </div>
                <div class="form-group">
                    <label>已选时间段</label>
                    <ul id="todo-slots" style="font-size: 0.9em; color: var(--text-muted); padding-left: 1em; list-style: disc;"></ul>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="button" onclick="closeCreateModal()">取消</button>
                <button type="button" class="button button-primary" onclick="confirmCreate()">确定</button>
            </div>
        </div>
    </div>
</div>
```

- [ ] **Step 2: 替换 Task 7 留下的空 `openCreateModal`，并追加弹窗逻辑**

```js
function openCreateModal() {
    document.getElementById('todo-title').value = '';
    document.getElementById('todo-notes').value = '';
    document.querySelectorAll('input[name="todo-quadrant"]').forEach(r => { r.checked = false; });
    const list = document.getElementById('todo-slots');
    list.innerHTML = '';
    mergedRanges().forEach(r => {
        const li = document.createElement('li');
        li.textContent = DAY_LABELS[r.day].split(' ')[0] + ' ' + fmt(r.start) + '–' + fmt(r.end);
        list.appendChild(li);
    });
    document.getElementById('create-todo-modal').style.display = 'block';
    document.getElementById('todo-title').focus();
}

function closeCreateModal() {
    document.getElementById('create-todo-modal').style.display = 'none';
}

function confirmCreate() {
    const title = document.getElementById('todo-title').value.trim();
    const quadrant = (document.querySelector('input[name="todo-quadrant"]:checked') || {}).value;
    if (!title) { alert('请输入标题'); return; }
    if (!quadrant) { alert('请选择象限'); return; }
    events.push({
        title: title,
        quadrant: quadrant,
        notes: document.getElementById('todo-notes').value.trim(),
        ranges: mergedRanges(),
    });
    selected.clear();
    closeCreateModal();
    refreshSelection();
    renderGrid();
}
```

- [ ] **Step 3: 验证**

Run: `open public/design/schedule-week.html`
Expected:
1. 拖拽模式松手立即弹窗，"已选时间段"逐条列出（如"周三 09:00–10:30"）。
2. 不填标题点确定 → 提示"请输入标题"；不选象限 → 提示"请选择象限"。
3. 填"写周报"+选"重要且紧急"确定后：弹窗关闭、选区清空、周三列出现红色事件块，文本含"09:00 写周报"，hover 显示完整时间。
4. 多选模式跨天选 3 格 → 完成选择 → 确定后 3 处各自出现事件块。
5. 切换粒度后事件块位置/高度依然正确（分钟制换算）。
6. 取消按钮关闭弹窗且保留选区。

- [ ] **Step 4: Commit**

```bash
git add public/design/schedule-week.html
git commit -m "design: add create-todo modal and event blocks to schedule-week"
```

---

### Task 9: calendar-day.html 重做

**Files:**
- 重写: `public/design/calendar-day.html`（整文件替换）

- [ ] **Step 1: 用以下完整内容重写文件**

```html
<!DOCTYPE html>
<html lang="zh-CN">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>日视图 - 我的效率应用</title>
    <link rel="stylesheet" href="style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .view-toggle .button.active { background: var(--primary-light); color: var(--primary-color); border-color: var(--primary-color); }
        .day-timeline { position: relative; border: 1px solid var(--border-color); user-select: none; }
        .hour-slot { height: 48px; border-bottom: 1px solid var(--border-light); position: relative; padding-left: 56px; box-sizing: border-box; }
        .hour-slot::before { content: attr(data-time); position: absolute; left: 6px; top: -0.55em; font-size: 0.75em; color: var(--text-muted); background: var(--bg-color); padding: 0 2px; }
        .hour-slot.drop-hint { background: var(--primary-light); }
        .day-event { position: absolute; left: 56px; right: 10px; border-radius: 4px; padding: 2px 6px; font-size: 0.85em; color: #fff; overflow: hidden; z-index: 2; box-sizing: border-box; }
        .unscheduled-item { cursor: grab; }
        .unscheduled-item:active { cursor: grabbing; }
    </style>
</head>

<body>
    <header>
        <h1><a href="/"><i class="fas fa-check-double"></i> 我的效率应用</a></h1>
        <nav>
            <span><i class="fas fa-user"></i> 用户名</span>
            <a href="settings.html"><i class="fas fa-cog"></i> 设置</a>
            <a href="#"><i class="fas fa-sign-out-alt"></i> 退出</a>
        </nav>
    </header>

    <div class="main-container">
        <aside class="sidebar">
            <nav>
                <ul>
                    <li><a href="dashboard.html"><i class="fas fa-calendar-day"></i> 今日</a></li>
                    <li><a href="tasks.html"><i class="fas fa-tasks"></i> 任务</a></li>
                    <li><a href="schedule-week.html" class="active"><i class="fas fa-calendar-week"></i> 日历</a></li>
                    <li><a href="matrix.html"><i class="fas fa-th-large"></i> 四象限</a></li>
                    <li><a href="habits.html"><i class="fas fa-sync-alt"></i> 习惯</a></li>
                    <li><a href="goals.html"><i class="fas fa-flag-checkered"></i> 计划</a></li>
                    <li><a href="summary.html"><i class="fas fa-glasses"></i> 回顾总结</a></li>
                </ul>
            </nav>
        </aside>

        <main class="content">
            <div class="calendar-controls">
                <button class="button"><i class="fas fa-chevron-left"></i></button>
                <span>2026年8月4日, 星期二</span>
                <button class="button"><i class="fas fa-chevron-right"></i></button>
                <input type="date" class="form-control" style="width: auto;" value="2026-08-04">
                <span class="view-toggle" style="margin-left: auto;">
                    <a href="calendar-day.html" class="button active">日</a>
                    <a href="schedule-week.html" class="button">周</a>
                </span>
            </div>

            <div class="day-timeline" id="day-timeline"></div>

            <section style="margin-top: 2em;">
                <h3><i class="far fa-calendar-times"></i> 未安排的任务（拖到时间轴上排程）</h3>
                <ul class="task-list" id="unscheduled-list">
                    <li class="task-item unscheduled-item" draggable="true" data-title="设计宣传海报 V1" data-quadrant="important_not_urgent">
                        <div class="task-content">
                            <span class="task-title"><span class="quadrant-dot q-inu"></span>设计宣传海报 V1</span>
                            <div class="task-meta"><span><i class="far fa-calendar"></i> 8月18日截止</span></div>
                        </div>
                    </li>
                    <li class="task-item unscheduled-item" draggable="true" data-title="回复 David 的邮件" data-quadrant="urgent_important">
                        <div class="task-content">
                            <span class="task-title"><span class="quadrant-dot q-ui"></span>回复 David 的邮件</span>
                            <div class="task-meta"><span><i class="far fa-calendar"></i> 今天截止</span></div>
                        </div>
                    </li>
                    <li class="task-item unscheduled-item" draggable="true" data-title="整理桌面文件" data-quadrant="not_urgent_not_important">
                        <div class="task-content">
                            <span class="task-title"><span class="quadrant-dot q-nn"></span>整理桌面文件</span>
                            <div class="task-meta"><span>无截止时间</span></div>
                        </div>
                    </li>
                </ul>
            </section>
        </main>
    </div>

    <script>
        const HOUR_PX = 48;
        const COLORS = {
            urgent_important: '#f5222d',
            urgent_not_important: '#faad14',
            important_not_urgent: '#1890ff',
            not_urgent_not_important: '#909399',
        };
        let blocks = [
            { title: '团队会议', quadrant: 'urgent_important', start: 9 * 60, end: 10 * 60 + 30 },
            { title: '晨间阅读（习惯）', quadrant: 'important_not_urgent', start: 7 * 60, end: 7 * 60 + 30 },
            { title: '准备报告', quadrant: 'urgent_not_important', start: 14 * 60, end: 15 * 60 },
        ];

        function fmt(min) {
            return String(Math.floor(min / 60)).padStart(2, '0') + ':' + String(min % 60).padStart(2, '0');
        }

        function renderTimeline() {
            const tl = document.getElementById('day-timeline');
            tl.innerHTML = '';
            for (let hh = 0; hh < 24; hh++) {
                const slot = document.createElement('div');
                slot.className = 'hour-slot';
                slot.dataset.time = String(hh).padStart(2, '0') + ':00';
                tl.appendChild(slot);
            }
            blocks.forEach(b => {
                const ev = document.createElement('div');
                ev.className = 'day-event';
                ev.style.top = (b.start / 60 * HOUR_PX) + 'px';
                ev.style.height = ((b.end - b.start) / 60 * HOUR_PX - 2) + 'px';
                ev.style.backgroundColor = COLORS[b.quadrant];
                ev.title = b.title + ' ' + fmt(b.start) + '–' + fmt(b.end);
                ev.innerHTML = '<strong>' + fmt(b.start) + '</strong> ' + b.title;
                tl.appendChild(ev);
            });
            const now = new Date();
            const line = document.createElement('div');
            line.style.cssText = 'position:absolute;left:0;right:0;height:2px;background:var(--danger-color);z-index:3;pointer-events:none;';
            line.style.top = ((now.getHours() * 60 + now.getMinutes()) / 60 * HOUR_PX) + 'px';
            tl.appendChild(line);
        }

        let dragged = null;
        document.getElementById('unscheduled-list').addEventListener('dragstart', e => {
            const item = e.target.closest('.unscheduled-item');
            if (!item) return;
            dragged = { title: item.dataset.title, quadrant: item.dataset.quadrant, el: item };
            e.dataTransfer.effectAllowed = 'move';
        });

        const timeline = document.getElementById('day-timeline');
        timeline.addEventListener('dragover', e => {
            if (!dragged) return;
            e.preventDefault();
            const slot = e.target.closest('.hour-slot');
            timeline.querySelectorAll('.drop-hint').forEach(s => s.classList.remove('drop-hint'));
            if (slot) slot.classList.add('drop-hint');
        });
        timeline.addEventListener('dragleave', () => {
            timeline.querySelectorAll('.drop-hint').forEach(s => s.classList.remove('drop-hint'));
        });
        timeline.addEventListener('drop', e => {
            e.preventDefault();
            timeline.querySelectorAll('.drop-hint').forEach(s => s.classList.remove('drop-hint'));
            if (!dragged) return;
            const rect = timeline.getBoundingClientRect();
            const y = e.clientY - rect.top;
            const startMin = Math.floor(y / (HOUR_PX / 2)) * 30; // 按 30 分钟吸附
            blocks.push({ title: dragged.title, quadrant: dragged.quadrant, start: startMin, end: startMin + 60 });
            dragged.el.remove();
            dragged = null;
            renderTimeline();
        });

        renderTimeline();
    </script>
</body>

</html>
```

- [ ] **Step 2: 验证**

Run: `open public/design/calendar-day.html`
Expected: 完整页面；时间轴 0:00–23:00 共 24 格；预置 3 个事件块按象限着色（7:00 蓝"晨间阅读（习惯）"、9:00 红"团队会议"、14:00 橙"准备报告"）；红色当前时间线；把"回复 David 的邮件"拖到时间轴 16 点附近 → 该处出现红色 1 小时事件块（按 30min 吸附），列表中该项消失；日|周切换按钮可跳转 schedule-week.html。

- [ ] **Step 3: Commit**

```bash
git add public/design/calendar-day.html
git commit -m "design: rework calendar-day into full page with 0-23 axis and drag-in scheduling"
```

---

### Task 10: tasks.html 重做 — 页面结构与分组列表

**Files:**
- 重写: `public/design/tasks.html`（整文件替换）

**Interfaces:**
- Produces: 页面含 `openModal(id)` / `closeModal(id)` 函数与 `id="task-detail-modal"` 的挂载点（本任务先放注释占位符 `<!-- task-detail-modal (Task 11) -->`，Task 11 替换为真实弹窗）。列表项 `.task-title` 均带 `onclick="openModal('task-detail-modal')"`。

- [ ] **Step 1: 用以下完整内容重写文件**

```html
<!DOCTYPE html>
<html lang="zh-CN">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>任务 - 我的效率应用</title>
    <link rel="stylesheet" href="style.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .tasks-layout { display: flex; gap: 1.5em; align-items: flex-start; }
        .project-nav { width: 200px; flex-shrink: 0; background: var(--bg-alt); border: 1px solid var(--border-light); border-radius: 6px; padding: 0.8em 0; }
        .project-nav ul li a { display: flex; align-items: center; padding: 0.45em 1em; color: var(--text-muted); text-decoration: none; font-size: 0.92em; }
        .project-nav ul li a i { margin-right: 0.6em; width: 14px; text-align: center; }
        .project-nav ul li a:hover { background: var(--hover-bg); }
        .project-nav ul li a.active { background: var(--primary-light); color: var(--primary-color); font-weight: 500; }
        .project-nav .nav-group { font-size: 0.8em; font-weight: 600; color: var(--text-color); padding: 0.8em 1em 0.3em; }
        .project-nav ul ul { padding-left: 1.2em; }
        .task-area { flex: 1; min-width: 0; }
        .group-title { margin: 1em 0 0.5em 0.5em; font-size: 0.9em; font-weight: 600; }
    </style>
</head>

<body>
    <header>
        <h1><a href="/"><i class="fas fa-check-double"></i> 我的效率应用</a></h1>
        <nav>
            <span><i class="fas fa-user"></i> 用户名</span>
            <a href="settings.html"><i class="fas fa-cog"></i> 设置</a>
            <a href="#"><i class="fas fa-sign-out-alt"></i> 退出</a>
        </nav>
    </header>

    <div class="main-container">
        <aside class="sidebar">
            <nav>
                <ul>
                    <li><a href="dashboard.html"><i class="fas fa-calendar-day"></i> 今日</a></li>
                    <li><a href="tasks.html" class="active"><i class="fas fa-tasks"></i> 任务</a></li>
                    <li><a href="schedule-week.html"><i class="fas fa-calendar-week"></i> 日历</a></li>
                    <li><a href="matrix.html"><i class="fas fa-th-large"></i> 四象限</a></li>
                    <li><a href="habits.html"><i class="fas fa-sync-alt"></i> 习惯</a></li>
                    <li><a href="goals.html"><i class="fas fa-flag-checkered"></i> 计划</a></li>
                    <li><a href="summary.html"><i class="fas fa-glasses"></i> 回顾总结</a></li>
                </ul>
            </nav>
        </aside>

        <main class="content">
            <div class="tasks-layout">
                <nav class="project-nav">
                    <ul>
                        <li><a href="#" class="active"><i class="fas fa-inbox"></i> 收件箱 <span style="margin-left:auto;">3</span></a></li>
                    </ul>
                    <div class="nav-group">工作</div>
                    <ul>
                        <li><a href="#"><i class="fas fa-briefcase"></i> Q4 营销活动</a></li>
                        <li><a href="#"><i class="fas fa-briefcase"></i> 官网改版</a></li>
                    </ul>
                    <div class="nav-group">学习</div>
                    <ul>
                        <li><a href="#"><i class="fas fa-graduation-cap"></i> React 进阶</a></li>
                    </ul>
                    <div class="nav-group">清单</div>
                    <ul>
                        <li><a href="#"><i class="fas fa-list"></i> 本周购物清单</a></li>
                    </ul>
                    <ul style="margin-top: 0.6em; border-top: 1px solid var(--border-light); padding-top: 0.6em;">
                        <li><a href="#"><i class="fas fa-plus"></i> 新建项目/清单</a></li>
                    </ul>
                </nav>

                <div class="task-area">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1em;">
                        <h2 style="margin-bottom: 0;"><i class="fas fa-inbox"></i> 收件箱</h2>
                        <div>
                            <button class="button"><i class="fas fa-sort-amount-down"></i> 排序</button>
                            <button class="button"><i class="fas fa-filter"></i> 过滤</button>
                        </div>
                    </div>

                    <section class="quick-add" style="margin-bottom: 1em;">
                        <form onsubmit="return false;">
                            <input type="text" class="form-control" placeholder="添加任务到收件箱 (按 Enter 保存)">
                            <button type="submit" class="button button-primary"><i class="fas fa-plus"></i> 添加</button>
                        </form>
                    </section>

                    <ul class="task-list">
                        <li><h4 class="group-title" style="color: var(--danger-color);">已过期</h4></li>
                        <li class="task-item">
                            <label class="checkbox-custom task-checkbox"><input type="checkbox"><span class="checkmark"></span></label>
                            <div class="task-content">
                                <span class="task-title" onclick="openModal('task-detail-modal')">联系供应商确认物料</span>
                                <div class="task-meta">
                                    <span style="color: var(--danger-color);"><i class="far fa-calendar"></i> 昨天</span>
                                    <span><span class="quadrant-dot q-ui"></span>重要且紧急</span>
                                </div>
                            </div>
                            <div class="task-actions">
                                <button class="button-icon" title="排程"><i class="fas fa-calendar-plus"></i></button>
                                <button class="button-icon" title="编辑" onclick="openModal('task-detail-modal')"><i class="fas fa-edit"></i></button>
                            </div>
                        </li>

                        <li><h4 class="group-title" style="color: var(--primary-color);">今天</h4></li>
                        <li class="task-item">
                            <label class="checkbox-custom task-checkbox"><input type="checkbox"><span class="checkmark"></span></label>
                            <div class="task-content">
                                <span class="task-title" onclick="openModal('task-detail-modal')">完成项目报告初稿</span>
                                <div class="task-meta">
                                    <span><i class="far fa-calendar"></i> 今天 18:00</span>
                                    <span><span class="quadrant-dot q-ui"></span>重要且紧急</span>
                                    <span><i class="far fa-check-square"></i> 1/3 子任务</span>
                                </div>
                            </div>
                            <div class="task-actions">
                                <button class="button-icon" title="排程"><i class="fas fa-calendar-plus"></i></button>
                                <button class="button-icon" title="编辑" onclick="openModal('task-detail-modal')"><i class="fas fa-edit"></i></button>
                            </div>
                        </li>
                        <li class="task-item">
                            <label class="checkbox-custom task-checkbox"><input type="checkbox" checked><span class="checkmark"></span></label>
                            <div class="task-content">
                                <span class="task-title" onclick="openModal('task-detail-modal')">晨间阅读（习惯）</span>
                                <div class="task-meta">
                                    <span><i class="fas fa-sync-alt"></i> 习惯生成</span>
                                    <span><span class="quadrant-dot q-inu"></span>重要不紧急</span>
                                </div>
                            </div>
                        </li>

                        <li><h4 class="group-title">稍后</h4></li>
                        <li class="task-item">
                            <label class="checkbox-custom task-checkbox"><input type="checkbox"><span class="checkmark"></span></label>
                            <div class="task-content">
                                <span class="task-title" onclick="openModal('task-detail-modal')">设计宣传海报 V1</span>
                                <div class="task-meta">
                                    <span><i class="far fa-calendar"></i> 8月18日</span>
                                    <span><span class="quadrant-dot q-inu"></span>重要不紧急</span>
                                </div>
                            </div>
                            <div class="task-actions">
                                <button class="button-icon" title="排程"><i class="fas fa-calendar-plus"></i></button>
                                <button class="button-icon" title="编辑" onclick="openModal('task-detail-modal')"><i class="fas fa-edit"></i></button>
                            </div>
                        </li>
                        <li class="task-item">
                            <label class="checkbox-custom task-checkbox"><input type="checkbox"><span class="checkmark"></span></label>
                            <div class="task-content">
                                <span class="task-title" onclick="openModal('task-detail-modal')">浏览行业资讯</span>
                                <div class="task-meta">
                                    <span>无截止时间</span>
                                    <span><span class="quadrant-dot q-nn"></span>不紧急不重要</span>
                                </div>
                            </div>
                            <div class="task-actions">
                                <button class="button-icon" title="排程"><i class="fas fa-calendar-plus"></i></button>
                                <button class="button-icon" title="编辑" onclick="openModal('task-detail-modal')"><i class="fas fa-edit"></i></button>
                            </div>
                        </li>
                    </ul>
                </div>
            </div>
        </main>
    </div>

    <!-- task-detail-modal (Task 11) -->

    <script>
        function openModal(id) { const m = document.getElementById(id); if (m) m.style.display = 'block'; }
        function closeModal(id) { const m = document.getElementById(id); if (m) m.style.display = 'none'; }
    </script>
</body>

</html>
```

- [ ] **Step 2: 验证**

Run: `open public/design/tasks.html`
Expected: 完整页面；左侧项目导航（收件箱 active、工作/学习/清单分组、新建入口）；右侧快速添加框 + 三组任务（已过期红、今天蓝、稍后），每条带象限色点+文案；有一条"习惯生成"标记的任务；无"高/中/低"字样；点任务标题暂无反应（弹窗 Task 11 提供）。

- [ ] **Step 3: Commit**

```bash
git add public/design/tasks.html
git commit -m "design: rework tasks page with project nav and quadrant-based list"
```

---

### Task 11: tasks.html 内嵌任务详情弹窗，删除 task-detail.html

**Files:**
- Modify: `public/design/tasks.html`（替换 `<!-- task-detail-modal (Task 11) -->` 注释）
- Delete: `public/design/task-detail.html`

- [ ] **Step 1: 将占位注释替换为以下弹窗**

对齐蓝图：优先级下拉 → 象限单选；新增"关联计划"；保留项目/截止/提醒/子任务。

```html
<div id="task-detail-modal" class="modal">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">任务详情</h5>
                <button type="button" class="close" onclick="closeModal('task-detail-modal')" aria-label="Close"><span aria-hidden="true">×</span></button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <input type="text" class="form-control" value="完成项目报告初稿" style="font-size: 1.15em; font-weight: 500; border: none; box-shadow: none; padding: 0.4em 0;">
                </div>
                <div class="form-group">
                    <textarea class="form-control" rows="2" placeholder="添加备注...（可记录完成方法、收获、注意事项等）"></textarea>
                </div>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1em; margin-bottom: 1em;">
                    <div class="form-group">
                        <label><i class="fas fa-folder"></i> 项目</label>
                        <select class="form-control">
                            <option>收件箱</option>
                            <option selected>工作 / Q4 营销活动</option>
                            <option>工作 / 官网改版</option>
                            <option>学习 / React 进阶</option>
                            <option>清单 / 本周购物清单</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label><i class="far fa-calendar"></i> 截止日期</label>
                        <input type="date" class="form-control" value="2026-08-04">
                    </div>
                    <div class="form-group">
                        <label><i class="far fa-bell"></i> 提醒</label>
                        <input type="datetime-local" class="form-control" value="2026-08-04T16:00">
                    </div>
                    <div class="form-group">
                        <label><i class="fas fa-flag-checkered"></i> 关联计划</label>
                        <select class="form-control">
                            <option selected>无</option>
                            <option>提升 React 编程技能</option>
                            <option>完成毕业论文</option>
                        </select>
                    </div>
                </div>

                <div class="form-group">
                    <label>象限（优先级）</label>
                    <div class="quadrant-options">
                        <label><input type="radio" name="detail-quadrant" value="urgent_important" checked><span class="quadrant-dot q-ui"></span>重要且紧急</label>
                        <label><input type="radio" name="detail-quadrant" value="urgent_not_important"><span class="quadrant-dot q-uni"></span>紧急不重要</label>
                        <label><input type="radio" name="detail-quadrant" value="important_not_urgent"><span class="quadrant-dot q-inu"></span>重要不紧急</label>
                        <label><input type="radio" name="detail-quadrant" value="not_urgent_not_important"><span class="quadrant-dot q-nn"></span>不紧急不重要</label>
                    </div>
                </div>

                <hr style="border: none; border-top: 1px solid var(--border-light); margin: 1.2em 0;">

                <section>
                    <h4 style="font-size: 1em; font-weight: 600; margin-bottom: 0.6em;">子任务</h4>
                    <ul class="task-list" style="margin-bottom: 0.8em;">
                        <li class="task-item" style="padding: 0.4em 0;">
                            <label class="checkbox-custom task-checkbox"><input type="checkbox" checked><span class="checkmark"></span></label>
                            <div class="task-content"><input type="text" class="form-control" value="收集数据" style="border: none; padding-left: 0;"></div>
                            <div class="task-actions" style="display: flex;"><button class="button-icon"><i class="fas fa-trash-alt"></i></button></div>
                        </li>
                        <li class="task-item" style="padding: 0.4em 0;">
                            <label class="checkbox-custom task-checkbox"><input type="checkbox"><span class="checkmark"></span></label>
                            <div class="task-content"><input type="text" class="form-control" value="撰写第一部分" style="border: none; padding-left: 0;"></div>
                            <div class="task-actions" style="display: flex;"><button class="button-icon"><i class="fas fa-trash-alt"></i></button></div>
                        </li>
                        <li class="task-item" style="padding: 0.4em 0;">
                            <label class="checkbox-custom task-checkbox"><input type="checkbox"><span class="checkmark"></span></label>
                            <div class="task-content"><input type="text" class="form-control" value="图表制作" style="border: none; padding-left: 0;"></div>
                            <div class="task-actions" style="display: flex;"><button class="button-icon"><i class="fas fa-trash-alt"></i></button></div>
                        </li>
                    </ul>
                    <form style="display: flex;" onsubmit="return false;">
                        <input type="text" class="form-control" placeholder="添加子任务...">
                        <button type="submit" class="button button-primary" style="margin-left: 0.5em; padding: 0.4em 0.8em;">添加</button>
                    </form>
                </section>
            </div>
            <div class="modal-footer">
                <button type="button" class="button button-danger" style="margin-right: auto;"><i class="fas fa-trash-alt"></i> 删除任务</button>
                <button type="button" class="button" onclick="closeModal('task-detail-modal')">取消</button>
                <button type="button" class="button button-primary" onclick="closeModal('task-detail-modal')">保存更改</button>
            </div>
        </div>
    </div>
</div>
```

- [ ] **Step 2: 删除旧片段文件**

```bash
git rm public/design/task-detail.html
```

- [ ] **Step 3: 验证**

Run: `open public/design/tasks.html`
Expected: 点任意任务标题或编辑图标弹出详情；弹窗含标题/备注/项目/截止/提醒/关联计划/象限单选（无优先级下拉）/子任务清单；取消与保存均可关闭。

- [ ] **Step 4: Commit**

```bash
git add public/design/tasks.html
git commit -m "design: embed aligned task-detail modal and remove standalone fragment"
```

---

### Task 12: 清理 style.css 中废弃的 priority 类

**Files:**
- Modify: `public/design/style.css`（删除 `.priority-dot`、`.priority-high`、`.priority-medium`、`.priority-low` 四条规则）

- [ ] **Step 1: 确认无残留引用**

Run: `grep -rn "priority-" public/design/`
Expected: 仅命中 style.css 自身的定义行（Task 4/10/11 已移除 dashboard.html 与 tasks.html 的全部使用处）。若有其它命中，先修复再继续。

- [ ] **Step 2: 删除 style.css 中这四条规则**

删除以下整块：

```css
.priority-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 5px;
    vertical-align: middle;
}

.priority-high {
    background-color: #ff4d4f;
}

.priority-medium {
    background-color: #faad14;
}

.priority-low {
    background-color: #1890ff;
}
```

- [ ] **Step 3: 验证**

Run: `open public/design/dashboard.html && open public/design/tasks.html`
Expected: 两页渲染正常，象限色点不受影响。

- [ ] **Step 4: Commit**

```bash
git add public/design/style.css
git commit -m "design: drop obsolete priority classes from prototype stylesheet"
```

---

## Self-Review

- **Spec coverage**：schedule-week spec 的验收标准逐条对应 Task 6（独立打开、粒度切换）、Task 7（单日拖拽、跨天多选）、Task 8（表单+象限+事件块、纯前端状态）✓；蓝图对齐项：matrix 配色（Task 3）、dashboard 旗标（Task 4）、habits 默认象限（Task 5）、tasks/task-detail 补全（Task 10/11）、calendar-day 重做（Task 9）、侧边栏统一（Task 2）✓。
- **Placeholder scan**：Task 6 的空 `refreshSelection` 与 Task 10 的弹窗注释是任务间的显式接缝（后续任务整体替换），已在文中标注；无其它 TBD。
- **Type consistency**：`QUADRANTS` 键名与蓝图 `QuadrantType` 枚举一致（urgent_important 等）；`mergedRanges()` 返回 `{day,start,end}` 与 Task 8 消费处一致；`openModal/closeModal` 签名在 Task 10/11 一致。
