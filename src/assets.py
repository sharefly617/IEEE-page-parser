import hashlib
import ipaddress
import json
import mimetypes
import re
import base64
from pathlib import Path
from typing import Dict, Iterable, Optional
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


def _safe_remote_host(host: str) -> bool:
    if not host or host.lower() in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved)


def safe_filename(url: str, fallback: str = "asset") -> str:
    path = Path(urlparse(url).path).name or fallback
    path = re.sub(r"[^A-Za-z0-9._-]+", "_", path)[:120]
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    stem = Path(path).stem or fallback
    suffix = Path(path).suffix
    return f"{stem}-{digest}{suffix}"


def download_assets(html: str, page_url: str, assets_dir: Path, *, timeout: int = 20) -> Dict[str, str]:
    """Download referenced images/CSS/fonts best-effort and return URL -> relative path."""
    from bs4 import BeautifulSoup
    assets_dir.mkdir(parents=True, exist_ok=True)
    soup = BeautifulSoup(html, "lxml")
    urls = set()
    aliases: Dict[str, str] = {}
    for node in soup.select("img[src], img[data-src], source[srcset], link[rel~='stylesheet'], figure a[href], .figure a[data-fig-id][href], [style]"):
        for attr in ("src", "data-src", "href"):
            if node.get(attr):
                raw_url = node[attr]
                absolute_url = urljoin(page_url, raw_url)
                urls.add(absolute_url)
                aliases[raw_url] = absolute_url
        if node.get("srcset"):
            urls.update(urljoin(page_url, x.strip().split(" ")[0]) for x in node["srcset"].split(","))
        style = node.get("style", "")
        urls.update(urljoin(page_url, x) for x in re.findall(r"url\([\"']?([^)'\"]+)", style))
    result: Dict[str, str] = {}
    for asset_url in urls:
        parsed = urlparse(asset_url)
        if parsed.scheme not in {"http", "https"} or not _safe_remote_host(parsed.hostname or ""):
            continue
        filename = safe_filename(asset_url)
        destination = assets_dir / filename
        try:
            request = Request(asset_url, headers={"User-Agent": "authorized-paper-archiver/1.0"})
            with urlopen(request, timeout=timeout) as response:
                destination.write_bytes(response.read())
            result[asset_url] = str(Path("assets") / filename).replace("\\", "/")
        except Exception:
            continue
    for raw_url, absolute_url in aliases.items():
        if absolute_url in result:
            result[raw_url] = result[absolute_url]
    return result


def download_assets_from_browser(page: object, html: str, page_url: str, assets_dir: Path) -> Dict[str, str]:
    """Download page assets through the authenticated Playwright context.

    IEEE media endpoints may reject a plain urllib request even after the image
    has rendered in the user's authorized browser session.
    """
    from bs4 import BeautifulSoup
    assets_dir.mkdir(parents=True, exist_ok=True)
    soup = BeautifulSoup(html, "lxml")
    urls = set()
    aliases: Dict[str, str] = {}
    image_urls = set()
    for node in soup.select("img[src], img[data-src], img[data-lazy-src], img[data-original], img[data-url], source[srcset], figure a[href], .figure a[data-fig-id][href], link[rel~='stylesheet'], [style*='background-image']"):
        for attr in ("src", "data-src", "data-lazy-src", "data-original", "data-url", "href"):
            raw = node.get(attr)
            if raw:
                absolute = urljoin(page_url, raw)
                if urlparse(absolute).scheme in {"http", "https"} and _safe_remote_host(urlparse(absolute).hostname or ""):
                    urls.add(absolute)
                    aliases[raw] = absolute
                    if node.name == "img" or node.find("img") is not None:
                        image_urls.add(absolute)
        if node.get("srcset"):
            for part in node["srcset"].split(","):
                raw = part.strip().split(" ")[0]
                absolute = urljoin(page_url, raw)
                urls.add(absolute)
                aliases[raw] = absolute
                image_urls.add(absolute)
        style = node.get("style", "")
        for raw in re.findall(r"url\([\"']?([^)'\"]+)", style):
            absolute = urljoin(page_url, raw)
            if urlparse(absolute).scheme in {"http", "https"} and _safe_remote_host(urlparse(absolute).hostname or ""):
                urls.add(absolute)
                aliases[raw] = absolute
    result: Dict[str, str] = {}
    request_context = page.context.request
    direct_result = download_image_urls_from_html(html, page_url, request_context, assets_dir)
    result.update(direct_result)
    # Download image URLs explicitly from the final HTML first. This is the
    # primary path for manually authenticated IEEE pages; the browser context
    # supplies the same cookies and headers as the visible page.
    ordered_urls = list(image_urls) + [item for item in urls if item not in image_urls]
    for asset_url in ordered_urls:
        if asset_url in result:
            continue
        try:
            response = request_context.get(asset_url, headers={"Referer": page_url})
            if not response.ok:
                raise RuntimeError(f"asset response status {response.status}")
            filename = safe_filename(asset_url)
            (assets_dir / filename).write_bytes(response.body())
            result[asset_url] = str(Path("assets") / filename).replace("\\", "/")
        except Exception:
            # A page fetch uses the authenticated document session and can
            # succeed when APIRequestContext is rejected by an image CDN.
            try:
                payload = page.evaluate("""async (url) => {
                  const response = await fetch(url, {credentials: 'include'});
                  if (!response.ok) return null;
                  const bytes = new Uint8Array(await response.arrayBuffer());
                  let binary = '';
                  const chunk = 0x8000;
                  for (let i = 0; i < bytes.length; i += chunk)
                    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
                  return btoa(binary);
                }""", asset_url)
                if payload:
                    filename = safe_filename(asset_url)
                    (assets_dir / filename).write_bytes(base64.b64decode(payload))
                    result[asset_url] = str(Path("assets") / filename).replace("\\", "/")
            except Exception:
                continue
    for raw, absolute in aliases.items():
        if absolute in result:
            result[raw] = result[absolute]
    # IEEE sometimes keeps the figure URL in a lazy/zoom anchor while the
    # visible image is only available as a browser-rendered resource. Capture
    # the rendered figure as a PNG when the authenticated request failed.
    try:
        figure_locator = page.locator("figure img, .figure img, img.document-ft-image")
        for index in range(figure_locator.count()):
            image = figure_locator.nth(index)
            raw_src = image.get_attribute("src") or image.get_attribute("data-src")
            parent_link = image.locator("xpath=ancestor::a[1]")
            raw_href = parent_link.get_attribute("href")
            if not raw_src and not raw_href:
                continue
            source_key = urljoin(page_url, raw_href or raw_src or "")
            if source_key in result:
                continue
            filename = safe_filename(source_key or f"figure-{index}")
            filename = str(Path(filename).with_suffix(".png"))
            target = assets_dir / filename
            image.scroll_into_view_if_needed()
            image.screenshot(path=str(target), type="png")
            relative = str(Path("assets") / filename).replace("\\", "/")
            for raw in (raw_src, raw_href):
                if raw:
                    absolute = urljoin(page_url, raw)
                    result[absolute] = relative
                    result[raw] = relative
    except Exception:
        # A missing/hidden figure should not abort the rest of the archive.
        pass
    return result


def download_image_urls_from_html(html: str, page_url: str, request_context: object, assets_dir: Path) -> Dict[str, str]:
    """Download only image/figure URLs found in final rendered HTML."""
    from bs4 import BeautifulSoup
    assets_dir.mkdir(parents=True, exist_ok=True)
    soup = BeautifulSoup(html, "lxml")
    urls = set()
    for image in soup.select("img, source[srcset], figure a[href], .figure a[href]"):
        for attr in ("src", "data-src", "data-lazy-src", "data-original", "data-url", "href"):
            raw = image.get(attr)
            if raw:
                absolute = urljoin(page_url, raw)
                if urlparse(absolute).scheme in {"http", "https"} and _safe_remote_host(urlparse(absolute).hostname or ""):
                    urls.add(absolute)
        for part in (image.get("srcset") or "").split(","):
            raw = part.strip().split(" ")[0]
            if raw:
                absolute = urljoin(page_url, raw)
                if urlparse(absolute).scheme in {"http", "https"} and _safe_remote_host(urlparse(absolute).hostname or ""):
                    urls.add(absolute)
    result = {}
    for asset_url in urls:
        try:
            response = request_context.get(asset_url, headers={"Referer": page_url})
            if not response.ok:
                continue
            filename = safe_filename(asset_url)
            (assets_dir / filename).write_bytes(response.body())
            result[asset_url] = str(Path("assets") / filename).replace("\\", "/")
        except Exception:
            continue
    return result


def convert_gif_assets(assets_dir: Path, mapping: Dict[str, str]) -> Dict[str, str]:
    """Convert downloaded GIFs to PNG so LaTeX never references GIF files."""
    try:
        from PIL import Image
    except ImportError:
        return mapping
    converted: Dict[str, str] = {}
    for source_url, relative in list(mapping.items()):
        if Path(relative).suffix.lower() != ".gif":
            continue
        source = assets_dir / Path(relative).name
        target = source.with_suffix(".png")
        try:
            if not target.exists():
                with Image.open(source) as image:
                    image.seek(0)
                    frame = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                    frame.save(target, format="PNG")
            converted[source_url] = str(Path(relative).with_suffix(".png")).replace("\\", "/")
        except Exception:
            continue
    mapping.update(converted)
    return mapping
