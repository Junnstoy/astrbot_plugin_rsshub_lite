# 来源与裁剪范围

本插件直接基于 AstrBot-Elementary-School/astrbot_plugin_rsshub 的 v2.1.4 源码裁剪。

- 上游仓库：https://github.com/AstrBot-Elementary-School/astrbot_plugin_rsshub
- 基线提交：`a047f46e47cb2a0f7a795f30b9f82ae027005846`
- 原作者：FlanChanXwO；本地裁剪维护：Yuma。
- 许可证：GNU Affero General Public License v3，完整条款保留在 LICENSE。

沿用原版数据库、迁移和 Repository 体系，保留订阅管理、Feed 解析与指纹去重、历史记录、失败重试、会话队列、平台发送与基础管理界面。移除 AI 内容处理运行时、LLM 工具注册、Agent XML 即时推送和 RSSHub Routes 知识库及对应入口。

数据库中的 handlers、handlers_mode、handler_trace 等旧字段保留以维持原版结构；它们不再作为可执行配置。既有推送记录仍可读取和重试，新的推送不调用模型。

原领域层的 handlers 模块仅保留历史 JSON 的存储兼容：移除注册表、AI 配置默认值、启用判断和构建入口，修复 HandlerSpec 重复归一化导致旧值意外清空的问题。旧 config 字典原样保存，不参与发送执行。

另包含一处 Windows 兼容修复：多个线程同时生成同一表格图片缓存时，仅对最终文件替换加共享锁，避免并发 `os.replace` 偶发拒绝访问。图片绘制仍可并行，缓存格式、媒体发送和失败降级机制不变。媒体测试的路径断言与字体发现也已适配 Windows。

不导入或迁移 yuma_yys 的 NoneBot2 数据。工作区的 yuma_yys、.previous-lite、.upstream 和测试依赖仅供本地参考，不进入发布包。

metadata 保留原版插件标识 astrbot_plugin_rsshub，以沿用原版 API 与数据路径；此裁剪版应与原版二选一安装。未配置上游自动更新地址，防止裁剪版被原版升级覆盖。

2026-11-11 的 lite.2 更新修复聊天命令多参数丢失、已有订阅启停误用新增接口的问题；增加 push/unpush 和按订阅 ID 手动推送最新 N 条，接通会话默认配置与 RSSHub 路由订阅，允许用户默认 style=2。数据库结构、迁移和 Repository 保持上游实现。

2026-11-11 的 lite.3 更新拆分普通推送与手动 /feed 配置，统一直接/合并发送和独立显示开关，增加合并媒体，移除未实现的 RSSRT 选项；默认使用自定义排版。新增 V3 数据库迁移、配置与 TOML 版本转换，并相应扩展模型和 Repository，保留既有订阅与历史数据。旧枚举值按版本一次性转换，用户与订阅的新字段默认继承。/feed 将最新条目和统计放入同一合并消息，/sub_test 按普通发送模式放置统计。合并转发当前支持 OneBot；其他平台保留原生直接发送，对不支持的媒体组合明确报错。

测试目录中的 `astrbot_command_filter.py` 来自 AstrBotDevs/AstrBot（Copyright (C) 2022-2099 Soulter，GNU AGPL v3 or later），对应 Git blob `abf339fda7f0740f542a91cd4adb859d5ef6ed5f`。测试使用其实际参数解析器验证插件入口，避免只调用 handler 而遗漏宿主解析差异；该测试夹具不进入安装包。
