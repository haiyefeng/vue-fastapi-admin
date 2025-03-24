<template>
  <AppPage :show-footer="false">
    <n-card rounded-10 mb-4>
      <n-grid :cols="4" :x-gap="12">
        <n-form-item-gi :span="3" label="日期范围">
          <n-date-picker type="daterange" v-model:value="filterForm.dateRange" clearable />
        </n-form-item-gi>
        <n-form-item-gi :span="1" label=" ">
          <n-button type="primary" @click="handleSearch">查询</n-button>
          <n-button ml-2 @click="handleReset">重置</n-button>
        </n-form-item-gi>
      </n-grid>
    </n-card>

    <n-grid :cols="24" :x-gap="12" mb-4>
      <n-grid-item :span="16">
        <n-card title="每日完成待办数量" rounded-10>
          <div ref="dailyChartRef" style="height: 350px;"></div>
        </n-card>
      </n-grid-item>
      <n-grid-item :span="8">
        <n-card title="四象限待办分布" rounded-10>
          <div ref="quadrantChartRef" style="height: 350px;"></div>
        </n-card>
      </n-grid-item>
    </n-grid>

    <n-card title="已完成待办列表" rounded-10>
      <n-data-table :loading="loading" :columns="columns" :data="completedTodos" :pagination="pagination"
        @update:page="handlePageChange" @update:page-size="handlePageSizeChange" @update:sorter="handleSortChange" />
    </n-card>
  </AppPage>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, h } from 'vue'
import { useMessage } from 'naive-ui'
import todoApi from '@/api/todo'
import * as echarts from 'echarts'
import { NButton, NPopconfirm, NTag, useDialog } from 'naive-ui'

const message = useMessage()
const dialog = useDialog()

// 过滤表单
const filterForm = ref({
  dateRange: null
})

// 图表相关
const dailyChartRef = ref(null)
const quadrantChartRef = ref(null)
let dailyChart = null
let quadrantChart = null

// 列表相关
const loading = ref(false)
const completedTodos = ref([])
const pagination = ref({
  page: 1,
  pageSize: 10,
  itemCount: 0,
  pageSizes: [10, 20, 50, 100],
  showSizePicker: true
})
const sortConfig = ref({
  prop: '',
  order: ''
})

// 表格列定义
const columns = [
  {
    title: '标题',
    key: 'title',
    width: 200
  },
  {
    title: '象限',
    key: 'quadrant_type',
    width: 120,
    render(row) {
      const typeMap = {
        urgent_important: {
          type: 'error',
          label: '重要且紧急'
        },
        urgent_not_important: {
          type: 'warning',
          label: '紧急不重要'
        },
        important_not_urgent: {
          type: 'primary',
          label: '重要不紧急'
        },
        not_urgent_not_important: {
          type: 'info',
          label: '不紧急不重要'
        }
      }
      const quadrant = typeMap[row.quadrant_type] || { type: 'default', label: row.quadrant_type }
      return h(NTag, { type: quadrant.type }, { default: () => quadrant.label })
    }
  },
  {
    title: '截止日期',
    key: 'due_date',
    width: 120,
    sorter: true
  },
  {
    title: '完成时间',
    key: 'completed_at',
    width: 180,
    sorter: true
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render(row) {
      return [
        h(
          NButton,
          {
            text: true,
            type: 'primary',
            onClick: () => handleViewDetail(row)
          },
          { default: () => '查看' }
        ),
        h(
          NPopconfirm,
          {
            onPositiveClick: () => handleDelete(row)
          },
          {
            default: () => '确定要删除这条待办记录吗？',
            trigger: () => h(
              NButton,
              {
                text: true,
                type: 'error',
                style: 'margin-left: 10px;'
              },
              { default: () => '删除' }
            )
          }
        )
      ]
    }
  }
]

// 初始化图表
const initCharts = async () => {
  await nextTick()

  try {
    console.log('dailyChartRef:', dailyChartRef.value)
    console.log('quadrantChartRef:', quadrantChartRef.value)

    if (dailyChartRef.value) {
      if (dailyChart) {
        dailyChart.dispose()
      }
      dailyChart = echarts.init(dailyChartRef.value)
      dailyChart.setOption({
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: ['加载中...']
        },
        yAxis: {
          type: 'value'
        },
        series: [{
          type: 'bar',
          data: [0]
        }]
      })
    }

    if (quadrantChartRef.value) {
      if (quadrantChart) {
        quadrantChart.dispose()
      }
      quadrantChart = echarts.init(quadrantChartRef.value)
      quadrantChart.setOption({
        tooltip: {
          trigger: 'item'
        },
        series: [{
          type: 'pie',
          radius: '50%',
          data: [
            { value: 0, name: '加载中...' }
          ]
        }]
      })
    }

    window.addEventListener('resize', handleResize)
    await fetchStatistics()
    handleResize()
  } catch (error) {
    console.error('图表初始化失败:', error)
  }
}

// 处理窗口大小改变
const handleResize = () => {
  if (dailyChart) {
    dailyChart.resize()
  }
  if (quadrantChart) {
    quadrantChart.resize()
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
          color: '#18a058'
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
          { value: data.urgent_important || 0, name: '重要且紧急', itemStyle: { color: '#d03050' } },
          { value: data.urgent_not_important || 0, name: '紧急不重要', itemStyle: { color: '#f0a020' } },
          { value: data.important_not_urgent || 0, name: '重要不紧急', itemStyle: { color: '#2080f0' } },
          { value: data.not_urgent_not_important || 0, name: '不紧急不重要', itemStyle: { color: '#909399' } }
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
    // 处理日期格式
    let startDate = null
    let endDate = null

    if (filterForm.value.dateRange && filterForm.value.dateRange.length === 2) {
      startDate = formatDate(filterForm.value.dateRange[0])
      endDate = formatDate(filterForm.value.dateRange[1])
    }

    const params = {
      is_completed: true,
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      start_date: startDate,
      end_date: endDate,
      sort_by: sortConfig.value.prop,
      sort_order: sortConfig.value.order
    }
    const response = await todoApi.getTodos(params)
    completedTodos.value = (response.data || []).filter(item => item !== null && item !== undefined)
    pagination.value.itemCount = response.total || 0
  } catch (error) {
    console.error('获取已完成待办列表失败:', error)
    message.error('获取已完成待办列表失败')
  } finally {
    loading.value = false
  }
}

// 获取统计数据
const fetchStatistics = async () => {
  try {
    // 处理日期格式
    let startDate = null
    let endDate = null

    if (filterForm.value.dateRange && filterForm.value.dateRange.length === 2) {
      startDate = formatDate(filterForm.value.dateRange[0])
      endDate = formatDate(filterForm.value.dateRange[1])
    }

    const [dailyStats, quadrantStats] = await Promise.all([
      todoApi.getDailyStatistics({
        start_date: startDate,
        end_date: endDate
      }),
      todoApi.getQuadrantStatistics()
    ])
    updateDailyChart(dailyStats.data || [])
    updateQuadrantChart(quadrantStats.data || {})
  } catch (error) {
    console.error('获取统计数据失败:', error)
    message.error('获取统计数据失败')
  }
}

// 格式化日期为 YYYY-MM-DD
const formatDate = (date) => {
  if (!date) return null
  if (typeof date === 'string') return date.split('T')[0]
  return new Date(date).toISOString().split('T')[0]
}

// 事件处理函数
const handleSearch = () => {
  pagination.value.page = 1
  fetchCompletedTodos()
  fetchStatistics()
}

const handleReset = () => {
  filterForm.value.dateRange = null
  handleSearch()
}

const handlePageChange = (page) => {
  pagination.value.page = page
  fetchCompletedTodos()
}

const handlePageSizeChange = (pageSize) => {
  pagination.value.pageSize = pageSize
  pagination.value.page = 1
  fetchCompletedTodos()
}

const handleSortChange = (sorter) => {
  if (sorter) {
    sortConfig.value.prop = sorter.columnKey
    sortConfig.value.order = sorter.order
  } else {
    sortConfig.value.prop = ''
    sortConfig.value.order = ''
  }
  fetchCompletedTodos()
}

const handleViewDetail = (row) => {
  // TODO: 实现查看详情功能
  console.log('查看详情:', row)
}

const handleDelete = async (row) => {
  try {
    await todoApi.deleteTodo(row.id)
    message.success('删除成功')
    fetchCompletedTodos()
  } catch (error) {
    console.error('删除待办失败:', error)
    message.error('删除待办失败')
  }
}

// 生命周期钩子
onMounted(async () => {
  console.log('组件挂载完成')
  // 设置默认日期范围：最近一周
  const end = new Date()
  const start = new Date()
  start.setTime(start.getTime() - 3600 * 1000 * 24 * 7)
  filterForm.value.dateRange = [start, end]

  await initCharts()
  handleSearch()
})

onUnmounted(() => {
  if (dailyChart) {
    dailyChart.dispose()
  }
  if (quadrantChart) {
    quadrantChart.dispose()
  }
  window.removeEventListener('resize', handleResize)
})
</script>