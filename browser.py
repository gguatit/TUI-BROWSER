'''TUI Browser'''
import sys
from tui_browser import TUIBrowser, _error_page, HOME_MARKDOWN

def main() -> None:
    app = TUIBrowser()
    app.run()

if __name__ == '__main__':
    main()
