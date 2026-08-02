from bs4 import BeautifulSoup

from src.latex_exporter import build_bibtex, to_latex
from src.models import PaperMetadata


def test_citations_get_compilable_placeholder_bib_entries():
    soup = BeautifulSoup('<main><p>Prior work <a ref-type="bibr" anchor="ref1">[1]</a>.</p></main>', "lxml")
    metadata = PaperMetadata(url="u", title="Paper")
    bib = build_bibtex(soup.main, metadata)
    tex = to_latex(soup.main, metadata)
    assert "@misc{ref1" in bib
    assert "\\cite{ref1}" in tex


def test_adjacent_citations_are_grouped():
    soup = BeautifulSoup('<main><p><a ref-type="bibr" anchor="ref24">[24]</a>, <a ref-type="bibr" anchor="ref30">[30]</a>, <a ref-type="bibr" anchor="ref34">[34]</a></p></main>', "lxml")
    tex = to_latex(soup.main, PaperMetadata(url="u", title="Paper"))
    assert "\\cite{ref24,ref30,ref34}" in tex
    assert tex.count("\\cite{") == 1
