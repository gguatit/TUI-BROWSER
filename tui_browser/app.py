"""Main application logic for TUI Browser."""

from typing import Optional
from urllib.parse import urljoin
import requests

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Button, Footer, Input, Markdown, Static

from .constants import REQUEST_TIMEOUT, REQUEST_HEADERS, HOME_MARKDOWN, _error_page
from .parser import html_to_markdown
from .modals import ImageViewerModal, VideoViewerModal

# ---------------------------------------------------------------------------
# HARD BLOCK GUI BROWSER
# Absolutely prevent Python from EVER launching an external GUI browser.
# Textual and other libraries use this module under the hood.
# ---------------------------------------------------------------------------
import webbrowser
webbrowser.open = lambda *args, **kwargs: False
webbrowser.open_new = lambda *args, **kwargs: False
webbrowser.open_new_tab = lambda *args, **kwargs: False

class TUIBrowser(App[None]):
    """A cross-platform TUI web browser with mouse interaction."""

    TITLE = "TUI Browser"
    SUB_TITLE = ""
    DARK = True

    CSS = """
    $border-color: $primary-darken-2;

    /* ── Toolbar ── */
    #toolbar {
        height: auto;
        background: $boost;
        border-bottom: double $border-color;
        padding: 1 2;
        align: left middle;
    }

    .nav-btn {
        min-width: 5;
        height: auto;
        border: round $border-color;
        background: $surface;
        color: $text;
        margin-right: 1;
    }

    .nav-btn:hover {
        background: $primary-background;
        border: round $accent;
        color: $accent;
    }

    .nav-btn:disabled {
        color: $text-disabled;
        border: round #555555;
        background: transparent;
    }

    #url-bar {
        height: 3;
        border: round $border-color;
        background: $surface;
        margin: 0 1;
        padding: 0 1;
    }

    #url-bar:focus {
        border: round $accent;
        background: $surface;
    }

    #go-btn {
        min-width: 8;
        height: 3;
        background: $accent;
        color: $text;
        border: round $accent;
        margin-left: 1;
    }

    #go-btn:hover {
        background: $accent-lighten-1;
        border: round $accent-lighten-1;
    }

    /* ── Content ── */
    #content {
        padding: 1 3;
        background: $surface;
        overflow-y: scroll;
        border-left: panel $border-color;
        border-right: panel $border-color;
        margin: 0 2;
    }

    Markdown {
        padding: 0;
        margin: 0;
    }

    Markdown H1, Markdown H2 {
        border-bottom: solid $border-color;
        color: $accent-lighten-2;
    }

    Markdown BlockQuote {
        border-left: thick $accent;
        background: $boost;
        padding: 0 1;
        color: $text-muted;
    }

    Markdown Table {
        border: solid $border-color;
        margin: 1 0;
    }

    /* ── Status bar ── */
    #status-bar {
        height: 1;
        background: $panel;
        border-top: double $border-color;
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
            yield Button("⬅ Back", id="back-btn",    classes="nav-btn", disabled=True,  tooltip="Back (Alt+Left)")
            yield Button("Forward ➡", id="forward-btn", classes="nav-btn", disabled=True,  tooltip="Forward (Alt+Right)")
            yield Button("🔄 Refresh", id="refresh-btn", classes="nav-btn",                 tooltip="Refresh (Ctrl+R)")
            yield Button("🏠 Home",    id="home-btn",    classes="nav-btn",                 tooltip="Home (Ctrl+H)")
            yield Input(placeholder="Enter URL or search term…", id="url-bar")
            yield Button("Go 🚀", id="go-btn", tooltip="Navigate (Enter)")

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
            btn.label = "🛑 Stop" if loading else "🔄 Refresh"
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
        event.prevent_default()
        event.stop()

        href = event.href
        if href == "action:back":
            self.action_go_back()
        elif href == "action:home":
            self.action_go_home()
        elif "youtube.com/watch" in href or "youtu.be" in href or href.lower().endswith((".mp4", ".webm", ".avi", ".mkv")):
            full_url = urljoin(self._current_base_url, href) if self._current_base_url else href
            self.app.push_screen(VideoViewerModal(full_url))
        elif href.startswith("image-view:"):
            real_url = href.split("image-view:", 1)[1]
            full_url = urljoin(self._current_base_url, real_url) if self._current_base_url else real_url
            self.app.push_screen(ImageViewerModal(full_url, self._session))
        elif href.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", "svg", "ico")):
            full_url = urljoin(self._current_base_url, href) if self._current_base_url else href
            self.app.push_screen(ImageViewerModal(full_url, self._session))
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

        # Instantly intercept Direct YouTube Video Links
        if "youtube.com/watch" in url or "youtu.be" in url or url.lower().endswith((".mp4", ".webm", ".avi", ".mkv")):
            self.app.push_screen(VideoViewerModal(url))
            return

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
            # Special case: Quick visual intercept for raw youtube requests to avoid massive JS footers
            if "youtube.com" in url or "youtu.be" in url:
                if "watch" not in url:
                    self.call_from_thread(self._apply_page,
                        "# 🛑 YouTube / Empty Frame Detected\n\nYouTube requires heavy JavaScript which cannot run inside this terminal browser.\n\n### How to watch videos:\n- Search for videos using the search bar (e.g. `apple`, then click **[🎥 Videos]**)\n- Or Paste an exact video URL (e.g., `https://youtube.com/watch?v=...`) to instantly play it via the Terminal Video Player.",
                        url,
                        "YouTube (JS Disabled)"
                    )
                    return

            resp = self._session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            final_url = resp.url
            ctype = resp.headers.get("content-type", "").lower()

            if "text/html" in ctype or "application/xhtml" in ctype:
                markdown = html_to_markdown(resp.text, final_url)
                status = f"📄 {final_url}  [{resp.status_code}]"
            elif "text/plain" in ctype:
                text = resp.text.replace("`", "'")
                markdown = f"```\n{text}\n```"
                status = f"📄 {final_url}  [plain text]"
            elif ctype.startswith("image/"):
                markdown = f"# 🖼️ Image Viewer\n\n[Click here to view high-res image](image-view:{final_url})"
                status = f"🖼️ {final_url}  [{ctype}]"
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
        self.status = f"⚠️ {title}"

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

    # Compatibility wrapper for tests
    @staticmethod
    def _html_to_markdown(html: str, base_url: str) -> str:
        return html_to_markdown(html, base_url)