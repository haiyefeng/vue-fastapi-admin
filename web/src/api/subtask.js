import { request } from '@/utils'

/**
 * 子任务API接口
 */
export default {
  /**
   * 获取指定待办事项下的子任务列表
   * @param {Number} todoItemId
   * @returns {Promise}
   */
  getSubtasks: (todoItemId) => request.get('/subtask/list', { params: { todo_item_id: todoItemId } }),

  /**
   * 创建子任务
   * @param {Object} data
   * @param {Number} data.todo_item_id
   * @param {String} data.title
   * @returns {Promise}
   */
  createSubtask: (data = {}) => request.post('/subtask/create', data),

  /**
   * 更新子任务（改标题或勾选状态）
   * @param {Number} id
   * @param {Object} data
   * @returns {Promise}
   */
  updateSubtask: (id, data = {}) => request.post('/subtask/update', { ...data, id }),

  /**
   * 删除子任务
   * @param {Number} id
   * @returns {Promise}
   */
  deleteSubtask: (id) => request.delete('/subtask/delete', { params: { subtask_id: id } })
}
