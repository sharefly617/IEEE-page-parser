import hashlib
import ipaddress
import json
import mimetypes
import re
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
    for node in soup.select("img[src], img[data-src], source[srcset], figure a[href], .figure a[data-fig-id][href], link[rel~='stylesheet']"):
        for attr in ("src", "data-src", "href"):
            raw = node.get(attr)
            if raw:
                absolute = urljoin(page_url, raw)
                if urlparse(absolute).scheme in {"http", "https"} and _safe_remote_host(urlparse(absolute).hostname or ""):
                    urls.add(absolute)
                    aliases[raw] = absolute
        if node.get("srcset"):
            for part in node["srcset"].split(","):
                raw = part.strip().split(" ")[0]
                absolute = urljoin(page_url, raw)
                urls.add(absolute)
                aliases[raw] = absolute
    result: Dict[str, str] = {}
    request_context = page.context.request
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
    for raw, absolute in aliases.items():
        if absolute in result:
            result[raw] = result[absolute]
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
