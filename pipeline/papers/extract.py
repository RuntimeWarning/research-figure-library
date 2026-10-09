#!/usr/bin/env python3
"""Crop original figures from the cached arXiv PDFs listed in figures.json.

For each figure the script finds its caption ("Figure 3:", "Fig. 3.", "Table 1:"),
takes the graphics between the caption and the preceding body text, and exports:

* ``<id>.png``   rendered crop (300 dpi, or the native resolution of a dominant
                 embedded bitmap), white background, no redrawing or recolouring;
* ``<id>.pdf``   one-page PDF clipped to the same box, keeping vector content
                 (vector figures only, when the file stays under 500 KB);
* ``<id>.svg``   only when the PDF region is vector and renders faithfully;
* ``thumbs/<id>.webp`` a small preview used by the web page.

A figure entry may override the automatic box with ``"crop": [page, x0, y0, x1, y1]``
in PDF points.  Results are written to ``pipeline/manifests/papers.json`` (merged
with the existing records) and contact sheets go to ``.cache/papers/qa/``.

Requires PyMuPDF, Pillow, numpy and resvg-py.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pymupdf
import resvg_py
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ASSETS, CACHE, read_json, sha256, write_json  # noqa: E402

HERE = Path(__file__).resolve().parent
PDF_DIR = CACHE / "papers" / "pdf"
QA_DIR = CACHE / "papers" / "qa"
OUT = ASSETS / "papers"
THUMBS = OUT / "thumbs"
DPI = 300
MAX_SIDE = 3000
MAX_PDF_BYTES = 500_000
MAX_SVG_BYTES = 2_000_000
THUMB_SIDE = 720
CAPTION_LINE = re.compile(r"^\s*(?:figure|fig\.?|table|tab\.)\s*\d+(?:\.\d+)?\s*(?:[:.|–—]|\s+[A-Z(])", re.I)


def caption_regex(fig: str):
    kind, number = fig[0], re.escape(fig[1:])
    head = r"(?:table|tab\.)" if kind == "T" else r"(?:figure|fig\.?)"
    return re.compile(rf"^\s*{head}\s*{number}(?![\d.]\d)\s*(?P<rest>.*)$", re.I)


def page_lines(page):
    """Yield (text, line_rect, block_rect, size, first_line_of_block) in reading order."""
    data = page.get_text("dict")
    for block in data["blocks"]:
        if block.get("type") != 0:
            continue
        first = True
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not text:
                continue
            size = max(span["size"] for span in line["spans"])
            yield text, pymupdf.Rect(line["bbox"]), pymupdf.Rect(block["bbox"]), size, first
            first = False


def find_caption(doc, fig):
    """Return (page_index, caption_line_rect, caption_block_rect) for the figure caption.

    Real captions start a text block with "Figure 2:", "Fig. 2.", "Figure 2 |" or a capitalised
    sentence ("Figure 2 The ..."); in-text references read "Figure 2 shows ...".
    """
    pattern = caption_regex(fig)
    ranked = []
    for index, page in enumerate(doc):
        for text, line, block, size, first in page_lines(page):
            match = pattern.match(text)
            if not match:
                continue
            rest = match.group("rest")
            if re.match(r"^[:.|–—\-]", rest):
                rank = 0 if first else 2
            elif not rest or rest[:1].isupper() or rest[:1] == "(":
                rank = 1 if first else 3
            else:
                continue
            ranked.append((rank, index, line.y0, line, block))
    if not ranked:
        raise LookupError(f"caption {fig} not found")
    rank, index, _, line, block = min(ranked, key=lambda r: (r[0], r[1], r[2]))
    return index, line, block


def body_font_size(doc):
    sizes = {}
    for page in list(doc)[: min(len(doc), 6)]:
        for text, line, block, size, first in page_lines(page):
            sizes[round(size, 1)] = sizes.get(round(size, 1), 0) + len(text)
    return max(sizes, key=sizes.get) if sizes else 10.0


def running_lines(doc):
    """Map page index -> rects of running headers/footers and page numbers."""
    def norm(text):
        return re.sub(r"\d+", "#", text.lower()).strip()
    entries, counts = [], {}
    for index, page in enumerate(doc):
        height = page.rect.height
        for text, line, block, size, first in page_lines(page):
            if line.y1 < height * 0.15 or line.y0 > height * 0.9:
                # Running headers repeat at the same height; figure labels do not.
                key = (norm(text), round(line.y0 / 4))
                entries.append((index, line, key))
                counts.setdefault(key, set()).add(index)
    known = re.compile(r"^(published as|under review|a preprint|technical report|submission and formatting|"
                       r"preprint|accepted|proceedings|arxiv)")
    result = {}
    for index, line, key in entries:
        # Count distinct pages: a label repeated within one figure is not a running header.
        repeats = len(set().union(*(counts.get((key[0], key[1] + d), set()) for d in (-1, 0, 1))))
        number = bool(re.fullmatch(r"[#\s:•·|–—.\-]+", key[0]))
        if repeats >= min(3, max(2, len(doc) // 3)) or number or known.match(key[0]):
            result.setdefault(index, []).append((line, number))
    return result


def layout(page, body_size):
    """Estimate text-area margins and whether the page uses two columns."""
    blocks = []
    data = page.get_text("dict")
    for block in data["blocks"]:
        if block.get("type") != 0:
            continue
        lines = block["lines"]
        text = " ".join("".join(s["text"] for s in l["spans"]) for l in lines)
        sizes = [s["size"] for l in lines for s in l["spans"] if s["text"].strip()]
        if not sizes:
            continue
        direction = lines[0].get("dir", (1, 0))
        blocks.append({
            "rect": pymupdf.Rect(block["bbox"]), "lines": len(lines), "chars": len(text),
            "size": sum(sizes) / len(sizes), "horizontal": abs(direction[0]) > 0.9,
        })
    body = [b for b in blocks if b["horizontal"] and b["lines"] >= 3 and abs(b["size"] - body_size) < 1.2]
    width = page.rect.width
    if body:
        left = min(b["rect"].x0 for b in body)
        right = max(b["rect"].x1 for b in body)
    else:
        left, right = width * 0.08, width * 0.92
    narrow = [b for b in body if b["rect"].width < (right - left) * 0.6]
    two_columns = len(narrow) >= max(2, len(body) * 0.5)
    return blocks, left, right, two_columns


def is_body(block, body_size, span_width, shapes=()):
    if not block["horizontal"] or abs(block["size"] - body_size) >= 1.0:
        return False
    wide = block["rect"].width > span_width * 0.6
    if not (wide and ((block["lines"] >= 2 and block["chars"] > 80)
                      or (block["chars"] > 60 and block["rect"].width > span_width * 0.85))):
        return False
    area = block["rect"].get_area() or 1
    covered = sum((block["rect"] & r).get_area() for r in shapes if r.width > 4 and r.height > 4)
    return covered < area * 0.15


def graphics(page):
    rects = []
    def visible(colour):
        return colour is not None and min(colour) < 0.995
    for item in page.get_drawings():
        r = item.get("rect")
        if r is None:
            continue
        kind = item.get("type") or ""
        if not (("f" in kind and visible(item.get("fill"))) or ("s" in kind and visible(item.get("color")))):
            continue  # white or transparent shapes are invisible on the page
        r = pymupdf.Rect(r)
        if r.width > page.rect.width * 0.95 and r.height > page.rect.height * 0.9:
            continue  # page background
        rects.append(r)
    for info in page.get_image_info():
        rects.append(pymupdf.Rect(info["bbox"]))
    return rects


def union(rects):
    xs0 = [r.x0 for r in rects]; ys0 = [r.y0 for r in rects]
    xs1 = [r.x1 for r in rects]; ys1 = [r.y1 for r in rects]
    return pymupdf.Rect(min(xs0), min(ys0), max(xs1), max(ys1))


def centre(r):
    return pymupdf.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)


def gaps(a, b):
    dx = max(0.0, max(a.x0, b.x0) - min(a.x1, b.x1))
    dy = max(0.0, max(a.y0, b.y0) - min(a.y1, b.y1))
    return dx, dy


def components(items, tol_x=14.0, tol_y=11.0):
    """Group (kind, rect) items whose boxes lie within the tolerances of each other."""
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    order = sorted(range(len(items)), key=lambda i: items[i][1].y0)
    for a_pos, a in enumerate(order):
        ra = items[a][1]
        for b in order[a_pos + 1:]:
            rb = items[b][1]
            if rb.y0 > ra.y1 + tol_y:
                break
            dx, dy = gaps(ra, rb)
            if dx <= tol_x and dy <= tol_y:
                parent[find(a)] = find(b)
    groups = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(items[i])
    result = []
    for members in groups.values():
        rect = union([r for _, r in members])
        area = sum(r.get_area() for kind, r in members if kind == "g" and min(r.width, r.height) >= 2.5)
        result.append({"rect": rect, "area": area, "graphic": any(k == "g" for k, _ in members)})
    return result


def select_figure(items, bottom):
    """Anchor on the component nearest the caption and add substantial nearby graphics.

    Text-only components join when they touch the figure, sit between the figure and its
    caption (sub-captions, legends), or form a short label row just above the figure.
    """
    comps = components(items)
    anchor = max(comps, key=lambda c: (c["rect"].y1, c["area"]))
    if not anchor["graphic"]:
        graphic = [c for c in comps if c["graphic"] and c["area"] > 150]
        if graphic:
            anchor = max(graphic, key=lambda c: c["rect"].y1)
    chosen = [anchor]
    box = pymupdf.Rect(anchor["rect"])
    changed = True
    while changed:
        changed = False
        for comp in comps:
            if any(comp is c for c in chosen):
                continue
            r = comp["rect"]
            dx, dy = gaps(r, box)
            inside_x = r.x0 >= box.x0 - 12 and r.x1 <= box.x1 + 12
            below = r.y0 >= box.y1 - 2 and r.y1 <= bottom + 1 and inside_x
            label_row = r.y1 <= box.y0 + 2 and dy <= 16 and inside_x and r.height < 40
            if ((comp["area"] >= 300 and dy <= 30 and dx <= 150) or (dx <= 14 and dy <= 11)
                    or below or label_row):
                chosen.append(comp)
                box |= r
                changed = True
    return box


AFFILIATION = re.compile(r"@|universit|institut|research|laborator|college|school of|department|"
                         r"google|deepmind|microsoft|facebook|meta ai|openai|nvidia|inc\.|corp", re.I)


def auto_box(doc, fig, body_size, headers):
    index, cap_line, cap_block = find_caption(doc, fig)
    page = doc[index]
    height = page.rect.height
    blocks, left, right, two_columns = layout(page, body_size)
    lines = list(page_lines(page))
    shapes = graphics(page)
    middle = (left + right) / 2
    text_width = right - left
    running = headers.get(index, [])
    head_bottom = max([r.y1 for r, number in running if r.y1 < height * 0.1 and not number], default=24)
    foot_top = min([r.y0 for r, number in running if r.y0 > height * 0.5 and not number], default=height - 24)
    other_caps = [block for text, line, block, size, first in lines
                  if first and CAPTION_LINE.match(text) and abs(block.y0 - cap_block.y0) + abs(block.x0 - cap_block.x0) > 1]
    restricted = False
    if two_columns and cap_block.x1 <= middle + 12:
        x0, x1 = left - 4, middle + 4
    elif two_columns and cap_block.x0 >= middle - 12:
        x0, x1 = middle - 4, right + 4
    else:
        x0, x1 = left - 6, right + 6
        narrow = cap_block.width < text_width * 0.62
        off_centre = abs((cap_block.x0 + cap_block.x1) / 2 - middle) > text_width * 0.15
        side_by_side = any(abs(b.y0 - cap_block.y0) < 70 and (b.x1 < cap_block.x0 + 5 or b.x0 > cap_block.x1 - 5)
                           for b in other_caps)
        if (narrow and off_centre) or (side_by_side and narrow):
            x0, x1 = cap_block.x0 - 14, cap_block.x1 + 14
            restricted = True

    def is_running(r):
        return any(r.intersects(h) for h, number in running)

    # On the first page the title, authors and affiliations sit above any figure.
    title_bottom = 0
    if index == 0:
        abstract = [line.y0 for text, line, block, size, first in lines if re.match(r"^\s*abstract\b", text, re.I)]
        limit = min(abstract) if abstract else height * 0.35
        for text, line, block, size, first in lines:
            if line.y1 < min(cap_line.y0 - 2, limit) and (
                    size >= body_size + 1.5 or (len(text) < 120 and AFFILIATION.search(text))):
                title_bottom = max(title_bottom, line.y1 + 1)

    def bounds(x0, x1):
        span_width = x1 - x0

        def span(r):
            overlap = min(r.x1, x1) - max(r.x0, x0)
            return overlap > 2 and overlap >= min(r.width, span_width) * 0.5
        if fig[0] == "T":
            top = cap_block.y1 + 1
            below = [b["rect"].y0 for b in blocks if b["rect"].y0 > cap_block.y1 + 2 and span(b["rect"])
                     and is_body(b, body_size, span_width, shapes)]
            below += [b.y0 for b in other_caps if b.y0 > cap_block.y1 + 2 and span(b)]
            bottom = min(below + [foot_top]) - 1
        else:
            bottom = cap_line.y0 - 0.5
            above = [b["rect"].y1 for b in blocks if b["rect"].y1 < cap_line.y0 - 1 and span(b["rect"])
                     and is_body(b, body_size, span_width, shapes) and not cap_block.intersects(b["rect"])]
            above += [b.y1 for b in other_caps if b.y1 < cap_line.y0 - 1 and span(b)]
            top = max(above + [head_bottom, title_bottom]) + 1
        return pymupdf.Rect(x0, top, x1, bottom)

    def collect(region):
        items = []
        for r in shapes:
            if not region.contains(centre(r)):
                continue
            if r.height < 2 and r.width > text_width * 0.6 and r.y1 < height * 0.15:
                continue  # rule under a running header
            items.append(("g", r))
        top_graphic = min([r.y0 for kind, r in items], default=region.y1)
        block_text = {}
        for text, line, block, size, first in lines:
            key = tuple(block)
            block_text[key] = (block_text.get(key, "") + " " + text).strip()
        for text, line, block, size, first in lines:
            c = centre(line)
            if region.contains(c) and not cap_block.contains(c) and not is_running(line):
                # A numbered section heading above the drawing is page text, not a label;
                # its number and title may be separate lines of one block.
                heading = block_text[tuple(block)]
                if line.y1 <= top_graphic + 1 and size >= body_size - 0.3 and len(heading) < 120 \
                        and re.match(r"^\d+(\.\d+)*\.?\s*[A-Z][a-z]", heading):
                    continue
                items.append(("t", line))
        return items

    region = bounds(x0, x1)
    items = collect(region)
    # A figure spanning both columns can carry a caption in one column only.  Switch to the
    # full width only when a wide graphic sits right above the caption and the other column
    # holds no body text next to it.
    if two_columns and not restricted and x1 - x0 < text_width * 0.75:
        wide = bounds(left - 6, right + 6)
        band = pymupdf.Rect(wide.x0, region.y0, wide.x1, region.y1)
        crossing = [r for r in shapes if band.contains(centre(r)) and r.height > 3
                    and r.x0 < middle - 15 and r.x1 > middle + 15 and r.width > text_width * 0.45]
        other = pymupdf.Rect(middle + 4, band.y0, right + 6, band.y1) if x1 < middle + 10 else \
            pymupdf.Rect(left - 6, band.y0, middle - 4, band.y1)
        prose = [b for b in blocks if is_body(b, body_size, text_width / 2, shapes) and b["rect"].intersects(other)]
        if crossing and not prose and wide.y0 <= region.y0 + 10:
            wide_items = collect(wide)
            if wide_items:
                region, items = wide, wide_items
    if not items:
        raise LookupError(f"no graphics near caption {fig} on page {index + 1}")
    box = union([r for _, r in items]) if fig[0] == "T" else select_figure(items, region.y1)
    # Labels clipped by a column edge: take in whole text lines that the box already touches.
    near = pymupdf.Rect(box.x0 - 8, box.y0, box.x1 + 8, box.y1)
    for text, line, block, size, first in lines:
        touches = line.intersects(box) or (len(text) <= 20 and line.intersects(near))
        if (touches and not cap_block.contains(centre(line)) and not is_running(line)
                and line.y0 >= region.y0 - 1 and line.y1 <= region.y1 + 1):
            box |= line
    # Clip vertically to the region; full-width or column figures may overhang a little.
    overhang = 0 if restricted else 40
    box = pymupdf.Rect(max(box.x0 - 3, region.x0 - overhang), max(box.y0 - 3, region.y0),
                       min(box.x1 + 3, region.x1 + overhang), min(box.y1 + 3, region.y1)) & page.rect
    return index, box


def opaque(image):
    image = image.convert("RGBA")
    background = Image.new("RGBA", image.size, "white")
    background.alpha_composite(image)
    return background.convert("RGB")


def svg_fidelity(xml, reference):
    width, height = reference.size
    scale = min(1, 900 / max(width, height))
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    rendered = Image.open(io.BytesIO(resvg_py.svg_to_bytes(svg_string=xml, width=size[0], height=size[1],
                                                           skip_system_fonts=True)))
    rendered = opaque(rendered)
    if rendered.size != size:
        rendered = rendered.resize(size, Image.Resampling.LANCZOS)
    a = np.asarray(rendered, dtype=np.int16)
    b = np.asarray(reference.convert("RGB").resize(size, Image.Resampling.LANCZOS), dtype=np.int16)
    diff = np.abs(a - b)
    return float(diff.mean()), float((diff.max(axis=2) > 70).mean())


def export(task):
    spec, meta = task
    pdf = PDF_DIR / f"{spec['paper']}.pdf"
    doc = pymupdf.open(pdf)
    body = body_font_size(doc)
    headers = running_lines(doc)
    if spec.get("crop"):
        page_no, *box = spec["crop"]
        index, rect = page_no - 1, pymupdf.Rect(box)
        method = "manual"
    else:
        index, rect = auto_box(doc, spec["fig"], body, headers)
        method = "auto"
    page = doc[index]
    rect &= page.rect
    images = [i for i in page.get_image_info() if rect.intersects(pymupdf.Rect(i["bbox"])) and i["width"] > 8]
    dominant = [i for i in images if (pymupdf.Rect(i["bbox"]) & rect).get_area() > rect.get_area() * 0.9]
    if dominant:
        native = dominant[0]
        zoom = native["width"] / pymupdf.Rect(native["bbox"]).width
        zoom = min(max(zoom, 150 / 72), DPI * 1.6 / 72)
    else:
        zoom = DPI / 72
    zoom = min(zoom, MAX_SIDE / max(rect.width, rect.height))
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=rect, alpha=False)
    sid = spec["id"]
    png_path = OUT / f"{sid}.png"
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    image.save(png_path, optimize=True)
    thumb = image.copy()
    thumb.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.Resampling.LANCZOS)
    thumb.save(THUMBS / f"{sid}.webp", quality=88, method=6)
    crop_doc = pymupdf.open()
    crop_page = crop_doc.new_page(width=rect.width, height=rect.height)
    crop_page.show_pdf_page(crop_page.rect, doc, index, clip=rect)
    crop_doc.set_metadata({"title": f"{spec['name']} — {spec['label']}",
                           "author": ", ".join(meta["authors"]),
                           "subject": f"{meta['title']} (arXiv:{meta['arxiv']}{meta['version']}), {spec['label']}; figure crop only"})
    pdf_path = OUT / f"{sid}.pdf"
    crop_doc.save(pdf_path, garbage=4, deflate=True)
    # A clipped page still carries the whole source page's fonts and images.  Keep the
    # vector PDF only when it is compact; bitmap figures gain nothing over the PNG.
    keep_pdf = not dominant and pdf_path.stat().st_size <= MAX_PDF_BYTES
    if not keep_pdf:
        pdf_path.unlink()
    svg_path = OUT / f"{sid}.svg"
    svg_kind = ""
    fidelity = None
    if not dominant:
        page.set_cropbox(rect)
        xml = page.get_svg_image(text_as_path=True)
        page.set_cropbox(page.mediabox)
        if len(xml) <= MAX_SVG_BYTES:
            mean, strong = svg_fidelity(xml, image)
            fidelity = {"mean_abs_diff": round(mean, 3), "strong_pixels": round(strong, 5)}
            if mean <= 4.0 and strong <= 0.02:
                svg_path.write_text(xml, encoding="utf-8")
                svg_kind = "mixed" if re.search(r"<(?:\w+:)?image\b", xml) else "vector"
    if not svg_kind and svg_path.exists():
        svg_path.unlink()
    files = {"png": png_path}
    if keep_pdf:
        files["pdf"] = pdf_path
    if svg_kind:
        files["svg"] = svg_path
    return {
        "id": sid, "page": index + 1, "box": [round(v, 2) for v in rect], "method": method,
        "width": pix.width, "height": pix.height, "dpi": round(zoom * 72, 1),
        "native_bitmap": bool(dominant), "svg_kind": svg_kind, "svg_fidelity": fidelity,
        "hashes": {k: sha256(p) for k, p in files.items()},
        "bytes": {k: p.stat().st_size for k, p in files.items()},
    }


def label(fig):
    return ("Table " if fig[0] == "T" else "Fig. ") + fig[1:]


def contact_sheet(rows, name):
    QA_DIR.mkdir(parents=True, exist_ok=True)
    cols, cell = 4, (460, 330)
    sheet = Image.new("RGB", (cols * cell[0], ((len(rows) + cols - 1) // cols) * (cell[1] + 24)), "#cfd5dc")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
    except OSError:
        font = None
    for i, (sid, title) in enumerate(rows):
        x, y = (i % cols) * cell[0], (i // cols) * (cell[1] + 24)
        try:
            im = Image.open(OUT / f"{sid}.png").convert("RGB")
            im.thumbnail((cell[0] - 10, cell[1] - 6))
            sheet.paste(im, (x + (cell[0] - im.width) // 2, y + 24 + (cell[1] - im.height) // 2))
        except OSError:
            pass
        draw.text((x + 5, y + 4), f"{sid}  {title}"[:58], fill="black", font=font)
    path = QA_DIR / name
    sheet.save(path, quality=86)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="figure ids or paper keys to (re)build")
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    figures = read_json(HERE / "figures.json")
    papers = read_json(HERE / "papers.json")
    metadata = read_json(HERE / "arxiv_metadata.json")
    OUT.mkdir(parents=True, exist_ok=True)
    THUMBS.mkdir(parents=True, exist_ok=True)
    for spec in figures:
        spec["id"] = f"p-{spec['paper']}-{spec['fig'].lower().replace('.', '-')}"
        spec["label"] = label(spec["fig"])
    selected = [s for s in figures if not args.only or s["id"] in args.only or s["paper"] in args.only]
    results, failures = {}, []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {s["id"]: pool.submit(export, (s, metadata[s["paper"]])) for s in selected}
        for sid, future in futures.items():
            try:
                results[sid] = future.result()
                print("ok", sid, results[sid]["page"], results[sid]["box"], results[sid]["svg_kind"] or "-", flush=True)
            except Exception as error:  # report and continue; fix with a manual crop
                failures.append((sid, str(error)))
                print("FAIL", sid, error, flush=True)
    previous = read_json(HERE / "extracted.json", {})
    previous.update(results)
    write_json(HERE / "extracted.json", dict(sorted(previous.items())))
    rows = [(s["id"], s["name"]) for s in selected if s["id"] in results]
    for start in range(0, len(rows), 24):
        print("sheet", contact_sheet(rows[start:start + 24], f"sheet-{start // 24 + 1:02d}.jpg"))
    if failures:
        print("failures:", json.dumps(failures, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
