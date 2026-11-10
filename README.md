# RSSHub for AstrBot · 无 AI 裁剪版

本版本直接基于 [AstrBot-Elementary-School/astrbot_plugin_rsshub](https://github.com/AstrBot-Elementary-School/astrbot_plugin_rsshub) **v2.1.4** 裁剪，基线提交为 `a047f46e47cb2a0f7a795f30b9f82ae027005846`。数据库、订阅、抓取、去重和推送优先沿用原版实现。

## 保留的功能

- RSS、Atom、JSON Feed 订阅，支持完整 URL 和 RSSHub 路由。
- 订阅增删、列表、批量启停、用户/会话默认配置、TOML 导入导出。
- 原版定时调度、条件 GET、首次跳过历史、指纹去重与成功投递幂等。
- 原版会话发送队列、平台适配、图文媒体处理、失败降级与重试。
- 基础管理页面：订阅、用户、Feed、推送历史、默认设置和数据管理。
- SQLite、原版 SQLModel 模型、数据库迁移与 Repository。

已移除 AI 内容处理运行时、LLM 工具注册、Agent XML 即时推送、RSSHub Routes 知识库及对应命令、配置、API 和管理页面。普通 HTML 清洗、图片提取和格式化仍保留。

## 安装

需要 **AstrBot >=4.24.0**，使用符合该 AstrBot 版本要求的 Python。

将发布 ZIP 上传到 AstrBot 插件管理，或把 ZIP 内的 `astrbot_plugin_rsshub` 目录放到：

```text
AstrBot/data/plugins/astrbot_plugin_rsshub/
```

插件保留原版标识和数据路径，**与原版二选一安装**。此本地裁剪版不配置上游自动更新地址，避免被原版覆盖。安装前先停止已有同名插件，保留需要的数据备份。

如果宿主没有自动安装依赖，在 AstrBot 实际运行环境执行：

```bash
python -m pip install -r data/plugins/astrbot_plugin_rsshub/requirements.txt
```

随后重载插件，在配置中设置 `basic_config.rsshub_base_url`。沿用自己的 RSSHub 实例时可填 `http://rsshub.yuma.fun`；该地址来自旧插件，本次未验证服务可用性。

## 重新订阅

不读取或迁移 `yuma_yys/rsshub.db`，也不自动导入上一版独立 Lite 数据。在目标会话中重新订阅即可，例如阴阳师官方网易大神账号：

```text
/sub /163/ds/5b00c224c7de46d98d33a6e0722ce28f
/sub_list
/sub_test 1
/sub_state 1 off
/sub_state 1 on
```

ID `1` 请替换为列表中的实际订阅 ID。也可以 `/sub https://你的实例/163/ds/用户ID`。本版沿用原版命令，不提供之前独立实现的 `/动态`、`/rss_on` 或内置名称快捷源；查看 Feed 当前条目可使用管理页面，管理员可用 `/sub_test` 发送最新一条。

`/sub_stop` 只停止正在运行/排队的任务；要持续停用订阅，请用 `/sub_state <ID> off` 或 `/deactivate_subs`。权限规则同原版，测试推送、全局删除和全量导出要求 AstrBot 管理员。

| 命令 | 用途 |
| --- | --- |
| `/sub <URL或路由>` | 新增订阅，支持批量 |
| `/unsub <ID或URL>` | 取消订阅 |
| `/sub_list` | 当前会话订阅列表 |
| `/sub_state <ID> on/off` | 单项启停 |
| `/activate_subs`、`/deactivate_subs` | 当前会话批量启停 |
| `/sub_status`、`/sub_stop` | 查看/停止当前发送任务 |
| `/sub_profile`、`/sub_session` | 用户、订阅及会话配置 |
| `/sub_export`、`/sub_import` | TOML 导出和导入 |
| `/sub_test <ID或URL>` | 管理员测试推送最新一条 |
| `/rsshelp` | 命令帮助图 |

完整说明见 [命令](docs/usage/commands.md)、[配置](docs/usage/configuration.md)、[管理页面](docs/usage/plugin-pages.md)。

## 数据与兼容

默认数据库仍为：

```text
AstrBot/data/plugin_data/astrbot_plugin_rsshub/rsshub.db
```

保留原版 `rsshub_user`、`rsshub_feed`、`rsshub_sub`、`rsshub_push_history`、`rsshub_migration_record` 表及迁移代码。推送记录驱动持久化失败重试，运行中的会话 Task/队列仍为内存状态，语义同原版。

`handlers`、`handlers_mode`、`handler_trace` 等历史字段保留以维持结构兼容。旧值不会触发处理器，新的推送记录不产生 AI trace；配置入口拒绝处理器选项，导入旧 TOML 会忽略处理器字段并提示，导出不携带它们。保留 `raw_xml` 用于记录原始内容，它不代表 AI 功能。

本版没有执行任何数据迁移操作；原版自带的数据库结构升级仍在插件启动时运行。工作区的旧 `yuma_yys` 目录保持原样，不进入安装包。

## 开发、验证与打包

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests
node --test tests/frontend/*.test.mjs
python scripts/package.py
```

Windows 如使用旧版 pip，请先设置 `PYTHONUTF8=1`，以正确读取带中文注释的依赖清单。测试使用 AstrBot API mock，不会发送真实平台消息；外网媒体集成测试默认跳过。生产环境仍需实际验证 RSSHub 实例和 Bot 平台连接。

安装包输出到 `dist/`。打包仅包含运行源码、前端、资源及许可文档，排除 `yuma_yys`、`.previous-lite`、`.upstream`、数据库、测试依赖和临时检查文件。

[目标架构与裁剪边界](docs/project/architecture.md) · [来源与许可](NOTICE.md) · [GNU AGPL v3](LICENSE)
