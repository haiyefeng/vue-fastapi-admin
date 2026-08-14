<template>
  <div class="dashboard-page">
    <div class="dashboard-header">
      <h2>今日概览</h2>
      <p class="dashboard-date">{{ todayLabel }}</p>
    </div>

    <section class="quick-add">
      <n-input
        v-model:value="quickAddTitle"
        placeholder="添加任务到收件箱 (按 Enter 保存)"
        @keyup.enter="handleQuickAdd"
      />
      <n-button type="primary" @click="handleQuickAdd">添加</n-button>
    </section>

    <div class="dashboard-grid">
      <section class="dashboard-card">
        <h3>今日日程</h3>
        <div
          v-for="block in schedule"
          :key="block.id"
          class="schedule-row"
          @click="openDetail(block.todo_item_id)"
        >
          <span
            class="quadrant-dot"
            :style="{ background: quadrantColor(block.quadrant_type) }"
          ></span>
          <span>{{ formatTimeRange(block.start_time, block.end_time) }} {{ block.title }}</span>
        </div>
        <n-empty v-if="!schedule.length" description="今天还没有安排" size="small">
          <template #extra>
            <n-button text type="primary" @click="router.push('/todo/schedule')"
              >查看完整日历</n-button
            >
          </template>
        </n-empty>
      </section>

      <section class="dashboard-card">
        <h3>今日待办</h3>
        <div v-for="task in tasks" :key="task.id" class="task-row">
          <n-checkbox :checked="false" @update:checked="() => toggleTaskComplete(task)" />
          <span
            class="quadrant-dot"
            :style="{ background: quadrantColor(task.quadrant_type) }"
          ></span>
          <span class="task-title" @click="openDetail(task.id)">{{ task.title }}</span>
        </div>
        <n-empty v-if="!tasks.length" description="今天没有待办事项" size="small">
          <template #extra>
            <n-button text type="primary" @click="router.push('/todo/tasks')"
              >查看所有任务</n-button
            >
          </template>
        </n-empty>
      </section>

      <section class="dashboard-card">
        <h3>今日习惯</h3>
        <div v-for="habit in habits" :key="habit.id" class="habit-row">
          <div class="habit-content">
            <span class="habit-name">{{ habit.name }}</span>
            <span class="habit-meta">{{ habitMetaLabel(habit) }}</span>
          </div>
          <n-button
            size="small"
            :type="habit.today_completed ? 'default' : 'primary'"
            :disabled="habit.today_completed"
            @click="checkInHabit(habit)"
          >
            {{ habit.today_completed ? '已打卡 ✓' : '打卡' }}
          </n-button>
        </div>
        <n-empty v-if="!habits.length" description="今天没有需要打卡的习惯" size="small">
          <template #extra>
            <n-button text type="primary" @click="router.push('/todo/habit')">管理习惯</n-button>
          </template>
        </n-empty>
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

defineOptions({ name: '今日' })

const router = useRouter()
const message = useMessage()

const schedule = ref([])
const tasks = ref([])
const habits = ref([])
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

const todayLabel = computed(() => {
  const now = new Date()
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  return `${weekdays[now.getDay()]}，${now.getFullYear()}年${
    now.getMonth() + 1
  }月${now.getDate()}日`
})

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
  if (habit.streak !== null && habit.streak !== undefined) parts.push(`连续坚持 ${habit.streak} 天`)
  if (habit.week_progress) parts.push(`本周 ${habit.week_progress}`)
  return parts.join(' · ')
}

const loadToday = async () => {
  try {
    const res = await api.getTodayOverview()
    schedule.value = res.data.schedule || []
    tasks.value = res.data.tasks || []
    habits.value = res.data.habits || []
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
  margin-bottom: 1em;
}
.dashboard-header h2 {
  margin: 0;
}
.dashboard-date {
  opacity: 0.6;
  margin: 0.2em 0 0;
}
.quick-add {
  display: flex;
  gap: 0.5em;
  margin-bottom: 1.5em;
}
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5em;
}
.dashboard-card h3 {
  margin: 0 0 0.8em;
  font-size: 1em;
}
.schedule-row {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.4em 0;
  cursor: pointer;
}
.task-row {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.4em 0;
}
.task-title {
  cursor: pointer;
}
.quadrant-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.habit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.5em 0;
}
.habit-content {
  display: flex;
  flex-direction: column;
  gap: 0.2em;
}
.habit-meta {
  font-size: 0.82em;
  opacity: 0.7;
}
</style>
