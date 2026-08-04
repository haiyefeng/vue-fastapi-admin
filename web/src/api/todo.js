import { request } from '@/utils'

/**
 * 待办事项API接口
 */
export default {
    /**
     * 获取待办事项列表，支持筛选
     * @param {Object} params - 筛选参数
     * @param {Number} params.page - 页码
     * @param {Number} params.page_size - 每页数量
     * @param {String} params.quadrant_type - 象限类型
     * @param {Boolean} params.is_completed - 是否已完成
     * @param {String} params.start_date - 开始日期
     * @param {String} params.end_date - 结束日期
     * @returns {Promise} - 返回待办事项列表
     */
    getTodos: (params = {}) => request.get('/todo/list', { params }),

    /**
     * 创建新待办事项
     * @param {Object} data - 待办事项数据
     * @param {String} data.title - 标题
     * @param {String} data.quadrant_type - 象限类型
     * @param {String} data.due_date - 截止日期（可选）
     * @returns {Promise} - 返回创建的待办事项
     */
    createTodo: (data = {}) => request.post('/todo/create', data),

    /**
     * 获取指定ID的待办事项
     * @param {Number} id - 待办事项ID
     * @returns {Promise} - 返回待办事项详情
     */
    getTodoById: (id) => request.get('/todo/get', { params: { todo_id: id } }),

    /**
     * 更新待办事项
     * @param {Number} id - 待办事项ID
     * @param {Object} data - 更新的数据
     * @param {String} data.title - 标题（可选）
     * @param {String} data.quadrant_type - 象限类型（可选）
     * @param {String} data.due_date - 截止日期（可选）
     * @param {Boolean} data.is_completed - 是否已完成（可选）
     * @returns {Promise} - 返回更新后的待办事项
     */
    updateTodo: (id, data = {}) => request.post('/todo/update', { ...data, id }),

    /**
     * 删除待办事项
     * @param {Number} id - 待办事项ID
     * @returns {Promise} - 返回删除结果
     */
    deleteTodo: (id) => request.delete('/todo/delete', { params: { todo_id: id } }),

    /**
     * 获取按日期统计的已完成待办事项数量
     * @param {Object} params - 筛选参数
     * @param {String} params.start_date - 开始日期（可选）
     * @param {String} params.end_date - 结束日期（可选）
     * @returns {Promise} - 返回按日期统计的数据
     */
    getDailyStatistics: (params = {}) => request.get('/todo/statistics/daily', { params }),

    /**
     * 获取按象限统计的待办事项数量
     * @returns {Promise} - 返回按象限统计的数据
     */
    getQuadrantStatistics: () => request.get('/todo/statistics/quadrant')
} 