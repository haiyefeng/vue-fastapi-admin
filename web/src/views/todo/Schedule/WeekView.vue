<template>
  <div class="week-view">
    <div class="schedule-toolbar">
      <button class="button" @click="shiftWeek(-1)">‹</button>
      <span class="week-label">{{ weekLabel }}</span>
      <button class="button" @click="shiftWeek(1)">›</button>
      <select v-model.number="granularity" class="form-control" @change="onGranularityChange">
        <option :value="15">15 分钟</option>
        <option :value="30">30 分钟</option>
        <option :value="60">1 小时</option>
      </select>
      <span class="mode-toggle">
        <button class="button" :class="{ active: mode === 'drag' }" @click="setMode('drag')">拖拽选择</button>
        <button class="button" :class="{ active: mode === 'multi' }" @click="setMode('multi')">多选格子</button>
      </span>
      <button v-if="mode === 'multi' && selected.size" class="button button-primary" @click="openCreateModal">
        完成选择
      </button>
      <button v-if="selected.size" class="button" @click="clearSelection">清空选择</button>
    </div>
    <div class="selection-summary">{{ selectionSummary }}</div>

    <div class="schedule-grid">
      <div class="time-gutter">
        <div class="day-head"></div>
        <div class="col-body">
          <div v-for="row in rowCount" :key="row" class="gutter-cell" :style="{ height: rowHeight + 'px' }">
            <span v-if="gutterLabel(row - 1)">{{ gutterLabel(row - 1) }}</span>
          </div>
        </div>
      </div>

      <div v-for="(day, dIdx) in weekDays" :key="dIdx" class="day-col" :class="{ today: isToday(day) }">
        <div class="day-head">{{ dayLabel(day) }}</div>
        <div
          class="col-body"
          :style="{ height: rowCount * rowHeight + 'px' }"
          @mousedown="onColumnMouseDown(dIdx, $event)"
          @mousemove="onColumnMouseMove(dIdx, $event)"
          @click="onColumnClick(dIdx, $event)"
        >
          <div
            v-for="row in rowCount"
            :key="row"
            class="slot-cell"
            :class="{ selected: isSelected(dIdx, (row - 1) * granularity), 'hour-end': isHourEnd(row - 1) }"
            :style="{ height: rowHeight + 'px' }"
          ></div>
          <div
            v-for="block in blocksForDay(dIdx)"
            :key="block.id"
            class="event-block"
            :style="eventBlockStyle(block)"
            :title="eventBlockTitle(block)"
            @mousedown.stop
            @click.stop="$emit('edit-todo', block.todo_item_id)"
          >
            {{ formatMin(block.startMin) }} {{ block.title }}
          </div>
          <div v-if="isToday(day)" class="now-line" :style="{ top: nowLineTop + 'px' }"></div>
        </div>
      </div>
    </div>

    <CreateTodoWithSlotsModal v-model:show="showCreateModal" :ranges="mergedRanges" @created="handleCreated" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '@/api'
import CreateTodoWithSlotsModal from './CreateTodoWithSlotsModal.vue'

defineEmits(['edit-todo'])

const QUADRANT_COLORS = {
  urgent_important: '#f5222d',
  urgent_not_important: '#faad14',
  important_not_urgent: '#1890ff',
  not_urgent_not_important: '#909399'
}

const granularity = ref(30)
const mode = ref('drag')
const selected = ref(new Set()) // "day-min"
const dragging = ref(false)
const dragDay = ref(null)
const dragAnchor = ref(null)
const showCreateModal = ref(false)
const rawBlocks = ref([])

const startOfWeek = (date) => {
  const d = new Date(date)
  const dow = (d.getDay() + 6) % 7 // 周一 = 0
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() - dow)
  return d
}

const weekStart = ref(startOfWeek(new Date()))

const weekDays = computed(() => {
  const days = []
  for (let i = 0; i < 7; i++) {
    const d = new Date(weekStart.value)
    d.setDate(d.getDate() + i)
    days.push(d)
  }
  return days
})

const weekLabel = computed(() => {
  const start = weekDays.value[0]
  const end = weekDays.value[6]
  const fmt = (d) => `${d.getMonth() + 1}月${d.getDate()}日`
  return `${start.getFullYear()}年 ${fmt(start)} - ${fmt(end)}`
})

const dayLabel = (date) => {
  const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const dow = (date.getDay() + 6) % 7
  return `${weekdays[dow]} ${date.getMonth() + 1}/${date.getDate()}`
}

const isToday = (date) => {
  const now = new Date()
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  )
}

const rowCount = computed(() => 1440 / granularity.value)
const rowHeight = computed(() => ({ 15: 16, 30: 26, 60: 44 })[granularity.value])
const isHourEnd = (rowIdx) => (rowIdx * granularity.value + granularity.value) % 60 === 0

const pad = (n) => String(n).padStart(2, '0')
const formatMin = (min) => `${pad(Math.floor(min / 60))}:${pad(min % 60)}`
const gutterLabel = (rowIdx) => {
  const min = rowIdx * granularity.value
  return min > 0 && min % 60 === 0 ? formatMin(min) : ''
}

const selectionKey = (day, min) => `${day}-${min}`
const isSelected = (day, min) => selected.value.has(selectionKey(day, min))

const mergedRanges = computed(() => {
  const byDay = new Map()
  selected.value.forEach((key) => {
    const [d, m] = key.split('-').map(Number)
    if (!byDay.has(d)) byDay.set(d, [])
    byDay.get(d).push(m)
  })
  const out = []
  Array.from(byDay.keys())
    .sort((a, b) => a - b)
    .forEach((d) => {
      const mins = byDay.get(d).sort((a, b) => a - b)
      let start = mins[0]
      let prev = mins[0]
      for (let i = 1; i <= mins.length; i++) {
        if (i === mins.length || mins[i] !== prev + granularity.value) {
          out.push({ date: weekDays.value[d], start, end: prev + granularity.value })
          start = mins[i]
        }
        prev = mins[i]
      }
    })
  return out
})

const selectionSummary = computed(() => {
  if (selected.value.size === 0) return ''
  const hours = ((selected.value.size * granularity.value) / 60).toFixed(2).replace(/\.?0+$/, '')
  return `已选 ${mergedRanges.value.length} 个时间段，合计 ${hours} 小时`
})

const clearSelection = () => {
  selected.value = new Set()
}

const setMode = (next) => {
  mode.value = next
  clearSelection()
}

const onGranularityChange = () => {
  clearSelection()
}

const applyDragRange = (day, cur) => {
  const lo = Math.min(dragAnchor.value, cur)
  const hi = Math.max(dragAnchor.value, cur)
  const next = new Set()
  for (let m = lo; m <= hi; m += granularity.value) next.add(selectionKey(day, m))
  selected.value = next
}

const minuteFromEvent = (evt) => {
  const rect = evt.currentTarget.getBoundingClientRect()
  const offsetY = evt.clientY - rect.top
  const row = Math.max(0, Math.min(rowCount.value - 1, Math.floor(offsetY / rowHeight.value)))
  return row * granularity.value
}

const onColumnMouseDown = (day, evt) => {
  if (mode.value !== 'drag') return
  dragging.value = true
  dragDay.value = day
  dragAnchor.value = minuteFromEvent(evt)
  applyDragRange(day, dragAnchor.value)
}

const onColumnMouseMove = (day, evt) => {
  if (!dragging.value || mode.value !== 'drag' || day !== dragDay.value) return
  applyDragRange(day, minuteFromEvent(evt))
}

const onColumnClick = (day, evt) => {
  if (mode.value !== 'multi') return
  const min = minuteFromEvent(evt)
  const key = selectionKey(day, min)
  const next = new Set(selected.value)
  next.has(key) ? next.delete(key) : next.add(key)
  selected.value = next
}

const stopDragging = () => {
  if (!dragging.value) return
  dragging.value = false
  if (selected.value.size) openCreateModal()
}

const openCreateModal = () => {
  showCreateModal.value = true
}

const handleCreated = () => {
  clearSelection()
  fetchBlocks()
}

const blocksForDay = (dIdx) => {
  const dayKey = weekDays.value[dIdx].toDateString()
  return rawBlocks.value
    .filter((b) => new Date(b.start_time).toDateString() === dayKey)
    .map((b) => {
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
}

const eventBlockStyle = (block) => ({
  top: `${(block.startMin * rowHeight.value) / granularity.value}px`,
  height: `${((block.endMin - block.startMin) * rowHeight.value) / granularity.value - 2}px`,
  backgroundColor: QUADRANT_COLORS[block.quadrant_type] || '#909399'
})

const eventBlockTitle = (block) => `${block.title} ${formatMin(block.startMin)}–${formatMin(block.endMin)}`

const nowLineTop = computed(() => {
  const now = new Date()
  const min = now.getHours() * 60 + now.getMinutes()
  return (min * rowHeight.value) / granularity.value
})

const shiftWeek = (delta) => {
  clearSelection()
  const d = new Date(weekStart.value)
  d.setDate(d.getDate() + delta * 7)
  weekStart.value = d
  fetchBlocks()
}

const fetchBlocks = async () => {
  const start = weekDays.value[0]
  const end = weekDays.value[6]
  const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  const res = await api.getTimeBlocks({ start_date: fmt(start), end_date: fmt(end) })
  rawBlocks.value = res.data || []
}

defineExpose({ refresh: fetchBlocks })

onMounted(() => {
  document.addEventListener('mouseup', stopDragging)
  document.addEventListener('mouseleave', stopDragging)
  fetchBlocks()
})

onUnmounted(() => {
  document.removeEventListener('mouseup', stopDragging)
  document.removeEventListener('mouseleave', stopDragging)
})
</script>

<style scoped>
.schedule-toolbar {
  display: flex;
  align-items: center;
  gap: 0.8em;
  margin-bottom: 0.8em;
  flex-wrap: wrap;
}
.week-label {
  font-size: 1.1em;
  font-weight: 500;
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
.mode-toggle .button.active,
.button-primary {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
  border-color: #1890ff;
}
.selection-summary {
  min-height: 1.5em;
  margin-bottom: 0.6em;
  font-size: 0.9em;
  opacity: 0.7;
}
.schedule-grid {
  display: flex;
  border: 1px solid rgba(128, 128, 128, 0.3);
  user-select: none;
}
.time-gutter {
  width: 56px;
  flex-shrink: 0;
  border-right: 1px solid rgba(128, 128, 128, 0.3);
}
.day-col {
  flex: 1;
  min-width: 0;
  border-right: 1px solid rgba(128, 128, 128, 0.15);
}
.day-col:last-child {
  border-right: none;
}
.day-head {
  height: 2.2em;
  line-height: 2.2em;
  text-align: center;
  font-size: 0.88em;
  font-weight: 500;
  border-bottom: 1px solid rgba(128, 128, 128, 0.3);
  white-space: nowrap;
  overflow: hidden;
}
.day-col.today .day-head {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
}
.col-body {
  position: relative;
}
.slot-cell {
  border-bottom: 1px dashed rgba(128, 128, 128, 0.15);
  box-sizing: border-box;
}
.slot-cell.hour-end {
  border-bottom: 1px solid rgba(128, 128, 128, 0.3);
}
.slot-cell:hover {
  background: rgba(128, 128, 128, 0.08);
}
.slot-cell.selected {
  background: rgba(24, 144, 255, 0.12);
  box-shadow: inset 0 0 0 1px #1890ff;
}
.gutter-cell {
  position: relative;
  box-sizing: border-box;
}
.gutter-cell span {
  position: absolute;
  top: -0.55em;
  right: 6px;
  font-size: 0.72em;
  opacity: 0.6;
}
.now-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: #f5222d;
  z-index: 3;
  pointer-events: none;
}
.event-block {
  position: absolute;
  left: 2px;
  right: 2px;
  border-radius: 4px;
  padding: 1px 4px;
  font-size: 0.76em;
  color: #fff;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  z-index: 2;
  box-sizing: border-box;
  cursor: pointer;
}
</style>
