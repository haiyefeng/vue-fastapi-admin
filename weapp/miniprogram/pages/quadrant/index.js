const todoApi = require('../../services/todo');
const petApi = require('../../services/pet');
const cat = require('../../utils/cat');
const { QUADRANT_KEYS, quadrantMeta } = require('../../utils/quadrant');
const { formatDateTime, startOfDay } = require('../../utils/date');

// 始终返回 4 个象限的空结构，保证页面即使没数据也渲染出 4 张卡片
function emptyQuadrants() {
  return QUADRANT_KEYS.map((key) => {
    const meta = quadrantMeta(key);
    return { key, label: meta.label, color: meta.color, todos: [] };
  });
}

Page({
  data: {
    quadrants: emptyQuadrants(),
    quadrantNames: QUADRANT_KEYS.map((k) => quadrantMeta(k).label),
    loading: true,
    saving: false,
    catTip: '',
    dialogVisible: false,
    dialogType: 'add', // add | edit
    quadrantIndex: 0,
    form: { id: null, title: '', quadrant_type: QUADRANT_KEYS[0], due_date: null, notes: '', quadrant_label: quadrantMeta(QUADRANT_KEYS[0]).label },
    dueDateText: '',
  },

  onShow() { this.fetchTodos(); },
  onPullDownRefresh() { this.fetchTodos().finally(() => wx.stopPullDownRefresh()); },

  async fetchTodos() {
    this.setData({ loading: true });
    try {
      const data = await todoApi.list({ is_completed: false, pageSize: 200, sort_by: 'created_at', sort_order: 'desc' });
      const list = (data.list || []).map((t) => Object.assign({}, t, { due_text: t.due_date ? formatDateTime(t.due_date) : '' }));
      const quadrants = emptyQuadrants().map((q) => {
        q.todos = list.filter((t) => t.quadrant_type === q.key);
        return q;
      });
      const todayStart = startOfDay(Date.now());
      // 猫的台词纯本地计算（配置与计数都在 Storage 里），不额外发请求
      const catTip = cat.pickLine('quadrant', {
        urgent_important: list.filter((t) => t.quadrant_type === 'urgent_important').length,
        overdue: list.filter((t) => t.due_date && t.due_date < todayStart).length,
        total: list.length,
      });
      this.setData({ quadrants, loading: false, catTip });
      this.syncCat();
    } catch (e) {
      console.error(e);
      this.setData({ loading: false });
      wx.showToast({ title: e.message || '加载失败', icon: 'none' });
    }
  },

  closeCatTip() { this.setData({ catTip: '' }); },

  // 后台静默校准猫的状态与配置；失败无所谓，页面已用缓存渲染过了
  syncCat() {
    petApi.sync().then((res) => cat.saveBootstrap(res)).catch(() => {});
  },

  // 由扁平任务列表重建四象限分组（乐观更新时本地重排用，避免整页重拉）
  regroup(list) {
    return emptyQuadrants().map((q) => {
      q.todos = list.filter((t) => t.quadrant_type === q.key);
      return q;
    });
  },

  // 当前四张卡片里的全部任务，摊平成一维
  flatTodos() {
    return this.data.quadrants.reduce((acc, q) => acc.concat(q.todos), []);
  },

  openAdd(e) {
    const key = e.currentTarget.dataset.key;
    this.setData({
      dialogVisible: true,
      dialogType: 'add',
      quadrantIndex: QUADRANT_KEYS.indexOf(key),
      form: { id: null, title: '', quadrant_type: key, due_date: null, notes: '', quadrant_label: quadrantMeta(key).label },
      dueDateText: '',
    });
  },

  openEdit(e) {
    const id = e.currentTarget.dataset.id;
    const todo = this.findTodo(id);
    if (!todo) return;
    this.setData({
      dialogVisible: true,
      dialogType: 'edit',
      quadrantIndex: QUADRANT_KEYS.indexOf(todo.quadrant_type),
      form: { id: todo._id, title: todo.title, quadrant_type: todo.quadrant_type, due_date: todo.due_date || null, notes: todo.notes || '', quadrant_label: quadrantMeta(todo.quadrant_type).label },
      dueDateText: todo.due_date ? formatDateTime(todo.due_date) : '',
    });
  },

  closeDialog() { this.setData({ dialogVisible: false }); },
  noop() {},

  onInputTitle(e) { this.setData({ 'form.title': e.detail.value }); },
  onInputNotes(e) { this.setData({ 'form.notes': e.detail.value }); },
  onPickQuadrant(e) {
    const idx = Number(e.detail.value);
    const key = QUADRANT_KEYS[idx];
    this.setData({ quadrantIndex: idx, 'form.quadrant_type': key, 'form.quadrant_label': quadrantMeta(key).label });
  },
  onPickDue(e) {
    const p = e.detail.value.split('-').map(Number); // 'YYYY-MM-DD'
    const ms = new Date(p[0], p[1] - 1, p[2], 23, 59, 59).getTime();
    this.setData({ 'form.due_date': ms, dueDateText: e.detail.value });
  },
  onClearDue() { this.setData({ 'form.due_date': null, dueDateText: '' }); },

  async onSave() {
    const { form, dialogType } = this.data;
    if (!form.title.trim()) { wx.showToast({ title: '请输入标题', icon: 'none' }); return; }
    if (this.data.saving) return;
    this.setData({ saving: true });
    try {
      if (dialogType === 'add') {
        await todoApi.create({ title: form.title.trim(), quadrant_type: form.quadrant_type, due_date: form.due_date || undefined, notes: form.notes });
      } else {
        await todoApi.update(form.id, { title: form.title.trim(), quadrant_type: form.quadrant_type, due_date: form.due_date, notes: form.notes });
      }
      this.setData({ dialogVisible: false });
      wx.showToast({ title: '已保存', icon: 'success' });
      this.fetchTodos();
    } catch (e) {
      wx.showToast({ title: e.message || '保存失败', icon: 'none' });
    } finally {
      this.setData({ saving: false });
    }
  },

  /**
   * 勾选完成：本页只展示未完成任务，所以完成即从卡片上移除。
   * 先本地移除再发请求，避免等两轮云函数调用期间毫无反馈。
   */
  async toggleComplete(e) {
    const id = e.currentTarget.dataset.id;
    this.setData({ quadrants: this.regroup(this.flatTodos().filter((t) => t._id !== id)) });
    try {
      await todoApi.update(id, { is_completed: true });
      if (true) cat.bump('todo_completed');
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' });
      this.fetchTodos(); // 重拉以回滚到服务端真实状态
    }
  },

  onDelete(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认删除',
      content: '确定删除这条待办吗？',
      success: async (res) => {
        if (!res.confirm) return;
        this.setData({ quadrants: this.regroup(this.flatTodos().filter((t) => t._id !== id)) });
        try {
          await todoApi.remove(id);
          wx.showToast({ title: '已删除', icon: 'success' });
        } catch (err) {
          wx.showToast({ title: err.message || '删除失败', icon: 'none' });
          this.fetchTodos(); // 重拉以回滚到服务端真实状态
        }
      },
    });
  },

  // 长按移动到其它象限（替代 HTML5 拖拽）
  onMove(e) {
    const id = e.currentTarget.dataset.id;
    const todo = this.findTodo(id);
    if (!todo) return;
    const names = this.data.quadrantNames;
    wx.showActionSheet({
      itemList: names,
      success: async (res) => {
        const target = QUADRANT_KEYS[res.tapIndex];
        if (target === todo.quadrant_type) return;
        // 先本地挪到目标象限，卡片立刻发生变化
        const moved = this.flatTodos().map((t) => (t._id === id ? Object.assign({}, t, { quadrant_type: target }) : t));
        this.setData({ quadrants: this.regroup(moved) });
        try {
          await todoApi.update(id, { quadrant_type: target });
        } catch (err) {
          wx.showToast({ title: err.message || '移动失败', icon: 'none' });
          this.fetchTodos(); // 重拉以回滚到服务端真实状态
        }
      },
    });
  },

  findTodo(id) {
    for (const q of this.data.quadrants) {
      const t = q.todos.find((x) => x._id === id);
      if (t) return t;
    }
    return null;
  },
});
