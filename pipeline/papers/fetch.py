#!/usr/bin/env python3
"""Download the arXiv PDFs listed in papers.json and record their metadata.

* Atom API: title, authors, dates and the latest version of each paper.
* OAI-PMH: the license URL that the authors selected on arXiv.
* PDFs are pinned to that version and cached in ``.cache/papers/pdf/``.

The metadata is written to ``pipeline/papers/arxiv_metadata.json`` so that the
figure extraction step can run offline and the catalog can cite each source.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import CACHE, fetch, read_json, write_json  # noqa: E402

HERE = Path(__file__).resolve().parent
PAPERS = HERE / "papers.json"
METADATA = HERE / "arxiv_metadata.json"
PDF_DIR = CACHE / "papers" / "pdf"
ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
OAI = {"o": "http://www.openarchives.org/OAI/2.0/", "x": "http://arxiv.org/OAI/arXiv/"}


def text(node, path, ns):
    found = node.find(path, ns)
    return " ".join(found.text.split()) if found is not None and found.text else ""


def atom_metadata(ids):
    result = {}
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        query = urllib.parse.urlencode({"id_list": ",".join(chunk), "max_results": len(chunk)})
        root = ET.fromstring(fetch("https://export.arxiv.org/api/query?" + query))
        for entry in root.findall("a:entry", ATOM):
            versioned = entry.find("a:id", ATOM).text.rsplit("/abs/", 1)[-1]
            base = re.sub(r"v\d+$", "", versioned)
            result[base] = {
                "arxiv": base,
                "version": versioned[len(base):],
                "title": text(entry, "a:title", ATOM),
                "authors": [" ".join(a.find("a:name", ATOM).text.split()) for a in entry.findall("a:author", ATOM)],
                "published": text(entry, "a:published", ATOM)[:10],
                "updated": text(entry, "a:updated", ATOM)[:10],
                "primary_category": entry.find("arxiv:primary_category", ATOM).get("term"),
                "doi": text(entry, "arxiv:doi", ATOM),
                "journal_ref": text(entry, "arxiv:journal_ref", ATOM),
            }
        time.sleep(3.5)
    return result


def oai_license(arxiv_id):
    url = ("https://oaipmh.arxiv.org/oai?verb=GetRecord&metadataPrefix=arXiv&identifier=oai:arXiv.org:"
           + arxiv_id)
    root = ET.fromstring(fetch(url, delay=1.2))
    found = root.find(".//x:license", OAI)
    return found.text.strip() if found is not None and found.text else ""


def download_pdf(item):
    key, meta = item
    dest = PDF_DIR / f"{key}.pdf"
    url = f"https://arxiv.org/pdf/{meta['arxiv']}{meta['version']}"
    data = fetch(url, dest, delay=1.0)
    if not data.startswith(b"%PDF"):
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"Not a PDF: {url}")
    return key, len(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="paper keys to refresh")
    args = parser.parse_args()
    papers = read_json(PAPERS)
    metadata = read_json(METADATA, {})
    keys = args.only or [k for k in papers if k not in metadata]
    if keys:
        atom = atom_metadata([papers[k]["arxiv"] for k in keys])
        for key in keys:
            entry = dict(atom[papers[key]["arxiv"]])
            entry["license"] = oai_license(papers[key]["arxiv"])
            metadata[key] = entry
            print(key, entry["version"], entry["license"], flush=True)
        write_json(METADATA, dict(sorted(metadata.items())))
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        wanted = [(k, metadata[k]) for k in papers if papers[k].get("pdf", True)]
        for key, size in pool.map(download_pdf, wanted):
            print("pdf", key, size, flush=True)


if __name__ == "__main__":
    main()
