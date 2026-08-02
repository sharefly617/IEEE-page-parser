from typing import Iterable, Optional

from bs4 import BeautifulSoup, Tag


DEFAULT_REMOVE_SELECTORS = [
    "script", "style", "nav", "header", "footer", "aside", "form",
    ".advertisement", ".ad", ".recommended", ".related", ".cookie",
    ".modal", ".popup", ".login-prompt",
]


def clean_document(html: str, content_selectors: Optional[Iterable[str]] = None,
                   remove_selectors: Optional[Iterable[str]] = None) -> BeautifulSoup:
    """Return a cleaned DOM while retaining article HTML, tables, images and math."""
    soup = BeautifulSoup(html, "lxml")
    for selector in list(remove_selectors or DEFAULT_REMOVE_SELECTORS):
        for node in soup.select(selector):
            if selector == "script":
                script_type = (node.get("type") or "").lower()
                if "math/tex" in script_type or "latex" in script_type or "ld+json" in script_type:
                    continue
            node.decompose()

    # IEEE Xplore MathJax v2 keeps the original TeX in <script type="math/tex">
    # and a second visual tree in .MathJax. Keep the source and remove only the
    # duplicate visual tree from converted outputs.
    for node in soup.select(".MathJax_Preview, .MathJax"):
        node.decompose()
    for node in soup.select("#article .links, #article .zoom-container, #article button.all"):
        node.decompose()

    candidates = []
    selectors = list(content_selectors or [])
    if selectors:
        # Explicit selectors are ordered preferences, not a pool scored against
        # the whole application shell.
        for selector in selectors:
            matches = soup.select(selector)
            if matches:
                chosen = max(matches, key=lambda n: len(n.get_text(" ", strip=True)))
                return BeautifulSoup(str(chosen), "lxml")
    else:
        selectors = ["#article", "article", "main", "[role='main']", ".article-content"]
    for selector in selectors:
        candidates.extend(soup.select(selector))
    if candidates:
        chosen = max(candidates, key=lambda n: len(n.get_text(" ", strip=True)))
        body = BeautifulSoup(str(chosen), "lxml")
        return body
    body = soup.body or soup
    return BeautifulSoup(str(body), "lxml")


def find_main_node(soup: BeautifulSoup) -> Tag:
    candidates = soup.select("#article, .ArticlePage, article, main") or [soup.body or soup]
    return max(candidates, key=lambda n: len(n.get_text(" ", strip=True)))
