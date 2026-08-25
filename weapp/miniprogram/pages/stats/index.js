const todoApi = require('../../services/todo');
const { quadrantMeta, QUADRANT_KEYS } = require('../../utils/quadrant');
const { toDateStr, startOfDay, endOfDay, parseDateStr, formatDateTime } = require('../../utils/date');

Page({
  data: {
    startStr: '', endStr: '',
    series: [],        // [{label, count, height}]
    maxCount: 0,
    quadrants: [],     // [{key,label,color,count}]
    maxCount2: 0,
    completed: [],
    loading: false,
  },

  onLoad() {
    const end = new Date();
    const start = new Date(end.getFullYear(), end.getMonth(), end.getDate() - 6);
    this.setData({ startStr: toDateStr(start.getTime()), endStr: toDateStr(end.getTime()) });
  },
  onShow() { this.load(); },

  onPickStart(e) { this.setData({ startStr: e.detail.value }); this.load(); },
  onPickEnd(e) { this.setData({ endStr: e.detail.value }); this.load(); },

  async load() {
    this.setData({ loading: true });
    const sMs = startOfDay(parseDateStr(this.data.startStr) || Date.now());
    const eMs = endOfDay(parseDateStr(this.data.endStr) || Date.now());
    try {
      const boot = await todoApi.statsBootstrap({
        start_ms: sMs, end_ms: eMs,
        is_completed: true, completed_start: sMs, completed_end: eMs,
        sort_by: 'completed_at', sort_order: 'desc', pageSize: 100,
      });
      const quadRes = boot.quadrant || {};
      const listRes = boot.completed || {};
      // 按日分组
      const byDate = {};
      for (const t of (boot.daily || [])) {
        const ds = toDateStr(t.completed_at);
        byDate[ds] = (byDate[ds] || 0) + 1;
      }
      const series = [];
      let maxCount = 0;
      for (let ms = sMs; ms <= eMs; ms += 86400000) {
        const ds = toDateStr(ms);
        const count = byDate[ds] || 0;
        if (count > maxCount) maxCount = count;
        series.push({ label: ds.slice(5), count });
      }
      const quadrants = QUADRANT_KEYS.map((k) => {
        const m = quadrantMeta(k);
        return { key: k, label: m.label, color: m.color, count: quadRes[k] || 0 };
      });
      const maxCount2 = Math.max(0, ...quadrants.map((q) => q.count));
      const completed = (listRes.list || []).map((t) => Object.assign({}, t, {
        quadrant_label: quadrantMeta(t.quadrant_type).label,
        completed_text: t.completed_at ? formatDateTime(t.completed_at) : '',
      }));
      this.setData({ series, maxCount, quadrants, maxCount2, completed, loading: false });
    } catch (e) {
      this.setData({ loading: false });
      wx.showToast({ title: e.message || '加载失败', icon: 'none' });
    }
  },
});
