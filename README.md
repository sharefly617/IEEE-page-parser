# IEEE 论文网页归档工具 / IEEE Paper Web Archiver

本项目用于归档操作者有权访问的 IEEE 论文网页，并生成原始 HTML、Markdown 和 IEEEtran LaTeX 工程。  
This project archives IEEE paper pages that the operator is authorized to access and produces raw HTML, Markdown, and an IEEEtran LaTeX project.

项目使用 Playwright 控制真实浏览器，等待动态内容和 MathJax 完成渲染。工具不会自动输入账号密码、处理验证码、绕过付费墙或规避其他访问控制。  
It uses Playwright to control a real browser and wait for dynamic content and MathJax rendering. It never enters credentials, solves CAPTCHAs, bypasses paywalls, or circumvents access controls.

## 合规边界 / Compliance

- 只处理用户明确指定且拥有授权的 URL，并遵守 IEEE 服务条款、`robots.txt`、版权要求和合理访问频率。  
  Process only explicitly specified URLs you are authorized to access, following IEEE terms, `robots.txt`, copyright requirements, and reasonable request rates.
- 默认串行运行，支持延迟、超时和有限重试。  
  Processing is serial by default with configurable delays, timeouts, and limited retries.
- 登录失效、验证码和付费墙由用户在浏览器中合法处理，工具不会自动绕过。  
  The user must handle expired login, CAPTCHAs, and paywalls lawfully in the browser; the tool does not bypass them.

## 安装 / Installation

```powershell
python -m venv .ieeescraping
.\.ieeescraping\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

如果选择 Playwright 自带 Chromium，还需要：  
If you select Playwright's bundled Chromium, also run:

```powershell
python -m playwright install chromium
```

## 登录模式 / Login Modes

在 `config.yaml` 的 `browser` 部分选择一种模式。  
Choose one mode in the `browser` section of `config.yaml`.

### 1. 公开页面，无登录 / Public page, no login

适用于无需账号即可访问的页面。  
Use this for pages accessible without an account.

```yaml
browser:
  channel: null
  headless: true
  user_data_dir: null
  manual_login: false
```

需要安装 Playwright Chromium：`python -m playwright install chromium`。  
Install Playwright Chromium with `python -m playwright install chromium`.

### 2. 使用已安装的 Chrome 或 Edge / Use installed Chrome or Edge

适用于不需要复用登录状态，但希望使用本机浏览器程序的情况。  
Use this when you want the installed browser binary without reusing a login session.

```yaml
browser:
  channel: chrome       # 或 msedge / or msedge
  headless: true
  user_data_dir: null
  manual_login: false
```

此模式不需要下载 Playwright Chromium。  
This mode does not require downloading Playwright Chromium.

### 3. 手动登录并复用配置 / Manual login with a persistent profile

适用于你有权通过机构账号访问论文的情况。工具会打开可见浏览器，你手动完成登录后回到终端按 Enter。  
Use this when you are authorized to access the paper through an institutional account. The tool opens a headed browser; complete login manually, then return to the terminal and press Enter.

```yaml
browser:
  channel: chrome       # 或 msedge / or msedge
  headless: false
  user_data_dir: "C:/Users/YourName/AppData/Local/IEEE-archiver-profile"
  manual_login: true
```

也可以只对单次运行启用手动登录：  
You can enable manual login for one run:

```powershell
python main.py --url "https://ieeexplore.ieee.org/document/10684554" --manual-login --format all
```

复用配置目录前请关闭使用该目录的普通 Chrome/Edge 窗口。工具会启动新的浏览器进程，不会连接已经打开的普通浏览器窗口。  
Close any normal Chrome/Edge process using the same profile before reusing it. The tool launches a new browser process; it does not attach to an already-running ordinary browser window.

## 单篇论文 / Single Paper

示例 URL：`https://ieeexplore.ieee.org/document/10684554`。仅在你拥有访问授权时运行。  
Example URL: `https://ieeexplore.ieee.org/document/10684554`. Run it only when you are authorized to access it.

```powershell
python main.py --url "https://ieeexplore.ieee.org/document/10684554" --output .\output --format all --wait-for-mathjax --save-screenshot --offline-check
```

`--format` 支持 `raw`、`markdown`、`latex` 和 `all`。  
`--format` supports `raw`, `markdown`, `latex`, and `all`.

## 批量归档 / Batch Mode

`urls.txt` 每行放置一个已授权 URL。程序会去重，并独立记录每篇论文的失败。  
Put one authorized URL per line in `urls.txt`. URLs are deduplicated and failures are recorded independently.

```powershell
python main.py --urls-file urls.txt --output .\output --format all --delay 2 --retries 2
```

## 输出结构 / Output Structure

```text
output/<paper-slug>/
├─ raw/rendered.html
├─ raw/screenshot.png
├─ markdown/paper.md
├─ markdown/structure.json
├─ markdown/assets/
├─ latex/main.tex
├─ latex/references.bib
├─ latex/figures/
├─ metadata.json
├─ formulas/formulas.json
└─ conversion_report.json
```

原始 TeX 优先用于公式转换；无法可靠转换时会保留 SVG/DOM 并标记 `needs_manual_review`，不会静默丢弃。  
Original TeX is preferred for formulas. If conversion is uncertain, SVG/DOM is retained and marked `needs_manual_review` instead of being silently discarded.

## 测试 / Tests

```powershell
python -m pytest -q
```

测试不需要登录 IEEE，覆盖 MathJax、Markdown、IEEEtran 结构、正文清理、资源安全和参考文献处理。  
Tests do not require an IEEE session and cover MathJax, Markdown, IEEEtran structure, content cleaning, asset safety, and references.

