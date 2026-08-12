<template>
  <n-modal :show="show" preset="card" title="计划详情" style="width: 560px" @update:show="onUpdateShow">
    <n-spin :show="loading">
      <template v-if="detail">
        <h3 style="margin: 0 0 0.3em">{{ detail.name }}</h3>
        <p v-if="detail.target_date" style="opacity: 0.6; font-size: 0.9em; margin: 0 0 0.8em">
          目标日期: {{ detail.target_date }}
        </p>
        <p v-if="detail.description" style="margin: 0 0 1em">{{ detail.description }}</p>

        <n-divider />

        <section>
          <h4 style="font-size: 1em; font-weight: 600; margin-bottom: 0.6em">
            关联任务（{{ completedTaskCount }}/{{ detail.tasks.length }} 完成）
          </h4>
          <div v-for="task in detail.tasks" :key="task.id" class="goal-task-row">
            <n-checkbox :checked="task.is_completed" @update:checked="(v) => toggleTask(task, v)" />
            <span :class="{ 'task-completed': task.is_completed }">{{ task.title }}</span>
          </div>
          <n-empty v-if="!detail.tasks.length" description="还没有关联任务" size="small" />
        </section>

        <n-divider />

        <section>
          <h4 style="font-size: 1em; font-weight: 600; margin-bottom: 0.6em">关联习惯</h4>
          <div v-for="habit in detail.habits" :key="habit.id" class="goal-habit-row">
            <span>{{ habit.name }}</span>
            <span class="habit-frequency">{{ frequencyLabel(habit) }}</span>
          </div>
          <n-empty v-if="!detail.habits.length" description="还没有关联习惯" size="small" />
        </section>
      </template>
    </n-spin>
    <template #footer>
      <n-button @click="onUpdateShow(false)">关闭</n-button>
    </template>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import api from '@/api'

const props = defineProps({
  show: { type: Boolean, default: false },
  goalId: { type: Number, default: null }
})
const emit = defineEmits(['update:show'])

const message = useMessage()
const loading = ref(false)
const detail = ref(null)

const completedTaskCount = computed(() =>
  detail.value ? detail.value.tasks.filter((t) => t.is_completed).length : 0
)

const frequencyLabel = (habit) => {
  const config = habit.frequency_config || {}
  if (habit.frequency_type === 'daily') return '每天'
  if (habit.frequency_type === 'weekly_days') {
    const names = ['一', '二', '三', '四', '五', '六', '日']
    return '每周' + (config.days || []).map((d) => names[d - 1]).join('')
  }
  if (habit.frequency_type === 'weekly_count') return `每周${config.count}次`
  if (habit.frequency_type === 'interval_days') return `每隔${config.interval}天`
  return ''
}

const onUpdateShow = (value) => emit('update:show', value)

const loadDetail = async () => {
  if (!props.goalId) return
  loading.value = true
  try {
    const res = await api.getGoalDetail(props.goalId)
    detail.value = res.data
  } catch (error) {
    console.error('获取计划详情失败:', error)
    message.error('获取计划详情失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.show, props.goalId],
  ([visible]) => {
    if (visible) loadDetail()
  }
)

const toggleTask = async (task, checked) => {
  const previous = task.is_completed
  task.is_completed = checked
  try {
    await api.updateTodo(task.id, { is_completed: checked })
  } catch (error) {
    console.error('更新任务状态失败:', error)
    message.error('更新任务状态失败')
    task.is_completed = previous
  }
}
</script>

<style scoped>
.goal-task-row,
.goal-habit-row {
  display: flex;
  align-items: center;
  gap: 0.5em;
  padding: 0.3em 0;
}
.goal-habit-row {
  justify-content: space-between;
}
.task-completed {
  text-decoration: line-through;
  opacity: 0.5;
}
.habit-frequency {
  font-size: 0.85em;
  opacity: 0.6;
}
</style>
