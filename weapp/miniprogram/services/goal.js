const { call } = require('./cloud');
const list = () => call('goal', { action: 'list' });
const archived = () => call('goal', { action: 'archived' });
const bootstrap = () => call('goal', { action: 'bootstrap' });
const detail = (goalId) => call('goal', { action: 'detail', goal_id: goalId });
const create = (data = {}) => call('goal', Object.assign({ action: 'create' }, data));
const update = (id, data = {}) => call('goal', Object.assign({ action: 'update', id }, data));
const remove = (id) => call('goal', { action: 'remove', id });
module.exports = { list, archived, bootstrap, detail, create, update, remove };
