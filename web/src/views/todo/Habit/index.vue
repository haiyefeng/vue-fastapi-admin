<template>
  <div class="habit-page">
    <div class="habit-header">
      <h2>习惯追踪</h2>
      <n-button type="primary" @click="openCreateModal">+ 添加习惯</n-button>
    </div>

    <section>
      <h3>进行中的习惯</h3>
      <div v-for="habit in habits" :key="habit.id" class="habit-item" :class="{ paused: habit.is_paused }">
        <div class="habit-content">
          <span class="habit-title">
            <span v-if="habit.icon" class="habit-icon">{{ habit.icon }}</span>
            {{ habit.name }}
            <span v-if="habit.is_paused" class="paused-tag">(已暂停)</span>
          </span>
          <div class="habit-meta">
            <span>{{ frequencyLabel(habit) }}</span>
            <span v-if="habit.goal_desc">目标: {{ habit.goal_desc }}</span>
            <span v-if="habit.streak !== null">连续坚持 {{ habit.streak }} 天</span>
            <span v-if="habit.week_progress">本周 {{ habit.week_progress }}</span>
          </div>
          <div v-if="habit.week_progress" class="progress-bar">
            <div
              class="progress-bar-inner"
              :style="{ width: progressPercent(habit) + '%', background: habit.color_hex || '#1890ff' }"
            ></div>
          </div>
        </div>
        <div class="habit-actions">
          <n-button
            size="small"
            :type="habit.today_completed ? 'default' : 'primary'"
            :disabled="!habit.today_todo_id || habit.today_completed"
            @click="checkIn(habit)"
          >
            {{ habit.today_completed ? '已打卡 ✓' : '今日打卡' }}
          </n-button>
          <n-dropdown trigger="click" :options="activeHabitOptions" @select="(key) => handleAction(key, habit)">
            <button class="habit-more-btn" @click.stop>⋯</button>
          </n-dropdown>
        </div>
      </div>
      <EmptyState v-if="!habits.length" icon="material-symbols:eco-outline" text="还没有习惯，点右上角添加一个" />
    </section>

    <n-collapse v-if="archivedHabits.length" class="archived-collapse">
      <n-collapse-item title="已归档习惯" name="archived">
        <div v-for="habit in archivedHabits" :key="habit.id" class="habit-item archived">
          <div class="habit-content">
            <span class="habit-title">{{ habit.name }}</span>
          </div>
          <div class="habit-actions">
            <n-button size="small" @click="handleAction('unarchive', habit)">恢复</n-button>
            <n-button size="small" quaternary type="error" @click="handleAction('delete', habit)">删除</n-button>
          </div>
        </div>
      </n-collapse-item>
    </n-collapse>

    <HabitFormModal v-model:show="showFormModal" :habit="editingHabit" @saved="fetchAll" />
  </div>
</template>

<script setup>
import { ref, onActivated } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import api from '@/api'
import HabitFormModal from './HabitFormModal.vue'
import EmptyState from '@/components/common/EmptyState.vue'

defineOptions({ name: '习惯' })

const message = useMessage()
const dialog = useDialog()

const habits = ref([])
const archivedHabits = ref([])
const showFormModal = ref(false)
const editingHabit = ref(null)

const activeHabitOptions = [
  { label: '编辑', key: 'edit' },
  { label: '暂停/恢复', key: 'toggle-pause' },
  { label: '归档', key: 'archive' },
  { label: '删除', key: 'delete' }
]

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

const progressPercent = (habit) => {
  if (!habit.week_progress) return 0
  const [done, total] = habit.week_progress.split('/').map(Number)
  return total ? Math.min(100, (done / total) * 100) : 0
}

const fetchHabits = async () => {
  try {
    const res = await api.getHabits()
    habits.value = res.data || []
  } catch (error) {
    console.error('获取习惯列表失败:', error)
    message.error('获取习惯列表失败')
  }
}

const fetchArchivedHabits = async () => {
  try {
    const res = await api.getArchivedHabits()
    archivedHabits.value = res.data || []
  } catch (error) {
    console.error('获取归档习惯失败:', error)
    message.error('获取归档习惯失败')
  }
}

const fetchAll = () => Promise.all([fetchHabits(), fetchArchivedHabits()])

const openCreateModal = () => {
  editingHabit.value = null
  showFormModal.value = true
}

const checkIn = async (habit) => {
  if (!habit.today_todo_id) return
  try {
    await api.updateTodo(habit.today_todo_id, { is_completed: true })
    message.success('打卡成功')
    fetchAll()
  } catch (error) {
    console.error('打卡失败:', error)
    message.error('打卡失败')
  }
}

const updateHabitField = async (habit, data) => {
  try {
    await api.updateHabit(habit.id, data)
    fetchAll()
  } catch (error) {
    console.error('更新习惯失败:', error)
    message.error('更新习惯失败')
  }
}

const confirmDelete = (habit) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除习惯「${habit.name}」吗？它的所有历史打卡记录也会被一并删除，且不可恢复。`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.deleteHabit(habit.id)
        message.success('删除成功')
        fetchAll()
      } catch (error) {
        console.error('删除习惯失败:', error)
        message.error('删除失败')
      }
    }
  })
}

const handleAction = (key, habit) => {
  if (key === 'edit') {
    editingHabit.value = habit
    showFormModal.value = true
  } else if (key === 'toggle-pause') {
    updateHabitField(habit, { is_paused: !habit.is_paused })
  } else if (key === 'archive') {
    updateHabitField(habit, { is_archived: true })
  } else if (key === 'unarchive') {
    updateHabitField(habit, { is_archived: false })
  } else if (key === 'delete') {
    confirmDelete(habit)
  }
}

// onActivated covers both the initial mount and every KeepAlive re-activation
// (Vue fires it on first mount too), so a separate onMounted call would double-fetch.
onActivated(fetchAll)
</script>

<style scoped>
.habit-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px 24px;
  height: 100%;
  overflow-y: auto;
}
.habit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5em;
}
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
  border-radius: 0;
  background: transparent;
  opacity: 0.7;
}
.habit-item.paused {
  opacity: 0.5;
}
.habit-content {
  flex: 1;
  min-width: 0;
}
.habit-title {
  font-size: 1em;
  font-weight: 500;
}
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
.paused-tag {
  font-size: 0.8em;
  opacity: 0.6;
  margin-left: 0.4em;
}
.habit-meta {
  display: flex;
  gap: 1em;
  font-size: 0.82em;
  opacity: 0.7;
  margin-top: 0.2em;
}
.progress-bar {
  height: 8px;
  border-radius: 4px;
  background: var(--dt-surface-subtle, rgba(128, 128, 128, 0.15));
  margin-top: 0.6em;
  overflow: hidden;
}
.progress-bar-inner {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}
.habit-actions {
  display: flex;
  align-items: center;
  gap: 0.5em;
  flex-shrink: 0;
}
.habit-more-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0.2em 0.5em;
  border-radius: 4px;
  color: inherit;
  opacity: 0.6;
  line-height: 1;
}
.habit-more-btn:hover {
  opacity: 1;
  background: rgba(128, 128, 128, 0.15);
}
.archived-collapse {
  margin-top: 2em;
}
</style>
