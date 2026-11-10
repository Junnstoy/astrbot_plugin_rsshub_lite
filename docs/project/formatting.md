# 文本格式化与组件排序

## 负责什么

当前格式化链可以分成两个层面：

1. `EntryTextFormatter`
   - `format_entry` 整理纯文本，`format_layout` 生成带显示开关的最终文字/媒体布局
2. `MessageComponentSorter`
   - 提供无布局时的兼容排序和媒体候选；当前发送器优先保留 formatter 给出的布局

## 为什么拆成两层

文本清洗和平台排序不是同一个问题：

- 文本格式化关心标题、正文、via、作者、标签
- 组件排序关心媒体与文本在不同平台上的发送顺序

布局与平台组件分开后，显示开关统一由 formatter 处理，平台只决定可发送的媒体类型和消息组合方式。

## EntryTextFormatter 算法

主要步骤：

1. `clean_text`
   - 走 `HTMLParser`
   - 提取纯文本
   - 去掉 `[视频]` / `[音频]` 占位
2. 仅在标题启用时，去掉正文开头与条目标题完全重复的部分；标题禁用时保留完整正文。
3. 应用正文长度限制，不计作者、标题、标签与来源。
4. 按独立 bool 开关组合作者、标题、正文、RSS 标签和来源。
5. `format_layout` 自定义模式将上述文本放前、媒体放后；原始顺序模式在作者/标题和标签/来源之间保留正文图文片段。

## 为什么 via 要单独处理

`via` 是兼容历史行为的重要部分。它承担两类信息：

- 条目链接
- feed 来源

来源启用时输出可用的文章链接和 Feed 名称/链接，关闭时移除整个来源段。作者现在是独立的前置段，来源开关不会连带隐藏作者。源字段缺失时只使用实际存在的数据，不生成空分隔符或占位作者。当前配置不再提供「仅链接来源」选项。

## MessageComponentSorter 算法

排序目标是平台无关组件：

- `media`
- `text`
- `tail`
- `failed_url`

无 layout 的兼容排序规则：

- 默认媒体优先于文本
- onebot-like 平台把 `tail` 里的音频/文件也尽量放在媒体区
- 文本主体统一放后面

当前主链路使用 `format_layout`，sender 的 `_configured_components` 优先保留该布局，仅补充 enclosure 媒体和失败链接；重试等没有 layout 的请求使用最终文本加媒体。`merge_media` 决定是否拆分，不由 `style` 或 sorter 隐式修改。

## 推送排版策略

`style` 字段现在表示推送排版策略：

- `0` 自定义：作者、标题、清洗后的正文、RSS 标签、来源组成文字部分，媒体随后。
- `2` 原始顺序：正文内部使用 HTML/XML 解析产生的 layout fragments，作者/标题在前、标签/来源在后；正文文本片段累计遵守 `length_limit`。

两种排版均应用所有显示开关。显示媒体关闭会移除媒体片段，标题关闭不删除正文原有文字。作者和来源独立。普通字段与 `feed_` 字段分别继承各自全局默认值，`feed_display_title` 不回退到普通 `display_title`。

`send_mode=1/2` 独立决定直接消息/合并转发；`merge_media=1` 将单条内容合成一个消息或转发节点，`0` 按片段拆分。RSSRT、自动发送、仅链接模式退出当前配置面，旧值按版本 3 规则一次转换。

## 表格图片语义

HTML `<table>` 解析时会先尝试走轻量转图链路：

- `HTMLParser._parse_table()` 调用 `infrastructure.rendering.TableImageRenderer`。
- Renderer 使用 `BeautifulSoup/lxml` 读取 `caption`、`thead`、`tbody`、`tr`、`th`、`td`，并基础处理 `rowspan` / `colspan`。
- 图片用 `Pillow` 绘制为统一聊天卡片风格，不做网页 CSS 高保真截图。
- 字体按 `RSSHUB_TABLE_FONT_PATH` 环境变量、`RSSHUB_TABLE_FONT_DIR` 环境变量、运行时下载目录（`data/fonts/`）、`assets/fonts/` 的顺序查找。插件启动时自动从 jsDelivr CDN 下载 Noto Sans SC 子集 OTF 到持久化数据目录，SHA256 + 大小双重校验，下载失败时表格回退为 `A | B | C` 纯文本（不使用 Pillow 默认字体）。用户也可通过环境变量指定自定义字体，或把 `.ttf`/`.otf`/`.ttc` 放入 `assets/fonts/` 或运行时字体目录。
- 成功后正文树里放入 `GeneratedImageContent`，`layout` 中生成带 `local_path` 的 image fragment；original style 不再把 `[表格已转为图片]` 作为可见文本片段发送，表格纯文本只作为图片缺失或发送失败时的内部 fallback。
- 文本格式化会按 `display_media` 决定是否走表格转图：正常显示媒体时移除短占位以避免重复刷屏；关闭媒体时保留 `A | B | C` 文本 fallback。

表格图片按规范化表格模型计算 sha256。启用 `media.cache_enabled` 时保存为 `cache/table_images/table_<hash>.png`，旁置 `.meta` 记录 `expire_ts`；命中会刷新 TTL，旧版无 meta 的 PNG 会先视为可复用并补写 meta，过期后重渲染。每次启用缓存渲染都会顺带清理已过期的其他表格图和明显陈旧的无 meta 孤儿 PNG，但会跳过当前 digest，避免误删刚被访问的旧版 PNG。同一表格重复推送会复用同一张图，缓存写入使用唯一临时文件避免并发同 hash 互相覆盖。

关闭 `media.cache_enabled` 时，表格图渲染为系统临时目录下的 `rsshub_table_*.png`，不写 digest cache 或 meta。sender 发送前会把 layout 上的一次性本地图复制成当次发送专用临时图，并通过 `PreparedMedia.owned_paths` 清理副本；共享 layout 原始临时图由 dispatcher、手动推送或文本清洗调用方清理。外部传入的非 cache `local_path` 不会被自动接管。空表格、坏 HTML 或渲染异常会保留原有 `A | B | C` 文本 fallback，不阻断 RSS 推送。

## 失败链接追加策略

失败链接只在失败面向场景追加：

- sender 发送失败回退文本
- history 记录失败时

正常成功态不追加，避免正文被原始媒体链接污染。

平台不支持同条合并的媒体组合会明确提示关闭合并媒体；不支持合并转发会明确返回错误。不会静默改变用户选择的直接/合并模式。各平台边界见[平台规则](./platforms.md)。

## 标题去重边界

正文开头与标题完全重复时，formatter 只会在标题实际显示的情况下剔除重复正文标题。若用户关闭标题显示，正文必须保持完整；这避免 bsky 等源把正文首句同时写入 `title` 和 `description` 时，推送只剩 hashtag 或后半段正文。
