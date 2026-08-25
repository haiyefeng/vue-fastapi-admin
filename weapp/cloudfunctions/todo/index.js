/**
 * todo 云函数：待办事项 + 子任务 + 时间块 CRUD + 统计
 * 约定：
 *  - 纯日期字段存 'YYYY-MM-DD' 字符串；时间点字段存毫秒时间戳（number）
 *  - 云函数以管理员身份访问数据库，需手动按 _openid 过滤（单用户隔离）
 *  - 可空关联字段（project_id/goal_id/habit_id/due_date 等）为空时不写入（而非存 null），
 *    便于用 _.exists(false) 查询；清空时用 _.remove() 删除字段
 *  - 「今天/本周」等日期边界由客户端在本地时区计算后传入 *_ms 参数，云函数只做数值/字符串范围过滤
 */
const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();
const _ = db.command;
const $ = db.command.aggregate;

const QUADRANTS = ['urgent_important', 'urgent_not_important', 'important_not_urgent', 'not_urgent_not_important'];

const ok = (data = null) => ({ code: 0, data });
const fail = (message, code = 1) => ({ code, message });

function pageArgs(event) {
  const page = Math.max(1, parseInt(event.page, 10) || 1);
  const pageSize = Math.min(200, Math.max(1, parseInt(event.pageSize, 10) || 20));
  return { page, pageSize, skip: (page - 1) * pageSize, limit: pageSize };
}

function toMs(v) {
  if (v === undefined || v === null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function rangeCond(start, end) {
  const s = toMs(start), e = toMs(end);
  if (s !== null && e !== null) return _.gte(s).and(_.lte(e));
  if (s !== null) return _.gte(s);
  if (e !== null) return _.lte(e);
  return null;
}

function dayOf(ms) {
  const d = new Date(ms);
  const pad = (n) => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
}

async function list(openid, event) {
  const { page, pageSize, skip, limit } = pageArgs(event);
  const where = { _openid: openid };

  if (event.quadrant_type) {
    const qs = String(event.quadrant_type).split(',').map((s) => s.trim()).filter(Boolean);
    if (qs.length) where.quadrant_type = _.in(qs);
  }
  if (event.is_completed === true || event.is_completed === 'true') where.is_completed = true;
  else if (event.is_completed === false || event.is_completed === 'false') where.is_completed = false;

  if (event.project_id) where.project_id = event.project_id;
  else if (event.inbox_only) where.project_id = _.exists(false);
  if (event.habit_only) where.habit_id = _.exists(true);

  if (event.unscheduled_only) {
    where.is_completed = false;
    // 已有任意时间块的任务里 todo_id 去重后排除，供日历页「未排程任务」列表用
    const blocks = await db.collection('time_blocks').where({ _openid: openid }).field({ todo_id: true }).limit(1000).get();
    const scheduledIds = Array.from(new Set(blocks.data.map((b) => b.todo_id)));
    if (scheduledIds.length) where._id = _.nin(scheduledIds);
  }

  const due = rangeCond(event.due_start, event.due_end);
  if (due) where.due_date = due;
  const completed = rangeCond(event.completed_start, event.completed_end);
  if (completed) where.completed_at = completed;

  const SORTABLE = ['due_date', 'quadrant_type', 'created_at', 'completed_at'];
  const sortBy = SORTABLE.includes(event.sort_by) ? event.sort_by : 'created_at';
  // 时间点类字段默认倒序（最近的在前），due_date/quadrant_type 默认正序
  const defaultDir = (sortBy === 'created_at' || sortBy === 'completed_at') ? 'desc' : 'asc';
  const dir = event.sort_order === 'desc' ? 'desc' : (event.sort_order === 'asc' ? 'asc' : defaultDir);

  const coll = db.collection('todos').where(where);
  const countRes = await coll.count();
  const res = await coll.orderBy(sortBy, dir).skip(skip).limit(limit).get();
  return ok({ list: res.data, total: countRes.total, page, pageSize });
}

async function create(openid, event) {
  const title = String(event.title || '').trim();
  if (!title) return fail('标题不能为空');
  if (!QUADRANTS.includes(event.quadrant_type)) return fail('请选择象限');

  if (event.project_id) {
    const c = await db.collection('projects').where({ _id: event.project_id, _openid: openid }).count();
    if (!c.total) return fail('项目不存在', 404);
  }
  if (event.goal_id) {
    const c = await db.collection('goals').where({ _id: event.goal_id, _openid: openid }).count();
    if (!c.total) return fail('计划不存在', 404);
  }

  const blocks = Array.isArray(event.time_blocks) ? event.time_blocks : [];
  for (const b of blocks) {
    const s = toMs(b.start_time), e = toMs(b.end_time);
    if (s === null || e === null || e <= s) return fail('时间块结束时间必须晚于开始时间');
    if (dayOf(s) !== dayOf(e)) return fail('时间块不能跨天');
  }

  const now = Date.now();
  const data = {
    _openid: openid,
    title,
    quadrant_type: event.quadrant_type,
    is_completed: false,
    created_at: now,
    updated_at: now,
  };
  const due = toMs(event.due_date);
  if (due !== null) data.due_date = due;
  if (event.notes) data.notes = String(event.notes);
  if (event.project_id) data.project_id = event.project_id;
  if (event.goal_id) data.goal_id = event.goal_id;
  const remind = toMs(event.reminder_at);
  if (remind !== null) data.reminder_at = remind;

  const addRes = await db.collection('todos').add({ data });
  const todoId = addRes._id;

  for (const b of blocks) {
    await db.collection('time_blocks').add({
      data: {
        _openid: openid,
        todo_id: todoId,
        title,
        quadrant_type: event.quadrant_type,
        start_time: toMs(b.start_time),
        end_time: toMs(b.end_time),
        created_at: now,
        updated_at: now,
      },
    });
  }

  return ok(Object.assign({ _id: todoId }, data));
}

async function get(openid, event) {
  const id = event.todo_id;
  if (!id) return fail('缺少 todo_id');
  const res = await db.collection('todos').where({ _id: id, _openid: openid }).get();
  if (!res.data.length) return fail('待办不存在', 404);
  const todo = res.data[0];
  const [subs, blocks] = await Promise.all([
    db.collection('subtasks').where({ _openid: openid, todo_id: id }).orderBy('order', 'asc').get(),
    db.collection('time_blocks').where({ _openid: openid, todo_id: id }).orderBy('start_time', 'asc').get(),
  ]);
  todo.subtasks = subs.data;
  todo.time_blocks = blocks.data;
  return ok(todo);
}

async function update(openid, event) {
  const id = event.id;
  if (!id) return fail('缺少 id');
  const res = await db.collection('todos').where({ _id: id, _openid: openid }).get();
  if (!res.data.length) return fail('待办不存在', 404);
  const todo = res.data[0];

  if (event.project_id) {
    const c = await db.collection('projects').where({ _id: event.project_id, _openid: openid }).count();
    if (!c.total) return fail('项目不存在', 404);
  }
  if (event.goal_id) {
    const c = await db.collection('goals').where({ _id: event.goal_id, _openid: openid }).count();
    if (!c.total) return fail('计划不存在', 404);
  }

  const data = { updated_at: Date.now() };
  let justCompleted = false;
  if (event.title !== undefined) {
    const t = String(event.title).trim();
    if (!t) return fail('标题不能为空');
    data.title = t;
  }
  if (event.quadrant_type !== undefined) {
    if (!QUADRANTS.includes(event.quadrant_type)) return fail('请选择象限');
    data.quadrant_type = event.quadrant_type;
  }
  if (event.notes !== undefined) data.notes = (event.notes === null || event.notes === '') ? _.remove() : String(event.notes);
  if (event.due_date !== undefined) {
    const due = toMs(event.due_date);
    data.due_date = due === null ? _.remove() : due;
  }
  if (event.reminder_at !== undefined) {
    const r = toMs(event.reminder_at);
    data.reminder_at = r === null ? _.remove() : r;
  }
  if (event.project_id !== undefined) data.project_id = event.project_id ? event.project_id : _.remove();
  if (event.goal_id !== undefined) data.goal_id = event.goal_id ? event.goal_id : _.remove();
  if (event.is_completed !== undefined) {
    const completed = event.is_completed === true || event.is_completed === 'true';
    data.is_completed = completed;
    if (completed && !todo.is_completed) { data.completed_at = Date.now(); justCompleted = true; }
    if (!completed) data.completed_at = _.remove();
  }

  await db.collection('todos').doc(id).update({ data });
  if (justCompleted) await ensurePetIncrement(openid);
  return ok(Object.assign({}, todo, data, { _id: id }));
}

async function remove(openid, event) {
  const id = event.id;
  if (!id) return fail('缺少 id');
  const res = await db.collection('todos').where({ _id: id, _openid: openid }).get();
  if (!res.data.length) return fail('待办不存在', 404);
  await Promise.all([
    db.collection('subtasks').where({ _openid: openid, todo_id: id }).remove(),
    db.collection('time_blocks').where({ _openid: openid, todo_id: id }).remove(),
  ]);
  await db.collection('todos').doc(id).remove();
  return ok({ _id: id });
}

// ---------- 子任务 ----------
async function subtaskList(openid, event) {
  const res = await db.collection('subtasks').where({ _openid: openid, todo_id: event.todo_item_id }).orderBy('order', 'asc').get();
  return ok({ list: res.data });
}

async function subtaskCreate(openid, event) {
  const title = String(event.title || '').trim();
  if (!title) return fail('子任务标题不能为空');
  const t = await db.collection('todos').where({ _id: event.todo_item_id, _openid: openid }).count();
  if (!t.total) return fail('待办不存在', 404);
  const cnt = await db.collection('subtasks').where({ _openid: openid, todo_id: event.todo_item_id }).count();
  const now = Date.now();
  const data = { _openid: openid, todo_id: event.todo_item_id, title, is_completed: false, order: cnt.total, created_at: now, updated_at: now };
  const res = await db.collection('subtasks').add({ data });
  return ok(Object.assign({ _id: res._id }, data));
}

async function subtaskUpdate(openid, event) {
  const id = event.id;
  const s = await db.collection('subtasks').where({ _id: id, _openid: openid }).get();
  if (!s.data.length) return fail('子任务不存在', 404);
  const data = { updated_at: Date.now() };
  if (event.title !== undefined) data.title = String(event.title).trim();
  if (event.is_completed !== undefined) data.is_completed = event.is_completed === true || event.is_completed === 'true';
  await db.collection('subtasks').doc(id).update({ data });
  return ok(Object.assign({}, s.data[0], data, { _id: id }));
}

async function subtaskRemove(openid, event) {
  const id = event.id;
  await db.collection('subtasks').where({ _id: id, _openid: openid }).remove();
  return ok({ _id: id });
}

// ---------- 时间块 ----------
async function timeblockList(openid, event) {
  const where = { _openid: openid };
  if (event.todo_item_id) where.todo_id = event.todo_item_id;
  const c = rangeCond(event.start_ms, event.end_ms);
  if (c) where.start_time = c;
  const res = await db.collection('time_blocks').where(where).orderBy('start_time', 'asc').get();
  return ok({ list: res.data });
}

async function timeblockCreate(openid, event) {
  const t = await db.collection('todos').where({ _id: event.todo_item_id, _openid: openid }).get();
  if (!t.data.length) return fail('待办不存在', 404);
  const s = toMs(event.start_time), e = toMs(event.end_time);
  if (s === null || e === null || e <= s) return fail('结束时间必须晚于开始时间');
  if (dayOf(s) !== dayOf(e)) return fail('时间块不能跨天');
  const now = Date.now();
  const todo = t.data[0];
  const data = { _openid: openid, todo_id: todo._id, title: todo.title, quadrant_type: todo.quadrant_type, start_time: s, end_time: e, created_at: now, updated_at: now };
  const res = await db.collection('time_blocks').add({ data });
  return ok(Object.assign({ _id: res._id }, data));
}

async function timeblockRemove(openid, event) {
  const id = event.id;
  await db.collection('time_blocks').where({ _id: id, _openid: openid }).remove();
  return ok({ _id: id });
}

// ---------- 统计 ----------
async function statisticsDaily(openid, event) {
  const where = { _openid: openid, is_completed: true, habit_id: _.exists(false) };
  const c = rangeCond(event.start_ms, event.end_ms);
  if (c) where.completed_at = c;
  const res = await db.collection('todos')
    .where(where)
    .field({ completed_at: true, quadrant_type: true })
    .limit(1000)
    .get();
  return ok({ list: res.data });
}

async function statisticsQuadrant(openid) {
  const res = await db.collection('todos')
    .aggregate()
    .match({ _openid: openid, habit_id: _.exists(false) })
    .group({ _id: '$quadrant_type', count: $.sum(1) })
    .end();
  const counts = { total: 0 };
  for (const q of QUADRANTS) counts[q] = 0;
  for (const row of res.list) {
    if (QUADRANTS.includes(row._id)) {
      counts[row._id] = row.count;
      counts.total += row.count;
    }
  }
  return ok(counts);
}

/**
 * statsBootstrap：统计页初始化数据（每日完成 + 象限分布 + 已完成列表）
 * 合并原先三次 callFunction（statisticsDaily / statisticsQuadrant / list）为一次，
 * 避免并发抢占云函数实例。
 */
async function statsBootstrap(openid, event) {
  const [daily, quad, completed] = await Promise.all([
    statisticsDaily(openid, event),
    statisticsQuadrant(openid),
    list(openid, event),
  ]);
  if (daily.code !== 0) return daily;
  if (quad.code !== 0) return quad;
  if (completed.code !== 0) return completed;
  return ok({ daily: daily.data.list, quadrant: quad.data, completed: completed.data });
}

/**
 * 完成待办时累加养成猫的计数（分维度，只增不减）。
 * 直接下发条件更新，命中即 1 次数据库操作；只有首次（文档不存在）才多一次写入，
 * 避免在「完成任务」这条热路径上固定付出「先查后改」两次操作。
 */
async function ensurePetIncrement(openid) {
  const now = Date.now();
  const res = await db.collection('pet').where({ _openid: openid }).update({
    data: { 'stats.todo_completed': _.inc(1), updated_at: now },
  });
  if (res.stats && res.stats.updated) return;
  await db.collection('pet').add({
    data: {
      _openid: openid,
      active_cat_id: 'orange',
      owned_cats: [{ cat_id: 'orange', at: now }],
      stats: { todo_completed: 1, habit_checkin: 0, review_done: 0, goal_achieved: 0 },
      last_seen_at: now,
      visit_streak: 1,
      created_at: now,
      updated_at: now,
    },
  });
}

exports.main = async (event, context) => {
  const { OPENID } = cloud.getWXContext();
  if (!OPENID) return fail('无法获取用户身份', 401);
  const action = event && event.action;
  try {
    switch (action) {
      case 'list': return await list(OPENID, event);
      case 'create': return await create(OPENID, event);
      case 'get': return await get(OPENID, event);
      case 'update': return await update(OPENID, event);
      case 'remove': return await remove(OPENID, event);
      case 'subtaskList': return await subtaskList(OPENID, event);
      case 'subtaskCreate': return await subtaskCreate(OPENID, event);
      case 'subtaskUpdate': return await subtaskUpdate(OPENID, event);
      case 'subtaskRemove': return await subtaskRemove(OPENID, event);
      case 'timeblockList': return await timeblockList(OPENID, event);
      case 'timeblockCreate': return await timeblockCreate(OPENID, event);
      case 'timeblockRemove': return await timeblockRemove(OPENID, event);
      case 'statisticsDaily': return await statisticsDaily(OPENID, event);
      case 'statsBootstrap': return await statsBootstrap(OPENID, event);
      case 'statisticsQuadrant': return await statisticsQuadrant(OPENID);
      default: return fail('未知操作: ' + action);
    }
  } catch (e) {
    console.error('[todo]', action, e);
    return fail((e && e.message) || '服务端错误', 500);
  }
};
