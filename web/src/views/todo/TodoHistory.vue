<template>
  <div class="todo-history">
    <!-- 筛选区域 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filterForm">
        <el-form-item label="日期范围">
          <el-date-picker v-model="filterForm.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期"
            end-placeholder="结束日期" :shortcuts="dateShortcuts" @change="handleDateChange" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :span="16">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>每日完成待办数量</span>
            </div>
          </template>
          <div ref="dailyChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <span>四象限待办分布</span>
            </div>
          </template>
          <div ref="quadrantChartRef" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 已完成待办列表 -->
    <el-card class="list-card">
      <template #header>
        <div class="card-header">
          <span>已完成待办列表</span>
        </div>
      </template>
      <el-table v-loading="loading" :data="completedTodos" style="width: 100%" @sort-change="handleSortChange">
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="quadrant_type" label="象限" width="120">
          <template #default="{ row }">
            <el-tag :type="getQuadrantTagType(row.quadrant_type)">
              {{ getQuadrantLabel(row.quadrant_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="due_date" label="截止日期" width="120" sortable="custom" />
        <el-table-column prop="completed_at" label="完成时间" width="180" sortable="custom" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleViewDetail(row)">查看</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[10, 20, 50, 100]"
          :total="total" layout="total, sizes, prev, pager, next, jumper" @size-change="handleSizeChange"
          @current-change="handleCurrentChange" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import todoApi from '@/api/todo'
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox } from 'element-plus'

const filterForm = ref({
  dateRange: []
})

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

// 图表相关
const dailyChartRef = ref(null)
const quadrantChartRef = ref(null)
let dailyChart = null
let quadrantChart = null

// 列表相关
const loading = ref(false)
const completedTodos = ref([])
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const sortConfig = ref({
  prop: '',
  order: ''
})

// 初始化图表
const initCharts = () => {
  if (dailyChartRef.value) {
    dailyChart = echarts.init(dailyChartRef.value)
  }
  if (quadrantChartRef.value) {
    quadrantChart = echarts.init(quadrantChartRef.value)
  }
}

// 更新每日完成待办图表
const updateDailyChart = (data) => {
  if (!dailyChart) return

  const dates = data.map(item => item.date)
  const completedCounts = data.map(item => item.total)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
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
        name: '完成数量',
        type: 'bar',
        data: completedCounts,
        itemStyle: {
          color: '#409eff'
        }
      }
    ]
  }

  dailyChart.setOption(option)
}

// 更新四象限分布图表
const updateQuadrantChart = (data) => {
  if (!quadrantChart) return

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left'
    },
    series: [
      {
        name: '四象限分布',
        type: 'pie',
        radius: '50%',
        data: [
          { value: data.urgent_important || 0, name: '重要且紧急' },
          { value: data.urgent_not_important || 0, name: '紧急不重要' },
          { value: data.important_not_urgent || 0, name: '重要不紧急' },
          { value: data.not_urgent_not_important || 0, name: '不紧急不重要' }
        ],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }

  quadrantChart.setOption(option)
}

// 获取已完成待办列表
const fetchCompletedTodos = async () => {
  loading.value = true
  try {
    const params = {
      is_completed: true,
      page: currentPage.value,
      page_size: pageSize.value,
      start_date: filterForm.value.dateRange[0],
      end_date: filterForm.value.dateRange[1],
      sort_by: sortConfig.value.prop,
      sort_order: sortConfig.value.order
    }
    const response = await todoApi.getTodos(params)
    completedTodos.value = response.items
    total.value = response.total
  } catch (error) {
    console.error('获取已完成待办列表失败:', error)
    ElMessage.error('获取已完成待办列表失败')
  } finally {
    loading.value = false
  }
}

// 获取统计数据
const fetchStatistics = async () => {
  try {
    const [dailyStats, quadrantStats] = await Promise.all([
      todoApi.getDailyStatistics({
        start_date: filterForm.value.dateRange[0],
        end_date: filterForm.value.dateRange[1]
      }),
      todoApi.getQuadrantStatistics()
    ])
    updateDailyChart(dailyStats)
    updateQuadrantChart(quadrantStats)
  } catch (error) {
    console.error('获取统计数据失败:', error)
    ElMessage.error('获取统计数据失败')
  }
}

// 事件处理函数
const handleDateChange = () => {
  handleSearch()
}

const handleSearch = () => {
  currentPage.value = 1
  fetchCompletedTodos()
  fetchStatistics()
}

const handleReset = () => {
  filterForm.value.dateRange = []
  handleSearch()
}

const handleSizeChange = (val) => {
  pageSize.value = val
  fetchCompletedTodos()
}

const handleCurrentChange = (val) => {
  currentPage.value = val
  fetchCompletedTodos()
}

const handleSortChange = ({ prop, order }) => {
  sortConfig.value = { prop, order }
  fetchCompletedTodos()
}

const handleViewDetail = (row) => {
  // TODO: 实现查看详情功能
  console.log('查看详情:', row)
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除这条待办记录吗？', '提示', {
      type: 'warning'
    })
    await todoApi.deleteTodo(row.id)
    ElMessage.success('删除成功')
    fetchCompletedTodos()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除待办失败:', error)
      ElMessage.error('删除待办失败')
    }
  }
}

// 象限标签相关
const getQuadrantLabel = (type) => {
  const labels = {
    URGENT_IMPORTANT: '重要且紧急',
    URGENT_NOT_IMPORTANT: '紧急不重要',
    IMPORTANT_NOT_URGENT: '重要不紧急',
    NOT_URGENT_NOT_IMPORTANT: '不紧急不重要'
  }
  return labels[type] || type
}

const getQuadrantTagType = (type) => {
  const types = {
    URGENT_IMPORTANT: 'danger',
    URGENT_NOT_IMPORTANT: 'warning',
    IMPORTANT_NOT_URGENT: 'primary',
    NOT_URGENT_NOT_IMPORTANT: 'info'
  }
  return types[type] || 'info'
}

// 生命周期钩子
onMounted(() => {
  initCharts()
  // 默认显示最近一周的数据
  filterForm.value.dateRange = dateShortcuts[0].value()
  handleSearch()
})

onUnmounted(() => {
  if (dailyChart) {
    dailyChart.dispose()
  }
  if (quadrantChart) {
    quadrantChart.dispose()
  }
})
</script>

<style scoped>
.todo-history {
  padding: 20px;
}

.filter-card {
  margin-bottom: 20px;
}

.chart-row {
  margin-bottom: 20px;
}

.chart-card {
  height: 400px;
}

.chart-container {
  height: 350px;
}

.list-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>