<template>
  <n-modal :show="show" preset="card" title="创建待办事项" style="width: 480px" @update:show="onUpdateShow">
    <n-form label-placement="left" label-width="70">
      <n-form-item label="标题">
        <n-input v-model:value="form.title" placeholder="要做什么？" />
      </n-form-item>
      <n-form-item label="象限">
        <n-radio-group v-model:value="form.quadrant_type">
          <n-space vertical>
            <n-radio v-for="opt in quadrantOptions" :key="opt.value" :value="opt.value">
              <span class="quadrant-dot" :style="{ background: opt.color }"></span>
              {{ opt.label }}
            </n-radio>
          </n-space>
        </n-radio-group>
      </n-form-item>
      <n-form-item label="备注">
        <n-input v-model:value="form.notes" type="textarea" :rows="2" placeholder="可选" />
      </n-form-item>
      <n-form-item label="已选时间段">
        <ul class="slot-list">
          <li v-for="(r, idx) in ranges" :key="idx">{{ formatRange(r) }}</li>
        </ul>
      </n-form-item>
    </n-form>
    <template #footer>
      <div style="display: flex; justify-content: flex-end; gap: 0.5em">
        <n-button @click="onUpdateShow(false)">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="handleSubmit">确定</n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false },
  ranges: { type: Array, default: () => [] } // [{ date: Date, start: Number(分钟), end: Number(分钟) }]
})
const emit = defineEmits(['update:show', 'created'])

const message = useMessage()
const submitting = ref(false)

const defaultForm = () => ({ title: '', quadrant_type: '', notes: '' })
const form = ref(defaultForm())

const quadrantOptions = [
  { label: '重要且紧急', value: 'urgent_important', color: '#f5222d' },
  { label: '紧急不重要', value: 'urgent_not_important', color: '#faad14' },
  { label: '重要不紧急', value: 'important_not_urgent', color: '#1890ff' },
  { label: '不紧急不重要', value: 'not_urgent_not_important', color: '#909399' }
]

const onUpdateShow = (value) => emit('update:show', value)

watch(
  () => props.show,
  (visible) => {
    if (visible) form.value = defaultForm()
  }
)

const pad = (n) => String(n).padStart(2, '0')
const formatMin = (min) => `${pad(Math.floor(min / 60))}:${pad(min % 60)}`
const formatRange = (r) => {
  const label = r.date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric', weekday: 'short' })
  return `${label} ${formatMin(r.start)}–${formatMin(r.end)}`
}

const minutesToDate = (baseDate, minutes) => {
  const d = new Date(baseDate)
  d.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0)
  return d
}

const handleSubmit = async () => {
  const title = form.value.title.trim()
  if (!title) {
    message.error('请输入标题')
    return
  }
  if (!form.value.quadrant_type) {
    message.error('请选择象限')
    return
  }
  submitting.value = true
  try {
    const payload = {
      title,
      quadrant_type: form.value.quadrant_type,
      notes: form.value.notes || null,
      time_blocks: props.ranges.map((r) => ({
        start_time: minutesToDate(r.date, r.start).toISOString(),
        end_time: minutesToDate(r.date, r.end).toISOString()
      }))
    }
    const res = await api.createTodo(payload)
    message.success('创建成功')
    emit('created', res.data)
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
.slot-list {
  font-size: 0.9em;
  opacity: 0.75;
  padding-left: 1.2em;
  margin: 0;
}
</style>
