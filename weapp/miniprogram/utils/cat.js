/**
 * 养成猫：本地缓存 + 台词规则求值
 *
 * 性能要点：热页面（今日/四象限/习惯）渲染猫时【不发任何网络请求】。
 * 配置（猫的定义 + 台词）和用户状态都缓存在 Storage：
 *  - 配置只有作者会改，靠 config_version 判断是否需要更新，命中率接近 100%
 *  - 用户状态只在完成任务时增长，本地乐观累加即可，偏差几次对猫说什么毫无影响
 * 真正的同步只发生在猫窝页（显式访问）和后台静默刷新时。
 */
const CONFIG_KEY = 'cat_config';
const STATE_KEY = 'cat_state';

const SPEAK_THRESHOLD = 5; // 累计完成数达到该值猫才开始说话

// ---------- 缓存读写 ----------
function getConfig() {
  try { return wx.getStorageSync(CONFIG_KEY) || null; } catch (e) { return null; }
}
function setConfig(cfg) {
  try { wx.setStorageSync(CONFIG_KEY, cfg); } catch (e) { /* 容量满等情况忽略，下次重新拉 */ }
}
function getState() {
  try { return wx.getStorageSync(STATE_KEY) || null; } catch (e) { return null; }
}
function setState(st) {
  try { wx.setStorageSync(STATE_KEY, st); } catch (e) { /* 同上 */ }
}
function configVersion() {
  const c = getConfig();
  return (c && c.version) || 0;
}

/**
 * 把 bootstrap 的返回写入缓存。配置为空表示服务端判定版本未变，保留原缓存。
 */
function saveBootstrap(res) {
  if (!res) return;
  if (res.config) setConfig(res.config);
  const pet = res.pet || {};
  setState({
    stats: pet.stats || {},
    total: res.total || 0,
    active_cat_id: pet.active_cat_id || 'orange',
    owned_cats: (pet.owned_cats || []).map((o) => o.cat_id),
    visit_streak: pet.visit_streak || 0,
    pet_name: pet.pet_name || '',
  });
}

/**
 * 本地乐观累加某个维度。完成任务后立即调用，猫的进度即时反映，
 * 无需为了刷新计数再发一次请求（服务端仍是真源，下次 bootstrap 会校准）。
 */
function bump(field, n) {
  const st = getState();
  if (!st) return;
  st.stats = st.stats || {};
  st.stats[field] = (st.stats[field] || 0) + (n || 1);
  st.total = (st.total || 0) + (n || 1);
  setState(st);
}

// ---------- 条件求值 ----------
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
    return fn(ctx[c.field] || 0, c.value);
  });
}

// 日期种子：同一天内选中同一条变体（不会一刷新就换，那样显得很廉价），跨天轮换
function daySeed() {
  const d = new Date();
  return d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate();
}

function fill(text, ctx) {
  return String(text).replace(/\{(\w+)\}/g, (m, k) => (ctx && ctx[k] != null ? ctx[k] : ''));
}

/**
 * 选一句台词。纯本地计算，零网络。
 * @param page  today | quadrant | habit | pet
 * @param ctx   页面上下文（overdue / pending / urgent_important ...）
 * @returns 台词字符串；猫还不会说话或没有命中规则时返回 null
 */
function pickLine(page, ctx) {
  const cfg = getConfig();
  const st = getState();
  if (!cfg || !st) return null;

  const total = st.total || 0;
  if (total < SPEAK_THRESHOLD) return null;

  // 台词条件读页面上下文，解锁条件读累计计数，两者字段空间不同
  const full = Object.assign({ _total: total, visit_streak: st.visit_streak || 0 }, st.stats || {}, ctx || {});
  const unlockCtx = Object.assign({ _total: total }, st.stats || {});
  const activeCat = st.active_cat_id || 'orange';

  const hit = (cfg.lines || [])
    .filter((l) => l.page === page)
    .filter((l) => l.cat_id === '*' || l.cat_id === activeCat)
    .filter((l) => matches(l.unlock, unlockCtx))
    .filter((l) => matches(l.conditions, full))
    .sort((a, b) => (b.priority || 0) - (a.priority || 0))[0];

  if (!hit) return null;
  const texts = hit.texts && hit.texts.length ? hit.texts : [hit.text];
  if (!texts.length) return null;
  return fill(texts[daySeed() % texts.length], full);
}

// 成长阶段由累计总数驱动，一张图 + CSS 缩放即可，无需按阶段准备美术
function growthStage(total) {
  if (total < 10) return { label: '幼猫', scale: 0.72, next: 10 };
  if (total < 50) return { label: '少年猫', scale: 0.9, next: 50 };
  if (total < 150) return { label: '成猫', scale: 1.0, next: 150 };
  return { label: '大猫', scale: 1.12, next: null };
}

module.exports = {
  SPEAK_THRESHOLD, CONFIG_KEY, STATE_KEY,
  getConfig, getState, setState, configVersion, saveBootstrap, bump,
  pickLine, growthStage, matches,
};
