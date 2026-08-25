const todoApi = require('../../services/todo');
const cat = require('../../utils/cat');
const projectApi = require('../../services/project');
const { quadrantMeta } = require('../../utils/quadrant');
const { todayStr, startOfDay, formatDateTime, relativeDayLabel } = require('../../utils/date');

Page({
  data: {
    projects: [], // 进行中的项目/清单
    archivedProjects: [],
    categories: [],
    selection: { type: 'inbox', name: '收件箱' },
    todos: [],
    groups: [],
    quickAdd: '',
    loading: true,
    adding: false,
    statusFilter: 'incomplete', // all | incomplete | completed
    showNewProject: false,
    newProjectName: '',
    newProjectType: 'project',
    categoryNames: ['不分类'],
    categoryIndex: 0,
    newCategoryName: '', // 仅当 categoryIndex 指向「+ 新建分类」时使用
    showManage: false,
  },

  onShow() { this.refresh(); },
  onPullDownRefresh() { this.refresh().finally(() => wx.stopPullDownRefresh()); },

  async refresh() {
    await Promise.all([this.fetchProjects(), this.fetchTodos()]);
  },

  async fetchProjects() {
    try {
      const res = await projectApi.bootstrap();
      const categories = res.categories || [];
      this.setData({
        projects: res.list || [],
        archivedProjects: res.archived || [],
        categories,
        categoryNames: ['不分类'].concat(categories.map((c) => c.name), ['+ 新建分类']),
      });
    } catch (e) { console.error(e); }
  },

  async fetchTodos() {
    const sel = this.data.selection;
    const params = { pageSize: 200, sort_by: 'due_date', sort_order: 'asc' };
    if (sel.type === 'project') params.project_id = sel._id;
    else params.inbox_only = true;
    const sf = this.data.statusFilter;
    if (sf === 'incomplete') params.is_completed = false;
    if (sf === 'completed') params.is_completed = true;
    try {
      const res = await todoApi.list(params);
      const todayStart = startOfDay(Date.now());
      const list = (res.list || []).map((t) => Object.assign({}, t, {
        quadrant_label: quadrantMeta(t.quadrant_type).label,
        quadrant_color: quadrantMeta(t.quadrant_type).color,
        due_text: t.due_date ? formatDateTime(t.due_date) : '',
        is_overdue: !!(t.due_date && !t.is_completed && t.due_date < todayStart),
      }));
      this.setData({ todos: list, groups: this.groupTodos(list) });
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  groupTodos(list) {
    const today = startOfDay(Date.now());
    const overdue = [], todayItems = [], later = [];
    for (const t of list) {
      if (t.is_completed) { later.push(t); continue; }
      if (!t.due_date) { later.push(t); continue; }
      const due = t.due_date;
      if (due < today) overdue.push(t);
      else if (due < today + 86400000) todayItems.push(t);
      else later.push(t);
    }
    const out = [];
    if (overdue.length) out.push({ key: 'overdue', label: '已过期', color: '#f5222d', items: overdue });
    if (todayItems.length) out.push({ key: 'today', label: '今天', color: '#1890ff', items: todayItems });
    if (later.length) out.push({ key: 'later', label: '稍后', color: '#999', items: later });
    return out;
  },

  selectInbox() { this.setData({ selection: { type: 'inbox', name: '收件箱' } }); this.fetchTodos(); },
  selectProject(e) {
    const id = e.currentTarget.dataset.id;
    const name = e.currentTarget.dataset.name;
    this.setData({ selection: { type: 'project', _id: id, name } });
    this.fetchTodos();
  },
  onStatusFilter(e) {
    const v = e.currentTarget.dataset.v;
    this.setData({ statusFilter: v });
    this.fetchTodos();
  },

  onInputQuick(e) { this.setData({ quickAdd: e.detail.value }); },
  async addQuick() {
    const title = this.data.quickAdd.trim();
    if (!title || this.data.adding) return;
    const payload = { title, quadrant_type: 'not_urgent_not_important' };
    if (this.data.selection.type === 'project') payload.project_id = this.data.selection._id;
    // 输入框立刻清空、按钮进入禁用态，让点击有即时反馈并避免连点重复创建
    this.setData({ quickAdd: '', adding: true });
    try {
      await todoApi.create(payload);
      wx.showToast({ title: '已添加', icon: 'success', duration: 1200 });
      await this.fetchTodos();
    } catch (e) {
      this.setData({ quickAdd: title }); // 失败则把内容还给用户
      wx.showToast({ title: e.message || '添加失败', icon: 'none' });
    } finally {
      this.setData({ adding: false });
    }
  },

  /**
   * 勾选完成：先本地生效再发请求（乐观更新）。
   * 原实现要等「更新 + 重拉列表」两轮云函数调用才有视觉变化，中间毫无反馈。
   */
  async toggleComplete(e) {
    const { id, done } = e.currentTarget.dataset;
    const next = done !== true;

    const todos = this.data.todos.map((t) => (t._id === id ? Object.assign({}, t, { is_completed: next }) : t));
    this.setData({ todos, groups: this.groupTodos(todos) });

    try {
      await todoApi.update(id, { is_completed: next });
      if (next) cat.bump('todo_completed');
      this.fetchTodos(); // 后台校准（当前筛选下该条可能需要移出列表）
    } catch (e) {
      wx.showToast({ title: e.message || '操作失败', icon: 'none' });
      this.fetchTodos(); // 回滚到服务端真实状态
    }
  },

  openDetail(e) {
    wx.navigateTo({ url: '/pages/task-detail/index?id=' + e.currentTarget.dataset.id });
  },

  // ---- 新建项目 ----
  openNewProject() {
    this.setData({ showNewProject: true, newProjectName: '', newProjectType: 'project', categoryIndex: 0, newCategoryName: '' });
  },
  closeNewProject() { this.setData({ showNewProject: false }); },
  noop() {},
  onInputProjectName(e) { this.setData({ newProjectName: e.detail.value }); },
  onPickProjectType(e) { this.setData({ newProjectType: e.detail.value === '0' ? 'project' : 'list' }); },
  onPickCategory(e) { this.setData({ categoryIndex: Number(e.detail.value) }); },
  onInputNewCategory(e) { this.setData({ newCategoryName: e.detail.value }); },
  async createProject() {
    const name = this.data.newProjectName.trim();
    if (!name) { wx.showToast({ title: '请输入项目名', icon: 'none' }); return; }
    const { categoryIndex, categories, newCategoryName } = this.data;
    const payload = { name, type: this.data.newProjectType };
    if (categoryIndex >= 1 && categoryIndex <= categories.length) {
      payload.category_id = categories[categoryIndex - 1]._id;
    } else if (categoryIndex === categories.length + 1) {
      const cn = newCategoryName.trim();
      if (!cn) { wx.showToast({ title: '请输入新分类名称', icon: 'none' }); return; }
      payload.category_name = cn;
    }
    try {
      await projectApi.create(payload);
      this.setData({ showNewProject: false });
      this.fetchProjects();
    } catch (e) { wx.showToast({ title: e.message || '创建失败', icon: 'none' }); }
  },

  // ---- 项目管理：重命名 / 归档 / 取消归档 / 删除 ----
  openManage() { this.setData({ showManage: true }); },
  closeManage() { this.setData({ showManage: false }); },

  renameProject(e) {
    const id = e.currentTarget.dataset.id;
    const name = e.currentTarget.dataset.name;
    wx.showModal({
      title: '重命名', editable: true, placeholderText: '项目名称', content: name,
      success: async (res) => {
        if (!res.confirm) return;
        const newName = (res.content || '').trim();
        if (!newName || newName === name) return;
        try {
          await projectApi.update(id, { name: newName });
          this.fetchProjects();
          if (this.data.selection.type === 'project' && this.data.selection._id === id) {
            this.setData({ 'selection.name': newName });
          }
        } catch (err) { wx.showToast({ title: err.message || '重命名失败', icon: 'none' }); }
      },
    });
  },
  async archiveProject(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await projectApi.update(id, { is_archived: true });
      if (this.data.selection.type === 'project' && this.data.selection._id === id) {
        this.setData({ selection: { type: 'inbox', name: '收件箱' } });
        this.fetchTodos();
      }
      this.fetchProjects();
    } catch (err) { wx.showToast({ title: err.message || '归档失败', icon: 'none' }); }
  },
  async unarchiveProject(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await projectApi.update(id, { is_archived: false });
      this.fetchProjects();
    } catch (err) { wx.showToast({ title: err.message || '操作失败', icon: 'none' }); }
  },
  deleteProject(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认删除', content: '删除后项目下的任务会移入收件箱，项目本身不可恢复。',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await projectApi.remove(id);
          if (this.data.selection.type === 'project' && this.data.selection._id === id) {
            this.setData({ selection: { type: 'inbox', name: '收件箱' } });
            this.fetchTodos();
          }
          this.fetchProjects();
        } catch (err) { wx.showToast({ title: err.message || '删除失败', icon: 'none' }); }
      },
    });
  },
});
