"""Downloads filing PDFs (validated: the NSE archive sometimes serves a truncated file, see docs/spikes.md),
caches them on disk, and gives page text (for finding pages) and page images (for reading numbers)."""
import hashlib
import io
import json
import zipfile
from pathlib import Path

import httpx
import pymupdf
from pydantic import BaseModel

from finn.snapshot import REPO_ROOT

DEFAULT_CACHE = REPO_ROOT / "backend" / ".cache" / "docs"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")


class DocumentError(Exception):
    pass


class DocText(BaseModel):
    url: str
    pages: list[str]

    @property
    def readable(self) -> bool:
        return sum(len(p.strip()) for p in self.pages) >= 200


def _valid_pdf(data: bytes) -> bool:
    try:
        return data[:4] == b"%PDF" and pymupdf.open(stream=data, filetype="pdf").page_count > 0
    except Exception:
        return False


def pdf_from_zip(data: bytes) -> bytes | None:
    """The largest valid PDF inside a ZIP attachment (some companies file e.g. ..._KMP_Doc.zip), else None."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = sorted((i for i in z.infolist() if i.filename.lower().endswith(".pdf")),
                           key=lambda i: i.file_size, reverse=True)
            for info in names:
                pdf = z.read(info)
                if _valid_pdf(pdf):
                    return pdf
    except zipfile.BadZipFile:
        return None
    return None


def fetch_pdf(url: str, cache_dir: Path = DEFAULT_CACHE, fallback_urls: tuple[str, ...] = ()) -> Path:
    """Local path of a valid PDF for `url`, trying `fallback_urls` (e.g. screener's Raw PDF link) if it is broken."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{hashlib.sha1(url.encode()).hexdigest()}.pdf"
    if path.exists():
        return path
    errors = []
    for candidate in (url, *fallback_urls):
        try:
            r = httpx.get(candidate, timeout=120, follow_redirects=True,
                          headers={"User-Agent": UA, "Referer": "https://www.nseindia.com/"})
            content = pdf_from_zip(r.content) if r.content[:2] == b"PK" else r.content
            if r.status_code == 200 and content and _valid_pdf(content):
                path.write_bytes(content)
                return path
            errors.append(f"{candidate}: HTTP {r.status_code}, {len(r.content)} bytes, not a valid PDF")
        except httpx.HTTPError as e:
            errors.append(f"{candidate}: {type(e).__name__}")
    raise DocumentError("; ".join(errors))


def pdf_text(path: Path) -> list[str]:
    with pymupdf.open(path) as doc:
        return [page.get_text() for page in doc]


def fetch_pdf_text(url: str, cache_dir: Path = DEFAULT_CACHE, fallback_urls: tuple[str, ...] = ()) -> DocText:
    path = fetch_pdf(url, cache_dir, fallback_urls)
    text_cache = path.with_suffix(".json")
    if text_cache.exists():
        return DocText(url=url, pages=json.loads(text_cache.read_text()))
    pages = pdf_text(path)
    text_cache.write_text(json.dumps(pages))
    return DocText(url=url, pages=pages)


def render_page_png(path: Path, page: int, dpi: int | None = None) -> bytes:
    """PNG of one page; by default scaled to fit 1664×2048, the vision model's recommended size."""
    with pymupdf.open(path) as doc:
        p = doc[page]
        zoom = dpi / 72 if dpi else min(1664 / p.rect.width, 2048 / p.rect.height)
        return p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png")
