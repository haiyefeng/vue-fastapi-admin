const petApi = require('../../services/pet');
const cat = require('../../utils/cat');

Page({
  data: {
    pet: { active_cat_id: 'orange', pet_name: '' },
    cats: [],
    total: 0,
    growth: { label: '', scale: 1, next: null },
    progressPercent: 0,
    distanceToNext: 0,
    greeting: '',
    loading: true,
  },

  onShow() { this.load(); },
  onPullDownRefresh() { this.load().finally(() => wx.stopPullDownRefresh()); },

  async load() {
    // 先用缓存立刻渲染，再拉服务端校准，避免进页面白屏
    this.render();
    try {
      const res = await petApi.bootstrap();
      cat.saveBootstrap(res);
      this.render();
      if (res.newly_unlocked && res.newly_unlocked.length) this.celebrate(res.newly_unlocked);
    } catch (e) {
      wx.showToast({ title: e.message || '加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  // 全部渲染数据都来自本地缓存，网络只负责更新缓存
  render() {
    const cfg = cat.getConfig();
    const st = cat.getState();
    if (!cfg || !st) return;

    const total = st.total || 0;
    const growth = cat.growthStage(total);
    const owned = st.owned_cats || [];
    const cats = (cfg.cats || []).map((c) => Object.assign({}, c, {
      id: c._id,
      unlocked: owned.indexOf(c._id) >= 0,
      threshold: (c.unlock && c.unlock[0] && c.unlock[0].value) || 0,
    }));

    this.setData({
      pet: { active_cat_id: st.active_cat_id, pet_name: st.pet_name || '' },
      cats,
      total,
      growth,
      progressPercent: growth.next ? Math.min(100, Math.round(total / growth.next * 100)) : 100,
      distanceToNext: growth.next ? growth.next - total : 0,
      greeting: cat.pickLine('pet', {}) || '',
    });
  },

  celebrate(ids) {
    const cfg = cat.getConfig();
    const names = ids.map((id) => {
      const c = (cfg.cats || []).find((x) => x._id === id);
      return c ? c.name : id;
    });
    wx.showModal({
      title: '🎉 解锁新猫咪',
      content: '你解锁了「' + names.join('、') + '」，去猫皮肤里换上试试吧～',
      showCancel: false,
      confirmText: '好耶',
    });
  },

  async switchCat(e) {
    const { id, unlocked } = e.currentTarget.dataset;
    if (unlocked !== true) { wx.showToast({ title: '这只猫还没解锁', icon: 'none' }); return; }
    if (id === this.data.pet.active_cat_id) return;

    // 乐观切换：先本地生效，失败再回滚
    const st = cat.getState();
    const prev = st.active_cat_id;
    st.active_cat_id = id;
    cat.setState(st);
    this.render();

    try {
      await petApi.update({ active_cat_id: id });
    } catch (err) {
      st.active_cat_id = prev;
      cat.setState(st);
      this.render();
      wx.showToast({ title: err.message || '切换失败', icon: 'none' });
    }
  },
});
