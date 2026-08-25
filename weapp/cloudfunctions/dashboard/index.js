/**
 * dashboard 云函数：今日概览（日程/待办 + 完成度）
 * 今日边界由客户端传入；今日习惯由客户端并行调用 habit 云函数获取
 */
const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();
const _ = db.command;

const ok = (d = null) => ({ code: 0, data: d });
const fail = (m, c = 1) => ({ code: c, message: m });

async function today(openid, event) {
  const todayStr = event.today_str;
  const startMs = Number(event.today_start_ms);
  const endMs = Number(event.today_end_ms);
  const range = _.gte(startMs).and(_.lte(endMs));

  // 今日日程：今天开始的时间块
  const blocks = await db.collection('time_blocks').where({ _openid: openid, start_time: range }).orderBy('start_time', 'asc').get();

  // 今日待办：due_date 今天 ∪ 今天有时间块，排除习惯生成
  const dueTodos = await db.collection('todos').where({ _openid: openid, habit_id: _.exists(false), due_date: range }).field({ _id: true }).limit(1000).get();
  const scheduledTodos = await db.collection('time_blocks').where({ _openid: openid, start_time: range }).field({ todo_id: true }).get();
  const idSet = new Set();
  for (const t of dueTodos.data) idSet.add(t._id);
  for (const b of scheduledTodos.data) if (b.todo_id) idSet.add(b.todo_id);
  const ids = Array.from(idSet);

  let tasks = [], completedCount = 0, totalCount = 0;
  if (ids.length) {
    const res = await db.collection('todos').where({ _openid: openid, _id: _.in(ids), habit_id: _.exists(false) }).get();
    totalCount = res.data.length;
    completedCount = res.data.filter((t) => t.is_completed).length;
    tasks = res.data.filter((t) => !t.is_completed).sort((a, b) => {
      const an = a.due_date ? 0 : 1, bn = b.due_date ? 0 : 1;
      if (an !== bn) return an - bn;
      return (a.due_date || 0) - (b.due_date || 0);
    });
  }

  return ok({
    date: todayStr,
    schedule: blocks.data.map((b) => ({ _id: b._id, todo_item_id: b.todo_id, title: b.title, quadrant_type: b.quadrant_type, start_time: b.start_time, end_time: b.end_time })),
    tasks,
    completed_task_count: completedCount,
    total_task_count: totalCount,
  });
}

exports.main = async (event, context) => {
  const { OPENID } = cloud.getWXContext();
  if (!OPENID) return fail('无法获取用户身份', 401);
  const action = event && event.action;
  try {
    switch (action) {
      case 'today': return await today(OPENID, event);
      default: return fail('未知操作: ' + action);
    }
  } catch (e) {
    console.error('[dashboard]', action, e);
    return fail((e && e.message) || '服务端错误', 500);
  }
};
