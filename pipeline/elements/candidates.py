#!/usr/bin/env python3
"""Find reusable figure elements (图元) inside the figures of the cached paper PDFs.

Every figure region (all captioned figures of every paper, plus the curated crops)
is split into connected groups of vector drawings — feature-map cubes, stacked
slices, token rows, attention matrices, kernels, graphs, encoder trapezoids …
Each group is redrawn on its own page from its original paths only (no text, no
neighbouring shapes), which gives an editable SVG and a transparent PNG.  Bitmaps
embedded in the figures (feature maps, heat maps, weather fields, noise) are
extracted at their native resolution.

Plain boxes, single lines and other trivial shapes are filtered out; near
duplicates are merged with a perceptual hash.  Results go to ``.cache/elements``
(``candidates.json``, ``cand/``, contact sheets) for manual curation in
``pipeline/elements/elements.json``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / "papers")]
from common import CACHE, read_json, write_json  # noqa: E402
import extract  # noqa: E402

HERE = Path(__file__).resolve().parent
PAPERS = HERE.parent / "papers"
PDF_DIR = CACHE / "papers" / "pdf"
OUT = CACHE / "elements"
PAD = 1.5
PREVIEW_SIDE = 480
CAPTION = re.compile(r"^\s*(?:figure|fig\.?)\s*(\d{1,2})(?![\d.]\d)\s*(?:[:.|–—]|\s+[A-Z(])", re.I)
# Diagrams worth mining; captions of result plots and qualitative examples are skipped.
DIAGRAM = re.compile(r"architect|overview|framework|pipeline|module|block|structure|illustrat|schem|diagram|"
                     r"network|layer|mechanism|design|process|unit|cell|encoder|decoder|operation|approach|"
                     r"model|attention|component|procedure|paradigm|stage|branch|flow|computation|"
                     r"convolution|embedding|token|patch|fusion|decomposition|depict|sketch", re.I)
RESULT = re.compile(r"accurac|results? (?:on|of|for)|performance|curve|plot|error|loss|speed|latency|trade-?off|"
                    r"ablation|comparison (?:with|to|of (?:the )?(?:results|accuracy))|versus|\bvs\.?|scaling|"
                    r"qualitative|examples? of|samples? (?:from|of|generated)|generated|visuali[sz]ation of|"
                    r"top-?1|map\b|mIoU|AP\b|BLEU|perplexity|histogram|distribution of|correlation|training|"
                    r"statistic|benchmark|t-?SNE|confusion|ROC|success|failure|zero-shot|fine-?tun", re.I)


# ----------------------------------------------------------------------- regions
def figure_regions(key):
    """All captioned figures of one paper: (figure id, page index, box)."""
    doc = pymupdf.open(PDF_DIR / f"{key}.pdf")
    body = extract.body_font_size(doc)
    headers = extract.running_lines(doc)
    numbers = {}
    for page in doc:
        for text, line, block, size, first in extract.page_lines(page):
            m = CAPTION.match(text)
            if m and first and int(m.group(1)) not in numbers:
                numbers[int(m.group(1))] = " ".join(page.get_text("text", clip=block).split())[:300]
    out = []
    for n, caption in sorted(numbers.items()):
        head = caption[:160]
        if not DIAGRAM.search(head) or RESULT.search(head):
            continue
        try:
            index, box = extract.auto_box(doc, f"F{n}", body, headers)
        except Exception:
            continue
        if box.width > 20 and box.height > 20:
            out.append((f"{key}-f{n}", index, [round(v, 2) for v in box]))
    return out


# --------------------------------------------------------------------- drawings
def opacity(value):
    return 1.0 if value is None else float(value)


def is_white(colour):
    return colour is not None and len(colour) >= 3 and min(colour) > 0.965


def has_fill(d):
    fill = d.get("fill")
    return ("f" in (d.get("type") or "") and fill is not None and len(fill) >= 3
            and not is_white(fill) and opacity(d.get("fill_opacity")) > 0.04)


def has_stroke(d):
    colour = d.get("color")
    return ("s" in (d.get("type") or "") and colour is not None and len(colour) >= 3
            and not is_white(colour) and opacity(d.get("stroke_opacity")) > 0.04 and (d.get("width") or 1) > 0)


def usable(d, page_rect):
    r = d["rect"]
    if r.width > page_rect.width * 0.85 and r.height > page_rect.height * 0.7:
        return False
    return has_fill(d) or has_stroke(d)


def connector(d):
    """Thin strokes and arrow heads that join separate shapes."""
    r = d["rect"]
    if has_fill(d):
        return r.width * r.height < 14 and min(r.width, r.height) < 4 and len(d["items"]) <= 4
    return min(r.width, r.height) < 1.2 and max(r.width, r.height) > 6 and len(d["items"]) <= 3


def cluster(rects, tol=0.9):
    parent = list(range(len(rects)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    order = sorted(range(len(rects)), key=lambda i: rects[i].y0)
    for pos, a in enumerate(order):
        ra = rects[a]
        for b in order[pos + 1:]:
            rb = rects[b]
            if rb.y0 > ra.y1 + tol:
                break
            if rb.x0 <= ra.x1 + tol and ra.x0 <= rb.x1 + tol:
                parent[find(a)] = find(b)
    groups = {}
    for i in range(len(rects)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def features(members):
    fills, chroma, slanted, rects, curves, lines = set(), set(), 0, 0, 0, 0
    for d in members:
        if has_fill(d):
            key = tuple(round(c, 2) for c in d["fill"][:3])
            fills.add(key)
            if max(key) - min(key) > 0.12:
                chroma.add(key)
        for item in d["items"]:
            op = item[0]
            if op == "re":
                rects += 1
            elif op == "qu":
                rects += 1
            elif op == "c":
                curves += 1
            elif op == "l":
                lines += 1
                p, q = item[1], item[2]
                dx, dy = abs(q.x - p.x), abs(q.y - p.y)
                if dx > 0.8 and dy > 0.8 and 0.15 < dy / dx < 6:
                    slanted += 1
    return {"paths": len(members), "fills": len(fills), "colours": len(chroma), "slanted": slanted,
            "rects": rects, "curves": curves, "lines": lines}


def classify(f, w, h):
    """Rough shape class used to group contact sheets (curation decides the final one)."""
    if f["slanted"] >= 6 and f["fills"] >= 1:
        return "solid"        # cubes, slabs, stacked slices, planes
    if f["rects"] >= 6 and f["fills"] >= 1:
        return "grid"         # matrices, token rows, kernels
    if f["curves"] >= 12 and f["lines"] >= 3:
        return "graph"
    if f["slanted"] >= 2 and f["fills"] >= 1 and f["paths"] <= 6:
        return "trapezoid"
    if max(w, h) < 26 and f["curves"] >= 4:
        return "operator"
    if f["colours"] >= 2:
        return "colour"
    return "other"


def worth_keeping(f, w, h, region):
    if max(w, h) < 12 or min(w, h) < 4.5:
        return False
    if w * h > region.width * region.height * 0.55:
        return False
    if max(w / max(h, .1), h / max(w, .1)) > 14:
        return False
    if f["paths"] <= 2 and f["slanted"] < 4 and f["rects"] < 4 and f["curves"] < 8:
        return False      # a lone box, circle or line
    if f["fills"] == 0 and f["slanted"] < 6 and f["rects"] < 9 and f["curves"] < 16:
        return False      # outline-only boxes and arrows
    if f["fills"] <= 1 and f["colours"] == 0 and f["slanted"] < 4 and f["rects"] < 6 and f["curves"] < 12:
        return False      # single grey box with a frame
    return True


def redraw(members, box):
    doc = pymupdf.open()
    page = doc.new_page(width=box.width + 2 * PAD, height=box.height + 2 * PAD)
    shift = pymupdf.Matrix(1, 0, 0, 1, -box.x0 + PAD, -box.y0 + PAD)
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
            fill=d["fill"][:3] if has_fill(d) else None,
            color=d["color"][:3] if has_stroke(d) else None,
            dashes=d.get("dashes") or None, even_odd=bool(d.get("even_odd")),
            closePath=bool(d.get("closePath")), lineJoin=d.get("lineJoin") or 0, lineCap=cap,
            width=d.get("width") or 0.5,
            stroke_opacity=opacity(d.get("stroke_opacity")), fill_opacity=opacity(d.get("fill_opacity")))
    shape.commit()
    return doc


def ahash(image, size=12):
    im = image.convert("L").resize((size, size), Image.Resampling.BILINEAR)
    a = np.asarray(im, dtype=np.float32)
    return "".join("1" if v else "0" for v in (a > a.mean()).flatten())


def on_white(image):
    im = image.convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    return bg.convert("RGB")


# ----------------------------------------------------------------------- process
def process(task):
    key, regions = task
    doc = pymupdf.open(PDF_DIR / f"{key}.pdf")
    results, digests = [], set()
    by_page = {}
    for fid, index, box in regions:
        by_page.setdefault(index, []).append((fid, pymupdf.Rect(box)))
    for index, items in sorted(by_page.items()):
        page = doc[index]
        drawings = [d for d in page.get_drawings() if usable(d, page.rect)]
        claimed = set()
        for fid, region in items:
            inside = [d for d in drawings if region.contains(pymupdf.Point((d["rect"].x0 + d["rect"].x1) / 2,
                                                                               (d["rect"].y0 + d["rect"].y1) / 2))]
            seeds = [d for d in inside if not connector(d)]
            n = 0
            for group in cluster([d["rect"] for d in seeds]):
                members = [seeds[i] for i in group]
                box = pymupdf.Rect(members[0]["rect"])
                for d in members[1:]:
                    box |= d["rect"]
                marker = tuple(round(v) for v in box)
                if marker in claimed:
                    continue
                claimed.add(marker)
                grow = box + (-0.6, -0.6, 0.6, 0.6)
                members += [d for d in inside if connector(d) and grow.contains(d["rect"])]
                f = features(members)
                if not worth_keeping(f, box.width, box.height, region):
                    continue
                sub = redraw(members, box)
                zoom = PREVIEW_SIDE / max(box.width, box.height)
                pix = sub[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=True)
                image = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
                rgb = np.asarray(on_white(image))
                if (rgb < 245).any(axis=2).mean() < 0.01:
                    continue
                h = ahash(on_white(image))
                if (h, round(box.width / 4), round(box.height / 4)) in digests:
                    continue
                digests.add((h, round(box.width / 4), round(box.height / 4)))
                n += 1
                cid = f"{fid}~v{n:02d}"
                image.save(OUT / "cand" / f"{cid}.png")
                results.append({"id": cid, "paper": key, "figure": fid, "page": index + 1, "kind": "vector",
                                "box": [round(v, 2) for v in box], "class": classify(f, box.width, box.height),
                                "hash": h, **f})
            m = 0
            for info in page.get_image_info(xrefs=True):
                r = pymupdf.Rect(info["bbox"])
                if not region.intersects(r) or (r & region).get_area() < r.get_area() * 0.6:
                    continue
                if info["width"] < 40 or info["height"] < 40 or not info.get("xref"):
                    continue
                if r.width < 18 or r.height < 18:
                    continue
                try:
                    pix = pymupdf.Pixmap(doc, info["xref"])
                    smask = doc.xref_get_key(info["xref"], "SMask")
                    if smask[0] == "xref":
                        pix = pymupdf.Pixmap(pix, pymupdf.Pixmap(doc, int(smask[1].split()[0])))
                    if pix.colorspace and pix.colorspace.n not in (1, 3):
                        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                    mode = {1: "L", 2: "LA", 3: "RGB", 4: "RGBA"}[pix.n]
                    image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
                except Exception:
                    continue
                if image.width * image.height > 40_000_000:
                    continue
                rgb = np.asarray(on_white(image), dtype=np.int16)
                if rgb.std() < 6:
                    continue          # flat colour
                h = ahash(on_white(image))
                if h in digests:
                    continue
                digests.add(h)
                m += 1
                cid = f"{fid}~i{m:02d}"
                image.save(OUT / "cand" / f"{cid}.png")
                spread = float(np.mean(np.std(rgb.reshape(-1, 3), axis=0)))
                results.append({"id": cid, "paper": key, "figure": fid, "page": index + 1, "kind": "raster",
                                "box": [round(v, 2) for v in r], "xref": info["xref"],
                                "w": image.width, "h": image.height, "class": "bitmap", "hash": h,
                                "spread": round(spread, 1)})
    return results


def tasks():
    figures = read_json(PAPERS / "figures.json")
    curated = {}
    for sid, rec in read_json(PAPERS / "extracted.json").items():
        spec = next((f for f in figures if f"p-{f['paper']}-{f['fig'].lower().replace('.', '-')}" == sid), None)
        if spec:
            curated.setdefault(spec["paper"], []).append((sid, rec["page"] - 1, rec["box"]))
    for item in read_json(PAPERS / "legacy.json"):
        prov = item.get("provenance") or {}
        if item.get("paper") and prov.get("page") and prov.get("box"):
            curated.setdefault(item["paper"], []).append((item["id"], prov["page"] - 1, prov["box"]))
    keys = sorted(p.stem for p in PDF_DIR.glob("*.pdf"))
    return [(k, curated.get(k, [])) for k in keys]


def regions_for(task):
    key, curated = task
    try:
        found = figure_regions(key)
    except Exception:
        found = []
    regions = list(curated)
    for fid, index, box in found:
        r = pymupdf.Rect(box)
        if any(index == i and (r & pymupdf.Rect(b)).get_area() > 0.6 * min(r.get_area(), pymupdf.Rect(b).get_area())
               for _, i, b in curated):
            continue
        regions.append((fid, index, box))
    return key, regions


def sheet(cands, path, cols=8, cell=200):
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 11)
    rows = (len(cands) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * cell, rows * (cell + 16)), "#dfe3e8")
    draw = ImageDraw.Draw(canvas)
    for i, c in enumerate(cands):
        x, y = (i % cols) * cell, (i // cols) * (cell + 16)
        im = Image.open(OUT / "cand" / f"{c['id']}.png")
        im.draft("RGB", (cell, cell))
        im = on_white(im)
        im.thumbnail((cell - 8, cell - 8))
        canvas.paste(im, (x + (cell - im.width) // 2, y + 16 + (cell - im.height) // 2))
        draw.text((x + 3, y + 1), f"{c['n']} {c['id'][:26]}", fill="black", font=font)
    canvas.save(path, quality=80)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    (OUT / "cand").mkdir(parents=True, exist_ok=True)
    for old in (OUT / "cand").glob("*"):
        old.unlink()
    for old in OUT.glob("*.jpg"):
        old.unlink()
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        work = list(pool.map(regions_for, tasks()))
        print("regions", sum(len(r) for _, r in work), flush=True)
        results = [c for part in pool.map(process, work) for c in part]
    # Global de-duplication of identical shapes reused across papers.
    seen, unique = set(), []
    for c in results:
        key = (c["hash"], c["kind"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
    order = ["solid", "grid", "graph", "trapezoid", "operator", "colour", "other", "bitmap"]
    unique.sort(key=lambda c: (order.index(c["class"]), c["paper"], c["id"]))
    for n, c in enumerate(unique):
        c["n"] = n
    write_json(OUT / "candidates.json", unique)
    counts = {k: sum(c["class"] == k for c in unique) for k in order}
    print("candidates", len(unique), counts, flush=True)
    per = 64
    for k in order:
        items = [c for c in unique if c["class"] == k]
        for start in range(0, len(items), per):
            sheet(items[start:start + per], OUT / f"{k}-{start // per + 1:03d}.jpg",
                  cols=10 if k == "bitmap" else 8, cell=160 if k == "bitmap" else 200)


if __name__ == "__main__":
    main()
