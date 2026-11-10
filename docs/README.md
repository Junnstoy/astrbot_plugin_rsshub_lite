# RssHub lite 文档

RssHub lite 保留原版 AstrBot RSSHub 插件的基础订阅推送功能，移除处理器、LLM 工具和知识库能力。安装入口见 [README](../README.md)，来源与许可见 [NOTICE](../NOTICE.md)。

## 使用

1. [命令说明](./usage/commands.md)：新增订阅、启停、测试推送、TOML 导入导出。
2. [配置说明](./usage/configuration.md)：RSSHub 地址、网络、媒体和平台策略。
3. [管理页面](./usage/plugin-pages.md)：订阅、Feed、用户和推送历史管理。
4. [兼容性](./usage/compatibility.md)：RSS 和平台差异。

## 项目与维护

- [项目概览](./project/overview.md)：保留能力、裁剪边界和旧数据兼容。
- [项目文档索引](./project/README.md)：架构、领域、轮询、发送、仓储和接口。
- [当前维护范围](./PLAN.md)：基础功能与回归检查。
- [开发环境](./dev/setup.md)、[测试说明](./dev/testing.md)、[贡献约定](./dev/contributing.md)。
- [工程原则](./dev/engineering-principles.md)、[维护规则](./dev/maintenance.md)。

业务语义在 `project/` 对应专题维护，操作说明在 `usage/`，开发流程在 `dev/`。更新功能时同步相应文档，避免恢复本版已经移除的 AI 使用说明。
