<template>
  <div class="goal-page">
    <div class="goal-header">
      <h2>计划与目标</h2>
      <n-button type="primary" @click="openCreateModal">+ 添加计划</n-button>
    </div>

    <section>
      <h3>进行中的计划</h3>
      <div v-for="goal in goals" :key="goal.id" class="goal-item">
        <div class="goal-content">
          <span class="goal-title">{{ goal.name }}</span>
          <div class="goal-meta">
            <span v-if="goal.target_date">目标日期: {{ goal.target_date }}</span>
            <span v-else>无目标日期</span>
            <span>关联任务: {{ goal.task_completed }}/{{ goal.task_total }}</span>
            <span v-if="goal.habit_count">关联习惯: {{ goal.habit_count }} 个</span>
          </div>
          <div class="progress-bar">
            <div class="progress-bar-inner" :style="{ width: progressPercent(goal) + '%' }"></div>
          </div>
        </div>
        <div class="goal-actions">
          <n-button size="small" @click="openDetail(goal)">查看详情</n-button>
          <n-dropdown trigger="click" :options="activeGoalOptions" @select="(key) => handleAction(key, goal)">
            <button class="goal-more-btn" @click.stop>⋯</button>
          </n-dropdown>
        </div>
      </div>
      <n-empty v-if="!goals.length" description="还没有计划，点右上角添加一个" />
    </section>

    <n-collapse v-if="archivedGoals.length" class="archived-collapse">
      <n-collapse-item title="已归档计划" name="archived">
        <div v-for="goal in archivedGoals" :key="goal.id" class="goal-item archived">
          <div class="goal-content">
            <span class="goal-title">{{ goal.name }}</span>
          </div>
          <div class="goal-actions">
            <n-button size="small" @click="openDetail(goal)">查看详情</n-button>
            <n-button size="small" @click="handleAction('unarchive', goal)">恢复</n-button>
            <n-button size="small" quaternary type="error" @click="handleAction('delete', goal)">删除</n-button>
          </div>
        </div>
      </n-collapse-item>
    </n-collapse>

    <GoalFormModal v-model:show="showFormModal" :goal="editingGoal" @saved="fetchAll" />
    <GoalDetailModal v-model:show="showDetailModal" :goal-id="detailGoalId" />
  </div>
</template>

<script setup>
import { ref, onActivated } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import api from '@/api'
import GoalFormModal from './GoalFormModal.vue'
import GoalDetailModal from './GoalDetailModal.vue'

defineOptions({ name: '计划' })

const message = useMessage()
const dialog = useDialog()

const goals = ref([])
const archivedGoals = ref([])
const showFormModal = ref(false)
const editingGoal = ref(null)
const showDetailModal = ref(false)
const detailGoalId = ref(null)

const activeGoalOptions = [
  { label: '编辑', key: 'edit' },
  { label: '归档', key: 'archive' },
  { label: '删除', key: 'delete' }
]

const progressPercent = (goal) =>
  goal.task_total ? Math.min(100, (goal.task_completed / goal.task_total) * 100) : 0

const fetchGoals = async () => {
  try {
    const res = await api.getGoals()
    goals.value = res.data || []
  } catch (error) {
    console.error('获取计划列表失败:', error)
    message.error('获取计划列表失败')
  }
}

const fetchArchivedGoals = async () => {
  try {
    const res = await api.getArchivedGoals()
    archivedGoals.value = res.data || []
  } catch (error) {
    console.error('获取归档计划失败:', error)
    message.error('获取归档计划失败')
  }
}

const fetchAll = () => Promise.all([fetchGoals(), fetchArchivedGoals()])

const openCreateModal = () => {
  editingGoal.value = null
  showFormModal.value = true
}

const openDetail = (goal) => {
  detailGoalId.value = goal.id
  showDetailModal.value = true
}

const updateGoalField = async (goal, data) => {
  try {
    await api.updateGoal(goal.id, data)
    fetchAll()
  } catch (error) {
    console.error('更新计划失败:', error)
    message.error('更新计划失败')
  }
}

const confirmDelete = (goal) => {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除计划「${goal.name}」吗？关联的任务和习惯会保留，只是解除关联。`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.deleteGoal(goal.id)
        message.success('删除成功')
        fetchAll()
      } catch (error) {
        console.error('删除计划失败:', error)
        message.error('删除失败')
      }
    }
  })
}

const handleAction = (key, goal) => {
  if (key === 'edit') {
    editingGoal.value = goal
    showFormModal.value = true
  } else if (key === 'archive') {
    updateGoalField(goal, { is_archived: true })
  } else if (key === 'unarchive') {
    updateGoalField(goal, { is_archived: false })
  } else if (key === 'delete') {
    confirmDelete(goal)
  }
}

// onActivated 同时覆盖首次挂载和每次 KeepAlive 重新激活（Vue 首次挂载也会触发 onActivated），
// 不需要再额外写 onMounted，否则首次进入页面会重复请求两次
onActivated(fetchAll)
</script>

<style scoped>
.goal-page {
  max-width: 900px;
}
.goal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5em;
}
.goal-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1em;
  padding: 0.8em 0.2em;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
}
.goal-item.archived {
  opacity: 0.7;
}
.goal-content {
  flex: 1;
  min-width: 0;
}
.goal-title {
  font-size: 1em;
  font-weight: 500;
}
.goal-meta {
  display: flex;
  gap: 1em;
  font-size: 0.82em;
  opacity: 0.7;
  margin-top: 0.2em;
}
.progress-bar {
  height: 6px;
  border-radius: 3px;
  background: rgba(128, 128, 128, 0.15);
  margin-top: 0.5em;
  overflow: hidden;
}
.progress-bar-inner {
  height: 100%;
  background: #1890ff;
  transition: width 0.2s;
}
.goal-actions {
  display: flex;
  align-items: center;
  gap: 0.5em;
  flex-shrink: 0;
}
.goal-more-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 0.2em 0.5em;
  border-radius: 4px;
  color: inherit;
  opacity: 0.6;
  line-height: 1;
}
.goal-more-btn:hover {
  opacity: 1;
  background: rgba(128, 128, 128, 0.15);
}
.archived-collapse {
  margin-top: 2em;
}
</style>
