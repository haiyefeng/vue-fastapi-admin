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
            <div class="card-icon-badge schedule">
              <TheIcon icon="material-symbols:schedule-outline" :size="15" />
            </div>
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
            <div class="card-icon-badge tasks">
              <TheIcon icon="material-symbols:check-circle-outline" :size="15" />
            </div>
            <h3>今日待办</h3>
          </div>
          <span v-if="tasks.length" class="card-count">{{ tasks.length }} 项</span>
        </div>
        <div v-for="task in tasks" :key="task.id" class="task-row">
          <n-checkbox :checked="false" @update:checked="() => toggleTaskComplete(task)" />
          <span
            class="quadrant-bar"
            :style="{ background: quadrantColor(task.quadrant_type) }"
          ></span>
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
            <div class="card-icon-badge habits">
              <TheIcon icon="material-symbols:sync" :size="15" />
            </div>
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
import { useMessage } from 'naive-ui'
import api from '@/api'
import TaskDetailModal from '../TaskList/TaskDetailModal.vue'
import TheIcon from '@/components/icon/TheIcon.vue'
import EmptyState from '@/components/common/EmptyState.vue'

defineOptions({ name: '今日' })

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
  not_urgent_not_important: '#909399',
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
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
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
  transition: box-shadow 0.25s ease, transform 0.25s ease;
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
  background: var(--dt-surface-subtle);
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
  background: var(--dt-surface-subtle);
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
  background: var(--dt-surface-subtle);
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
