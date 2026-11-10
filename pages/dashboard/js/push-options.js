// Shared contract for global defaults and inherited user/subscription forms.
export const displayOptions = [
  ['display_media', '显示媒体'],
  ['merge_media', '合并媒体'],
  ['display_author', '显示作者'],
  ['display_via', '显示来源'],
  ['display_title', '显示标题'],
  ['display_entry_tags', '显示 RSS 标签'],
];

export const displayFields = ['length_limit', ...displayOptions.map(([key]) => key), 'style'];
export const pushFields = ['send_mode', ...displayFields, ...displayFields.map((key) => `feed_${key}`)];

export function createDisplayDefaults() {
  return {
    length_limit: 0,
    display_media: true,
    merge_media: true,
    display_author: true,
    display_via: true,
    display_title: true,
    display_entry_tags: false,
    style: 0,
  };
}
