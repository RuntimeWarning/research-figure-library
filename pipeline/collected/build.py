#!/usr/bin/env python3
"""Collect figure elements from openly licensed libraries (see ``picks.py``).

Sources are downloaded at pinned commits into ``.cache/web/`` and processed into
``dist/assets/collected/<source>/``: an SVG where the source is vector, a PNG and a
WebP thumbnail.  Metadata goes to ``pipeline/manifests/collected.json``.

* d2l (CC BY-SA 4.0): the book's SVG figures, unchanged apart from px sizes.
* dl-visuals (CC BY 4.0): PNG figures with the surrounding white space trimmed.
* ML Visuals (MIT): slides exported from Google Slides as PDF, cropped per element
  and converted to SVG with PyMuPDF.
* NN-SVG (MIT): schematics rendered by ``nnsvg.mjs`` (run it first; needs
  puppeteer-core and Chrome) into ``.cache/web/nn-svg-out``.
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

import pymupdf
import resvg_py
from PIL import Image, ImageChops

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from common import ASSETS, CACHE, DIST, MANIFESTS, fetch, sha256, write_json  # noqa: E402
from picks import PICKS, PREFIX, SOURCES  # noqa: E402

WEB = CACHE / "web"
OUT = ASSETS / "collected"
PNG_SIDE = 1600
THUMB_SIDE = 560
ORDER = ["ml-visuals", "nn-svg", "d2l", "dl-visuals"]


def categories():
    text = (Path(__file__).resolve().parents[1] / "elements" / "generate.py").read_text(encoding="utf-8")
    block = re.search(r"^CATEGORIES = \[(.*?)\]", text, re.S | re.M).group(1)
    return re.findall(r'"([^"]+)"', block)


# ------------------------------------------------------------------ sources
def raw(repo, commit, path):
    return f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"


def unpack(repo, commit):
    root = WEB / f"{repo.split('/')[1]}-{commit}"
    if not root.is_dir():
        data = fetch(f"https://codeload.github.com/{repo}/zip/{commit}", WEB / f"{repo.split('/')[1]}-{commit}.zip")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            archive.extractall(WEB)
    return root


def prepare():
    licences = DIST / "licenses"
    s = SOURCES["d2l"]
    for ref, *_ in PICKS["d2l"]:
        fetch(raw("d2l-ai/d2l-en", s["commit"], f"img/{ref}"), WEB / "d2l" / ref)
    (licences / "d2l-LICENSE.txt").write_bytes(fetch(raw("d2l-ai/d2l-en", s["commit"], "LICENSE"), WEB / "d2l" / "LICENSE"))
    roots = {"dl-visuals": unpack("dvgodoy/dl-visuals", SOURCES["dl-visuals"]["commit"])}
    (licences / "dl-visuals-LICENSE.txt").write_bytes((roots["dl-visuals"] / "LICENSE").read_bytes())
    deck = SOURCES["ml-visuals"]["deck"]
    fetch(deck + "export/pdf", WEB / "ml-visuals" / "ml-visuals.pdf", timeout=300)
    (licences / "ml-visuals-LICENSE.txt").write_bytes(
        fetch(raw("dair-ai/ml-visuals", SOURCES["ml-visuals"]["commit"], "LICENSE"), WEB / "ml-visuals" / "LICENSE"))
    roots["nn-svg"] = unpack("alexlenail/NN-SVG", SOURCES["nn-svg"]["commit"])
    (licences / "nn-svg-LICENSE.txt").write_bytes((roots["nn-svg"] / "LICENSE").read_bytes())
    if not (WEB / "nn-svg-out").is_dir():
        raise SystemExit(f"Run first: node pipeline/collected/nnsvg.mjs {roots['nn-svg']} {WEB / 'nn-svg-out'}")
    return roots


# ------------------------------------------------------------------ processing
def px_size(svg: str) -> str:
    """Use unitless (px) width/height on the root element; resvg rejects some units."""
    match = re.search(r"<svg\b[^>]*>", svg)
    root = match.group(0)
    fixed = re.sub(r'\b(width|height)="([\d.]+)(?:pt|px|mm)?"', r'\1="\2"', root)
    return svg[:match.start()] + fixed + svg[match.end():]


def render_svg(svg: str) -> Image.Image:
    vb = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', svg)
    w, h = float(vb.group(1)), float(vb.group(2))
    scale = PNG_SIDE / max(w, h)
    png = resvg_py.svg_to_bytes(svg_string=svg, width=round(w * scale), height=round(h * scale))
    return Image.open(io.BytesIO(bytes(png))).convert("RGBA")


def trim(image: Image.Image, margin: int = 24) -> Image.Image:
    rgb = image.convert("RGB")
    corner = rgb.getpixel((0, 0))
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, corner)).convert("L").point(lambda v: 255 if v > 12 else 0)
    box = diff.getbbox()
    if not box:
        return image
    x0, y0, x1, y1 = box
    return image.crop((max(0, x0 - margin), max(0, y0 - margin), min(image.width, x1 + margin),
                       min(image.height, y1 + margin)))


def slide_box(page) -> pymupdf.Rect:
    full = page.rect
    rects = [pymupdf.Rect(d["rect"]) for d in page.get_drawings()]
    rects += [pymupdf.Rect(i["bbox"]) for i in page.get_image_info()]
    rects += [pymupdf.Rect(b["bbox"]) for b in page.get_text("dict")["blocks"] if b["type"] == 0]
    box = pymupdf.Rect()
    for r in rects:
        if r.is_empty or (r.width > full.width * 0.97 and r.height > full.height * 0.9):
            continue
        box |= r
    return (box + (-6, -6, 6, 6)) & full


def crop_slide(doc, page_no, box):
    page = doc[page_no]
    clip = pymupdf.Rect(box) if box else slide_box(page)
    out = pymupdf.open()
    target = out.new_page(width=clip.width, height=clip.height)
    target.show_pdf_page(target.rect, doc, page_no, clip=clip)
    svg = px_size(target.get_svg_image(text_as_path=True))
    zoom = PNG_SIDE / max(clip.width, clip.height)
    pix = target.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=True)
    image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
    return svg, image


def upstream(key, ref):
    s = SOURCES[key]
    if key == "d2l":
        return f"{s['repo']}/blob/{s['commit']}/img/{ref}"
    if key == "dl-visuals":
        return f"{s['repo']}/blob/{s['commit']}/{ref}".replace(" ", "%20")
    if key == "ml-visuals":
        return s["deck"]
    return s["url"]


def process(key, ref, roots, deck):
    if key == "d2l":
        svg = px_size((WEB / "d2l" / ref).read_text(encoding="utf-8"))
        return svg, render_svg(svg)
    if key == "nn-svg":
        svg = px_size((WEB / "nn-svg-out" / ref).read_text(encoding="utf-8"))
        return svg, render_svg(svg)
    if key == "ml-visuals":
        page_no, box = ref
        return crop_slide(deck, page_no, box)
    image = Image.open(roots["dl-visuals"] / ref)
    image = trim(image.convert("RGBA") if image.mode not in ("RGB", "RGBA") else image)
    return None, image


def main():
    allowed = set(categories())
    roots = prepare()
    deck = pymupdf.open(WEB / "ml-visuals" / "ml-visuals.pdf")
    OUT.mkdir(parents=True, exist_ok=True)
    records, keep = [], set()
    for key in ORDER:
        source = SOURCES[key]
        folder = OUT / key
        (folder / "thumbs").mkdir(parents=True, exist_ok=True)
        for ref, pid, zh, en, category, tags in PICKS[key]:
            if category not in allowed:
                raise ValueError(f"{pid}: unknown category {category}")
            ident = f"{PREFIX[key]}-{pid}"
            svg, image = process(key, ref, roots, deck)
            files = {"png": folder / f"{pid}.png", "thumb": folder / "thumbs" / f"{pid}.webp"}
            if svg is not None:
                files["svg"] = folder / f"{pid}.svg"
                files["svg"].write_text(svg, encoding="utf-8", newline="\n")
            image.save(files["png"], optimize=True)
            thumb = image.copy()
            thumb.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.Resampling.LANCZOS)
            thumb.save(files["thumb"], quality=90, method=6)
            keep.update(p.resolve() for p in files.values())
            page = ref[0] + 1 if key == "ml-visuals" else ""
            records.append({
                "id": ident, "kind": "atomic", "collection": key, "source": key, "category": category,
                "name": zh, "english": en, "tags": tags + [source["short"]],
                "description": f"收集自 {source['title']}，{source['license_name']} 许可。{source['processing']}。",
                "upstream": upstream(key, ref), "page": page,
                "svg_kind": "" if svg is None else ("mixed" if "<image" in svg else "vector"),
                "has_alpha": image.mode == "RGBA" and image.getextrema()[3][0] < 255,
                "width": image.width, "height": image.height,
                "files": {k: p.relative_to(DIST).as_posix() for k, p in files.items()},
                "hashes": {k: sha256(p) for k, p in files.items() if k != "thumb"},
                "bytes": {k: p.stat().st_size for k, p in files.items() if k != "thumb"},
                "order": 10000 + len(records),
            })
    for path in OUT.rglob("*.*"):
        if path.resolve() not in keep:
            path.unlink()
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate collected ids")
    sources = {k: {**v, "collected": True} for k, v in SOURCES.items()}
    write_json(MANIFESTS / "collected.json", {"sources": sources, "assets": records})
    print({"collected": len(records), "by_source": Counter(r["collection"] for r in records),
           "by_category": Counter(r["category"] for r in records),
           "bytes": sum(sum(r["bytes"].values()) for r in records)})


if __name__ == "__main__":
    main()
