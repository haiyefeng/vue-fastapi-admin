import { request } from '@/utils'

/**
 * 项目/清单API接口
 */
export default {
  /**
   * 获取当前用户的项目/清单列表
   * @returns {Promise}
   */
  getProjects: (params = {}) => request.get('/project/list', { params }),

  /**
   * 创建项目/清单
   * @param {Object} data
   * @param {String} data.name - 名称
   * @param {String} data.type - 类型，project 或 list
   * @param {Number} [data.category_id] - 已有分类ID
   * @param {String} [data.category_name] - 新分类名称，与 category_id 二选一
   * @param {String} [data.color_hex] - 颜色代码
   * @returns {Promise}
   */
  createProject: (data = {}) => request.post('/project/create', data),

  /**
   * 更新项目/清单
   * @param {Number} id
   * @param {Object} data
   * @returns {Promise}
   */
  updateProject: (id, data = {}) => request.post('/project/update', { ...data, id }),

  /**
   * 删除项目/清单（关联任务会保留，project_id 置空退回收件箱）
   * @param {Number} id
   * @returns {Promise}
   */
  deleteProject: (id) => request.delete('/project/delete', { params: { project_id: id } })
}
