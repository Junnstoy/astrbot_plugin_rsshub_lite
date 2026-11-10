# RSSHub Routes 知识库同步已移除

本精简版不再提供知识库初始化、文档同步、Embedding/Rerank Provider 配置、同步任务或知识库管理页面。对应 `/rsshub_kb_*` 命令、后台服务及 LLM tools 均已移除。

RSSHub 路由仍可直接通过 `/sub` 订阅；RSS/Atom/JSON Feed 抓取、订阅管理和定时推送不依赖知识库。相关操作见 [聊天命令](./commands.md)。

移除插件中的知识库功能不会自动删除 AstrBot 中已有的知识库。数据库兼容与旧推送历史的保留边界见 [领域模型](./domain-model.md)。本页保留作为旧文档链接的移除说明，不再描述可执行的同步流程。
