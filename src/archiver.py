import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import yaml

from .assets import convert_gif_assets, download_assets
from .browser import capture_page
from .extractor import PaperExtractor
from .latex_exporter import write_latex
from .mathjax import formulas_json
from .markdown_exporter import write_markdown
from .validator import validate_archive

LOGGER = logging.getLogger(__name__)


def slugify(url: str, title: str = "paper") -> str:
    value = title or urlparse(url).path.rsplit("/", 1)[-1] or "paper"
    value = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return value[:80] or "paper"


def archive_one(url: str, output: Path, config: Dict[str, Any], formats: str = "all",
                *, wait_for_mathjax: Optional[bool] = None, save_screenshot: Optional[bool] = None) -> Dict[str, Any]:
    if not url.startswith(("http://", "https://")):
        raise ValueError("Only http(s) URLs are allowed")
    browser_cfg = config.get("browser", {})
    extractor_cfg = config.get("extractor", {})
    # Capture into a temporary URL slug first, then metadata determines final folder name.
    provisional = output / "_working" / slugify(url)
    raw_dir = provisional / "raw"
    html = capture_page(url, raw_dir, headless=browser_cfg.get("headless", True),
                        user_data_dir=browser_cfg.get("user_data_dir"), timeout_ms=browser_cfg.get("timeout_ms", 30000),
                        navigation_timeout_ms=browser_cfg.get("navigation_timeout_ms", 60000),
                        wait_for_mathjax=browser_cfg.get("wait_for_mathjax", True) if wait_for_mathjax is None else wait_for_mathjax,
                        save_screenshot=browser_cfg.get("screenshot", True) if save_screenshot is None else save_screenshot,
                        scroll_pause_ms=browser_cfg.get("scroll_pause_ms", 250), max_scrolls=browser_cfg.get("max_scrolls", 80),
                        extra_wait_ms=browser_cfg.get("extra_wait_ms", 1000),
                        channel=browser_cfg.get("channel"), executable_path=browser_cfg.get("executable_path"),
                        expand_references=browser_cfg.get("expand_references", True),
                        asset_dir=provisional / "markdown" / "assets",
                        auto_scroll=browser_cfg.get("auto_scroll", True),
                        load_all_images_via_cdp=browser_cfg.get("load_all_images_via_cdp", False))
    extractor = PaperExtractor(extractor_cfg.get("content_selectors"), extractor_cfg.get("remove_selectors"))
    result = extractor.extract(html, url)
    final_dir = output / slugify(url, result.metadata.title)
    final_dir.mkdir(parents=True, exist_ok=True)
    if final_dir != provisional:
        import shutil
        if final_dir.exists(): shutil.rmtree(final_dir)
        provisional.rename(final_dir)
    (final_dir / "metadata.json").write_text(json.dumps(result.metadata.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (final_dir / "formulas").mkdir(exist_ok=True)
    (final_dir / "formulas" / "formulas.json").write_text(formulas_json(result.formulas), encoding="utf-8")
    assets = {}
    asset_map_path = final_dir / "raw" / "asset-map.json"
    if asset_map_path.exists():
        try:
            assets.update(json.loads(asset_map_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            LOGGER.warning("Could not read browser asset manifest")
    assets.update(download_assets(html, url, final_dir / "markdown" / "assets"))
    assets = convert_gif_assets(final_dir / "markdown" / "assets", assets)
    if formats in {"all", "markdown"}:
        write_markdown(final_dir / "markdown" / "paper.md", result.body, result.metadata, assets)
    if formats in {"all", "latex"}:
        write_latex(final_dir / "latex", result.body, result.metadata, assets)
    validation = validate_archive(final_dir)
    manual_review = [f.order for f in result.formulas if f.conversion_status != "ok"]
    if manual_review:
        validation.setdefault("warnings", []).append({"formulas_needing_review": manual_review})
    cited = result.body.select("a[ref-type='bibr']")
    if cited and not result.metadata.references:
        validation.setdefault("warnings", []).append({
            "references": "IEEE page did not expose the reference list; placeholder BibTeX entries were generated for cited numbers"
        })
    (final_dir / "conversion_report.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"url": url, "output": str(final_dir), "valid": validation["valid"], "warnings": validation.get("warnings", [])}
