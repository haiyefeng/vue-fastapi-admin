# 小程序迁移 · 阶段二：小程序切换到 HTTP 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把小程序的全部数据请求从 `wx.cloud.callFunction` 切换到 FastAPI 的 HTTP 接口，并删除 `cloudfunctions/` 目录。

**Architecture:** 小程序的数据层早已收敛——10 个页面只调 `services/*.js`（8 个文件共 99 行），底层统一走 `services/cloud.js` 的 `call(name, data)`。因此改造集中在 services 层：新增 `services/http.js` 替代 `cloud.js`，8 个 service 文件逐个改写为 REST 调用，**页面代码原则上不动**。逐模块切换，每切一个模块就在开发者工具里回归对应页面。

**Tech Stack:** 微信小程序原生（无框架）· `wx.request` · 微信开发者工具

**Spec:** `docs/superpowers/specs/2026-08-26-miniprogram-fastapi-migration-design.md`

**前置依赖:** `docs/superpowers/plans/2026-08-26-miniprogram-backend-api.md`（阶段一）全部完成并通过验收，特别是其中的 Task 15 差异校对文档 `docs/superpowers/notes/2026-08-26-cloudfn-parity.md`——本阶段凡是「结论 = 改小程序」的条目都要在对应模块的 Task 里落实。

## Global Constraints

- **中文注释与 commit message**。
- **小程序端没有测试运行器**，本阶段每个 Task 的验证是**开发者工具里的手动回归**。每个 Task 都给出了要点开的页面和要确认的现象——逐条走，不要跳。
- **开发者工具设置**：`详情 → 本地设置 → 勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」**。域名备案前只能这样连本机。
- **后端必须在跑**：`python run.py`（`:9999`）。
- **后端 token 请求头名字是 `token`**，不是 `Authorization`。见 `app/core/dependency.py::AuthControl.is_authed`。
- **后端响应恒为 `{code, msg, data}`**，且 HTTP 状态码与 `code` 一致（业务失败走 `Fail`，异常走 `app/core/exceptions.py` 的处理器）。所以 `http.js` 只需判 `code === 200`。
- **service 层对外的函数名保持不变**（`remove` / `dataSummary` / `bootstrap` …），只改内部实现指向的 URL。这是页面代码零改动的前提。
- **ID 全面从字符串变整数**。凡是把 id 拼进 `wx.navigateTo` URL 再从 `options` 里取回的地方，取回后必须 `Number()`。
- **提交粒度**：每个 Task 末尾提交一次。

---

## File Structure

**新建**

| 文件 | 职责 |
|---|---|
| `weapp/miniprogram/config.js` | 后端基址配置（开发/生产），替代 `envList.js` |
| `weapp/miniprogram/services/http.js` | HTTP 传输层：token 注入、响应解包、401 静默重登与请求重放 |
| `weapp/miniprogram/services/auth.js` | 登录状态：`wx.login` → `/base/wx_login` → token 存取，含并发锁 |
| `weapp/miniprogram/utils/storage.js` | 本地缓存的版本化清理（ID 类型变更后必须清空旧数据） |

**修改**

| 文件 | 改动 |
|---|---|
| `weapp/miniprogram/app.js` | 去掉 `wx.cloud.init`，改为启动时做 storage 版本校验 + 静默登录 |
| `weapp/miniprogram/services/dashboard.js` | 改调 `GET /dashboard/today` |
| `weapp/miniprogram/services/todo.js` | 改调 todo / subtask / timeblock / statistics 各 REST 端点 |
| `weapp/miniprogram/services/habit.js` | 改调 habit 各端点 |
| `weapp/miniprogram/services/goal.js` | 改调 goal 各端点 |
| `weapp/miniprogram/services/project.js` | 改调 project + category |
| `weapp/miniprogram/services/review.js` | 改调 review 各端点 |
| `weapp/miniprogram/services/pet.js` | 改调 pet 各端点 |
| `weapp/miniprogram/utils/date.js` | 移除只为云函数服务的毫秒边界导出（改造末期清理） |

**删除**（Task 11）

`weapp/cloudfunctions/`（整个目录）、`weapp/miniprogram/services/cloud.js`、`weapp/miniprogram/envList.js`、`weapp/uploadCloudFunction.sh`

---

### Task 1: 后端基址配置与传输层 `http.js`

**Files:**
- Create: `weapp/miniprogram/config.js`
- Create: `weapp/miniprogram/services/http.js`
- Test: 开发者工具手动验证

**Interfaces:**
- Produces:
  - `config.js` 导出 `{ BASE_URL: string }`
  - `http.js` 导出 `{ get(path, params), post(path, data), del(path, params), request(method, path, options) }`，全部返回 `Promise<data>`（已解包，失败时 reject 一个带 `code` / `msg` 的 Error）

**设计要点**：`cloud.js` 里的 `stripUndefined` 必须搬过来——GET 查询串里的 `undefined` 同样是脏数据，会变成字面量 `"undefined"` 传给后端。

- [ ] **Step 1: 写配置文件**

新建 `weapp/miniprogram/config.js`：

```js
/**
 * 后端基址配置。
 * 开发期：开发者工具需勾选「不校验合法域名」才能连本机 http。
 * 上线前：把 PROD 改成备案后的 https 域名，并在小程序后台配置 request 合法域名。
 */
const DEV = 'http://localhost:9999/api/v1';
const PROD = 'https://待备案域名/api/v1';

// 开发者工具与真机调试都属于非正式版本，envVersion 为 develop/trial
function resolveBaseUrl() {
  try {
    const info = wx.getAccountInfoSync();
    const env = info && info.miniProgram && info.miniProgram.envVersion;
    return env === 'release' ? PROD : DEV;
  } catch (e) {
    return DEV;
  }
}

module.exports = { BASE_URL: resolveBaseUrl() };
```

- [ ] **Step 2: 写传输层**

新建 `weapp/miniprogram/services/http.js`：

```js
/**
 * HTTP 传输层，替代原先的 services/cloud.js。
 *
 * 约定：
 *  - 后端恒返回 { code, msg, data }，且 HTTP 状态码与 code 一致
 *  - code === 200 视为成功，直接把 data 交给调用方；其余 reject 一个带 code/msg 的 Error
 *  - 401 触发静默重登并重放原请求（见 services/auth.js 的并发锁）
 *  - 沿用 cloud.js 的 stripUndefined：GET 查询串里的 undefined 会变成字面量 "undefined"
 */
const { BASE_URL } = require('../config');
const auth = require('./auth');

function stripUndefined(v) {
  if (Array.isArray(v)) return v.map(stripUndefined);
  if (v !== null && typeof v === 'object') {
    const out = {};
    for (const key of Object.keys(v)) {
      if (v[key] !== undefined) out[key] = stripUndefined(v[key]);
    }
    return out;
  }
  return v;
}

function rawRequest(method, path, payload, token) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + path,
      method,
      data: stripUndefined(payload || {}),
      header: token ? { token, 'content-type': 'application/json' } : { 'content-type': 'application/json' },
      success: resolve,
      fail: (err) => reject(new Error((err && err.errMsg) || '网络请求失败')),
    });
  });
}

async function request(method, path, payload, options = {}) {
  const token = await auth.getToken();
  let res = await rawRequest(method, path, payload, token);

  // token 过期或失效：静默重登一次再重放。auth.login 内部有并发锁，
  // 多个请求同时 401 只会真正登录一次。
  if (res.statusCode === 401 && !options._retried) {
    const fresh = await auth.login({ force: true });
    res = await rawRequest(method, path, payload, fresh);
  }

  const body = res.data || {};
  if (body.code === 200) return body.data;

  const err = new Error(body.msg || `请求失败(${res.statusCode})`);
  err.code = body.code || res.statusCode;
  err.body = body;
  throw err;
}

const get = (path, params) => request('GET', path, params);
const post = (path, data) => request('POST', path, data);
const del = (path, params) => request('DELETE', path, params);

module.exports = { request, get, post, del };
```

- [ ] **Step 3: 提交（此时还跑不起来，auth.js 在 Task 2）**

```bash
git add weapp/miniprogram/config.js weapp/miniprogram/services/http.js
git commit -m "feat(weapp): 新增后端基址配置与 HTTP 传输层"
```

---

### Task 2: 登录状态 `auth.js` 与并发锁

**Files:**
- Create: `weapp/miniprogram/services/auth.js`
- Modify: `weapp/miniprogram/app.js`
- Test: 开发者工具手动验证

**Interfaces:**
- Consumes: `config.BASE_URL`（Task 1）
- Produces: `auth.getToken() -> Promise<string>`、`auth.login({force}) -> Promise<string>`、`auth.clear() -> void`

**这是本阶段最容易写出 bug 的地方**（spec §4.4）。没有并发锁的话，首屏若同时发 3 个请求，就会触发 3 次 `wx.login`，其中两次的 code 会被微信作废，表现为随机的登录失败。

- [ ] **Step 1: 实现**

新建 `weapp/miniprogram/services/auth.js`：

```js
/**
 * 登录状态管理。
 *
 * 不主动判断 token 过期（后端有效期 7 天，本地也读不到过期时间），
 * 靠 401 触发静默重登——见 services/http.js。
 *
 * pending 是并发锁：首屏同时发多个请求时，若都撞上 401，
 * 必须只真正登录一次。wx.login 的 code 是一次性的，
 * 并发调用会让先拿到的 code 被作废，表现为随机登录失败。
 */
const { BASE_URL } = require('../config');

const TOKEN_KEY = 'auth_token';
let pending = null;

function getStoredToken() {
  try {
    return wx.getStorageSync(TOKEN_KEY) || '';
  } catch (e) {
    return '';
  }
}

function setStoredToken(token) {
  try {
    wx.setStorageSync(TOKEN_KEY, token);
  } catch (e) {
    /* 容量满等情况忽略，下次重新登录 */
  }
}

function clear() {
  try {
    wx.removeStorageSync(TOKEN_KEY);
  } catch (e) {
    /* 忽略 */
  }
}

function wxLoginCode() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: (res) => (res.code ? resolve(res.code) : reject(new Error('wx.login 未返回 code'))),
      fail: (err) => reject(new Error((err && err.errMsg) || 'wx.login 失败')),
    });
  });
}

function exchangeToken(code) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + '/base/wx_login',
      method: 'POST',
      data: { code },
      header: { 'content-type': 'application/json' },
      success: (res) => {
        const body = res.data || {};
        if (body.code === 200 && body.data && body.data.access_token) resolve(body.data.access_token);
        else reject(new Error(body.msg || '登录失败'));
      },
      fail: (err) => reject(new Error((err && err.errMsg) || '登录请求失败')),
    });
  });
}

function login({ force = false } = {}) {
  if (!force) {
    const cached = getStoredToken();
    if (cached) return Promise.resolve(cached);
  }
  if (pending) return pending;

  pending = wxLoginCode()
    .then(exchangeToken)
    .then((token) => {
      setStoredToken(token);
      return token;
    })
    .finally(() => {
      pending = null;
    });

  return pending;
}

function getToken() {
  const cached = getStoredToken();
  return cached ? Promise.resolve(cached) : login();
}

module.exports = { getToken, login, clear, TOKEN_KEY };
```

- [ ] **Step 2: 改造 `app.js`**

把 `weapp/miniprogram/app.js` 整个替换为：

```js
// app.js
const auth = require('./services/auth');

App({
  onLaunch: function () {
    // 提前静默登录，让首屏请求不必各自等一次 wx.login
    auth.login().catch((e) => {
      console.error('[auth] 启动登录失败', e);
    });
  },
});
```

- [ ] **Step 3: 手动验证**

在微信开发者工具里：

1. 确认后端在跑（`python run.py`）
2. `详情 → 本地设置` 勾选「不校验合法域名…」
3. 清缓存：`工具 → 清除缓存 → 全部清除`
4. 重新编译，看 Network 面板

Expected:
- 有一条 `POST /api/v1/base/wx_login`，返回 `code: 200` 且 `data.access_token` 非空，首次应 `is_new: true`
- `Storage` 面板里出现 `auth_token`
- 再次编译（不清缓存）时**不再发** `wx_login`——说明缓存命中

Expected（后端侧）：`app/logs/` 或控制台能看到该请求；数据库 `user` 表新增一条 `openid` 非空、`username` 形如 `wx_xxx` 的记录，且该用户已绑定「小程序用户」角色。

- [ ] **Step 4: 验证并发锁**

在 `pages/today/index.js` 的 `onLoad` 里临时加一段（验证完删掉）：

```js
    // 临时：验证 401 并发重登只触发一次登录
    const http = require('../../services/http');
    wx.setStorageSync('auth_token', 'invalid-token-for-test');
    Promise.all([
      http.get('/dashboard/today'),
      http.get('/dashboard/today'),
      http.get('/dashboard/today'),
    ]).then(() => console.log('三个并发请求都成功了'));
```

Expected: Network 面板里 3 条 `/dashboard/today` 先各返回 401，随后**只有 1 条** `wx_login`，然后 3 条重放请求全部返回 200，控制台打印「三个并发请求都成功了」。

> 如果看到多于 1 条 `wx_login`，说明并发锁没生效——检查 `pending` 是否在 `login()` 的所有分支上都被复用。

验证通过后**删除这段临时代码**。

- [ ] **Step 5: 提交**

```bash
git add weapp/miniprogram/services/auth.js weapp/miniprogram/app.js
git commit -m "feat(weapp): 新增微信登录与 401 静默重登（含并发锁）"
```

---

### Task 3: 本地缓存版本化清理

**Files:**
- Create: `weapp/miniprogram/utils/storage.js`
- Modify: `weapp/miniprogram/app.js`
- Test: 开发者工具手动验证

**Interfaces:**
- Produces: `storage.ensureVersion() -> void`，版本不匹配时清空全部本地缓存并写入新版本号

**为什么必须做**（spec §6.2）：ID 从字符串 `_id` 变成整数主键。用户升级后，Storage 里残留的旧 id（如养成猫的 `cat_state`、页面缓存的任务 id）会和新 id 混用，表现为「点进去找不到任务」这类极难排查的问题。

- [ ] **Step 1: 实现**

新建 `weapp/miniprogram/utils/storage.js`：

```js
/**
 * 本地缓存的版本化清理。
 *
 * 从云开发切到 FastAPI 后，所有 id 由字符串 _id 变成整数主键。
 * 老版本残留的缓存里混着旧 id，会造成「点进去找不到任务」这类难排查的问题，
 * 所以版本号一变就整体清空，让缓存从干净状态重建。
 * 以后凡是改变了缓存数据结构，把 STORAGE_VERSION 加一即可。
 */
const VERSION_KEY = 'storage_version';
const STORAGE_VERSION = 2; // 1 = 云开发时代；2 = FastAPI（整数 id）

function ensureVersion() {
  let current = 0;
  try {
    current = wx.getStorageSync(VERSION_KEY) || 0;
  } catch (e) {
    current = 0;
  }
  if (current === STORAGE_VERSION) return;

  try {
    wx.clearStorageSync();
    wx.setStorageSync(VERSION_KEY, STORAGE_VERSION);
    console.info('[storage] 缓存结构升级，已清空旧数据');
  } catch (e) {
    console.error('[storage] 清理缓存失败', e);
  }
}

module.exports = { ensureVersion, STORAGE_VERSION, VERSION_KEY };
```

- [ ] **Step 2: 在 `app.js` 里最先调用**

`weapp/miniprogram/app.js` 改为：

```js
// app.js
const auth = require('./services/auth');
const storage = require('./utils/storage');

App({
  onLaunch: function () {
    // 必须在任何读缓存的代码之前：id 类型已变，旧缓存必须先清掉
    storage.ensureVersion();

    // 提前静默登录，让首屏请求不必各自等一次 wx.login
    auth.login().catch((e) => {
      console.error('[auth] 启动登录失败', e);
    });
  },
});
```

- [ ] **Step 3: 手动验证**

1. 开发者工具 `Storage` 面板手动加一条 `storage_version = 1`，再随便加一条 `cat_state = {"x":1}`
2. 重新编译

Expected: 控制台打印「[storage] 缓存结构升级，已清空旧数据」，`Storage` 面板里 `cat_state` 消失，`storage_version` 变成 `2`，随后 `auth_token` 被重新写入（因为登录也被清掉了，会重新登录一次）。

3. 再次编译

Expected: 不再打印清理日志，`auth_token` 保留。

- [ ] **Step 4: 提交**

```bash
git add weapp/miniprogram/utils/storage.js weapp/miniprogram/app.js
git commit -m "feat(weapp): 缓存版本化清理，切换后端时清空旧 id 缓存"
```

---

### Task 4: 切换 dashboard（首个模块，打通链路）

**Files:**
- Modify: `weapp/miniprogram/services/dashboard.js`
- Test: 开发者工具「今日」页手动回归

**Interfaces:**
- Consumes: `http.get`（Task 1）
- Produces: `dashboard.today() -> Promise<data>`，签名不变

**先切它的原因**：只有一个接口、无参数、页面结构简单，是验证「登录 → 请求 → 解包 → 渲染」整条链路的最小样本。

**注意一个真实差异**：云函数版本要求客户端传 `today_str` / `today_start_ms` / `today_end_ms`（时区边界在客户端算）；**后端 `GET /dashboard/today` 不收任何参数**，日期边界由后端按 `Asia/Shanghai` 自己算（见 `app/api/v1/dashboard/route.py`）。用户与服务器同处东八区，这个差异无实际影响，但要记录在案——将来若有跨时区用户，需要回头补时区参数。

- [ ] **Step 1: 改写 service**

`weapp/miniprogram/services/dashboard.js` 整个替换为：

```js
const http = require('./http');

// 后端按 Asia/Shanghai 自行计算今日边界，不再需要客户端传时区参数
const today = () => http.get('/dashboard/today');

module.exports = { today };
```

- [ ] **Step 2: 手动回归「今日」页**

在开发者工具里打开 `pages/today/index`，逐条确认：

- [ ] 页面正常渲染，无报错
- [ ] Network 面板里是 `GET /api/v1/dashboard/today`，返回 `code: 200`
- [ ] 今日日程（时间块）区块的数据与后端数据库一致
- [ ] 今日待办列表正确
- [ ] 今日习惯打卡区块正确
- [ ] 完成度圆环数字正确

> 若某个区块空白，先比对后端 `GET /dashboard/today` 的返回字段名与页面模板取的字段名——云函数与后端的字段命名可能不同，这类差异应已记录在 `docs/superpowers/notes/2026-08-26-cloudfn-parity.md` 第 15 项。字段名不一致时**改小程序的取值，不要改后端**（Web 端也在用）。

- [ ] **Step 3: 提交**

```bash
git add weapp/miniprogram/services/dashboard.js
git commit -m "feat(weapp): dashboard 切换到 FastAPI 接口"
```

---

### Task 5: 切换 todo（含子任务、时间块、统计）

**Files:**
- Modify: `weapp/miniprogram/services/todo.js`
- Test: 「任务」「四象限」「日历」「任务详情」「待办统计」五个页面手动回归

**Interfaces:**
- Consumes: `http.get/post/del`（Task 1）
- Produces: `todo.js` 导出的 15 个函数，**名字与参数签名全部保持不变**

这是最大的一个模块。后端把子任务、时间块、统计拆成了独立路由组，所以一个 `todo` 云函数对应 4 个后端路由前缀。

- [ ] **Step 1: 改写 service**

`weapp/miniprogram/services/todo.js` 整个替换为：

```js
const http = require('./http');

// 后端把子任务/时间块/统计拆成了独立路由组，这里做一次映射，
// 让页面侧看到的仍是原来那一组 todo.* 函数。
const list = (params = {}) => http.get('/todo/list', params);
const create = (data = {}) => http.post('/todo/create', data);
const get = (todoId) => http.get('/todo/get', { todo_id: todoId });
const update = (id, data = {}) => http.post('/todo/update', Object.assign({ id }, data));
const remove = (id) => http.del('/todo/delete', { todo_id: id });

const subtaskList = (todoItemId) => http.get('/subtask/list', { todo_item_id: todoItemId });
const subtaskCreate = (data = {}) => http.post('/subtask/create', data);
const subtaskUpdate = (id, data = {}) => http.post('/subtask/update', Object.assign({ id }, data));
const subtaskRemove = (id) => http.del('/subtask/delete', { subtask_id: id });

const timeblockList = (params = {}) => http.get('/timeblock/list', params);
const timeblockCreate = (data = {}) => http.post('/timeblock/create', data);
const timeblockRemove = (id) => http.del('/timeblock/delete', { time_block_id: id });

const statisticsDaily = (params = {}) => http.get('/todo/statistics/daily', params);
const statisticsQuadrant = () => http.get('/todo/statistics/quadrant');
const statsBootstrap = (params = {}) => http.get('/todo/stats-bootstrap', params);

module.exports = {
  list, create, get, update, remove,
  subtaskList, subtaskCreate, subtaskUpdate, subtaskRemove,
  timeblockList, timeblockCreate, timeblockRemove,
  statisticsDaily, statisticsQuadrant, statsBootstrap,
};
```

> 上面的 Query 参数名已核对过后端路由签名：`GET /todo/get` 与 `DELETE /todo/delete` 用 `todo_id`（`app/api/v1/todos/route.py:92,130`），`GET /subtask/list` 用 `todo_item_id`、`DELETE /subtask/delete` 用 `subtask_id`（`app/api/v1/subtask/route.py:18,46`），`DELETE /timeblock/delete` 用 `time_block_id`（`app/api/v1/timeblock/route.py:64`）。

- [ ] **Step 2: 处理日期参数**

页面传给 `list` / `timeblockList` / `statisticsDaily` 的日期参数，云函数时代是**毫秒时间戳**（`due_start` / `completed_start` 等），后端要的是 **`YYYY-MM-DD` 字符串**（`start_date` / `end_date`）。

在各调用方（`pages/tasks`、`pages/calendar`、`pages/stats`）里，把传毫秒的地方改成传 `utils/date.js` 的 `toDateStr(ms)` 结果，参数名同时改为后端的 `start_date` / `end_date`。

**逐个 grep 找出所有调用点**：

```bash
cd weapp/miniprogram
grep -rn "due_start\|due_end\|completed_start\|completed_end\|_ms" pages/ services/
```

对每一处：确认它最终流向哪个后端参数，改成日期字符串，并把参数名对齐后端。

- [ ] **Step 3: 处理 ID 类型**

```bash
cd weapp/miniprogram
grep -rn "options.id\|options.todo_id\|currentTarget.dataset" pages/
```

对每一处从 URL 参数或 dataset 取回的 id，用 `Number()` 包一层——`wx.navigateTo` 的 query 与 `data-*` 属性取回的都是字符串，而后端现在要整数。

- [ ] **Step 4: 手动回归五个页面**

**「任务」页（`pages/tasks`）**
- [ ] 收件箱与各项目/清单的任务列表正确
- [ ] 「已过期 / 今天 / 稍后」三组分组正确
- [ ] 勾选完成 → 任务移出未完成组，后端 `todo` 表 `is_completed` 变 true
- [ ] 排序与筛选切换正常
- [ ] 分页/上拉加载正常

**「四象限」页（`pages/quadrant`）**
- [ ] 四个象限卡片各自的任务正确
- [ ] 新建任务落到正确象限
- [ ] 修改象限后任务移动到对应卡片
- [ ] 设置截止时间、备注后再进入详情仍在

**「日历」页（`pages/calendar`）**
- [ ] 日/周视图切换正常
- [ ] 时间块显示在正确的日期与时段
- [ ] 新建时间块后立即出现
- [ ] 「未排程任务」列表只含没有任何时间块的未完成任务

**「任务详情」页（`pages/task-detail`）**
- [ ] 从任务列表点进来能正确加载（**重点验证 ID 类型改造**）
- [ ] 子任务的增/删/改/勾选都生效
- [ ] 时间块的增删生效
- [ ] 关联项目、关联计划显示正确
- [ ] 提醒时间保存后回显正确

**「待办统计」页（`pages/stats`）**
- [ ] 每日完成柱状图有数据
- [ ] 四象限饼图比例正确
- [ ] 已完成列表分页、排序、删除都正常
- [ ] Network 面板确认走的是 `GET /todo/stats-bootstrap`（**一个请求**，不是三个）

- [ ] **Step 5: 提交**

```bash
git add weapp/miniprogram/services/todo.js weapp/miniprogram/pages/
git commit -m "feat(weapp): todo/子任务/时间块/统计切换到 FastAPI 接口"
```

---

### Task 6: 切换 habit

**Files:**
- Modify: `weapp/miniprogram/services/habit.js`
- Test: 「习惯」页手动回归

**Interfaces:**
- Consumes: `http.get/post/del`（Task 1）；`GET /habit/bootstrap`、`GET /habit/summary`（阶段一 Task 5、Task 9）
- Produces: `habit.js` 的 7 个函数，签名不变

**参数变化**：`todayParams()` 整个消失——后端自己算今日边界（`date.today()`），不再需要客户端传 `today_str` / `today_start_ms` / `today_end_ms`。

- [ ] **Step 1: 改写 service**

`weapp/miniprogram/services/habit.js` 整个替换为：

```js
const http = require('./http');

// 后端按 Asia/Shanghai 自行计算今日边界，原先的 todayParams() 不再需要
const list = () => http.get('/habit/list');
const archived = () => http.get('/habit/archived');
const bootstrap = () => http.get('/habit/bootstrap');
const create = (data = {}) => http.post('/habit/create', data);
const update = (id, data = {}) => http.post('/habit/update', Object.assign({ id }, data));
const remove = (id) => http.del('/habit/delete', { habit_id: id });
// 后端要 YYYY-MM-DD 字符串（start_date/end_date），不再是 start_str/end_str
const summary = (params = {}) => http.get('/habit/summary', params);

module.exports = { list, archived, bootstrap, create, update, remove, summary };
```

- [ ] **Step 2: 记下 summary 的调用方待改**

`summary` 的唯一调用点在「回顾总结」页（`pages/review/index.js:57`），参数名要从 `start_str` / `end_str` 改成 `start_date` / `end_date`，返回值的解包方式也要改。**这两处在 Task 8 一并处理**，本 Task 只改 service 层。

确认没有别的调用点：

```bash
cd weapp/miniprogram && grep -rn "\.summary(" pages/ services/
```

Expected: 只有 `pages/review/index.js` 一处。

- [ ] **Step 3: 手动回归「习惯」页（`pages/habits`）**

- [ ] 进行中习惯列表正确，Network 面板确认走 `GET /habit/bootstrap`（**一个请求**）
- [ ] 已归档习惯列表正确
- [ ] 四种频率都能创建：每天 / 每周几天 / 每周 N 次 / 每 N 天
- [ ] 打卡后当天状态变为已完成
- [ ] 连续天数（streak）数字正确
- [ ] 「每周 N 次」类型显示的是周进度（如 `2/3`）而不是 streak
- [ ] 暂停后不再生成新的打卡待办，历史保留
- [ ] 归档后从主列表消失、出现在归档列表
- [ ] 删除习惯后其历史打卡待办一并消失

- [ ] **Step 4: 提交**

```bash
git add weapp/miniprogram/services/habit.js weapp/miniprogram/pages/
git commit -m "feat(weapp): habit 切换到 FastAPI 接口"
```

---

### Task 7: 切换 goal 与 project

**Files:**
- Modify: `weapp/miniprogram/services/goal.js`
- Modify: `weapp/miniprogram/services/project.js`
- Test: 「计划」页与「任务」页的项目导航手动回归

**Interfaces:**
- Consumes: `GET /goal/bootstrap`、`GET /project/bootstrap`（阶段一 Task 6、Task 7）
- Produces: `goal.js` 7 个函数、`project.js` 6 个函数，签名不变

**注意 `project.listCategories` 的去向**：后端没有这个端点，分类走独立的 `GET /category/list`（spec §7.2）。service 层的函数名保留，只改内部 URL，页面不用动。

- [ ] **Step 1: 改写 goal service**

`weapp/miniprogram/services/goal.js` 整个替换为：

```js
const http = require('./http');

const list = () => http.get('/goal/list');
const archived = () => http.get('/goal/archived');
const bootstrap = () => http.get('/goal/bootstrap');
const detail = (goalId) => http.get('/goal/detail', { goal_id: goalId });
const create = (data = {}) => http.post('/goal/create', data);
const update = (id, data = {}) => http.post('/goal/update', Object.assign({ id }, data));
const remove = (id) => http.del('/goal/delete', { goal_id: id });

module.exports = { list, archived, bootstrap, detail, create, update, remove };
```

- [ ] **Step 2: 改写 project service**

`weapp/miniprogram/services/project.js` 整个替换为：

```js
const http = require('./http');

// 后端没有 project/listCategories，分类走独立的 category 路由组；
// 这里保留原函数名，页面侧无需改动
const listCategories = () => http.get('/category/list');
const list = () => http.get('/project/list');
const bootstrap = () => http.get('/project/bootstrap');
const create = (data = {}) => http.post('/project/create', data);
const update = (id, data = {}) => http.post('/project/update', Object.assign({ id }, data));
const remove = (id) => http.del('/project/delete', { project_id: id });

module.exports = { listCategories, list, bootstrap, create, update, remove };
```

- [ ] **Step 3: 手动回归「计划」页（`pages/goals`）**

- [ ] 进行中计划列表正确，Network 面板确认走 `GET /goal/bootstrap`（**一个请求**）
- [ ] 已归档计划列表正确
- [ ] 每个计划的进度条数字（关联任务完成数 / 总数）正确
- [ ] 关联习惯数量正确
- [ ] 点进详情能看到关联任务列表与关联习惯列表
- [ ] 新建 / 编辑 / 归档 / 删除计划都生效
- [ ] 删除计划后，原本关联它的任务与习惯仍在（只是解除了关联）

- [ ] **Step 4: 手动回归「任务」页的项目导航**

- [ ] 项目/清单列表正确，分类分组正确
- [ ] Network 面板确认走 `GET /project/bootstrap`（**一个请求**，不是 list + listCategories 两个）
- [ ] 切换项目后任务列表跟着变
- [ ] 新建 / 重命名 / 删除项目都生效

- [ ] **Step 5: 提交**

```bash
git add weapp/miniprogram/services/goal.js weapp/miniprogram/services/project.js weapp/miniprogram/pages/
git commit -m "feat(weapp): goal 与 project 切换到 FastAPI 接口"
```

---

### Task 8: 切换 review

**Files:**
- Modify: `weapp/miniprogram/services/review.js`
- Test: 「回顾总结」页手动回归

**Interfaces:**
- Produces: `review.js` 的 5 个函数，签名不变

**参数变化最大的一个模块**：云函数版本要客户端算好 `start_str` / `end_str` / `start_ms` / `end_ms` / `today_str` 五个参数传过去；**后端只要 `period_type` 与 `anchor_date` 两个参数**，周期边界由后端自己算（见 `app/api/v1/review/route.py`）。所以 `calcPeriodRange` 在 service 层不再需要——但**页面自己展示周期范围时可能还用它**，不要删除 `utils/date.js` 里的这个函数。

**`bootstrap` 的去向**：后端没有 `review/bootstrap`。它在云函数里是 `dataSummary` + `detail` 的合并。这里用 `Promise.all` 并发两个请求实现——**只有这一处例外**，因为回顾页不是高频页面，不值得为它在后端新增一个聚合端点。

- [ ] **Step 1: 改写 service**

`weapp/miniprogram/services/review.js` 整个替换为：

```js
const http = require('./http');

// 后端按 period_type + anchor_date 自行推算周期边界，
// 客户端不再需要传 start_str/end_str/start_ms/end_ms/today_str
const dataSummary = (periodType, anchorDate) =>
  http.get('/review/data-summary', { period_type: periodType, anchor_date: anchorDate });

const detail = (periodType, anchorDate) =>
  http.get('/review/detail', { period_type: periodType, anchor_date: anchorDate });

// 后端没有 review/bootstrap：回顾页不是高频页面，不值得为它加聚合端点，
// 这里用两个并发请求代替。键名 {summary, detail} 与云函数 review/index.js:119 一致，
// 页面 pages/review/index.js:59-60 直接读这两个键，因此页面无需改动
const bootstrap = (periodType, anchorDate) =>
  Promise.all([dataSummary(periodType, anchorDate), detail(periodType, anchorDate)]).then(
    ([summary, detail]) => ({ summary, detail })
  );

const save = (data = {}) => http.post('/review/save', data);
const list = (periodType) => http.get('/review/list', { period_type: periodType || undefined });

module.exports = { dataSummary, bootstrap, detail, save, list };
```

- [ ] **Step 2: 修正回顾页对 habit/summary 的调用**

`weapp/miniprogram/pages/review/index.js:57` 现在是：

```js
        habitApi.summary({ start_str: r.startStr, end_str: r.endStr, today_str: todayStr() }),
```

改为（参数名对齐后端的 `start_date` / `end_date`，`today_str` 后端自己算）：

```js
        habitApi.summary({ start_date: r.startStr, end_date: r.endStr }),
```

同一文件 `:61` 现在是：

```js
      summary.habits = (habitRes && habitRes.list) || [];
```

云函数 `habit.summary` 返回 `{ list: [...] }`，而后端 `GET /habit/summary` 返回的是**裸数组**（与 `/habit/list` 等其他后端端点一致）。改为：

```js
      summary.habits = habitRes || [];
```

`bootstrap` 的返回键名 `{ summary, detail }` 与云函数一致，`:59-60` 两行不用动。

- [ ] **Step 3: 手动回归「回顾总结」页（`pages/review`）**

- [ ] 周 / 月 / 季 / 年四种周期都能切换，数据跟着变
- [ ] 数据聚合区块正确：任务完成情况、习惯打卡情况、计划进展
- [ ] 习惯坚持度用的是 `GET /habit/summary`（Task 6 改的参数名在这里生效），完成数/应完成数正确
- [ ] 七步反思法的问答能输入
- [ ] 存草稿 → 退出 → 再进来内容还在
- [ ] 标记完成 → 状态变为已完成
- [ ] 历史回顾列表按周期开始日期倒序
- [ ] 点历史条目能加载出当时的内容

- [ ] **Step 4: 提交**

```bash
git add weapp/miniprogram/services/review.js weapp/miniprogram/pages/review/
git commit -m "feat(weapp): review 切换到 FastAPI 接口"
```

---

### Task 9: 切换 pet

**Files:**
- Modify: `weapp/miniprogram/services/pet.js`
- Test: 「猫窝」页 + 三个热页面手动回归

**Interfaces:**
- Consumes: `GET /pet/bootstrap`、`POST /pet/update`（阶段一 Task 12、Task 13）
- Produces: `pet.js` 的 `bootstrap` / `sync` / `update`

**`seed` 函数删除**：配置数据现在由后端启动时的 `init_pet_config()` 写入，不再需要客户端触发。

**关键验证点**：`utils/cat.js`（133 行本地缓存与台词求值）**一行都不该改**。阶段一的 pet 接口刻意返回了与云函数一致的形状（`cats`/`lines` 带 `_id`、通用台词 `cat_id` 为 `"*"`）。如果这一步需要改 `cat.js`，说明后端返回体没对齐，**应该回头改后端而不是改 `cat.js`**。

- [ ] **Step 1: 改写 service**

`weapp/miniprogram/services/pet.js` 整个替换为：

```js
const http = require('./http');
const cat = require('../utils/cat');

// 带上本地已缓存的配置版本；版本未变时服务端不会回传配置体
const bootstrap = () => http.get('/pet/bootstrap', { config_version: cat.configVersion() });
// 后台静默同步：不更新来访记录，避免非猫窝页也算作一次「来看我」
const sync = () => http.get('/pet/bootstrap', { config_version: cat.configVersion(), touch: false });
const update = (data = {}) => http.post('/pet/update', data);

// 配置数据改由后端启动时 init_pet_config() 幂等写入，不再需要客户端触发 seed
module.exports = { bootstrap, sync, update };
```

- [ ] **Step 2: 清理 seed 的调用点**

```bash
cd weapp/miniprogram && grep -rn "\.seed(" pages/ services/
```

找到的调用（通常是猫窝页的一个调试按钮）连同按钮一起删掉。

- [ ] **Step 3: 手动回归「猫窝」页（`pages/pet`）**

- [ ] 猫正常显示，成长阶段（幼猫/少年猫/成猫/大猫）与累计数匹配
- [ ] 猫会说话（累计完成数达到 5 之后）
- [ ] Network 面板：**首次**进入有 `GET /pet/bootstrap`，返回体里**有** `config`
- [ ] **再次**进入时返回体里**没有** `config`（版本命中缓存）
- [ ] 切换猫：只能切到已解锁的；切到未解锁的会提示「这只猫还没解锁」
- [ ] 给猫起名后回显正确，超过 20 字被截断
- [ ] 连续来访天数正确（同一天反复进入不重复累加）

- [ ] **Step 4: 验证热页面零请求**

分别打开「今日」「四象限」「习惯」三个页面，看 Network 面板：

- [ ] 这三个页面渲染猫时**不发任何 pet 请求**（这是 `utils/cat.js` 本地缓存的核心价值，spec §9.3）
- [ ] 猫说的话与当前页面上下文匹配（如今日页有过期任务时会提到过期件数）

- [ ] **Step 5: 验证计数与解锁**

- [ ] 完成一个任务 → 猫的累计数 +1（本地乐观累加，立即反映）
- [ ] 退出重进猫窝页 → 服务端返回的 `total` 与本地一致（说明后端 `pet_controller.increment` 生效）
- [ ] 数据库里 `pet_profile.stats` 的 `todo_completed` 与之匹配

- [ ] **Step 6: 确认 `cat.js` 未被修改**

```bash
git diff --stat weapp/miniprogram/utils/cat.js
```

Expected: 无输出（文件未改动）。若有改动，说明后端返回体没对齐，回头改 `app/controllers/pet.py::load_config` / `profile_out`。

- [ ] **Step 7: 提交**

```bash
git add weapp/miniprogram/services/pet.js weapp/miniprogram/pages/pet/
git commit -m "feat(weapp): pet 切换到 FastAPI 接口"
```

---

### Task 10: 全量回归

**Files:**
- Modify: 回归中发现问题的文件
- Test: 10 个页面完整走查

**Interfaces:** 无新增

切换完成后做一次端到端走查，重点是跨模块的联动——这些是逐模块回归时看不到的。

- [ ] **Step 1: 清空环境重来一遍**

1. 开发者工具 `工具 → 清除缓存 → 全部清除`
2. 后端数据库里删掉测试期间产生的微信用户（或换一个干净的库）
3. 重新编译

Expected: 完整跑通「首次登录 → 自动建号 → 空数据首屏」这条冷启动路径，10 个页面都不报错。

- [ ] **Step 2: 跨模块联动走查**

- [ ] 在「四象限」建一个任务 → 「任务」页收件箱能看到 → 「今日」页（若截止今天）能看到
- [ ] 给该任务加时间块 → 「日历」页对应时段出现
- [ ] 把该任务关联到某个计划 → 「计划」页该计划的任务总数 +1
- [ ] 完成该任务 → 「计划」页完成数 +1、「待办统计」页当日柱状图 +1、猫的累计数 +1
- [ ] 创建一个每天的习惯 → 「今日」页习惯区块出现 → 打卡 → 「习惯」页 streak 变化
- [ ] 把习惯关联到计划 → 「计划」页关联习惯数 +1
- [ ] 写一份本周回顾并标记完成 → 「回顾总结」历史列表出现该条

- [ ] **Step 3: 异常路径走查**

- [ ] 后端停掉 → 页面给出网络错误提示，不白屏、不卡死
- [ ] 后端重新启动 → 页面下拉刷新能恢复
- [ ] 手动把 Storage 里的 `auth_token` 改成乱码 → 下一个请求触发静默重登，页面正常（Network 面板可见 401 → wx_login → 重放）
- [ ] 把某个任务在数据库里直接删掉 → 小程序点进它的详情页时给出「不存在」提示，不是白屏

- [ ] **Step 4: 修复发现的问题并提交**

```bash
git add weapp/
git commit -m "fix(weapp): 全量回归发现的问题修复"
```

---

### Task 11: 删除云开发遗留

**Files:**
- Delete: `weapp/cloudfunctions/`、`weapp/miniprogram/services/cloud.js`、`weapp/miniprogram/envList.js`、`weapp/uploadCloudFunction.sh`
- Modify: `weapp/miniprogram/utils/date.js`、`weapp/project.config.json`、`CLAUDE.md`、`docs/miniprogram-todo-design.md`
- Test: 编译通过 + 抽查三个页面

**只在 Task 10 全量回归通过后做。** 删早了出问题就没有对照物了。

- [ ] **Step 1: 确认没有残留引用**

```bash
cd weapp && grep -rn "wx.cloud\|callFunction\|require('./cloud')\|require('../services/cloud')\|envList" miniprogram/
```

Expected: 无输出。有输出就先改掉那些引用，不要往下走。

- [ ] **Step 2: 删除文件**

```bash
cd weapp
git rm -r cloudfunctions
git rm miniprogram/services/cloud.js miniprogram/envList.js uploadCloudFunction.sh
```

- [ ] **Step 3: 清理 `project.config.json`**

打开 `weapp/project.config.json`，删掉 `cloudfunctionRoot` 配置项（若存在）。`weapp/project.private.config.json` 里若也有，一并删。

- [ ] **Step 4: 清理 `utils/date.js` 的死代码**

```bash
cd weapp/miniprogram
grep -rn "startOfDay\|endOfDay\|nowMs" pages/ services/ utils/
```

只被 `date.js` 自己引用、没有任何外部调用点的导出函数，从 `module.exports` 里移除并删除实现。**`calcPeriodRange` / `toDateStr` / `parseDateStr` / `todayStr` 大概率仍在页面里用于展示，不要误删**——以 grep 结果为准。

同时更新 `date.js` 顶部的文件注释：原文写的是「云函数只做数值范围过滤」，现在应改为说明日期边界的新约定（纯日期传 `YYYY-MM-DD`，后端按 `Asia/Shanghai` 推算边界）。

- [ ] **Step 5: 重新编译并抽查**

Expected: 编译无报错，「今日」「任务」「猫窝」三个页面正常。

- [ ] **Step 6: 更新文档**

**`CLAUDE.md`**：小程序相关章节改写——数据层不再是云开发，改为「小程序通过 `services/http.js` 调用 FastAPI 的 `/api/v1`，登录走 `POST /base/wx_login` 换 JWT，与 Web 端共用同一份数据与同一套用户体系」。

**`docs/miniprogram-todo-design.md`**：在文件顶部加一行醒目标注：

```markdown
> ⚠️ **已废弃（2026-08）**：本文描述的微信云开发方案已被 FastAPI 后端取代。
> 保留作历史参考。当前方案见 `docs/superpowers/specs/2026-08-26-miniprogram-fastapi-migration-design.md`。
```

- [ ] **Step 7: 提交**

```bash
git add -A weapp/ CLAUDE.md docs/miniprogram-todo-design.md
git commit -m "chore(weapp): 删除云开发遗留代码并更新文档"
```

---

## 阶段验收

- [ ] `grep -rn "wx.cloud\|callFunction" weapp/` 无输出
- [ ] `weapp/cloudfunctions/` 目录已不存在
- [ ] 10 个页面全部功能正常（Task 10 走查表全部打勾）
- [ ] `weapp/miniprogram/utils/cat.js` 相对切换前**零改动**
- [ ] 「今日」「四象限」「习惯」三个页面渲染猫时零 pet 请求
- [ ] 「习惯」「计划」「任务」「统计」四个页面的首屏各只发一个聚合请求
- [ ] 冷启动路径（清缓存 → 首次登录 → 自动建号）跑通
- [ ] 401 静默重登跑通，且并发时只登录一次
- [ ] `CLAUDE.md` 与 `docs/miniprogram-todo-design.md` 已更新

达成后，阶段三（数据迁移）可以开工。

---

## 遗留给阶段三

- **数据迁移**：本阶段跑在空库/新数据上。云数据库里的历史数据由阶段三的迁移脚本导入，届时需要重新验证一遍列表类页面（数据量变大后的分页、排序）。
- **部署**：域名备案完成后，把 `weapp/miniprogram/config.js` 的 `PROD` 改成真实域名，并在小程序后台配置 request 合法域名。
