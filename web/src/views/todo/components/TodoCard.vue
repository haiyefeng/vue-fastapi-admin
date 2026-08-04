<template>
  <div
    class="todo-card"
    :class="{ 'is-completed': todo.is_completed }"
  >
    <div class="todo-content">
      <div class="todo-header">
        <n-checkbox
          :checked="todo.is_completed"
          @update:checked="$emit('complete', todo)"
        />
        <h4 class="todo-title">{{ todo.title }}</h4>
      </div>
      <div class="todo-info">
        <div class="info-item">
          <n-icon><calendar /></n-icon>
          <span>创建时间：{{ formatDate(todo.created_at) }}</span>
        </div>
        <div v-if="todo.due_date" class="info-item">
          <n-icon><time /></n-icon>
          <span>截止日期：{{ formatDate(todo.due_date) }}</span>
        </div>
      </div>
    </div>
    <div class="todo-actions">
      <n-button
        quaternary
        circle
        type="info"
        @click="$emit('move', todo)"
      >
        <template #icon>
          <n-icon><arrow-right /></n-icon>
        </template>
      </n-button>
      <n-button
        quaternary
        circle
        type="error"
        @click="$emit('delete', todo)"
      >
        <template #icon>
          <n-icon><trash /></n-icon>
        </template>
      </n-button>
    </div>
  </div>
</template>

<script setup>
import { Calendar, Time, ArrowRight, Trash } from '@vicons/carbon'
import { formatDate } from '@/utils/format'

defineOptions({ name: 'TodoCard' })

defineProps({
  todo: {
    type: Object,
    required: true
  }
})

defineEmits(['complete', 'move', 'delete'])
</script>

<style scoped>
.todo-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 6px;
  transition: all 0.3s ease;
}

.todo-card:hover {
  background: #f0f0f0;
}

.todo-card.is-completed {
  opacity: 0.7;
}

.todo-card.is-completed .todo-title {
  text-decoration: line-through;
  color: #999;
}

.todo-content {
  flex: 1;
  margin-right: 12px;
}

.todo-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.todo-title {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
}

.todo-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #666;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.todo-actions {
  display: flex;
  gap: 4px;
}

/* 暗色模式适配 */
:root.dark .todo-card {
  background: #2a2a2a;
}

:root.dark .todo-card:hover {
  background: #333;
}

:root.dark .todo-info {
  color: #999;
}
</style> 