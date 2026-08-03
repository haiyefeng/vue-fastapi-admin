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

    <!-- 待办详情对话框 -->
    <client-only>
      <component :is="renderDetailModal()" />
    </client-only>
  </AppPage>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, h } from 'vue'
import { useMessage, NPopover, NSpace, NModal, NButton, NPopconfirm, NTag } from 'naive-ui'
import todoApi from '@/api/todo'
import * as echarts from 'echarts'
import { useDialog } from 'naive-ui'

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
const columns = ref([
  {
    title: '标题',
    key: 'title',
    sorter: true
  },
  {
    title: '象限',
    key: 'quadrant_type',
    render(row) {
      const typeMap = {
        urgent_important: { text: '重要且紧急', color: '#f5222d' },
        urgent_not_important: { text: '紧急不重要', color: '#faad14' },
        important_not_urgent: { text: '重要不紧急', color: '#1890ff' },
        not_urgent_not_important: { text: '不紧急不重要', color: '#909399' }
      };
      const config = typeMap[row.quadrant_type] || { text: row.quadrant_type, color: '#909399' };
      return h(NTag, { 
        type: 'default',
        style: { 
          backgroundColor: config.color,
          borderColor: config.color,
          color: '#fff'
        }
      }, { default: () => config.text });
    }
  },
  {
    title: '截止时间',
    key: 'due_date',
    render(row) {
      return row.due_date ? new Date(row.due_date).toLocaleString() : '无';
    },
    sorter: true
  },
  {
    title: '完成时间',
    key: 'completed_at',
    render(row) {
      return row.completed_at ? new Date(row.completed_at).toLocaleString() : '无';
    },
    sorter: true
  },
  {
    title: '操作',
    key: 'actions',
    render(row) {
      return h(
        'div',
        { class: 'operations-column' },
        [
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
              onPositiveClick: () => handleDelete(row.id)
            },
            {
              trigger: () => h(NButton, { text: true, type: 'error' }, { default: () => '删除' }),
              default: () => '确定删除吗？'
            }
          )
        ]
      );
    }
  }
]);

// 查看待办详情
const detailModalVisible = ref(false)
const currentTodo = ref(null)

// 初始化图表
const initCharts = async () => {
  await nextTick()

  try {
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
          { value: data.important_not_urgent || 0, name: '重要不紧急', itemStyle: { color: '#1890ff' } },
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

const handleViewDetail = (todo) => {
  currentTodo.value = todo
  detailModalVisible.value = true
}

const handleDelete = async (id) => {
  try {
    await todoApi.deleteTodo(id)
    message.success('删除成功')
    fetchCompletedTodos()
  } catch (error) {
    console.error('删除待办失败:', error)
    message.error('删除待办失败')
  }
}

// 渲染详情对话框
const renderDetailModal = () => {
  return h(
    NModal,
    {
      show: detailModalVisible.value,
      preset: 'card',
      title: '待办详情',
      style: { width: '500px' },
      onUpdateShow: (v) => { detailModalVisible.value = v }
    },
    {
      default: () => [
        h('div', { class: 'p-4 detail-modal-content' }, [
          // 标题
          h('div', { class: 'detail-item' }, [
            h('div', { class: 'detail-label' }, '标题'),
            h('div', { class: 'detail-value font-bold text-16' }, currentTodo.value?.title || '')
          ]),
          
          // 象限
          h('div', { class: 'detail-item' }, [
            h('div', { class: 'detail-label' }, '象限'),
            h('div', { class: 'detail-value' }, [
              (() => {
                const config = getQuadrantTypeConfig(currentTodo.value?.quadrant_type);
                return h(NTag, 
                  { 
                    type: 'default',
                    size: 'medium',
                    style: { 
                      backgroundColor: config.color,
                      borderColor: config.color,
                      color: '#fff'
                    }
                  },
                  { default: () => config.text }
                );
              })()
            ])
          ]),
          
          // 截止时间
          h('div', { class: 'detail-item' }, [
            h('div', { class: 'detail-label' }, '截止时间'),
            h('div', { class: 'detail-value' }, currentTodo.value?.due_date ? new Date(currentTodo.value.due_date).toLocaleString() : '无')
          ]),
          
          // 创建时间
          h('div', { class: 'detail-item' }, [
            h('div', { class: 'detail-label' }, '创建时间'),
            h('div', { class: 'detail-value' }, currentTodo.value?.created_at ? new Date(currentTodo.value.created_at).toLocaleString() : '无')
          ]),
          
          // 完成时间
          h('div', { class: 'detail-item' }, [
            h('div', { class: 'detail-label' }, '完成时间'),
            h('div', { class: 'detail-value' }, currentTodo.value?.completed_at ? new Date(currentTodo.value.completed_at).toLocaleString() : '无')
          ]),
        ])
      ],
      footer: () => h(
        NButton,
        {
          type: 'primary',
          onClick: () => { detailModalVisible.value = false }
        },
        { default: () => '关闭' }
      )
    }
  )
}

// 获取象限类型配置
const getQuadrantTypeConfig = (type) => {
  const typeMap = {
    urgent_important: { text: '重要且紧急', color: '#f5222d' },
    urgent_not_important: { text: '紧急不重要', color: '#faad14' },
    important_not_urgent: { text: '重要不紧急', color: '#1890ff' },
    not_urgent_not_important: { text: '不紧急不重要', color: '#909399' }
  };
  return typeMap[type] || { text: type || '未知', color: '#909399' };
}

// 生命周期钩子
onMounted(async () => {
  // 设置默认日期范围：最近一周，包含当天
  const end = new Date()
  end.setHours(23, 59, 59, 999) // 设置为当天的最后一毫秒
  const start = new Date()
  start.setDate(start.getDate() - 6) // 从今天开始往前7天（包含今天）
  start.setHours(0, 0, 0, 0) // 设置为起始日的第一毫秒
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

<style>
.detail-modal-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-label {
  color: #555;
  font-size: 14px;
  font-weight: 500;
}

.detail-value {
  color: #333;
  font-size: 15px;
}

/* 表格操作栏居中对齐 */
.operations-column {
  display: flex;
  justify-content: flex-start;
  gap: 12px;
}
</style>