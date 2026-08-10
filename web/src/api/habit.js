import { request } from '@/utils'

/**
 * 习惯API接口
 */
export default {
  /**
   * 获取当前用户进行中的习惯列表（含今日生成检查）
   * @returns {Promise}
   */
  getHabits: () => request.get('/habit/list'),

  /**
   * 获取已归档的习惯列表
   * @returns {Promise}
   */
  getArchivedHabits: () => request.get('/habit/archived'),

  /**
   * 创建习惯
   * @param {Object} data
   * @returns {Promise}
   */
  createHabit: (data = {}) => request.post('/habit/create', data),

  /**
   * 更新习惯
   * @param {Number} id
   * @param {Object} data
   * @returns {Promise}
   */
  updateHabit: (id, data = {}) => request.post('/habit/update', { ...data, id }),

  /**
   * 删除习惯（级联删除历史打卡待办）
   * @param {Number} id
   * @returns {Promise}
   */
  deleteHabit: (id) => request.delete('/habit/delete', { params: { habit_id: id } }),
}
