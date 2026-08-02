# IEEE 论文网页归档工具

英文说明：[README.md](README.md)

本项目用于归档操作者**有权访问**的 IEEE 论文网页，并生成可离线使用的原始 HTML、Markdown 和 IEEEtran LaTeX 工程。项目使用真实的 Playwright 浏览器处理动态渲染，可复用用户手动登录的本地浏览器上下文，但不会自动登录、识别验证码、绕过付费墙或规避其他访问控制。

## 合规与使用边界

- 只处理用户明确指定且有权访问的 URL。
- 遵守 IEEE 服务条款、`robots.txt`、版权要求和合理的访问频率限制。
- 默认串行执行，并支持请求间隔、超时和有限重试。
- 不自动处理登录失效、验证码或付费墙；遇到这些情况请由用户在浏览器中合法处理。

## 安装

```powershell
python -m venv .ieeeParser
.\.ieeeParser\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

也可以在 `config.yaml` 中设置 `browser.channel: chrome` 或 `browser.channel: msedge`，使用本机已安装的浏览器。若需要复用已手动登录的浏览器配置，设置独立的 `browser.user_data_dir`；复用配置目录前请先关闭该浏览器。

## 归档单篇论文

仅对你获授权访问的页面执行：

```powershell
python main.py --url "https://ieeexplore.ieee.org/document/10684554" --output .\output --format all --wait-for-mathjax --save-screenshot --offline-check
```

`--format` 支持 `raw`、`markdown`、`latex` 和 `all`。程序会等待页面与 MathJax 完成渲染，处理懒加载资源，保存最终 DOM，并按需重新打开离线页面进行检查。

## 批量归档

`urls.txt` 每行填写一个授权访问的论文 URL：

```powershell
python main.py --urls-file urls.txt --output .\output --format all --delay 2 --retries 2
```

URL 会自动去重；单篇失败会记录在 `summary.json` 中，不会阻止其他条目继续处理。已成功归档的条目默认跳过。

## 输出结构

每篇论文的目录通常包含：

```text
output/<paper-slug>/
├─ raw/rendered.html       # 浏览器最终渲染的 HTML
├─ raw/screenshot.png      # 可选截图
├─ markdown/paper.md       # Markdown 正文和相对资源路径
├─ markdown/assets/        # Markdown 使用的图片等资源
├─ latex/main.tex          # IEEEtran 工程入口
├─ latex/references.bib    # BibTeX 参考文献
├─ latex/figures/          # LaTeX 图片
├─ metadata.json            # DOI、作者、标题等元数据
├─ formulas/formulas.json  # 原始 TeX、公式类型和来源节点
└─ conversion_report.json  # 警告、占位内容和人工检查项
```

公式优先使用页面提供的原始 TeX，Markdown 使用 `$...$`/`$$...$$`，LaTeX 使用相应的数学环境。若只能取得渲染后的 SVG 或 DOM，项目会保留这些内容并在转换报告中标记 `needs_manual_review`，不会静默丢弃公式。参考文献可用时会生成 BibTeX 和 `\\cite{refN}` 引用；页面不提供完整信息时会生成可编译的占位条目并记录警告。

## 测试与 LaTeX 检查

```powershell
python -m pytest -q
```

测试不需要登录 IEEE，覆盖 MathJax v2/v3 公式提取、Markdown 表格和公式、IEEEtran 结构、正文清理、图片命名和参考文献处理。若本机安装了 LaTeX，可在生成的 `latex/` 目录运行：

```powershell
pdflatex -interaction=nonstopmode main.tex
```

## 已知限制

不同 IEEE 页面模板的 DOM 结构可能变化，正文选择器集中在 `config.yaml` 中可调整。无法下载的资源、无法还原的复杂表格以及缺少原始 TeX 的公式都会保留可用的原始内容，并写入日志和转换报告，供人工校对。
