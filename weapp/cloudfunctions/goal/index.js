const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();
const _ = db.command;

const ok = (d = null) => ({ code: 0, data: d });
const fail = (m, c = 1) => ({ code: c, message: m });

async function getOrCreateCategory(openid, name) {
  const n = String(name || '').trim();
  if (!n) return null;
  const existing = await db.collection('categories').where({ _openid: openid, name: n }).get();
  if (existing.data.length) return existing.data[0]._id;
  const now = Date.now();
  const add = await db.collection('categories').add({
    data: { _openid: openid, name: n, type: 'user_custom', display_order: 0, is_archived: false, created_at: now, updated_at: now },
  });
  return add._id;
}

/**
 * 给一批计划补上任务/习惯统计。
 * 原实现对每个计划各发 3 条 count 查询（N+1，且外层 for 串行），
 * 这里改为一次性拉取所有带 goal_id 的 todos/habits，在内存里聚合。
 */
async function decorateGoals(openid, goals) {
  if (!goals.length) return [];
  const ids = goals.map((g) => g._id);
  const [todos, habits] = await Promise.all([
    db.collection('todos').where({ _openid: openid, goal_id: _.in(ids) }).field({ goal_id: true, is_completed: true }).limit(1000).get(),
    db.collection('habits').where({ _openid: openid, goal_id: _.in(ids) }).field({ goal_id: true }).limit(1000).get(),
  ]);
  const stat = {};
  for (const id of ids) stat[id] = { task_total: 0, task_completed: 0, habit_count: 0 };
  for (const t of todos.data) {
    const s = stat[t.goal_id];
    if (!s) continue;
    s.task_total++;
    if (t.is_completed) s.task_completed++;
  }
  for (const h of habits.data) {
    const s = stat[h.goal_id];
    if (s) s.habit_count++;
  }
  return goals.map((g) => Object.assign({}, g, stat[g._id]));
}

async function list(openid) {
  const goals = await db.collection('goals').where({ _openid: openid, is_archived: false }).orderBy('created_at', 'desc').get();
  return ok({ list: await decorateGoals(openid, goals.data) });
}

/**
 * bootstrap：计划页初始化数据（进行中 + 已归档）
 * 合并原先两次 callFunction（list / archived）为一次，避免并发抢占云函数实例。
 */
async function bootstrap(openid) {
  const all = await db.collection('goals').where({ _openid: openid }).orderBy('created_at', 'desc').get();
  const active = all.data.filter((g) => !g.is_archived);
  const archivedGoals = all.data
    .filter((g) => g.is_archived)
    .sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0));
  return ok({ list: await decorateGoals(openid, active), archived: archivedGoals });
}

async function archived(openid) {
  const goals = await db.collection('goals').where({ _openid: openid, is_archived: true }).orderBy('updated_at', 'desc').get();
  return ok({ list: goals.data });
}

async function detail(openid, event) {
  const id = event.goal_id;
  const g = await db.collection('goals').where({ _id: id, _openid: openid }).get();
  if (!g.data.length) return fail('计划不存在', 404);
  const goal = g.data[0];
  const [tasks, habits] = await Promise.all([
    db.collection('todos').where({ _openid: openid, goal_id: id }).orderBy('created_at', 'asc').get(),
    db.collection('habits').where({ _openid: openid, goal_id: id }).orderBy('created_at', 'asc').get(),
  ]);
  goal.tasks = tasks.data.map((t) => ({ _id: t._id, title: t.title, is_completed: t.is_completed }));
  goal.habits = habits.data.map((h) => ({ _id: h._id, name: h.name, frequency_type: h.frequency_type, frequency_config: h.frequency_config }));
  return ok(goal);
}

async function create(openid, event) {
  const name = String(event.name || '').trim();
  if (!name) return fail('名称不能为空');
  let category_id = event.category_id || null;
  if (!category_id && event.category_name) category_id = await getOrCreateCategory(openid, event.category_name);
  if (category_id) {
    const c = await db.collection('categories').where({ _id: category_id, _openid: openid }).count();
    if (!c.total) return fail('分类不存在', 404);
  }
  const now = Date.now();
  const data = { _openid: openid, name, is_archived: false, created_at: now, updated_at: now };
  if (event.description) data.description = String(event.description);
  if (event.target_date) data.target_date = event.target_date; // 'YYYY-MM-DD'
  if (category_id) data.category_id = category_id;
  const res = await db.collection('goals').add({ data });
  return ok(Object.assign({ _id: res._id }, data));
}

async function update(openid, event) {
  const id = event.id;
  const g = await db.collection('goals').where({ _id: id, _openid: openid }).get();
  if (!g.data.length) return fail('计划不存在', 404);
  const data = { updated_at: Date.now() };
  if (event.name !== undefined) data.name = String(event.name).trim();
  if (event.description !== undefined) data.description = event.description ? String(event.description) : _.remove();
  if (event.target_date !== undefined) data.target_date = event.target_date ? event.target_date : _.remove();
  if (event.is_archived !== undefined) data.is_archived = event.is_archived === true || event.is_archived === 'true';
  if (event.category_id !== undefined) data.category_id = event.category_id ? event.category_id : _.remove();
  await db.collection('goals').doc(id).update({ data });
  return ok(Object.assign({}, g.data[0], data, { _id: id }));
}

async function remove(openid, event) {
  const id = event.id;
  const g = await db.collection('goals').where({ _id: id, _openid: openid }).get();
  if (!g.data.length) return fail('计划不存在', 404);
  await Promise.all([
    db.collection('todos').where({ _openid: openid, goal_id: id }).update({ data: { goal_id: _.remove() } }),
    db.collection('habits').where({ _openid: openid, goal_id: id }).update({ data: { goal_id: _.remove() } }),
  ]);
  await db.collection('goals').doc(id).remove();
  return ok({ _id: id });
}

exports.main = async (event, context) => {
  const { OPENID } = cloud.getWXContext();
  if (!OPENID) return fail('无法获取用户身份', 401);
  const action = event && event.action;
  try {
    switch (action) {
      case 'list': return await list(OPENID);
      case 'bootstrap': return await bootstrap(OPENID);
      case 'archived': return await archived(OPENID);
      case 'detail': return await detail(OPENID, event);
      case 'create': return await create(OPENID, event);
      case 'update': return await update(OPENID, event);
      case 'remove': return await remove(OPENID, event);
      default: return fail('未知操作: ' + action);
    }
  } catch (e) {
    console.error('[goal]', action, e);
    return fail((e && e.message) || '服务端错误', 500);
  }
};
