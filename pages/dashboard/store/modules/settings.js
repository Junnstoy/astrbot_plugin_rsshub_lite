import {
  getPluginSettings,
  setPluginSettings
} from '../../js/api.js';

export const settingsModule = {
  async loadSettings() {
    this.pluginSettingsLoading = true;
    try {
      const pluginResult = await getPluginSettings();
      if (pluginResult.history_retention_days !== undefined) {
        this.historyRetentionDays = Number(pluginResult.history_retention_days) || 30;
      }
      if (pluginResult.feed_defaults) {
        this.feedDefaults = { ...this.feedDefaults, ...pluginResult.feed_defaults };
      }
      if (pluginResult.subscription_defaults) {
        this.subscriptionDefaults = {
          ...this.subscriptionDefaults,
          ...pluginResult.subscription_defaults,
        };
      }
    } catch (err) {
      this.showToast(`加载设置失败: ${err.message}`, 'error');
    } finally {
      this.pluginSettingsLoading = false;
    }
  },

  async savePluginSettings() {
    await this.runPending('plugin-settings:save', async () => {
      const result = await setPluginSettings({
        subscription_defaults: this.subscriptionDefaults,
        feed_defaults: this.feedDefaults,
        history_retention_days: this.historyRetentionDays,
      });
      if (result.history_retention_days !== undefined) {
        this.historyRetentionDays = Number(result.history_retention_days) || 30;
      }
      if (result.feed_defaults) {
        this.feedDefaults = { ...this.feedDefaults, ...result.feed_defaults };
      }
      if (result.subscription_defaults) {
        this.subscriptionDefaults = {
          ...this.subscriptionDefaults,
          ...result.subscription_defaults,
        };
      }
      this.showToast(result.message || '插件设置已保存');
    }).catch((err) => {
      this.showToast(`保存插件设置失败: ${err.message}`, 'error');
    });
  }
};
