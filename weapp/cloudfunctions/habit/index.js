/**
 * habit 云函数：习惯 CRUD + 惰性生成打卡待办 + 连续天数/周进度 + 周期聚合(summary)
 * 约定：
 *  - 纯日期用 'YYYY-MM-DD' 字符串；时间点用 ms 数字
 *  - 「今天」由客户端本地时区计算后通过 today_str / today_start_ms / today_end_ms 传入
 *  - 习惯创建时由客户端传入 created_date（本地时区的创建日），interval_days 以它为锚点
 */
const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();
const _ = db.command;

const ok = (d = null) => ({ code: 0, data: d });
const fail = (m, c = 1) => ({ code: c, message: m });

const FREQS = ['daily', 'weekly_days', 'weekly_count', 'interval_days'];

// ---- 日期工具（纯日期字符串，时区无关） ----
const pad = (n) => String(n).padStart(2, '0');
function parseDate(str) { const p = str.split('-').map(Number); return { y: p[0], m: p[1], d: p[2] }; }
function toStr(y, m, d) { return y + '-' + pad(m) + '-' + pad(d); }
function isoWeekday(str) { const { y, m, d } = parseDate(str); const wd = new Date(y, m - 1, d).getDay(); return wd === 0 ? 7 : wd; }
function addDays(str, n) { const { y, m, d } = parseDate(str); const t = new Date(y, m - 1, d + n); return toStr(t.getFullYear(), t.getMonth() + 1, t.getDate()); }
function diffDays(a, b) { const pa = parseDate(a), pb = parseDate(b); return Math.round((Date.UTC(pb.y, pb.m - 1, pb.d) - Date.UTC(pa.y, pa.m - 1, pa.d)) / 86400000); }
function weekRangeStr(todayStr) { const wd = isoWeekday(todayStr); const start = addDays(todayStr, -(wd - 1)); return { start, end: addDays(start, 6) }; }
function toStrFromMs(ms) { const d = new Date(ms); return toStr(d.getFullYear(), d.getMonth() + 1, d.getDate()); }

// 纯计算：习惯在 dayStr 是否「应该做」（daily/weekly_days/interval_days）
function isScheduledDay(habit, dayStr) {
  const cfg = habit.frequency_config || {};
  const t = habit.frequency_type;
  if (t === 'daily') return true;
  if (t === 'weekly_days') return (cfg.days || []).indexOf(isoWeekday(dayStr)) >= 0;
  if (t === 'interval_days') {
    const interval = cfg.interval || 1;
    const anchor = habit.created_date || toStrFromMs(habit.created_at);
    const diff = diffDays(anchor, dayStr);
    return diff >= 0 && diff % interval === 0;
  }
  return false;
}

function validateFreq(ft, cfg) {
  if (!FREQS.includes(ft)) return '非法频率类型';
  if (ft === 'weekly_days') {
    const days = cfg.days;
    if (!Array.isArray(days) || !days.length || !days.every((d) => Number.isInteger(d) && d >= 1 && d <= 7)) return 'weekly_days 需要 days 为 1-7 的整数数组';
  } else if (ft === 'weekly_count') {
    if (!Number.isInteger(cfg.count) || cfg.count < 1) return 'weekly_count 需要 count 为正整数';
  } else if (ft === 'interval_days') {
    if (!Number.isInteger(cfg.interval) || cfg.interval < 1) return 'interval_days 需要 interval 为正整数';
  }
  return null;
}

async function countCompleted(openid, habitId, startStr, endStr) {
  const res = await db.collection('todos').where({
    _openid: openid, habit_id: habitId, is_completed: true,
    generated_date: _.gte(startStr).and(_.lte(endStr)),
  }).count();
  return res.total;
}

// 是否应生成（weekly_count 需查本周完成数）
async function shouldGenerateToday(openid, habit, dayStr) {
  if (habit.frequency_type === 'weekly_count') {
    const count = (habit.frequency_config || {}).count || 0;
    const { start, end } = weekRangeStr(dayStr);
    return (await countCompleted(openid, habit._id, start, end)) < count;
  }
  return isScheduledDay(habit, dayStr);
}

async function calcStreak(openid, habit, todayStr) {
  const todos = await db.collection('todos').where({ _openid: openid, habit_id: habit._id }).field({ generated_date: true, is_completed: true }).limit(1000).get();
  const map = {};
  for (const t of todos.data) map[t.generated_date] = t.is_completed;
  let streak = 0;
  let cursor = addDays(todayStr, -1);
  for (let i = 0; i < 3650; i++) {
    if (!isScheduledDay(habit, cursor)) { cursor = addDays(cursor, -1); continue; }
    if (map[cursor]) { streak++; cursor = addDays(cursor, -1); } else break;
  }
  return streak;
}

async function ensureTodayGenerated(openid, todayStr, todayStartMs, todayEndMs) {
  const habits = await db.collection('habits').where({ _openid: openid, is_paused: false, is_archived: false }).get();
  // last_generated_date 命中今天的习惯当天已经处理过（生成/清理都已落地），直接跳过，
  // 避免同一天内每次进页面都对所有习惯重新做一遍判断+查询
  const pending = habits.data.filter((h) => h.last_generated_date !== todayStr);
  await Promise.all(pending.map(async (habit) => {
    const should = await shouldGenerateToday(openid, habit, todayStr);
    if (habit.frequency_type === 'weekly_count' && !should) {
      const { start, end } = weekRangeStr(todayStr);
      await db.collection('todos').where({
        _openid: openid, habit_id: habit._id, is_completed: false,
        generated_date: _.gte(start).and(_.lte(end)),
      }).remove();
    }
    if (should) {
      const exists = await db.collection('todos').where({ _openid: openid, habit_id: habit._id, generated_date: todayStr }).count();
      if (!exists.total) {
        const data = {
          _openid: openid,
          title: habit.name,
          quadrant_type: habit.default_quadrant || 'important_not_urgent',
          habit_id: habit._id,
          generated_date: todayStr,
          is_completed: false,
          created_at: Date.now(),
          updated_at: Date.now(),
        };
        if (todayEndMs) data.due_date = Number(todayEndMs);
        if (habit.reminder_time && todayStartMs != null) {
          const p = String(habit.reminder_time).split(':').map(Number);
          data.reminder_at = Number(todayStartMs) + (p[0] * 60 + p[1]) * 60000;
        }
        await db.collection('todos').add({ data });
      }
    }
    await db.collection('habits').doc(habit._id).update({ data: { last_generated_date: todayStr } });
  }));
}

async function list(openid, event) {
  const todayStr = event.today_str;
  const todayStartMs = Number(event.today_start_ms);
  const todayEndMs = Number(event.today_end_ms);
  await ensureTodayGenerated(openid, todayStr, todayStartMs, todayEndMs);

  const habits = await db.collection('habits').where({ _openid: openid, is_archived: false }).orderBy('created_at', 'desc').get();
  // streak 只统计到「昨天」为止（今天的打卡不影响它），所以同一个 todayStr 内它是稳定值，
  // 缓存在 habit 文档上（streak/streak_date），当天只需重算一次，而不是每次进页面都全量拉历史打卡重算
  const toCache = [];
  const out = await Promise.all(habits.data.map(async (habit) => {
    const h = Object.assign({}, habit);
    if (habit.is_paused) {
      h.today_todo_id = null;
      h.today_completed = null;
    } else {
      const todo = await db.collection('todos').where({ _openid: openid, habit_id: habit._id, generated_date: todayStr }).get();
      h.today_todo_id = todo.data.length ? todo.data[0]._id : null;
      h.today_completed = todo.data.length ? todo.data[0].is_completed : false;
    }
    if (habit.frequency_type === 'weekly_count') {
      h.streak = null;
      const count = (habit.frequency_config || {}).count || 0;
      const { start, end } = weekRangeStr(todayStr);
      h.week_progress = (await countCompleted(openid, habit._id, start, end)) + '/' + count;
    } else {
      if (habit.streak_date === todayStr && habit.streak != null) {
        h.streak = habit.streak;
      } else {
        h.streak = await calcStreak(openid, habit, todayStr);
        h.streak_date = todayStr;
        toCache.push({ id: habit._id, streak: h.streak });
      }
      h.week_progress = null;
    }
    return h;
  }));

  if (toCache.length) {
    await Promise.all(toCache.map((c) => db.collection('habits').doc(c.id).update({ data: { streak: c.streak, streak_date: todayStr } })));
  }
  return ok({ list: out });
}

async function archived(openid) {
  const res = await db.collection('habits').where({ _openid: openid, is_archived: true }).orderBy('updated_at', 'desc').get();
  return ok({ list: res.data });
}

/**
 * bootstrap：习惯页初始化数据（在用 + 已归档）
 * 合并原先两次 callFunction（list / archived）为一次，避免并发抢占云函数实例。
 * 复用 list/archived 的实现，惰性生成打卡待办等逻辑保持唯一实现处。
 */
async function bootstrap(openid, event) {
  const [l, a] = await Promise.all([list(openid, event), archived(openid)]);
  if (l.code !== 0) return l;
  if (a.code !== 0) return a;
  return ok({ list: l.data.list, archived: a.data.list });
}

async function create(openid, event) {
  const name = String(event.name || '').trim();
  if (!name) return fail('习惯名称不能为空');
  const ft = event.frequency_type;
  const cfg = event.frequency_config || {};
  const verr = validateFreq(ft, cfg);
  if (verr) return fail(verr);
  if (event.goal_id) {
    const c = await db.collection('goals').where({ _id: event.goal_id, _openid: openid }).count();
    if (!c.total) return fail('计划不存在', 404);
  }
  const now = Date.now();
  const data = {
    _openid: openid,
    name,
    frequency_type: ft,
    default_quadrant: event.default_quadrant || 'important_not_urgent',
    is_paused: false,
    is_archived: false,
    created_at: now,
    updated_at: now,
    created_date: event.created_date || toStrFromMs(now),
  };
  if (Object.keys(cfg).length) data.frequency_config = cfg;
  if (event.icon) data.icon = event.icon;
  if (event.color_hex) data.color_hex = event.color_hex;
  if (event.goal_desc) data.goal_desc = String(event.goal_desc);
  if (event.reminder_time) data.reminder_time = String(event.reminder_time);
  if (event.goal_id) data.goal_id = event.goal_id;
  const res = await db.collection('habits').add({ data });
  return ok(Object.assign({ _id: res._id }, data));
}

async function update(openid, event) {
  const id = event.id;
  const h = await db.collection('habits').where({ _id: id, _openid: openid }).get();
  if (!h.data.length) return fail('习惯不存在', 404);
  const habit = h.data[0];

  let ft = habit.frequency_type, cfg = habit.frequency_config || {};
  if (event.frequency_type !== undefined) ft = event.frequency_type;
  if (event.frequency_config !== undefined) cfg = event.frequency_config || {};
  const verr = validateFreq(ft, cfg);
  if (verr) return fail(verr);

  if (event.goal_id) {
    const c = await db.collection('goals').where({ _id: event.goal_id, _openid: openid }).count();
    if (!c.total) return fail('计划不存在', 404);
  }

  const data = { updated_at: Date.now() };
  if (event.name !== undefined) data.name = String(event.name).trim();
  if (event.frequency_type !== undefined) data.frequency_type = ft;
  if (event.frequency_config !== undefined) data.frequency_config = cfg;
  if (event.default_quadrant !== undefined) data.default_quadrant = event.default_quadrant;
  if (event.icon !== undefined) data.icon = event.icon || _.remove();
  if (event.color_hex !== undefined) data.color_hex = event.color_hex || _.remove();
  if (event.goal_desc !== undefined) data.goal_desc = event.goal_desc ? String(event.goal_desc) : _.remove();
  if (event.reminder_time !== undefined) data.reminder_time = event.reminder_time ? String(event.reminder_time) : _.remove();
  if (event.goal_id !== undefined) data.goal_id = event.goal_id ? event.goal_id : _.remove();
  if (event.is_paused !== undefined) data.is_paused = event.is_paused === true || event.is_paused === 'true';
  if (event.is_archived !== undefined) data.is_archived = event.is_archived === true || event.is_archived === 'true';
  // 频率规则变了，之前缓存的 streak 是按旧规则算的，必须失效，否则当天会显示错误的连续天数
  if (event.frequency_type !== undefined || event.frequency_config !== undefined) {
    data.streak = _.remove();
    data.streak_date = _.remove();
  }
  await db.collection('habits').doc(id).update({ data });
  return ok(Object.assign({}, habit, data, { _id: id }));
}

async function remove(openid, event) {
  const id = event.id;
  const h = await db.collection('habits').where({ _id: id, _openid: openid }).get();
  if (!h.data.length) return fail('习惯不存在', 404);
  await db.collection('todos').where({ _openid: openid, habit_id: id }).remove();
  await db.collection('habits').doc(id).remove();
  return ok({ _id: id });
}

// 周期聚合（供 review 云函数调用）：各习惯在 [start,end] 的 expected/completed/streak
async function summary(openid, event) {
  const { start_str, end_str, today_str } = event;
  const habits = await db.collection('habits').where({ _openid: openid, is_archived: false, is_paused: false }).get();
  const out = await Promise.all(habits.data.map(async (habit) => {
    if (habit.frequency_type === 'weekly_count') {
      const count = (habit.frequency_config || {}).count || 0;
      const totalDays = diffDays(start_str, end_str) + 1;
      const expected = Math.floor(totalDays / 7) * count;
      const completed = await countCompleted(openid, habit._id, start_str, end_str);
      return { habit_id: habit._id, name: habit.name, frequency_type: habit.frequency_type, completed, expected, streak: null };
    }
    const rangeStart = (habit.created_date && habit.created_date > start_str) ? habit.created_date : start_str;
    const rangeEnd = (today_str && today_str < end_str) ? today_str : end_str;
    const todos = await db.collection('todos').where({
      _openid: openid, habit_id: habit._id,
      generated_date: _.gte(start_str).and(_.lte(end_str)),
    }).get();
    const map = {};
    for (const t of todos.data) map[t.generated_date] = t.is_completed;
    let expected = 0, completed = 0;
    let cursor = rangeStart;
    while (cursor <= rangeEnd) {
      if (isScheduledDay(habit, cursor)) { expected++; if (map[cursor]) completed++; }
      cursor = addDays(cursor, 1);
    }
    // 跟 list() 共用同一份 streak 缓存：today_str 命中缓存日期就直接复用，避免再拉一次历史打卡
    const streak = (habit.streak_date === today_str && habit.streak != null)
      ? habit.streak
      : await calcStreak(openid, habit, today_str);
    return { habit_id: habit._id, name: habit.name, frequency_type: habit.frequency_type, completed, expected, streak };
  }));
  return ok({ list: out });
}

exports.main = async (event, context) => {
  const { OPENID } = cloud.getWXContext();
  if (!OPENID) return fail('无法获取用户身份', 401);
  const action = event && event.action;
  try {
    switch (action) {
      case 'list': return await list(OPENID, event);
      case 'bootstrap': return await bootstrap(OPENID, event);
      case 'archived': return await archived(OPENID);
      case 'create': return await create(OPENID, event);
      case 'update': return await update(OPENID, event);
      case 'remove': return await remove(OPENID, event);
      case 'summary': return await summary(OPENID, event);
      default: return fail('未知操作: ' + action);
    }
  } catch (e) {
    console.error('[habit]', action, e);
    return fail((e && e.message) || '服务端错误', 500);
  }
};
