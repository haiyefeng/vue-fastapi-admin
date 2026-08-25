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

async function listCategories(openid, event) {
  const where = { _openid: openid };
  if (!event.include_archived) where.is_archived = false;
  const res = await db.collection('categories').where(where).orderBy('display_order', 'asc').get();
  return ok({ list: res.data });
}

async function list(openid, event) {
  const where = { _openid: openid, is_archived: event.archived ? true : false };
  const res = await db.collection('projects').where(where).orderBy('created_at', 'desc').get();
  return ok({ list: res.data });
}

/**
 * bootstrap：任务页初始化数据（在职项目 + 归档项目 + 分类）
 * 合并原先三次 callFunction（list / list?archived / listCategories）为一次，
 * 避免云函数单实例单并发下并发拉起多个实例造成的冷启动开销。
 */
async function bootstrap(openid) {
  const [projects, cats] = await Promise.all([
    db.collection('projects').where({ _openid: openid }).orderBy('created_at', 'desc').get(),
    db.collection('categories').where({ _openid: openid, is_archived: false }).orderBy('display_order', 'asc').get(),
  ]);
  return ok({
    list: projects.data.filter((p) => !p.is_archived),
    archived: projects.data.filter((p) => p.is_archived),
    categories: cats.data,
  });
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
  const data = {
    _openid: openid,
    name,
    type: event.type === 'list' ? 'list' : 'project',
    is_archived: false,
    created_at: now,
    updated_at: now,
  };
  if (category_id) data.category_id = category_id;
  if (event.color_hex) data.color_hex = event.color_hex;
  const res = await db.collection('projects').add({ data });
  return ok(Object.assign({ _id: res._id }, data));
}

async function update(openid, event) {
  const id = event.id;
  const p = await db.collection('projects').where({ _id: id, _openid: openid }).get();
  if (!p.data.length) return fail('项目不存在', 404);
  const data = { updated_at: Date.now() };
  if (event.name !== undefined) data.name = String(event.name).trim();
  if (event.type !== undefined) data.type = event.type === 'list' ? 'list' : 'project';
  if (event.color_hex !== undefined) data.color_hex = event.color_hex ? event.color_hex : _.remove();
  if (event.is_archived !== undefined) data.is_archived = event.is_archived === true || event.is_archived === 'true';
  if (event.category_id !== undefined) data.category_id = event.category_id ? event.category_id : _.remove();
  await db.collection('projects').doc(id).update({ data });
  return ok(Object.assign({}, p.data[0], data, { _id: id }));
}

async function remove(openid, event) {
  const id = event.id;
  const p = await db.collection('projects').where({ _id: id, _openid: openid }).get();
  if (!p.data.length) return fail('项目不存在', 404);
  await db.collection('todos').where({ _openid: openid, project_id: id }).update({ data: { project_id: _.remove() } });
  await db.collection('projects').doc(id).remove();
  return ok({ _id: id });
}

exports.main = async (event, context) => {
  const { OPENID } = cloud.getWXContext();
  if (!OPENID) return fail('无法获取用户身份', 401);
  const action = event && event.action;
  try {
    switch (action) {
      case 'listCategories': return await listCategories(OPENID, event);
      case 'list': return await list(OPENID, event);
      case 'bootstrap': return await bootstrap(OPENID);
      case 'create': return await create(OPENID, event);
      case 'update': return await update(OPENID, event);
      case 'remove': return await remove(OPENID, event);
      default: return fail('未知操作: ' + action);
    }
  } catch (e) {
    console.error('[project]', action, e);
    return fail((e && e.message) || '服务端错误', 500);
  }
};
