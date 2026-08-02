# IEEE 论文网页归档工具 / IEEE Paper Parser

## 项目简介 / Overview

本项目用于归档操作者有权访问的 IEEE 论文网页，并生成原始 HTML、Markdown 和 IEEEtran LaTeX 工程。  
This project archives IEEE paper pages that the operator is authorized to access and produces raw HTML, Markdown, and an IEEEtran LaTeX project.

项目使用真实 Playwright 浏览器处理动态渲染，可复用用户手动登录的本地浏览器上下文；不会自动登录、识别验证码、绕过付费墙或规避其他访问控制。  
It uses a real Playwright browser and may reuse a manually authenticated local context; it never automates login, CAPTCHA solving, paywall bypass, or access-control circumvention.

## 合规要求 / Compliance

- 只处理用户明确指定且有权访问的 URL；遵守 IEEE 服务条款、`robots.txt` 和版权要求。  
  Process only explicitly specified URLs you are authorized to access; follow IEEE terms, `robots.txt`, and copyright requirements.
- 默认串行执行，并支持请求间隔、超时和有限重试。  
  Processing is serial by default with configurable delays, timeouts, and limited retries.
- 不自动处理登录失效、验证码或付费墙。  
  Login failures, CAPTCHAs, and paywalls are not handled automatically.

## 安装 / Installation

```powershell
python -m venv .ieeeParser
.\.ieeeParser\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## 单篇论文 / Single Paper

仅对获授权页面执行以下命令。  
Run this only for a page you are authorized to access.

```powershell
python main.py --url "https://ieeexplore.ieee.org/document/10684554" --output .\output --format all --wait-for-mathjax --save-screenshot --offline-check
```

也可在 `config.yaml` 中设置 `browser.channel: chrome`、`msedge` 或独立的 `browser.user_data_dir`。  
You may set `browser.channel: chrome`, `msedge`, or a separate `browser.user_data_dir` in `config.yaml`.

## 批量处理 / Batch Mode

将授权 URL 每行写入 `urls.txt`，程序会去重并独立记录失败项。  
Put one authorized URL per line in `urls.txt`; URLs are deduplicated and failures are recorded independently.

```powershell
python main.py --urls-file urls.txt --output .\output --format all --delay 2 --retries 2
```

## 输出 / Output

每篇论文通常生成以下文件：  
Each paper normally produces:

```text
output/<paper-slug>/
├─ raw/rendered.html
├─ raw/screenshot.png
├─ markdown/paper.md
├─ markdown/assets/
├─ latex/main.tex
├─ latex/references.bib
├─ latex/figures/
├─ metadata.json
├─ formulas/formulas.json
└─ conversion_report.json
```

公式优先保留原始 TeX；无法可靠转换时保留 SVG/DOM，并标记 `needs_manual_review`，不会静默丢失。  
Original TeX is preferred for formulas; if conversion is uncertain, SVG/DOM is retained and marked `needs_manual_review` rather than silently discarded.

## 测试 / Tests

```powershell
python -m pytest -q
```

测试不需要登录 IEEE，覆盖 MathJax、Markdown、IEEEtran 结构、正文清理、图片和参考文献处理。  
Tests do not require an IEEE session and cover MathJax, Markdown, IEEEtran structure, cleaning, assets, and references.

完整中文说明 / Full Chinese guide: [README.zh-CN.md](README.zh-CN.md)
