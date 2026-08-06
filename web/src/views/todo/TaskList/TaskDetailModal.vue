<template>
  <n-modal :show="show" preset="card" title="任务详情" style="width: 640px" @update:show="onUpdateShow">
    <n-spin :show="loading">
      <n-form label-placement="left" label-width="70">
        <n-form-item label="标题">
          <n-input v-model:value="form.title" placeholder="标题" />
        </n-form-item>
        <n-form-item label="备注">
          <n-input
            v-model:value="form.notes"
            type="textarea"
            :rows="2"
            placeholder="添加备注...（可记录完成方法、收获、注意事项等）"
          />
        </n-form-item>

        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5em 1em">
          <n-form-item label="项目">
            <n-select v-model:value="form.project_id" :options="projectOptions" clearable placeholder="收件箱" />
          </n-form-item>
          <n-form-item label="截止日期">
            <n-date-picker v-model:value="form.due_date" type="date" clearable style="width: 100%" />
          </n-form-item>
          <n-form-item label="提醒时间">
            <n-date-picker v-model:value="form.reminder_at" type="datetime" clearable style="width: 100%" />
          </n-form-item>
        </div>

        <n-form-item label="象限">
          <n-radio-group v-model:value="form.quadrant_type">
            <n-space>
              <n-radio v-for="opt in quadrantOptions" :key="opt.value" :value="opt.value">
                <span class="quadrant-dot" :style="{ background: opt.color }"></span>
                {{ opt.label }}
              </n-radio>
            </n-space>
          </n-radio-group>
        </n-form-item>
      </n-form>

      <n-divider />

      <section>
        <h4 style="font-size: 1em; font-weight: 600; margin-bottom: 0.6em">子任务</h4>
        <div v-for="sub in subtasks" :key="sub.id" class="subtask-row">
          <n-checkbox :checked="sub.is_completed" @update:checked="(v) => toggleSubtask(sub, v)" />
          <n-input
            v-model:value="sub.title"
            size="small"
            style="flex: 1; margin: 0 0.5em"
            @blur="renameSubtask(sub)"
          />
          <n-button text type="error" @click="removeSubtask(sub)">删除</n-button>
        </div>
        <div style="display: flex; margin-top: 0.5em">
          <n-input v-model:value="newSubtaskTitle" placeholder="添加子任务..." @keyup.enter="addSubtask" />
          <n-button type="primary" style="margin-left: 0.5em" @click="addSubtask">添加</n-button>
        </div>
      </section>
    </n-spin>

    <template #footer>
      <div style="display: flex; justify-content: space-between">
        <n-button type="error" ghost @click="handleDelete">删除任务</n-button>
        <div style="display: flex; gap: 0.5em">
          <n-button @click="onUpdateShow(false)">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleSave">保存更改</n-button>
        </div>
      </div>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false },
  todoId: { type: Number, default: null },
  projects: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:show', 'saved', 'deleted'])

const message = useMessage()
const dialog = useDialog()

const loading = ref(false)
const saving = ref(false)
const subtasks = ref([])
const newSubtaskTitle = ref('')

const form = ref({
  title: '',
  notes: '',
  project_id: null,
  due_date: null,
  reminder_at: null,
  quadrant_type: 'not_urgent_not_important'
})

const quadrantOptions = [
  { label: '重要且紧急', value: 'urgent_important', color: '#f5222d' },
  { label: '紧急不重要', value: 'urgent_not_important', color: '#faad14' },
  { label: '重要不紧急', value: 'important_not_urgent', color: '#1890ff' },
  { label: '不紧急不重要', value: 'not_urgent_not_important', color: '#909399' }
]

const projectOptions = computed(() => {
  const options = props.projects.filter((p) => !p.is_archived).map((p) => ({ label: p.name, value: p.id }))
  const current = props.projects.find((p) => p.id === form.value.project_id)
  if (current && current.is_archived) {
    options.push({ label: `${current.name}（已归档）`, value: current.id })
  }
  return options
})

const onUpdateShow = (value) => {
  emit('update:show', value)
}

const toDateValue = (isoString) => (isoString ? new Date(isoString).getTime() : null)

const loadDetail = async () => {
  if (!props.todoId) return
  loading.value = true
  try {
    const [todoRes, subtaskRes] = await Promise.all([api.getTodoById(props.todoId), api.getSubtasks(props.todoId)])
    const todo = todoRes.data
    form.value = {
      title: todo.title,
      notes: todo.notes || '',
      project_id: todo.project_id,
      due_date: toDateValue(todo.due_date),
      reminder_at: toDateValue(todo.reminder_at),
      quadrant_type: todo.quadrant_type
    }
    subtasks.value = subtaskRes.data || []
  } catch (error) {
    console.error('获取任务详情失败:', error)
    message.error('获取任务详情失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.show, props.todoId],
  ([visible]) => {
    if (visible) loadDetail()
  }
)

const handleSave = async () => {
  saving.value = true
  try {
    const payload = {
      title: form.value.title,
      notes: form.value.notes,
      project_id: form.value.project_id,
      due_date: form.value.due_date ? new Date(form.value.due_date).toISOString() : null,
      reminder_at: form.value.reminder_at ? new Date(form.value.reminder_at).toISOString() : null,
      quadrant_type: form.value.quadrant_type
    }
    const res = await api.updateTodo(props.todoId, payload)
    message.success('保存成功')
    emit('saved', res.data)
    onUpdateShow(false)
  } catch (error) {
    console.error('保存任务失败:', error)
    message.error('保存任务失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = () => {
  dialog.warning({
    title: '确认删除',
    content: '确定要删除这条任务吗？',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await api.deleteTodo(props.todoId)
        message.success('删除成功')
        emit('deleted', props.todoId)
        onUpdateShow(false)
      } catch (error) {
        console.error('删除任务失败:', error)
        message.error('删除任务失败')
      }
    }
  })
}

const toggleSubtask = async (sub, checked) => {
  const previous = sub.is_completed
  sub.is_completed = checked
  try {
    await api.updateSubtask(sub.id, { is_completed: checked })
  } catch (error) {
    console.error('更新子任务状态失败:', error)
    message.error('更新子任务状态失败')
    sub.is_completed = previous
  }
}

const renameSubtask = async (sub) => {
  try {
    await api.updateSubtask(sub.id, { title: sub.title })
  } catch (error) {
    console.error('重命名子任务失败:', error)
    message.error('重命名子任务失败')
  }
}

const removeSubtask = async (sub) => {
  try {
    await api.deleteSubtask(sub.id)
    subtasks.value = subtasks.value.filter((s) => s.id !== sub.id)
  } catch (error) {
    console.error('删除子任务失败:', error)
    message.error('删除子任务失败')
  }
}

const addSubtask = async () => {
  const title = newSubtaskTitle.value.trim()
  if (!title) return
  try {
    const res = await api.createSubtask({ todo_item_id: props.todoId, title })
    subtasks.value.push(res.data)
    newSubtaskTitle.value = ''
  } catch (error) {
    console.error('添加子任务失败:', error)
    message.error('添加子任务失败')
  }
}
</script>

<style scoped>
.subtask-row {
  display: flex;
  align-items: center;
  padding: 0.3em 0;
}
.quadrant-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.4em;
}
</style>
