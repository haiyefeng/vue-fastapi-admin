import { request } from '@/utils'

/**
 * 时间块API接口
 */
export default {
  /**
   * 获取时间块列表（按日期范围或按待办事项二选一）
   * @param {Object} params
   * @param {String} [params.start_date]
   * @param {String} [params.end_date]
   * @param {Number} [params.todo_item_id]
   * @returns {Promise}
   */
  getTimeBlocks: (params = {}) => request.get('/timeblock/list', { params }),

  /**
   * 为待办事项新增一个时间块
   * @param {Object} data
   * @param {Number} data.todo_item_id
   * @param {String} data.start_time
   * @param {String} data.end_time
   * @returns {Promise}
   */
  createTimeBlock: (data = {}) => request.post('/timeblock/create', data),

  /**
   * 删除时间块
   * @param {Number} id
   * @returns {Promise}
   */
  deleteTimeBlock: (id) => request.delete('/timeblock/delete', { params: { time_block_id: id } }),
}
