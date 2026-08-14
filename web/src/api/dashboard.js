import { request } from '@/utils'

/**
 * 今日概览API接口
 */
export default {
  /**
   * 获取今日概览（今日日程/今日待办/今日习惯）
   * @returns {Promise}
   */
  getTodayOverview: () => request.get('/dashboard/today'),
}
