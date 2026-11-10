"""测试当前 HTML 解析服务."""

from __future__ import annotations

import pytest
from astrbot_plugin_rsshub_lite.src.application.services.html_parser import HTMLParser
from astrbot_plugin_rsshub_lite.src.domain.entities.content_types import (
    ImageContent,
    LinkContent,
    TextContent,
)


class TestHTMLParser:
    """测试 HTMLParser 类."""

    @pytest.mark.asyncio
    async def test_parse_removes_script_and_style_text(self):
        html = (
            '<p>Hello</p><script>alert("xss")</script><style>.x{}</style><p>World</p>'
        )
        parser = HTMLParser(html)

        await parser.parse()
        text = parser.get_plain_text()

        assert "alert" not in text
        assert ".x" not in text
        assert "Hello" in text
        assert "World" in text

    @pytest.mark.asyncio
    async def test_parse_text_and_basic_formatting(self):
        html = "<p>Paragraph</p><b>Bold</b><i>Italic</i>"

        result = await HTMLParser(html).parse()

        texts = [
            node.text
            for node in result.html_tree.children
            if isinstance(node, TextContent)
        ]
        assert any("Paragraph" in text for text in texts)
        assert "**Bold**" in texts
        assert "*Italic*" in texts

    @pytest.mark.asyncio
    async def test_parse_extracts_links(self):
        html = '<a href="https://example.com">Click here</a>'

        result = await HTMLParser(html).parse()

        assert result.links == ["https://example.com"]
        assert any(
            isinstance(node, LinkContent) and node.text == "Click here"
            for node in result.html_tree.children
        )

    @pytest.mark.asyncio
    async def test_parse_resolves_relative_image_urls(self):
        html = '<img src="/image.png" alt="Image">'

        result = await HTMLParser(html, feed_link="https://example.com/feed").parse()

        assert len(result.media) == 1
        assert isinstance(result.media[0], ImageContent)
        assert result.media[0].url == "https://example.com/image.png"
