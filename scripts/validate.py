#!/usr/bin/env python3
"""Validate dist/: catalog structure, referenced files, SVG safety and source records.

Standard library only, so it also runs in the GitHub Pages workflow.
Pass ``--hashes`` to verify every SHA-256 listed in sources.csv (slower).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "dist"
MAX_BYTES = 50 * 1024 * 1024
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def fail(message):
    raise SystemExit(f"validation failed: {message}")


def check_path(directory: Path, value: str) -> Path:
    if not value or not value.isascii() or "\\" in value or value.startswith("/") or ".." in value.split("/"):
        fail(f"bad path {value!r}")
    path = (directory / value).resolve()
    if not path.is_relative_to(directory) or not path.is_file():
        fail(f"missing file {value}")
    if path.stat().st_size > MAX_BYTES:
        fail(f"file larger than 50 MB: {value}")
    return path


def check_svg(path: Path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        fail(f"invalid SVG {path.name}: {error}")
    if not root.tag.endswith("svg"):
        fail(f"not an SVG root: {path}")
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in ("script", "foreignObject"):
            fail(f"{tag} element in {path}")
        for key, value in element.attrib.items():
            name = key.rsplit("}", 1)[-1].lower()
            if name.startswith("on"):
                fail(f"event handler in {path}")
            if name == "href" and re.match(r"^\s*(https?:|file:|//|javascript:)", value, re.I):
                fail(f"external reference in {path}")


def validate(directory: Path, hashes: bool = False):
    directory = directory.resolve()
    data = json.loads((directory / "data.json").read_text(encoding="utf-8"))
    if data.get("version") != 3:
        fail("data.json must be catalog version 3")
    counts = data["counts"]
    papers, icons = data["papers"], data["icons"]
    fields = icons["fields"]
    col = {k: i for i, k in enumerate(fields)}
    ids = [p["id"] for p in papers] + [r[col["id"]] for r in icons["rows"]]
    duplicates = [i for i, n in Counter(ids).items() if n > 1]
    if duplicates:
        fail(f"duplicate ids {duplicates[:5]}")
    kinds = Counter(p["kind"] for p in papers)
    if kinds["paper"] != counts["papers"] or kinds["atomic"] != counts["atomic"]:
        fail("paper counts do not match")
    if len(icons["rows"]) != counts["icons"] or counts["total"] != len(ids):
        fail("icon counts do not match")
    files = set()
    for p in papers:
        if p["source"] not in data["sources"]:
            fail(f"{p['id']}: unknown source {p['source']}")
        if p["category"] not in data["categories"]["paper"] + data["categories"]["atomic"]:
            fail(f"{p['id']}: unknown category {p['category']}")
        if not ("png" in p["files"] or "jpg" in p["files"]) or "thumb" not in p["files"]:
            fail(f"{p['id']}: a PNG or JPEG and a thumbnail are required")
        for value in p["files"].values():
            files.add(check_path(directory, value))
    for key, source in data["sources"].items():
        for field in ("title", "authors", "url", "license", "license_name"):
            if not source.get(field):
                fail(f"source {key} lacks {field}")
        if not source["url"].startswith("https://"):
            fail(f"source {key} url must be https")
    for key, pack in data["packs"].items():
        check_path(directory, pack["license_file"])
    n_cat = len(data["categories"]["icon"])
    for row in icons["rows"]:
        pack = data["packs"].get(row[col["pack"]])
        if not pack:
            fail(f"{row[0]}: unknown pack")
        if not 0 <= row[col["cat"]] < n_cat:
            fail(f"{row[0]}: bad category index")
        if row[col["pack"]] == "bioicons" and not (row[col["author"]] and row[col["license"]]):
            fail(f"{row[0]}: Bioicons need author and license")
        files.add(check_path(directory, pack["path"] + row[col["file"]]))
    svgs = [p for p in files if p.suffix == ".svg"]
    for path in svgs:
        check_svg(path)
    with (directory / "sources.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len(ids) or {r["id"] for r in rows} != set(ids):
        fail("sources.csv does not list every asset")
    if hashes:
        for row in rows:
            entries = row["sha256"].split()
            targets = row["files"].split()
            if row["type"] == "icon":
                pairs = [(targets[0], entries[0])]
            else:
                by_ext = dict(e.split(":", 1) for e in entries)
                pairs = [(t, by_ext[t.rsplit(".", 1)[1]]) for t in targets]
            for target, expected in pairs:
                if hashlib.sha256((directory / target).read_bytes()).hexdigest() != expected:
                    fail(f"hash mismatch {target}")
    summary = {"status": "passed", "papers": counts["papers"], "atomic": counts["atomic"], "icons": counts["icons"],
               "sources": len(data["sources"]), "packs": len(data["packs"]), "files_checked": len(files),
               "svg_checked": len(svgs), "hashes_checked": hashes}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default=str(ROOT))
    parser.add_argument("--hashes", action="store_true", help="verify SHA-256 of every file")
    args = parser.parse_args()
    validate(Path(args.directory), args.hashes)
