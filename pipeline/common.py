"""Shared helpers for the asset pipeline (Python standard library only).

The pipeline downloads pinned upstream sources into ``.cache/`` (ignored by Git),
writes publishable files into ``dist/assets/`` and records every asset in a
manifest under ``pipeline/manifests/``.  ``pipeline/catalog.py`` merges the
manifests into the compact ``dist/data.json`` used by the web page.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DIST = PROJECT / "dist"
ASSETS = DIST / "assets"
CACHE = PROJECT / ".cache"
MANIFESTS = PROJECT / "pipeline" / "manifests"
USER_AGENT = "research-figure-library/2.0 (+https://github.com/RuntimeWarning/research-figure-library)"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def fetch(url: str, dest: Path | None = None, *, retries: int = 4, timeout: int = 120, delay: float = 0.0) -> bytes:
    """Download ``url`` (optionally caching it at ``dest``) with simple retries."""
    if dest is not None and dest.is_file() and dest.stat().st_size:
        return dest.read_bytes()
    last = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
            if dest is not None:
                dest.parent.mkdir(parents=True, exist_ok=True)
                temporary = dest.with_suffix(dest.suffix + ".part")
                temporary.write_bytes(data)
                temporary.replace(dest)
            if delay:
                time.sleep(delay)
            return data
        except Exception as error:  # network errors are retried, then re-raised
            last = error
            time.sleep(2 + attempt * 3)
    data = fetch_with_curl(url, timeout)  # some networks fail Python's TLS handshake but not curl's
    if data is not None:
        if dest is not None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        return data
    raise RuntimeError(f"Download failed: {url}: {last}")


def fetch_with_curl(url: str, timeout: int = 120) -> bytes | None:
    curl = shutil.which("curl")
    if not curl:
        return None
    for _ in range(4):
        result = subprocess.run([curl, "-sSL", "--retry", "3", "--retry-all-errors", "-m", str(timeout),
                                 "-A", USER_AGENT, "-f", url], capture_output=True)
        if result.returncode == 0 and result.stdout:
            return result.stdout
        time.sleep(2)
    return None


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(value, ensure_ascii=False, indent=1)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def slug(value: str) -> str:
    """ASCII file-name slug: lowercase words joined by hyphens."""
    value = re.sub(r"[^0-9A-Za-z]+", "-", value).strip("-").lower()
    return re.sub(r"-{2,}", "-", value) or "item"


def rel(path: Path) -> str:
    """Site-relative POSIX path for a file inside ``dist``."""
    return path.resolve().relative_to(DIST.resolve()).as_posix()


def load_manifest(name: str) -> dict:
    return read_json(MANIFESTS / f"{name}.json", {"pack": name, "assets": []})


def save_manifest(name: str, manifest: dict) -> None:
    manifest["assets"].sort(key=lambda a: a.get("order", 0))
    write_json(MANIFESTS / f"{name}.json", manifest)
