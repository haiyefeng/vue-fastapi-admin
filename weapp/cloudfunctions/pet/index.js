/**
 * pet 云函数：养成猫
 *
 * 数据分两类：
 *  - 配置数据（所有用户共享、只读、极少变）：cats（猫的定义）、cat_lines（台词 + 触发条件）
 *  - 用户数据（一人一条）：pet（当前猫、已解锁的猫、分维度累计计数）
 *
 * 性能约定：
 *  - 客户端只在 bootstrap 时带上已缓存的 config_version，版本未变则不回传配置，
 *    热页面（今日/四象限/习惯）因此可以完全走本地缓存、零网络开销地渲染猫。
 *  - 配置版本 = 两个配置集合中最大的 updated_at，改台词后自动生效，无需手动维护版本号。
 */
const cloud = require('wx-server-sdk');
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();
const _ = db.command;

const ok = (d = null) => ({ code: 0, data: d });
const fail = (m, c = 1) => ({ code: c, message: m });

// 计数维度：新增维度时在这里加一项即可，解锁条件与台词条件都能直接引用
const STAT_FIELDS = ['todo_completed', 'habit_checkin', 'review_done', 'goal_achieved'];

const emptyStats = () => STAT_FIELDS.reduce((o, k) => { o[k] = 0; return o; }, {});

/**
 * 读取用户的猫，不存在则创建。
 * 兼容旧结构：老版本只有标量 total_earned，这里迁移到 stats.todo_completed，
 * 避免用户升级后进度归零。
 */
async function ensurePet(openid) {
  const res = await db.collection('pet').where({ _openid: openid }).get();
  const now = Date.now();

  if (!res.data.length) {
    const data = {
      _openid: openid,
      active_cat_id: 'orange',
      owned_cats: [{ cat_id: 'orange', at: now }],
      stats: emptyStats(),
      last_seen_at: now,
      visit_streak: 1,
      created_at: now,
      updated_at: now,
    };
    const add = await db.collection('pet').add({ data });
    return Object.assign({ _id: add._id }, data);
  }

  const pet = res.data[0];
  if (pet.stats) return pet;

  // ---- 旧结构迁移（只在第一次读到老文档时执行一次）----
  const stats = emptyStats();
  stats.todo_completed = pet.total_earned || 0;
  const owned = (pet.unlocked_skins || ['orange']).map((id) => ({ cat_id: id, at: pet.created_at || now }));
  const patch = {
    stats,
    owned_cats: owned,
    active_cat_id: pet.skin_id || 'orange',
    updated_at: now,
  };
  await db.collection('pet').doc(pet._id).update({ data: patch });
  return Object.assign({}, pet, patch);
}

// 累计计数总和，驱动成长阶段
const totalOf = (stats) => STAT_FIELDS.reduce((s, k) => s + ((stats && stats[k]) || 0), 0);

// 声明式条件求值：[{field, op, value}]，多条为「与」关系
const OPS = {
  gte: (a, b) => a >= b, gt: (a, b) => a > b,
  lte: (a, b) => a <= b, lt: (a, b) => a < b,
  eq: (a, b) => a === b, ne: (a, b) => a !== b,
};
function matches(conds, ctx) {
  if (!Array.isArray(conds) || !conds.length) return true;
  return conds.every((c) => {
    const fn = OPS[c.op];
    if (!fn) return false;
    const left = c.field === '_total' ? totalOf(ctx) : (ctx[c.field] || 0);
    return fn(left, c.value);
  });
}

// 按 stats 判定应当拥有哪些猫，新解锁的写回并单独返回（供前端弹「解锁」提示）
async function applyUnlocks(pet, cats) {
  const owned = (pet.owned_cats || []).slice();
  const ownedIds = owned.map((o) => o.cat_id);
  const newly = [];
  const now = Date.now();

  for (const c of cats) {
    if (ownedIds.indexOf(c._id) >= 0) continue;
    if (matches(c.unlock, pet.stats)) {
      owned.push({ cat_id: c._id, at: now });
      newly.push(c._id);
    }
  }
  if (newly.length) {
    await db.collection('pet').doc(pet._id).update({ data: { owned_cats: owned, updated_at: now } });
    pet.owned_cats = owned;
  }
  return newly;
}

// 记录来访：跨天才更新，避免同一天反复进页面反复写库
async function touchVisit(pet) {
  const now = Date.now();
  const dayOf = (ms) => { const d = new Date(ms); return d.getFullYear() * 10000 + d.getMonth() * 100 + d.getDate(); };
  const last = pet.last_seen_at || 0;
  if (last && dayOf(last) === dayOf(now)) return pet;

  const streak = (now - last) < 2 * 86400000 ? (pet.visit_streak || 0) + 1 : 1;
  await db.collection('pet').doc(pet._id).update({ data: { last_seen_at: now, visit_streak: streak, updated_at: now } });
  pet.last_seen_at = now;
  pet.visit_streak = streak;
  return pet;
}

async function loadConfig() {
  const [cats, lines] = await Promise.all([
    db.collection('cats').orderBy('order', 'asc').limit(100).get(),
    db.collection('cat_lines').limit(1000).get(),
  ]);
  const all = cats.data.concat(lines.data);
  const version = all.reduce((m, d) => Math.max(m, d.updated_at || 0), 0);
  return { cats: cats.data, lines: lines.data, version };
}

/**
 * 一次调用拿齐：用户状态 + （必要时）配置。
 * 客户端把配置缓存到本地 Storage，version 未变就不重复传输。
 */
async function bootstrap(openid, event) {
  let pet = await ensurePet(openid);
  const config = await loadConfig();
  const newly = await applyUnlocks(pet, config.cats);
  if (event.touch !== false) pet = await touchVisit(pet);

  const out = {
    pet,
    total: totalOf(pet.stats),
    newly_unlocked: newly,
    config_version: config.version,
  };
  // 版本一致时省略配置体，热页面因此只传回极小的用户状态
  if (Number(event.config_version) !== config.version) {
    out.config = { cats: config.cats, lines: config.lines, version: config.version };
  }
  return ok(out);
}

async function update(openid, event) {
  const pet = await ensurePet(openid);
  const data = { updated_at: Date.now() };
  if (event.active_cat_id !== undefined) {
    const owned = (pet.owned_cats || []).map((o) => o.cat_id);
    if (owned.indexOf(event.active_cat_id) < 0) return fail('这只猫还没解锁');
    data.active_cat_id = event.active_cat_id;
  }
  if (event.pet_name !== undefined) data.pet_name = String(event.pet_name).slice(0, 20);
  await db.collection('pet').doc(pet._id).update({ data });
  return ok(Object.assign({}, pet, data));
}

exports.main = async (event, context) => {
  const { OPENID } = cloud.getWXContext();
  if (!OPENID) return fail('无法获取用户身份', 401);
  const action = event && event.action;
  try {
    switch (action) {
      case 'bootstrap': return await bootstrap(OPENID, event);
      case 'update': return await update(OPENID, event);
      case 'seed': return await require('./seed')(db, _);
      default: return fail('未知操作: ' + action);
    }
  } catch (e) {
    console.error('[pet]', action, e);
    return fail((e && e.message) || '服务端错误', 500);
  }
};
