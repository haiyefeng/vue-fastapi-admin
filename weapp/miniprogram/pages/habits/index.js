const habitApi = require('../../services/habit');
const todoApi = require('../../services/todo');
const goalApi = require('../../services/goal');
const petApi = require('../../services/pet');
const cat = require('../../utils/cat');
const { todayStr } = require('../../utils/date');

const FREQ_OPTIONS = [
  { label: '每天', value: 'daily' },
  { label: '每周固定几天', value: 'weekly_days' },
  { label: '每周任意 N 次', value: 'weekly_count' },
  { label: '每隔 N 天', value: 'interval_days' },
];
const WEEK_NAMES = ['一', '二', '三', '四', '五', '六', '日'];

function buildDayStates(days) {
  return [1, 2, 3, 4, 5, 6, 7].map((d) => ({ d, on: (days || []).indexOf(d) >= 0 }));
}

Page({
  data: {
    habits: [], archivedHabits: [],
    catTip: '',
    showForm: false, editingHabit: null,
    freqOptions: FREQ_OPTIONS,
    freqIndex: 0,
    weekNames: WEEK_NAMES,
    dayStates: buildDayStates([1, 2, 3, 4, 5]),
    goals: [], goalNames: ['无'], goalIndex: 0,
    form: { name: '', icon: '', reminder_time: '', days: [1,2,3,4,5], count: 3, interval: 2 },
    showArchived: false,
  },

  onShow() { this.fetchAll(); },

  closeCatTip() { this.setData({ catTip: '' }); },
  onPullDownRefresh() { this.fetchAll().finally(() => wx.stopPullDownRefresh()); },

  async fetchAll() {
    try {
      const [habitRes, goalRes] = await Promise.all([habitApi.bootstrap(), goalApi.list()]);
      const goals = (goalRes.list || []).filter((g) => !g.is_archived);
      const decorate = (h) => Object.assign({}, h, { freq_label: this.frequencyLabel(h) });
      // 猫的台词纯本地计算（配置与计数都在 Storage 里），不额外发请求
      const catTip = cat.pickLine('habit', {
        pending: (habitRes.list || []).filter((h) => !h.is_paused && h.today_todo_id && !h.today_completed).length,
      });
      this.setData({ habits: (habitRes.list || []).map(decorate), archivedHabits: habitRes.archived || [], goals, goalNames: ['无'].concat(goals.map((g) => g.name)), catTip });
    } catch (e) { wx.showToast({ title: e.message || '加载失败', icon: 'none' }); }
    this.syncCat();
  },

  // 后台静默校准猫的状态与配置；失败无所谓，页面已用缓存渲染过了
  syncCat() {
    petApi.sync().then((res) => cat.saveBootstrap(res)).catch(() => {});
  },

  frequencyLabel(h) {
    const cfg = h.frequency_config || {};
    if (h.frequency_type === 'daily') return '每天';
    if (h.frequency_type === 'weekly_days') return '每周' + (cfg.days || []).map((d) => WEEK_NAMES[d - 1]).join('');
    if (h.frequency_type === 'weekly_count') return '每周' + cfg.count + '次';
    if (h.frequency_type === 'interval_days') return '每隔' + cfg.interval + '天';
    return '';
  },

  openCreate() {
    this.setData({ showForm: true, editingHabit: null, freqIndex: 0, goalIndex: 0, dayStates: buildDayStates([1,2,3,4,5]), form: { name: '', icon: '', reminder_time: '', days: [1,2,3,4,5], count: 3, interval: 2 } });
  },
  openEdit(e) {
    const h = this.data.habits.find((x) => x._id === e.currentTarget.dataset.id);
    if (!h) return;
    const cfg = h.frequency_config || {};
    const gi = h.goal_id ? this.data.goals.findIndex((g) => g._id === h.goal_id) : -1;
    this.setData({
      showForm: true, editingHabit: h,
      freqIndex: Math.max(0, FREQ_OPTIONS.findIndex((o) => o.value === h.frequency_type)),
      goalIndex: gi >= 0 ? gi + 1 : 0,
      dayStates: buildDayStates(cfg.days || [1,2,3,4,5]),
      form: {
        name: h.name, icon: h.icon || '', reminder_time: h.reminder_time || '',
        days: cfg.days || [1,2,3,4,5], count: cfg.count || 3, interval: cfg.interval || 2,
      },
    });
  },
  closeForm() { this.setData({ showForm: false }); },
  noop() {},
  onInputName(e) { this.setData({ 'form.name': e.detail.value }); },
  onInputIcon(e) { this.setData({ 'form.icon': e.detail.value }); },
  onInputReminder(e) { this.setData({ 'form.reminder_time': e.detail.value }); },
  onPickFreq(e) { this.setData({ freqIndex: Number(e.detail.value) }); },
  onPickGoal(e) { this.setData({ goalIndex: Number(e.detail.value) }); },
  toggleDay(e) {
    const d = Number(e.currentTarget.dataset.d);
    const dayStates = this.data.dayStates.map((x) => (x.d === d ? { d, on: !x.on } : x));
    const days = dayStates.filter((x) => x.on).map((x) => x.d);
    this.setData({ dayStates, 'form.days': days });
  },
  onInputCount(e) { this.setData({ 'form.count': Number(e.detail.value) || 0 }); },
  onInputInterval(e) { this.setData({ 'form.interval': Number(e.detail.value) || 0 }); },

  async onSave() {
    const { form, editingHabit, freqIndex } = this.data;
    if (!form.name.trim()) { wx.showToast({ title: '请输入习惯名称', icon: 'none' }); return; }
    const ft = FREQ_OPTIONS[freqIndex].value;
    let cfg = {};
    if (ft === 'weekly_days') {
      if (!form.days.length) { wx.showToast({ title: '请选择至少一天', icon: 'none' }); return; }
      cfg = { days: form.days };
    } else if (ft === 'weekly_count') {
      if (!(form.count >= 1)) { wx.showToast({ title: '请输入每周次数', icon: 'none' }); return; }
      cfg = { count: form.count };
    } else if (ft === 'interval_days') {
      if (!(form.interval >= 1)) { wx.showToast({ title: '请输入间隔天数', icon: 'none' }); return; }
      cfg = { interval: form.interval };
    }
    const goalId = this.data.goalIndex === 0 ? null : (this.data.goals[this.data.goalIndex - 1] || {})._id;
    const payload = { name: form.name.trim(), icon: form.icon, reminder_time: form.reminder_time, frequency_type: ft, frequency_config: cfg, goal_id: goalId };
    try {
      if (editingHabit) await habitApi.update(editingHabit._id, payload);
      else await habitApi.create(Object.assign({}, payload, { created_date: todayStr() }));
      this.setData({ showForm: false });
      this.fetchAll();
    } catch (e) { wx.showToast({ title: e.message || '保存失败', icon: 'none' }); }
  },

  async checkIn(e) {
    const id = e.currentTarget.dataset.id;
    const h = this.data.habits.find((x) => x._id === id);
    if (!h || !h.today_todo_id || h.today_completed) return;
    try {
      await todoApi.update(h.today_todo_id, { is_completed: true });
      wx.showToast({ title: '打卡成功', icon: 'success' });
      this.fetchAll();
    } catch (err) { wx.showToast({ title: err.message || '打卡失败', icon: 'none' }); }
  },

  async togglePause(e) {
    const id = e.currentTarget.dataset.id;
    const h = this.data.habits.find((x) => x._id === id);
    try { await habitApi.update(id, { is_paused: !h.is_paused }); this.fetchAll(); }
    catch (err) { wx.showToast({ title: err.message || '操作失败', icon: 'none' }); }
  },
  async archive(e) { await this.setArchived(e, true); },
  async unarchive(e) { await this.setArchived(e, false); },
  async setArchived(e, val) {
    const id = e.currentTarget.dataset.id;
    try { await habitApi.update(id, { is_archived: val }); this.fetchAll(); }
    catch (err) { wx.showToast({ title: err.message || '操作失败', icon: 'none' }); }
  },
  onDelete(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认删除', content: '删除后所有历史打卡记录一并删除，不可恢复。',
      success: async (res) => {
        if (!res.confirm) return;
        try { await habitApi.remove(id); this.fetchAll(); }
        catch (err) { wx.showToast({ title: err.message || '删除失败', icon: 'none' }); }
      },
    });
  },
});
