# 内容处理器已移除

本精简版已删除 `ContentHandlerRuntime`、`ai_filter`、`ai_transform`、Provider/人格调用及处理器配置入口。RSS 条目直接经过基础解析、清洗、格式化和平台发送；不需要配置 AI 模型。

## 旧数据库兼容

- `rsshub_sub.handlers`、`rsshub_user.handlers`、`handlers_mode` 及原版 ORM/迁移保留。
- 即使旧配置非空，inherit、override、disabled 三种模式都不会执行处理器。
- 新推送历史的 `handler_trace` 留空；已有历史与 trace 不因移除功能而擦除。
- 共用条目 DTO `EntryContentContext` 移到 `src/application/services/entry_content.py`，仅用于解析、格式化和历史上下文。

推送历史、失败重试、成功态幂等、多 BOT 去重、会话队列与媒体发送沿用原版。详见 [分发与推送历史](./dispatch.md) 和 [领域模型](./domain-model.md)。
