const todoApi = require('../../services/todo');
const { weekRange, startOfDay, endOfDay, toDateStr, todayStr, formatTime } = require('../../utils/date');
const { quadrantMeta } = require('../../utils/quadrant');

const pad = (n) => String(n).padStart(2, '0');
const HOUR_PX = 96; // 每小时格子高度（px），日程块按时长比例定位
/**
 * 可选粒度。不开放更细的档位是因为格子高度 = hourPx * gran / 60，
 * 15 分钟档已经只有约 30px，再细就低于可靠的触摸目标尺寸、点不准了。
 * 15 分钟档同时把每小时高度放大，以换回可点性（代价是时间轴更长）。
 */
const GRAN_OPTIONS = [
  { value: 60, label: '1小时', hourPx: HOUR_PX },
  { value: 30, label: '30分', hourPx: HOUR_PX },
  { value: 15, label: '15分', hourPx: 120 },
];
const DEFAULT_GRAN = 30;

const granConf = (gran) => GRAN_OPTIONS.find((o) => o.value === gran) || GRAN_OPTIONS[1];

const fmtMin = (m) => pad(Math.floor(m / 60)) + ':' + pad(m % 60);

// 由已选区间生成格子渲染数据（sel 命中区间，anchor 是「已点起点、等待终点」的那一格）
function buildSlots(ranges, anchor, gran, hourPx) {
  const slotPx = hourPx * gran / 60;
  const count = 24 * 60 / gran;
  const out = [];
  for (let i = 0; i < count; i++) {
    const min = i * gran;
    out.push({
      min,
      top: i * slotPx,
      sel: ranges.some((r) => min >= r.start && min < r.end),
      anchor: anchor === min,
    });
  }
  return out;
}

// 合并重叠/相邻区间，并按开始时间排序
function mergeRanges(ranges) {
  const sorted = ranges.slice().sort((a, b) => a.start - b.start);
  const out = [];
  for (const r of sorted) {
    const last = out[out.length - 1];
    if (last && r.start <= last.end) last.end = Math.max(last.end, r.end);
    else out.push({ start: r.start, end: r.end });
  }
  return out;
}

Page({
  data: {
    anchorMs: Date.now(),
    weekDays: [],       // [{date, dateStr, dayLabel, isToday}]
    selectedStr: '',
    hours: Array.from({ length: 24 }, (_, i) => pad(i) + ':00'),
    hourPx: HOUR_PX,
    timelineHeight: 24 * HOUR_PX,
    blocks: [],          // 选中日的日程（已按时间比例定位好 top/height）
    nowTop: -1,           // 当前时间线的 top，不在当天时为 -1（不渲染）
    unscheduledTodos: [],
    scrollTop: 0,
    // ---- 选择时段（点选起点 + 终点，可选多段）----
    selMode: false,
    slots: [],            // 选择态下的格子（buildSlots 产物）
    granOptions: GRAN_OPTIONS,
    gran: DEFAULT_GRAN,
    slotPx: HOUR_PX * DEFAULT_GRAN / 60,
    selRanges: [],        // [{start, end}]（分钟）
    selAnchor: null,      // 已点起点、等待终点时为该格分钟数
    selSummary: '',
    showAdd: false,
    scheduling: null,     // 非空时表示「给已有任务排程」，为空时表示「新建任务+日程」
    form: { title: '', date: '', start: '', end: '' },
    formRanges: [],       // 多时段模式下待创建的区间（含展示文案）
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },

  async load() {
    const r = weekRange(this.data.anchorMs);
    const sel = this.data.selectedStr || todayStr();
    const weekDays = [];
    for (let i = 0; i < 7; i++) {
      const ms = r.start + i * 86400000;
      const ds = toDateStr(ms);
      const d = new Date(ms);
      weekDays.push({ date: ds, dateStr: pad(d.getMonth() + 1) + '/' + pad(d.getDate()), dayLabel: ['日', '一', '二', '三', '四', '五', '六'][d.getDay()], isToday: ds === todayStr() });
    }
    this.setData({ weekDays, selectedStr: sel });
    await Promise.all([this.loadBlocks(), this.loadUnscheduled()]);
  },

  async loadBlocks() {
    const ds = this.data.selectedStr;
    const p = ds.split('-').map(Number);
    const start = new Date(p[0], p[1] - 1, p[2]).getTime();
    const end = endOfDay(start);
    try {
      const res = await todoApi.timeblockList({ start_ms: start, end_ms: end });
      // 只保留与每小时高度无关的原始分钟数，具体像素位置由 layout() 按当前 hourPx 换算，
      // 这样切换粒度（会改变 hourPx）时无需重新请求即可重排
      this.rawBlocks = (res.list || []).map((b) => {
        const s = new Date(b.start_time), e = new Date(b.end_time);
        return Object.assign({}, b, {
          startMin: s.getHours() * 60 + s.getMinutes(),
          endMin: e.getHours() * 60 + e.getMinutes(),
          start_text: formatTime(b.start_time), end_text: formatTime(b.end_time),
          color: quadrantMeta(b.quadrant_type).color,
        });
      });
      this.isToday = ds === todayStr();
      const { blocks, nowTop } = this.layout();
      this.scrollToFocus(nowTop, blocks);
    } catch (e) { wx.showToast({ title: e.message || '加载失败', icon: 'none' }); }
  },

  async loadUnscheduled() {
    try {
      const res = await todoApi.list({ unscheduled_only: true, pageSize: 200, sort_by: 'due_date', sort_order: 'asc' });
      const list = (res.list || []).map((t) => Object.assign({}, t, { color: quadrantMeta(t.quadrant_type).color }));
      this.setData({ unscheduledTodos: list });
    } catch (e) { /* 未排程列表加载失败不打断日历主体展示 */ }
  },

  /**
   * 按当前 hourPx 把原始分钟数换算成像素位置，并写回 blocks / nowTop / timelineHeight。
   * 加载数据和切换粒度都走这里，保证两者用的是同一套换算逻辑。
   */
  layout() {
    const hourPx = granConf(this.data.gran).hourPx;
    const blocks = (this.rawBlocks || []).map((b) => Object.assign({}, b, {
      top: Math.round((b.startMin / 60) * hourPx),
      height: Math.max(36, Math.round(((b.endMin - b.startMin) / 60) * hourPx) - 2),
    }));
    const now = new Date();
    const nowTop = this.isToday ? Math.round(((now.getHours() * 60 + now.getMinutes()) / 60) * hourPx) : -1;
    this.setData({
      blocks, nowTop, hourPx,
      timelineHeight: 24 * hourPx,
      slotPx: hourPx * this.data.gran / 60,
    });
    return { blocks, nowTop, hourPx };
  },

  /**
   * 时间轴自动定位：今天滚到当前时间，其他日期滚到当天第一个日程，都没有则 8:00。
   * 目标位置留出约三分之一屏的上方余量，使焦点落在偏上位置、能看到接下来的安排。
   */
  scrollToFocus(nowTop, blocks) {
    const hourPx = granConf(this.data.gran).hourPx;
    let target;
    if (nowTop >= 0) target = nowTop;
    else if (blocks && blocks.length) target = blocks[0].top;
    else target = 8 * hourPx;

    let viewH = 360; // 兜底值：.timeline-scroll 高 720rpx，约当 360px
    try {
      const info = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
      if (info && info.windowWidth) viewH = (720 / 750) * info.windowWidth;
    } catch (e) { /* 取不到就用兜底值 */ }

    const maxTop = Math.max(0, 24 * hourPx - viewH);
    const scrollTop = Math.min(maxTop, Math.max(0, Math.round(target - viewH / 3)));
    // scroll-top 值不变时不会触发滚动，先归零再设目标值以保证每次进页面都重新定位
    this.setData({ scrollTop: 0 }, () => this.setData({ scrollTop }));
  },

  // ---- 选择时段 ----
  toggleSelMode() {
    const on = !this.data.selMode;
    const conf = granConf(this.data.gran);
    this.setData({
      selMode: on,
      selRanges: [], selAnchor: null, selSummary: '',
      slots: on ? buildSlots([], null, this.data.gran, conf.hourPx) : [],
    });
  },

  /**
   * 切换粒度。已选区间的边界未必对齐新格子，直接清空而不是勉强换算，
   * 避免出现「选中的段和高亮的格子对不上」这种更难理解的状态。
   */
  onPickGran(e) {
    const gran = Number(e.currentTarget.dataset.gran);
    if (gran === this.data.gran) return;
    this.setData({ gran, selRanges: [], selAnchor: null, selSummary: '' }, () => {
      const conf = granConf(gran);
      this.setData({ slots: this.data.selMode ? buildSlots([], null, gran, conf.hourPx) : [] });
      const { blocks, nowTop } = this.layout();
      this.scrollToFocus(nowTop, blocks);
    });
  },

  /**
   * 点选逻辑：第一次点确定起点，第二次点确定终点并落成一段；
   * 再点则开始新的一段，可累积多段。点已选中的段则移除该段。
   */
  onSlotTap(e) {
    const min = Number(e.currentTarget.dataset.min);
    const { selAnchor, selRanges } = this.data;

    if (selAnchor === null) {
      const hit = selRanges.findIndex((r) => min >= r.start && min < r.end);
      if (hit >= 0) {
        const next = selRanges.slice();
        next.splice(hit, 1);
        this.applySelection(next, null);
        return;
      }
      this.applySelection(selRanges, min);
      return;
    }

    const start = Math.min(selAnchor, min);
    const end = Math.max(selAnchor, min) + this.data.gran;
    this.applySelection(mergeRanges(selRanges.concat([{ start, end }])), null);
  },

  applySelection(ranges, anchor) {
    const totalMin = ranges.reduce((sum, r) => sum + (r.end - r.start), 0);
    const hours = Math.round(totalMin / 6) / 10;
    this.setData({
      selRanges: ranges,
      selAnchor: anchor,
      slots: buildSlots(ranges, anchor, this.data.gran, granConf(this.data.gran).hourPx),
      selSummary: ranges.length
        ? '已选 ' + ranges.length + ' 段，合计 ' + hours + ' 小时'
        : (anchor !== null ? '起点 ' + fmtMin(anchor) + '，请点击结束时间' : ''),
    });
  },

  clearSelection() { this.applySelection([], null); },

  // 用已选时段打开创建弹窗（一个任务 + 多个时间块）
  openAddWithSlots() {
    if (!this.data.selRanges.length) return;
    this.setData({
      showAdd: true,
      scheduling: null,
      form: { title: '', date: this.data.selectedStr, start: '', end: '' },
      formRanges: this.data.selRanges.map((r) => Object.assign({}, r, { text: fmtMin(r.start) + '–' + fmtMin(r.end) })),
    });
  },

  prevWeek() { this.setData({ anchorMs: this.data.anchorMs - 7 * 86400000 }); this.load(); },
  nextWeek() { this.setData({ anchorMs: this.data.anchorMs + 7 * 86400000 }); this.load(); },
  selectDay(e) {
    this.setData({ selectedStr: e.currentTarget.dataset.date });
    this.loadBlocks();
  },

  openTask(e) { wx.navigateTo({ url: '/pages/task-detail/index?id=' + e.currentTarget.dataset.id }); },

  openAdd() {
    this.setData({ showAdd: true, scheduling: null, formRanges: [], form: { title: '', date: this.data.selectedStr, start: '09:00', end: '10:00' } });
  },
  // 未排程任务：点击直接进入「给这条任务排时间」的流程，而不是新建一条任务
  openSchedule(e) {
    const id = e.currentTarget.dataset.id;
    const todo = this.data.unscheduledTodos.find((t) => t._id === id);
    if (!todo) return;
    this.setData({
      showAdd: true, scheduling: todo, formRanges: [],
      form: { title: todo.title, date: this.data.selectedStr, start: '09:00', end: '10:00' },
    });
  },
  closeAdd() { this.setData({ showAdd: false }); },
  noop() {},
  onFormTitle(e) { this.setData({ 'form.title': e.detail.value }); },
  onFormDate(e) { this.setData({ 'form.date': e.detail.value }); },
  onFormStart(e) { this.setData({ 'form.start': e.detail.value }); },
  onFormEnd(e) { this.setData({ 'form.end': e.detail.value }); },

  async addSchedule() {
    const { title, date, start, end } = this.data.form;
    const scheduling = this.data.scheduling;
    const ranges = this.data.formRanges;
    if (!scheduling && !title.trim()) { wx.showToast({ title: '请输入标题', icon: 'none' }); return; }
    if (!date) { wx.showToast({ title: '请选择日期', icon: 'none' }); return; }

    const p = date.split('-').map(Number);
    const atMin = (min) => new Date(p[0], p[1] - 1, p[2], Math.floor(min / 60), min % 60).getTime();

    // 多时段（来自日历上的点选）与单时段（弹窗里的起止选择器）走同一套创建逻辑
    let timeBlocks;
    if (ranges.length) {
      timeBlocks = ranges.map((r) => ({
        start_time: atMin(r.start),
        // 24:00 落在次日 0 点，用当天 23:59 收口，避免云函数的「时间块不能跨天」校验拦截
        end_time: r.end >= 1440 ? atMin(1439) : atMin(r.end),
      }));
    } else {
      if (!start || !end) { wx.showToast({ title: '请选择起止时间', icon: 'none' }); return; }
      const toMs = (hhmm) => { const q = hhmm.split(':').map(Number); return new Date(p[0], p[1] - 1, p[2], q[0], q[1]).getTime(); };
      const s = toMs(start), e = toMs(end);
      if (e <= s) { wx.showToast({ title: '结束需晚于开始', icon: 'none' }); return; }
      timeBlocks = [{ start_time: s, end_time: e }];
    }

    try {
      if (scheduling) {
        for (const tb of timeBlocks) {
          await todoApi.timeblockCreate(Object.assign({ todo_item_id: scheduling._id }, tb));
        }
      } else {
        await todoApi.create({ title: title.trim(), quadrant_type: 'important_not_urgent', time_blocks: timeBlocks });
      }
      this.setData({ showAdd: false, selectedStr: date, selMode: false, selRanges: [], selAnchor: null, selSummary: '', slots: [], formRanges: [] });
      this.load();
    } catch (err) { wx.showToast({ title: err.message || '添加失败', icon: 'none' }); }
  },
});
