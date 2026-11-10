# 兼容性说明

## RSS 解析

- RSS 解析优先读取 `content` 结构化正文，并兼容 `content:encoded` / `content_encoded` 字段。
- HTML `<video>`、`<audio>` 会作为结构化媒体传入发送器，正文中不会残留 `[视频]` / `[音频]` 占位。
- RSSHub 常见的 `?url=<encoded media>` 包装链接会参与媒体类型推断。
- 关闭标题显示时，正文不会因为与标题开头重复而被剔除。

## 媒体发送

- 发送前会先下载媒体到本地成功缓存，再根据本地文件头和 `filetype` 探测结果修正图片、视频、音频类型。
- 下载失败不会写入失败缓存，下一次推送会重新尝试。
- m3u8/HLS 会通过 FFmpeg 合并为 MP4，并用 ffprobe 校验视频流与时长。
- 本地图片超过平台限制时会按平台能力降级为文件、链接或文本 fallback。
- HTML 表格可按 `media.table_to_image` 渲染为图片，关闭后使用文本表格 fallback。

## 平台差异

- 普通推送的 `send_mode=1` 直接发送，`2` 合并转发；`style` 只决定排版，不再隐式切换发送方式。
- 真正的合并转发和 `/feed` 当前仅支持 OneBot；其他平台明确返回不支持。
- `merge_media=1` 时，Telegram 支持单图/单视频配正文，QQ Official 支持单图文；两者不支持多媒体同条，QQ Official 也不支持视频和正文同条。Weixin OC 不支持图文或多媒体同条组合。
- `merge_media=0` 时，Telegram、QQ Official、Weixin OC 按格式化顺序逐项发送，并保留各平台媒体候选降级。Telegram 的大图可按平台路径转为文件。
- QQ Official 当前主动推送保持纯文本，不承诺消息级 Markdown。旧 Telegraph 自动策略不是当前直接/合并模式的选择入口。

平台规则与实现边界见[平台与媒体](../project/platforms.md)。

## 升级兼容

- `minimal_interval` 是保存期硬限制，所有写入订阅、用户默认值、会话默认值的入口都不能保存更小值。
- `failed_queue_capacity=0` 只禁用自动失败重试队列，不关闭失败历史记录。
- `failed_queue_max_retries` 只控制自动重试次数；超过上限后仍保留失败历史。
- `deduplicate_multi_bot` 只在同一 `target_session` 内比较最终 payload 是否等价；命中后写入 `status=skipped` 审计记录。
- 插件启动时会补齐旧库中被订阅或推送历史引用、但缺失于 `rsshub_user` 的用户记录，避免孤儿订阅或孤儿历史。
