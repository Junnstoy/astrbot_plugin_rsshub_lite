# 领域值、枚举与常量归属

本文是跨模块稳定值的唯一细节来源。修改实体、DTO、配置模型、sender strategy、数据库迁移或共享常量时优先参考本文。

> [!IMPORTANT]
> 这里记录的是跨层契约。某个函数内部的实现细节、局部阈值、缓存 GC 节奏，不应为了“统一”硬塞进共享常量。

## 核心领域值速查

| 领域值 | 当前取值 | 语义 | 备注 |
| --- | --- | --- | --- |
| 配置继承标记 | `-100` | 订阅继承用户配置，用户继承全局默认 | 不恢复 `use_sub_config` / `use_user_config`。 |
| 用户状态 | `1` / `-1` | `USER_STATE_USER` / `USER_STATE_BANNED` | 旧非负状态统一视为普通用户。 |
| `send_mode` | `1` / `2` | 直接消息 / 真正合并转发 | 用户/订阅另支持 `-100`；手动 `/feed` 固定 `2`，无 feed_send_mode。 |
| `style` | `0` / `2` | 自定义排版 / 原始正文图文顺序 | 用户/订阅另支持 `-100`，不再暴露 RSSRT。 |
| 显示类字段 | 全局 bool；用户/订阅 `-100/0/1` | `display_author`、`display_via`、`display_title`、`display_entry_tags`、`display_media` | `0` 禁用、`1` 启用；`-100` 继承。 |
| `merge_media` | 同显示类字段 | 单条内容的文字媒体是否放在同一消息/转发节点 | 与 send_mode 独立，用户/订阅默认继承。 |
| 手动显示字段 | 八个 `feed_` 前缀字段，默认 `-100` | 长度、作者、来源、标题、条目标签、媒体、排版、合并媒体 | 只继承独立 feed_defaults，不回退普通字段。 |
| `source_type` | `feed` / `agent` | 当前订阅推送 / 旧版 AI 或 XML 即时推送历史 | 新建入口仅使用 `feed`；旧 `agent` 历史继续可读、可重试。 |
| `handlers_mode` | disabled / override / inherit 等 | 旧库兼容字段，不参与当前推送 | 保留原版模型与迁移，不恢复处理器配置入口。 |

配置继承关系：

```text
普通：subscription option -> user option -> global_config option
手动：subscription feed_option -> user feed_option -> feed_defaults option
```

仅显示/发送选项按这两套规则解析。订阅 `interval` 为正数时优先，否则使用全局间隔，调度器不读取用户 interval。状态、投递目标和管理 title/tags 不属于显示继承字段。

## 数据模型约束

| 对象 | 必须保持的语义 | 不要恢复 |
| --- | --- | --- |
| `rsshub_sub` | 订阅配置通过 `-100` 继承用户配置；`handlers` 仅保留旧 JSON 配置，不执行 | `use_sub_config`、旧翻译列语义、`ai_prompt`。 |
| `rsshub_user` | 用户配置通过 `-100` 继承全局默认；`handlers` 仅保留旧 JSON 配置，不执行 | `use_user_config`、插件自有 admin / guest 角色。 |
| `rsshub_user` 事实表 | 订阅或推送历史中出现的非空 `user_id` 都应有对应用户行 | 不要让订阅 / 历史长期引用缺失用户。 |
| `push_history` | 保存最终可发送文本、原始 XML、媒体上下文和失败原因；旧 `handler_trace` 列保留，新记录留空 | 不要把失败历史当成可随意丢弃的临时日志。 |

启动期数据库自愈会从订阅和推送历史补齐缺失用户。删除用户默认删除该用户订阅，但推送历史默认保留，只有显式选择时才删除。

## 旧处理器数据兼容

| 字段 / 概念 | 当前语义 | 备注 |
| --- | --- | --- |
| `rsshub_sub.handlers` | 保留旧订阅级 JSON 配置 | 不解析为运行链，不执行过滤或改写。 |
| `rsshub_user.handlers` | 保留旧用户级 JSON 配置 | 不作为处理链继承来源。 |
| `handlers_mode` | 保留旧继承、覆盖、禁用值 | 三种模式在当前推送中均不执行处理器。 |
| `handler_trace` | 保留原版历史列 | 新历史留空，旧历史不擦除。 |
| 数据库升级 | 保留原表和原迁移，增加 `V3_display_profiles` | 新增 merge_media/feed_* 列并一次转换旧显示值；旧处理器 JSON 不擦除、不执行。 |

HTML/XML 基础清洗仍属于解析与格式化链；`ai_filter`、`ai_transform` 及相应运行时、配置和工具入口已移除。

当前选项字段清单、写入验证和一次性旧值转换统一在 `src/shared/profile_options.py`。数据库升级保留 `-100`；旧显示禁用值转 `0`、自动/启用值转 `1`；旧自动/仅链接发送转 `1`，RSSRT 转自定义 `0`。全局配置和 TOML 标记为版本 3，不能把当前 `0=禁用` 重复当成旧自动值转换。完整映射见[配置兼容](../usage/configuration.md#旧配置兼容)。

## 推送历史状态与来源

| 状态 / 来源 | 语义 | 备注 |
| --- | --- | --- |
| `success` | 成功发送，参与成功态去重 | 只对成功态做幂等去重。 |
| `failed` | 发送失败，保留失败原因和媒体上下文 | 可用于人工重试和排障。 |
| `skipped` | 通知关闭、成功态去重或多 bot 等价去重压制 | 必须保留审计记录。 |
| `stopped` | 任务被停止 | 不进入自动重试。 |
| `source_type=feed` | 正常订阅轮询或测试推送 | `source_key` 应包含稳定 feed/sub 范围。 |
| `source_type=agent` | 旧版 AI tool / XML 即时推送历史 | 仅保留读取和重试兼容，不依赖公开 `sub_id`。 |

## 配置模型归属

| 文件 | 职责 |
| --- | --- |
| `src/infrastructure/config/models/plugin_config_models.py` | AstrBot 持久化配置模型。 |
| `src/infrastructure/config/models/runtime_settings.py` | 运行态设置。 |
| `src/infrastructure/config/models/sender_strategy_models.py` | sender strategy 兼容模型。 |
| `src/infrastructure/config/datamodels.py` | 兼容 re-export，不放新模型。 |

`MediaConfig` 的 `cache_enabled` / `cache_ttl_seconds` 是启动级媒体缓存配置；`settings_builder` 会把它们收敛到 `MediaPlatformLimits`，供远程媒体下载、表格图片渲染、GIF / 压缩 GIF 转码和视频 MP4 转码共用。TTL 配置面下限为 `60` 秒，运行态也保持同一下界。`media.gif_transcode_profile` 是启动级 GIF 输出档位，枚举严格限定为 `compatibility`、`balanced`、`quality`；未知值会在配置加载时明确报错，不能静默回退。具体尺寸、帧率、内存风险和缓存隔离语义见 [`platforms.md`](./platforms.md#媒体下载与缓存)。

## 常量归属

| 放置位置 | 适合内容 | 不适合内容 |
| --- | --- | --- |
| `src/shared/constants.py` | 跨 domain / application / infrastructure 共同使用的领域值；平台限制或可能随平台调整的默认策略；sender strategy 公共枚举候选；用户状态、继承值、发送模式、排版策略等稳定语义 | 单个函数内部实现细节；缓存 GC 间隔；媒体完整性最小字节数；只在单个模块内部使用且不会形成跨层契约的局部值。 |
| 具体实现或运行时设置附近 | 固定实现细节、局部运行参数、单模块私有值 | 会被多层依赖或形成持久化 / API 语义的值。 |

## 配置面边界

| 配置面 | 暴露内容 | 不属于这里 |
| --- | --- | --- |
| `_conf_schema.json` | 网络、平台 sender strategy、媒体运行配置及 global_config/feed_defaults | 用户/订阅继承选项、推送历史页业务设置。 |
| Plugin Pages | 普通和手动全局默认、用户配置、订阅配置、推送历史清理设置 | 启动级网络、credentials 和 sender 的底层 schema 定义。 |
| 配置自愈测试 | `_conf_schema.json` 字段新增、删除、类型变化时必须同步 | 不要只改 schema 而不更新自愈回归。 |

固定选择字段使用 `options`；有上下界的数字字段使用 `slider`。
