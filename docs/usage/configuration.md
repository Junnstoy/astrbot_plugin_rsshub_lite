# 配置说明

AstrBot 配置页只保留启动级基础设施配置、媒体配置和平台发送策略。全局订阅默认值在 Plugin Pages 的默认设置中维护；用户、现有订阅和会话新订阅模板也可以通过[聊天命令](./commands.md)设置。

插件启动时会按 `_conf_schema.json` 对实际配置做轻量自愈：补齐缺失字段、移除废弃字段、修正常见类型错误，并把下拉选项和滑块数值收敛到合法范围。只有检测到实际变化时才会写回配置文件。

## 配置范围与何时生效

| 设置位置 | 作用对象 | 实际生效时间 |
| --- | --- | --- |
| `/sub_profile set sub <ID> ...` / 管理页订阅编辑 | 指定订阅 | 后续分发读取；已进入队列的消息不会重新排版。 |
| `/sub_profile set user ...` / 管理页用户编辑 | 该用户不同会话中仍继承此字段的订阅 | 后续分发读取，不覆盖订阅上的显式值。 |
| `/sub_session set ...` | 当前会话以后通过 `/sub` 新建的订阅 | 创建时复制到订阅字段；不更新已有订阅，也不是动态继承层。 |
| Plugin Pages 全局默认设置 | 订阅和用户均继承的字段 | 保存后重载插件；发送器和调度器持有启动时构建的默认值。 |
| AstrBot 插件配置 | 网络、媒体、调度基础设施、平台策略 | 保存后重载插件以完整生效。 |

发送时，`notify`、`send_mode`、`length_limit`、`display_*`、`style` 逐字段按 **订阅 → 用户 → 全局默认** 查找。只有 `-100` 表示继承，`0` 是具体值。例如用户设 `style=2`，订阅设 `style=-100`，本次使用 `2`；若订阅设 `style=0`，本次使用 `0`。

会话模板先复制到新订阅，再参与上述规则。例如会话设 `style=2`，新订阅就会保存显式的 `2`，不会跟随用户之后的 `style` 变化。要恢复跟随，执行 `/sub_profile set sub <ID> style -100`。同一群的会话模板属于会话，用户默认值属于发送者，两者的范围不同。

**监控间隔有独立规则：订阅正数 `interval` → 全局间隔（默认 10 分钟）。** 当前调度器不读取用户 `interval`，即使用户配置中保存了该字段也不改变抓取频率。请使用 `/sub_profile set sub 12 interval 15`，或者在创建订阅前 `/sub_session set interval 15`。订阅 `interval=-100` 恢复全局间隔；会话 `interval` 不能为 `-100`。

`state`、`title`、`tags`、目标会话和平台都不属于发送选项继承链。持续启停使用 `/push`、`/unpush`；`notify=0` 会使自动分发跳过整条消息，不是静音通知，也不会取消已入队任务。`/push` 不会重置 `notify`。用户的 `state`、`default_target_session` 目前只是可保存的原版字段，主轮询链路和聊天 `/sub` 不用它们停推或重定向目标。

## 排版 `style` 实际行为

| 值 / 管理页名称 | 当前实现 |
| --- | --- |
| `0` / 自动 (`auto`) | 清洗 HTML，组成标题、正文、条目标签和来源后缀，再由平台发送器安排图文、媒体和消息分段。不会保持 HTML 中所有图文位置。 |
| `1` / RSSRT (`rssrt`) | 保留的兼容选项。目前 formatter 和 sender 没有 RSSRT 专用分支，与自动使用相同排版链路，不会额外启用另一套模板。 |
| `2` / 原始顺序 (`original`) | 在支持的平台，使用解析出的 HTML 文本/媒体片段顺序发送；保留内容顺序，不保留网页 CSS、字体或原网页视觉样式。 |

普通排版把标题、正文、标签和 `via` 来源拼成正文，再处理媒体。基础组件排序为图片、视频、音频、文件、文本，各平台仍会做消息链、合并转发、图片说明或降级处理；例如 OneBot 普通发送走合并转发，Telegram 自动模式可能转到 Telegraph。`style` 与 `send_mode` 是两个不同选项。

原始顺序目前由 **OneBot、QQ Official、Weixin** 的专用发送器实现，要求解析结果中有布局片段。Telegram 和默认发送器没有原始顺序分支，仍使用普通链路；平台回退到默认发送器或没有布局时也不能保证原始顺序。OneBot、QQ Official 可把图片与其后紧随的文本组合，Weixin 按片段分别发送。

显示开关的边界：

- 普通排版中，`display_title=-1` 隐藏标题；作者、标题的 `0` 与 `1` 都显示已有数据，缺失内容不会生成。`display_entry_tags=-1` 隐藏源条目标签，`0` 显示；订阅管理字段 `tags` 不会成为源条目标签。
- `display_via=-1` 只保留文章链接、不带 Feed 来源名；`-2` 移除整个来源后缀，也隐藏该后缀中的作者。`display_author=-1` 单独隐藏作者。
- `length_limit>0` 在普通排版中限制正文字符数，标题和来源后缀不计入；原始顺序则累计限制布局中的文本片段，媒体保留。
- 原始顺序直接发送 HTML 布局，通常不包含 formatter 额外拼接的标题、标签、作者或 `via` 后缀；`display_title` 等选项不能保证与普通排版得到相同外观。
- `display_media=-1` 会清除媒体和原始布局，改走文本链路；`send_mode=-1` 会直接只发条目标题和链接，忽略媒体及原始布局。

可在当前会话选一个订阅比较：

```text
/sub_profile set sub 12 style 0
/feed 12 1
/sub_profile set sub 12 style 2
/feed 12 1
```

`/feed` 需要 AstrBot 管理员权限，允许重复发送当前源内容。若仅切换 `style=1`，当前实现不会出现区别于 `style=0` 的专用模板。

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
| `enable_telegraph` | Telegram | 启用 Telegraph 自动分流。 |
| `telegraph_token` | Telegram | Telegraph access token；启用自动分流时必填。 |
| `telegraph_proxy` | Telegram | Telegraph createPage API 独立代理；留空直连且不继承 `http_config.proxy`，裸 `host:port` 按 `http://` 处理。 |
| `prefer_local_video` | OneBot | 覆盖默认视频来源策略；默认优先使用本地视频文件。 |
| `markdown_mode` | QQ Official | 预留 Markdown 三态配置；当前主动推送临时统一按纯文本发送。 |

Telegraph 不是显式 `send_mode`。它只在 Telegram 自动发送策略中触发：自动发送、Telegram 策略启用 Telegraph、token 有效，且去重后的媒体条目数大于 1。

## 旧配置兼容

精简版已删除 `content_handlers`、`route_knowledge` 配置块。旧配置启动自愈后会移除这些字段，不再选择模型、人格或知识库。

用户配置、订阅配置和会话默认值不再接受 `handlers`、`handlers_mode` 或 `handler_specs`。已有会话默认值中的处理器字段会被忽略，其他基础选项继续生效。

TOML 导出仅包含基础订阅选项。导入原版 TOML 时，处理器字段会被忽略并给出提示；订阅 URL、标题、标签、发送方式和时间间隔仍可导入。
