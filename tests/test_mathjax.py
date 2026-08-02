from bs4 import BeautifulSoup

from src.mathjax import collect_formulas, formula_tex, normalize_tex


def test_mathjax_v3_annotation_and_display():
    soup = BeautifulSoup('<mjx-container display="true"><math><annotation encoding="application/x-tex">\\frac{1}{2}</annotation></math></mjx-container>', "lxml")
    formulas = collect_formulas(soup)
    assert len(formulas) == 1
    assert formulas[0].tex == r"\frac{1}{2}"
    assert formulas[0].display is True


def test_img_alttext_fallback():
    soup = BeautifulSoup('<img class="MathJax" alttext="x^2" />', "lxml")
    assert formula_tex(soup.img) == "x^2"


def test_bm_is_normalized_for_latex_export():
    assert normalize_tex(r"\bm{\alpha}_{k} + \bm x") == r"\mathbf{\alpha}_{k} + \mathbf{x}"
