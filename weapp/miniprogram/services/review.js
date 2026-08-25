const { call } = require('./cloud');
const { todayStr, calcPeriodRange } = require('../utils/date');

const dataSummary = (periodType, anchorDate) => {
  const r = calcPeriodRange(periodType, anchorDate);
  return call('review', {
    action: 'dataSummary', period_type: periodType, anchor_date: anchorDate,
    start_str: r.startStr, end_str: r.endStr, start_ms: r.start, end_ms: r.end, today_str: todayStr(),
  });
};
const bootstrap = (periodType, anchorDate) => {
  const r = calcPeriodRange(periodType, anchorDate);
  return call('review', {
    action: 'bootstrap', period_type: periodType, anchor_date: anchorDate,
    start_str: r.startStr, end_str: r.endStr, start_ms: r.start, end_ms: r.end, today_str: todayStr(),
    period_start: r.startStr,
  });
};
const detail = (periodType, periodStart) => call('review', { action: 'detail', period_type: periodType, period_start: periodStart });
const save = (data = {}) => call('review', Object.assign({ action: 'save' }, data));
const list = (periodType) => call('review', { action: 'list', period_type: periodType || undefined });
module.exports = { dataSummary, bootstrap, detail, save, list };
