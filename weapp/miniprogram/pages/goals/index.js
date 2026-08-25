const goalApi = require('../../services/goal');

Page({
  data: {
    goals: [], archivedGoals: [],
    showForm: false, editingGoal: null,
    form: { name: '', description: '', target_date: '' },
    showDetail: false, detail: null,
    showArchived: false,
  },

  onShow() { this.fetchAll(); },
  onPullDownRefresh() { this.fetchAll().finally(() => wx.stopPullDownRefresh()); },

  async fetchAll() {
    try {
      const res = await goalApi.bootstrap();
      this.setData({ goals: res.list || [], archivedGoals: res.archived || [] });
    } catch (e) { wx.showToast({ title: e.message || '加载失败', icon: 'none' }); }
  },

  openCreate() { this.setData({ showForm: true, editingGoal: null, form: { name: '', description: '', target_date: '' } }); },
  openEdit(e) {
    const g = this.data.goals.find((x) => x._id === e.currentTarget.dataset.id);
    if (!g) return;
    this.setData({ showForm: true, editingGoal: g, form: { name: g.name, description: g.description || '', target_date: g.target_date || '' } });
  },
  closeForm() { this.setData({ showForm: false }); },
  noop() {},
  onInputName(e) { this.setData({ 'form.name': e.detail.value }); },
  onInputDesc(e) { this.setData({ 'form.description': e.detail.value }); },
  onPickTarget(e) { this.setData({ 'form.target_date': e.detail.value }); },

  async onSave() {
    const { form, editingGoal } = this.data;
    if (!form.name.trim()) { wx.showToast({ title: '请输入名称', icon: 'none' }); return; }
    const payload = { name: form.name.trim(), description: form.description, target_date: form.target_date || undefined };
    try {
      if (editingGoal) await goalApi.update(editingGoal._id, payload);
      else await goalApi.create(payload);
      this.setData({ showForm: false });
      this.fetchAll();
    } catch (e) { wx.showToast({ title: e.message || '保存失败', icon: 'none' }); }
  },

  async openDetail(e) {
    const id = e.currentTarget.dataset.id;
    try {
      const detail = await goalApi.detail(id);
      this.setData({ showDetail: true, detail });
    } catch (e) { wx.showToast({ title: e.message || '加载失败', icon: 'none' }); }
  },
  closeDetail() { this.setData({ showDetail: false }); },

  async archive(e) { await this.setArchived(e, true); },
  async unarchive(e) { await this.setArchived(e, false); },
  async setArchived(e, val) {
    const id = e.currentTarget.dataset.id;
    try { await goalApi.update(id, { is_archived: val }); this.fetchAll(); }
    catch (err) { wx.showToast({ title: err.message || '操作失败', icon: 'none' }); }
  },
  onDelete(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '确认删除', content: '删除后关联的任务和习惯会保留，仅解除关联。',
      success: async (res) => {
        if (!res.confirm) return;
        try { await goalApi.remove(id); this.fetchAll(); }
        catch (err) { wx.showToast({ title: err.message || '删除失败', icon: 'none' }); }
      },
    });
  },
});
