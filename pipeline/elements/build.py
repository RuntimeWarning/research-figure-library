#!/usr/bin/env python3
"""Build the curated figure elements (图元) listed in ``elements.json``.

Each entry points at a candidate found by ``candidates.py`` (paper, page, box).
Vector elements are redrawn from their original PDF paths — no text, no
neighbouring shapes — and exported as an editable SVG and a transparent PNG.
Bitmap elements are copied from the PDF at their native resolution.  Names are
generated from the element type, its dominant colour and, for grids, its size.

Output: ``dist/assets/elements/`` and ``pipeline/manifests/elements.json``.
"""
from __future__ import annotations

import colorsys
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from common import ASSETS, CACHE, MANIFESTS, read_json, sha256, write_json  # noqa: E402
import candidates as cand  # noqa: E402

HERE = Path(__file__).resolve().parent
PDF_DIR = CACHE / "papers" / "pdf"
OUT = ASSETS / "elements"
PNG_SIDE = 1200
THUMB_SIDE = 420

# type key -> (Chinese noun, category, English noun)
TYPES = {
    "cube": ("三维特征张量", "张量与特征图", "3D feature tensor"),
    "slab": ("扁平特征张量", "张量与特征图", "flat feature tensor"),
    "stack": ("多通道特征堆叠", "张量与特征图", "stacked feature maps"),
    "plane": ("特征平面", "张量与特征图", "feature plane"),
    "volume": ("三维体数据网格", "张量与特征图", "3D volume grid"),
    "matrix": ("矩阵网格", "矩阵与注意力图", "matrix grid"),
    "attn": ("注意力矩阵", "矩阵与注意力图", "attention matrix"),
    "mask": ("注意力掩码", "矩阵与注意力图", "attention mask"),
    "tokens": ("Token 序列", "Token 与向量", "token sequence"),
    "vector": ("特征向量", "Token 与向量", "feature vector"),
    "bars": ("权重条", "Token 与向量", "weight bars"),
    "kernel": ("卷积核", "卷积核与采样", "convolution kernel"),
    "patches": ("图像分块", "卷积核与采样", "image patches"),
    "sampling": ("采样网格", "卷积核与采样", "sampling grid"),
    "graph": ("图结构", "网络与图结构", "graph"),
    "nn": ("神经元连接层", "网络与图结构", "neuron layers"),
    "tree": ("树状结构", "网络与图结构", "tree"),
    "trap": ("编码器梯形", "模块与结构块", "encoder trapezoid"),
    "block": ("网络模块", "模块与结构块", "network block"),
    "layers": ("层堆叠模块", "模块与结构块", "stacked layers"),
    "unet": ("U 形编码解码结构", "模块与结构块", "U-shaped encoder-decoder"),
    "op": ("运算符号", "符号与箭头", "operator symbol"),
    "wave": ("时序曲线", "曲线与信号", "time series"),
    "curve": ("函数曲线", "曲线与信号", "curve"),
    "surface": ("三维曲面", "曲线与信号", "3D surface"),
    "heat": ("热力图", "热图与特征图", "heat map"),
    "fmap": ("特征图", "热图与特征图", "feature map"),
    "noise": ("噪声图", "噪声、频谱与小波", "noise image"),
    "spectrum": ("频谱图", "噪声、频谱与小波", "spectrum"),
    "weather": ("气象场", "气象与地球数据", "weather field"),
    "globe": ("地球网格", "气象与地球数据", "globe mesh"),
    "radar": ("雷达回波图", "气象与地球数据", "radar echo"),
    "sample": ("输入图像样例", "图像与点云", "input image"),
    "pc": ("点云", "图像与点云", "point cloud"),
    "mesh": ("三维网格", "图像与点云", "3D mesh"),
    "icon": ("示意符号", "符号与箭头", "pictogram"),
}
CATEGORIES = ["张量与特征图", "矩阵与注意力图", "Token 与向量", "卷积核与采样", "网络与图结构", "模块与结构块",
              "符号与箭头", "曲线与信号", "热图与特征图", "噪声、频谱与小波", "气象与地球数据", "图像与点云"]
COLOURS = [(15, "红色"), (40, "橙色"), (65, "黄色"), (160, "绿色"), (195, "青色"), (250, "蓝色"), (290, "紫色"),
           (335, "粉色"), (361, "红色")]


def colour_name(rgb_list):
    """Chinese name of the dominant chromatic colour, weighted by area."""
    weights = Counter()
    for (r, g, b), area in rgb_list:
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        if s < 0.18 or l > 0.93 or l < 0.08:
            continue
        hue = h * 360
        name = next(n for limit, n in COLOURS if hue < limit)
        weights[name] += area * (0.4 + s)
    total = sum(a for _, a in rgb_list) or 1
    if not weights:
        return "灰色"
    name, weight = weights.most_common(1)[0]
    if len(weights) >= 3 and weight < total * 0.45:
        return "彩色"
    return name


def grid_size(members):
    """(rows, cols) when the element is a regular grid of equally sized cells, else (0, 0)."""
    cells = []
    for d in members:
        for item in d["items"]:
            if item[0] == "re":
                r = pymupdf.Rect(item[1])
                if 1.5 < r.width < 60 and 1.5 < r.height < 60:
                    cells.append(r)
    if len(cells) < 4:
        return 0, 0
    size = Counter((round(r.width), round(r.height)) for r in cells).most_common(1)[0][0]
    same = [r for r in cells if (round(r.width), round(r.height)) == size]

    def groups(values):
        values = sorted(values)
        count, last = 0, None
        for v in values:
            if last is None or v - last > 1.0:
                count += 1
            last = v
        return count
    rows, cols = groups([r.y0 for r in same]), groups([r.x0 for r in same])
    if rows >= 2 and cols >= 2 and len(same) >= 0.8 * rows * cols and rows <= 24 and cols <= 24:
        return rows, cols
    return 0, 0


def visible_fill(d):
    fill = d.get("fill")
    return "f" in (d.get("type") or "") and fill is not None and len(fill) >= 3 and cand.opacity(d.get("fill_opacity")) > 0.04


def vector_members(page, box):
    inner = box + (-0.7, -0.7, 0.7, 0.7)
    out = []
    for d in page.get_drawings():
        r = d["rect"]
        if not inner.contains(r) or r.width > page.rect.width * 0.85:
            continue
        if cand.has_fill(d) or cand.has_stroke(d) or visible_fill(d):
            out.append(d)
    return out


def redraw(members, box):
    """Like candidates.redraw, but white fills are kept."""
    doc = pymupdf.open()
    page = doc.new_page(width=box.width + 2 * cand.PAD, height=box.height + 2 * cand.PAD)
    shift = pymupdf.Matrix(1, 0, 0, 1, -box.x0 + cand.PAD, -box.y0 + cand.PAD)
    shape = page.new_shape()
    for d in sorted(members, key=lambda d: d.get("seqno", 0)):
        for item in d["items"]:
            op = item[0]
            if op == "l":
                shape.draw_line(item[1] * shift, item[2] * shift)
            elif op == "c":
                shape.draw_bezier(item[1] * shift, item[2] * shift, item[3] * shift, item[4] * shift)
            elif op == "re":
                shape.draw_rect(pymupdf.Rect(item[1]) * shift)
            elif op == "qu":
                shape.draw_quad(pymupdf.Quad(item[1]) * shift)
        cap = d.get("lineCap") or 0
        if isinstance(cap, (tuple, list)):
            cap = max(cap) if cap else 0
        shape.finish(
            fill=d["fill"][:3] if visible_fill(d) else None,
            color=d["color"][:3] if cand.has_stroke(d) else None,
            dashes=d.get("dashes") or None, even_odd=bool(d.get("even_odd")),
            closePath=bool(d.get("closePath")), lineJoin=d.get("lineJoin") or 0, lineCap=cap,
            width=d.get("width") or 0.5,
            stroke_opacity=cand.opacity(d.get("stroke_opacity")), fill_opacity=cand.opacity(d.get("fill_opacity")))
    shape.commit()
    return doc


def export(task):
    entry, candidate = task
    eid = entry["id"]
    doc = pymupdf.open(PDF_DIR / f"{candidate['paper']}.pdf")
    page = doc[candidate["page"] - 1]
    box = pymupdf.Rect(entry.get("box") or candidate["box"])
    files, info = {}, {}
    if candidate["kind"] == "vector":
        members = vector_members(page, box)
        if not members:
            raise ValueError(f"{eid}: no drawings in box")
        sub = redraw(members, box)
        svg = sub[0].get_svg_image()
        (OUT / f"{eid}.svg").write_text(svg, encoding="utf-8")
        zoom = PNG_SIDE / max(box.width, box.height)
        pix = sub[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=True)
        image = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
        bbox = image.getbbox()
        if bbox:
            image = image.crop(bbox)
        image.save(OUT / f"{eid}.png", optimize=True)
        files = {"png": f"{eid}.png", "svg": f"{eid}.svg"}
        areas = [((d["fill"][0], d["fill"][1], d["fill"][2]), d["rect"].width * d["rect"].height)
                 for d in members if cand.has_fill(d)]
        areas += [((d["color"][0], d["color"][1], d["color"][2]), d["rect"].width + d["rect"].height)
                  for d in members if cand.has_stroke(d)]
        info["colour"] = colour_name(areas)
        info["grid"] = grid_size(members)
    else:
        pix = pymupdf.Pixmap(doc, candidate["xref"])
        smask = doc.xref_get_key(candidate["xref"], "SMask")
        if smask[0] == "xref":
            pix = pymupdf.Pixmap(pix, pymupdf.Pixmap(doc, int(smask[1].split()[0])))
        if pix.colorspace and pix.colorspace.n not in (1, 3):
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        mode = {1: "L", 2: "LA", 3: "RGB", 4: "RGBA"}[pix.n]
        image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
        if image.mode in ("L", "LA") and entry["type"] in ("heat", "fmap", "weather", "radar", "sample", "noise"):
            image = image.convert("RGB" if image.mode == "L" else "RGBA")
        if max(image.size) > 2400:
            image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
        image.save(OUT / f"{eid}.png", optimize=True)
        files = {"png": f"{eid}.png"}
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255
        sample = rgb.reshape(-1, 3)[:: max(1, rgb.shape[0] * rgb.shape[1] // 4000)]
        info["colour"] = colour_name([((r, g, b), 1) for r, g, b in sample])
        info["grid"] = (0, 0)
    thumb = image.copy()
    if thumb.mode not in ("RGB", "RGBA"):
        thumb = thumb.convert("RGBA")
    thumb.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.Resampling.LANCZOS)
    thumb.save(OUT / "thumbs" / f"{eid}.webp", quality=90, method=6)
    files["thumb"] = f"thumbs/{eid}.webp"
    return {"id": eid, "files": files, "width": image.width, "height": image.height,
            "has_alpha": image.mode in ("RGBA", "LA"), "svg_kind": "vector" if "svg" in files else "",
            "hashes": {k: sha256(OUT / v) for k, v in files.items() if k != "thumb"},
            "bytes": {k: (OUT / v).stat().st_size for k, v in files.items()}, **info}


def name_for(entry, info, short):
    noun = TYPES[entry["type"]][0]
    if entry.get("name"):
        return entry["name"]
    colour = info.get("colour", "")
    rows, cols = info.get("grid") or (0, 0)
    size = ""
    if entry["type"] in ("matrix", "attn", "mask", "kernel", "patches", "sampling") and 2 <= rows <= 24 and 2 <= cols <= 24:
        size = f"{rows}×{cols} "
    if entry["type"] in ("heat", "fmap", "sample", "weather", "radar", "noise", "spectrum", "pc", "globe", "mesh",
                         "op", "wave", "curve", "surface"):
        colour = "" if entry["type"] in ("op", "sample", "weather", "radar", "pc", "globe", "mesh") else colour
    if colour in ("灰色",) and entry["type"] in ("heat", "fmap"):
        colour = "灰度"
    return f"{size}{colour}{noun}".strip()


def main():
    curated = read_json(HERE / "elements.json")
    candidates = {c["id"]: c for c in read_json(CACHE / "elements" / "candidates.json")}
    papers = read_json(HERE.parent / "papers" / "papers.json")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "thumbs").mkdir(exist_ok=True)
    work, seen = [], set()
    for n, entry in enumerate(curated["elements"]):
        c = candidates[entry["cand"]]
        entry = dict(entry)
        entry["id"] = "e-" + entry["cand"].replace("~", "-").replace("arch-paper-", "")
        if entry["id"] in seen:
            raise ValueError(f"duplicate element {entry['id']}")
        seen.add(entry["id"])
        work.append((entry, c))
    with ProcessPoolExecutor(max_workers=8) as pool:
        built = list(pool.map(export, work))
    records, names = [], Counter()
    for (entry, c), out in zip(work, built):
        short = papers[c["paper"]]["short"]
        name = name_for(entry, out, short)
        names[name] += 1
        noun, category, english = TYPES[entry["type"]]
        figure = c["figure"].split("~")[0]
        fig_no = figure.rsplit("-f", 1)[-1] if "-f" in figure else ""
        records.append({
            "id": out["id"], "kind": "atomic", "name": name, "category": category, "type": entry["type"],
            "tags": list(dict.fromkeys([short, noun, english, out.get("colour", ""), *entry.get("tags", [])]))[:10],
            "description": entry.get("desc") or f"从 {short} 论文插图中分离出的{noun}，"
                                                 + ("保留原始矢量路径，可在 SVG 中直接改色、改尺寸。" if "svg" in out["files"]
                                                    else "按论文中嵌入位图的原始分辨率导出。"),
            "source": c["paper"], "page": c["page"], "figure": f"Fig. {fig_no}" if fig_no.isdigit() else "",
            "files": {k: f"assets/elements/{v}" for k, v in out["files"].items()},
            "width": out["width"], "height": out["height"], "svg_kind": out["svg_kind"],
            "has_alpha": out["has_alpha"], "hashes": out["hashes"], "bytes": out["bytes"],
            "provenance": {"page": c["page"], "box": c["box"], "candidate": c["id"], "kind": c["kind"]},
        })
    # Make repeated names distinguishable by the source model.
    for r in records:
        if names[r["name"]] > 1:
            r["name"] = f"{r['name']} · {r['tags'][0]}"
    counts = Counter(r["name"] for r in records)
    for r in records:
        if counts[r["name"]] > 1:
            counts[r["name"]] -= 1
            r["name"] = f"{r['name']} {counts[r['name']] + 1}"
    keep = {Path(v).name for r in records for v in r["files"].values()}
    for path in list(OUT.glob("*.*")) + list((OUT / "thumbs").glob("*.*")):
        if path.name not in keep:
            path.unlink()
    sys.path.insert(0, str(HERE.parent / "papers"))
    import catalog as paper_catalog  # papers/catalog.py: source records with authors and licenses
    all_sources = paper_catalog.sources()
    used = sorted({r["source"] for r in records})
    write_json(MANIFESTS / "elements.json", {"categories": CATEGORIES, "sources": {k: all_sources[k] for k in used},
                                             "assets": records})
    print({"elements": len(records), "by_category": Counter(r["category"] for r in records),
           "vector": sum(1 for r in records if r["svg_kind"]),
           "bytes": sum(sum(r["bytes"].values()) for r in records)})


if __name__ == "__main__":
    main()
