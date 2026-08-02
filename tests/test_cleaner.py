from src.cleaner import clean_document
from src.extractor import PaperExtractor


def test_cleaner_removes_navigation_keeps_article():
    soup = clean_document('<html><body><nav>Menu</nav><article><h1>Paper</h1><p>Body</p></article></body></html>')
    assert soup.select_one("nav") is None
    assert soup.select_one("article").get_text(" ", strip=True) == "Paper Body"


def test_metadata_is_read_before_article_isolated():
    result = PaperExtractor().extract('<html><head><meta name="citation_title" content="A paper"></head><body><article><p>Body</p></article></body></html>', "https://example.com")
    assert result.metadata.title == "A paper"


def test_ieee_article_selector_excludes_page_shell():
    html = '<main><nav>Shell</nav><div id="BodyWrapper"><div id="article"><div class="section" id="sec1"><div class="header"><h2>Introduction</h2></div><p>Body</p></div></div></div></main>'
    result = PaperExtractor(["#BodyWrapper #article"]).extract(html, "https://example.com")
    assert result.body.select_one("#sec1") is not None
    assert result.body.select_one("nav") is None
