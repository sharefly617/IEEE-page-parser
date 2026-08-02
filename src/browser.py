import logging
import time
from pathlib import Path
from typing import Optional


LOGGER = logging.getLogger(__name__)


class BrowserError(RuntimeError):
    pass


def _load_all_images_via_cdp(context: object, page: object) -> int:
    """Use Chromium Runtime.evaluate to promote lazy image URLs without scrolling."""
    expression = r"""() => {
      const urls = new Set();
      const add = (value) => {
        if (!value || value.startsWith('data:') || value.startsWith('blob:')) return;
        urls.add(new URL(value, document.baseURI).href);
      };
      for (const image of document.images) {
        image.loading = 'eager';
        for (const key of ['data-src', 'data-lazy-src', 'data-original', 'data-url']) add(image.getAttribute(key));
        if (image.dataset.srcset) image.srcset = image.dataset.srcset;
        const source = image.closest('picture');
        if (source) for (const item of source.querySelectorAll('source')) {
          const value = item.dataset.srcset || item.getAttribute('srcset');
          if (value) value.split(',').forEach(part => add(part.trim().split(/\s+/)[0]));
          if (item.dataset.src) add(item.dataset.src);
        }
        const replacement = image.dataset.src || image.dataset.lazySrc || image.dataset.original || image.dataset.url;
        if (replacement) image.src = replacement;
        add(image.currentSrc || image.src);
      }
      for (const node of document.querySelectorAll('[style*="background-image"], [data-bg], [data-background-image]')) {
        add(node.dataset.bg || node.dataset.backgroundImage);
        const match = (node.getAttribute('style') || '').match(/url\(["']?([^)'\"]+)/);
        if (match) add(match[1]);
      }
      return Array.from(urls);
    }"""
    try:
        cdp = context.new_cdp_session(page)
        result = cdp.send("Runtime.evaluate", {
            "expression": expression,
            "awaitPromise": True,
            "returnByValue": True,
        })
        return len((result.get("result") or {}).get("value") or [])
    except Exception:
        # Playwright's evaluator is a safe fallback for non-CDP test doubles.
        try:
            return len(page.evaluate(expression) or [])
        except Exception:
            return 0


def capture_page(url: str, raw_dir: Path, *, headless: bool = True,
                user_data_dir: Optional[str] = None, timeout_ms: int = 30000,
                navigation_timeout_ms: int = 60000, wait_for_mathjax: bool = True,
                save_screenshot: bool = True, scroll_pause_ms: int = 250,
                max_scrolls: int = 80, extra_wait_ms: int = 1000,
                channel: Optional[str] = None, executable_path: Optional[str] = None,
                expand_references: bool = True, asset_dir: Optional[Path] = None,
                auto_scroll: bool = True, load_all_images_via_cdp: bool = False,
                manual_login: bool = False) -> str:
    """Capture the final browser DOM. Playwright is imported lazily for testability."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Only http(s) URLs are allowed")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise BrowserError("Playwright is required; run `playwright install chromium`") from exc
    raw_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = None
        context = None
        try:
            launch_options = {"headless": headless}
            if channel:
                if channel not in {"chrome", "chrome-beta", "msedge", "msedge-beta"}:
                    raise ValueError("channel must be chrome, chrome-beta, msedge, or msedge-beta")
                launch_options["channel"] = channel
            if executable_path:
                launch_options["executable_path"] = executable_path
            if user_data_dir:
                context = playwright.chromium.launch_persistent_context(user_data_dir, **launch_options)
            else:
                browser = playwright.chromium.launch(**launch_options)
                context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            page.set_default_navigation_timeout(navigation_timeout_ms)
            page.goto(url, wait_until="domcontentloaded")
            if manual_login:
                if headless:
                    raise BrowserError("--manual-login requires browser.headless: false")
                print("\n请在打开的浏览器中完成 IEEE institution 登录。完成后回到此终端按 Enter 继续...", flush=True)
                input()
                page.reload(wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=navigation_timeout_ms)
            except Exception:
                LOGGER.info("Network did not become idle; continuing with DOM captured after domcontentloaded")
            if wait_for_mathjax:
                try:
                    page.wait_for_function("""() => !window.MathJax || !window.MathJax.startup ||
                      window.MathJax.startup.document?.state === 'rendered'""", timeout=5000)
                except Exception:
                    LOGGER.info("MathJax readiness check timed out; preserving rendered DOM")
            if load_all_images_via_cdp:
                LOGGER.info("Promoted %s lazy image/background URLs through Chromium CDP", _load_all_images_via_cdp(context, page))
            if auto_scroll:
                # Optional fallback for sites whose lazy loader hides URLs in
                # application state rather than data-* attributes.
                for pass_number in range(3):
                    page.evaluate("window.scrollTo(0, 0)")
                    page.wait_for_timeout(scroll_pause_ms)
                    stable_steps = 0
                    for _ in range(max_scrolls):
                        before_y = page.evaluate("window.scrollY")
                        page.evaluate("window.scrollBy(0, Math.max(window.innerHeight * 0.8, 400))")
                        page.wait_for_timeout(scroll_pause_ms)
                        after_y = page.evaluate("window.scrollY")
                        stable_steps = stable_steps + 1 if after_y <= before_y else 0
                        if stable_steps >= 2:
                            break
                    page.wait_for_timeout(max(scroll_pause_ms * 2, 500))
                    height = page.evaluate("document.body.scrollHeight")
                    if pass_number > 0 and height == page.evaluate("window.__archiverLastHeight || 0"):
                        break
                    page.evaluate("height => { window.__archiverLastHeight = height; }", height)
            try:
                page.wait_for_function("""() => Array.from(document.images).every(img => img.complete || !img.src)""", timeout=10000)
            except Exception:
                LOGGER.info("Some images did not report complete before capture; preserving their final DOM URLs")
            if expand_references:
                try:
                    references_button = page.locator("button#references").first
                    if references_button.is_visible():
                        references_button.click()
                        page.wait_for_timeout(500)
                        if load_all_images_via_cdp:
                            _load_all_images_via_cdp(context, page)
                except Exception:
                    LOGGER.info("Reference panel was not available or could not be expanded")
            page.wait_for_timeout(extra_wait_ms)
            html = page.content()
            (raw_dir / "rendered.html").write_text(html, encoding="utf-8")
            if asset_dir:
                try:
                    from .assets import download_assets_from_browser
                    import json
                    asset_map = download_assets_from_browser(page, html, url, asset_dir)
                    (raw_dir / "asset-map.json").write_text(json.dumps(asset_map, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    LOGGER.exception("Browser asset download failed; continuing with best-effort URL download")
            if save_screenshot:
                page.screenshot(path=str(raw_dir / "screenshot.png"), full_page=True)
            return html
        finally:
            if context:
                context.close()
            if browser:
                browser.close()
