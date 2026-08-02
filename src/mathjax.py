import json
import re
from typing import Any, Dict, Iterable, List, Optional

from bs4 import BeautifulSoup, Tag

from .models import Formula


_NUMBER_RE = re.compile(r"(?:equation|eq\.?|formula)[^0-9]*([0-9]+)", re.I)


def normalize_tex(tex: str) -> str:
    """Use amsmath-compatible bold macros without requiring the bm package."""
    value = tex.replace("\\boldsymbol", "\\mathbf")
    # Replace braced macros with a small brace-aware scanner so nested groups
    # such as \bm{\alpha_{k}} are handled without corrupting the TeX.
    while "\\bm" in value:
        start = value.find("\\bm")
        end = start + 3
        while end < len(value) and value[end].isspace():
            end += 1
        if end < len(value) and value[end] == "{":
            depth = 0
            close = None
            for index in range(end, len(value)):
                if value[index] == "{": depth += 1
                elif value[index] == "}":
                    depth -= 1
                    if depth == 0:
                        close = index
                        break
            if close is None:
                break
            value = value[:start] + "\\mathbf{" + value[end + 1:close] + "}" + value[close + 1:]
        elif end < len(value):
            value = value[:start] + "\\mathbf{" + value[end] + "}" + value[end + 1:]
        else:
            break
    return value


def _annotation(node: Tag) -> Optional[str]:
    ann = node.find("annotation", attrs={"encoding": "application/x-tex"})
    if ann and ann.string:
        return ann.string.strip()
    return None


def formula_tex(node: Tag) -> Optional[str]:
    """Extract original TeX from MathJax v2/v3 and common fallback markup."""
    ann = _annotation(node)
    if ann:
        return ann
    if node.name == "script" and node.string:
        return node.string.strip()
    source = node.find("script", type=re.compile(r"math/tex|latex", re.I))
    if source and source.string:
        return source.string.strip()
    hidden_source = node.select_one(".tex, .tex2jax_ignore")
    if hidden_source:
        value = hidden_source.get_text(" ", strip=True)
        if value:
            return value
    for attr in ("alttext", "data-tex", "data-latex", "data-original-text", "aria-label"):
        value = node.get(attr)
        if value and (attr != "aria-label" or "math" in value.lower() or "\\" in value):
            return value.strip()
    script = node.find_parent().find("script", type=re.compile(r"math/tex|latex", re.I)) if node.parent else None
    if script and script.string:
        return script.string.strip()
    return None


def is_formula_node(node: Tag) -> bool:
    if node.name in {"math", "mjx-container", "tex-math", "inline-formula", "disp-formula", "display-formula"}:
        return True
    classes = " ".join(node.get("class", []))
    return node.name in {"img", "span", "div", "script"} and (
        "MathJax" in classes or "math" in classes.lower() or "formula" in classes.lower() or node.get("data-tex") or "math/tex" in (node.get("type") or "").lower()
    )


def _display(node: Tag) -> bool:
    if node.name in {"disp-formula", "display-formula"}:
        return True
    tex = formula_tex(node)
    if tex and re.search(r"\\begin\{(?:equation\*?|align\*?|alignat\*?|gather\*?|multline\*?|split)\}", tex):
        return True
    if "formula" in " ".join(node.get("class", [])).lower():
        source = node.select_one(".tex, .tex2jax_ignore")
        if source and "\\begin{" in source.get_text():
            return True
    if node.name == "mjx-container" and node.get("display") == "true":
        return True
    classes = " ".join(node.get("class", []))
    if "display" in classes.lower() or node.get("data-display") in {"true", "block"}:
        return True
    return node.find_parent(["div", "figure", "section", "disp-formula", "display-formula"]) is not None and node.name in {"math", "mjx-container"}


def markdown_tex(tex: str) -> str:
    r"""Normalize source TeX for Markdown MathJax/KaTeX delimiters.

    Markdown already supplies the math delimiters, so nested `$`, `\[`, or
    equation environments must be removed before wrapping the source.
    """
    value = tex.strip()
    wrappers = (("\\[", "\\]"), ("\\(", "\\)"), ("$$", "$$"), ("$", "$"))
    changed = True
    while changed:
        changed = False
        for start, end in wrappers:
            if value.startswith(start) and value.endswith(end) and len(value) > len(start) + len(end):
                value = value[len(start):-len(end)].strip()
                changed = True
                break
    value = normalize_tex(value)
    # equation/align environments are LaTeX document environments. Inside a
    # Markdown display delimiter, aligned is the portable MathJax equivalent.
    environment_pattern = re.compile(
        r"^\\begin\{(equation\*?|align\*?|alignat\*?|gather\*?|multline\*?|split)\}(.*?)\\end\{\1\}$",
        re.S,
    )
    match = environment_pattern.match(value.strip())
    if match:
        environment, body = match.groups()
        if environment.startswith(("align", "alignat", "gather", "multline", "split")):
            value = r"\begin{aligned}" + body + r"\end{aligned}"
        else:
            value = body.strip()
    # Markdown MathJax/KaTeX cannot reliably combine alignment environments
    # with equation tags. Formula numbers remain available in formulas.json.
    value = re.sub(r"\\(?:tag\*?|notag)\s*\{[^{}]*\}", "", value)
    # Labels are useful in a LaTeX document but commonly make Markdown
    # MathJax/KaTeX fail; formula order and numbers remain in formulas.json.
    value = re.sub(r"\\label\{[^{}]*\}", "", value)
    return value.strip()


def collect_formulas(soup: BeautifulSoup) -> List[Formula]:
    formulas: List[Formula] = []
    seen = set()
    selectors = ["span.formula", "disp-formula", "display-formula", "inline-formula", "tex-math", "mjx-container", "math", "img[alttext]", "img[data-tex]", "script[type*='math/tex']", "script[type*='latex']"]
    nodes: List[Tag] = []
    for selector in selectors:
        nodes.extend(soup.select(selector))
    for node in nodes:
        marker = id(node)
        if marker in seen:
            continue
        if node.name == "math" and node.find_parent("mjx-container") is not None:
            continue
        if node.name == "script" and node.find_parent(["tex-math", "inline-formula", "disp-formula", "display-formula"]) is not None:
            continue
        if node.name == "tex-math" and node.find_parent(["inline-formula", "disp-formula", "display-formula"]) is not None:
            continue
        if node.name in {"tex-math", "script"} and node.find_parent("span", class_="formula") is not None:
            continue
        seen.add(marker)
        tex = formula_tex(node)
        svg = str(node.find("svg")) if node.find("svg") else None
        identifier = node.get("id", "")
        number_match = _NUMBER_RE.search(identifier) or _NUMBER_RE.search(node.get_text(" ", strip=True))
        formula = Formula(
            order=len(formulas) + 1,
            tex=tex,
            display=_display(node),
            number=number_match.group(1) if number_match else None,
            source=str(node)[:4000],
            svg=svg,
            conversion_status="ok" if tex else "needs_manual_review",
        )
        formulas.append(formula)
    return formulas


def formulas_json(formulas: Iterable[Formula]) -> str:
    return json.dumps([f.as_dict() for f in formulas], ensure_ascii=False, indent=2)
