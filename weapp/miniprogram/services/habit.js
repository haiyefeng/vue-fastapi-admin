const { call } = require('./cloud');
const { todayStr, startOfDay, endOfDay, nowMs } = require('../utils/date');

function todayParams() {
  const now = nowMs();
  return { today_str: todayStr(), today_start_ms: startOfDay(now), today_end_ms: endOfDay(now) };
}
const list = () => call('habit', Object.assign({ action: 'list' }, todayParams()));
const archived = () => call('habit', { action: 'archived' });
const bootstrap = () => call('habit', Object.assign({ action: 'bootstrap' }, todayParams()));
const create = (data = {}) => call('habit', Object.assign({ action: 'create' }, data));
const update = (id, data = {}) => call('habit', Object.assign({ action: 'update', id }, data));
const remove = (id) => call('habit', { action: 'remove', id });
const summary = (params = {}) => call('habit', Object.assign({ action: 'summary' }, params));
module.exports = { list, archived, bootstrap, create, update, remove, summary };
