/**
 * review 云函数：回顾 CRUD + 数据聚合（任务完成/习惯打卡/计划进展）
 * 周期边界由客户端计算后传入（start_str/end_str/start_ms/end_ms/today_str）
 * 习惯聚合通过 cloud.callFunction 调用 habit 云函数（逻辑唯一实现处）
 */
const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();
const _ = db.command;

const ok = (d = null) => ({ code: 0, data: d });
const fail = (m, c = 1) => ({ code: c, message: m });

async function taskSummary(openid, startMs, endMs) {
  const common = { _openid: openid, habit_id: _.exists(false) };
  const dueCond = _.gte(Number(startMs)).and(_.lte(Number(endMs)));
  const inPeriod = Object.assign({}, common, { due_date: dueCond });
  const [total, completed, uiTotal, uiCompleted] = await Promise.all([
    db.collection('todos').where(inPeriod).count(),
    db.collection('todos').where(Object.assign({}, inPeriod, { is_completed: true })).count(),
    db.collection('todos').where(Object.assign({}, inPeriod, { quadrant_type: 'urgent_important' })).count(),
    db.collection('todos').where(Object.assign({}, inPeriod, { quadrant_type: 'urgent_important', is_completed: true })).count(),
  ]);
  const by_category = await byCategorySummary(openid, inPeriod);
  return {
    total: total.total, completed: completed.total,
    urgent_important_total: uiTotal.total, urgent_important_completed: uiCompleted.total,
    by_category: by_category,
  };
}

async function byCategorySummary(openid, inPeriod) {
  const [todos, projects] = await Promise.all([
    db.collection('todos').where(inPeriod).field({ project_id: true, is_completed: true }).limit(1000).get(),
    db.collection('projects').where({ _openid: openid }).get(),
  ]);
  const projCat = {};
  for (const p of projects.data) projCat[p._id] = p.category_id || null;
  const catIds = Object.values(projCat).filter(Boolean);
  let catNames = {};
  if (catIds.length) {
    const cats = await db.collection('categories').where({ _openid: openid, _id: _.in(catIds) }).get();
    for (const c of cats.data) catNames[c._id] = c.name;
  }
  const agg = {};
  for (const t of todos.data) {
    if (!t.project_id) continue;
    const catId = projCat[t.project_id];
    if (!catId) continue;
    if (!agg[catId]) agg[catId] = { category_id: catId, category_name: catNames[catId] || '', total: 0, completed: 0 };
    agg[catId].total++;
    if (t.is_completed) agg[catId].completed++;
  }
  return Object.values(agg);
}

/**
 * 各计划在周期内的进展。
 * 原实现对每个计划各发 2 条 count 查询（N+1），这里改为一次性拉取所有
 * 带 goal_id 的 todos，在内存里聚合总数与「周期内新完成数」。
 */
async function goalSummary(openid, startMs, endMs) {
  const goals = await db.collection('goals').where({ _openid: openid, is_archived: false }).get();
  if (!goals.data.length) return [];
  const ids = goals.data.map((g) => g._id);
  const todos = await db.collection('todos')
    .where({ _openid: openid, goal_id: _.in(ids) })
    .field({ goal_id: true, is_completed: true, completed_at: true })
    .limit(1000)
    .get();

  const s = Number(startMs), e = Number(endMs);
  const stat = {};
  for (const id of ids) stat[id] = { total: 0, newly: 0 };
  for (const t of todos.data) {
    const st = stat[t.goal_id];
    if (!st) continue;
    st.total++;
    if (t.is_completed && t.completed_at >= s && t.completed_at <= e) st.newly++;
  }

  return goals.data.map((g) => {
    const st = stat[g._id];
    return {
      goal_id: g._id, name: g.name,
      newly_completed: st.newly,
      total_linked_tasks: st.total,
      progress_percent: st.total ? Math.round(st.newly / st.total * 1000) / 10 : null,
    };
  });
}

async function dataSummary(openid, event) {
  const { start_str, end_str, start_ms, end_ms } = event;
  const [task, goals] = await Promise.all([
    taskSummary(openid, start_ms, end_ms),
    goalSummary(openid, start_ms, end_ms),
  ]);
  return ok({ period_start: start_str, period_end: end_str, task_completion: task, goals });
}

async function detail(openid, event) {
  const res = await db.collection('reviews').where({ _openid: openid, period_type: event.period_type, period_start: event.period_start }).get();
  return ok(res.data.length ? res.data[0] : null);
}

/**
 * bootstrap：回顾页初始化数据（周期聚合 + 当期回顾详情）
 * 合并原先两次 callFunction（dataSummary / detail）为一次，避免并发抢占云函数实例。
 * 习惯聚合仍由客户端并行调用 habit 云函数（不同函数不争抢实例）。
 */
async function bootstrap(openid, event) {
  const [summary, d] = await Promise.all([
    dataSummary(openid, event),
    detail(openid, Object.assign({}, event, { period_start: event.period_start || event.start_str })),
  ]);
  if (summary.code !== 0) return summary;
  if (d.code !== 0) return d;
  return ok({ summary: summary.data, detail: d.data });
}

async function save(openid, event) {
  const { period_type, period_start, period_end, answers, status } = event;
  if (!period_type || !period_start) return fail('缺少周期参数');
  const existing = await db.collection('reviews').where({ _openid: openid, period_type, period_start }).get();
  const now = Date.now();
  if (existing.data.length) {
    const id = existing.data[0]._id;
    const data = { period_end: period_end || existing.data[0].period_end, answers: answers || {}, status: status || 'draft', updated_at: now };
    await db.collection('reviews').doc(id).update({ data });
    return ok(Object.assign({}, existing.data[0], data, { _id: id }));
  }
  const data = { _openid: openid, period_type, period_start, period_end: period_end || period_start, answers: answers || {}, status: status || 'draft', created_at: now, updated_at: now };
  const res = await db.collection('reviews').add({ data });
  return ok(Object.assign({ _id: res._id }, data));
}

async function list(openid, event) {
  const where = { _openid: openid };
  if (event.period_type) where.period_type = event.period_type;
  const res = await db.collection('reviews').where(where).orderBy('period_start', 'desc').get();
  return ok({ list: res.data });
}

exports.main = async (event, context) => {
  const { OPENID } = cloud.getWXContext();
  if (!OPENID) return fail('无法获取用户身份', 401);
  const action = event && event.action;
  try {
    switch (action) {
      case 'dataSummary': return await dataSummary(OPENID, event);
      case 'bootstrap': return await bootstrap(OPENID, event);
      case 'detail': return await detail(OPENID, event);
      case 'save': return await save(OPENID, event);
      case 'list': return await list(OPENID, event);
      default: return fail('未知操作: ' + action);
    }
  } catch (e) {
    console.error('[review]', action, e);
    return fail((e && e.message) || '服务端错误', 500);
  }
};
