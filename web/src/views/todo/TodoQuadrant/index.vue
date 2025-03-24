<template>
  <div class="todo-quadrant">
    <n-grid :cols="2" :x-gap="20">
      <!-- 重要且紧急 -->
      <n-gi>
        <n-card title="重要且紧急" class="quadrant-card urgent-important">
          <template #header-extra>
            <n-button type="error" @click="handleAddTodo(1)">添加</n-button>
          </template>
          <div class="todo-list" @dragover.prevent @drop="(event) => handleDrop(event, 'urgent_important')">
            <n-empty v-if="todoList1.length === 0" description="暂无待办事项" />
            <div v-for="todo in todoList1" :key="todo.id" class="todo-item" draggable="true"
              @dragstart="(event) => handleDragStart(event, todo)">
              <n-checkbox v-model:checked="todo.is_completed" @update:checked="handleTodoComplete(todo)" />
              <div class="todo-content">
                <div class="todo-title">{{ todo.title }}</div>
                <div class="todo-meta">
                  <n-tag type="error" size="small" v-if="todo.due_date">
                    截止: {{ todo.due_date }}
                  </n-tag>
                </div>
              </div>
              <div class="todo-actions">
                <n-button text type="primary" @click="handleEditTodo(todo)">编辑</n-button>
                <n-button text type="error" @click="handleDeleteTodo(todo)">删除</n-button>
              </div>
            </div>
          </div>
        </n-card>
      </n-gi>

      <!-- 紧急不重要 -->
      <n-gi>
        <n-card title="紧急不重要" class="quadrant-card urgent-not-important">
          <template #header-extra>
            <n-button type="warning" @click="handleAddTodo(2)">添加</n-button>
          </template>
          <div class="todo-list" @dragover.prevent @drop="(event) => handleDrop(event, 'urgent_not_important')">
            <n-empty v-if="todoList2.length === 0" description="暂无待办事项" />
            <div v-for="todo in todoList2" :key="todo.id" class="todo-item" draggable="true"
              @dragstart="(event) => handleDragStart(event, todo)">
              <n-checkbox v-model:checked="todo.is_completed" @update:checked="handleTodoComplete(todo)" />
              <div class="todo-content">
                <div class="todo-title">{{ todo.title }}</div>
                <div class="todo-meta">
                  <n-tag type="warning" size="small" v-if="todo.due_date">
                    截止: {{ todo.due_date }}
                  </n-tag>
                </div>
              </div>
              <div class="todo-actions">
                <n-button text type="primary" @click="handleEditTodo(todo)">编辑</n-button>
                <n-button text type="error" @click="handleDeleteTodo(todo)">删除</n-button>
              </div>
            </div>
          </div>
        </n-card>
      </n-gi>

      <!-- 重要不紧急 -->
      <n-gi>
        <n-card title="重要不紧急" class="quadrant-card important-not-urgent">
          <template #header-extra>
            <n-button type="primary" @click="handleAddTodo(3)">添加</n-button>
          </template>
          <div class="todo-list" @dragover.prevent @drop="(event) => handleDrop(event, 'important_not_urgent')">
            <n-empty v-if="todoList3.length === 0" description="暂无待办事项" />
            <div v-for="todo in todoList3" :key="todo.id" class="todo-item" draggable="true"
              @dragstart="(event) => handleDragStart(event, todo)">
              <n-checkbox v-model:checked="todo.is_completed" @update:checked="handleTodoComplete(todo)" />
              <div class="todo-content">
                <div class="todo-title">{{ todo.title }}</div>
                <div class="todo-meta">
                  <n-tag type="primary" size="small" v-if="todo.due_date">
                    截止: {{ todo.due_date }}
                  </n-tag>
                </div>
              </div>
              <div class="todo-actions">
                <n-button text type="primary" @click="handleEditTodo(todo)">编辑</n-button>
                <n-button text type="error" @click="handleDeleteTodo(todo)">删除</n-button>
              </div>
            </div>
          </div>
        </n-card>
      </n-gi>

      <!-- 不紧急不重要 -->
      <n-gi>
        <n-card title="不紧急不重要" class="quadrant-card not-urgent-not-important">
          <template #header-extra>
            <n-button type="info" @click="handleAddTodo(4)">添加</n-button>
          </template>
          <div class="todo-list" @dragover.prevent @drop="(event) => handleDrop(event, 'not_urgent_not_important')">
            <n-empty v-if="todoList4.length === 0" description="暂无待办事项" />
            <div v-for="todo in todoList4" :key="todo.id" class="todo-item" draggable="true"
              @dragstart="(event) => handleDragStart(event, todo)">
              <n-checkbox v-model:checked="todo.is_completed" @update:checked="handleTodoComplete(todo)" />
              <div class="todo-content">
                <div class="todo-title">{{ todo.title }}</div>
                <div class="todo-meta">
                  <n-tag type="info" size="small" v-if="todo.due_date">
                    截止: {{ todo.due_date }}
                  </n-tag>
                </div>
              </div>
              <div class="todo-actions">
                <n-button text type="primary" @click="handleEditTodo(todo)">编辑</n-button>
                <n-button text type="error" @click="handleDeleteTodo(todo)">删除</n-button>
              </div>
            </div>
          </div>
        </n-card>
      </n-gi>
    </n-grid>

    <div style="height: 20px"></div>

    <!-- 添加/编辑待办对话框 -->
    <n-modal v-model:show="dialogVisible" :title="dialogType === 'add' ? '添加待办事项' : '编辑待办事项'" preset="card">
      <n-form ref="todoFormRef" :model="todoForm" :rules="rules" label-placement="left" label-width="auto">
        <n-form-item label="标题" path="title">
          <n-input v-model:value="todoForm.title" placeholder="请输入待办事项标题" />
        </n-form-item>
        <n-form-item label="象限" path="quadrant_type">
          <n-select v-model:value="todoForm.quadrant_type" placeholder="请选择象限" :options="quadrantOptions" />
        </n-form-item>
        <n-form-item label="截止日期" path="due_date">
          <n-date-picker v-model:value="todoForm.due_date" type="datetime" placeholder="请选择截止日期" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="dialogVisible = false">取消</n-button>
          <n-button type="primary" @click="handleSubmitTodo">确定</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import todoApi from '@/api/todo'

const message = useMessage()
const dialog = useDialog()

// 对话框相关
const dialogVisible = ref(false)
const dialogType = ref('add') // add or edit
const todoFormRef = ref(null)
const todoForm = ref({
  title: '',
  quadrant_type: null,
  due_date: null,
  is_completed: false
})
const rules = {
  title: {
    required: true,
    message: '请输入标题',
    trigger: 'blur'
  },
  quadrant_type: {
    required: true,
    message: '请选择象限',
    trigger: 'change'
  }
}

// 象限选项
const quadrantOptions = [
  { label: '重要且紧急', value: 'urgent_important' },
  { label: '紧急不重要', value: 'urgent_not_important' },
  { label: '重要不紧急', value: 'important_not_urgent' },
  { label: '不紧急不重要', value: 'not_urgent_not_important' }
]

// 待办事项相关
const todoList1 = ref([])
const todoList2 = ref([])
const todoList3 = ref([])
const todoList4 = ref([])
const loading = ref(false)

// 拖拽相关变量
const draggedTodo = ref(null)

// 获取待办列表
const fetchTodos = async () => {
  loading.value = true
  try {
    const params = {
      is_completed: false
    }
    const response = await todoApi.getTodos(params)
    // 根据后端返回数据结构进行处理
    const todos = response.data || []

    // 分配到不同象限
    todoList1.value = todos.filter(todo => todo.quadrant_type === 'urgent_important')
    todoList2.value = todos.filter(todo => todo.quadrant_type === 'urgent_not_important')
    todoList3.value = todos.filter(todo => todo.quadrant_type === 'important_not_urgent')
    todoList4.value = todos.filter(todo => todo.quadrant_type === 'not_urgent_not_important')
  } catch (error) {
    console.error('获取待办列表失败:', error)
    message.error('获取待办列表失败')
  } finally {
    loading.value = false
  }
}

// 获取象限类型
const getQuadrantType = (index) => {
  switch (index) {
    case 1: return 'urgent_important'
    case 2: return 'urgent_not_important'
    case 3: return 'important_not_urgent'
    case 4: return 'not_urgent_not_important'
    default: return null
  }
}

// 添加待办
const handleAddTodo = (quadrantIndex) => {
  dialogType.value = 'add'
  // 重置表单，确保所有字段有默认值
  todoForm.value = {
    title: '',
    quadrant_type: getQuadrantType(quadrantIndex),
    due_date: null,
    is_completed: false
  }
  dialogVisible.value = true
}

// 编辑待办
const handleEditTodo = (todo) => {
  dialogType.value = 'edit'

  // 创建一个新对象，避免直接修改原对象
  const todoData = { ...todo }

  // 处理日期，将字符串日期转换为 Date 对象
  if (todoData.due_date) {
    try {
      // 如果是字符串日期，需要转换为 Date 对象
      if (typeof todoData.due_date === 'string') {
        // 添加时间部分如果只有日期
        if (!todoData.due_date.includes('T')) {
          todoData.due_date = `${todoData.due_date}T00:00:00`
        }
        todoData.due_date = new Date(todoData.due_date)
      }
    } catch (error) {
      console.error('日期转换错误:', error)
      todoData.due_date = null
    }
  }

  todoForm.value = todoData
  dialogVisible.value = true
}

// 提交待办表单
const handleSubmitTodo = async () => {
  if (!todoFormRef.value) return

  try {
    await todoFormRef.value.validate()

    // 创建一个新对象来存储处理后的数据
    const todoData = { ...todoForm.value }

    // 处理日期格式
    if (todoData.due_date) {
      try {
        // 如果是 Date 对象，转换为 ISO 格式字符串并截取到 yyyy-MM-dd
        if (todoData.due_date instanceof Date) {
          if (isNaN(todoData.due_date.getTime())) {
            // 无效日期
            console.error('无效的日期对象')
            todoData.due_date = null
          } else {
            todoData.due_date = todoData.due_date.toISOString().split('T')[0]
          }
        } else if (typeof todoData.due_date === 'number') {
          // 如果是时间戳，先转换为 Date 对象，再转换为 ISO 格式字符串
          const date = new Date(todoData.due_date)
          if (isNaN(date.getTime())) {
            // 无效时间戳
            console.error('无效的时间戳')
            todoData.due_date = null
          } else {
            todoData.due_date = date.toISOString().split('T')[0]
          }
        } else if (typeof todoData.due_date === 'string') {
          // 如果已经是字符串，确保格式正确
          if (todoData.due_date.includes('T')) {
            // 带有时间部分的 ISO 字符串，截取日期部分
            todoData.due_date = todoData.due_date.split('T')[0]
          } else if (!/^\d{4}-\d{2}-\d{2}$/.test(todoData.due_date)) {
            // 不是 yyyy-MM-dd 格式
            try {
              const date = new Date(todoData.due_date)
              if (isNaN(date.getTime())) {
                throw new Error('无法解析日期字符串')
              }
              todoData.due_date = date.toISOString().split('T')[0]
            } catch (error) {
              console.error('日期字符串解析错误:', error)
              todoData.due_date = null
            }
          }
          // 如果已经是 yyyy-MM-dd 格式，保持不变
        } else {
          // 其他类型，置为 null
          console.error('未知的日期类型')
          todoData.due_date = null
        }
      } catch (error) {
        console.error('日期处理错误:', error)
        todoData.due_date = null
      }
    }

    if (dialogType.value === 'add') {
      await todoApi.createTodo(todoData)
      message.success('添加成功')
    } else {
      await todoApi.updateTodo(todoData.id, todoData)
      message.success('更新成功')
    }

    dialogVisible.value = false
    fetchTodos()
  } catch (error) {
    console.error('提交待办失败:', error)
    message.error('提交失败，请重试')
  }
}

// 完成待办
const handleTodoComplete = async (todo) => {
  try {
    await todoApi.updateTodo(todo.id, {
      is_completed: todo.is_completed,
      completed_at: todo.is_completed ? new Date().toISOString().split('T')[0] : null
    })
    message.success(todo.is_completed ? '已完成' : '已取消完成')
    fetchTodos()
  } catch (error) {
    console.error('更新待办状态失败:', error)
    message.error('更新状态失败')
    // 恢复原状态
    todo.is_completed = !todo.is_completed
  }
}

// 删除待办
const handleDeleteTodo = async (todo) => {
  dialog.warning({
    title: '确认删除',
    content: '确定要删除这条待办事项吗？',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await todoApi.deleteTodo(todo.id)
        message.success('删除成功')
        fetchTodos()
      } catch (error) {
        console.error('删除待办失败:', error)
        message.error('删除失败')
      }
    }
  })
}

// 处理拖拽开始
const handleDragStart = (event, todo) => {
  draggedTodo.value = todo
  event.dataTransfer.effectAllowed = 'move'
  // 设置拖拽图像和数据
  event.dataTransfer.setData('text/plain', todo.id)

  // 添加拖拽样式
  event.target.classList.add('dragging')
}

// 处理拖拽放下
const handleDrop = async (event, targetQuadrant) => {
  event.preventDefault()

  // 恢复样式
  document.querySelectorAll('.dragging').forEach(el => {
    el.classList.remove('dragging')
  })

  if (!draggedTodo.value || draggedTodo.value.quadrant_type === targetQuadrant) {
    return
  }

  try {
    message.info(`正在将待办从 ${getQuadrantLabel(draggedTodo.value.quadrant_type)} 移动到 ${getQuadrantLabel(targetQuadrant)}`)

    // 更新待办事项象限
    await todoApi.updateTodo(draggedTodo.value.id, {
      ...draggedTodo.value,
      quadrant_type: targetQuadrant
    })

    // 刷新列表
    fetchTodos()
    message.success('移动成功')
  } catch (error) {
    console.error('移动待办事项失败:', error)
    message.error('移动待办事项失败')
  }
}

// 获取象限的中文名称
const getQuadrantLabel = (type) => {
  const labels = {
    urgent_important: '重要且紧急',
    urgent_not_important: '紧急不重要',
    important_not_urgent: '重要不紧急',
    not_urgent_not_important: '不紧急不重要'
  }
  return labels[type] || type
}

onMounted(() => {
  fetchTodos()
})
</script>

<style scoped>
.todo-quadrant {
  padding: 20px;
}

.quadrant-card {
  height: 100%;
  min-height: 300px;
}

.todo-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 400px;
  overflow-y: auto;
}

.todo-item {
  display: flex;
  align-items: flex-start;
  padding: 10px;
  border-radius: 4px;
  background-color: rgba(0, 0, 0, 0.02);
  transition: all 0.3s;
}

.todo-item:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

.todo-content {
  flex: 1;
  margin: 0 10px;
}

.todo-title {
  font-size: 14px;
  line-height: 1.4;
  word-break: break-word;
}

.todo-meta {
  margin-top: 5px;
  display: flex;
  gap: 5px;
}

.todo-actions {
  display: flex;
  flex-direction: column;
}

.urgent-important :deep(.n-card-header) {
  background-color: rgba(237, 60, 80, 0.1);
}

.urgent-not-important :deep(.n-card-header) {
  background-color: rgba(250, 173, 20, 0.1);
}

.important-not-urgent :deep(.n-card-header) {
  background-color: rgba(24, 144, 255, 0.1);
}

.not-urgent-not-important :deep(.n-card-header) {
  background-color: rgba(144, 156, 170, 0.1);
}

/* 添加拖拽相关样式 */
.todo-item {
  cursor: move;
  transition: all 0.2s;
}

.todo-item.dragging {
  opacity: 0.5;
  transform: scale(0.98);
  box-shadow: 0 0 5px rgba(0, 0, 0, 0.2);
}

.todo-list {
  min-height: 50px;
  padding: 8px;
  border-radius: 4px;
}

.todo-list.drag-over {
  background-color: rgba(0, 0, 0, 0.05);
}
</style>