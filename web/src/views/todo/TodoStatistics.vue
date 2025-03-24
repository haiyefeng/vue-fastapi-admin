<template>
  <div class="todo-statistics">
    <el-card class="statistics-card">
      <template #header>
        <div class="card-header">
          <span>待办统计</span>
          <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期"
            end-placeholder="结束日期" :shortcuts="dateShortcuts" @change="handleDateChange" />
        </div>
      </template>

      <div class="statistics-content">
        <!-- 四象限统计 -->
        <div class="quadrant-stats">
          <h3>四象限分布</h3>
          <el-row :gutter="20">
            <el-col :span="12">
              <div class="quadrant-item urgent-important">
                <h4>重要且紧急</h4>
                <div class="count">{{ stats.urgent_important || 0 }}</div>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="quadrant-item urgent-not-important">
                <h4>紧急不重要</h4>
                <div class="count">{{ stats.urgent_not_important || 0 }}</div>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="quadrant-item important-not-urgent">
                <h4>重要不紧急</h4>
                <div class="count">{{ stats.important_not_urgent || 0 }}</div>
              </div>
            </el-col>
            <el-col :span="12">
              <div class="quadrant-item not-urgent-not-important">
                <h4>不紧急不重要</h4>
                <div class="count">{{ stats.not_urgent_not_important || 0 }}</div>
              </div>
            </el-col>
          </el-row>
        </div>

        <!-- 每日统计图表 -->
        <div class="daily-stats">
          <h3>每日待办数量</h3>
          <div ref="chartRef" style="height: 300px"></div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import todoApi from '@/api/todo'
import * as echarts from 'echarts'

const dateRange = ref([])
const stats = ref({})
const chartRef = ref(null)
let chart = null

const dateShortcuts = [
  {
    text: '最近一周',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 7)
      return [start, end]
    }
  },
  {
    text: '最近一个月',
    value: () => {
      const end = new Date()
      const start = new Date()
      start.setTime(start.getTime() - 3600 * 1000 * 24 * 30)
      return [start, end]
    }
  }
]

const initChart = () => {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)
}

const updateChart = (data) => {
  if (!chart) return

  const dates = data.map(item => item.date)
  const urgentImportant = data.map(item => item.urgent_important)
  const urgentNotImportant = data.map(item => item.urgent_not_important)
  const importantNotUrgent = data.map(item => item.important_not_urgent)
  const notUrgentNotImportant = data.map(item => item.not_urgent_not_important)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    legend: {
      data: ['重要且紧急', '紧急不重要', '重要不紧急', '不紧急不重要']
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates
    },
    yAxis: {
      type: 'value'
    },
    series: [
      {
        name: '重要且紧急',
        type: 'bar',
        stack: 'total',
        data: urgentImportant
      },
      {
        name: '紧急不重要',
        type: 'bar',
        stack: 'total',
        data: urgentNotImportant
      },
      {
        name: '重要不紧急',
        type: 'bar',
        stack: 'total',
        data: importantNotUrgent
      },
      {
        name: '不紧急不重要',
        type: 'bar',
        stack: 'total',
        data: notUrgentNotImportant
      }
    ]
  }

  chart.setOption(option)
}

const fetchData = async () => {
  try {
    const [quadrantStats, dailyStats] = await Promise.all([
      todoApi.getQuadrantStatistics(),
      todoApi.getDailyStatistics({
        start_date: dateRange.value[0],
        end_date: dateRange.value[1]
      })
    ])
    stats.value = quadrantStats
    updateChart(dailyStats)
  } catch (error) {
    console.error('获取统计数据失败:', error)
  }
}

const handleDateChange = () => {
  fetchData()
}

onMounted(() => {
  initChart()
  // 默认显示最近一周的数据
  dateRange.value = dateShortcuts[0].value()
  fetchData()
})

onUnmounted(() => {
  if (chart) {
    chart.dispose()
  }
})
</script>

<style scoped>
.todo-statistics {
  padding: 20px;
}

.statistics-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.statistics-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.quadrant-stats {
  margin-bottom: 20px;
}

.quadrant-item {
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  margin-bottom: 20px;
}

.quadrant-item h4 {
  margin: 0 0 10px 0;
  color: #fff;
}

.quadrant-item .count {
  font-size: 24px;
  font-weight: bold;
  color: #fff;
}

.urgent-important {
  background-color: #f56c6c;
}

.urgent-not-important {
  background-color: #e6a23c;
}

.important-not-urgent {
  background-color: #409eff;
}

.not-urgent-not-important {
  background-color: #909399;
}

.daily-stats {
  margin-top: 20px;
}
</style>