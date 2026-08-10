<template>
  <n-modal :show="show" preset="card" :title="isEdit ? '编辑习惯' : '添加新习惯'" style="width: 480px" @update:show="onUpdateShow">
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="left" label-width="80">
      <n-form-item label="名称" path="name">
        <n-input v-model:value="form.name" placeholder="例如：每天阅读" />
      </n-form-item>
      <div style="display: flex; gap: 1em">
        <n-form-item label="图标" style="flex: 1">
          <n-input v-model:value="form.icon" placeholder="emoji，如 📖" maxlength="10" />
        </n-form-item>
        <n-form-item label="颜色" style="flex: 1">
          <n-color-picker v-model:value="form.color_hex" :show-alpha="false" />
        </n-form-item>
      </div>
      <n-form-item label="频率" path="frequency_type">
        <n-radio-group v-model:value="form.frequency_type">
          <n-space>
            <n-radio value="daily">每天</n-radio>
            <n-radio value="weekly_days">每周固定几天</n-radio>
            <n-radio value="weekly_count">每周N次</n-radio>
            <n-radio value="interval_days">每隔N天</n-radio>
          </n-space>
        </n-radio-group>
      </n-form-item>
      <n-form-item v-if="form.frequency_type === 'weekly_days'" label="星期">
        <n-checkbox-group v-model:value="form.weekly_days">
          <n-checkbox v-for="opt in weekdayOptions" :key="opt.value" :value="opt.value" :label="opt.label" />
        </n-checkbox-group>
      </n-form-item>
      <n-form-item v-if="form.frequency_type === 'weekly_count'" label="每周次数">
        <n-input-number v-model:value="form.weekly_count" :min="1" style="width: 100%" />
      </n-form-item>
      <n-form-item v-if="form.frequency_type === 'interval_days'" label="间隔天数">
        <n-input-number v-model:value="form.interval_days" :min="1" style="width: 100%" />
      </n-form-item>
      <n-form-item label="默认象限">
        <n-radio-group v-model:value="form.default_quadrant">
          <n-space>
            <n-radio v-for="opt in quadrantOptions" :key="opt.value" :value="opt.value">
              <span class="quadrant-dot" :style="{ background: opt.color }"></span>
              {{ opt.label }}
            </n-radio>
          </n-space>
        </n-radio-group>
      </n-form-item>
      <n-form-item label="目标描述">
        <n-input v-model:value="form.goal_desc" placeholder="例如：30分钟（可选）" />
      </n-form-item>
      <n-form-item label="提醒时间">
        <n-time-picker
          v-model:formatted-value="form.reminder_time"
          value-format="HH:mm:ss"
          clearable
          style="width: 100%"
        />
      </n-form-item>
    </n-form>
    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5em">
        <n-button @click="onUpdateShow(false)">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="handleSubmit">保存习惯</n-button>
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
  habit: { type: Object, default: null }
})
const emit = defineEmits(['update:show', 'saved'])

const message = useMessage()
const formRef = ref(null)
const submitting = ref(false)

const isEdit = computed(() => !!props.habit)

const weekdayOptions = [
  { label: '一', value: 1 },
  { label: '二', value: 2 },
  { label: '三', value: 3 },
  { label: '四', value: 4 },
  { label: '五', value: 5 },
  { label: '六', value: 6 },
  { label: '日', value: 7 }
]

const quadrantOptions = [
  { label: '重要且紧急', value: 'urgent_important', color: '#f5222d' },
  { label: '紧急不重要', value: 'urgent_not_important', color: '#faad14' },
  { label: '重要不紧急', value: 'important_not_urgent', color: '#1890ff' },
  { label: '不紧急不重要', value: 'not_urgent_not_important', color: '#909399' }
]

const defaultForm = () => ({
  name: '',
  icon: '',
  color_hex: '#1890FF',
  frequency_type: 'daily',
  weekly_days: [],
  weekly_count: 3,
  interval_days: 2,
  default_quadrant: 'important_not_urgent',
  goal_desc: '',
  reminder_time: null
})
const form = ref(defaultForm())

const rules = {
  name: { required: true, message: '请输入名称', trigger: 'blur' }
}

const onUpdateShow = (value) => emit('update:show', value)

const fillFormFromHabit = (habit) => {
  const config = habit.frequency_config || {}
  form.value = {
    name: habit.name,
    icon: habit.icon || '',
    color_hex: habit.color_hex || '#1890FF',
    frequency_type: habit.frequency_type,
    weekly_days: config.days || [],
    weekly_count: config.count || 3,
    interval_days: config.interval || 2,
    default_quadrant: habit.default_quadrant,
    goal_desc: habit.goal_desc || '',
    reminder_time: habit.reminder_time || null
  }
}

watch(
  () => props.show,
  (visible) => {
    if (!visible) return
    if (props.habit) {
      fillFormFromHabit(props.habit)
    } else {
      form.value = defaultForm()
    }
  }
)

const buildFrequencyConfig = () => {
  if (form.value.frequency_type === 'weekly_days') return { days: form.value.weekly_days }
  if (form.value.frequency_type === 'weekly_count') return { count: form.value.weekly_count }
  if (form.value.frequency_type === 'interval_days') return { interval: form.value.interval_days }
  return null
}

const handleSubmit = async () => {
  await formRef.value?.validate()
  if (form.value.frequency_type === 'weekly_days' && !form.value.weekly_days.length) {
    message.error('请至少选择一天')
    return
  }
  submitting.value = true
  try {
    const payload = {
      name: form.value.name,
      icon: form.value.icon || null,
      color_hex: form.value.color_hex,
      frequency_type: form.value.frequency_type,
      frequency_config: buildFrequencyConfig(),
      default_quadrant: form.value.default_quadrant,
      goal_desc: form.value.goal_desc || null,
      reminder_time: form.value.reminder_time || null
    }
    if (isEdit.value) {
      await api.updateHabit(props.habit.id, payload)
    } else {
      await api.createHabit(payload)
    }
    message.success('保存成功')
    emit('saved')
    onUpdateShow(false)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.quadrant-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.4em;
}
</style>
