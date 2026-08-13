"""
Dropbox public shared-link downloader (NO OAuth required).

Strategy (per Dropbox API v2 mechanics for scl/fo|scl/fi links):
- Preserve rlkey and force dl=1 -> Dropbox serves folder as ZIP (or file directly)
- Stream to disk, sniff magic bytes (PK.. = zip, %PDF = single pdf)
- Safe-extract ONLY .pdf members (path traversal protected)
"""
import os
import zipfile
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

MAX_DOWNLOAD_BYTES = int(os.environ.get("MAX_DOWNLOAD_MB", "1024")) * 1024 * 1024


class DropboxLinkError(Exception):
    pass


def dropbox_download_url(raw: str) -> str:
    """Validate host, preserve rlkey and replace/add dl=1."""
    p = urlsplit(raw.strip())
    host = (p.hostname or "").lower()
    if host not in {"dropbox.com", "www.dropbox.com"} and not host.endswith(".dropbox.com"):
        raise DropboxLinkError("Only Dropbox shared links are accepted")
    q = dict(parse_qsl(p.query, keep_blank_values=True))
    q["dl"] = "1"
    return urlunsplit(("https", p.netloc, p.path, urlencode(q), ""))


def _safe_pdf_target(name: str, root: Path):
    candidate = (root / name).resolve()
    if root.resolve() not in candidate.parents and candidate != root.resolve():
        return None
    if not name.lower().endswith(".pdf"):
        return None
    return candidate


def download_shared_link(shared_url: str, dest_dir: str, progress_cb=None) -> list:
    """
    Download a public Dropbox shared link into dest_dir/pdfs/.
    Returns list of {name, path, bytes} for every extracted PDF.
    progress_cb(downloaded_bytes) is called periodically during download.
    """
    root = Path(dest_dir)
    pdf_root = root / "pdfs"
    pdf_root.mkdir(parents=True, exist_ok=True)
    archive = root / "payload.bin"
    url = dropbox_download_url(shared_url)

    downloaded = 0
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(60.0, read=900.0)) as client:
        with client.stream("GET", url, headers={"User-Agent": "homeart-datahub/1.0"}) as r:
            if r.status_code in (403, 404, 410):
                raise DropboxLinkError(f"Dropbox link unavailable (HTTP {r.status_code}). Check that the link is public.")
            r.raise_for_status()
            ctype = r.headers.get("content-type", "")
            if "text/html" in ctype:
                raise DropboxLinkError("Dropbox returned an HTML page instead of a file. The link may be password-protected or downloads are disabled.")
            with archive.open("wb") as out:
                for chunk in r.iter_bytes(1024 * 1024):
                    out.write(chunk)
                    downloaded += len(chunk)
                    if downloaded > MAX_DOWNLOAD_BYTES:
                        raise DropboxLinkError(f"Download exceeds limit of {MAX_DOWNLOAD_BYTES // (1024*1024)} MB")
                    if progress_cb and downloaded % (5 * 1024 * 1024) < 1024 * 1024:
                        progress_cb(downloaded)
    if progress_cb:
        progress_cb(downloaded)

    with archive.open("rb") as f:
        magic = f.read(4)

    results = []
    if magic.startswith(b"%PDF"):
        # single-file shared link
        fname = os.path.basename(urlsplit(shared_url).path) or "document.pdf"
        if not fname.lower().endswith(".pdf"):
            fname += ".pdf"
        target = pdf_root / fname
        archive.replace(target)
        results.append({"name": fname, "path": str(target), "bytes": target.stat().st_size})
        return results

    if not magic.startswith(b"PK"):
        raise DropboxLinkError("Unexpected payload from Dropbox (neither ZIP nor PDF)")

    try:
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                target = _safe_pdf_target(info.filename, pdf_root)
                if target is None:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, target.open("wb") as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
                results.append({
                    "name": info.filename,
                    "path": str(target),
                    "bytes": info.file_size,
                })
    except zipfile.BadZipFile:
        raise DropboxLinkError("Corrupted ZIP received from Dropbox")
    finally:
        archive.unlink(missing_ok=True)

    if not results:
        raise DropboxLinkError("No PDF files found in the shared folder")
    return results
