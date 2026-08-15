<template>
  <div class="day-view">
    <div class="calendar-controls">
      <button class="button" @click="shiftDay(-1)">‹</button>
      <span>{{ dateLabel }}</span>
      <button class="button" @click="shiftDay(1)">›</button>
      <input type="date" class="form-control" :value="dateInputValue" @change="onDateInput" />
    </div>

    <div
      class="day-timeline"
      :style="{ height: 24 * HOUR_PX + 'px' }"
      @dragover.prevent="onDragOver"
      @dragleave="onDragLeave"
      @drop.prevent="onDrop"
    >
      <div v-for="hh in 24" :key="hh" class="hour-slot" :class="{ 'drop-hint': dropHintHour === hh - 1 }">
        <span class="hour-label">{{ pad(hh - 1) }}:00</span>
      </div>
      <div
        v-for="block in blocks"
        :key="block.id"
        class="day-event"
        :style="eventStyle(block)"
        :title="eventTitle(block)"
        @click="$emit('edit-todo', block.todo_item_id)"
      >
        <strong>{{ formatMin(block.startMin) }}</strong> {{ block.title }}
      </div>
      <div v-if="nowLineTop >= 0" class="now-line" :style="{ top: nowLineTop + 'px' }"></div>
    </div>

    <section class="unscheduled-section">
      <h3>未安排的任务（拖到时间轴上排程）</h3>
      <ul class="task-list">
        <li
          v-for="todo in unscheduledTodos"
          :key="todo.id"
          class="unscheduled-item"
          draggable="true"
          @dragstart="onDragStart(todo, $event)"
          @dragend="onDragEnd"
        >
          <span class="quadrant-dot" :style="{ background: quadrantColor(todo.quadrant_type) }"></span>
          {{ todo.title }}
          <span class="task-meta">{{ dueLabel(todo) }}</span>
        </li>
      </ul>
      <n-empty v-if="!unscheduledTodos.length" description="没有未安排的任务" />
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/api'

defineEmits(['edit-todo'])

const HOUR_PX = 48
const QUADRANT_COLORS = {
  urgent_important: '#f5222d',
  urgent_not_important: '#faad14',
  important_not_urgent: '#1890ff',
  not_urgent_not_important: '#909399'
}

function startOfDay(date) {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  return d
}

const currentDate = ref(startOfDay(new Date()))
const rawBlocks = ref([])
const unscheduledTodos = ref([])
const dragged = ref(null)
const dropHintHour = ref(null)

const pad = (n) => String(n).padStart(2, '0')
const formatMin = (min) => `${pad(Math.floor(min / 60))}:${pad(min % 60)}`
// 本地时间（非 UTC）序列化：后端 use_tz=False，按裸时间处理，不能用 toISOString()（会转成 UTC，
// 在 UTC+8 环境下会导致跨零点校验误判，例如本地 07:30–08:30 被错误当成跨天）。
const toLocalIsoString = (d) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`

const dateLabel = computed(() => {
  const d = currentDate.value
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日, ${weekdays[d.getDay()]}`
})

const dateInputValue = computed(() => {
  const d = currentDate.value
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
})

const quadrantColor = (type) => QUADRANT_COLORS[type] || '#909399'

const dueLabel = (todo) => {
  if (!todo.due_date) return '无截止时间'
  const due = new Date(todo.due_date)
  const today = startOfDay(new Date())
  if (startOfDay(due).getTime() === today.getTime()) return '今天截止'
  return `${due.getMonth() + 1}月${due.getDate()}日截止`
}

const blocks = computed(() =>
  rawBlocks.value.map((b) => {
    const start = new Date(b.start_time)
    const end = new Date(b.end_time)
    return {
      id: b.id,
      todo_item_id: b.todo_item_id,
      title: b.title,
      quadrant_type: b.quadrant_type,
      startMin: start.getHours() * 60 + start.getMinutes(),
      endMin: end.getHours() * 60 + end.getMinutes()
    }
  })
)

const eventStyle = (block) => ({
  top: `${(block.startMin / 60) * HOUR_PX}px`,
  height: `${((block.endMin - block.startMin) / 60) * HOUR_PX - 2}px`,
  backgroundColor: QUADRANT_COLORS[block.quadrant_type] || '#909399'
})
const eventTitle = (block) => `${block.title} ${formatMin(block.startMin)}–${formatMin(block.endMin)}`

const nowLineTop = computed(() => {
  const now = new Date()
  if (startOfDay(now).getTime() !== currentDate.value.getTime()) return -100
  return ((now.getHours() * 60 + now.getMinutes()) / 60) * HOUR_PX
})

const shiftDay = (delta) => {
  const d = new Date(currentDate.value)
  d.setDate(d.getDate() + delta)
  currentDate.value = d
  fetchAll()
}

const onDateInput = (evt) => {
  const [y, m, day] = evt.target.value.split('-').map(Number)
  currentDate.value = new Date(y, m - 1, day)
  fetchAll()
}

const onDragStart = (todo, evt) => {
  dragged.value = todo
  evt.dataTransfer.effectAllowed = 'move'
  evt.dataTransfer.setData('text/plain', String(todo.id))
}

const onDragOver = (evt) => {
  if (!dragged.value) return
  const rect = evt.currentTarget.getBoundingClientRect()
  const y = evt.clientY - rect.top
  dropHintHour.value = Math.max(0, Math.min(23, Math.floor(y / HOUR_PX)))
}

const onDragLeave = () => {
  dropHintHour.value = null
}

const onDragEnd = () => {
  // 兜底清理：拖拽被取消（松手在时间轴之外、按 Esc 等）时 drop 不会触发，
  // 但 dragend 总会触发，避免 dragged 状态残留到下一次拖拽
  dragged.value = null
  dropHintHour.value = null
}

const onDrop = async (evt) => {
  dropHintHour.value = null
  if (!dragged.value) return
  const rect = evt.currentTarget.getBoundingClientRect()
  const y = evt.clientY - rect.top
  let startMin = Math.floor(y / (HOUR_PX / 2)) * 30 // 30 分钟吸附
  startMin = Math.max(0, Math.min(1380, startMin)) // 钳制到 23:00，避免跨零点
  const endMinRaw = startMin + 60

  const start = new Date(currentDate.value)
  start.setHours(0, startMin, 0, 0)
  const end = new Date(currentDate.value)
  if (endMinRaw >= 1440) {
    end.setHours(23, 59, 59, 999)
  } else {
    end.setHours(0, endMinRaw, 0, 0)
  }

  const todo = dragged.value
  dragged.value = null
  try {
    await api.createTimeBlock({
      todo_item_id: todo.id,
      start_time: toLocalIsoString(start),
      end_time: toLocalIsoString(end)
    })
    await fetchAll()
  } catch (error) {
    console.error('创建时间块失败:', error)
  }
}

const fetchBlocks = async () => {
  const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  const res = await api.getTimeBlocks({ start_date: fmt(currentDate.value), end_date: fmt(currentDate.value) })
  rawBlocks.value = res.data || []
}

const fetchUnscheduled = async () => {
  const res = await api.getTodos({ unscheduled_only: true, page: 1, page_size: 200 })
  unscheduledTodos.value = res.data || []
}

const fetchAll = () => Promise.all([fetchBlocks(), fetchUnscheduled()])

defineExpose({ refresh: fetchAll })

onMounted(fetchAll)
</script>

<style scoped>
.calendar-controls {
  display: flex;
  align-items: center;
  gap: 0.8em;
  margin-bottom: 0.8em;
}
.button {
  padding: 0.4em 0.9em;
  border: 1px solid rgba(128, 128, 128, 0.3);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  color: inherit;
}
.form-control {
  padding: 0.4em 0.6em;
  border: 1px solid rgba(128, 128, 128, 0.3);
  border-radius: 4px;
  background: transparent;
  color: inherit;
}
.day-timeline {
  position: relative;
  border: 1px solid rgba(128, 128, 128, 0.3);
  user-select: none;
}
.hour-slot {
  height: 48px;
  border-bottom: 1px solid rgba(128, 128, 128, 0.15);
  position: relative;
  box-sizing: border-box;
}
.hour-slot.drop-hint {
  background: var(--dt-schedule-soft);
}
.hour-label {
  position: absolute;
  left: 6px;
  top: -0.55em;
  font-size: 0.75em;
  opacity: 0.6;
}
.day-event {
  position: absolute;
  left: 56px;
  right: 10px;
  border-radius: 6px;
  padding: 2px 6px;
  font-size: 0.85em;
  color: #fff;
  overflow: hidden;
  z-index: 2;
  box-sizing: border-box;
  cursor: pointer;
  box-shadow: var(--dt-shadow-sm);
  transition: filter 0.15s ease;
}
.day-event:hover {
  filter: brightness(0.94);
}
.now-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--dt-quadrant-urgent-important, #f5222d);
  z-index: 3;
  pointer-events: none;
  box-shadow: 0 0 4px rgba(245, 34, 45, 0.4);
}
.unscheduled-section {
  margin-top: 2em;
}
.unscheduled-section h3 {
  font-size: 1em;
  margin-bottom: 0.6em;
}
.task-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.unscheduled-item {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.6em 0.5em;
  border-radius: var(--dt-radius-sm);
  cursor: grab;
  transition: background 0.15s ease;
}
.unscheduled-item:hover {
  background: var(--dt-surface-subtle);
}
.unscheduled-item:active {
  cursor: grabbing;
}
.quadrant-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.task-meta {
  margin-left: auto;
  font-size: 0.8em;
  opacity: 0.6;
}
</style>
