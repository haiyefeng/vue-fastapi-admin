# 小程序从微信云开发迁移到 FastAPI 后端 · 改造蓝图

> 状态：设计稿，待逐节评审
> 日期：2026-08-26
> 范围：`weapp/`（小程序）、`app/`（FastAPI 后端）

---

## 1. 背景与现状

小程序 `weapp/` 目前完全跑在微信云开发上：云数据库（NoSQL）+ 8 个云函数，数据按 `_openid` 隔离。
后端 `app/` 是 FastAPI + Tortoise ORM，已经存在与云函数**高度对等**的业务模块。

### 1.1 现状盘点

**小程序侧**

- 10 个页面：`today / tasks / quadrant / calendar / goals / habits / review / stats / pet / task-detail`
- 数据层已充分收敛：所有页面只调 `services/*.js`（8 个文件，共 99 行），底层统一走 `services/cloud.js` 的 `call(name, data)`（29 行）
- `utils/cat.js`（133 行）实现养成猫的本地缓存 + 台词规则求值，**热页面渲染猫零网络请求**
- `utils/date.js`（99 行）负责本地时区的日期边界计算

**云函数侧**（`weapp/cloudfunctions/`，共 1693 行）

| 云函数 | 行数 | actions |
|---|---|---|
| todo | 387 | list / create / get / update / remove / subtask{List,Create,Update,Remove} / timeblock{List,Create,Remove} / statisticsDaily / statisticsQuadrant / statsBootstrap |
| habit | 321 | list / bootstrap / archived / create / update / remove / summary |
| pet | 182 | bootstrap / update / seed |
| review | 162 | dataSummary / bootstrap / detail / save / list |
| goal | 148 | list / bootstrap / archived / detail / create / update / remove |
| project | 116 | listCategories / list / bootstrap / create / update / remove |
| dashboard | 64 | today |
| quickstartFunctions | 185 | 模板遗留，未使用 |

云数据库集合：`todos / subtasks / time_blocks / habits / goals / projects / categories / reviews / pet / cats / cat_lines`

**后端侧**

已有路由组：`todo / subtask / timeblock / category / habit / goal / project / review / dashboard`（外加 RBAC 的 user/role/menu/api/dept/auditlog）。
模型定义在 `app/models/todo.py`：`TodoItem / Category / Project / SubTask / TimeBlock / Habit / Goal` 等。

### 1.2 差距清单

云函数 action 与 FastAPI 路由**几乎一一对应**，命名差异是表层的（`remove`↔`delete`、`dataSummary`↔`data-summary`）。真正的缺口只有六类：

| # | 缺口 | 影响面 |
|---|---|---|
| G1 | 后端**没有任何微信登录**（无 openid、无 code2session） | 阻塞性 |
| G2 | 后端**没有 pet 模块**（模型、路由、配置数据全无） | 阻塞性 |
| G3 | 后端缺 `bootstrap` 类聚合端点（habit / goal / project / todo.statsBootstrap） | 请求数退化 |
| G4 | 后端缺 `habit/summary`、`project/listCategories`（后者可用已有 `category/list` 顶替） | 功能缺失 |
| G5 | 参数约定不同：小程序传毫秒时间戳 + `YYYY-MM-DD`（`today_start_ms` / `start_str`），后端用 ISO datetime | 全量接口 |
| G6 | 响应壳不同（`{code:0,data}` vs `{code:200,msg,data}`）；ID 从字符串 `_id` 变 int | 全量接口 |

---

## 2. 目标与非目标

### 2.1 目标

1. 小程序全部数据请求改为走 FastAPI HTTP 接口，最终删除 `cloudfunctions/` 目录
2. 小程序与 Web 端**共用同一份数据、同一套 API、同一个用户体系**
3. 微信一键登录，复用现有 JWT 认证
4. 现有云数据库数据完整迁移到后端数据库
5. 迁移后小程序功能不缺失（含 pet），页面请求数不退化

### 2.2 非目标

- **不做宠物养成系统的重做**（成就 / 好感度 / 小鱼干喂食）。本期 pet 只做**能力平移**，养成系统作为主线之后的**独立一期**，设计已定稿见附录 A
- 不做域名备案与生产部署。开发期用开发者工具「不校验合法域名」直连本机，部署在改造完成后单独处理
- 不重构 Web 前端
- 不做微信支付、订阅消息、分享等新的小程序能力

### 2.3 已确认的决策

| 议题 | 决策 |
|---|---|
| 登录方式 | 微信 `code2session` 换取现有 JWT（方案 A） |
| 数据迁移 | 要做，但排在**最后一个阶段**，等模型稳定后再写映射 |
| pet 后端 | 补齐，本期只平移现有能力 |
| 养成系统 | 独立一期，主线之后 |
| 接口对齐策略 | 方案 C：小程序走标准 REST，后端**新增**聚合端点；**永远只维护一套 API** |
| 部署 | 后置，不阻塞改造 |

### 2.4 被否决的方案

- **方案 B（后端加 `/api/v1/mp/*` BFF 层）**：小程序侧改动最小，但后端从此背两套 API，每次改业务要同步两处。省下的前端工作量不值得换长期双维护负担。
- **方案 A（小程序单方面适配，bootstrap 用 `Promise.all` 拆开）**：后端零改动，但页面请求数从 1 个涨到 2-3 个。而聚合端点对 Web 端首屏同样有价值，不算适配层。

---

## 3. 总体架构

```
┌──────────────────────────────────────────────┐
│              小程序（客户端）                  │
│  pages/  ← 不动                               │
│  services/*.js  ← 重写，对齐 REST             │
│  services/http.js  ← 新增，替代 cloud.js      │
│  utils/cat.js  ← 保留本地缓存策略             │
└────────────────┬─────────────────────────────┘
                 │ HTTPS + token 头
┌────────────────▼─────────────────────────────┐
│           FastAPI  /api/v1                    │
│  base/wx_login  ← 新增（公开）                 │
│  todo subtask timeblock category              │
│  habit goal project review dashboard  ← 补聚合 │
│  pet  ← 新增                                   │
│  除 base 外全部 dependencies=[DependPermission]│
└────────────────┬─────────────────────────────┘
                 │ Tortoise ORM
┌────────────────▼─────────────────────────────┐
│         SQLite / MySQL（与 Web 端同库）        │
└──────────────────────────────────────────────┘
```

---

## 4. 第 1 节 · 微信登录与用户体系

### 4.1 现有约束

- `User.email` 是 **unique 且非空**
- `User.username` **max_length=20**，而 openid 是 28 位，塞不进去
- `User.password` 已经是 `null=True`，微信用户无需伪造密码
- JWT 有效期 `JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60*24*7`（7 天）

### 4.2 模型改动

`app/models/admin.py` 的 `User` 新增：

```python
openid = fields.CharField(max_length=64, unique=True, null=True, description="微信 openid", index=True)
```

`unique + null=True` 让 Web 端已有用户保持 `openid=None`，互不干扰。
不加 `unionid`——只有一个小程序，用不上跨应用打通，需要时再加。

### 4.3 新端点 `POST /api/v1/base/wx_login`

挂在 `base_router` 下（`base` 是唯一不带 `DependPermission` 的路由组，登录接口必须公开）。

流程：

1. 收 `{code}` → 请求 `https://api.weixin.qq.com/sns/jscode2session`
   - `appid` / `secret` 从 `settings` 读，走**环境变量，不进代码**
2. 拿到 `openid` → `User.get_or_none(openid=...)`
3. 不存在则自动建号：
   - `username = f"wx_{openid[-16:]}"`（19 字符，卡在 20 上限内）
   - `email = f"{openid}@wx.local"`（占位，满足 unique 非空约束）
   - `password = None`、`is_active=True`、`is_superuser=False`
   - 分配「小程序用户」角色（见第 8 节）
4. 签发**与 Web 端完全同一套 JWT**（`create_access_token` + 现有 `JWTPayload`），有效期沿用 7 天
5. 返回 `Success(data={access_token, username, is_new})`

**关键判断：复用现有 JWT 体系，不为小程序另起一套。**
这样 `AuthControl.is_authed` 一行都不用改，`CTX_USER_ID` 照常工作，所有业务 controller 的 `user_id` 过滤天然生效。

### 4.4 小程序侧登录流程

- `wx.login()` 拿 code → `POST /base/wx_login` → token 存 Storage
- **不主动判断过期，靠 401 触发静默重登**：拦截器收到 401 就重跑 `wx.login` + `wx_login`，然后重放原请求
- 重登必须**加并发锁**：多个请求同时 401 时只发起一次登录，其余排队等结果。这是本节最容易写出 bug 的地方

### 4.5 昵称头像

不放进登录流程。微信已收紧 `getUserInfo`，现在需要 `<button open-type="chooseAvatar">` 由用户主动授权，属于独立的「完善资料」动作。
首次登录先用默认头像 + `username`，不阻塞主流程。后续走 `POST /base/update_userinfo`。

### 4.6 开发期连调

`AuthControl.is_authed` 现有的 `token == "dev"` 后门照常可用；开发者工具勾选「不校验合法域名」即可直连 `http://localhost:9999`。
**登录与业务改造可以完全并行推进，不被部署卡住。**

---

## 5. 第 2 节 · 传输层 `services/http.js`

新增 `weapp/miniprogram/services/http.js`，替代 `services/cloud.js`，职责：

1. **基址与方法**：`request(method, path, data)`，基址从 `envList.js` 之外的新配置文件读（区分开发/生产）
2. **token 注入**：请求头 `token: <jwt>`（后端 `AuthControl` 读的就是 `token` 头，不是 `Authorization`）
3. **响应解包**：`{code:200,msg,data}` → `data`；`code !== 200` → `reject(new Error(msg))`
4. **401 静默重登 + 请求重放**，带并发锁（见 4.4）
5. **保留 `stripUndefined`**：GET 查询串里 `undefined` 同样是脏数据，逻辑从 `cloud.js` 原样搬过来
6. **统一错误提示**：网络失败 / 5xx 统一 `wx.showToast`，业务错误交给调用方

`services/cloud.js` 在最后一个模块切完后删除。

---

## 6. 第 3 节 · 接口与参数约定

### 6.1 日期与时区（G5）

现状：时区边界在客户端算，传毫秒时间戳（`today_start_ms` / `today_end_ms` / `start_ms`）+ `YYYY-MM-DD` 字符串（`today_str` / `start_str`）。

**改造后统一为：**

- **纯日期字段**（`due_date` 的日期部分、统计的日期分组）→ `YYYY-MM-DD` 字符串，与现状一致
- **时间点字段**（`completed_at` / `reminder_at` / 时间块起止）→ **ISO 8601 带时区偏移**字符串
- **日期范围** → 客户端仍在本地时区算好边界，但转成 ISO 字符串传，不再传毫秒数
- 客户端计算边界的逻辑保留在 `utils/date.js`，只改输出格式

理由：后端字段是 `DatetimeField`，ISO 是 Tortoise/Pydantic 的原生格式，避免两侧各写一套时间戳转换。

### 6.2 ID 类型（G6）

字符串 `_id` → 整数主键。影响面：

- `services/*.js` 全部参数
- 页面 `data` 里缓存的 id、`wx.navigateTo` 的 URL 参数（`?id=xxx`）需要 `Number()` 转换
- **本地 Storage 里缓存的旧数据必须清空**，否则新旧 id 混用会出现诡异的「找不到任务」

### 6.3 响应壳（G6）

由 `http.js` 统一吸收，`services/*.js` 和页面都感知不到差异。

### 6.4 命名对齐

小程序侧**服务函数名保持不变**（`remove` / `dataSummary` …），只改内部实现指向的 URL。
这样页面代码零改动，是本次改造范围可控的关键。

---

## 7. 第 4 节 · 后端补齐

### 7.1 聚合端点（G3）

新增 4 个薄聚合端点，实现就是并发调已有 controller 方法再拼装：

| 端点 | 等价于 | 云函数参考 |
|---|---|---|
| `GET /api/v1/habit/bootstrap` | `list` + `archived` | `habit/index.js:180`（6 行） |
| `GET /api/v1/goal/bootstrap` | `list` + `archived` | goal 云函数 |
| `GET /api/v1/project/bootstrap` | `list` + `category/list` | project 云函数 |
| `GET /api/v1/todo/stats-bootstrap` | `statistics/daily` + `statistics/quadrant` + 已完成列表 | todo 云函数 |

这些聚合对 Web 端首屏同样有价值，属于**真实能力补齐，不是小程序适配层**。

### 7.2 缺失端点（G4）

- `GET /api/v1/habit/summary`——对照 `habit` 云函数的 `summary` action 实现
- `project/listCategories` 用已有 `GET /api/v1/category/list` 顶替，小程序侧改调用即可

### 7.3 差异校对

逐个云函数与对应 controller 做**行为差异校对**，重点：

- 分页参数（云函数 `page/pageSize`，上限 200）
- 排序白名单与默认排序方向（todo 云函数对 `created_at`/`completed_at` 默认倒序，其余正序）
- 可空关联字段语义：云函数用「不写入字段」表示空，用 `_.exists(false)` 查询；关系库里就是 `NULL`，需确认 controller 的筛选逻辑等价（如 `inbox_only` = `project_id IS NULL`）
- 习惯的惰性生成逻辑（云函数在 list 时按频率补生成待办）是否已在后端 controller 中实现

**这一步是本期最大的隐藏工作量**，不能假设「路由名对上了行为就一致」。

---

## 8. 第 5 节 · 权限（RBAC）

**这是最容易漏的坑**：后端除 `base` 外所有路由都挂了 `dependencies=[DependPermission]`，小程序用户若非超管，必须有角色被授权了这些 API，否则**全部 403**。

改造内容：

1. `init_roles()` 中新增「小程序用户」角色，授权范围 = 待办事项相关的全部 API（todo / subtask / timeblock / category / habit / goal / project / review / dashboard / pet），**不含** RBAC 管理类 API
2. `wx_login` 自动建号时分配该角色
3. 新增路由（`wx_login` 除外，它是公开的）后需跑 `refresh_api()`——应用启动会自动跑，也可从后台「刷新 API」触发
4. 新增的 pet / bootstrap 端点要记得加进该角色的授权列表

---

## 9. 第 6 节 · pet 模块平移（G2）

本期**只平移现有能力**，不做养成系统重做。

### 9.1 模型（`app/models/pet.py`）

对照云函数现有结构，最小化关系型建模：

| 表 | 字段 |
|---|---|
| `pet_profile` | `user`(1:1) / `active_cat_code` / `pet_name` / `stats`(JSON) / `owned_cats`(JSON) / `visit_streak` / `last_seen_at` |
| `pet_cat` | `code`(unique) / `name` / `persona` / `order` / `unlock`(JSON) |
| `pet_line` | `code`(unique) / `cat_code`(可空=通用) / `page` / `priority` / `conditions`(JSON) / `texts`(JSON) / `unlock`(JSON) |

`stats` / `owned_cats` 用 JSON 而非独立表：这些数据**只按 user 单行读写，从不跨用户查询**，拆表换不来查询能力。
`unlock` / `conditions` 用 JSON 存声明式规则数组——规则型配置在关系库里本就该这么存。

### 9.2 路由 `/api/v1/pet`

- `GET /bootstrap`：参数 `config_version`、`touch`；返回 `{pet, total, newly_unlocked, config_version, config?}`
- `POST /update`：`active_cat_id` / `pet_name`

### 9.3 必须保留的性能设计

现状小程序热页面（今日/四象限/习惯）渲染猫是**完全走本地 Storage、零网络请求**的，靠 `config_version` 命中缓存（`utils/cat.js`）。
**换到 HTTP 后这套机制必须原样保留**：`config_version` = 配置表 `max(updated_at)` 的时间戳，版本一致则不回传 `config` 体。

### 9.4 配置数据初始化

`seed.js` 里的 3 只猫 + 13 组台词翻译成后端的初始化数据，随 `init_data()` 幂等写入（按 `code` upsert）。

### 9.5 计数累加

`todo` 云函数在标记完成时会 `stats.todo_completed +1`（`todo/index.js:343`）。
后端对应到 `todo` controller 的完成动作里，用 `select_for_update()` 读改写 JSON 计数。
注意：`STAT_FIELDS` 声明了 4 个维度，但**实际只有 `todo_completed` 在被累加**，另外三个一直是 0——本期保持现状，不补，留给养成系统那一期。

---

## 10. 第 7 节 · 数据迁移

**排在最后**，等模型稳定后再写，避免返工。

### 10.1 导出

写一个一次性云函数（或用云开发控制台的导出功能），把 11 个集合全量导出为 JSON。

### 10.2 导入脚本

后端侧一次性脚本，核心是 **ID 重映射**：

1. 建立 `openid → user_id` 映射（单用户场景就一条）
2. 按**依赖顺序**导入：`categories → projects → goals → habits → todos → subtasks → time_blocks → reviews → pet`
3. 每导一层，维护 `旧字符串_id → 新int主键` 的映射表，供下一层的外键引用翻译
4. 字段类型转换：毫秒时间戳 → `datetime`；`YYYY-MM-DD` 字符串 → `date`；缺失字段 → `NULL`
5. **幂等**：脚本可重复执行，已导入的跳过（用一张临时映射表或在目标表加一个 `legacy_id` 字段，导完可删）

### 10.3 校验

导入后逐表比对行数，并抽查跨表引用（如任务的项目归属、时间块的任务归属）是否正确。

---

## 11. 第 8 节 · 收尾

1. 删除 `weapp/cloudfunctions/` 整个目录（含未使用的 `quickstartFunctions`）
2. `app.js` 去掉 `wx.cloud.init`，移除 `envList.js`
3. 删除 `services/cloud.js`
4. `uploadCloudFunction.sh` 删除
5. 更新 `CLAUDE.md` 的小程序章节与 `docs/miniprogram-todo-design.md`（后者标注为「已废弃，历史参考」）
6. 小程序端**清空本地 Storage**（id 类型已变，见 6.2）

---

## 12. 实施阶段

| 阶段 | 内容 | 可独立验证 |
|---|---|---|
| P1 | 微信登录：`User.openid`、`wx_login`、「小程序用户」角色、小程序 token 流程 | 能登录，`/base/userinfo` 返回正确用户 |
| P2 | 传输层：`services/http.js`（含 401 重登并发锁） | 单元验证 + 一个模块试点 |
| P3 | 后端补齐：4 个 bootstrap + `habit/summary` + **逐云函数行为差异校对** | 后端测试 |
| P4 | pet 模块后端 + 配置初始化 | pet 页面功能对齐 |
| P5 | 8 个 `services/*.js` 重写切换，逐模块灰度 | 逐页面回归 |
| P6 | 数据迁移脚本 + 校验 | 行数与引用比对 |
| P7 | 收尾清理 + 部署（域名备案后） | 全量回归 |

P1/P2 可并行；P3 是最大的不确定项（见 7.3）。

---

## 13. 风险

| 风险 | 应对 |
|---|---|
| **行为差异**：路由名对上但业务逻辑不等价（分页、排序、空值语义、习惯惰性生成） | P3 逐云函数校对，不靠假设；这是最大工作量来源 |
| **401 重登并发** 写错导致重复登录或请求丢失 | 单独实现 + 针对性验证 |
| **ID 类型变更**导致旧 Storage 数据污染 | 切换时强制清空 Storage，加一个 storage schema version |
| **RBAC 403** 全量接口不可用 | P1 就把角色授权做完并验证 |
| **域名备案**卡住上线 | 开发期用「不校验合法域名」，改造不被阻塞；备案与改造并行推进 |
| 迁移脚本跨表引用错乱 | 幂等 + 依赖顺序导入 + 导入后校验 |

---

## 附录 A · 宠物养成系统（独立一期，设计已定稿）

**不在本期范围内**，此处记录已达成的设计共识，供后续单独立项。

### A.1 机制

- 猫是陪伴用户坚持习惯、完成任务、达成目标的伙伴
- 猫可切换、可关闭陪伴；不同的猫有不同性格与专属语句
- 猫种：橘猫 / 奶牛 / 狸花 / 美短 / 布偶 / 缅因，解锁门槛逐级递增。**没有皮肤这一层**，猫本身就是唯一的收集单位
- 完成事情 → 瓶子里掉一条**小鱼干**（带来源，如「完成了：写周报」）→ 用户点击喂猫 → 转成**好感度**
- 支持一键全喂；**不喂不亏**，鱼干永久留在瓶子里等你

### A.2 三条设计支点（已确认）

1. **只有好感度一根轴**：`intimacy_total` 决定解锁，`intimacy` 决定展示。鱼干是积分的载体，不是第二种货币
2. **成就是唯一解锁钥匙**：猫和语句都挂在成就上解锁；「累计好感度 500」本身就是一个成就。加内容不用改代码
3. **只增不减**：好感度、成就、解锁不可逆

### A.3 防刷分规则（关键）

1. **一个来源只发一次鱼干**——`pet_fish` 唯一索引 `(user, source_type, source_id)` 兜底
2. **鱼干不回收**——取消完成不影响已发放的
3. 因此 `pet_fish` **喂食后不能删行**，用 `consumed_at` 标记；否则会丢失幂等记录，反复勾选可无限刷鱼
4. 计数按「曾经完成过的不同任务数」语义，而非「完成动作次数」

副产物：`pet_fish` 顺带成为**喂养历史**（「你和橘猫一起完成过 137 件事」），是这套机制最有情感价值的部分。

### A.4 表设计（5 张：配置 3 + 用户 2）

**配置表**（全用户共享、只读、可后台编辑）

| 表 | 关键字段 |
|---|---|
| `pet_cat` | `code`(unique) / `name` / `persona` / `order` / `unlock_achievement`(FK,可空=初始猫) / `is_active` |
| `pet_line` | `code` / `cat`(FK,可空=通用兜底) / `page` / `priority` / `conditions`(JSON) / `texts`(JSON) / `unlock_achievement`(FK,可空) |
| `pet_achievement` | `code` / `name` / `description` / `icon` / `conditions`(JSON) / `reward_intimacy` / `order` |

**用户数据表**

| 表 | 关键字段 |
|---|---|
| `pet_profile` | `user`(1:1) / `is_enabled` / `active_cat_code` / `pet_name` / `intimacy` / `intimacy_total` / `pending_fish` / `counters`(JSON) / `owned_cats`(JSON) / `achievements`(JSON) / `visit_streak` / `last_seen_at` |
| `pet_fish` | `user` / `source_type` / `source_id` / `source_title` / `created_at` / `consumed_at`(空=在瓶子里)；唯一索引 `(user, source_type, source_id)` |

用户侧接受适当冗余（原设计 5 张压缩为 2 张），代价明确：

1. 失去跨用户统计（「哪只猫最受欢迎」「成就达成率」）——单用户自用场景不值得为此保留三张表
2. 计数不能用 `F()` 原子自增，`counters` 是 JSON 需读-改-写——**必须套 `select_for_update()`**，否则同时完成两个任务会丢计数

### A.5 实现要点

1. **单一事件入口**：各 controller 的完成动作统一调 `PetService.on_event(user, type, ref)`，它负责计数 +1、插鱼干、重算成就。加事件类型只加一个 case
2. **成就重算只在 `on_event` 和喂食后跑**，不在 bootstrap 里跑
3. **保留零请求缓存策略**（见 9.3），新增的鱼干数在本地乐观累加
4. 内容铺法：**通用兜底 + 逐只猫加料**——先把通用语句写全保证任何猫任何页面都有话说，再给每只猫写最有辨识度的几个场景。不必一开始填满 6 猫 × 6 页面的矩阵
5. `unlock_achievement` 可以不只是数值门槛，比如缅因猫挂在「连续 30 天有打卡」上，比纯数字更有故事
