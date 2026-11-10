# 来源、许可与修改声明

**RssHub lite**（`astrbot_plugin_rsshub_lite`）是 AstrBot RSSHub 插件的修改版本。项目源码位于 [Junnstoy/astrbot_plugin_rsshub_lite](https://github.com/Junnstoy/astrbot_plugin_rsshub_lite)，首个公开版本为 `v0.1.0`。

## 上游来源

- 上游仓库：[AstrBot-Elementary-School/astrbot_plugin_rsshub](https://github.com/AstrBot-Elementary-School/astrbot_plugin_rsshub)。
- 基线版本：`v2.1.4`。
- 固定提交：[`a047f46e47cb2a0f7a795f30b9f82ae027005846`](https://github.com/AstrBot-Elementary-School/astrbot_plugin_rsshub/tree/a047f46e47cb2a0f7a795f30b9f82ae027005846)。
- 上游作者：**FlanChanXwO** 及上游贡献者；原作者的项目地址为 [FlanChanXwO/astrbot_plugin_rsshub](https://github.com/FlanChanXwO/astrbot_plugin_rsshub)。
- 上游许可证：**GNU Affero General Public License, version 3**。本项目继续采用该许可证，完整 [LICENSE](LICENSE) 保留原文。原有版权和许可声明继续适用，本声明不授予额外权限，也不代表上游作者对本修改版本的认可。

上游版本历史单独归档在[上游变更记录](docs/project/upstream-changelog.md)，其中版本号、日期和功能描述属于上游，不是 RssHub lite 的发行记录。固定基线与文件审计信息见 [UPSTREAM.json](UPSTREAM.json)。

## 本修改版本

修改日期：**2026-11-11**。这是修改记录日期，不是承诺的发布日。

首个公开版本整合了开发期间的裁剪与修复：

- 保留原版分层、订阅、RSS/Atom/JSON Feed 抓取、SQLite 仓储、轮询去重、历史与重试、媒体缓存、会话队列和基础 Plugin Pages。
- 移除 AI 内容处理器、LLM 工具、Agent XML 推送及 RSSHub Routes 知识库的装配、执行、配置、命令、接口和页面。旧处理器数据库字段仅作存储兼容，不再参与执行。
- 修复聊天命令多参数解析，接通 RSSHub 路由与新订阅会话模板；统一以 `/push`、`/unpush` 控制持续推送，增加按订阅 ID 即时发送的 `/feed`，区分任务查询与取消。
- 拆分普通推送与手动 `/feed` 的显示配置，统一直接/合并发送、显示开关、合并媒体和自定义/原始顺序排版；扩展模型、仓储、数据库迁移及版本 3 配置/TOML 转换。
- 明确平台实际发送能力；OneBot 使用真正合并转发，其他平台对不支持的合并方式或媒体组合明确报错。修复 Windows 同一表格图片缓存的并发替换问题。
- 更新管理页面、自动化测试与公开文档，采用独立插件标识、API 前缀和数据目录。不自动读取或迁移原版插件及其他框架插件的运行数据库。

具体行为见 [README](README.md) 和 [CHANGELOG](CHANGELOG.md)。开发期间使用的内部版本标签不代表此前正式发行的 RssHub lite 版本。

## 其他来源与致谢

保留上游对 [RSS-to-Telegram-Bot](https://github.com/Rongronggg9/RSS-to-Telegram-Bot)、[AstrBot](https://github.com/AstrBotDevs/AstrBot) 和 [feedparser](https://github.com/kurtmckee/feedparser) 的致谢。随项目保留的第三方代码及资源继续遵循各自附带的版权与许可声明。

测试夹具 `tests/fixtures/astrbot_command_filter.py` 来自 [AstrBotDevs/AstrBot](https://github.com/AstrBotDevs/AstrBot)，原声明为 **Copyright (C) 2022-2099 Soulter**，许可为 **GNU AGPL v3 or later**，对应 Git blob `abf339fda7f0740f542a91cd4adb859d5ef6ed5f`。它用于验证宿主实际参数解析行为，不包含在插件安装包内。
