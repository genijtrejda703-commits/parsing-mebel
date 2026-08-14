"""Dropbox shared-folder traversal.

A Dropbox folder share link with `dl=1` streams the whole folder as one ZIP, so
we can traverse an arbitrarily nested share without OAuth. The ZIP is cached on
disk (keyed by link hash) so re-scans are instant, extracted PDFs are kept for
page rendering, and the archive is removed once extraction succeeds.
"""
import hashlib
import os
import re
import shutil
import subprocess
import time
import zipfile

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
TMP = os.path.join(DATA_DIR, "tmp")
PDF_DIR = os.path.join(DATA_DIR, "pdfs")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def _force_dl(url):
    url = url.strip()
    if "dl=" in url:
        return re.sub(r"dl=\d", "dl=1", url)
    return url + ("&" if "?" in url else "?") + "dl=1"


def zip_path_for(url):
    h = hashlib.sha1(url.encode()).hexdigest()[:12]
    return os.path.join(TMP, f"dropbox_{h}.zip")


def download_folder(url, log=lambda m: None):
    dest = zip_path_for(url)
    os.makedirs(TMP, exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) > 1024:
        log(f"using cached archive {os.path.basename(dest)} "
            f"({os.path.getsize(dest) / 1e6:.0f} MB)")
        return dest
    dl = _force_dl(url)
    log("requesting Dropbox folder archive (dl=1) via curl, following redirects ...")
    tmp = dest + ".part"
    if os.path.exists(tmp):
        os.remove(tmp)
    # curl follows Dropbox's 302 -> signed dl.dropboxusercontent.com URL reliably
    proc = subprocess.Popen(
        ["curl", "-sL", "--fail", "-A", UA, "--max-time", "1800", "-o", tmp, dl],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    last = 0
    while proc.poll() is None:
        time.sleep(5)
        if os.path.exists(tmp):
            mb = os.path.getsize(tmp) / 1e6
            if mb - last >= 100:
                log(f"downloaded {mb:.0f} MB ...")
                last = mb
    rc = proc.wait()
    err = (proc.stderr.read().decode(errors="ignore") if proc.stderr else "")[:200]
    if rc != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 1024:
        raise RuntimeError(f"curl download failed (rc={rc}) {err}")
    # sanity: must be a zip
    with open(tmp, "rb") as f:
        if f.read(2) != b"PK":
            raise RuntimeError("downloaded payload is not a ZIP (link/token may be expired)")
    os.replace(tmp, dest)
    log(f"archive ready: {os.path.getsize(dest) / 1e6:.0f} MB")
    return dest


def list_pdfs(zip_path):
    out = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".pdf"):
                continue
            name = os.path.basename(info.filename)
            out.append({
                "rel": info.filename,
                "name": name,
                "size": info.file_size,
                "folder": os.path.dirname(info.filename) or "/",
                "is_price_list": ("_PL_" in name) or ("прайс" in info.filename.lower()),
            })
    out.sort(key=lambda x: (not x["is_price_list"], -x["size"]))
    return out


def list_spreadsheets(zip_path):
    """Spreadsheet price files (xlsx/xls) — flagged, never geometrically parsed."""
    out = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if info.filename.lower().endswith((".xlsx", ".xls")):
                out.append({"rel": info.filename,
                            "name": os.path.basename(info.filename),
                            "size": info.file_size,
                            "folder": os.path.dirname(info.filename) or "/"})
    return out


def extract(zip_path, rels, log=lambda m: None):
    os.makedirs(PDF_DIR, exist_ok=True)
    found = []
    with zipfile.ZipFile(zip_path) as zf:
        for rel in rels:
            try:
                info = zf.getinfo(rel)
            except KeyError:
                log(f"missing in archive: {rel}")
                continue
            dest = os.path.join(PDF_DIR, os.path.basename(rel))
            if not os.path.exists(dest) or os.path.getsize(dest) != info.file_size:
                with zf.open(info) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
                log(f"extracted {os.path.basename(rel)} ({info.file_size / 1e6:.1f} MB)")
            found.append({"path": dest, "name": os.path.basename(rel), "rel": rel})
    return found


def cleanup_archive(zip_path, log=lambda m: None):
    try:
        if os.path.exists(zip_path):
            mb = os.path.getsize(zip_path) / 1e6
            os.remove(zip_path)
            log(f"cleaned up temporary archive ({mb:.0f} MB freed)")
    except Exception as e:
        log(f"cleanup skipped: {e}")
