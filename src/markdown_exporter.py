import html
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import NavigableString, Tag

from .mathjax import _display, formula_tex, is_formula_node, markdown_tex
from .models import PaperMetadata


def _inline(node: object, assets: Dict[str, str]) -> str:
    if isinstance(node, NavigableString):
        return re.sub(r"\\s+", " ", str(node))
    if not isinstance(node, Tag):
        return ""
    if is_formula_node(node):
        tex = formula_tex(node)
        if tex:
            value = markdown_tex(tex)
            return f"$${value}$$" if _display(node) else f"${value}$"
        return "<!-- formula requires manual review -->" + str(node)
    name = node.name.lower()
    inner = "".join(_inline(child, assets) for child in node.children)
    if name in {"strong", "b"}: return f"**{inner.strip()}**"
    if name in {"em", "i"}: return f"*{inner.strip()}*"
    if name == "sup": return f"^{inner.strip()}^"
    if name == "sub": return f"~{inner.strip()}~"
    if name == "br": return "\n"
    if name == "a":
        href = node.get("href", "#")
        if href.startswith("javascript:"):
            return inner
        return f"[{inner.strip()}]({href})"
    if name == "img":
        src = assets.get(node.get("src", ""), node.get("src", ""))
        return f"![{node.get('alt', '')}]({src})"
    return inner


def _table(node: Tag, assets: Dict[str, str]) -> str:
    rows = []
    for tr in node.find_all("tr"):
        cells = [re.sub(r"\s+", " ", _inline(c, assets).strip()) for c in tr.find_all(["th", "td"], recursive=False)]
        if cells: rows.append(cells)
    if not rows: return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines.extend("| " + " | ".join(r) + " |" for r in rows[1:])
    return "\n".join(lines)


def _block_lines(node: Tag, assets: Dict[str, str], level: int = 2) -> List[str]:
    """Render IEEE's #article/.section/.section_2 hierarchy without flattening it."""
    lines: List[str] = []
    name = node.name.lower()
    classes = set(node.get("class", []))
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        lines += ["#" * min(level, 6) + " " + _inline(node, assets).strip(), ""]
    elif name == "div" and "header" in classes:
        heading = node.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        if heading:
            lines += ["#" * min(level, 6) + " " + _inline(heading, assets).strip(), ""]
    elif name == "p":
        text = _inline(node, assets).strip()
        if text: lines += [text, ""]
    elif name in {"ul", "ol"}:
        for i, li in enumerate(node.find_all("li", recursive=False), 1):
            lines.append(f"{i}. {_inline(li, assets).strip()}" if name == "ol" else f"- {_inline(li, assets).strip()}")
        lines.append("")
    elif name == "table":
        table = _table(node, assets)
        if table: lines += [table, ""]
    elif name == "figure" or (name == "div" and "figure" in classes):
        image = node.find("img")
        if image:
            link = node.select_one("a[data-fig-id][href], a[href]")
            image_url = (link.get("href") if link and link.get("href") else image.get("src", ""))
            src = assets.get(image_url, assets.get(image.get("src", ""), image_url))
            caption = node.select_one("figcaption, .figcaption, caption, .caption")
            lines += [f"![{caption.get_text(' ', strip=True) if caption else image.get('alt', '')}]({src})", ""]
    elif name in {"div", "section", "article"}:
        node_id = node.get("id", "")
        nested_section = "section_2" in classes or (node_id.startswith(("sec", "app")) and not re.fullmatch(r"(?:sec|app)\d+", node_id))
        child_level = level + 1 if nested_section else level
        for child in node.find_all(recursive=False):
            if isinstance(child, Tag):
                lines.extend(_block_lines(child, assets, child_level))
    elif name == "blockquote":
        text = _inline(node, assets).strip()
        if text: lines += ["> " + text, ""]
    return lines


def to_markdown(body: Tag, metadata: PaperMetadata, assets: Optional[Dict[str, str]] = None) -> str:
    assets = assets or {}
    lines: List[str] = [f"# {metadata.title}", ""]
    if metadata.authors: lines += ["**Authors:** " + ", ".join(metadata.authors), ""]
    if metadata.abstract: lines += ["## Abstract", "", metadata.abstract, ""]
    if metadata.keywords: lines += ["**Keywords:** " + ", ".join(metadata.keywords), ""]
    for node in body.find_all(recursive=False):
        if isinstance(node, Tag):
            lines.extend(_block_lines(node, assets, 2))
    return "\n".join(lines).strip() + "\n"


def write_markdown(path: Path, body: Tag, metadata: PaperMetadata, assets: Optional[Dict[str, str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_markdown(body, metadata, assets), encoding="utf-8")
    (path.parent / "README.md").write_text("# Markdown archive\n\nRender with a Markdown engine configured for MathJax or KaTeX.\n", encoding="utf-8")
    mapping = []
    for index, node in enumerate(body.find_all(True), 1):
        if node.name in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "figure", "table"}:
            mapping.append({"markdown_index": index, "dom_tag": node.name, "dom_id": node.get("id")})
    (path.parent / "structure.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
