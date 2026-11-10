# 命令说明

命令中的 ID 默认指 `/sub_list` 方括号内的**订阅 ID**。列表前的序号、Feed ID 和发送任务的 job ID 是不同标识。

## 订阅与持续推送

| 命令 | 中文别名 | 说明 |
| --- | --- | --- |
| `/sub <URL或RSSHub路由> [更多URL或路由...]` | `/订阅` | 在当前会话新增订阅；多个目标用空格分隔。路由以 `/` 开头，使用配置的 RSSHub 域名。 |
| `/sub_list [page] [page_size]` | `/订阅列表` | 查看自己在当前会话的订阅。默认第 1 页、每页 5 条；每页可设 1～100 条。 |
| `/push <订阅ID[,ID...]\|all>` | `/启用推送` | 持续启用自己在当前会话的订阅，等待定时检查。`all` 表示自己的当前会话订阅。 |
| `/unpush <订阅ID[,ID...]\|all>` | `/停用推送`、`/停止推送` | 持续停用所选订阅，并请求取消对应的运行中、排队中任务；保留订阅。 |
| `/unsub <ID或URL...>` | `/取消订阅` | 删除订阅，多个 ID 或 URL 用空格分隔。 |
| `/unsub_all [global]` | `/取消全部订阅` | 删除自己的当前会话订阅；`global` 删除自己所有会话的订阅，需要管理员权限。 |

新建订阅默认启用。`/push`、`/unpush` 的开关写入数据库，插件重启后仍保留；`/push` 不会立即发送历史条目，也不会覆盖 `notify` 配置。需要马上看内容时使用 `/feed`。

```text
/sub /163/ds/5b00c224c7de46d98d33a6e0722ce28f
/sub_list
/sub_list 2 10
/unpush 1,3
/push 1,3
/unpush all
```

请用实际订阅 ID 替换示例中的 `1`、`3`。`/push 1,3` 使用逗号分隔；没有参数时只显示用法，不会默认批量修改。

## 立即发送与本次任务

| 命令 | 别名 | 说明 |
| --- | --- | --- |
| `/feed <订阅ID> <N>` | `/立即推送` | 管理员抓取当前会话中该订阅的最新 N 条，按从新到旧顺序发送到当前会话。两个参数都必填。 |
| `/push_status` | `/sub_status`、`/推送状态`、`/任务状态` | 查看当前会话正在运行、排队的发送任务及 job ID、Feed ID。 |
| `/push_cancel [job_id\|feed_id\|all]` | `/sub_stop`、`/rss_stop`、`/停止RSS`、`/取消推送任务` | 取消本次任务；无参数取消当前运行任务，`all` 取消当前会话全部任务。 |
| `/sub_test <订阅ID或URL>` | `/测试订阅` | 保留的管理员诊断入口，真实推送最新 1 条；使用原有测试分发链路。 |

`/feed` 接收订阅 ID，不接收 Feed ID、URL 或名称；N 为正整数。如果源只有 4 条，`/feed 12 10` 会发送可用的 4 条并提示数量不足。按发布时间降序排列；缺少时间的条目排在有时间的条目之后，相同或缺少时间时保留源顺序。

`/feed` 是一次明确的手动发送：即使订阅已停用或 `notify=0`，仍可发送；不会改变自动推送开关、轮询时间、Feed 去重水位或自动推送成功记录。重复执行会再次发送，失败也不进入自动重试队列。排版继承该订阅及其所属用户的配置，消息发到执行命令的当前会话。

```text
/feed 12 5
/push_status
/push_cancel rss-000123
/push_cancel all
```

`/push_status` 没有任务，通常只代表此刻没有正在发送的消息。自动推送开关请看 `/sub_list` 的 `✓` / `✗`。`/push_cancel` 不会停用订阅，后续有更新仍会调度；长期停止请用 `/unpush`。其中纯数字取消目标是 **Feed ID**，请从 `/push_status` 读取。

取消针对已登记在发送队列中的任务。`/feed` 抓取、格式化或两条发送之间尚未入队时，可能没有可取消任务；正在发送的手动任务取消成功后，剩余条目会停止发送。已经发送到平台的消息不会撤回。

## `sub_profile`：现有订阅与用户默认配置

| 用法 | 作用 |
| --- | --- |
| `/sub_profile set sub <订阅ID> <选项> <值>` | 修改自己已有订阅的一个字段；按订阅 ID 定位。 |
| `/sub_profile set user <选项> <值>` | 修改当前发送者的用户默认值；会影响该用户不同会话中继承此字段的订阅。 |
| `/sub_profile get user [选项]` | 查看用户保存值；省略选项则列出全部。显示 `-100` 表示继承，不是最终解析结果。 |

中文命令组为 `/订阅配置 设置 ...`、`/订阅配置 获取 ...`。目前没有 `/sub_profile get sub` 查询入口；订阅详细配置可在管理页面查看。

发送选项逐字段按 **订阅 → 用户 → 全局默认** 解析，仅 `-100` 表示继续继承。用户默认值不会覆盖订阅已设置的值。常用示例：

```text
/sub_profile set user length_limit 800
/sub_profile set user display_media -1
/sub_profile set sub 12 display_media 0
/sub_profile set sub 12 style 2
/sub_profile get user
/sub_profile get user length_limit
```

以上将该用户继承默认值的订阅设为正文最多 800 字符、不发媒体；订阅 `12` 单独启用媒体并选择原始顺序排版。要恢复继承：

```text
/sub_profile set sub 12 display_media -100
/sub_profile set user display_media -100
```

第一条让订阅重新使用用户默认值，第二条让用户重新使用全局默认值。数值配置请直接写数字；`on/off` 只用于旧 `/sub_state` 开关，不是通用配置值。

### 可用选项

以下发送选项可用于 `set sub`、`set user` 和 `sub_session set`。订阅、用户字段以及会话的新订阅模板均可用 `-100` 继续继承；`interval` 的例外见表下说明。

| 选项 | 数字值 | 实际作用 |
| --- | --- | --- |
| `notify` | `0` 关闭、`1` 开启 | 自动分发时关闭会跳过整条消息并记 `skipped`，不是静音发送。 |
| `send_mode` | `-1` 仅链接、`0` 自动、`1` 直接发送 | 仅链接只发条目标题和链接；自动模式可触发平台策略，如 Telegram Telegraph。 |
| `length_limit` | `0` 不限制，正整数限制长度 | 普通排版限制正文，标题和来源不计入；用户配置最大 10000。 |
| `display_title` | `-1` 隐藏、`0` 自动、`1` 强制 | 普通排版中 `0`、`1` 都显示已有标题，缺失标题不会生成。 |
| `display_author` | `-1` 隐藏、`0` 自动、`1` 强制 | 普通排版中 `0`、`1` 都显示已有作者，通常在来源后缀内。 |
| `display_via` | `-2` 完全隐藏、`-1` 仅链接、`0` 自动、`1` 强制 | `-2` 隐藏整个来源后缀，也连同后缀中的作者一起隐藏。 |
| `display_entry_tags` | `-1` 隐藏、`0` 显示 | 显示源条目自带的标签；不是订阅管理标签。 |
| `display_media` | `-1` 禁用、`0` 启用 | 关闭会移除媒体及原始图文布局。 |
| `style` | `0` 自动、`1` RSSRT、`2` 原始顺序 | 当前 RSSRT 与自动走相同链路；原始顺序的支持平台和显示边界见[配置说明](./configuration.md#排版-style-实际行为)。 |
| `interval` | 正整数，单位分钟 | 设置实际抓取频率请使用订阅级字段；必须不小于 `basic_config.minimal_interval`。 |

**监控间隔例外：** 当前调度器只读取订阅的 `interval`；订阅为 `-100` 时使用全局间隔，**不读取用户 `interval`**。`set user interval` 可以保存，但不会改变抓取频率。会话 `interval` 会复制到以后新建的订阅，且不接受 `-100`。

```text
/sub_profile set sub 12 interval 15
/sub_profile set sub 12 interval -100
```

第一条把订阅设为每 15 分钟检查，第二条恢复全局间隔。变更间隔不等同立即抓取，现有的下次检查时间仍由调度器处理。

订阅还支持 `title`、`tags` 字符串，用于管理名称和标签，例如：

```text
/sub_profile set sub 12 title 阴阳师 官方动态
/sub_profile set sub 12 tags 游戏,公告
```

订阅 `state` 是 `0/1` 开关，推荐用 `/push`、`/unpush` 操作。高级订阅字段 `target_session`、`platform_name` 控制投递目标，不属于继承链；普通使用在目标会话 `/sub` 即可。用户 `state`、`default_target_session` 属于原版保留数据字段，当前自动轮询和聊天新建订阅不使用它们实现停推或更换目标。

## `sub_session`：以后在此会话新建订阅的模板

`/sub_session` 的范围是当前 `unified_msg_origin`，即当前群聊或私聊会话。它把默认值保存在插件 KV 中；以后在这里执行 `/sub` 时，将这些值**复制进新订阅的字段**。它不是每次发送都查询的第四层继承，也不修改已有订阅。

```text
/sub_session set interval 15
/sub_session set style 2
/sub_session set display_media 0
/sub_session get
/sub_session get style
/sub /163/ds/5b00c224c7de46d98d33a6e0722ce28f
```

此后新建的订阅会保存 `interval=15`、`style=2`、`display_media=0`。即使之后改用户 `style`，这些订阅仍保持自己的 `style=2`，直到用 `sub_profile set sub <ID> style -100` 恢复继承。

会话模板支持上表发送选项及 `title`、`tags`，不支持 `state`、`target_session` 或 `platform_name`。命令没有删除单个模板键的入口；发送选项可设置 `-100`，使以后新建的订阅继续继承用户/全局。已有订阅需要单独修改，重复 `/sub` 同一源不会重套模板。中文命令为 `/会话设置 设置 ...`、`/会话设置 获取 ...`。

## 导入、导出与帮助

| 命令 | 中文别名 | 说明 |
| --- | --- | --- |
| `/sub_export [all]` | `/导出订阅` | 导出 TOML，默认当前会话；`all` 全量导出需要管理员权限。 |
| `/sub_import [文件路径]` | `/导入订阅` | 从 TOML 导入；不带参数时进入 5 分钟文件上传等待。 |
| `/rsshelp` | `/RSS帮助`、`/rss帮助` | 查看预生成命令帮助图。 |

保留旧入口 `/sub_state <ID> on/off`、`/activate_subs [ID[,ID...]|all]`、`/deactivate_subs [ID[,ID...]|all]` 以及 `enable_subs`、`disable_subs` 别名。旧批量命令省略参数仍表示当前会话自己的全部订阅；新用法优先使用 `/push all`、`/unpush all`，这两个新命令必须明确传入 ID 或 `all`。

## 原版配置兼容

精简版不接受 `handlers`、`handlers_mode` 和 `handler_specs`，不提供知识库初始化、同步或 LLM 工具。导入原版 TOML 时，处理器字段会被忽略并给出提示，其他基础订阅选项照常导入。导出的 TOML 不携带处理器配置；旧会话默认值中的处理器内容不会应用到新订阅。
