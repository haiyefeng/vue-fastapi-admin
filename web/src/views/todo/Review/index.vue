<template>
  <div class="review-page">
    <n-spin :show="loading">
      <div class="review-header">
        <h2>回顾总结</h2>
        <n-button @click="openHistoryModal">查看历史回顾</n-button>
      </div>

      <section class="period-switcher">
        <n-radio-group v-model:value="periodType">
          <n-space>
            <n-radio v-for="opt in periodTypeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </n-radio>
          </n-space>
        </n-radio-group>
        <n-date-picker v-model:value="anchorDateMs" type="date" style="width: 160px" />
        <span v-if="summary" class="period-range-label">
          周期: {{ summary.period_start }} ~ {{ summary.period_end }}
        </span>
      </section>

      <section v-if="summary" id="data-review" class="metrics-section">
        <h3>数据回顾</h3>
        <div class="metrics-grid">
          <div class="metric-card">
            <h4>任务完成情况</h4>
            <p>
              <strong>总任务完成:</strong>
              {{ summary.task_completion.completed }} / {{ summary.task_completion.total }}
            </p>
            <p v-for="cat in summary.task_completion.by_category" :key="cat.category_id">
              <strong>{{ cat.category_name }}类完成:</strong> {{ cat.completed }} / {{ cat.total }}
            </p>
            <p>
              <strong>高优先级完成:</strong>
              {{ summary.task_completion.urgent_important_completed }} /
              {{ summary.task_completion.urgent_important_total }}
            </p>
          </div>
          <div class="metric-card">
            <h4>习惯打卡情况</h4>
            <p v-for="habit in summary.habits" :key="habit.habit_id">
              <strong>{{ habit.name }}:</strong>
              <template v-if="habit.streak !== null">
                完成 {{ habit.completed }} / {{ habit.expected }} 天（连续 {{ habit.streak }} 天）
              </template>
              <template v-else> 完成 {{ habit.completed }} / {{ habit.expected }} 次 </template>
            </p>
            <EmptyState v-if="!summary.habits.length" icon="material-symbols:eco-outline" text="还没有进行中的习惯" />
          </div>
          <div class="metric-card">
            <h4>计划进展</h4>
            <p v-for="goal in summary.goals" :key="goal.goal_id">
              <strong>{{ goal.name }}:</strong>
              <template v-if="goal.progress_percent !== null">
                +{{ goal.progress_percent }}%（完成 {{ goal.newly_completed }} 个关联任务）
              </template>
              <template v-else> 无明显进展 </template>
            </p>
            <EmptyState v-if="!summary.goals.length" icon="material-symbols:flag-outline" text="还没有进行中的计划" />
          </div>
        </div>
      </section>

      <n-divider />

      <section id="guided-reflection">
        <h3>引导式反思（七步提问法）</h3>
        <div v-for="step in reflectionSteps" :key="step.key" class="reflection-step">
          <h4>{{ step.title }}</h4>
          <p class="step-guidance">{{ step.guidance }}</p>
          <n-input
            v-model:value="answers[step.key]"
            type="textarea"
            :rows="4"
            :placeholder="step.placeholder"
          />
        </div>
      </section>

      <section id="action-plan">
        <h3>生成改进计划</h3>
        <p class="section-hint">
          根据你的反思，特别是第六、七步的思考，将具体的行动步骤转化为下阶段的计划/目标。
        </p>
        <ul v-if="sessionCreatedGoals.length" class="session-goal-list">
          <li v-for="goal in sessionCreatedGoals" :key="goal.id">{{ goal.name }}</li>
        </ul>
        <p v-else class="section-hint" style="text-align: center">暂无新计划</p>
        <n-button @click="showFormModal = true"><span>+ 添加新计划/目标...</span></n-button>
      </section>

      <div class="review-footer">
        <n-button :disabled="!summary" :loading="saving" @click="handleSave('draft')"
          >保存草稿</n-button
        >
        <n-button
          type="primary"
          :disabled="!summary"
          :loading="saving"
          @click="handleSave('completed')"
          >完成本次回顾</n-button
        >
      </div>
    </n-spin>

    <GoalFormModal v-model:show="showFormModal" :goal="null" @saved="handleGoalCreated" />

    <n-modal v-model:show="showHistoryModal" preset="card" title="历史回顾" style="width: 480px">
      <div
        v-for="item in historyList"
        :key="item.id"
        class="history-item"
        @click="jumpToReview(item)"
      >
        <span
          >{{ periodTypeLabel(item.period_type) }}回顾: {{ item.period_start }} ~
          {{ item.period_end }}</span
        >
        <span class="history-status">{{ item.status === 'completed' ? '已完成' : '草稿' }}</span>
      </div>
      <EmptyState v-if="!historyList.length" icon="material-symbols:history" text="还没有历史回顾" />
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, watch, onActivated } from 'vue'
import { useMessage } from 'naive-ui'
import api from '@/api'
import GoalFormModal from '../Goal/GoalFormModal.vue'
import EmptyState from '@/components/common/EmptyState.vue'

defineOptions({ name: '回顾总结' })

const message = useMessage()

const periodTypeOptions = [
  { label: '周', value: 'week' },
  { label: '月', value: 'month' },
  { label: '季度', value: 'quarter' },
  { label: '年', value: 'year' },
]

const reflectionSteps = [
  {
    key: 'step1',
    title: '第一步：负面 -> 正面',
    guidance:
      '回顾本周期，有哪些方面让你感觉不满意、效率不高或遇到了挑战？从这些挑战中，你观察到了哪些积极的信号、学习到的经验或值得肯定的地方？',
    placeholder:
      '例如：挑战是论文进展缓慢，感觉无从下手。但积极的是，我坚持完成了所有的日常习惯...',
  },
  {
    key: 'step2',
    title: '第二步：封闭 -> 开放',
    guidance:
      '针对你提到的某个亮点，具体是什么关键因素促成了它？除了这个因素，还有哪些其他可能的原因或条件帮助了你？',
    placeholder: '例如：关键因素是提前规划了任务优先级。其他原因可能包括本周期会议较少，干扰少...',
  },
  {
    key: 'step3',
    title: '第三步：单一 -> 复数',
    guidance:
      '为了在下个周期继续保持这个亮点，或者改进某个挑战，有哪些不同的方法、策略或途径可以尝试？（至少想出2-3种）',
    placeholder:
      '例如：保持任务完成度：1. 继续提前规划；2. 尝试番茄工作法；3. 预留特定时间处理邮件...',
  },
  {
    key: 'step4',
    title: '第四步：现实 -> 可能性',
    guidance:
      '想象一下，如果某个挑战完全不成问题，或者某个亮点能发挥到极致，未来可能会出现哪些令人兴奋的新机会或可能性？',
    placeholder: '例如：如果论文顺利，可以提前开始找实习，或者有更多时间学习新技术...',
  },
  {
    key: 'step5',
    title: '第五步：发散 -> 聚焦',
    guidance:
      '在所有这些可能性和你想改进的方面中，下个周期你最想集中精力去突破或改进的一个具体领域是什么？明确你的核心焦点。',
    placeholder: '例如：下个周期的核心焦点是：切实推进毕业论文的写作进度...',
  },
  {
    key: 'step6',
    title: '第六步：静态 -> 动态',
    guidance:
      '为了在你选择的核心焦点上取得看得见的、持续的进步，下个周期你可以采取哪些非常具体的、可衡量的行动步骤？（将它们转化为计划或任务）',
    placeholder:
      '例如：1. 与导师预约时间讨论论文框架；2. 每天固定时段为论文写作时间；3. 完成文献综述初稿...',
  },
  {
    key: 'step7',
    title: '第七步：个体 -> 系统',
    guidance:
      '从更宏观或系统的角度思考，改进核心焦点将如何影响你的其他目标（工作/学习）、习惯或整体生活状态？为了更好地支持这项改进，你是否需要调整外部环境、内部流程或其他相关系统？',
    placeholder: '例如：推进论文能减轻焦虑，提升整体幸福感。为支持写作，需要保证充足睡眠...',
  },
]

const defaultAnswers = () => ({
  step1: '',
  step2: '',
  step3: '',
  step4: '',
  step5: '',
  step6: '',
  step7: '',
})

const loading = ref(false)
const saving = ref(false)
const periodType = ref('week')
const anchorDateMs = ref(Date.now())
const summary = ref(null)
const answers = ref(defaultAnswers())
const sessionCreatedGoals = ref([])
const showFormModal = ref(false)
const showHistoryModal = ref(false)
const historyList = ref([])

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

const anchorDateStr = computed(() => formatLocalDateString(anchorDateMs.value))

const periodTypeLabel = (pt) => periodTypeOptions.find((opt) => opt.value === pt)?.label || pt

const loadAll = async () => {
  loading.value = true
  sessionCreatedGoals.value = []
  try {
    const [summaryRes, detailRes] = await Promise.all([
      api.getReviewDataSummary(periodType.value, anchorDateStr.value),
      api.getReviewDetail(periodType.value, anchorDateStr.value),
    ])
    summary.value = summaryRes.data
    if (detailRes.data) {
      answers.value = { ...defaultAnswers(), ...detailRes.data.answers }
    } else {
      answers.value = defaultAnswers()
    }
  } catch (error) {
    console.error('加载回顾数据失败:', error)
    message.error('加载回顾数据失败')
    summary.value = null
    answers.value = defaultAnswers()
  } finally {
    loading.value = false
  }
}

watch([periodType, anchorDateStr], loadAll)

const handleSave = async (status) => {
  saving.value = true
  try {
    await api.saveReview({
      period_type: periodType.value,
      anchor_date: anchorDateStr.value,
      answers: answers.value,
      status,
    })
    message.success(status === 'completed' ? '回顾已完成' : '草稿已保存')
  } catch (error) {
    console.error('保存回顾失败:', error)
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleGoalCreated = (goal) => {
  if (goal) {
    sessionCreatedGoals.value.push(goal)
  }
}

const openHistoryModal = async () => {
  showHistoryModal.value = true
  try {
    const res = await api.getReviewList()
    historyList.value = res.data || []
  } catch (error) {
    console.error('获取历史回顾失败:', error)
    message.error('获取历史回顾失败')
  }
}

const jumpToReview = (item) => {
  periodType.value = item.period_type
  anchorDateMs.value = parseLocalDateString(item.period_start)
  showHistoryModal.value = false
}

// onActivated 同时覆盖首次挂载和每次 KeepAlive 重新激活（Vue 首次挂载也会触发 onActivated），
// 不需要再额外写 onMounted，否则首次进入页面会重复请求两次
onActivated(loadAll)
</script>

<style scoped>
.review-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 20px 24px;
}
.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1em;
}
.period-switcher {
  display: flex;
  align-items: center;
  gap: 1em;
  margin-bottom: 1.5em;
}
.period-range-label {
  opacity: 0.6;
  font-size: 0.9em;
}
.metrics-section {
  margin-bottom: 1.5em;
}
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5em;
}
.metric-card {
  background: var(--dt-card-bg, transparent);
  border: 1px solid var(--dt-border);
  border-radius: var(--dt-radius-lg);
  padding: 22px 20px 18px;
  box-shadow: var(--dt-shadow-sm);
  transition: box-shadow 0.25s ease, transform 0.25s ease;
}
.metric-card:hover {
  box-shadow: var(--dt-shadow-md);
  transform: translateY(-2px);
}
.metric-card h4 {
  margin: 0 0 0.6em;
  font-size: 0.95em;
  font-weight: 700;
}
.metric-card p {
  margin: 0.4em 0;
  font-size: 0.92em;
}
.reflection-step {
  margin-bottom: 1.2em;
  padding: 1.2em 1.4em;
  background-color: var(--dt-page-bg, rgba(128, 128, 128, 0.06));
  border: 1px solid var(--dt-border);
  border-radius: var(--dt-radius-md);
}
.reflection-step h4 {
  margin: 0 0 0.5em;
  font-weight: 700;
}
.step-guidance {
  opacity: 0.65;
  font-size: 0.85em;
  margin-bottom: 0.8em;
  line-height: 1.6;
}
.section-hint {
  opacity: 0.6;
  font-size: 0.9em;
}
.session-goal-list {
  margin: 0 0 1em;
  padding-left: 1.2em;
}
.review-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.8em;
  margin-top: 2em;
}
.history-item {
  display: flex;
  justify-content: space-between;
  padding: 0.6em 0;
  border-bottom: 1px solid rgba(128, 128, 128, 0.12);
  cursor: pointer;
}
.history-status {
  opacity: 0.6;
  font-size: 0.85em;
}
</style>
