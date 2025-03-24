<template>
  <div class="todo-quadrant">
    <n-grid :cols="2" :x-gap="20">
      <!-- 重要且紧急 -->
      <n-gi>
        <n-card title="重要且紧急" class="quadrant-card urgent-important">
          <template #header-extra>
            <n-button type="error" @click="handleAddTodo(1)">添加</n-button>
          </template>
          <div class="todo-list">
            <n-empty v-if="todoList1.length === 0" description="暂无待办事项" />
            <div v-for="todo in todoList1" :key="todo.id" class="todo-item">
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
          <div class="todo-list">
            <n-empty v-if="todoList2.length === 0" description="暂无待办事项" />
            <div v-for="todo in todoList2" :key="todo.id" class="todo-item">
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
    </n-grid>

    <div style="height: 20px"></div>

    <n-grid :cols="2" :x-gap="20">
      <!-- 重要不紧急 -->
      <n-gi>
        <n-card title="重要不紧急" class="quadrant-card important-not-urgent">
          <template #header-extra>
            <n-button type="primary" @click="handleAddTodo(3)">添加</n-button>
          </template>
          <div class="todo-list">
            <n-empty v-if="todoList3.length === 0" description="暂无待办事项" />
            <div v-for="todo in todoList3" :key="todo.id" class="todo-item">
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

      <!-- 不紧急不重要 -->
      <n-gi>
        <n-card title="不紧急不重要" class="quadrant-card not-urgent-not-important">
          <template #header-extra>
            <n-button type="default" @click="handleAddTodo(4)">添加</n-button>
          </template>
          <div class="todo-list">
            <n-empty v-if="todoList4.length === 0" description="暂无待办事项" />
            <div v-for="todo in todoList4" :key="todo.id" class="todo-item">
              <n-checkbox v-model:checked="todo.is_completed" @update:checked="handleTodoComplete(todo)" />
              <div class="todo-content">
                <div class="todo-title">{{ todo.title }}</div>
                <div class="todo-meta">
                  <n-tag type="default" size="small" v-if="todo.due_date">
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
  { label: '重要且紧急', value: 'URGENT_IMPORTANT' },
  { label: '紧急不重要', value: 'URGENT_NOT_IMPORTANT' },
  { label: '重要不紧急', value: 'IMPORTANT_NOT_URGENT' },
  { label: '不紧急不重要', value: 'NOT_URGENT_NOT_IMPORTANT' }
]

// 待办事项相关
const todoList1 = ref([])
const todoList2 = ref([])
const todoList3 = ref([])
const todoList4 = ref([])
const loading = ref(false)

// 获取待办列表
const fetchTodos = async () => {
  loading.value = true
  try {
    const params = {
      is_completed: false
    }
    const response = await todoApi.getTodos(params)
    const todos = response.items || []

    // 分配到不同象限
    todoList1.value = todos.filter(todo => todo.quadrant_type === 'URGENT_IMPORTANT')
    todoList2.value = todos.filter(todo => todo.quadrant_type === 'URGENT_NOT_IMPORTANT')
    todoList3.value = todos.filter(todo => todo.quadrant_type === 'IMPORTANT_NOT_URGENT')
    todoList4.value = todos.filter(todo => todo.quadrant_type === 'NOT_URGENT_NOT_IMPORTANT')
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
    case 1: return 'URGENT_IMPORTANT'
    case 2: return 'URGENT_NOT_IMPORTANT'
    case 3: return 'IMPORTANT_NOT_URGENT'
    case 4: return 'NOT_URGENT_NOT_IMPORTANT'
    default: return null
  }
}

// 添加待办
const handleAddTodo = (quadrantIndex) => {
  dialogType.value = 'add'
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
  todoForm.value = { ...todo }
  dialogVisible.value = true
}

// 提交待办表单
const handleSubmitTodo = async () => {
  if (!todoFormRef.value) return

  try {
    await todoFormRef.value.validate()

    if (dialogType.value === 'add') {
      await todoApi.createTodo(todoForm.value)
      message.success('添加成功')
    } else {
      await todoApi.updateTodo(todoForm.value.id, todoForm.value)
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
const handleTodoComplete = async (isChecked, todo) => {
  try {
    await todoApi.updateTodo(todo.id, {
      is_completed: isChecked,
      completed_at: isChecked ? new Date().toISOString() : null
    })
    message.success(isChecked ? '已完成' : '已取消完成')
    fetchTodos()
  } catch (error) {
    console.error('更新待办状态失败:', error)
    message.error('更新状态失败')
    // 恢复原状态
    todo.is_completed = !isChecked
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
</style>