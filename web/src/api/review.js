import { request } from '@/utils'

/**
 * 回顾总结API接口
 */
export default {
  /**
   * 获取指定周期的数据回顾聚合（任务完成情况/习惯打卡情况/计划进展）
   * @param {String} periodType week/month/quarter/year
   * @param {String} anchorDate 周期内任意一天，格式 YYYY-MM-DD
   * @returns {Promise}
   */
  getReviewDataSummary: (periodType, anchorDate) =>
    request.get('/review/data-summary', {
      params: { period_type: periodType, anchor_date: anchorDate },
    }),

  /**
   * 获取指定周期的回顾详情；不存在时 data 为 null（不是错误，调用方按 res.data 是否为 null 分支即可）
   * @param {String} periodType
   * @param {String} anchorDate
   * @returns {Promise}
   */
  getReviewDetail: (periodType, anchorDate) =>
    request.get('/review/detail', {
      params: { period_type: periodType, anchor_date: anchorDate },
    }),

  /**
   * 保存回顾（草稿或完成），同周期已存在则覆盖更新
   * @param {Object} data { period_type, anchor_date, answers, status }
   * @returns {Promise}
   */
  saveReview: (data = {}) => request.post('/review/save', data),

  /**
   * 获取历史回顾列表
   * @param {String} periodType 可选，按周期类型筛选，不传返回全部
   * @returns {Promise}
   */
  getReviewList: (periodType) =>
    request.get('/review/list', {
      params: periodType ? { period_type: periodType } : {},
    }),
}
