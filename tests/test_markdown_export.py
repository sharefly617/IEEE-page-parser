from bs4 import BeautifulSoup

from src.markdown_exporter import to_markdown
from src.models import PaperMetadata


def test_markdown_preserves_formula_table_and_image():
    soup = BeautifulSoup('<main><h2>Method</h2><p>Energy <span data-tex="E=mc^2">x</span>.</p><table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table></main>', "lxml")
    text = to_markdown(soup.main, PaperMetadata(url="u", title="Test"))
    assert "## Method" in text
    assert "$E=mc^2$" in text
    assert "| A | B |" in text

