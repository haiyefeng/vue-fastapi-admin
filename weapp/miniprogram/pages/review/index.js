const reviewApi = require('../../services/review');
const habitApi = require('../../services/habit');
const { todayStr, toDateStr, parseDateStr, calcPeriodRange } = require('../../utils/date');

const PERIOD_OPTIONS = [
  { label: '周', value: 'week' },
  { label: '月', value: 'month' },
  { label: '季度', value: 'quarter' },
  { label: '年', value: 'year' },
];

const STEPS = [
  { key: 'step1', title: '负面 → 正面', guide: '本周期哪些方面不满意/遇到挑战？从中看到哪些积极信号、经验或值得肯定的地方？' },
  { key: 'step2', title: '封闭 → 开放', guide: '针对某个亮点，促成它的关键因素是什么？还有哪些其他可能的原因？' },
  { key: 'step3', title: '单一 → 复数', guide: '为了保持亮点或改进挑战，有哪些不同方法（至少 2-3 种）？' },
  { key: 'step4', title: '现实 → 可能性', guide: '如果挑战消失或亮点发挥到极致，可能出现哪些新机会？' },
  { key: 'step5', title: '发散 → 聚焦', guide: '下个周期你最想集中突破的一个具体领域是什么？' },
  { key: 'step6', title: '静态 → 动态', guide: '为这个焦点，下周期可采取哪些具体、可衡量的行动？' },
  { key: 'step7', title: '个体 → 系统', guide: '这项改进将如何影响其他目标/习惯？需要调整哪些环境或流程？' },
];

const emptyAnswers = () => ({ step1: '', step2: '', step3: '', step4: '', step5: '', step6: '', step7: '' });

function shiftAnchor(anchorStr, type, delta) {
  const [y, m, d] = anchorStr.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  if (type === 'week') dt.setDate(dt.getDate() + delta * 7);
  else if (type === 'month') dt.setMonth(dt.getMonth() + delta);
  else if (type === 'quarter') dt.setMonth(dt.getMonth() + delta * 3);
  else dt.setFullYear(dt.getFullYear() + delta);
  return toDateStr(dt.getTime());
}

Page({
  data: {
    periodOptions: PERIOD_OPTIONS,
    periodIndex: 0,
    anchorStr: todayStr(),
    rangeLabel: '',
    steps: STEPS.map((s) => Object.assign({}, s, { value: '' })),
    summary: null,
    answers: emptyAnswers(),
    loading: false, saving: false,
    showHistory: false, historyList: [],
  },

  onShow() { this.load(); },

  async load() {
    this.setData({ loading: true });
    const pt = PERIOD_OPTIONS[this.data.periodIndex].value;
    const r = calcPeriodRange(pt, this.data.anchorStr);
    this.setData({ rangeLabel: r.startStr + ' ~ ' + r.endStr });
    try {
      const [boot, habitRes] = await Promise.all([
        reviewApi.bootstrap(pt, this.data.anchorStr),
        habitApi.summary({ start_str: r.startStr, end_str: r.endStr, today_str: todayStr() }),
      ]);
      const summary = boot.summary;
      const detail = boot.detail;
      summary.habits = (habitRes && habitRes.list) || [];
      const merged = detail ? Object.assign(emptyAnswers(), detail.answers || {}) : emptyAnswers();
      const steps = STEPS.map((s) => Object.assign({}, s, { value: merged[s.key] || '' }));
      this.setData({ summary, answers: merged, steps, loading: false });
    } catch (e) {
      this.setData({ loading: false });
      wx.showToast({ title: e.message || '加载失败', icon: 'none' });
    }
  },

  onPickPeriod(e) { this.setData({ periodIndex: Number(e.detail.value) }); this.load(); },
  prev() { this.setData({ anchorStr: shiftAnchor(this.data.anchorStr, PERIOD_OPTIONS[this.data.periodIndex].value, -1) }); this.load(); },
  next() { this.setData({ anchorStr: shiftAnchor(this.data.anchorStr, PERIOD_OPTIONS[this.data.periodIndex].value, 1) }); this.load(); },

  onAnswer(e) { this.setData({ ['answers.' + e.currentTarget.dataset.k]: e.detail.value }); },

  async save(e) {
    const status = e.currentTarget.dataset.status;
    this.setData({ saving: true });
    const pt = PERIOD_OPTIONS[this.data.periodIndex].value;
    const r = calcPeriodRange(pt, this.data.anchorStr);
    try {
      await reviewApi.save({ period_type: pt, anchor_date: this.data.anchorStr, period_start: r.startStr, period_end: r.endStr, answers: this.data.answers, status });
      wx.showToast({ title: status === 'completed' ? '回顾已完成' : '草稿已保存', icon: 'success' });
    } catch (e) { wx.showToast({ title: e.message || '保存失败', icon: 'none' }); }
    finally { this.setData({ saving: false }); }
  },

  async openHistory() {
    this.setData({ showHistory: true });
    try {
      const res = await reviewApi.list();
      this.setData({ historyList: res.list || [] });
    } catch (e) { wx.showToast({ title: e.message || '加载失败', icon: 'none' }); }
  },
  closeHistory() { this.setData({ showHistory: false }); },
  jumpTo(e) {
    const item = this.data.historyList[e.currentTarget.dataset.i];
    const pi = PERIOD_OPTIONS.findIndex((o) => o.value === item.period_type);
    this.setData({ periodIndex: pi >= 0 ? pi : 0, anchorStr: item.period_start, showHistory: false });
    this.load();
  },
});
