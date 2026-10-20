#!/usr/bin/env python3
"""Assemble the web catalog ``dist/data.json`` and the full ``dist/sources.csv``.

Inputs are the manifests written by ``pipeline/papers/catalog.py`` and
``pipeline/icons/build.py``.  ``data.json`` is compact: paper figures are full
records, icons are rows of a table whose columns are listed in ``icons.fields``.
``sources.csv`` lists every asset with its files, source, license and SHA-256.
"""
from __future__ import annotations

import csv
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DIST, MANIFESTS, read_json, write_json  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent / "icons"))
import taxonomy as tx  # noqa: E402

PACK_ORDER = ["phosphor", "tabler", "iconpark", "fluent-emoji", "bioicons", "healthicons", "carbon-pictograms",
              "carbon", "mdi", "fluent-system"]
PAPER_CATEGORIES = [
    "卷积网络", "轻量化网络", "注意力模块", "视觉 Transformer", "目标检测", "图像分割", "序列与语言模型",
    "大语言模型", "多模态", "生成模型", "扩散模型", "自监督学习", "图神经网络", "时空预测", "气象大模型",
    "时间序列", "频域与小波", "三维视觉", "光流与运动", "超分辨率与复原", "基础组件",
]
ICON_FIELDS = ["id", "pack", "file", "zh", "en", "cat", "tags", "flags", "author", "license"]
FEATURED, MONO = 1, 2


def search_tags(tags, limit=90):
    text = ""
    for tag in tags:
        tag = " ".join(str(tag).split())
        if not tag or len(text) + len(tag) + 1 > limit:
            continue
        text = f"{text} {tag}".strip()
    return text


def main():
    papers = read_json(MANIFESTS / "papers.json")
    elements = read_json(MANIFESTS / "elements.json")
    ATOMIC_CATEGORIES = elements["categories"]
    papers["sources"] = {**elements["sources"], **papers["sources"]}
    papers["assets"] = papers["assets"] + elements["assets"]
    packs, rows, csv_rows = {}, [], []
    for key in PACK_ORDER:
        manifest = read_json(MANIFESTS / f"icons-{key}.json")
        info = manifest["pack"]
        packs[key] = {k: info[k] for k in ("name", "style", "version", "license", "license_file", "homepage",
                                           "recolor", "path", "count", "featured")}
        for a in manifest["assets"]:
            mono = info["recolor"] and a.get("recolor", True)
            flags = (FEATURED if a["featured"] else 0) | (MONO if mono else 0)
            rows.append([a["id"], key, a["file"], a["zh"], a["en"], tx.CATEGORIES.index(a["cat"]),
                         search_tags(a["tags"]), flags, a.get("author", ""), a.get("license", "")])
            csv_rows.append({
                "id": a["id"], "type": "icon", "name": a["zh"], "english": a["en"], "collection": info["name"],
                "category": a["cat"], "featured": int(a["featured"]), "files": f"{info['path']}{a['file']}",
                "source_title": f"{info['name']} ({info['version']})", "source_url": info["homepage"],
                "authors": a.get("author", ""), "license": a.get("license") or info["license"],
                "license_url": info["license_file"], "sha256": a["sha256"],
            })
    paper_rows = []
    for p in papers["assets"]:
        source = papers["sources"][p["source"]]
        record = {k: p.get(k, "") for k in ("id", "kind", "name", "category", "tags", "description", "figure", "caption",
                                    "source", "year", "page", "files", "width", "height", "svg_kind",
                                    "architecture", "has_alpha")}
        if p.get("original"):
            record.update(original=True, english=p["english"])
        paper_rows.append(record)
        csv_rows.append({
            "id": p["id"], "type": p["kind"], "name": p["name"], "english": p.get("english") or (f"{source['short']} · {p['figure']}" if p.get('figure') else source['short']),
            "collection": "论文原图" if p["kind"] == "paper" else "研图原创图元", "category": p["category"],
            "featured": 1, "files": " ".join(v for k, v in p["files"].items() if k != "thumb"),
            "source_title": f"{source['title']} ({source['venue']})" + (f", p. {p['page']}" if p.get("page") else ""),
            "source_url": source["url"],
            "authors": "; ".join(source["authors"]), "license": source["license_name"],
            "license_url": source["license_url"],
            "sha256": " ".join(f"{k}:{v}" for k, v in p["hashes"].items()),
        })
    order = {c: i for i, c in enumerate(PAPER_CATEGORIES + ATOMIC_CATEGORIES)}
    position = {a["id"]: a.get("order", 0) for a in papers["assets"]}
    paper_rows.sort(key=lambda r: (r["kind"] != "paper", order.get(r["category"], 99), r["year"] or 0,
                                   position.get(r["id"], 0), r["id"]))
    icon_count = len(rows)
    counts = {
        "papers": sum(r["kind"] == "paper" for r in paper_rows),
        "atomic": sum(r["kind"] == "atomic" for r in paper_rows),
        "icons": icon_count,
        "sources": len(papers["sources"]),
        "packs": len(packs),
        "featured_icons": sum(r[7] & FEATURED for r in rows) // FEATURED,
        "total": len(paper_rows) + icon_count,
    }
    catalog = {
        "version": 3,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "counts": counts,
        "categories": {"icon": tx.CATEGORIES, "paper": PAPER_CATEGORIES, "atomic": ATOMIC_CATEGORIES},
        "packs": packs,
        "sources": papers["sources"],
        "papers": paper_rows,
        "icons": {"fields": ICON_FIELDS, "rows": rows},
    }
    write_json(DIST / "data.json", catalog, compact=True)
    fields = ["id", "type", "name", "english", "collection", "category", "featured", "files", "source_title",
              "source_url", "authors", "license", "license_url", "sha256"]
    with (DIST / "sources.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(csv_rows)
    size = (DIST / "data.json").stat().st_size
    print({**counts, "data_json_bytes": size})


if __name__ == "__main__":
    main()
