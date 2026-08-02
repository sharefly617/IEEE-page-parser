from bs4 import BeautifulSoup

from src.latex_exporter import to_latex
from src.markdown_exporter import to_markdown
from src.models import PaperMetadata


def test_ieee_div_figure_is_exported():
    soup = BeautifulSoup('<main><div class="figure" id="fig1"><div class="img-wrap"><img src="/fig.gif" /></div><div class="figcaption">Fig. 1. Demo</div></div></main>', "lxml")
    metadata = PaperMetadata(url="u", title="Paper")
    md = to_markdown(soup.main, metadata, {"/fig.gif": "assets/fig.gif"})
    tex = to_latex(soup.main, metadata, {"/fig.gif": "figures/fig.gif"})
    assert "![Fig. 1. Demo](assets/fig.gif)" in md
    assert "\\includegraphics" in tex
    assert ".gif" not in tex
