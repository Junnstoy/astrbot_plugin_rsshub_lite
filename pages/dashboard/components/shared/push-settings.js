import { displayOptions } from '../../js/push-options.js';

function selectRow(model, key, label, options, inherited) {
  const values = inherited ? [[-100, '继承'], ...options] : options;
  return `<div class="setting-row"><label class="setting-label" for="${model}-${key}">${label}</label><select id="${model}-${key}" class="select-input" v-model.number="${model}.${key}">${values.map(([value, title]) => `<option :value="${value}">${title}</option>`).join('')}</select></div>`;
}

function numberRow(model, key, inherited) {
  const id = `${model}-${key}`;
  if (!inherited) {
    return `<div class="setting-row"><label class="setting-label" for="${id}">内容长度限制</label><div class="input-wrapper" style="max-width:120px;"><input id="${id}" type="number" v-model.number="${model}.${key}" min="0" max="10000" /></div></div>`;
  }
  return `<div class="setting-row"><label class="setting-label" for="${id}">内容长度限制</label><div class="inherit-control"><select id="${id}" class="select-input" v-model="${model}.${key}_control.mode"><option value="inherit">继承</option><option value="custom">自定义</option></select><div v-if="${model}.${key}_control.mode === 'custom'" class="input-wrapper"><input aria-label="内容长度限制数值" type="number" v-model.number="${model}.${key}_control.value" min="0" max="10000" /></div></div></div>`;
}

export function pushSettingsTemplate(model, { inherited = true, feed = false } = {}) {
  const prefix = feed && inherited ? 'feed_' : '';
  const fields = displayOptions.map(([key, label]) => {
    const field = `${prefix}${key}`;
    if (inherited) return selectRow(model, field, label, [[1, '启用'], [0, '禁用']], true);
    return `<div class="setting-row"><label class="setting-label" for="${model}-${field}">${label}</label><label class="toggle-switch"><input id="${model}-${field}" type="checkbox" v-model="${model}.${field}" /><span class="toggle-slider"></span></label></div>`;
  });
  return `
    <div class="panel-section push-settings-group" data-push-group="${feed ? 'feed' : 'normal'}">
      <h4>${feed ? '手动 /feed 推送' : '普通推送'}</h4>
      <p class="setting-help">${feed ? (inherited ? '仅用于 /feed，固定合并转发；独立继承手动推送默认值。' : '仅用于 /feed，固定合并转发，与普通推送配置独立。') : '用于订阅更新的自动推送。'}合并转发目前仅支持 OneBot。</p>
      ${feed ? '' : selectRow(model, 'send_mode', '发送模式', [[1, '直接发送'], [2, '合并转发']], inherited)}
      ${numberRow(model, `${prefix}length_limit`, inherited)}
      ${fields.join('\n')}
      ${selectRow(model, `${prefix}style`, '排版', [[0, '自定义'], [2, '原始顺序']], inherited)}
      <p class="setting-help">长度 0 表示不限。RSS 标签来自源条目的分类，与订阅管理标签无关。合并媒体将一条内容的文字与媒体放在同一消息或转发节点中；禁用时分别发送。</p>
    </div>`;
}
