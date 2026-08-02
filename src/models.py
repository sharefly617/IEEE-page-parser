from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Formula:
    order: int
    tex: Optional[str]
    display: bool
    number: Optional[str] = None
    source: str = ""
    svg: Optional[str] = None
    conversion_status: str = "ok"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "order": self.order,
            "tex": self.tex,
            "display": self.display,
            "number": self.number,
            "source": self.source,
            "svg": self.svg,
            "conversion_status": self.conversion_status,
        }


@dataclass
class PaperMetadata:
    url: str
    title: str = "Untitled paper"
    authors: List[str] = field(default_factory=list)
    affiliations: List[str] = field(default_factory=list)
    abstract: str = ""
    keywords: List[str] = field(default_factory=list)
    doi: Optional[str] = None
    publication: Optional[str] = None
    published: Optional[str] = None
    paper_id: Optional[str] = None
    references: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "authors": self.authors,
            "affiliations": self.affiliations,
            "abstract": self.abstract,
            "keywords": self.keywords,
            "doi": self.doi,
            "publication": self.publication,
            "published": self.published,
            "paper_id": self.paper_id,
            "references": self.references,
        }

