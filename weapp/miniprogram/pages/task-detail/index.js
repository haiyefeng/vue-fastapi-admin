const todoApi = require('../../services/todo');
const projectApi = require('../../services/project');
const goalApi = require('../../services/goal');
const { QUADRANT_KEYS, quadrantMeta } = require('../../utils/quadrant');
const { formatDateTime, formatTime } = require('../../utils/date');

const pad = (n) => String(n).padStart(2, '0');

Page({
  data: {
    id: null,
    todo: null,
    loading: true,
    projects: [], goals: [],
    projectNames: [], goalNames: [],
    projectIndex: 0, goalIndex: 0,
    quadrantNames: QUADRANT_KEYS.map((k) => quadrantMeta(k).label),
    quadrantIndex: 0,
    dueDateText: '',
    newSubtask: '',
    blockDate: '', blockStart: '', blockEnd: '',
  },

  onLoad(options) { this.setData({ id: options.id }); },
  onShow() { if (this.data.id) this.load(); },

  async load() {
    this.setData({ loading: true });
    try {
      const [todo, projRes, goalRes] = await Promise.all([
        todoApi.get(this.data.id),
        projectApi.list(),
        goalApi.list(),
      ]);
      const projects = (projRes.list || []).filter((p) => !p.is_archived);
      const goals = (goalRes.list || []).filter((g) => !g.is_archived);
      let pi = 0, gi = 0;
      projects.forEach((p, i) => { if (p._id === todo.project_id) pi = i; });
      goals.forEach((g, i) => { if (g._id === todo.goal_id) gi = i; });
      todo.time_blocks = (todo.time_blocks || []).map((b) => Object.assign({}, b, { start_text: formatTime(b.start_time), end_text: formatTime(b.end_time) }));
      const qi = QUADRANT_KEYS.indexOf(todo.quadrant_type);
      this.setData({
        todo,
        projects, goals,
        projectNames: ['收件箱'].concat(projects.map((p) => p.name)),
        goalNames: ['无'].concat(goals.map((g) => g.name)),
        projectIndex: todo.project_id ? pi + 1 : 0,
        goalIndex: todo.goal_id ? gi + 1 : 0,
        quadrantIndex: qi >= 0 ? qi : 0,
        dueDateText: todo.due_date ? formatDateTime(todo.due_date) : '',
        loading: false,
      });
    } catch (e) {
      this.setData({ loading: false });
      wx.showToast({ title: e.message || '加载失败', icon: 'none' });
    }
  },

  onInputTitle(e) { this.setData({ 'todo.title': e.detail.value }); },
  onInputNotes(e) { this.setData({ 'todo.notes': e.detail.value }); },
  onPickQuadrant(e) {
    const idx = Number(e.detail.value);
    this.setData({ quadrantIndex: idx, 'todo.quadrant_type': QUADRANT_KEYS[idx] });
  },
  onPickDue(e) {
    const p = e.detail.value.split('-').map(Number);
    const ms = new Date(p[0], p[1] - 1, p[2], 23, 59, 59).getTime();
    this.setData({ 'todo.due_date': ms, dueDateText: e.detail.value });
  },
  onClearDue() { this.setData({ 'todo.due_date': null, dueDateText: '' }); },
  onPickProject(e) {
    const idx = Number(e.detail.value);
    this.setData({ projectIndex: idx, 'todo.project_id': idx === 0 ? null : this.data.projects[idx - 1]._id });
  },
  onPickGoal(e) {
    const idx = Number(e.detail.value);
    this.setData({ goalIndex: idx, 'todo.goal_id': idx === 0 ? null : this.data.goals[idx - 1]._id });
  },

  // ---- 子任务 ----
  onInputSubtask(e) { this.setData({ newSubtask: e.detail.value }); },
  async addSubtask() {
    const title = this.data.newSubtask.trim();
    if (!title) return;
    try {
      await todoApi.subtaskCreate({ todo_item_id: this.data.id, title });
      this.setData({ newSubtask: '' });
      this.load();
    } catch (e) { wx.showToast({ title: e.message || '添加失败', icon: 'none' }); }
  },
  async toggleSubtask(e) {
    const { id, done } = e.currentTarget.dataset;
    try {
      await todoApi.subtaskUpdate(id, { is_completed: done !== true });
      this.load();
    } catch (e) { wx.showToast({ title: e.message || '操作失败', icon: 'none' }); }
  },
  async removeSubtask(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await todoApi.subtaskRemove(id);
      this.load();
    } catch (e) { wx.showToast({ title: e.message || '删除失败', icon: 'none' }); }
  },

  // ---- 时间块 ----
  onPickBlockDate(e) { this.setData({ blockDate: e.detail.value }); },
  onPickBlockStart(e) { this.setData({ blockStart: e.detail.value }); },
  onPickBlockEnd(e) { this.setData({ blockEnd: e.detail.value }); },
  async addBlock() {
    const { blockDate, blockStart, blockEnd } = this.data;
    if (!blockDate || !blockStart || !blockEnd) { wx.showToast({ title: '请选择日期和起止时间', icon: 'none' }); return; }
    const p = blockDate.split('-').map(Number);
    const toMs = (hhmm) => { const q = hhmm.split(':').map(Number); return new Date(p[0], p[1] - 1, p[2], q[0], q[1]).getTime(); };
    const s = toMs(blockStart), e = toMs(blockEnd);
    if (e <= s) { wx.showToast({ title: '结束需晚于开始', icon: 'none' }); return; }
    try {
      await todoApi.timeblockCreate({ todo_item_id: this.data.id, start_time: s, end_time: e });
      this.load();
    } catch (e) { wx.showToast({ title: e.message || '添加失败', icon: 'none' }); }
  },
  async removeBlock(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await todoApi.timeblockRemove(id);
      this.load();
    } catch (e) { wx.showToast({ title: e.message || '删除失败', icon: 'none' }); }
  },

  async onSave() {
    const t = this.data.todo;
    if (!t.title || !t.title.trim()) { wx.showToast({ title: '请输入标题', icon: 'none' }); return; }
    try {
      await todoApi.update(t._id, {
        title: t.title.trim(), quadrant_type: t.quadrant_type,
        due_date: t.due_date, notes: t.notes,
        project_id: t.project_id, goal_id: t.goal_id,
      });
      wx.showToast({ title: '已保存', icon: 'success' });
      wx.navigateBack();
    } catch (e) { wx.showToast({ title: e.message || '保存失败', icon: 'none' }); }
  },

  onDelete() {
    wx.showModal({
      title: '确认删除', content: '确定删除这条任务吗？子任务和时间块会一并删除。',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await todoApi.remove(this.data.id);
          wx.showToast({ title: '已删除', icon: 'success' });
          wx.navigateBack();
        } catch (e) { wx.showToast({ title: e.message || '删除失败', icon: 'none' }); }
      },
    });
  },
});
