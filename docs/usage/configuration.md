# 配置说明

AstrBot 配置页提供启动配置和全局普通/手动推送默认值。Plugin Pages 可编辑两套推送默认值并即时应用显示设置；用户、现有订阅和会话新订阅模板也可通过[聊天命令](./commands.md)设置。

插件启动时会按 `_conf_schema.json` 对实际配置做轻量自愈：补齐缺失字段、移除废弃字段、修正常见类型错误，并把下拉选项和滑块数值收敛到合法范围。只有检测到实际变化时才会写回配置文件。

## 两套独立的推送设置

普通推送用于订阅更新；手动推送只用于 `/feed`。管理页面在普通推送下方提供独立的「手动 /feed 推送」设置，用户和订阅编辑也分别显示这两组。

| 设置 | 普通推送全局 `global_config` | 手动推送全局 `feed_defaults` |
| --- | --- | --- |
| 发送模式 | `send_mode=1` 直接发送；可改 `2` 合并转发 | 固定合并转发，不提供 `send_mode` 字段 |
| 排版 | `style=0` 自定义；可改 `2` 原始顺序 | 同左，默认 `0` |
| 内容长度 | `length_limit=0` 不限 | 同左 |
| 显示媒体、合并媒体、作者、来源、标题 | 默认启用 | 默认启用 |
| 显示 RSS 标签 | 默认禁用 | 默认禁用 |
| 监控间隔、通知 | `interval=10` 分钟、`notify=true` | 不适用 |

全局显示开关使用勾选框，保存为 `true/false`。用户和订阅的对应字段使用 **`-100` 继承、`1` 启用、`0` 禁用**，新建时默认全继承。发送模式仅接受 `1/2`，排版仅接受 `0/2`，用户和订阅同样可用 `-100` 继承。界面不再提供自动、RSSRT、仅链接或强制显示等旧选项。

手动配置在用户和订阅上使用 `feed_` 前缀：`feed_length_limit`、`feed_display_author`、`feed_display_via`、`feed_display_title`、`feed_display_entry_tags`、`feed_display_media`、`feed_style`、`feed_merge_media`。全局 `feed_defaults` 内使用不带前缀的同名字段。

## 配置范围与何时生效

| 设置位置 | 作用对象 | 实际生效时间 |
| --- | --- | --- |
| `/sub_profile set sub <ID> ...` / 订阅编辑 | 指定订阅 | 后续准备消息时读取；已入队消息不会重新排版。 |
| `/sub_profile set user ...` / 用户编辑 | 该用户不同会话中继承此字段的订阅 | 后续准备消息时读取，不覆盖订阅显式值。 |
| `/sub_session set ...` | 当前会话以后通过 `/sub` 新建的订阅 | 创建时复制到订阅字段；不更新已有订阅。 |
| Plugin Pages 全局普通/手动默认值 | 相应配置组中订阅和用户均继承的字段 | 保存后立即用于后续准备的消息；监控间隔仍需重载插件。 |
| AstrBot 插件配置 | 启动配置、网络、媒体、平台策略及默认值 | 保存后重载插件以完整生效。 |

两套继承链互不回退：

```text
普通：订阅 display_title → 用户 display_title → global_config.display_title
手动：订阅 feed_display_title → 用户 feed_display_title → feed_defaults.display_title
```

只有 `-100` 表示继承；`0` 是明确禁用。将普通 `display_title` 设为 `0` 不会关闭 `/feed` 的标题，需要修改 `feed_display_title`。会话模板只是创建时复制的订阅值，不是第四层动态继承。设置查询返回保存值，不是最终解析值。

**监控间隔规则独立：订阅正数 `interval` → 全局间隔。** 当前调度器不读取用户 `interval`。请使用 `/sub_profile set sub 12 interval 15`，或在创建订阅前 `/sub_session set interval 15`。订阅 `interval=-100` 恢复全局间隔；会话 `interval` 不能为 `-100`。

`state`、`title`、`tags` 和投递目标不属于显示选项继承链。持续启停使用 `/push`、`/unpush`；`notify=0` 会使普通自动分发跳过整条消息，不是静音通知，`/push` 不会重置它。`/feed` 是手动请求，不受 `state`、`notify` 阻挡。用户 `state`、`default_target_session` 属于保留字段，主轮询链路和聊天 `/sub` 不用它们停推或重定向目标。

## 发送模式与合并媒体

`send_mode=1` 直接发送消息；`send_mode=2` 生成真正的合并转发。合并转发目前仅支持 OneBot，其他平台会明确返回不支持，不会静默改为多条直接消息。`/feed` 固定使用合并转发，将所选 N 条及末尾汇总放入同一个转发包。

`merge_media` 决定**单条内容内部**如何组合，与是否合并转发是两个设置：启用时把该条文字和媒体放入同一直接消息或同一转发节点；禁用时按布局分别发送文字片段和媒体，或分别建立转发节点。它不修改订阅的启停状态。

直接发送时，Telegram 只支持单图/单视频配正文合成一条；QQ Official 支持单图文，但不支持多媒体或视频配正文同条；Weixin OC 不支持图文同条或多媒体同条。遇到不支持的组合会提示关闭合并媒体，关闭后按顺序分别发送。这类能力错误不自动重试。

## 排版 `style` 实际行为

`style=0` 自定义排版按「作者 → 标题 → 正文 → RSS 标签 → 来源」组合文字，随后放置媒体。`style=2` 原始顺序保留源正文中可解析的图文顺序，作者和标题放在正文前，标签和来源放在正文后。两种排版均使用同一套显示开关，不保留网页 CSS 或字体。

- `display_author` 控制独立作者段，和来源开关互不影响；`display_via` 控制文章链接与 Feed 来源后缀。
- `display_title=0` 关闭额外添加的条目标题。RSS 正文自身如果也有相同文字，会保留正文，不会误删正文内容。
- `display_entry_tags` 控制 RSS/Atom 条目自带的分类标签。源没有这些标签时不显示；订阅编辑中的管理字段 `tags` 不会补充为 RSS 标签。
- `display_media=0` 过滤媒体，保留文字。显示媒体在表单中放在长度设置后、其他显示开关前。
- `length_limit>0` 限制正文字符数，作者、标题、标签、来源不计入；原始顺序累计限制正文文本片段。

手动推送使用对应的 `feed_` 选项。例如只调整 `/feed` 的标题与媒体：

```text
/sub_profile set sub 12 feed_display_title 0
/sub_profile set sub 12 feed_display_media 1
/sub_profile set sub 12 feed_style 2
/feed 12 3
```

## 基础配置 (`basic_config`)

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `rsshub_base_url` | 默认 RSSHub 域名，用于 RSSHub 路由订阅链接拼接。 | `https://rsshub.app` |
| `minimal_interval` | 最小监控间隔，保存订阅、用户默认值和会话默认值时都会强制检查。 | `1` |
| `hash_history_min` | 去重历史最小保留数量。 | `200` |
| `hash_history_multiplier` | 去重历史增长倍数。 | `2` |
| `hash_history_hard_limit` | 去重历史硬上限。 | `5000` |
| `tracking_query_params` | 链接去重时忽略的查询参数。 | 见 schema |
| `failed_queue_capacity` | 自动失败重试队列容量，`0` 表示禁用自动重试队列但仍保留失败历史。 | `50` |
| `failed_queue_max_retries` | 自动重试链路对单条失败历史的最大尝试次数。 | `3` |
| `deduplicate_multi_bot` | 同一会话多 BOT payload 等价时压重，并写入 `skipped` 审计记录。 | `true` |
| `bootstrap_skip_history` | 首轮是否只建立去重历史、不推送旧消息。 | `true` |
| `history_entry_limit` | 历史条目推送限制，`0` 表示不限制。 | `0` |

## HTTP 网络配置 (`http_config`)

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `proxy` | RSS 拉取、普通媒体预下载和 FFmpeg 下载使用的 HTTP/SOCKS 代理。裸 `host:port` 会按 `http://host:port` 处理。 | `""` |
| `timeout` | RSS 拉取和普通 HTTP 请求超时，单位秒。 | `30` |
| `media_timeout` | 媒体预下载、m3u8/HLS 合并与 FFmpeg 下载超时，单位秒。 | `300` |

## 媒体配置 (`media`)

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `telegraph_proxy` | Telegraph API 独立代理，留空直连且不继承 `http_config.proxy`。 | `""` |
| `image_relay_base_url` | 图片预下载反代地址，支持 `https://wsrv.nl/` 或 `https://wsrv.nl/?url=`。 | `""` |
| `media_relay_base_url` | 非图片媒体或未配置图片反代时使用的通用反代地址。 | `""` |
| `media_download_concurrency` | 同一条推送内远程媒体预下载并发数，`1` 表示串行。 | `1` |
| `cache_enabled` | 启用远程媒体、表格图片、GIF/压缩 GIF 和视频 MP4 转码结果缓存；关闭后使用本次临时文件并在发送后清理。 | `true` |
| `cache_ttl_seconds` | 媒体与转码缓存 TTL，单位秒；配置页面取值范围为 `60` 到 `604800`（7 天）。 | `900` |
| `table_to_image` | HTML 表格优先渲染为图片；关闭后使用文本表格 fallback。 | `true` |
| `video_transcode` | 视频发送前自动转码为兼容 MP4。 | `false` |
| `video_transcode_timeout` | 视频转码超时时间，单位秒。 | `120` |
| `gif_transcode` | 无声视频自动转 GIF。 | `false` |
| `gif_transcode_timeout` | GIF 转码超时时间，单位秒。 | `60` |

旧版 `ffmpeg` 配置会在启动自愈时迁移到 `media`，两者同时存在时以 `media` 已有字段为准。

## 发送策略 (`sender_strategies`)

`enabled_platforms` 是平台多选列表，默认启用 `telegram`、`aiocqhttp`、`qq_official`。未选中的平台回退到默认发送器。

平台策略写入 `platform_strategies` 模板列表。当前常用字段：

| 配置项 | 作用范围 | 说明 |
| --- | --- | --- |
| `enable_telegraph` | Telegram | 保留的旧 Telegraph 策略字段；当前直接/合并模式不走自动分流。 |
| `telegraph_token` | Telegram | 保留的 Telegraph access token 配置。 |
| `telegraph_proxy` | Telegram | Telegraph createPage API 独立代理；留空直连且不继承 `http_config.proxy`，裸 `host:port` 按 `http://` 处理。 |
| `prefer_local_video` | OneBot | 覆盖默认视频来源策略；默认优先使用本地视频文件。 |
| `markdown_mode` | QQ Official | 预留 Markdown 三态配置；当前主动推送临时统一按纯文本发送。 |

发送模式不再提供自动选项；直接发送按当前平台能力投递，合并转发仅在支持的平台执行。历史 Telegraph 策略字段保留兼容，不把它作为新的发送模式。

## 旧配置兼容

当前配置版本为 `config_version=3`。启动时先迁移旧值，再按 schema 自愈；版本标记保留在隐藏配置项中，保证之后保存的 `0=禁用` 不会被反复转换。旧自动/仅链接发送迁移为直接发送，RSSRT 迁移为自定义排版。

用户和订阅数据库只在 `V3_display_profiles` 迁移中转换一次：作者、标题、标签、媒体原先 `-1` 转 `0`，原先 `0/1` 转 `1`；来源原先 `-2` 转 `0`、`-1/0/1` 转 `1`；发送模式 `-1/0` 转 `1`；排版 `1` 转 `0`，所有 `-100` 继续继承。新增 `merge_media` 及八个 `feed_` 字段默认 `-100`。这不读取或迁移旧 NB2 插件的数据。

新 TOML 导出使用版本 3。导入无版本、版本 1 或 2 的文件时按旧值含义转换；版本 3 使用当前枚举严格校验。

精简版已删除 `content_handlers`、`route_knowledge` 配置块。旧配置启动自愈后会移除这些字段，不再选择模型、人格或知识库。

用户配置、订阅配置和会话默认值不再接受 `handlers`、`handlers_mode` 或 `handler_specs`。已有会话默认值中的处理器字段会被忽略，其他基础选项继续生效。

TOML 导出仅包含基础订阅选项。导入原版 TOML 时，处理器字段会被忽略并给出提示；订阅 URL、标题、标签、发送方式和时间间隔仍可导入。
