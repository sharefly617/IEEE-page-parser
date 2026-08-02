from bs4 import BeautifulSoup

from src.latex_exporter import to_latex
from src.models import PaperMetadata
from src.validator import validate_latex


def test_latex_is_ieeetran(tmp_path):
    soup = BeautifulSoup('<main><h2>Results</h2><p>Text</p></main>', "lxml")
    text = to_latex(soup.main, PaperMetadata(url="u", title="A & B", abstract="Summary"))
    path = tmp_path / "main.tex"
    path.write_text(text, encoding="utf-8")
    assert "IEEEtran" in text
    assert validate_latex(path)["valid"]


def test_mathjax_align_star_environment_is_preserved():
    soup = BeautifulSoup('<main><p><span class="formula"><span class="tex">\\begin{align*}a &= b \\tag{1}\\end{align*}</span></span></p></main>', "lxml")
    text = to_latex(soup.main, PaperMetadata(url="u", title="Paper"))
    assert "\\begin{align*}" in text
    assert "\\end{align*}" in text
    assert "\\begin{align}" not in text
