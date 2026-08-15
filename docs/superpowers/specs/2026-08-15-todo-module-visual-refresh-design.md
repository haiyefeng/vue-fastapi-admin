# 待办事项模块视觉优化设计

## 背景

一至四期把待办事项模块（任务、日历、四象限、习惯、计划、回顾总结、今日概览、待办统计，共 8 个页面）的功能全部落地了，但视觉上完全是 Naive UI 默认组件的堆叠：扁平列表、无层次的卡片、重复散落在各文件里的十六进制色值、干巴巴的"暂无数据"空状态。用户反馈"和常规应用一样，没有辨识度，不吸引人"。

本设计通过一份静态 HTML mockup（`今日概览`页的视觉方向稿）确定了方向：**清新现代、有精致细节**，在保留产品现有品牌色的基础上，把列表升级成有层次感的卡片，加入图标徽标、更讲究的空状态、细腻的 hover/交互反馈。mockup 已经过用户确认。

## 范围

- 覆盖待办事项模块全部 8 个页面：今日概览、四象限待办、待办统计、任务列表、日历（周/日视图）、习惯、计划、回顾总结。
- **只做视觉层面的优化**：配色、圆角、阴影、图标、空状态、间距、hover/过渡效果。**不改变任何业务逻辑、数据结构、路由**；API 层面同样以不改动为原则，唯一例外是今日概览完成度圆环需要的两个只读汇总字段（见"今日概览"一节），这是本次设计里唯一涉及后端的改动点。
- **日历页（周/日视图）刻意保守**：这是模块内交互最复杂的页面（拖拽排程、多选、时间轴坐标计算），只做外观打磨（事件块圆角/阴影、当前时间线样式、hover 反馈），不触碰任何交互代码。
- 平台级的全局主色（`web/settings/theme.json` 里的橙色）、登录页、系统管理模块（用户/角色/菜单/API/部门/审计日志）**不在本次范围内**，保持现状。
- 不引入新的前端依赖（图标继续用项目已有的 `@iconify/vue` + Material Symbols，不引入 Font Awesome 等）。

## 设计基础设施

### 设计 Token（新文件）

新建 `web/src/styles/design-tokens.scss`，在 `web/src/styles/global.scss` 顶部 `@use` 引入。定义一套语义化 CSS 自定义属性，8 个页面共用，不再各自硬编码 magic number：

```scss
:root {
  // 圆角
  --dt-radius-sm: 10px;
  --dt-radius-md: 14px;
  --dt-radius-lg: 20px;

  // 阴影（浅色主题；暗色主题在 [data-theme='dark'] 里覆盖，透明度调高、去掉冷色调）
  --dt-shadow-sm: 0 1px 2px rgba(28, 25, 23, 0.04), 0 1px 1px rgba(28, 25, 23, 0.03);
  --dt-shadow-md: 0 4px 16px rgba(28, 25, 23, 0.06), 0 1px 4px rgba(28, 25, 23, 0.04);
  --dt-shadow-lg: 0 12px 32px rgba(28, 25, 23, 0.08), 0 2px 8px rgba(28, 25, 23, 0.04);

  // 四象限语义色——数值照抄现有代码里反复出现的十六进制（TaskList/TodoQuadrant/Schedule/TaskDetailModal
  // 等文件里各自硬编码的同一组颜色），这里只是集中定义，不改变任何一个色值本身
  --dt-quadrant-urgent-important: #f5222d;
  --dt-quadrant-urgent-not-important: #faad14;
  --dt-quadrant-important-not-urgent: #1890ff;
  --dt-quadrant-not-urgent-not-important: #909399;

  // 板块辅助色（日程/习惯专属，四象限之外的语义色，全新引入）
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

暗色主题的判定复用现有 `appStore.isDark` 机制——`AppProvider.vue` 已经在 `<n-config-provider>` 上根据 `appStore.isDark` 切换 `darkTheme`；这里额外在根元素加一个 `data-theme` attribute（在 `AppProvider.vue` 的 `setupCssVar` 附近新增几行，`watch(() => appStore.isDark, ...)` 同步到 `document.documentElement.dataset.theme`），供上面这套 token 的 `[data-theme='dark']` 选择器使用。四象限色/日程色/习惯色本身在深浅色主题下不变（保持可识别性），只有中性色阶、阴影透明度需要跟着切换。

### Naive UI 组件视觉调整（改为页面级 scoped 样式，不用全局主题覆盖）

最初考虑过在 `web/settings/theme.json` 的 `naiveThemeOverrides` 里加 `Card`/`Button`/`Modal` 组件级 override 来统一圆角/阴影。**写计划阶段核实 Naive UI 源码后发现这个思路有问题并已改正**：`naiveThemeOverrides` 是通过唯一的一个 `<n-config-provider>` 全局生效的，组件级 override（哪怕只写 `Card.borderRadius`）会影响应用里**每一个** `n-card`/`n-button` 实例，包括系统管理模块（用户/角色/菜单/API/部门/审计日志）——直接违反本设计"系统管理模块不在本次范围内"的边界。

改为：每个待办模块页面在自己的 `<style scoped>` 里用 Vue 的 `:deep()` 选择器覆盖该页面内渲染的 `n-card`/`n-button` 样式（如 `:deep(.n-card) { border-radius: var(--dt-radius-lg); box-shadow: var(--dt-shadow-sm); }`）。`scoped` 样式天然只作用于当前组件模板范围内渲染的元素，不会外溢到其他页面，这是 Vue 里"局部覆盖第三方组件库默认样式"的标准做法，不需要引入任何新机制。

### 共享空状态组件（新组件，唯一值得抽取共享的部分）

新建 `web/src/components/common/EmptyState.vue`：

```vue
<template>
  <div class="empty-state">
    <div class="empty-state-icon"><TheIcon :icon="icon" :size="18" /></div>
    <div class="empty-state-text">{{ text }}</div>
    <n-button v-if="linkText" text type="primary" class="empty-state-link" @click="$emit('link-click')">
      {{ linkText }}
      <template #icon><TheIcon icon="material-symbols:arrow-forward" :size="12" /></template>
    </n-button>
  </div>
</template>

<script setup>
import TheIcon from '@/components/icon/TheIcon.vue'

defineProps({
  icon: { type: String, required: true },
  text: { type: String, required: true },
  linkText: { type: String, default: '' }
})
defineEmits(['link-click'])
</script>
```

这是本次设计基础设施里唯一预先确定要抽成共享组件的东西——因为它是完全相同的展示结构（图标徽标 + 文案 + 可选引导链接），不是"各页面各写一份"那类小格式化函数（`frequencyLabel`/`quadrantColor` 这类继续保持现有的"每个文件自己写一份"的既定做法，不因为这次视觉优化而改变代码组织原则）。任务列表页还涉及另一个可能共享的组件（`QuickAddInput.vue`），但那是视具体实现情况才能判断的个例，见"任务列表"与"已知边缘情况"两节，不在这里预先定死。

## 各页面设计要点

### 今日概览（`Dashboard/index.vue`）

已通过 mockup 确认，直接照此落地：
- 顶部问候语区块：`星期X · M月D日` 小字 + `{{ 时段问候 }}，欢迎回来` 大标题（问候语按当前时间分早上好/下午好/晚上好，纯前端计算，不依赖后端）+ 副标题文案汇总"今天有 N 件事等着你，M 个习惯待打卡"（`tasks.length` + `habits.filter(h => !h.today_completed).length`）。
- 右上角完成度圆环：`SVG` 画一个圆环进度条，数值 = 已完成任务数 / (今日待办数 + 今日待办已完成数)——**这个统计目前后端不提供**（`/dashboard/today` 只返回未完成任务），需要小改动：给 `TodayOverviewOut` 加两个只读汇总字段 `completed_task_count`/`total_task_count`（后端顺带统计一下今天到期或排程的任务总数，含已完成的），这是本次视觉优化里唯一涉及后端接口改动的地方。
- 快速添加输入框改胶囊形状 + focus 态外发光。
- 三个区块卡片：图标徽标（日程=靛蓝时钟图标、待办=橙色勾选图标、习惯=绿色循环图标）+ 计数徽标。
- 任务行：象限色条（`--dt-quadrant-*`）替代原来的圆点，checkbox 改自定义圆角方块。
- 习惯行：emoji 图标徽标（复用 `habit.icon` 字段，为空时用默认表情）+ 火焰图标连续天数。
- 空状态用 `EmptyState.vue`。

### 四象限待办（`TodoQuadrant/index.vue`）

已经是 `n-card` 2x2 网格，改动范围小：
- 四个 `n-card` 标题栏加对应象限色的图标徽标（复用 `--dt-quadrant-*`）。
- `todo-item` 行加 hover 态（轻微上浮 + 阴影），checkbox 圆角化。
- 拖拽中的视觉反馈（`dragover` 态）加一层强调色边框，提升可用性顺带更精致。
- 空状态用 `EmptyState.vue`。

### 待办统计（`TodoHistory/index.vue`）

- 统计数字（完成率等核心指标）用更大更粗的数字排版，视觉权重对齐今日概览的完成度圆环数字。
- 图表色板对齐 `--dt-quadrant-*`，避免图表颜色和其他页面的象限配色不一致。
- 统计区块整体卡片化（圆角、阴影 token）。

### 任务列表（`TaskList/index.vue`）

- 快速添加框改胶囊样式（跟今日概览一致的组件级样式，可考虑抽成 `QuickAddInput.vue` 共享组件，因为这是今日概览和任务列表两处完全相同的交互，符合"结构相同才共享"的标准，不同于象限颜色这类简单格式化）。
- 任务行的圆点替换成象限色条，hover 态加背景色过渡。
- 项目导航栏（`ProjectNav.vue`）的选中态、hover 态精致化。

### 日历（`Schedule/WeekView.vue` / `DayView.vue`）

**保守范围**，只动样式不动逻辑：
- `.event-block` 圆角对齐 `--dt-radius-sm`，加轻阴影。
- 当前时间线（如果已有）颜色/粗细调整为更醒目但不突兀。
- 拖拽/多选态的视觉反馈精致化（边框/背景色过渡动画）。
- **不改**：拖拽逻辑、时间轴计算、多选交互、`toLocalIsoString` 等已经过多轮 bug 修复的时区处理代码——这些是本项目里踩坑最多的部分，本次不碰。

### 习惯（`Habit/index.vue`）

- 每个习惯行卡片化（圆角、阴影、hover 上浮），emoji 图标徽标（复用 mockup 的处理）。
- 连续天数用火焰图标 + 数字，替代纯文字"连续坚持 N 天"。
- 打卡按钮态：未打卡=品牌色实心按钮，已打卡=浅绿背景+勾选图标的禁用态（跟 mockup 一致）。
- 归档折叠区块保持现状（次要信息，不需要同等视觉权重）。

### 计划（`Goal/index.vue`）

- 每个计划行卡片化，图标徽标（用计划名称首字或固定的旗帜图标）。
- 进度条加粗、圆角化、上色（进度条颜色可用 `--dt-habit` 绿色系，呼应"进展"的语义）。
- 归档折叠区块保持现状。

### 回顾总结（`Review/index.vue`）

- 数据回顾三个卡片对齐今日概览的卡片视觉规范（圆角、阴影、图标徽标）。
- 七步反思的卡片排版：标题字重加粗、引导文案颜色用 `--dt-ink-muted`、卡片间距对齐 token。
- 保存草稿/完成本次回顾按钮精致化（主按钮用品牌色，次按钮用轮廓态）。

## 已知边缘情况

- **今日概览的完成度圆环需要一个小的后端改动**（`TodayOverviewOut` 新增 `completed_task_count`/`total_task_count` 两个字段），这是本次视觉优化里唯一涉及后端的部分，其余 7 个页面纯前端改动，不碰任何 API。
- **暗色主题**：`design-tokens.scss` 里已经规划了 `[data-theme='dark']` 覆盖层，但四象限色/日程色/习惯色本身不随主题切换（保持跨主题一致的语义识别度）；实现时要确认 `AppProvider.vue` 正确把 `data-theme` attribute 同步到根元素，并且验证深色模式下的可读性（不是这次的重点验收项，但不能因为这次改动而在深色模式下出现不可读的情况）。
- **象限色统一到 CSS 变量后，不要求一次性把所有硬编码色值文件全部替换**——8 个页面各自的改动范围里，涉及到的地方顺手换成变量；不属于本次改动范围的文件（如已经很稳定、这次不涉及视觉调整的部分）如果还有硬编码色值，不强制在这次一起清理，避免不必要的改动面扩大。
- **`QuickAddInput.vue` 是否抽取为共享组件**是任务列表 + 今日概览两处的判断，其余共享判断（`EmptyState.vue`）已经在"设计基础设施"一节明确；实现阶段如果发现两处的快速添加框在细节上有差异（比如 placeholder 逻辑不同），以能不能"结构完全一致只是文案不同"为标准决定要不要抽取，不能为了保持一致性强行抽取出参数化程度过高的组件。

## 验收标准

- 8 个页面视觉统一使用新的设计 token（圆角、阴影、四象限色不再是页面各自硬编码，日程色/习惯色新引入且跨页面一致）。
- 今日概览：问候语随时间变化、完成度圆环显示正确的完成/总数比例、三卡片+图标徽标+空状态组件均按 mockup 呈现。
- 四象限待办：四个象限卡片标题带图标徽标，任务行 hover 有视觉反馈，空状态用新组件。
- 任务列表：快速添加框胶囊样式，任务行象限色条替代圆点。
- 日历页：事件块视觉打磨到位，**拖拽/多选/排程等所有既有交互行为不受影响**（这是最容易踩坑的验收点，需要专门跑一遍二期日历排程的手动验证清单）。
- 习惯/计划页：列表行卡片化，图标徽标、进度条/打卡按钮态符合设计。
- 回顾总结：数据卡片与今日概览视觉对齐，反思步骤排版精致化。
- 暗色模式下 8 个页面均可正常查看，无因为新增 token 导致的对比度问题（不要求逐像素还原亮色模式的精致度，但不能有不可读的文字/背景组合）。
- 全部现有 pytest 后端测试（本次改动前的基线 + 新增的两个统计字段的测试）继续通过；前端 `pnpm exec eslint` 对改动文件干净。
