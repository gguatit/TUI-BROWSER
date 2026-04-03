# TUI Browser 🌐

A **cross-platform terminal web browser** built with Python and [Textual](https://textual.textualize.io/).

- ✅ Works on **Windows, macOS, and Linux** terminals
- 🖱️ Full **mouse interaction** — click links, scroll, button clicks
- 🎨 Clean, minimal **dark UI** with readable typography
- ⌨️ Intuitive **keyboard shortcuts**
- 🔒 **Error-safe** — graceful handling of connection errors, timeouts, redirects, and unsupported content

---

## Screenshot

```
┌─────────────────────────────────────────────────────────────────────┐
│ TUI Browser                                                         │
│ ◀  ▶  ↺  ⌂  [ Enter URL or search term…                    ] [ Go ]│
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  🌐 TUI Browser                                                     │
│                                                                     │
│  Welcome to TUI Browser — a clean, lightweight terminal web browser.│
│                                                                     │
│  Quick Links                                                        │
│  • Brave Search                                                     │
│  • Wikipedia (Mobile)                                               │
│  • Hacker News                                                      │
│  • Python 3 Docs                                                    │
│  • GitHub                                                           │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ Ready                                                               │
│ Ctrl+L URL Bar  Ctrl+R Refresh  Alt+Left Back  Ctrl+Q Quit         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Requirements

- Python 3.8+
- Internet connection

## Installation

```bash
# Clone the repository
git clone https://github.com/gguatit/TUI-BROWSER.git
cd TUI-BROWSER

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
python browser.py
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+L` | Focus URL bar (select all) |
| `Ctrl+R` | Refresh current page |
| `Alt+Left` | Go back in history |
| `Alt+Right` | Go forward in history |
| `Ctrl+H` | Go to home page |
| `Ctrl+Q` | Quit the browser |
| `Escape` | Return focus to content area |

### URL Bar Behaviour

| Input | Action |
|-------|--------|
| `https://example.com` | Navigate directly |
| `example.com` | Adds `https://` automatically |
| `search term` | Brave search |

---

## Running Tests

```bash
pip install pytest pytest-asyncio
python -m pytest tests.py -v
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `textual` | TUI framework (cross-platform, mouse support) |
| `requests` | HTTP client |
| `html2text` | HTML → Markdown conversion |
| `beautifulsoup4` | HTML parsing & sanitisation |
| `lxml` | Fast HTML parser backend |
