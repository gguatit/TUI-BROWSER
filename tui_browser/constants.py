"""Constants and configuration for TUI Browser."""

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
# 🌍 TUI Browser

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
# ⚠️ {title}

{message}

---

[⬅️ Go Back](action:back) | [🏠 Home](action:home)
"""

def _error_page(title: str, message: str) -> str:
    """Helper to format an error markdown page."""
    return _ERROR_TEMPLATE.format(title=title, message=message)