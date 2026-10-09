#!/usr/bin/env python3
"""Merge new and legacy paper figures into ``pipeline/manifests/papers.json``.

Each record carries the files under ``dist/assets/papers``, a WebP thumbnail, the
original caption (read from the cached PDF when available) and a reference to a
source entry with title, authors, venue, link and the license chosen by the authors.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pymupdf
from PIL import Image

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from common import ASSETS, CACHE, MANIFESTS, read_json, sha256, write_json  # noqa: E402
import extract  # noqa: E402  (same directory)

HERE = Path(__file__).resolve().parent
OUT = ASSETS / "papers"
THUMBS = OUT / "thumbs"

LICENSES = {
    "http://arxiv.org/licenses/nonexclusive-distrib/1.0/": ("arXiv", "arXiv 非独占分发许可",
                                                           "https://arxiv.org/licenses/nonexclusive-distrib/1.0/license.html"),
    "http://creativecommons.org/licenses/by/4.0/": ("CC-BY-4.0", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    "http://creativecommons.org/licenses/by-sa/4.0/": ("CC-BY-SA-4.0", "CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/"),
    "http://creativecommons.org/licenses/by-nc-sa/4.0/": ("CC-BY-NC-SA-4.0", "CC BY-NC-SA 4.0", "https://creativecommons.org/licenses/by-nc-sa/4.0/"),
    "http://creativecommons.org/licenses/by-nc-nd/4.0/": ("CC-BY-NC-ND-4.0", "CC BY-NC-ND 4.0", "https://creativecommons.org/licenses/by-nc-nd/4.0/"),
    "http://creativecommons.org/publicdomain/zero/1.0/": ("CC0-1.0", "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
}
DIFFUSION = {"ddim", "scoresde", "ldm", "controlnet", "dit", "dalle2", "consistency", "ddpm"}
ARCH_WORDS = ("架构", "整体", "框架", "网络", "概览", "结构", "流程", "示意")
PART_WORDS = ("模块", "单元", "构建块", "残差块", "块结构", "块设计", "层", "门", "掩码", "滤波器", "输入表示", "分布")


def year_of(source):
    match = re.search(r"(19|20)\d\d", source.get("venue", ""))
    return int(match.group(0)) if match else source.get("year")


def sources():
    papers = read_json(HERE / "papers.json")
    meta = read_json(HERE / "arxiv_metadata.json")
    result = {}
    for key, info in papers.items():
        m = meta[key]
        license_id, license_name, license_url = LICENSES[m["license"]]
        result[key] = {
            "short": info["short"], "title": m["title"], "authors": m["authors"], "venue": info["venue"],
            "arxiv": m["arxiv"], "version": m["version"], "url": f"https://arxiv.org/abs/{m['arxiv']}",
            "pdf": f"https://arxiv.org/pdf/{m['arxiv']}{m['version']}",
            "license": license_id, "license_name": license_name, "license_url": license_url,
        }
        result[key]["year"] = year_of(result[key]) or int(m["published"][:4])
    for key, info in read_json(HERE / "other_sources.json").items():
        result[key] = {**info, "arxiv": ""}
    return result


def caption_text(key, figure_label, page_hint=None):
    """Return the original caption block for ``figure_label`` ("Fig. 3", "Table 1")."""
    pdf = CACHE / "papers" / "pdf" / f"{key}.pdf"
    match = re.search(r"(fig(?:ure)?|table)\.?\s*(\d+(?:\.\d+)?)", figure_label or "", re.I)
    if not pdf.is_file() or not match:
        return ""
    fig = ("T" if match.group(1).lower().startswith("t") else "F") + match.group(2)
    try:
        doc = pymupdf.open(pdf)
        index, line, block = extract.find_caption(doc, fig)
    except Exception:
        return ""
    page = doc[index]
    text = page.get_text("text", clip=block)
    text = re.sub(r"-\n(?=[a-z])", "", text)
    text = " ".join(text.split())
    if len(text) > 420:
        cut = text[:420].rsplit(". ", 1)[0]
        text = (cut if len(cut) > 120 else text[:420]).rstrip(" .") + " …"
    return text


def thumbnail(png: Path, target: Path):
    if target.is_file() and target.stat().st_mtime >= png.stat().st_mtime:
        return
    image = Image.open(png)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")
    image.thumbnail((extract.THUMB_SIDE, extract.THUMB_SIDE), Image.Resampling.LANCZOS)
    image.save(target, quality=88, method=6)


def is_architecture(name):
    return any(w in name for w in ARCH_WORDS) and not any(w in name for w in PART_WORDS)


def record(base, files, src_key, src):
    entry = {
        "id": base["id"], "kind": base.get("kind", "paper"), "name": base["name"],
        "category": base["category"], "tags": base.get("tags", []), "description": base.get("description", ""),
        "figure": base.get("figure", ""), "caption": base.get("caption", ""), "source": src_key,
        "year": src.get("year") or base.get("year"), "page": base.get("page"),
        "files": {k: f"assets/papers/{v}" for k, v in files.items()},
        "width": base["width"], "height": base["height"], "svg_kind": base.get("svg_kind", ""),
        "has_alpha": base.get("has_alpha", False), "architecture": base.get("architecture", False),
        "provenance": base.get("provenance", {}),
    }
    entry["hashes"] = {k: sha256(OUT / v) for k, v in files.items() if k != "thumb"}
    entry["bytes"] = {k: (OUT / v).stat().st_size for k, v in files.items()}
    return entry


def main():
    src = sources()
    THUMBS.mkdir(parents=True, exist_ok=True)
    figures = read_json(HERE / "figures.json")
    extracted = read_json(HERE / "extracted.json")
    records = []
    for spec in figures:
        sid = f"p-{spec['paper']}-{spec['fig'].lower().replace('.', '-')}"
        out = extracted[sid]
        label = extract.label(spec["fig"])
        files = {k: f"{sid}.{k}" for k in ("png", "svg", "pdf") if k in out["hashes"]}
        files["thumb"] = f"thumbs/{sid}.webp"
        category = "扩散模型" if spec["paper"] in DIFFUSION else spec["cat"]
        base = {
            "id": sid, "kind": "paper", "name": spec["name"], "category": category,
            "tags": [src[spec["paper"]]["short"], *spec.get("tags", [])], "description": spec["desc"],
            "figure": label, "caption": caption_text(spec["paper"], label), "page": out["page"],
            "width": out["width"], "height": out["height"], "svg_kind": out["svg_kind"],
            "architecture": is_architecture(spec["name"]),
            "provenance": {"page": out["page"], "box": out["box"], "dpi": out["dpi"], "method": out["method"],
                           "source_file": src[spec["paper"]]["pdf"]},
        }
        records.append(record(base, files, spec["paper"], src[spec["paper"]]))
    for item in read_json(HERE / "legacy.json"):
        key = item["paper"] or item["other_source"]
        files = dict(item["files"])
        thumb = f"thumbs/{item['id']}.webp"
        thumbnail(OUT / files["png"], OUT / thumb)
        files["thumb"] = thumb
        page = (item.get("provenance") or {}).get("page")
        base = {**item, "page": page,
                "caption": caption_text(item["paper"], item["figure"]) if item["paper"] and item["kind"] == "paper" else ""}
        base["tags"] = list(dict.fromkeys([src[key]["short"], *item["tags"]]))
        records.append(record(base, files, key, src[key]))
    used = sorted({r["source"] for r in records})
    manifest = {"pack": "papers", "count": len(records),
                "sources": {k: src[k] for k in used}, "assets": records}
    write_json(MANIFESTS / "papers.json", manifest)
    referenced = {Path(v).name for r in records for v in r["files"].values()}
    stray = [p.name for p in OUT.iterdir() if p.is_file() and p.name not in referenced]
    for name in stray:
        (OUT / name).unlink()
    stray_thumbs = [p.name for p in THUMBS.iterdir() if f"thumbs/{p.name}" not in
                    {v.split("papers/", 1)[1] for r in records for v in r["files"].values()}]
    for name in stray_thumbs:
        (THUMBS / name).unlink()
    print({"records": len(records), "sources": len(used), "removed_files": len(stray) + len(stray_thumbs),
           "architecture": sum(r["architecture"] for r in records),
           "captions": sum(bool(r["caption"]) for r in records)})


if __name__ == "__main__":
    main()
