import re
import unicodedata
from pathlib import Path
import shutil
from typing import Dict, Optional

from bs4 import NavigableString, Tag

from .assets import convert_gif_assets
from .mathjax import _display, formula_tex, is_formula_node, normalize_tex
from .models import PaperMetadata


def _escape(text: str) -> str:
    return re.sub(r"([#$%&_{}])", r"\\\1", text)


def _latex_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    text = (text.replace("\u00a0", " ").replace("\u200b", "")
            .replace("\u2212", "-").replace("\u2013", "--").replace("\u2014", "---")
            .replace("\u2018", "`").replace("\u2019", "'")
            .replace("\u201c", "``").replace("\u201d", "''"))
    return re.sub(r"([#$%&_{}])", r"\\\1", text)


def _latex_formula(tex: str) -> str:
    # amsmath permits \tag inside starred equation/align environments, so keep
    # the MathJax source environment unchanged. Only normalize unsupported
    # bold macros in the source TeX.
    return normalize_tex(tex).strip()


def _latex_image_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return str(Path(path).with_suffix(".png")).replace("\\", "/") if suffix == ".gif" else path


def _citation_key(node: Tag) -> Optional[str]:
    if node.get("ref-type") != "bibr":
        return None
    raw = " ".join(str(node.get(attr, "")) for attr in ("anchor", "data-range", "id"))
    match = re.search(r"(?:ref|context_ref_?)(\d+)", raw, re.I)
    return f"ref{match.group(1)}" if match else None


def _cited_keys(body: Tag) -> set[str]:
    return {key for node in body.select("a[ref-type='bibr']") if (key := _citation_key(node))}


def _bib_escape(value: str) -> str:
    return value.replace("\\", "").replace("{", "").replace("}", "").replace("&", r"\&").replace("%", r"\%")


def build_bibtex(body: Tag, metadata: PaperMetadata) -> str:
    """Build compilable BibTeX, using page references or explicit placeholders."""
    refs = {f"ref{str(item.get('key'))}": item for item in metadata.references}
    keys = sorted(_cited_keys(body), key=lambda value: int(re.search(r"\d+", value).group(0)))
    keys.extend(key for key in refs if key not in keys)
    entries = []
    for key in keys:
        item = refs.get(key)
        number = key.removeprefix("ref")
        if item:
            raw = _bib_escape(item.get("text", ""))
            doi = item.get("doi")
            year = item.get("year")
            fields = [f"  title = {{{raw}}}", f"  note = {{IEEE reference {number}: {raw}}}"]
            if year: fields.append(f"  year = {{{year}}}")
            if doi: fields.append(f"  doi = {{{_bib_escape(doi)}}}")
            entries.append("@misc{" + key + ",\n" + ",\n".join(fields) + "\n}")
        else:
            entries.append("@misc{" + key + ",\n" +
                           f"  title = {{Reference {number}}},\n" +
                           "  note = {Reference metadata was not exposed by the authorized IEEE page; manual completion required}\n}")
    return "\n\n".join(entries) + ("\n" if entries else "")


def _latex_inline(node: object, assets: Dict[str, str]) -> str:
    if isinstance(node, NavigableString):
        return _latex_text(str(node))
    if not isinstance(node, Tag):
        return ""
    if is_formula_node(node):
        tex = formula_tex(node)
        if not tex:
            return ""
        value = _latex_formula(tex)
        if _display(node) or value.startswith("\\begin{"):
            return value if value.startswith("\\begin{") else "\\[" + value + "\\]"
        return "\\(" + value + "\\)"
    citation = _citation_key(node)
    if citation:
        return "\\cite{" + citation + "}"
    name = node.name.lower()
    inner = _latex_children(node, assets)
    if name in {"strong", "b"}: return "\\textbf{" + inner.strip() + "}"
    if name in {"em", "i"}: return "\\textit{" + inner.strip() + "}"
    if name == "sup": return "\\textsuperscript{" + inner.strip() + "}"
    if name == "sub": return "\\textsubscript{" + inner.strip() + "}"
    if name == "br": return "\\\\\n"
    if name == "img": return ""
    return inner


def _latex_children(node: Tag, assets: Dict[str, str]) -> str:
    r"""Coalesce adjacent IEEE citation anchors into one \cite command."""
    output = []
    pending: list[str] = []

    def flush() -> None:
        if pending:
            output.append("\\cite{" + ",".join(dict.fromkeys(pending)) + "}")
            pending.clear()

    for child in node.children:
        key = _citation_key(child) if isinstance(child, Tag) else None
        if key:
            pending.append(key)
            continue
        if pending and isinstance(child, NavigableString):
            separator = str(child)
            if re.fullmatch(r"[\s,;:()\[\]–—-]+", separator) or re.fullmatch(r"\s+(?:and|or)\s+", separator):
                continue
        flush()
        output.append(_latex_inline(child, assets))
    flush()
    return "".join(output)


def _coalesce_citations(text: str) -> str:
    """Merge citation commands separated only by whitespace or punctuation."""
    pattern = re.compile(r"\\cite\{([^{}]+)\}((?:\s*(?:[,;]|and|or)?\s*\\cite\{[^{}]+\})+)")

    def replace(match: re.Match[str]) -> str:
        values = [match.group(1)] + re.findall(r"\\cite\{([^{}]+)\}", match.group(2))
        keys = []
        for value in values:
            for key in value.split(","):
                if key not in keys:
                    keys.append(key)
        return "\\cite{" + ",".join(keys) + "}"

    previous = None
    while previous != text:
        previous = text
        text = pattern.sub(replace, text)
    return text


def _body_latex(body: Tag, assets: Dict[str, str]) -> str:
    out = []
    def render(parent: Tag, section_level: int = 1) -> None:
      for node in parent.find_all(recursive=False):
        if not isinstance(node, Tag): continue
        name = node.name.lower()
        classes = set(node.get("class", []))
        if name == "div" and "header" in classes:
            heading = node.find(["h1", "h2", "h3", "h4", "h5", "h6"])
            if heading:
                command = {1: "section", 2: "subsection", 3: "subsubsection"}.get(section_level, "paragraph")
                out.append(f"\\{command}{{{_latex_text(_latex_inline(heading, assets).strip())}}}")
        elif name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            command = {"h1":"section","h2":"subsection","h3":"subsubsection"}.get(name, "paragraph")
            out.append(f"\\{command}{{{_latex_text(_latex_inline(node, assets).strip())}}}")
        elif name == "p": out.append(_latex_inline(node, assets).strip())
        elif name == "div" and "figure" in classes:
            image = node.find("img")
            if image:
                link = node.select_one("a[data-fig-id][href], a[href]")
                image_url = (link.get("href") if link and link.get("href") else image.get("src", ""))
                src = _latex_image_path(assets.get(image_url, assets.get(image.get("src", ""), image_url)))
                caption = node.select_one("figcaption, .figcaption, caption, .caption, .figure-caption")
                caption_text = caption.get_text(" ", strip=True) if caption else image.get("alt", "")
                out.append("\\begin{figure}[!t]\n\\centering\n\\includegraphics[width=\\columnwidth]{" + src.replace("assets/", "../markdown/assets/") + "}\n\\caption{" + _escape(caption_text) + "}\n\\end{figure}")
        elif name == "div" and ("section" in classes or "section_2" in classes or node.get("id", "").startswith(("sec", "app"))):
            nested = section_level + 1 if "section_2" in classes or (node.get("id", "").startswith(("sec", "app")) and not re.fullmatch(r"(?:sec|app)\d+", node.get("id", ""))) else section_level
            render(node, nested)
        elif name == "figure":
            image = node.find("img")
            if image:
                src = _latex_image_path(assets.get(image.get("src", ""), image.get("src", "")))
                out.append("\\begin{figure}[!t]\n\\centering\n\\includegraphics[width=\\columnwidth]{" + src.replace("assets/", "../markdown/assets/") + "}\n\\caption{" + _escape((node.find(["figcaption", "caption"]).get_text(" ", strip=True) if node.find(["figcaption", "caption"]) else "")) + "}\n\\end{figure}")
        elif name == "table":
            rows = []
            for tr in node.find_all("tr"):
                cells = [_latex_inline(c, assets).strip() for c in tr.find_all(["th", "td"], recursive=False)]
                if cells: rows.append(" & ".join(cells) + r" \\")
            if rows:
                cols = max(1, len(rows[0].split(" & ")))
                out.append("\\begin{table}[!t]\n\\centering\n\\begin{tabular}{" + "l" * cols + "}\n" + "\n".join(rows) + "\n\\end{tabular}\n\\end{table}")
        else:
            if name in {"div", "section", "article", "blockquote", "ul", "ol"}:
                render(node, section_level)
            else:
                text = _latex_inline(node, assets).strip()
                if text: out.append(text)
    render(body)
    return _coalesce_citations("\n\n".join(out))


def to_latex(body: Tag, metadata: PaperMetadata, assets: Optional[Dict[str, str]] = None) -> str:
    assets = assets or {}
    author = " \\and ".join(_escape(a) for a in metadata.authors) or "Unknown author"
    abstract = _escape(metadata.abstract)
    keywords = ", ".join(_escape(k) for k in metadata.keywords)
    body_text = _body_latex(body, assets)
    return "\\documentclass[conference]{IEEEtran}\n\\usepackage{amsmath,amssymb,graphicx}\n\\usepackage[T1]{fontenc}\n\\usepackage[utf8]{inputenc}\n\\begin{document}\n" + \
        f"\\title{{{_escape(metadata.title)}}}\n\\author{{{author}}}\n\\maketitle\n" + \
        (f"\\begin{{abstract}}{abstract}\\end{{abstract}}\n" if abstract else "") + \
        (f"\\begin{{IEEEkeywords}}{keywords}\\end{{IEEEkeywords}}\n" if keywords else "") + body_text + "\n\\bibliographystyle{IEEEtran}\n\\bibliography{references}\n\\end{document}\n"


def write_latex(directory: Path, body: Tag, metadata: PaperMetadata, assets: Optional[Dict[str, str]] = None) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "figures").mkdir(exist_ok=True)
    latex_assets = convert_gif_assets(directory.parent / "markdown" / "assets", dict(assets or {}))
    for source_url, relative in latex_assets.items():
        if not relative.startswith("assets/"):
            continue
        source = directory.parent / "markdown" / relative
        target = directory / "figures" / Path(relative).name
        if source.exists():
            shutil.copy2(source, target)
            latex_assets[ source_url ] = "figures/" + target.name
    (directory / "main.tex").write_text(to_latex(body, metadata, latex_assets), encoding="utf-8")
    (directory / "references.bib").write_text(build_bibtex(body, metadata), encoding="utf-8")
    (directory / "README.md").write_text("# IEEEtran archive\n\nCompile with `pdflatex -interaction=nonstopmode main.tex`, then run `bibtex main`, followed by two more `pdflatex` passes. Placeholder entries are emitted when the authorized page does not expose its reference list.\n", encoding="utf-8")
