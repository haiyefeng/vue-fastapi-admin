<template>
  <n-modal
    :show="show"
    preset="card"
    :title="isEdit ? '编辑计划' : '添加新计划'"
    style="width: 480px"
    @update:show="onUpdateShow"
  >
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="80">
      <n-form-item label="名称" path="name">
        <n-input v-model:value="form.name" placeholder="例如：学习新语言，完成XX项目" />
      </n-form-item>
      <n-form-item label="描述">
        <n-input
          v-model:value="form.description"
          type="textarea"
          :rows="3"
          placeholder="简要说明这个计划的目标和意义（可选）"
        />
      </n-form-item>
      <n-form-item label="目标日期">
        <n-date-picker v-model:value="form.target_date" type="date" clearable style="width: 100%" />
      </n-form-item>
      <n-form-item label="分类" path="category_id">
        <n-select
          v-model:value="form.category_id"
          :options="categoryOptions"
          placeholder="选择已有分类（可留空）"
          clearable
        />
      </n-form-item>
      <n-form-item label="新分类">
        <n-input
          v-model:value="form.new_category_name"
          placeholder="或输入新分类名称（留空则用上面的选择）"
        />
      </n-form-item>
    </n-form>
    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5em">
        <n-button @click="onUpdateShow(false)">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="handleSubmit">保存计划</n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false },
  goal: { type: Object, default: null },
})
const emit = defineEmits(['update:show', 'saved'])

const message = useMessage()
const formRef = ref(null)
const submitting = ref(false)
const categories = ref([])

const isEdit = computed(() => !!props.goal)

const defaultForm = () => ({
  name: '',
  description: '',
  target_date: null,
  category_id: null,
  new_category_name: '',
})
const form = ref(defaultForm())

const rules = {
  name: { required: true, message: '请输入名称', trigger: 'blur' },
}

const categoryOptions = computed(() =>
  categories.value.map((c) => ({ label: c.name, value: c.id }))
)

const fetchCategories = async () => {
  try {
    const res = await api.getCategories()
    categories.value = res.data || []
  } catch (error) {
    console.error('获取分类列表失败:', error)
    message.error('获取分类列表失败')
  }
}

const onUpdateShow = (value) => emit('update:show', value)

// 纯日期字符串（"YYYY-MM-DD"）不带时间/时区信息，用本地年月日拼接和解析，
// 不能用 new Date(dateString) / toISOString()——那两种写法都会按 UTC 解读/输出，
// 在东八区这类正时区下会把日期往前错移一天
const parseLocalDateString = (dateStr) => {
  if (!dateStr) return null
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d).getTime()
}

const formatLocalDateString = (ms) => {
  if (!ms) return null
  const d = new Date(ms)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const fillFormFromGoal = (goal) => {
  form.value = {
    name: goal.name,
    description: goal.description || '',
    target_date: parseLocalDateString(goal.target_date),
    category_id: goal.category_id,
    new_category_name: '',
  }
}

watch(
  () => props.show,
  (visible) => {
    if (!visible) return
    fetchCategories()
    if (props.goal) {
      fillFormFromGoal(props.goal)
    } else {
      form.value = defaultForm()
    }
  }
)

const handleSubmit = async () => {
  await formRef.value?.validate()
  submitting.value = true
  try {
    const payload = {
      name: form.value.name,
      description: form.value.description || null,
      target_date: formatLocalDateString(form.value.target_date),
    }
    if (form.value.new_category_name.trim()) {
      payload.category_name = form.value.new_category_name.trim()
    } else if (form.value.category_id) {
      payload.category_id = form.value.category_id
    }
    const res = isEdit.value
      ? await api.updateGoal(props.goal.id, payload)
      : await api.createGoal(payload)
    message.success('保存成功')
    emit('saved', res.data)
    onUpdateShow(false)
  } finally {
    submitting.value = false
  }
}
</script>
