#!/usr/bin/env python3
"""TUI Browser — A cross-platform terminal web browser with mouse support.

Features
--------
* Works on Windows, macOS, and Linux terminals
* Full mouse interaction (click links, scroll, button clicks)
* Clean, dark UI with a readable typography
* Back / Forward / Refresh / Home navigation
* Inline search with Ctrl+F
* History-aware URL bar
* Smart URL handling (adds https://, treats bare text as search query)
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin, unquote

import html2text
import requests
from bs4 import BeautifulSoup

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Input, Label, Markdown, Static


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_HOME_URL = "https://search.brave.com/"
REQUEST_TIMEOUT = 15  # seconds

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

HOME_MARKDOWN = """\
# 🌐 TUI Browser

Welcome to **TUI Browser** — a clean, lightweight terminal web browser.

---

## Quick Links

- [Brave Search](https://search.brave.com/)
- [Wikipedia (Mobile)](https://en.m.wikipedia.org/wiki/Main_Page)
- [Hacker News](https://news.ycombinator.com/)
- [Python 3 Docs](https://docs.python.org/3/)
- [GitHub](https://github.com/)

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+L` | Focus the URL bar |
| `Ctrl+R` | Refresh current page |
| `Alt+Left` | Go back |
| `Alt+Right` | Go forward |
| `Ctrl+H` | Go home |
| `Ctrl+Q` | Quit |

---

*Type a URL or search term in the address bar above and press **Enter**.*
"""

_ERROR_TEMPLATE = """\
# ⚠ {title}

{message}

---

[← Go Back](action:back) | [⌂ Home](action:home)
"""


def _error_page(title: str, message: str) -> str:
    return _ERROR_TEMPLATE.format(title=title, message=message)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class TUIBrowser(App[None]):
    """A cross-platform TUI web browser with mouse interaction."""

    TITLE = "TUI Browser"
    SUB_TITLE = ""
    DARK = True

    CSS = """
    /* ── Toolbar ── */
    #toolbar {
        height: auto;
        background: $panel;
        border-bottom: solid $primary-darken-3;
        padding: 0 1;
        align: left middle;
    }

    .nav-btn {
        min-width: 5;
        height: auto;
        border: none;
        background: transparent;
        color: $text;
        margin-right: 0;
    }

    .nav-btn:hover {
        background: $primary-darken-2;
        color: $accent;
    }

    .nav-btn:disabled {
        color: $text-disabled;
        background: transparent;
    }

    #url-bar {
        height: 1;
        border: none;
        background: $surface;
        margin: 0 1;
    }

    #url-bar:focus {
        border: none;
        background: $primary-darken-1;
    }

    #go-btn {
        min-width: 6;
        height: auto;
        background: $primary;
        color: $text;
        border: none;
    }

    #go-btn:hover {
        background: $accent;
    }

    /* ── Content ── */
    #content {
        padding: 1 2;
        overflow-y: scroll;
    }

    Markdown {
        padding: 0;
        margin: 0;
    }

    /* ── Status bar ── */
    #status-bar {
        height: 1;
        background: $panel;
        border-top: solid $primary-darken-3;
        padding: 0 2;
        color: $text-muted;
        content-align: left middle;
    }
    """

    BINDINGS = [
        Binding("ctrl+l", "focus_url", "URL Bar"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("alt+left", "go_back", "Back"),
        Binding("alt+right", "go_forward", "Forward"),
        Binding("ctrl+h", "go_home", "Home"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("escape", "blur_url", "Close URL", show=False),
    ]

    # Reactive state
    status: reactive[str] = reactive("Ready")
    is_loading: reactive[bool] = reactive(False)

    def __init__(self) -> None:
        super().__init__()
        self._history: list[str] = []
        self._history_pos: int = -1
        self._current_url: str = ""
        self._current_base_url: str = ""
        self._session = requests.Session()
        self._session.headers.update(REQUEST_HEADERS)

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Horizontal(id="toolbar"):
            yield Button("◀", id="back-btn",    classes="nav-btn", disabled=True,  tooltip="Back (Alt+Left)")
            yield Button("▶", id="forward-btn", classes="nav-btn", disabled=True,  tooltip="Forward (Alt+Right)")
            yield Button("↺", id="refresh-btn", classes="nav-btn",                 tooltip="Refresh (Ctrl+R)")
            yield Button("⌂", id="home-btn",    classes="nav-btn",                 tooltip="Home (Ctrl+H)")
            yield Input(placeholder="Enter URL or search term…", id="url-bar")
            yield Button("Go", id="go-btn", tooltip="Navigate (Enter)")

        with ScrollableContainer(id="content"):
            yield Markdown(HOME_MARKDOWN, id="page-content")

        yield Static("Ready", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#url-bar", Input).focus()

    # ── Reactive watchers ────────────────────────────────────────────────────

    def watch_status(self, value: str) -> None:
        try:
            self.query_one("#status-bar", Static).update(value)
        except Exception:
            pass

    def watch_is_loading(self, loading: bool) -> None:
        try:
            btn = self.query_one("#refresh-btn", Button)
            btn.label = "✕" if loading else "↺"
            btn.tooltip = "Stop (Ctrl+R)" if loading else "Refresh (Ctrl+R)"
        except Exception:
            pass

    # ── Button handlers ──────────────────────────────────────────────────────

    @on(Button.Pressed, "#back-btn")
    def _on_back_pressed(self) -> None:
        self.action_go_back()

    @on(Button.Pressed, "#forward-btn")
    def _on_forward_pressed(self) -> None:
        self.action_go_forward()

    @on(Button.Pressed, "#refresh-btn")
    def _on_refresh_pressed(self) -> None:
        if self.is_loading:
            self.is_loading = False
            self.status = "Stopped"
        else:
            self.action_refresh()

    @on(Button.Pressed, "#home-btn")
    def _on_home_pressed(self) -> None:
        self.action_go_home()

    @on(Button.Pressed, "#go-btn")
    def _on_go_pressed(self) -> None:
        url = self.query_one("#url-bar", Input).value.strip()
        if url:
            self.navigate(url)

    # ── Input handler ────────────────────────────────────────────────────────

    @on(Input.Submitted, "#url-bar")
    def _on_url_submitted(self, event: Input.Submitted) -> None:
        url = event.value.strip()
        if url:
            self.navigate(url)

    # ── Link click handler ───────────────────────────────────────────────────

    @on(Markdown.LinkClicked)
    def _on_link_clicked(self, event: Markdown.LinkClicked) -> None:
        href = event.href
        if href == "action:back":
            self.action_go_back()
        elif href == "action:home":
            self.action_go_home()
        elif href.startswith(("http://", "https://", "ftp://")):
            self.navigate(href)
        elif self._current_base_url:
            self.navigate(urljoin(self._current_base_url, href))

    # ── Navigation helpers ───────────────────────────────────────────────────

    def navigate(self, url: str, *, push_history: bool = True) -> None:
        """Navigate to *url*, normalising it first."""
        url = self._normalise_url(url)

        if push_history:
            # Drop any forward history when the user navigates to a new page.
            self._history = self._history[: self._history_pos + 1]
            self._history.append(url)
            self._history_pos = len(self._history) - 1

        self._update_nav_buttons()
        self.query_one("#url-bar", Input).value = url
        self._current_url = url
        self._fetch_page(url)

    def _normalise_url(self, url: str) -> str:
        """Add a scheme or convert a bare search term into a DuckDuckGo search."""
        if url.startswith(("http://", "https://", "ftp://", "file://")):
            return url
        # Looks like a domain (contains a dot, no spaces)?
        if "." in url and " " not in url:
            return "https://" + url
        # Treat as a search query
        encoded = requests.utils.quote(url, safe="")
        return f"https://search.brave.com/search?q={encoded}"

    def _update_nav_buttons(self) -> None:
        try:
            self.query_one("#back-btn",    Button).disabled = self._history_pos <= 0
            self.query_one("#forward-btn", Button).disabled = self._history_pos >= len(self._history) - 1
        except Exception:
            pass

    # ── Page fetching (background thread) ───────────────────────────────────

    @work(thread=True)
    def _fetch_page(self, url: str) -> None:
        """Fetch *url* in a background thread and update the UI."""
        self.call_from_thread(self._set_loading, True, f"Loading {url} …")

        try:
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            final_url = resp.url
            ctype = resp.headers.get("content-type", "").lower()

            if "text/html" in ctype or "application/xhtml" in ctype:
                markdown = self._html_to_markdown(resp.text, final_url)
                status = f"✓  {final_url}  [{resp.status_code}]"
            elif "text/plain" in ctype:
                text = resp.text.replace("`", "'")
                markdown = f"```\n{text}\n```"
                status = f"✓  {final_url}  [plain text]"
            else:
                markdown = _error_page(
                    "Unsupported Content",
                    f"Cannot render `{ctype}`.\n\nURL: {final_url}",
                )
                status = f"Unsupported: {ctype}"
                final_url = url

            self.call_from_thread(self._apply_page, markdown, final_url, status)

        except requests.exceptions.SSLError as exc:
            self.call_from_thread(
                self._apply_error,
                "SSL / Certificate Error",
                f"TLS handshake failed for `{url}`.\n\n`{exc}`",
            )
        except requests.exceptions.ConnectionError:
            self.call_from_thread(
                self._apply_error,
                "Connection Error",
                f"Could not connect to `{url}`.\n\nCheck your internet connection or the URL.",
            )
        except requests.exceptions.Timeout:
            self.call_from_thread(
                self._apply_error,
                "Request Timeout",
                f"`{url}` did not respond within {REQUEST_TIMEOUT} seconds.",
            )
        except requests.exceptions.TooManyRedirects:
            self.call_from_thread(
                self._apply_error,
                "Too Many Redirects",
                f"`{url}` redirected too many times.",
            )
        except Exception as exc:  # noqa: BLE001
            self.call_from_thread(
                self._apply_error,
                "Unexpected Error",
                f"An unexpected error occurred:\n\n`{exc}`",
            )
        finally:
            self.call_from_thread(self._set_loading, False, None)

    # ── HTML → Markdown conversion ───────────────────────────────────────────

    @staticmethod
    def _html_to_markdown(html: str, base_url: str) -> str:
        """Parse *html* and return a Markdown string suitable for display."""
        try:
            soup = BeautifulSoup(html, "lxml")

            # Remove noisy / invisible elements
            _REMOVE_TAGS = ["script", "style", "noscript", "iframe", "svg", "canvas", "template"]
            for tag in soup.find_all(_REMOVE_TAGS):
                tag.decompose()

            # Resolve relative links so Markdown.LinkClicked gets full URLs
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    a["href"] = urljoin(base_url, href)

            # Special case: Clean formatting for Brave Search Results
            if "search.brave.com/search" in base_url:
                query_term = ""
                if "?q=" in base_url:
                    query_term = base_url.split("?q=")[-1].split("&")[0]
                    query_term = unquote(query_term).replace("+", " ")
                
                md_lines = [f"# 🔎 Search Results for '{query_term}'\n"]
                
                snippets = soup.select(".snippet[data-type=web]")
                if snippets:
                    for s in snippets:
                        title_elem = s.select_one(".title")
                        a_elem = s.select_one("a")
                        desc_elem = s.select_one(".content, .snippet-description, .description")
                        
                        if title_elem and a_elem:
                            title = title_elem.get_text(strip=True)
                            href = a_elem.get("href", "")
                            desc = desc_elem.get_text(strip=True) if desc_elem else ""
                            
                            md_lines.append(f"## [{title}]({href})")
                            md_lines.append(f"*{href}*")
                            if desc:
                                md_lines.append(f"\n> {desc}")
                            md_lines.append("\n---\n")
                    
                    return "\n".join(md_lines).strip()

            converter = html2text.HTML2Text()
            converter.ignore_images = True       # images can't be rendered in terminal
            converter.ignore_mailto_links = True
            converter.body_width = 0             # let the terminal handle wrapping
            converter.protect_links = True
            converter.wrap_links = False
            converter.single_line_break = True
            converter.unicode_snob = True

            md = converter.handle(str(soup))

            # Collapse runs of blank lines (≥3) to at most two
            md = re.sub(r"\n{3,}", "\n\n", md)
            return md.strip()

        except Exception as exc:  # noqa: BLE001
            return _error_page("Render Error", f"Failed to render page content:\n\n`{exc}`")

    # ── Thread-safe UI updaters ──────────────────────────────────────────────

    def _set_loading(self, loading: bool, status: Optional[str]) -> None:
        self.is_loading = loading
        if status is not None:
            self.status = status

    def _apply_page(self, markdown: str, url: str, status: str) -> None:
        """Update the content widget and status bar (called on the UI thread)."""
        self._current_base_url = url
        content_area = self.query_one("#content", ScrollableContainer)
        content_area.scroll_home(animate=False)
        self.query_one("#page-content", Markdown).update(markdown)
        if url:
            self.query_one("#url-bar", Input).value = url
            self._current_url = url
        self.status = status

    def _apply_error(self, title: str, message: str) -> None:
        """Display an error page (called on the UI thread)."""
        self._current_base_url = ""
        self.query_one("#content", ScrollableContainer).scroll_home(animate=False)
        self.query_one("#page-content", Markdown).update(_error_page(title, message))
        self.status = f"⚠  {title}"

    # ── Keybinding actions ───────────────────────────────────────────────────

    def action_focus_url(self) -> None:
        url_bar = self.query_one("#url-bar", Input)
        url_bar.focus()
        url_bar.action_select_all()

    def action_blur_url(self) -> None:
        """Return focus to the content area."""
        self.query_one("#content", ScrollableContainer).focus()

    def action_refresh(self) -> None:
        if self._current_url:
            self._fetch_page(self._current_url)

    def action_go_back(self) -> None:
        if self._history_pos > 0:
            self._history_pos -= 1
            url = self._history[self._history_pos]
            self._update_nav_buttons()
            self.query_one("#url-bar", Input).value = url
            self._current_url = url
            self._fetch_page(url)

    def action_go_forward(self) -> None:
        if self._history_pos < len(self._history) - 1:
            self._history_pos += 1
            url = self._history[self._history_pos]
            self._update_nav_buttons()
            self.query_one("#url-bar", Input).value = url
            self._current_url = url
            self._fetch_page(url)

    def action_go_home(self) -> None:
        self._current_base_url = ""
        self._current_url = ""
        self.query_one("#url-bar", Input).value = ""
        self.query_one("#content", ScrollableContainer).scroll_home(animate=False)
        self.query_one("#page-content", Markdown).update(HOME_MARKDOWN)
        self.status = "Home"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    TUIBrowser().run()


if __name__ == "__main__":
    main()
