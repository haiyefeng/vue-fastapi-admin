const { call } = require('./cloud');
const { todayStr, startOfDay, endOfDay, nowMs } = require('../utils/date');

const today = () => {
  const now = nowMs();
  return call('dashboard', { action: 'today', today_str: todayStr(), today_start_ms: startOfDay(now), today_end_ms: endOfDay(now) });
};
module.exports = { today };
