<template>
  <div class="task-list-page">
    <div class="tasks-layout">
      <ProjectNav ref="projectNavRef" @select="handleSelect" @changed="fetchProjectList" />

      <div class="task-area">
        <div class="task-area-header">
          <h2>{{ headerTitle }}</h2>
          <div class="toolbar">
            <n-select
              v-model:value="sortBy"
              :options="sortOptions"
              size="small"
              style="width: 140px"
              @update:value="fetchTodos"
            />
            <n-select
              v-model:value="filterStatus"
              :options="statusOptions"
              size="small"
              style="width: 110px"
              @update:value="fetchTodos"
            />
            <n-select
              v-model:value="filterQuadrants"
              :options="quadrantOptions"
              multiple
              clearable
              size="small"
              placeholder="全部象限"
              style="width: 180px"
              @update:value="fetchTodos"
            />
          </div>
        </div>

        <div class="quick-add">
          <n-input
            v-model:value="quickAddTitle"
            :placeholder="quickAddPlaceholder"
            @keyup.enter="handleQuickAdd"
          />
          <n-button type="primary" @click="handleQuickAdd">添加</n-button>
        </div>

        <div v-for="group in groupedTodos" :key="group.key" class="task-group">
          <h4 v-if="group.items.length" class="group-title" :style="{ color: group.color }">{{ group.label }}</h4>
          <div
            v-for="todo in group.items"
            :key="todo.id"
            class="task-item"
            :class="{ completed: todo.is_completed }"
          >
            <n-checkbox :checked="todo.is_completed" @update:checked="(v) => toggleComplete(todo, v)" />
            <div class="task-content" @click="openDetail(todo.id)">
              <span class="task-title">{{ todo.title }}</span>
              <div class="task-meta">
                <span v-if="todo.due_date" :class="{ overdue: isOverdue(todo) }">
                  {{ formatDueDate(todo.due_date) }}
                </span>
                <span v-else>无截止时间</span>
                <span>
                  <span class="quadrant-bar" :style="{ background: quadrantColor(todo.quadrant_type) }"></span>
                  {{ quadrantLabel(todo.quadrant_type) }}
                </span>
                <span v-if="todo.subtask_total">{{ todo.subtask_completed }}/{{ todo.subtask_total }} 子任务</span>
              </div>
            </div>
          </div>
        </div>

        <n-empty v-if="!todos.length" description="暂无任务" />
      </div>
    </div>

    <TaskDetailModal
      v-model:show="detailShow"
      :todo-id="detailTodoId"
      :projects="projectList"
      @saved="fetchTodos"
      @deleted="fetchTodos"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import api from '@/api'
import ProjectNav from './ProjectNav.vue'
import TaskDetailModal from './TaskDetailModal.vue'

const message = useMessage()

const projectNavRef = ref(null)
const selection = ref({ type: 'inbox' })
const projectList = ref([])
const todos = ref([])
const quickAddTitle = ref('')
const detailShow = ref(false)
const detailTodoId = ref(null)

const sortBy = ref('created_at')
const filterStatus = ref('incomplete')
const filterQuadrants = ref([])

const sortOptions = [
  { label: '按截止时间', value: 'due_date' },
  { label: '按象限', value: 'quadrant_type' },
  { label: '按创建时间', value: 'created_at' }
]
const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '未完成', value: 'incomplete' },
  { label: '已完成', value: 'completed' }
]
const quadrantMeta = {
  urgent_important: { label: '重要且紧急', color: '#f5222d' },
  urgent_not_important: { label: '紧急不重要', color: '#faad14' },
  important_not_urgent: { label: '重要不紧急', color: '#1890ff' },
  not_urgent_not_important: { label: '不紧急不重要', color: '#909399' }
}
const quadrantOptions = Object.entries(quadrantMeta).map(([value, meta]) => ({ label: meta.label, value }))
const quadrantLabel = (type) => quadrantMeta[type]?.label || type
const quadrantColor = (type) => quadrantMeta[type]?.color || '#909399'

const headerTitle = computed(() => (selection.value.type === 'inbox' ? '收件箱' : selection.value.name))
const quickAddPlaceholder = computed(() =>
  selection.value.type === 'inbox' ? '添加任务到收件箱 (按 Enter 保存)' : '添加任务到当前项目 (按 Enter 保存)'
)

const fetchProjectList = async () => {
  try {
    const res = await api.getProjects()
    projectList.value = res.data || []
  } catch (error) {
    console.error('获取项目列表失败:', error)
    message.error('获取项目列表失败')
  }
}

const fetchTodos = async () => {
  const params = {
    page: 1,
    page_size: 200,
    sort_by: sortBy.value,
    sort_order: sortBy.value === 'created_at' ? 'desc' : 'asc'
  }
  if (selection.value.type === 'inbox') {
    params.inbox_only = true
  } else {
    params.project_id = selection.value.id
  }
  if (filterStatus.value === 'incomplete') params.is_completed = false
  if (filterStatus.value === 'completed') params.is_completed = true
  if (filterQuadrants.value.length) params.quadrant_type = filterQuadrants.value.join(',')

  try {
    const res = await api.getTodos(params)
    todos.value = res.data || []
  } catch (error) {
    console.error('获取任务列表失败:', error)
    message.error('获取任务列表失败')
  }
}

const handleSelect = (payload) => {
  selection.value = payload
  fetchTodos()
}

const handleQuickAdd = async () => {
  const title = quickAddTitle.value.trim()
  if (!title) return
  const payload = { title, quadrant_type: 'not_urgent_not_important' }
  if (selection.value.type === 'project') payload.project_id = selection.value.id
  try {
    await api.createTodo(payload)
    quickAddTitle.value = ''
    message.success('已添加')
    fetchTodos()
  } catch (error) {
    console.error('添加任务失败:', error)
    message.error('添加任务失败')
  }
}

const toggleComplete = async (todo, checked) => {
  const previous = todo.is_completed
  todo.is_completed = checked
  try {
    await api.updateTodo(todo.id, { is_completed: checked })
    fetchTodos()
  } catch (error) {
    console.error('更新任务状态失败:', error)
    message.error('更新任务状态失败')
    todo.is_completed = previous
  }
}

const openDetail = (todoId) => {
  detailTodoId.value = todoId
  detailShow.value = true
}

const isOverdue = (todo) => {
  if (todo.is_completed || !todo.due_date) return false
  return new Date(todo.due_date).getTime() < startOfToday()
}

const startOfToday = () => {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d.getTime()
}

const formatDueDate = (dueDate) => {
  const date = new Date(dueDate)
  return date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const groupedTodos = computed(() => {
  const today = startOfToday()
  const tomorrow = today + 24 * 60 * 60 * 1000
  const overdue = []
  const todayItems = []
  const later = []

  for (const todo of todos.value) {
    if (!todo.due_date) {
      later.push(todo)
      continue
    }
    const due = new Date(todo.due_date).getTime()
    if (due < today) {
      overdue.push(todo)
    } else if (due >= today && due < tomorrow) {
      todayItems.push(todo)
    } else {
      later.push(todo)
    }
  }

  return [
    { key: 'overdue', label: '已过期', color: '#f5222d', items: overdue },
    { key: 'today', label: '今天', color: '#1890ff', items: todayItems },
    { key: 'later', label: '稍后', color: '', items: later }
  ]
})

onMounted(() => {
  fetchProjectList()
})
</script>

<style scoped>
.tasks-layout {
  display: flex;
  gap: 1.5em;
  align-items: flex-start;
}
.task-area {
  flex: 1;
  min-width: 0;
}
.task-area-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1em;
}
.toolbar {
  display: flex;
  gap: 0.5em;
}
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
.group-title {
  margin: 1em 0 0.5em 0.2em;
  font-size: 0.9em;
  font-weight: 600;
}
.task-item {
  display: flex;
  align-items: center;
  gap: 0.6em;
  padding: 0.6em 0.5em;
  border-radius: var(--dt-radius-sm);
  transition: background 0.15s ease;
}
.task-item:hover {
  background: var(--dt-surface-subtle);
}
.task-item.completed .task-title {
  text-decoration: line-through;
  opacity: 0.5;
}
.task-content {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}
.task-title {
  display: block;
}
.task-meta {
  display: flex;
  gap: 1em;
  font-size: 0.82em;
  opacity: 0.7;
  margin-top: 0.2em;
}
.task-meta .overdue {
  color: #f5222d;
  opacity: 1;
}
.quadrant-bar {
  display: inline-block;
  width: 3px;
  height: 11px;
  border-radius: 3px;
  margin-right: 0.4em;
  vertical-align: middle;
}
</style>
