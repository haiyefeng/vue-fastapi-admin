// app.js
const { envList } = require('./envList.js');

App({
  onLaunch: function () {
    // env 参数决定云开发调用指向哪个云环境。
    // 请填入你的环境 ID：开发者工具右上角「云开发」按钮 → 复制「环境 ID」，
    // 或直接写死在这里，例如：env: "your-env-id"
    const env = (envList && envList[0] && envList[0].envId) || '';
    this.globalData = { env };

    if (!wx.cloud) {
      console.error('请使用 2.2.3 或以上的基础库以使用云能力');
    } else {
      wx.cloud.init({ env, traceUser: true });
    }
  },
});
