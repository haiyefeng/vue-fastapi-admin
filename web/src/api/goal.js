import { request } from '@/utils'

/**
 * 计划/目标API接口
 */
export default {
  /**
   * 获取当前用户进行中的计划列表
   * @returns {Promise}
   */
  getGoals: () => request.get('/goal/list'),

  /**
   * 获取已归档的计划列表
   * @returns {Promise}
   */
  getArchivedGoals: () => request.get('/goal/archived'),

  /**
   * 获取计划详情（含关联任务/习惯列表）
   * @param {Number} id
   * @returns {Promise}
   */
  getGoalDetail: (id) => request.get('/goal/detail', { params: { goal_id: id } }),

  /**
   * 创建计划
   * @param {Object} data
   * @returns {Promise}
   */
  createGoal: (data = {}) => request.post('/goal/create', data),

  /**
   * 更新计划
   * @param {Number} id
   * @param {Object} data
   * @returns {Promise}
   */
  updateGoal: (id, data = {}) => request.post('/goal/update', { ...data, id }),

  /**
   * 删除计划（关联任务/习惯自动解除关联，本身不受影响）
   * @param {Number} id
   * @returns {Promise}
   */
  deleteGoal: (id) => request.delete('/goal/delete', { params: { goal_id: id } }),
}
