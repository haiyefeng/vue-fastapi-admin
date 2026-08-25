const dashboardApi = require('../../services/dashboard');
const habitApi = require('../../services/habit');
const todoApi = require('../../services/todo');
const petApi = require('../../services/pet');
const cat = require('../../utils/cat');
const { quadrantMeta } = require('../../utils/quadrant');
const { formatTime, todayStr, endOfDay } = require('../../utils/date');

const WEEK = ['日', '一', '二', '三', '四', '五', '六'];

Page({
  data: {
    dateLabel: '',
    greeting: '',
    summarySub: '',
    completed: 0, total: 0, percent: 0,
    schedule: [], tasks: [], habits: [],
    catTip: '',
    quickAdd: '',
    loading: true,   // 首次加载中（用于把「加载中」和「真的没有」区分开）
    adding: false,
    moreLinks: [
      { label: '计划', path: '/pages/goals/index' },
      { label: '习惯', path: '/pages/habits/index' },
      { label: '回顾', path: '/pages/review/index' },
      { label: '统计', path: '/pages/stats/index' },
      { label: '养成', path: '/pages/pet/index' },
    ],
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },

  async load() {
    const now = new Date();
    const hour = now.getHours();
    let greeting = '你好';
    if (hour < 6) greeting = '夜深了，注意休息';
    else if (hour < 12) greeting = '早上好';
    else if (hour < 18) greeting = '下午好';
    else greeting = '晚上好';
    this.setData({
      dateLabel: WEEK[now.getDay()] + ' · ' + (now.getMonth() + 1) + '月' + now.getDate() + '日',
      greeting,
    });
    try {
      const [res, habitRes] = await Promise.all([dashboardApi.today(), habitApi.list()]);
      const schedule = (res.schedule || []).map((b) => Object.assign({}, b, {
        time_text: formatTime(b.start_time) + '–' + formatTime(b.end_time),
        color: quadrantMeta(b.quadrant_type).color,
      }));
      const tasks = (res.tasks || []).map((t) => Object.assign({}, t, { color: quadrantMeta(t.quadrant_type).color }));
      const habits = (habitRes.list || []).filter((h) => h.today_todo_id != null).map((h) => Object.assign({}, h, {
        meta: (h.streak != null ? '连续 ' + h.streak + ' 天' : '') + (h.week_progress ? ' · 本周 ' + h.week_progress : ''),
      }));
      const total = res.total_task_count || 0, completed = res.completed_task_count || 0;
      // 猫的台词纯本地计算（配置与计数都在 Storage 里），不额外发请求
      const catTip = cat.pickLine('today', {
        pending: tasks.length,
        pending_habits: habits.filter((h) => !h.today_completed).length,
        overdue: tasks.filter((t) => t.due_date && t.due_date < Date.now()).length,
      });
      this.setData({
        schedule, tasks, habits, catTip,
        completed, total,
        percent: total ? Math.round(completed / total * 100) : 0,
        summarySub: '今天有 ' + tasks.length + ' 件事，' + habits.filter((h) => !h.today_completed).length + ' 个习惯待打卡',
      });
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
    this.syncCat();
  },

  // 后台静默校准猫的状态与配置；失败无所谓，页面已用缓存渲染过了
  syncCat() {
    petApi.sync().then((res) => cat.saveBootstrap(res)).catch(() => {});
  },

  closeCatTip() { this.setData({ catTip: '' }); },

  onInputQuick(e) { this.setData({ quickAdd: e.detail.value }); },
  async addQuick() {
    const title = this.data.quickAdd.trim();
    if (!title || this.data.adding) return;
    // 输入框立刻清空、按钮进入禁用态，让点击有即时反馈并避免连点重复创建
    this.setData({ quickAdd: '', adding: true });
    try {
      // 在「今日」页记下的事默认就是今天要做的，否则它没有截止日期，
      // 不会出现在今日待办里，用户会以为添加失败了
      await todoApi.create({
        title,
        quadrant_type: 'not_urgent_not_important',
        due_date: endOfDay(Date.now()),
      });
      wx.showToast({ title: '已添加到今天', icon: 'success', duration: 1200 });
      await this.load();
    } catch (e) {
      this.setData({ quickAdd: title }); // 失败则把内容还给用户，不让他白打一遍
      wx.showToast({ title: e.message || '添加失败', icon: 'none' });
    } finally {
      this.setData({ adding: false });
    }
  },
  openTask(e) { wx.navigateTo({ url: '/pages/task-detail/index?id=' + e.currentTarget.dataset.id }); },
  /**
   * 打卡：先本地生效再发请求（乐观更新）。
   * 原实现要等「更新 + 整页重拉」两轮云函数调用才有视觉变化，
   * 中间约 1s 毫无反馈，用户会以为没点中。
   */
  async checkIn(e) {
    const id = e.currentTarget.dataset.id;
    const idx = this.data.habits.findIndex((x) => x.today_todo_id === id);
    if (idx < 0 || this.data.habits[idx].today_completed) return;

    const habits = this.data.habits.slice();
    habits[idx] = Object.assign({}, habits[idx], { today_completed: true });
    const completed = this.data.completed + 1;
    const total = this.data.total;
    this.setData({
      habits,
      completed,
      percent: total ? Math.round(completed / total * 100) : 0,
      summarySub: '今天有 ' + this.data.tasks.length + ' 件事，' + habits.filter((h) => !h.today_completed).length + ' 个习惯待打卡',
    });

    try {
      await todoApi.update(id, { is_completed: true });
      cat.bump('todo_completed');
      this.load(); // 后台校准连续天数等服务端计算的字段
    } catch (err) {
      wx.showToast({ title: err.message || '打卡失败', icon: 'none' });
      this.load(); // 重拉以回滚到服务端真实状态
    }
  },
  goLink(e) { wx.navigateTo({ url: e.currentTarget.dataset.path }); },
});
