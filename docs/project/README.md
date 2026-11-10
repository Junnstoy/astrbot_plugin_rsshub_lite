# 项目文档

本目录记录直接基于原版裁剪后的 RSSHub 插件。AI 处理器、LLM 工具和知识库不属于运行功能。

- [项目概览](./overview.md)：定位、保留能力与裁剪边界。
- [架构](./architecture.md)：分层、启动装配和运行链路。
- [领域模型](./domain-model.md)：订阅、用户、配置继承和兼容字段。
- [应用层](./application.md)：命令、用户设置与推送历史。
- [轮询](./polling.md)：条件抓取、去重和增量识别。
- [推送分发](./dispatch.md)：发送、历史记录及重试。
- [平台与媒体](./platforms.md)：平台差异、下载、代理和缓存。
- [命令实现](./commands.md)：订阅命令与测试推送。
- [Web API](./web_api.md)：Plugin Pages 数据接口。
- [仓储](./repositories.md)：持久化、查询和幂等。
- [发送服务](./sender.md)：发送器和媒体处理。
- [格式化](./formatting.md)：文本排版和媒体顺序。
- [维护方向](./roadmap.md)：本版维护范围。

优先阅读概览和架构，再按问题查阅专题。业务语义由对应专题维护；使用方法见 [使用文档](../usage/README.md)。
