<template>
  <n-modal :show="show" preset="card" title="新建项目/清单" style="width: 420px" @update:show="onUpdateShow">
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="80">
      <n-form-item label="名称" path="name">
        <n-input v-model:value="form.name" placeholder="请输入名称" />
      </n-form-item>
      <n-form-item label="类型" path="type">
        <n-radio-group v-model:value="form.type">
          <n-radio value="project">项目</n-radio>
          <n-radio value="list">清单</n-radio>
        </n-radio-group>
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
        <n-input v-model:value="form.new_category_name" placeholder="或输入新分类名称（留空则用上面的选择）" />
      </n-form-item>
      <n-form-item label="颜色">
        <n-color-picker v-model:value="form.color_hex" :show-alpha="false" />
      </n-form-item>
    </n-form>
    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5em">
        <n-button @click="onUpdateShow(false)">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="handleSubmit">创建</n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false }
})
const emit = defineEmits(['update:show', 'created'])

const message = useMessage()
const formRef = ref(null)
const submitting = ref(false)
const categories = ref([])

const defaultForm = () => ({
  name: '',
  type: 'project',
  category_id: null,
  new_category_name: '',
  color_hex: '#1890FF'
})
const form = ref(defaultForm())

const rules = {
  name: { required: true, message: '请输入名称', trigger: 'blur' }
}

const categoryOptions = computed(() => categories.value.map((c) => ({ label: c.name, value: c.id })))

const fetchCategories = async () => {
  const res = await api.getCategories()
  categories.value = res.data || []
}

const onUpdateShow = (value) => {
  emit('update:show', value)
}

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      form.value = defaultForm()
      fetchCategories()
    }
  }
)

const handleSubmit = async () => {
  await formRef.value?.validate()
  submitting.value = true
  try {
    const payload = {
      name: form.value.name,
      type: form.value.type,
      color_hex: form.value.color_hex
    }
    if (form.value.new_category_name.trim()) {
      payload.category_name = form.value.new_category_name.trim()
    } else if (form.value.category_id) {
      payload.category_id = form.value.category_id
    }
    const res = await api.createProject(payload)
    message.success('创建成功')
    emit('created', res.data)
    onUpdateShow(false)
  } finally {
    submitting.value = false
  }
}
</script>
