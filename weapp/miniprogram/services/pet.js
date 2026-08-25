const { call } = require('./cloud');
const cat = require('../utils/cat');

// 带上本地已缓存的配置版本；版本未变时服务端不会回传配置体
const bootstrap = () => call('pet', { action: 'bootstrap', config_version: cat.configVersion() });
// 后台静默同步：不更新来访记录，避免非猫窝页也算作一次「来看我」
const sync = () => call('pet', { action: 'bootstrap', config_version: cat.configVersion(), touch: false });
const update = (data = {}) => call('pet', Object.assign({ action: 'update' }, data));
const seed = () => call('pet', { action: 'seed' });
module.exports = { bootstrap, sync, update, seed };
