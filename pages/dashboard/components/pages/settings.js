import { pushSettingsTemplate } from '../shared/push-settings.js';

export const settingsPageTemplate = String.raw`
      <section v-if="activeTab === 'settings'" class="settings-shell narrow-page">
        <div v-if="pluginSettingsLoading" class="empty-state"><p>加载中...</p></div>
        <div v-else class="settings-scroll-area">
          <div class="settings-form">
            <div class="panel-section">
              <h4>全局默认设置</h4>
              <div class="setting-row"><span class="setting-label">默认监控间隔（分钟）</span><div class="input-wrapper" style="max-width:120px;"><input type="number" v-model.number="subscriptionDefaults.interval" min="1" max="1440" /></div></div>
              <div class="setting-row"><span class="setting-label">默认通知</span><label class="toggle-switch"><input type="checkbox" v-model="subscriptionDefaults.notify" /><span class="toggle-slider"></span></label></div>
            </div>
            ${pushSettingsTemplate('subscriptionDefaults', { inherited: false })}
            ${pushSettingsTemplate('feedDefaults', { inherited: false, feed: true })}
            <div class="form-actions">
              <button class="btn btn-primary" :class="{ 'is-loading': isPending('plugin-settings:save') }" :disabled="isPending('plugin-settings:save')" @click="savePluginSettings()">保存插件设置</button>
            </div>
          </div>
        </div>
      </section>

`;
