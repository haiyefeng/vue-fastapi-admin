const { call } = require('./cloud');
const listCategories = (params = {}) => call('project', Object.assign({ action: 'listCategories' }, params));
const list = (params = {}) => call('project', Object.assign({ action: 'list' }, params));
const bootstrap = () => call('project', { action: 'bootstrap' });
const create = (data = {}) => call('project', Object.assign({ action: 'create' }, data));
const update = (id, data = {}) => call('project', Object.assign({ action: 'update', id }, data));
const remove = (id) => call('project', { action: 'remove', id });
module.exports = { listCategories, list, bootstrap, create, update, remove };
