from dataclasses import replace

import pytest
from astrbot_plugin_rsshub_lite.src.application.services.html_parser import HTMLParser
from astrbot_plugin_rsshub_lite.src.infrastructure.pipeline import (
    EffectivePushOptions,
    EntryFormatInput,
    EntryTextFormatter,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("style", [0, 2])
async def test_hidden_rss_summary_title_does_not_remove_body(style):
    # User-reported /163/ds sample: title is an ellipsized excerpt of the body.
    title = "【超鬼王阵容】7天在线文档：获取+使用教学！ ※文档使用说明；③超鬼王..."
    body = "【超鬼王阵容】7天在线文档：获取+使用教学！\n※文档使用说明；③超鬼王DAY1图片+阵容码\n#阴阳师#"
    entry = EntryFormatInput(title=title, content=body)
    parsed = await HTMLParser(body).parse()
    options = EffectivePushOptions(display_title=False, style=style)
    formatter = EntryTextFormatter()
    text = await formatter.format_entry(entry, options)
    layout = await formatter.format_layout(entry, options, parsed.layout)
    layout_text = "\n".join(
        fragment.text for fragment in layout if fragment.kind == "text"
    )
    for output in (text, layout_text):
        assert title not in output
        assert "7天在线文档：获取+使用教学！" in output
        assert "DAY1图片+阵容码" in output
        assert "#阴阳师#" in output  # Body hashtags are not RSS category metadata.


@pytest.mark.asyncio
async def test_custom_layout_orders_metadata_body_categories_source_then_media():
    html = '<p>正文A</p><img src="https://example.com/a.jpg"><p>正文B</p>'
    entry = EntryFormatInput(
        title="标题",
        author="作者甲",
        content=html,
        tags=("RSS分类",),
        link="https://example.com/post",
        feed_title="源名称",
    )
    parsed = await HTMLParser(html).parse()
    layout = await EntryTextFormatter().format_layout(
        entry,
        EffectivePushOptions(display_entry_tags=True),
        parsed.layout,
        media_items=[
            ("image", "https://example.com/a.jpg"),
            ("video", "https://example.com/b.mp4"),
        ],
    )
    assert [fragment.kind for fragment in layout] == ["text", "image", "video"]
    text = layout[0].text
    ordered = [
        "作者：作者甲",
        "标题",
        "正文A",
        "正文B",
        "#RSS分类",
        "via https://example.com/post | 源名称",
    ]
    positions = [text.index(item) for item in ordered]
    assert positions == sorted(positions)


@pytest.mark.asyncio
async def test_original_layout_preserves_body_order_and_switches_independently():
    html = '<p>正文A</p><img src="https://example.com/a.jpg"><p>正文B</p>'
    entry = EntryFormatInput(
        title="标题", author="作者", content=html, link="https://example.com/post"
    )
    parsed = await HTMLParser(html).parse()
    options = EffectivePushOptions(style=2, display_title=False, display_via=False)
    formatter = EntryTextFormatter()
    layout = await formatter.format_layout(entry, options, parsed.layout)
    assert [(x.kind, x.text) for x in layout] == [
        ("text", "作者：作者"),
        ("text", "正文A"),
        ("image", ""),
        ("text", "正文B"),
    ]
    hidden = await formatter.format_layout(
        entry,
        replace(options, display_author=False, display_media=False),
        parsed.layout,
    )
    assert [(x.kind, x.text) for x in hidden] == [("text", "正文A"), ("text", "正文B")]
    assert [x.kind for x in parsed.layout] == ["text", "image", "text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("style", [0, 2])
async def test_body_length_limit_does_not_truncate_metadata(style):
    entry = EntryFormatInput(
        title="完整标题",
        author="作者",
        content="abcdefghijk",
        link="https://example.com/post",
    )
    parsed = await HTMLParser(entry.content).parse()
    layout = await EntryTextFormatter().format_layout(
        entry, EffectivePushOptions(style=style, length_limit=6), parsed.layout
    )
    text = "\n".join(x.text for x in layout)
    assert "完整标题" in text and "作者" in text
    assert "abc..." in text and "defghijk" not in text
    assert "https://example.com/post" in text
