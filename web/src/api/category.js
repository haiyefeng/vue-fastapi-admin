import { request } from '@/utils'

/**
 * 分类API接口（只读，分类只能在创建项目时顺带生成）
 */
export default {
  /**
   * 获取当前用户可用的分类列表
   * @returns {Promise}
   */
  getCategories: (params = {}) => request.get('/category/list', { params })
}
