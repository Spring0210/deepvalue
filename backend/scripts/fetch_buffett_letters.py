"""Download Warren Buffett's Berkshire Hathaway shareholder letters and
extract them to plain text under backend/app/data/buffett_letters/.

Usage (from backend/):
    .venv/bin/python -m scripts.fetch_buffett_letters
    .venv/bin/python -m scripts.fetch_buffett_letters --years 2018-2024
    .venv/bin/python -m scripts.fetch_buffett_letters --force

The directory is .gitignored — the script must be run locally once after
checkout to populate the RAG corpus. The FAISS index auto-rebuilds on the
next backend start because rag.py signs source files by mtime + size.
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import httpx
from pypdf import PdfReader

# Letters live at https://www.berkshirehathaway.com/letters/{year}ltr.pdf
# for 2003-present. The most recent year is sometimes hosted at the site
# root (https://www.berkshirehathaway.com/{year}ltr.pdf), so the fetcher
# falls through to that on 404.
_BASE = "https://www.berkshirehathaway.com"
_URL_PATTERNS = ["{base}/letters/{year}ltr.pdf", "{base}/{year}ltr.pdf"]

_DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "buffett_letters"


def _parse_years(spec: str) -> list[int]:
    if "-" in spec:
        a, b = spec.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(y) for y in spec.split(",")]


def _download_pdf(year: int, client: httpx.Client) -> bytes | None:
    for pattern in _URL_PATTERNS:
        url = pattern.format(base=_BASE, year=year)
        try:
            resp = client.get(url, follow_redirects=True, timeout=30.0)
        except httpx.HTTPError as exc:
            print(f"  [{year}] network error on {url}: {exc}", file=sys.stderr)
            continue
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/pdf"):
            return resp.content
        if resp.status_code == 200 and resp.content[:4] == b"%PDF":
            return resp.content
    return None


def _pdf_to_text(blob: bytes) -> str:
    reader = PdfReader(io.BytesIO(blob))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:
            print(f"  page extract failed: {exc}", file=sys.stderr)
    return "\n\n".join(p.strip() for p in pages if p.strip())


def fetch_year(year: int, out_dir: Path, force: bool, client: httpx.Client) -> bool:
    out_path = out_dir / f"{year}.txt"
    if out_path.exists() and not force:
        print(f"  [{year}] already cached — skipping (use --force to redo)")
        return True
    print(f"  [{year}] downloading...")
    blob = _download_pdf(year, client)
    if blob is None:
        print(f"  [{year}] FAILED — no PDF found at expected URLs", file=sys.stderr)
        return False
    text = _pdf_to_text(blob)
    if len(text) < 1000:
        print(f"  [{year}] WARNING — extracted only {len(text)} chars, possibly scanned PDF", file=sys.stderr)
    out_path.write_text(text, encoding="utf-8")
    print(f"  [{year}] wrote {len(text):,} chars to {out_path.relative_to(Path.cwd()) if Path.cwd() in out_path.parents else out_path}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Buffett shareholder letters.")
    parser.add_argument(
        "--years", default="2015-2024",
        help="Year range like '2015-2024' or csv '2018,2020,2023'. Default: 2015-2024.",
    )
    parser.add_argument("--force", action="store_true", help="Re-download even if .txt already exists.")
    args = parser.parse_args()

    years = _parse_years(args.years)
    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Target directory: {_DATA_DIR}")
    print(f"Years requested:  {years}")

    ok = 0
    with httpx.Client(headers={"User-Agent": "DeepValue/0.5 (research; +https://github.com)"}) as client:
        for year in years:
            if fetch_year(year, _DATA_DIR, args.force, client):
                ok += 1

    print(f"\nDone: {ok}/{len(years)} letters fetched. Restart the backend to rebuild the FAISS index.")
    return 0 if ok == len(years) else 1


if __name__ == "__main__":
    sys.exit(main())
