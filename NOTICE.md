# 来源与裁剪范围

本插件直接基于 AstrBot-Elementary-School/astrbot_plugin_rsshub 的 v2.1.4 源码裁剪。

- 上游仓库：https://github.com/AstrBot-Elementary-School/astrbot_plugin_rsshub
- 基线提交：`a047f46e47cb2a0f7a795f30b9f82ae027005846`
- 原作者：FlanChanXwO；本地裁剪维护：Yuma。
- 许可证：GNU Affero General Public License v3，完整条款保留在 LICENSE。

保留原版数据库模型、迁移、Repository、订阅管理、Feed 解析与指纹去重、历史记录、失败重试、会话队列、平台发送与基础管理界面。移除 AI 内容处理运行时、LLM 工具注册、Agent XML 即时推送和 RSSHub Routes 知识库及对应入口。

数据库中的 handlers、handlers_mode、handler_trace 等旧字段保留以维持原版结构；它们不再作为可执行配置。既有推送记录仍可读取和重试，新的推送不调用模型。

原领域层的 handlers 模块仅保留历史 JSON 的存储兼容：移除注册表、AI 配置默认值、启用判断和构建入口，修复 HandlerSpec 重复归一化导致旧值意外清空的问题。旧 config 字典原样保存，不参与发送执行；Repository、ORM 和迁移代码仍沿用上游。

另包含一处 Windows 兼容修复：多个线程同时生成同一表格图片缓存时，仅对最终文件替换加共享锁，避免并发 `os.replace` 偶发拒绝访问。图片绘制仍可并行，缓存格式、媒体发送和失败降级机制不变。媒体测试的路径断言与字体发现也已适配 Windows。

不导入或迁移 yuma_yys 的 NoneBot2 数据。工作区的 yuma_yys、.previous-lite、.upstream 和测试依赖仅供本地参考，不进入发布包。

metadata 保留原版插件标识 astrbot_plugin_rsshub，以沿用原版 API 与数据路径；此裁剪版应与原版二选一安装。未配置上游自动更新地址，防止裁剪版被原版升级覆盖。
