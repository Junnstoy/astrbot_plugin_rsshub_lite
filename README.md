# RSSHub for AstrBot · 无 AI 裁剪版

本版本直接基于 [AstrBot-Elementary-School/astrbot_plugin_rsshub](https://github.com/AstrBot-Elementary-School/astrbot_plugin_rsshub) **v2.1.4** 裁剪，基线提交为 `a047f46e47cb2a0f7a795f30b9f82ae027005846`。数据库、订阅、抓取、去重和推送优先沿用原版实现。

## 保留的功能

- RSS、Atom、JSON Feed 订阅，支持完整 URL 和 RSSHub 路由。
- 订阅增删、分页列表、持续启停、最新 N 条即时发送、用户/会话默认配置、TOML 导入导出。
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
/feed 1 3
/unpush 1
/push 1
```

ID `1` 请替换为列表方括号中的实际订阅 ID。也可以 `/sub https://你的实例/163/ds/用户ID`。新订阅默认启用；`/feed 1 3` 由管理员即时发送最新 3 条，从新到旧排列。它允许重复查看，不改变自动推送开关或去重水位。本版不提供之前独立实现的 `/动态`、`/rss_on` 或内置名称快捷源。

`/push`、`/unpush` 持续启停自己在当前会话的订阅，支持 `1,3,4` 或 `all`。`/push_status` 只显示当前正在运行或排队的发送任务；`/push_cancel` 取消本次任务，后续更新仍会推送。管理员权限用于 `/feed`、测试推送、全局删除和全量导出。

| 命令 | 用途 |
| --- | --- |
| `/sub <URL或路由>` | 新增订阅，支持批量 |
| `/unsub <ID或URL>` | 取消订阅 |
| `/sub_list [page] [page_size]` | 当前会话自己的订阅；默认每页 5 条 |
| `/push <ID[,ID...]\|all>`、`/unpush <ID[,ID...]\|all>` | 持续启用、停用自动推送 |
| `/feed <订阅ID> <N>` | 管理员即时发送最新 N 条 |
| `/push_status`、`/push_cancel [job_id\|feed_id\|all]` | 查看、取消本次发送任务 |
| `/sub_profile`、`/sub_session` | 用户、订阅及会话配置 |
| `/sub_export`、`/sub_import` | TOML 导出和导入 |
| `/sub_test <ID或URL>` | 管理员测试推送最新一条 |
| `/rsshelp` | 命令帮助图 |

完整说明见 [命令](docs/usage/commands.md)、[配置](docs/usage/configuration.md)、[管理页面](docs/usage/plugin-pages.md)。

`/sub_profile set sub 1 style 2` 修改已有订阅，`/sub_profile set user style 2` 设置该用户的默认排版。发送选项按订阅 → 用户 → 全局默认逐字段继承，`-100` 恢复继承。`/sub_session set style 2` 仅作为当前会话**以后新建订阅**的模板，不修改已有订阅。实际抓取间隔请设订阅 `interval`；用户 `interval` 当前不参与调度。全局默认值在管理页面保存后需要重载插件。

排版 `0` 自动、`1` RSSRT、`2` 原始顺序中，RSSRT 当前与自动共用链路；原始顺序仅在 OneBot、QQ Official、Weixin 专用发送器有对应布局时生效，详细显示边界见[排版说明](docs/usage/configuration.md#排版-style-实际行为)。旧 `/sub_state`、`/activate_subs`、`/deactivate_subs`、`/sub_status`、`/sub_stop` 保留兼容入口。

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
