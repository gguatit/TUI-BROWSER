"""HTML validation and Markdown parsing module for TUI Browser."""

import re
from urllib.parse import urljoin, unquote

import html2text
from bs4 import BeautifulSoup
from .constants import _error_page

def html_to_markdown(html: str, base_url: str) -> str:
    """Parse *html* and return a Markdown string suitable for display in TUI Browser."""
    try:
        soup = BeautifulSoup(html, "lxml")

        # Remove noisy / invisible elements
        _REMOVE_TAGS = ["script", "style", "noscript", "iframe", "svg", "canvas", "template"]
        for tag in soup.find_all(_REMOVE_TAGS):
            tag.decompose()

        # Convert images to clickable ANSI view links
        for img in soup.find_all("img"):
            src = img.get("data-src") or img.get("src")
            if src:
                src = urljoin(base_url, src)
                a_tag = soup.new_tag("a", href=f"image-view:{src}")
                alt_text = img.get("alt", "").strip() or "Image"
                a_tag.string = f"🖼️ [{alt_text}]"
                img.replace_with(a_tag)

        # Resolve relative links so Markdown.LinkClicked gets full URLs     
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href and not href.startswith(("#", "javascript:", "mailto:", "tel:", "image-view:")):
                a["href"] = urljoin(base_url, href)

        md_lines = []
        # Special case: Clean formatting for Brave Search Results
        if "search.brave.com/search" in base_url or "search.brave.com/images" in base_url or "search.brave.com/news" in base_url:
            query_term = ""
            if "?q=" in base_url:
                query_term = base_url.split("?q=")[-1].split("&")[0]        
                query_term = unquote(query_term).replace("+", " ")
            else:
                query_term = "Search"

            md_lines.append(f"# 🔎 Search Results for '{query_term}'\n")       
            md_lines.append(f"[🔎 Web](https://search.brave.com/search?q={query_term}) | [🖼️ Images](https://search.brave.com/images?q={query_term}) | [📰 News](https://search.brave.com/news?q={query_term}) | [🎥 Videos](https://search.brave.com/videos?q={query_term})\n")
            md_lines.append("---\n")

            if "search.brave.com/search" in base_url:
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
        converter.ignore_images = False      # keep image placeholders      
        converter.images_to_alt = True       # show [image: alt text]       
        converter.ignore_mailto_links = True
        converter.body_width = 0             # let the terminal handle wrapping
        converter.protect_links = True
        converter.wrap_links = False
        converter.single_line_break = False  # preserve paragraphs better   
        converter.pad_tables = True          # align tables nicely
        converter.unicode_snob = True

        md = converter.handle(str(soup))

        # Collapse runs of blank lines (\n) to at most two
        md = re.sub(r"\n{3,}", "\n\n", md)

        if md_lines:
            md = "\n".join(md_lines) + "\n\n" + md

        return md.strip()

    except Exception as exc:  # noqa: BLE001
        return _error_page("Render Error", f"Failed to render page content:\n\n`{exc}`")