# IEEE Paper Parser

中文说明：[README.zh-CN.md](README.zh-CN.md)

This project parses an IEEE paper page that the operator is authorized to access, then produces raw HTML, Markdown, and an IEEEtran LaTeX project. It uses a real Playwright browser so a user may reuse a local authenticated browser context, but it never automates login, CAPTCHA solving, paywall bypass, or other access-control circumvention.

## Install

```powershell
python -m venv .ieeeParser
.\.ieeeParser\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Single paper

The requested example URL is:

```text
https://ieeexplore.ieee.org/document/10684554
```

Run it only when you have permission to access the page (and, where required, configure a browser profile that you logged into manually):

```powershell
python main.py --url "https://ieeexplore.ieee.org/document/10684554" --output .\output --format all --wait-for-mathjax --save-screenshot --offline-check
```

Use `browser.channel: chrome` or `browser.channel: msedge` in `config.yaml` to use an already installed browser instead of downloading Playwright Chromium. You can also set `browser.executable_path` to an explicit browser executable. Use `browser.user_data_dir` to point to a separate local browser profile that you logged into manually. Close the normal browser before reusing a profile; Chromium locks profiles while running. The default configuration uses Chromium DevTools Protocol to promote `data-src`, `data-original`, `srcset`, picture sources, and background-image URLs without scrolling. Set `browser.auto_scroll: true` as a fallback for sites that hide lazy URLs inside application state. Images are waited on and downloaded through the authorized browser context when the server rejects direct requests.

## Batch mode

```powershell
python main.py --urls-file urls.txt --output .\output --format all --delay 2 --retries 2
```

Each URL is deduplicated and handled independently; failures are recorded in `summary.json`.

## Output

Each paper directory contains `raw/rendered.html`, an optional screenshot, `metadata.json`, `formulas/formulas.json`, `markdown/paper.md`, `latex/main.tex`, `latex/references.bib`, and `conversion_report.json`. Animated or static GIF media is converted to PNG for generated Markdown/LaTeX assets; the raw HTML remains unchanged. The browser attempts to expand the IEEE References panel before capture. When the authorized page exposes reference entries, they are parsed into BibTeX and citation anchors become `\\cite{refN}`. If IEEE reports that references are unavailable, compilable placeholder entries are emitted and the conversion report records the limitation. Missing source TeX is reported as `needs_manual_review`; rendered SVG/source DOM is retained in the formula JSON rather than silently discarded.

## Tests

```powershell
python -m pytest -q
```

The tests cover MathJax v2/v3-style extraction, Markdown tables/formulas, IEEEtran structure, cleaning, and safe asset naming without requiring a live IEEE session.
