# 项目概览

`astrbot_plugin_rsshub` 精简版直接基于原版 AstrBot 插件裁剪，保留订阅、抓取、去重、定时推送、多平台消息发送和管理界面，不注册 LLM 工具、不执行内容处理器，也不访问 AstrBot 知识库。

## 保留的基础能力

- RSS、Atom、JSON Feed 抓取与条件请求，按订阅间隔调度。
- 按用户和目标会话管理订阅，支持启停、批量操作、测试推送及 TOML 导入导出。
- 用户/订阅默认配置和 `-100` 继承语义。
- 文本与图片、音视频等媒体发送，沿用原版平台发送策略和缓存。
- 推送历史、失败重试、多 BOT 去重和发送队列。
- Plugin Pages 中的订阅、用户、Feed、历史、默认设置及数据管理。

## 使用入口

新增订阅、导入导出和测试推送由聊天命令完成；Plugin Pages 管理已有数据并提供排障信息。命令与页面共用原版应用层和仓储层。

基础命令见 [命令说明](../usage/commands.md)，启动配置见 [配置说明](../usage/configuration.md)。

## 裁剪与兼容边界

内容处理器、AI 过滤/改写、LLM 工具、Routes 知识库及其配置、命令和页面入口已移除。推送使用 RSS 原始内容经过普通 HTML 解析与排版，不进行模型生成。

数据库保留旧处理器字段的兼容结构，避免破坏已有订阅和历史数据；这些字段不参与推送执行。旧启动配置中的 `content_handlers`、`route_knowledge` 由配置自愈移除，旧会话默认值及 TOML 中的处理器选项被忽略，新导出不携带处理器配置。

本版保留原版 `domain`、`application`、`infrastructure`、`interfaces` 分层及 `bootstrap.py` 启动装配方式，主要改动集中在移除能力的装配、接口和执行步骤。

## 维护参考

- [架构与运行链路](./architecture.md)
- [领域模型及配置语义](./domain-model.md)
- [应用层和命令边界](./application.md)
- [推送与重试](./dispatch.md)
- [平台、媒体和缓存](./platforms.md)
