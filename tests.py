"""Tests for TUI Browser — browser.py"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, patch
from browser import TUIBrowser, _error_page, HOME_MARKDOWN


# ---------------------------------------------------------------------------
# Unit tests (no UI)
# ---------------------------------------------------------------------------


class TestUrlNormalisation:
    """URL normalisation logic."""

    def setup_method(self):
        self.app = TUIBrowser.__new__(TUIBrowser)

    def test_bare_domain_gets_https(self):
        assert self.app._normalise_url("example.com") == "https://example.com"

    def test_subdomain_gets_https(self):
        assert self.app._normalise_url("docs.python.org") == "https://docs.python.org"

    def test_https_url_unchanged(self):
        url = "https://example.com/path?q=1"
        assert self.app._normalise_url(url) == url

    def test_http_url_unchanged(self):
        url = "http://example.com/"
        assert self.app._normalise_url(url) == url

    def test_search_query_becomes_brave(self):
        result = self.app._normalise_url("hello world")
        assert result.startswith("https://search.brave.com/search?q=")
        assert "hello" in result

    def test_single_word_becomes_search(self):
        result = self.app._normalise_url("wikipedia")
        assert "brave" in result

    def test_url_with_path_unchanged(self):
        url = "https://github.com/user/repo"
        assert self.app._normalise_url(url) == url


class TestHtmlToMarkdown:
    """HTML → Markdown conversion."""

    def test_heading_conversion(self):
        html = "<html><body><h1>My Title</h1></body></html>"
        md = TUIBrowser._html_to_markdown(html, "https://example.com")
        assert "My Title" in md

    def test_paragraph_text_preserved(self):
        html = "<html><body><p>Hello world</p></body></html>"
        md = TUIBrowser._html_to_markdown(html, "https://example.com")
        assert "Hello world" in md

    def test_scripts_stripped(self):
        html = "<html><body><p>Safe</p><script>alert('xss')</script></body></html>"
        md = TUIBrowser._html_to_markdown(html, "https://example.com")
        assert "alert" not in md
        assert "Safe" in md

    def test_styles_stripped(self):
        html = "<html><body><p>Content</p><style>.foo{color:red}</style></body></html>"
        md = TUIBrowser._html_to_markdown(html, "https://example.com")
        assert "color" not in md
        assert "Content" in md

    def test_relative_links_resolved(self):
        html = '<html><body><a href="/about">About</a></body></html>'
        md = TUIBrowser._html_to_markdown(html, "https://example.com")
        assert "https://example.com/about" in md

    def test_absolute_links_unchanged(self):
        html = '<html><body><a href="https://other.com">Link</a></body></html>'
        md = TUIBrowser._html_to_markdown(html, "https://example.com")
        assert "https://other.com" in md

    def test_malformed_html_does_not_raise(self):
        html = "<unclosed><p>text<div>broken"
        md = TUIBrowser._html_to_markdown(html, "https://example.com")
        assert isinstance(md, str)


class TestErrorPage:
    """Error page helper."""

    def test_title_present(self):
        page = _error_page("My Error", "Details here.")
        assert "My Error" in page

    def test_message_present(self):
        page = _error_page("Title", "Detailed message.")
        assert "Detailed message." in page

    def test_action_links_present(self):
        page = _error_page("T", "M")
        assert "action:back" in page
        assert "action:home" in page


# ---------------------------------------------------------------------------
# Integration tests (with UI)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_home_screen_buttons_disabled():
    """Back and Forward buttons must be disabled on startup."""
    app = TUIBrowser()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.2)
        assert app.query_one("#back-btn").disabled
        assert app.query_one("#forward-btn").disabled


@pytest.mark.asyncio
async def test_history_enables_back_button():
    """Populating history enables the Back button."""
    app = TUIBrowser()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.2)
        app._history = ["https://a.com", "https://b.com"]
        app._history_pos = 1
        app._update_nav_buttons()
        await pilot.pause(0.1)
        assert not app.query_one("#back-btn").disabled
        assert app.query_one("#forward-btn").disabled


@pytest.mark.asyncio
async def test_status_bar_updates():
    """Setting app.status should update the status bar widget."""
    app = TUIBrowser()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.2)
        app.status = "custom status text"
        await pilot.pause(0.1)
        rendered = str(app.query_one("#status-bar").render())
        assert "custom status text" in rendered


@pytest.mark.asyncio
async def test_url_bar_accepts_text():
    """URL bar should accept and display text input."""
    app = TUIBrowser()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.2)
        url_bar = app.query_one("#url-bar")
        url_bar.value = "https://python.org"
        await pilot.pause(0.1)
        assert "python.org" in url_bar.value


@pytest.mark.asyncio
async def test_go_home_resets_state():
    """action_go_home must clear the current URL and base URL."""
    app = TUIBrowser()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.2)
        app._current_url = "https://something.com"
        app._current_base_url = "https://something.com"
        app.action_go_home()
        await pilot.pause(0.2)
        assert app._current_url == ""
        assert app._current_base_url == ""


@pytest.mark.asyncio
async def test_loading_indicator_toggle():
    """Setting is_loading should change the refresh button label."""
    app = TUIBrowser()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.2)
        app.is_loading = True
        await pilot.pause(0.1)
        assert str(app.query_one("#refresh-btn").label) == "✕  Stop"
        app.is_loading = False
        await pilot.pause(0.1)
        assert str(app.query_one("#refresh-btn").label) == "↻  Refresh"
