<template>
  <div class="schedule-page">
    <div class="schedule-view-toggle">
      <button class="toggle-btn" :class="{ active: viewMode === 'day' }" @click="viewMode = 'day'">日</button>
      <button class="toggle-btn" :class="{ active: viewMode === 'week' }" @click="viewMode = 'week'">周</button>
    </div>

    <WeekView v-if="viewMode === 'week'" ref="weekViewRef" @edit-todo="openDetail" />
    <DayView v-else ref="dayViewRef" @edit-todo="openDetail" />

    <TaskDetailModal
      v-model:show="detailShow"
      :todo-id="detailTodoId"
      :projects="projectList"
      @saved="handleTodoChanged"
      @deleted="handleTodoChanged"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import api from '@/api'
import WeekView from './WeekView.vue'
import DayView from './DayView.vue'
import TaskDetailModal from '../TaskList/TaskDetailModal.vue'

const viewMode = ref('week')
const weekViewRef = ref(null)
const dayViewRef = ref(null)
const detailShow = ref(false)
const detailTodoId = ref(null)
const projectList = ref([])

const openDetail = (todoId) => {
  detailTodoId.value = todoId
  detailShow.value = true
}

const handleTodoChanged = () => {
  weekViewRef.value?.refresh()
  dayViewRef.value?.refresh()
}

// 关闭详情弹窗时也刷新日历，避免弹窗内的局部修改（如删除时间块）未触发 @saved/@deleted 时，
// 色块未从日历上移除
watch(detailShow, (visible) => {
  if (!visible) handleTodoChanged()
})

onMounted(async () => {
  const res = await api.getProjects()
  projectList.value = res.data || []
})
</script>

<style scoped>
.schedule-page {
  padding: 16px;
  height: 100%;
  overflow-y: auto;
}
.schedule-view-toggle {
  display: flex;
  gap: 0.4em;
  margin-bottom: 1em;
}
.toggle-btn {
  padding: 0.4em 1em;
  border: 1px solid rgba(128, 128, 128, 0.3);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  color: inherit;
}
.toggle-btn.active {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
  border-color: #1890ff;
}
</style>
