from dataclasses import dataclass
from typing import Iterable, Optional

from bs4 import BeautifulSoup, Tag

from .cleaner import clean_document, find_main_node
from .mathjax import collect_formulas
from .metadata import extract_metadata
from .models import Formula, PaperMetadata


@dataclass
class ExtractionResult:
    soup: BeautifulSoup
    body: Tag
    metadata: PaperMetadata
    formulas: list[Formula]


class PaperExtractor:
    def __init__(self, content_selectors: Optional[Iterable[str]] = None,
                 remove_selectors: Optional[Iterable[str]] = None):
        self.content_selectors = list(content_selectors or [])
        self.remove_selectors = list(remove_selectors or [])

    def extract(self, html: str, url: str) -> ExtractionResult:
        original = BeautifulSoup(html, "lxml")
        metadata = extract_metadata(original, url)
        soup = clean_document(html, self.content_selectors or None, self.remove_selectors or None)
        body = find_main_node(soup)
        formulas = collect_formulas(body)
        return ExtractionResult(soup=soup, body=body, metadata=metadata, formulas=formulas)
