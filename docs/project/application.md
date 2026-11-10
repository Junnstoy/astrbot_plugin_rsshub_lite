# 应用层入口与行为边界

本文记录应用层入口、聊天命令、订阅配置与推送历史的稳定语义。它面向需要修改 `src/application/`、`src/interfaces/` 或入口编排的维护者。

> [!IMPORTANT]
> 应用层只描述入口语义和用例边界。领域值细节看 [`domain-model.md`](./domain-model.md)，平台发送差异看 [`platforms.md`](./platforms.md)。

## 聊天命令边界

以下命令需要保持完整参数签名，兼容 `GreedyStr` 风格参数。

| 命令 | 当前行为 | 不要回退 |
| --- | --- | --- |
| `/sub` | 支持多个 URL 批量订阅。 | 不要退回单 URL 语义。 |
| `/unsub` | 支持 ID 和 URL 混合批量取消。 | 不要只支持单 ID。 |
| `/sub_list` | 只展示当前会话订阅，支持分页。 | 不恢复 `all` 范围。 |
| `/sub_export [all]` | 保留管理员校验。 | 不绕过 admin guard。 |
| `/sub_import` | 支持 TOML 路径和上传等待流程。 | 不要移除上传等待监听。 |
| `/sub_test <ID\|URL>` | 真实推送最新条目，不是预览；聊天命令不接受额外范围参数。 | 不要恢复“测试推送未进入正式链路”的泛化误判。 |
| `/sub_status` | 展示当前会话运行中或排队中的推送任务。 | 不把全局队列无筛选暴露给普通用户。 |
| `/sub_stop [job_id\|feed_id\|all]` | 支持精确停止和批量停止；无参数时停止当前运行任务。 | 不让停止语义绕过审计。 |
| `/rsshelp` | 发送预生成帮助图；按 AstrBot `timezone` 选择日间/夜间主题，读不到或时区非法时回退系统本地时间。 | 不把帮助图生成放到运行时热路径。 |

命令解析细节见 [`commands.md`](./commands.md)。

## 已移除的 AI 入口

插件不再注册 LLM tools，不执行内容处理器，不调用 Provider，也不创建或同步 RSSHub Routes 知识库。XML 即时推送工具与对应新建入口已移除。

旧库中 `source_type=agent` 的推送历史仍保留读取和重试能力：使用历史记录中的目标及媒体上下文直接重发，不再执行 AI。非空 `handlers` / `handlers_mode` 只作数据兼容保留；新推送的 `handler_trace` 为 `None`。

## 订阅、用户与历史语义

| 主题 | 当前语义 | 备注 |
| --- | --- | --- |
| 配置继承 | 订阅继承用户，用户继承全局默认；继承值只认 `-100` | 不恢复 `use_sub_config` / `use_user_config`。 |
| 旧处理器字段 | 原版数据库字段与迁移保留，现有 JSON 配置不再执行 | 聊天命令、Web UI 和 TOML 不提供处理器配置入口。 |
| 旧翻译字段 | `translate`、`translate_target_lang` 保持移除 | 翻译不再是应用层内置入口。 |
| `minimal_interval` | 写入阶段硬下限 | 不要降级成运行时临时 clamp。 |
| 用户事实表 | 写入订阅或推送历史前必须确保非空 `user_id` 有用户记录 | 启动自愈会从订阅和历史补齐缺失用户。 |
| 删除用户 | 默认删除用户和该用户全部订阅 | 推送历史默认保留，显式 `delete_push_history=true` 才删除。 |

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
