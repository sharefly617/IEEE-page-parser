import argparse
import json
import logging
import time
from pathlib import Path

import yaml

from src.archiver import archive_one


EXAMPLE_URL = "https://ieeexplore.ieee.org/document/10684554"


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archive authorized IEEE paper pages")
    parser.add_argument("--url", help=f"single authorized URL (example: {EXAMPLE_URL})")
    parser.add_argument("--urls-file", type=Path, help="file containing one authorized URL per line")
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--format", choices=["raw", "markdown", "latex", "all"], default="all")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--delay", type=float, default=None)
    parser.add_argument("--retries", type=int, default=None)
    parser.add_argument("--wait-for-mathjax", action="store_true")
    parser.add_argument("--save-screenshot", action="store_true")
    parser.add_argument("--offline-check", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.url and not args.urls_file:
        print("Provide --url or --urls-file")
        return 2
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(args.config)
    delay = args.delay if args.delay is not None else config.get("archive", {}).get("delay_seconds", 1.0)
    retries = args.retries if args.retries is not None else config.get("archive", {}).get("retries", 2)
    urls = [args.url] if args.url else list(dict.fromkeys(x.strip() for x in args.urls_file.read_text(encoding="utf-8").splitlines() if x.strip() and not x.strip().startswith("#")))
    results = []
    for index, url in enumerate(urls):
        result = None
        for attempt in range(retries + 1):
            try:
                result = archive_one(url, args.output, config, args.format,
                                     wait_for_mathjax=True if args.wait_for_mathjax else None,
                                     save_screenshot=True if args.save_screenshot else None)
                if args.offline_check:
                    result["offline_check"] = "passed" if result.get("valid") else "failed"
                break
            except Exception as exc:
                logging.error("Failed %s (attempt %s/%s): %s", url, attempt + 1, retries + 1, exc)
                if attempt < retries: time.sleep(delay)
        results.append(result or {"url": url, "status": "failed"})
        if index + 1 < len(urls): time.sleep(delay)
    if args.urls_file:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results[0] if len(results) == 1 else results, ensure_ascii=False, indent=2))
    return 0 if all(x.get("status") != "failed" for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
