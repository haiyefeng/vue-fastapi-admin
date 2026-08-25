const { call } = require('./cloud');

const list = (params = {}) => call('todo', Object.assign({ action: 'list' }, params));
const create = (data = {}) => call('todo', Object.assign({ action: 'create' }, data));
const get = (todoId) => call('todo', { action: 'get', todo_id: todoId });
const update = (id, data = {}) => call('todo', Object.assign({ action: 'update', id }, data));
const remove = (id) => call('todo', { action: 'remove', id });

const subtaskList = (todoItemId) => call('todo', { action: 'subtaskList', todo_item_id: todoItemId });
const subtaskCreate = (data = {}) => call('todo', Object.assign({ action: 'subtaskCreate' }, data));
const subtaskUpdate = (id, data = {}) => call('todo', Object.assign({ action: 'subtaskUpdate', id }, data));
const subtaskRemove = (id) => call('todo', { action: 'subtaskRemove', id });

const timeblockList = (params = {}) => call('todo', Object.assign({ action: 'timeblockList' }, params));
const timeblockCreate = (data = {}) => call('todo', Object.assign({ action: 'timeblockCreate' }, data));
const timeblockRemove = (id) => call('todo', { action: 'timeblockRemove', id });

const statisticsDaily = (params = {}) => call('todo', Object.assign({ action: 'statisticsDaily' }, params));
const statisticsQuadrant = () => call('todo', { action: 'statisticsQuadrant' });
const statsBootstrap = (params = {}) => call('todo', Object.assign({ action: 'statsBootstrap' }, params));

module.exports = {
  list, create, get, update, remove,
  subtaskList, subtaskCreate, subtaskUpdate, subtaskRemove,
  timeblockList, timeblockCreate, timeblockRemove,
  statisticsDaily, statisticsQuadrant, statsBootstrap,
};
