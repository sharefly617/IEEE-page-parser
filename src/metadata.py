import json
import re
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from .models import PaperMetadata


def _meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        node = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        if node and node.get("content"):
            return node["content"].strip()
    return ""


def extract_metadata(soup: BeautifulSoup, url: str) -> PaperMetadata:
    title_node = soup.select_one("h1.document-title, .document-title")
    title = _meta(soup, "citation_title", "DC.title") or (title_node.get_text(" ", strip=True) if title_node else "")
    if not title:
        title = soup.title.get_text(strip=True) if soup.title else "Untitled paper"
    title = re.sub(r"\s*\|\s*IEEE.*$", "", title, flags=re.I).strip()
    authors = [m.get("content", "").strip() for m in soup.find_all("meta", attrs={"name": re.compile(r"citation_author|DC.creator", re.I)}) if m.get("content")]
    if not authors:
        authors = [a.get_text(" ", strip=True) for a in soup.select(".authors-info, .authors a, .author, .author-name") if a.get_text(strip=True)]
    authors = list(dict.fromkeys(re.sub(r"\s*;\s*$", "", a).strip() for a in authors if a and a.lower() not in {"all authors", "authors"}))
    keywords = [x.strip() for x in re.split(r"[,;]", _meta(soup, "citation_keywords", "keywords")) if x.strip()]
    abstract = _meta(soup, "citation_abstract", "description")
    if not abstract:
        abstract_nodes = soup.select(".abstract-text-content, .abstract, #abstract")
        abstract_node = max(abstract_nodes, key=lambda n: len(n.get_text(" ", strip=True)), default=None)
        abstract = abstract_node.get_text(" ", strip=True) if abstract_node else ""
        abstract = re.sub(r"^Abstract:\s*", "", abstract, flags=re.I)
    doi = _meta(soup, "citation_doi", "DC.identifier")
    if not doi:
        doi_node = soup.select_one(".stats-document-abstract-doi")
        doi = re.sub(r"^DOI:\s*", "", doi_node.get_text(" ", strip=True), flags=re.I) if doi_node else ""
    if doi.startswith("https://doi.org/"):
        doi = doi.rsplit("/", 1)[-1]
    publication = _meta(soup, "citation_journal_title", "citation_conference")
    if not publication:
        publication_node = soup.select_one(".stats-document-abstract-publishedIn")
        publication = publication_node.get_text(" ", strip=True) if publication_node else ""
    published = _meta(soup, "citation_publication_date", "citation_date")
    if not published:
        published_node = soup.select_one(".doc-abstract-pubdate")
        published = published_node.get_text(" ", strip=True) if published_node else ""
    paper_id = _meta(soup, "citation_pdf_url")
    references: List[Dict[str, Any]] = []
    reference_nodes = soup.select(
        "#references-anchor li, #references-section-container li, "
        ".reference-list li, ol.references li, .bibliography li"
    )
    for index, ref in enumerate(reference_nodes, 1):
        text = ref.get_text(" ", strip=True)
        if not text or "references is not available" in text.lower():
            continue
        number_match = re.search(r"(?:^|\s|\[)(\d{1,3})(?:\]|[.)]\s)", text)
        key = number_match.group(1) if number_match else str(index)
        doi_match = re.search(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", text, re.I)
        year_match = re.search(r"\b(19|20)\d{2}\b", text)
        references.append({
            "key": key,
            "text": text,
            "doi": doi_match.group(0).rstrip(".,") if doi_match else None,
            "year": year_match.group(0) if year_match else None,
        })
    # JSON-LD is useful for sites that omit citation_* metadata.
    for node in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(node.string or "")
        except (TypeError, ValueError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("@type") in {"ScholarlyArticle", "Article"}:
                title = title or item.get("headline", "")
                if not authors and item.get("author"):
                    author_items = item["author"] if isinstance(item["author"], list) else [item["author"]]
                    authors = [a.get("name", "") if isinstance(a, dict) else str(a) for a in author_items]
    return PaperMetadata(url=url, title=title, authors=authors, abstract=abstract, keywords=keywords,
                         doi=doi or None, publication=publication or None, published=published or None,
                         paper_id=paper_id or None, references=references)
