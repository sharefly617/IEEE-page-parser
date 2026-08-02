from bs4 import BeautifulSoup

from src.markdown_exporter import to_markdown
from src.mathjax import markdown_tex
from src.models import PaperMetadata


def test_markdown_preserves_formula_table_and_image():
    soup = BeautifulSoup('<main><h2>Method</h2><p>Energy <span data-tex="E=mc^2">x</span>.</p><table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table></main>', "lxml")
    text = to_markdown(soup.main, PaperMetadata(url="u", title="Test"))
    assert "## Method" in text
    assert "$E=mc^2$" in text
    assert "| A | B |" in text


def test_markdown_normalizes_latex_environment_and_delimiters():
    soup = BeautifulSoup(r'<main><p><span class="formula" data-tex="$$\begin{equation}x &= y\tag{1}\end{equation}$$">x</span> <span data-tex="$a_b$">a</span></p></main>', "lxml")
    text = to_markdown(soup.main, PaperMetadata(url="u", title="Test"))
    assert "$$$$" not in text
    assert r"$$x &= y$$" in text
    assert r"\tag" not in text
    assert r"\begin{equation}" not in text
    assert "$a_b$" in text


def test_markdown_align_drops_tags():
    value = markdown_tex(r"\begin{align}a &= b \tag{1}\\ c &= d \tag{2}\end{align}")
    assert r"\begin{aligned}" in value
    assert r"\tag" not in value
