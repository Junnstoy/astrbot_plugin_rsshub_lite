# 应用层入口与行为边界

本文记录应用层入口、聊天命令、订阅配置与推送历史的稳定语义。它面向需要修改 `src/application/`、`src/interfaces/` 或入口编排的维护者。

> [!IMPORTANT]
> 应用层只描述入口语义和用例边界。领域值细节看 [`domain-model.md`](./domain-model.md)，平台发送差异看 [`platforms.md`](./platforms.md)。

## 聊天命令边界

需要接收整段文本的入口使用 AstrBot 真正的 `GreedyStr`，且不为该参数添加 `=""` 默认值。宿主参数分配器会优先走默认值分支，`args: str = ""` 或带默认值的 `GreedyStr` 都可能只收到第一个 token；纯函数 handler 测试无法发现这一集成问题。

| 命令 | 当前行为 | 不要回退 |
| --- | --- | --- |
| `/sub` | 支持多个 URL/RSSHub 路由；将当前会话 KV 默认值传给新建命令。 | 路由使用配置的 RSSHub base；重复订阅不重套模板。 |
| `/unsub` | 支持 ID 和 URL 混合批量取消。 | 不要只支持单 ID。 |
| `/sub_list [page] [page_size]` | 只展示当前用户、当前会话订阅；默认页码 1、每页 5 条，每页允许 1～100。 | 保留两个参数的完整解析，ID 是方括号中的订阅 ID。 |
| `/push`、`/unpush` | 当前用户、当前会话内，以订阅 ID/逗号列表/显式 `all` 持久化启停。停用时取消可归属所选订阅的任务。 | 新命令空参数不修改数据；不以 Feed ID 取消其他用户的任务。 |
| `/feed <订阅ID> <N>` | 管理员读取当前会话订阅源，按有效发布时间降序选择最多 N 条，与末尾汇总组成一个合并转发包；不足时发全部并提示。 | 不改变订阅开关、Feed 游标、去重水位或自动历史；继承订阅及所有者的 feed_* 显示设置；固定合并转发。 |
| `/sub_export [all]` | 保留管理员校验。 | 不绕过 admin guard。 |
| `/sub_import` | 支持 TOML 路径和上传等待流程。 | 不要移除上传等待监听。 |
| `/sub_test <ID\|URL>` | 真实推送最新条目，不是预览；聊天命令不接受额外范围参数。 | 不要恢复“测试推送未进入正式链路”的泛化误判。 |
| `/push_status` | 展示当前会话运行中或排队中的推送任务；`sub_status` 保留别名。 | 任务为空不表示自动推送已停用，订阅状态查看 `/sub_list`。 |
| `/push_cancel [job_id\|feed_id\|all]` | 支持精确取消和批量取消；无参数取消当前运行任务；`sub_stop` 保留别名。 | 不改订阅状态，不等同 `/unpush`；队列取消只能作用于已登记的任务。 |
| `/rsshelp` | 发送预生成帮助图；按 AstrBot `timezone` 选择日间/夜间主题，读不到或时区非法时回退系统本地时间。 | 不把帮助图生成放到运行时热路径。 |

保留 `sub_state` 兼容入口。持续推送统一使用 `push`、`unpush`，要求明确指定订阅 ID 或 `all`；无参数不修改数据。命令用法见 [`commands.md`](../usage/commands.md)。

`PushFeedCommand` 使用 `fetch_feed_entries` 读端口、`EntryTextFormatter.format_layout` 和 `send_entries_to_session`，将 N 条及末尾汇总一次入队。手动请求不受订阅 `state` 或 `notify` 阻挡，不持久化推送历史，因此可重复发送、没有自动失败重试，也不会让后续自动推送误判已送达。无有效时间的条目放在有时间的条目后；等时和无时间条目保持源顺序。合并转发目前只在 OneBot 支持，其他平台返回不支持；整批取消仅作用于已入队任务，抓取和排版阶段尚无队列任务。

## 已移除的 AI 入口

插件不再注册 LLM tools，不执行内容处理器，不调用 Provider，也不创建或同步 RSSHub Routes 知识库。XML 即时推送工具与对应新建入口已移除。

旧库中 `source_type=agent` 的推送历史仍保留读取和重试能力：使用历史记录中的目标及媒体上下文直接重发，不再执行 AI。非空 `handlers` / `handlers_mode` 只作数据兼容保留；新推送的 `handler_trace` 为 `None`。

## 订阅、用户与历史语义

| 主题 | 当前语义 | 备注 |
| --- | --- | --- |
| 发送配置继承 | 订阅 → 用户 → 对应全局默认，逐字段解析且仅 `-100` 继承 | 普通字段使用 global_config；feed_* 字段使用 feed_defaults，绝不回退到普通字段。state、interval、管理title/tags和目标不在显示继承链。 |
| 会话默认值 | `rsshub_session_defaults_<unified_msg_origin>` 插件 KV；只在 `/sub` 新建时复制到订阅 | 模板不是第四层动态继承，不覆盖已有订阅；模板显式值会遮蔽用户默认值。 |
| 调度间隔 | 正数订阅 interval 优先，否则全局默认间隔 | `RSSScheduler._load_due_subscriptions` 不查询 UserORM，用户 interval 不参与调度。 |
| 设置生效 | 用户与订阅选项后续准备时读取；全局显示默认通过 apply_defaults 热更新 | 监控间隔仍为 scheduler 启动快照；已入队消息不重新排版。 |
| 配置查询 | profile get user 返回保存值；session get 返回模板值 | 不是针对某个订阅计算后的最终值；没有 profile get sub 命令。 |
| 旧处理器字段 | 原版数据库字段与迁移保留，现有 JSON 配置不再执行 | 聊天命令、Web UI 和 TOML 不提供处理器配置入口。 |
| 旧翻译字段 | `translate`、`translate_target_lang` 保持移除 | 翻译不再是应用层内置入口。 |
| `minimal_interval` | 写入阶段硬下限 | 不要降级成运行时临时 clamp。 |
| 用户事实表 | 写入订阅或推送历史前必须确保非空 `user_id` 有用户记录 | 启动自愈会从订阅和历史补齐缺失用户。 |
| 删除用户 | 默认删除用户和该用户全部订阅 | 推送历史默认保留，显式 `delete_push_history=true` 才删除。 |

订阅 `state=0/1` 控制定时调度；`notify=0` 在分发阶段写 `skipped`，不会取消已准备的任务，`push` 也不会强制覆盖它。用户 `state`、`default_target_session` 可保存但当前主轮询与聊天 `/sub` 不读取它们进行停推或目标绑定；投递目标来自订阅自身的 `target_session`、`platform_name`。不要把用户状态与 AstrBot 管理员权限混用。

## 格式化、发送模式和媒体组合

`NotificationDispatcher._resolve_effective_push_options(profile="push"|"feed")` 解析两套独立显示字段，`_resolve_send_mode` 仅解析普通发送模式。`apply_defaults(subscription_defaults, feed_defaults)` 更新两套运行时默认值；Web API 持久化后直接调用该方法。

普通 `send_mode=1/2` 对应直接消息/合并转发；手动 `/feed` 固定 `2`，无 feed_send_mode。合并转发仅 OneBot 支持，其他平台明确返回不支持，不静默降级。`merge_media=1` 将单条 entry 的文字媒体放入同一消息或 Node；`0` 按片段拆分消息/Node，与 send_mode 相互独立。

`EntryTextFormatter.format_layout` 为两种 style 统一应用 bool 显示开关。自定义 `0` 输出作者、标题、清洗后的正文、源条目标签和来源，再附媒体；原始 `2` 在作者/标题与标签/来源之间保留可解析的正文图文顺序。源无元数据时不生成内容。`display_title=0` 只隐藏额外标题，不删除正文中可能相同的文字；`display_via=0` 不再连带隐藏作者。

全局 display_*、merge_media 使用 bool；用户/订阅使用 `-100/0/1`。`length_limit` 只作用于正文，原始顺序累计限制正文文本片段；关闭媒体过滤媒体片段而保留文字。RSS 条目标签来自 Entry.tags，订阅 tags 是独立管理元数据。RSSRT、自动发送和仅链接选项退出当前配置契约，旧值在存储兼容层迁移。

## 推送历史与重试

| 行为 | 当前语义 | 备注 |
| --- | --- | --- |
| `PushHistory.fail_reason` | 必须保持在模型和数据库限制内，当前上限为 512 字符 | 仓储读取历史脏数据时要能截断过长失败原因。 |
| `failed_queue_capacity=0` | 只关闭自动失败队列捞取 | 不影响失败历史写入和保留。 |
| `failed_queue_max_retries` | 只控制自动重试次数上限 | 不代表可以删除失败历史。 |
| Plugin Pages 手动重试 | 复用同一条 `push_history`，更新结果和最近活动时间 | 不新增历史行，不消耗自动重试次数。 |
| `deduplicate_multi_bot` | 只在同一 `target_session` 且最终 payload 等价时去重 | 被压制的发送必须写入 `status=skipped`。 |
| 规则性跳过 | 通知关闭、成功去重 guard、多 BOT 去重都写入 `status=skipped` | 这类 skipped 是可审计 ack；不能伪装成 success。 |
| Feed 水位确认 | 只有 `success` 或明确规则性 `skipped` 会确认本轮新 entry | `pending`、`failed` 或分发异常不能推进 `entry_hashes` / 条件请求水位，避免漏推。 |

## 已移除的应用能力

| 能力 | 当前状态 | 替代路径 |
| --- | --- | --- |
| 所有 LLM tools（含 route-search、route-build、订阅与 XML 即时推送） | 已移除 | 使用 `/sub` 等聊天命令；RSSHub 路由可直接作为订阅目标。 |
| 翻译、AI 过滤与 AI 改写 | 已移除 | 保留原始 RSS/Atom/JSON Feed 的解析、清洗与格式化。 |
| AI enrich / summarize、处理器配置与知识库同步 | 已移除 | 无 AI 配置或 Provider 依赖；数据库兼容字段不执行。 |
| Plugin Pages 新建订阅、TOML 导入、TOML 导出 | 不恢复 | 用户归属流程保留在聊天命令。 |
