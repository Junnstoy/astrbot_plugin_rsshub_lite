import assert from 'node:assert/strict';
import test from 'node:test';

import { createDashboardStore } from '../../pages/dashboard/store/index.js';
import { dashboardTemplate } from '../../pages/dashboard/components/dashboard-template.js';
import { displayFields, pushFields } from '../../pages/dashboard/js/push-options.js';
import { createInheritedPushForm, inheritedPushToPayload } from '../../pages/dashboard/store/helpers.js';
import { pushSettingsTemplate } from '../../pages/dashboard/components/shared/push-settings.js';

test('基础编辑保留用户归属和显示配置，不从旧数据回写处理链', async () => {
  const calls = [];
  globalThis.window = {
    AstrBotPluginPage: {
      apiPost: async (path, payload) => {
        calls.push({ path, payload });
        return { ok: true };
      },
    },
  };
  const store = createDashboardStore({ reactive: (value) => value });
  store.runPending = async (_key, operation) => operation();
  store.showToast = () => {};
  store.loadData = async () => {};
  store.loadUsers = async () => {};
  store.openEditPanel({
    id: 8, feed_id: 2, user_id: 'alice', state: 1, interval: 15,
    title: '新闻', display_media: 0, handlers_mode: 'override',
    handlers: [{ name: 'ai_filter' }],
  });
  await store.handleEditSub();
  assert.equal(calls[0].path, 'subscriptions/update');
  assert.equal(calls[0].payload.user_id, 'alice');
  assert.equal(calls[0].payload.options.interval, 15);
  assert.equal(calls[0].payload.options.display_media, 0);
  assert.equal('handlers' in calls[0].payload.options, false);
  assert.equal('handlers_mode' in calls[0].payload.options, false);

  store.openUserEditPanel({ user_id: 'alice', interval: 20, handlers: [{ name: 'ai_filter' }] });
  await store.handleSaveUserEdit();
  assert.equal(calls[1].path, 'users/update');
  assert.equal(calls[1].payload.user_id, 'alice');
  assert.equal('handlers' in calls[1].payload.settings, false);
  delete globalThis.window;
});

test('管理导航保留基础入口，导出预览保持独立样式', () => {
  for (const label of ['订阅列表', '用户', 'Feed 源', '推送历史', '默认订阅设置', '数据管理']) {
    assert.ok(dashboardTemplate.includes(label));
  }
  assert.doesNotMatch(dashboardTemplate, /内容处理链|知识库|handlers_json|historyTraceSteps/);
  assert.match(dashboardTemplate, /export-preview-content/);
  assert.doesNotMatch(dashboardTemplate, /RSSRT|仅链接|>自动<|>强制</);
});

test('普通与手动配置独立继承，默认表单不覆盖上层', () => {
  const form = createInheritedPushForm();
  assert.deepEqual(inheritedPushToPayload(form), Object.fromEntries(pushFields.map((key) => [key, -100])));
  const edited = createInheritedPushForm({ display_media: 0, feed_display_media: 1, merge_media: 1, feed_merge_media: 0 });
  edited.feed_length_limit_control = { mode: 'custom', value: 700 };
  const payload = inheritedPushToPayload(edited);
  assert.equal(payload.display_media, 0);
  assert.equal(payload.feed_display_media, 1);
  assert.equal(payload.merge_media, 1);
  assert.equal(payload.feed_merge_media, 0);
  assert.equal(payload.length_limit, -100);
  assert.equal(payload.feed_length_limit, 700);
});

test('用户与订阅保存完整的普通和手动字段', async () => {
  const calls = [];
  globalThis.window = { AstrBotPluginPage: { apiPost: async (path, payload) => { calls.push({ path, payload }); return { ok: true }; } } };
  try {
    const store = createDashboardStore({ reactive: (value) => value });
    store.runPending = async (_key, operation) => operation();
    store.showToast = () => {};
    store.loadData = store.loadUsers = async () => {};
    const fields = { send_mode: 2, style: 0, merge_media: 0, feed_style: 2, feed_merge_media: 1, feed_display_title: 0, feed_display_entry_tags: 1 };
    store.openEditPanel({ id: 12, user_id: 'alice', state: 1, ...fields });
    await store.handleEditSub();
    store.openUserEditPanel({ user_id: 'alice', ...fields });
    await store.handleSaveUserEdit();
    for (const payload of [calls[0].payload.options, calls[1].payload.settings]) {
      for (const [key, value] of Object.entries(fields)) assert.equal(payload[key], value, key);
      for (const key of pushFields) assert.ok(key in payload, key);
      assert.equal(payload.feed_length_limit, -100);
      assert.equal('feed_send_mode' in payload, false);
    }
  } finally { delete globalThis.window; }
});

test('全局两组配置加载和保存保留false，手动组没有发送模式', async () => {
  const calls = [];
  globalThis.window = { AstrBotPluginPage: {
    apiGet: async () => ({ ok: true, subscription_defaults: { send_mode: 2, display_title: false }, feed_defaults: { display_media: false, merge_media: false, style: 2 } }),
    apiPost: async (path, payload) => { calls.push({ path, payload }); return { ok: true, ...payload }; },
  } };
  try {
    const store = createDashboardStore({ reactive: (value) => value });
    store.runPending = async (_key, operation) => operation();
    store.showToast = () => {};
    assert.equal(store.subscriptionDefaults.send_mode, 1);
    assert.equal(store.subscriptionDefaults.style, 0);
    await store.loadSettings();
    await store.savePluginSettings();
    const { subscription_defaults: normal, feed_defaults: manual } = calls[0].payload;
    assert.equal(normal.display_title, false);
    assert.equal(normal.send_mode, 2);
    assert.equal(manual.display_media, false);
    assert.equal(manual.merge_media, false);
    assert.equal(manual.style, 2);
    assert.deepEqual(Object.keys(manual).sort(), [...displayFields].sort());
  } finally { delete globalThis.window; }
});

test('全局显示开关使用checkbox，继承表单使用三态且媒体排在作者之前', () => {
  const global = pushSettingsTemplate('feedDefaults', { inherited: false, feed: true });
  const inherited = pushSettingsTemplate('editForm', { feed: true });
  assert.equal((global.match(/type="checkbox"/g) || []).length, 6);
  assert.doesNotMatch(global, /send_mode|:value="-100"/);
  assert.match(inherited, /v-model.number="editForm.feed_display_media"/);
  assert.match(inherited, /:value="0">禁用/);
  assert.match(inherited, /:value="1">启用/);
  assert.match(inherited, /:value="-100">继承/);
  assert.ok(inherited.indexOf('feed_display_media') < inherited.indexOf('feed_display_author'));
  assert.ok(inherited.indexOf('feed_length_limit') < inherited.indexOf('feed_display_media'));
});
