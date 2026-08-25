/**
 * 日期工具
 * 约定：
 *  - 纯日期：'YYYY-MM-DD' 字符串（无时区歧义）
 *  - 时间点：本地毫秒时间戳（Date.now() 口径）
 * 所有「今天/本周/周期」边界都在客户端本地时区计算，云函数只做数值范围过滤，
 * 以此避免服务端时区与用户设备时区不一致导致的「日期错一天」问题。
 */
const pad = (n) => String(n).padStart(2, '0');

// 本地 ms -> 'YYYY-MM-DD'
function toDateStr(ms) {
  const d = new Date(ms);
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
}

// 'YYYY-MM-DD' -> 当天 00:00 本地 ms（拆开年月日，避免 new Date(str) 按 UTC 解析）
function parseDateStr(str) {
  if (!str) return null;
  const p = str.split('-').map(Number);
  if (p.length !== 3 || p.some((n) => !Number.isFinite(n))) return null;
  return new Date(p[0], p[1] - 1, p[2]).getTime();
}

function todayStr() { return toDateStr(Date.now()); }
function nowMs() { return Date.now(); }

// 当天 00:00 本地 ms
function startOfDay(ms) {
  const d = new Date(ms);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}
// 当天 23:59:59.999 本地 ms
function endOfDay(ms) { return startOfDay(ms) + 24 * 60 * 60 * 1000 - 1; }

// ISO 周几：周一=1 ... 周日=7
function isoWeekday(ms) {
  const wd = new Date(ms).getDay(); // 0=周日
  return wd === 0 ? 7 : wd;
}

// 本周范围（ISO 周一为起点）
function weekRange(anchorMs) {
  const a = startOfDay(anchorMs);
  const start = a - (isoWeekday(a) - 1) * 24 * 60 * 60 * 1000;
  const end = start + 7 * 24 * 60 * 60 * 1000 - 1;
  return { start, end, startStr: toDateStr(start), endStr: toDateStr(end) };
}

// 周期边界（周/月/季/年），等价 review.calc_period_range
function calcPeriodRange(periodType, anchorStr) {
  const a = new Date(parseDateStr(anchorStr));
  const y = a.getFullYear(), m = a.getMonth();
  let start, end;
  if (periodType === 'week') {
    const r = weekRange(a.getTime());
    start = r.start; end = r.end;
  } else if (periodType === 'month') {
    start = new Date(y, m, 1).getTime();
    end = endOfDay(new Date(y, m + 1, 0).getTime());
  } else if (periodType === 'quarter') {
    const qm = Math.floor(m / 3) * 3;
    start = new Date(y, qm, 1).getTime();
    end = endOfDay(new Date(y, qm + 3, 0).getTime());
  } else { // year
    start = new Date(y, 0, 1).getTime();
    end = endOfDay(new Date(y, 11, 31).getTime());
  }
  return { start, end, startStr: toDateStr(start), endStr: toDateStr(end) };
}

// 'HH:mm'
function formatTime(ms) {
  const d = new Date(ms);
  return pad(d.getHours()) + ':' + pad(d.getMinutes());
}

// 'M月D日 HH:mm'
function formatDateTime(ms) {
  const d = new Date(ms);
  return (d.getMonth() + 1) + '月' + d.getDate() + '日 ' + formatTime(ms);
}

// 相对标签：今天/明天/昨天/已过期
function relativeDayLabel(ms) {
  const today = startOfDay(Date.now());
  const day = startOfDay(ms);
  const diff = Math.round((day - today) / 86400000);
  if (diff === 0) return '今天';
  if (diff === 1) return '明天';
  if (diff === -1) return '昨天';
  if (diff < -1) return '已过期';
  return toDateStr(ms);
}

module.exports = {
  pad, toDateStr, parseDateStr, todayStr, nowMs, startOfDay, endOfDay,
  isoWeekday, weekRange, calcPeriodRange, formatTime, formatDateTime, relativeDayLabel,
};
