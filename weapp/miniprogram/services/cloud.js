/**
 * 云函数统一调用封装：返回 Promise<data>
 * 约定：云函数返回 { code: 0, data } 为成功，否则 reject
 * 注意：wx.cloud.callFunction 的 data 里不能含 undefined，
 * 否则会抛 "undefined" is not valid JSON，这里递归剔除所有 undefined 值。
 */
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

function call(name, data = {}) {
  return wx.cloud.callFunction({ name, data: stripUndefined(data) }).then((res) => {
    const r = res.result;
    if (r && r.code === 0) return r.data;
    const err = new Error((r && r.message) || '请求失败');
    err.result = r;
    return Promise.reject(err);
  });
}

module.exports = { call };
