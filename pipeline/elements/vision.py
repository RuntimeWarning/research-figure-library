#!/usr/bin/env python3
"""Computer-vision elements for model figures.

Two kinds of pieces, all released under CC0 1.0:

* photo pieces built from CC0 / public-domain photos (Wikimedia Commons and the
  scikit-image sample data): the input image itself, patch grids, MAE masking,
  noise steps, augmentations, edge maps, superpixels, GrabCut masks and cut-outs,
  detection boxes, pose keypoints, and photos laid on isometric planes or stacked
  as video frames;
* isometric 3-D vision schematics drawn with ``style.py``: camera frustums,
  multi-view rigs, NeRF ray sampling, voxels, 3-D boxes, BEV grids,
  Gaussian splats and tri-planes.

Outputs go to ``dist/assets/vision/`` and ``pipeline/manifests/vision.json``.
Photos are downloaded once into ``.cache/web/cv-photos``.
"""
from __future__ import annotations

import base64
import io
import math
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import cv2
import numpy as np
import resvg_py
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from skimage import data as skdata
from skimage import segmentation

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from common import ASSETS, CACHE, DIST, MANIFESTS, fetch, sha256, write_json  # noqa: E402
import style as st  # noqa: E402
from style import PALETTES as P  # noqa: E402

OUT = ASSETS / "vision"
PHOTO_CACHE = CACHE / "web" / "cv-photos"
SIDE = 768          # photo pieces
PNG_SIDE = 1024     # rendered SVG schematics
PHOTO_PNG_SIDE = 880  # rendered SVG pieces that embed a photo
THUMB_SIDE = 420
INPUT, TASK, THREE_D = "图像输入与预处理", "检测、分割与关键点", "三维视觉"
PAPER = st.Palette("paper", "白色", "white", "#eef1f6", "#aeb8c6", "#d6dce5", "#ffffff", "#ffffff", "#5d6d84")

COMMONS = {
    # key: (file name, author, licence, 中文名, crop box in the 1920 px download)
    "cat": ("Tabby cat with blue eyes-3336579.jpg", "AdinaVoicu", "CC0", "猫", (0, 200, 1920, 2120)),
    "dog": ("Dog resting on the grass.jpg", "Joselodos", "CC0", "狗", (340, 0, 1620, 1280)),
    "bird": ("Eisvogel kingfisher.jpg", "Frank-2.0", "CC0", "翠鸟", (180, 0, 1452, 1272)),
    "car": ("Auto in car sharing a Livorno.jpg", "Marcxosm", "CC0", "汽车", (90, 0, 1527, 1437)),
    "street": ("Traffic and pedestrians on Calle Velásquez near Catedral San Nicolás de Bari, Barcelona, Venezuela.jpg",
               "Wilfredor", "CC0", "街景", None),
    "road": ("Streets in Les Rivières, Quebec City (16).jpg", "Wilfredor", "CC0", "道路", None),
    "room": ("Living room (Unsplash).jpg", "Jarosław Ceborski", "CC0", "室内", None),
    "aerial": ("Seattle City Aerial View Sounds Peugeot.jpg", "Yourusernamewillbepublic2", "CC0", "城市航拍", (0, 330, 1280, 960)),
    "pose": ("Walking Rugby.jpg", "Back ache", "CC0", "运动人物", (150, 150, 1050, 1050)),
}
SKIMAGE = {
    # key: (loader, description, licence, 中文名)
    "astronaut": ("astronaut", "NASA photograph of Eileen Collins", "public domain", "宇航员"),
    "coffee": ("coffee", "photo by Rachel Michetti", "CC0", "咖啡杯"),
    "camera": ("camera", "photo by Lav Varshney", "CC0", "摄影师（灰度）"),
    "retina": ("retina", "fundus photograph by Mikael Häggström", "CC0", "眼底图像"),
}
SKIMAGE_DOCS = "https://scikit-image.org/docs/stable/api/skimage.data.html"

SPECS = []          # (id, category, zh, en, tags, maker, photo key or None)


def add(eid, category, zh, en, tags, maker, photo=None):
    SPECS.append((eid, category, zh, en, tags, maker, photo))


# ------------------------------------------------------------------ photos
_PHOTOS = {}


def photo(key) -> Image.Image:
    """The base photo, cropped; cached per run."""
    if key in _PHOTOS:
        return _PHOTOS[key]
    if key in COMMONS:
        name, *_, crop = COMMONS[key]
        url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(name)}?width=1920"
        data = fetch(url, PHOTO_CACHE / f"{key}.jpg", timeout=180)
        image = Image.open(io.BytesIO(data)).convert("RGB")
        if crop:
            image = image.crop(crop)
    else:
        image = Image.fromarray(getattr(skdata, SKIMAGE[key][0])()).convert("RGB")
    _PHOTOS[key] = image
    return image


def credit(key):
    if key in COMMONS:
        name, author, licence, *_ = COMMONS[key]
        return (f"Based on a photo by {author}, Wikimedia Commons ({licence}): "
                f"https://commons.wikimedia.org/wiki/File:{quote(name.replace(' ', '_'))}. Processed by Figure Atlas, CC0.")
    _, description, licence, _ = SKIMAGE[key]
    return f"Based on the scikit-image sample image ({description}, {licence}). Processed by Figure Atlas, CC0."


def upstream(key):
    if key in COMMONS:
        return f"https://commons.wikimedia.org/wiki/File:{quote(COMMONS[key][0].replace(' ', '_'))}"
    return f"{SKIMAGE_DOCS}#skimage.data.{SKIMAGE[key][0]}"


def fit(image, side=SIDE):
    image = image.copy()
    image.thumbnail((side, side), Image.Resampling.LANCZOS)
    return image


def square(key, side=SIDE):
    image = photo(key)
    s = min(image.size)
    x0, y0 = (image.width - s) // 2, (image.height - s) // 2
    return image.crop((x0, y0, x0 + s, y0 + s)).resize((side, side), Image.Resampling.LANCZOS)


def wide(key, width=1024):
    image = photo(key)
    return image.resize((width, round(image.height * width / image.width)), Image.Resampling.LANCZOS)


# ------------------------------------------------------------------ photo operations
def grid_overlay(image, n, colour=(255, 255, 255), width=3):
    out = image.copy()
    d = ImageDraw.Draw(out)
    for i in range(1, n):
        x, y = round(i * out.width / n), round(i * out.height / n)
        d.line([(x, 0), (x, out.height)], fill=colour, width=width)
        d.line([(0, y), (out.width, y)], fill=colour, width=width)
    return out


def tiles(image, n):
    w, h = image.width // n, image.height // n
    return [[image.crop((c * w, r * h, (c + 1) * w, (r + 1) * h)) for c in range(n)] for r in range(n)]


def exploded(image, n, gap=14, masked=None, keep_only=False):
    """Patches pulled apart; ``masked`` cells are greyed out (MAE) or left empty."""
    parts = tiles(image, n)
    w, h = parts[0][0].size
    out = Image.new("RGBA", (n * w + (n - 1) * gap, n * h + (n - 1) * gap), (0, 0, 0, 0))
    for r in range(n):
        for c in range(n):
            x, y = c * (w + gap), r * (h + gap)
            if masked and (r, c) in masked:
                if not keep_only:
                    out.paste(Image.new("RGBA", (w, h), (214, 219, 228, 255)), (x, y))
            else:
                out.paste(parts[r][c].convert("RGBA"), (x, y))
    return out


def mae_cells(n, ratio, seed):
    rng = np.random.default_rng(seed)
    cells = [(r, c) for r in range(n) for c in range(n)]
    pick = rng.choice(len(cells), size=round(len(cells) * ratio), replace=False)
    return {cells[i] for i in pick}


def patch_row(image, n=3, gap=12):
    parts = [p for row in tiles(image, n) for p in row]
    w, h = parts[0].size
    out = Image.new("RGBA", (len(parts) * w + (len(parts) - 1) * gap, h), (0, 0, 0, 0))
    for i, p in enumerate(parts):
        out.paste(p.convert("RGBA"), (i * (w + gap), 0))
    return out


def noisy(image, alpha_bar, seed=3):
    x = np.asarray(image, dtype=np.float32) / 127.5 - 1
    eps = np.random.default_rng(seed).standard_normal(x.shape).astype(np.float32)
    xt = math.sqrt(alpha_bar) * x + math.sqrt(1 - alpha_bar) * eps
    return Image.fromarray(np.clip((xt + 1) * 127.5, 0, 255).astype(np.uint8))


def strip(images, gap=16):
    w, h = images[0].size
    out = Image.new("RGBA", (len(images) * w + (len(images) - 1) * gap, h), (0, 0, 0, 0))
    for i, im in enumerate(images):
        out.paste(im.convert("RGBA"), (i * (w + gap), 0))
    return out


def on_white(image):
    return Image.alpha_composite(Image.new("RGBA", image.size, (255, 255, 255, 255)), image.convert("RGBA")).convert("RGB")


def lowres(image, k):
    return image.resize((k, k), Image.Resampling.BILINEAR).resize(image.size, Image.Resampling.NEAREST)


def canny(image):
    grey = cv2.GaussianBlur(np.asarray(image.convert("L")), (5, 5), 1.4)
    return Image.fromarray(cv2.Canny(grey, 60, 150)).convert("RGB")


def channel(image, index):
    arr = np.zeros_like(np.asarray(image))
    arr[..., index] = np.asarray(image)[..., index]
    return Image.fromarray(arr)


def spectrum(image):
    grey = np.asarray(image.convert("L"), dtype=np.float32)
    mag = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(grey))))
    mag = (mag - mag.min()) / (mag.max() - mag.min())
    return Image.fromarray(cv2.applyColorMap((mag * 255).astype(np.uint8), cv2.COLORMAP_MAGMA)[..., ::-1])


def superpixels(image, n=180):
    arr = np.asarray(image)
    labels = segmentation.slic(arr, n_segments=n, compactness=14, start_label=1)
    marked = segmentation.mark_boundaries(arr, labels, color=(1, 0.86, 0.2), mode="thick")
    return Image.fromarray((marked * 255).astype(np.uint8))


def superpixel_mean(image, n=180):
    arr = np.asarray(image)
    labels = segmentation.slic(arr, n_segments=n, compactness=14, start_label=1)
    out = np.zeros_like(arr)
    for lab in np.unique(labels):
        out[labels == lab] = arr[labels == lab].mean(axis=0)
    marked = segmentation.mark_boundaries(out, labels, color=(1, 1, 1))
    return Image.fromarray((marked * 255).astype(np.uint8))


def grabcut(image, rect):
    """Foreground mask (uint8 0/255) from a rough box, cleaned and limited to the largest component."""
    bgr = np.asarray(image)[..., ::-1].copy()
    mask = np.zeros(bgr.shape[:2], np.uint8)
    bg, fg = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    x0, y0, x1, y1 = rect
    cv2.grabCut(bgr, mask, (x0, y0, x1 - x0, y1 - y0), bg, fg, 6, cv2.GC_INIT_WITH_RECT)
    m = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    m = cv2.morphologyEx(cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel), cv2.MORPH_CLOSE, kernel)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(m)
    if count > 1:
        biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        m = np.where(labels == biggest, 255, 0).astype(np.uint8)
    holes = 255 - m
    count, labels, stats, _ = cv2.connectedComponentsWithStats(holes)
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        if x > 0 and y > 0 and x + w < m.shape[1] and y + h < m.shape[0] and area < 0.002 * m.size:
            m[labels == i] = 255   # close small gaps in fur or feathers, keep background seen between limbs
    return m


def overlay_mask(image, mask, colour, alpha=0.5):
    arr = np.asarray(image).astype(np.float32)
    tint = np.array(colour, np.float32)
    sel = mask > 127
    arr[sel] = arr[sel] * (1 - alpha) + tint * alpha
    out = arr.clip(0, 255).astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(out, contours, -1, tuple(int(c) for c in colour), 4, lineType=cv2.LINE_AA)
    return Image.fromarray(out)


def cutout(image, mask, margin=12):
    alpha = Image.fromarray(cv2.GaussianBlur(mask, (5, 5), 1.2))
    out = image.convert("RGBA")
    out.putalpha(alpha)
    ys, xs = np.nonzero(mask)
    box = (max(0, xs.min() - margin), max(0, ys.min() - margin), min(image.width, xs.max() + margin),
           min(image.height, ys.max() + margin))
    return out.crop(box)


def boxes(image, items, width=4):
    """Detection boxes: list of (box, colour); light fill and a corner tab without text."""
    base = image.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for (x0, y0, x1, y1), colour in items:
        d.rectangle((x0, y0, x1, y1), fill=colour + (34,))
        d.rectangle((x0, y0, x1, y1), outline=colour + (255,), width=width)
        d.rectangle((x0, y0 - 14, x0 + min(46, x1 - x0), y0), fill=colour + (255,))
    return Image.alpha_composite(base, layer).convert("RGB")


def heat_overlay(image, heat, alpha=0.5):
    heat = (heat - heat.min()) / (heat.max() - heat.min() + 1e-6)
    colour = cv2.applyColorMap((heat * 255).astype(np.uint8), cv2.COLORMAP_JET)[..., ::-1]
    out = np.asarray(image).astype(np.float32) * (1 - alpha) + colour.astype(np.float32) * alpha
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))


def gaussian_heat(size, centres, sigma):
    h, w = size
    yy, xx = np.mgrid[0:h, 0:w]
    heat = np.zeros((h, w), np.float32)
    for (cx, cy), s in zip(centres, sigma):
        heat += np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * s * s))
    return heat


# COCO-17 keypoints in the original 1125 x 1050 photo (two players)
POSE_PEOPLE = [
    {"nose": (372, 290), "left_eye": (385, 273), "right_eye": (361, 273), "left_ear": (407, 279), "right_ear": (349, 281),
     "left_shoulder": (440, 330), "right_shoulder": (338, 332), "left_elbow": (520, 422), "right_elbow": (322, 440),
     "left_wrist": (493, 515), "right_wrist": (318, 505), "left_hip": (508, 553), "right_hip": (392, 545),
     "left_knee": (487, 668), "right_knee": (386, 680), "left_ankle": (500, 790), "right_ankle": (420, 785)},
    {"nose": (712, 222), "left_ear": (738, 210), "left_shoulder": (684, 305), "right_shoulder": (812, 292),
     "left_elbow": (628, 356), "right_elbow": (712, 418), "left_wrist": (568, 386), "right_wrist": (657, 448),
     "left_hip": (800, 545), "right_hip": (902, 536), "left_knee": (832, 668), "right_knee": (900, 690),
     "left_ankle": (838, 860), "right_ankle": (966, 805)},
]
LIMBS = [("left_ankle", "left_knee", "l"), ("left_knee", "left_hip", "l"), ("right_ankle", "right_knee", "r"),
         ("right_knee", "right_hip", "r"), ("left_hip", "right_hip", "c"), ("left_shoulder", "left_hip", "l"),
         ("right_shoulder", "right_hip", "r"), ("left_shoulder", "right_shoulder", "c"), ("left_shoulder", "left_elbow", "l"),
         ("right_shoulder", "right_elbow", "r"), ("left_elbow", "left_wrist", "l"), ("right_elbow", "right_wrist", "r"),
         ("left_eye", "right_eye", "c"), ("nose", "left_eye", "l"), ("nose", "right_eye", "r"), ("left_eye", "left_ear", "l"),
         ("right_eye", "right_ear", "r")]
SIDE_COLOUR = {"l": (255, 146, 43), "r": (51, 154, 240), "c": (64, 192, 87)}


def pose_points(scale, offset):
    ox, oy = offset
    return [{k: ((x - ox) * scale, (y - oy) * scale) for k, (x, y) in person.items()} for person in POSE_PEOPLE]


def draw_skeleton(image, people, width=7, radius=8, background=None):
    out = (background or image).convert("RGBA")
    d = ImageDraw.Draw(out)
    for person in people:
        for a, b, side in LIMBS:
            if a in person and b in person:
                d.line([person[a], person[b]], fill=SIDE_COLOUR[side] + (255,), width=width)
        for x, y in person.values():
            d.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(255, 255, 255, 255), outline=(40, 40, 40, 255),
                      width=3)
    return out


def flow_wheel(size=640):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = cy = (size - 1) / 2
    dx, dy = (xx - cx) / cx, (yy - cy) / cy
    rad = np.sqrt(dx * dx + dy * dy)
    hue = (np.arctan2(-dy, -dx) / np.pi + 1) / 2 * 179
    hsv = np.stack([hue, np.clip(rad, 0, 1) * 255, np.full_like(hue, 255)], -1).astype(np.uint8)
    rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    alpha = np.clip((1 - rad) * size / 3, 0, 1) * 255
    return Image.fromarray(np.dstack([rgb, alpha.astype(np.uint8)]), "RGBA")


def flow_field(size=640):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    u = np.sin(2 * np.pi * yy) * 0.6 + 0.4 * (xx - 0.5)
    v = np.cos(2 * np.pi * xx) * 0.6 - 0.3 * (yy - 0.5)
    ang = (np.arctan2(-v, -u) / np.pi + 1) / 2 * 179
    mag = np.sqrt(u * u + v * v)
    hsv = np.stack([ang, np.clip(mag / mag.max(), 0, 1) * 255, np.full_like(ang, 255)], -1).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB))


# ------------------------------------------------------------------ photos on isometric planes (SVG)
def data_uri(image, side=560):
    image = image.convert("RGB")
    image.thumbnail((side, side), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=86)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def photo_face(image, w, h, x=0.0, y=0.0, z=0.0, grid=0, stroke=PAPER.ink):
    """SVG fragment placing ``image`` on the front face (x..x+w, y..y+h) of plane z."""
    o = st.proj((x, y + h, z))
    a = st.proj((x + w, y + h, z))
    b = st.proj((x, y, z))
    ax, ay = (a[0] - o[0]) / image.width, (a[1] - o[1]) / image.width
    bx, by = (b[0] - o[0]) / image.height, (b[1] - o[1]) / image.height
    uri = data_uri(image)
    frags = [f'<image width="{image.width}" height="{image.height}" preserveAspectRatio="none" href="{uri}" '
             f'transform="matrix({ax:.6f} {ay:.6f} {bx:.6f} {by:.6f} {o[0]:.4f} {o[1]:.4f})"/>']
    for i in range(1, grid):
        frags.append(st.line3((x + w * i / grid, y, z), (x + w * i / grid, y + h, z), "#ffffff", 0.045))
        frags.append(st.line3((x, y + h * i / grid, z), (x + w, y + h * i / grid, z), "#ffffff", 0.045))
    face = [st.proj(p) for p in [(x, y, z), (x + w, y, z), (x + w, y + h, z), (x, y + h, z)]]
    frags.append(st.poly(face, "none", f' stroke="{stroke}" stroke-width="0.035"'))
    return "".join(frags)


def photo_slab(scene, image, w, x=0.0, y=0.0, z=0.0, thick=0.16, grid=0, depth_bias=0.0):
    h = w * image.height / image.width
    st.extrude(scene, st.rect(w, h), z, thick, PAPER, origin=(x, y), front_svg=photo_face(image, w, h, x, y, z, grid),
               depth_bias=depth_bias)
    return h


def iso_photo(image, grid=0):
    def make(title):
        s = st.Scene()
        photo_slab(s, image, 4.0, grid=grid)
        return s.to_svg(title)
    return make


def iso_frames(images, step=(0.0, 0.0, 0.9)):
    def make(title):
        s = st.Scene()
        for i, image in enumerate(images):
            photo_slab(s, image, 4.0, x=i * step[0], y=i * step[1], z=i * step[2])
        return s.to_svg(title)
    return make


def iso_pyramid(image, widths=(4.0, 2.8, 1.9), gap=1.2):
    def make(title):
        s = st.Scene()
        x = 0.0
        for w in widths:
            h = w * image.height / image.width
            photo_slab(s, image, w, x=x, y=(widths[0] * image.height / image.width - h) / 2)
            x += w + gap
        return s.to_svg(title)
    return make


def iso_channels(image):
    def make(title):
        s = st.Scene()
        for i, idx in enumerate((0, 1, 2)):
            photo_slab(s, channel(image, idx), 4.0, x=i * 0.45, y=i * 0.45, z=i * 1.0)
        return s.to_svg(title)
    return make


# ------------------------------------------------------------------ isometric 3-D schematics
def _lines(scene, segs, colour, width=0.05, dash=None, depth=None, opacity=1.0):
    pts3 = [p for seg in segs for p in seg]
    svg = "".join(st.line3(a, b, colour, width, dash, opacity=opacity) for a, b in segs)
    scene.add(st.depth_of(pts3) if depth is None else depth, f"<g>{svg}</g>", [st.proj(p) for p in pts3])


def _dot(scene, p, r, fill, stroke="#ffffff", depth_bias=0.0):
    sx, sy = st.proj(p)
    scene.add(st.dot(p, st.D) + depth_bias, f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="{r}" fill="{fill}" stroke="{stroke}" '
              f'stroke-width="{r * 0.35:.3f}"/>', [(sx - r, sy - r), (sx + r, sy + r)])


def _box_edges(c, size):
    (cx, cy, cz), (w, h, d) = c, size
    xs, ys, zs = (cx - w / 2, cx + w / 2), (cy - h / 2, cy + h / 2), (cz - d / 2, cz + d / 2)
    corners = {(i, j, k): (xs[i], ys[j], zs[k]) for i in (0, 1) for j in (0, 1) for k in (0, 1)}
    edges = []
    for a in corners:
        for axis in range(3):
            if a[axis] == 0:
                b = list(a)
                b[axis] = 1
                edges.append((corners[a], corners[tuple(b)]))
    return edges


def camera_body(scene, pal, apex, back=0.55, size=0.5):
    """Small camera block behind the frustum apex (towards -z)."""
    x, y, z = apex
    st.cube(scene, pal, 1, 1, 1, x=x - size / 2, y=y - size / 2, z=z - back, cell=size)


def frustum(scene, pal, apex, plane_z, w, h, far=None, centre=None, colour=None):
    cx, cy = centre or (apex[0], apex[1])
    corners = [(cx - w / 2, cy - h / 2, plane_z), (cx + w / 2, cy - h / 2, plane_z), (cx + w / 2, cy + h / 2, plane_z),
               (cx - w / 2, cy + h / 2, plane_z)]
    colour = colour or pal.ink
    _lines(scene, [(apex, c) for c in corners], colour, 0.04)
    _lines(scene, list(zip(corners, corners[1:] + corners[:1])), colour, 0.05)
    face = [st.proj(c) for c in corners]
    scene.add(st.depth_of(corners) + 0.01, st.poly(face, pal.cell, ' fill-opacity="0.55"'), face)
    if far:
        k = (far - apex[2]) / (plane_z - apex[2])
        fc = [(apex[0] + (c[0] - apex[0]) * k, apex[1] + (c[1] - apex[1]) * k, far) for c in corners]
        _lines(scene, [(c, f) for c, f in zip(corners, fc)], colour, 0.03, dash="0.12 0.1", opacity=0.7)
        _lines(scene, list(zip(fc, fc[1:] + fc[:1])), colour, 0.03, dash="0.12 0.1", opacity=0.7)


def b_frustum(title, pal, image=None):
    p = P[pal]
    s = st.Scene()
    apex = (0.0, 0.0, -2.2)
    camera_body(s, P["slate"], apex)
    frustum(s, p, apex, 0.6, 2.6, 2.0, far=3.0)
    if image is not None:
        s.add(-0.5, photo_face(image, 2.6, 2.0, -1.3, -1.0, 0.6), [])
    return s.to_svg(title)


def b_multiview(title, pal, n=6):
    p = P[pal]
    s = st.Scene()
    st.cube(s, P["orange"], 2, 2, 2, x=-0.9, y=-0.9, z=-0.9, cell=0.9)
    for i in range(n):
        a = 2 * math.pi * i / n + 0.35
        apex = (4.2 * math.cos(a), 0.8, 4.2 * math.sin(a))
        target = (0.0, 0.0, 0.0)
        dx, dy, dz = (target[k] - apex[k] for k in range(3))
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        f = (dx / length, dy / length, dz / length)
        right = (f[2], 0.0, -f[0])
        rn = math.hypot(right[0], right[2])
        right = (right[0] / rn, 0.0, right[2] / rn)
        up = (f[1] * right[2] - f[2] * right[1], f[2] * right[0] - f[0] * right[2], f[0] * right[1] - f[1] * right[0])
        dist, hw, hh = 1.1, 0.5, 0.38
        c = tuple(apex[k] + f[k] * dist for k in range(3))
        quad = [tuple(c[k] + sx * hw * right[k] + sy * hh * up[k] for k in range(3)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        _lines(s, [(apex, q) for q in quad], p.ink, 0.035)
        face = [st.proj(q) for q in quad]
        s.add(st.depth_of(quad), st.poly(face, p.cell, f' stroke="{p.ink}" stroke-width="0.04" fill-opacity="0.85"'), face)
        _dot(s, apex, 0.11, p.base)
    return s.to_svg(title)


def b_nerf(title, pal):
    p = P[pal]
    s = st.Scene()
    apex = (-4.6, 0.6, -1.6)
    camera_body(s, P["slate"], apex)
    frustum(s, p, apex, -0.9, 1.1, 0.85)
    _lines(s, _box_edges((1.6, 0.3, 1.8), (3.2, 3.0, 3.2)), P["slate"].hi, 0.035, dash="0.1 0.08")
    blob = [(1.6 + 0.9 * math.cos(a), 0.3 + 0.9 * math.sin(a) * 0.9, 1.8) for a in np.linspace(0, 2 * math.pi, 40)]
    face = [st.proj(q) for q in blob]
    s.add(st.depth_of(blob) + 3, st.poly(face, P["orange"].cell, ' fill-opacity="0.55"'), face)
    for k, target in enumerate([(1.6, 1.2, 2.2), (1.6, 0.3, 1.8), (1.4, -0.7, 1.4)]):
        d = [target[i] - apex[i] for i in range(3)]
        end = tuple(apex[i] + d[i] * 1.55 for i in range(3))
        _lines(s, [(apex, end)], p.ink, 0.04, depth=-50 + k)
        for j, t in enumerate(np.linspace(0.78, 1.42, 9)):
            q = tuple(apex[i] + d[i] * t for i in range(3))
            dens = math.exp(-((t - 1.05) / 0.16) ** 2)
            _dot(s, q, 0.085, st.mix(P["orange"].cell, P["coral"].base, dens), depth_bias=-60 + k)
    return s.to_svg(title)


def b_voxels(title, pal, seed=0):
    p = P[pal]
    rng = np.random.default_rng(seed)
    s = st.Scene()
    n = 6
    c = (n - 1) / 2
    for i in range(n):
        for j in range(n):
            for k in range(n):
                r = math.sqrt((i - c) ** 2 + ((j - c) * 1.25) ** 2 + (k - c) ** 2)
                if r < 2.75 + 0.35 * rng.random():
                    shade = j / (n - 1)
                    colours = {(0, 0): p.ramp(0.15 + 0.6 * shade)}
                    st.cube(s, p, 1, 1, 1, x=i, y=j, z=k, cell=1.0, colours=colours,
                            top_colours={(0, 0): p.ramp(0.05 + 0.5 * shade)}, left_colours={(0, 0): p.ramp(0.35 + 0.6 * shade)})
    return s.to_svg(title)


def b_bbox3d(title, pal, seed=1):
    p = P[pal]
    g = np.random.default_rng(seed)
    s = st.Scene()
    pts = []
    for _ in range(520):
        x, y, z = g.uniform(-1, 1, 3)
        if (x / 1) ** 2 + (y / 0.55) ** 2 + (z / 1) ** 2 < 1 or (abs(x) < 0.55 and 0.2 < y < 0.75 and abs(z) < 0.6):
            pts.append((x * 2.1, y * 1.0, z * 1.0))
    ground = [(g.uniform(-3.8, 3.8), -0.62, g.uniform(-2.4, 2.4)) for _ in range(260)]
    body = []
    for q in sorted(ground + pts, key=lambda q: -st.dot(q, st.D)):
        sx, sy = st.proj(q)
        fill = P["slate"].hi if q[1] < -0.6 else p.ramp(0.3 + 0.5 * (q[1] + 0.6))
        body.append(f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="0.05" fill="{fill}"/>')
    s.add(0, "<g>" + "".join(body) + "</g>", [st.proj(q) for q in ground + pts])
    _lines(s, _box_edges((0.0, 0.0, 0.0), (4.6, 1.3, 2.3)), P["coral"].base, 0.06, depth=-20)
    return s.to_svg(title)


def b_bev(title, pal):
    p = P[pal]
    s = st.Scene()
    n, cell = 12, 0.6
    span = n * cell
    for (k, c), quad in st.face_grid_top(0, span, 0, 0, span, n, n, margin=0.02, gap=0.04).items():
        s.add(10, st.poly(quad, P["slate"].cell), quad)
    cars = [(5.5, 5.5, "ego"), (2.2, 6.4, None), (8.3, 4.6, None), (5.7, 1.4, None), (9.4, 8.6, None), (2.6, 2.4, None)]
    for x, z, kind in cars:
        pal_car = P["coral"] if kind else p
        st.cube(s, pal_car, 1, 1, 2, x=x - 0.35, y=0.0, z=z - 0.7, cell=0.7)
    return s.to_svg(title)


def b_splats(title, pals, seed=4, n=90):
    rng = np.random.default_rng(seed)
    s = st.Scene()
    items = []
    for _ in range(n):
        u, v = rng.uniform(0, 2 * math.pi), rng.uniform(-1, 1)
        r = 1.9 * (1 + 0.15 * rng.standard_normal())
        q = (r * math.sqrt(1 - v * v) * math.cos(u) * 1.2, r * v * 0.8 + 0.2, r * math.sqrt(1 - v * v) * math.sin(u))
        items.append((q, rng.uniform(0.18, 0.55), rng.uniform(0.07, 0.22), rng.uniform(0, 180), pals[rng.integers(len(pals))],
                      rng.uniform(0.25, 0.85)))
    for q, a, b, ang, pal, t in items:
        sx, sy = st.proj(q)
        colour = P[pal].ramp(t)
        s.add(st.dot(q, st.D), f'<ellipse cx="{sx:.3f}" cy="{sy:.3f}" rx="{a:.3f}" ry="{b:.3f}" fill="{colour}" '
              f'fill-opacity="0.62" transform="rotate({ang:.1f} {sx:.3f} {sy:.3f})"/>',
              [(sx - a, sy - a), (sx + a, sy + a)])
    return s.to_svg(title)


def b_triplane(title, pals=("blue", "teal", "orange"), n=5):
    s = st.Scene()
    size = 4.0
    xy, xz, yz = (P[k] for k in pals)
    for key, quad in st.cell_quads(0, 0, size, size, n, n, size).items():
        s.add(st.dot((size / 2, size / 2, size), st.D) + 5, st.poly(quad, xy.cell if (key[0] + key[1]) % 3 else xy.hi), quad)
    back = [st.proj(p) for p in [(0, 0, size), (size, 0, size), (size, size, size), (0, size, size)]]
    s.add(st.dot((size / 2, size / 2, size), st.D) + 5.01, st.poly(back, xy.base), back)
    for key, quad in st.face_grid_top(0, size, 0, 0, size, n, n).items():
        s.add(st.dot((size / 2, 0, size / 2), st.D) + 4, st.poly(quad, xz.cell if (key[0] * 2 + key[1]) % 3 else xz.hi), quad)
    floor = [st.proj(p) for p in [(0, 0, 0), (size, 0, 0), (size, 0, size), (0, 0, size)]]
    s.add(st.dot((size / 2, 0, size / 2), st.D) + 4.01, st.poly(floor, xz.base), floor)
    for key, quad in st.face_grid_left(size, 0, size, 0, size, n, n).items():
        s.add(st.dot((size, size / 2, size / 2), st.D) + 3, st.poly(quad, yz.cell if (key[0] + 2 * key[1]) % 3 else yz.hi), quad)
    wall = [st.proj(p) for p in [(size, 0, 0), (size, size, 0), (size, size, size), (size, 0, size)]]
    s.add(st.dot((size, size / 2, size / 2), st.D) + 3.01, st.poly(wall, yz.base), wall)
    return s.to_svg(title)


def b_epipolar(title, pal):
    p = P[pal]
    s = st.Scene()
    point = (0.0, 1.2, 4.0)
    for apex, tilt in (((-3.2, 0.0, -1.0), 0.35), ((3.2, 0.0, -1.0), -0.35)):
        camera_body(s, P["slate"], apex)
        cz = apex[2] + 1.6
        cx = apex[0] + tilt * 1.6
        frustum(s, p, apex, cz, 1.8, 1.4, centre=(cx, apex[1]))
        _lines(s, [(apex, point)], P["coral"].base, 0.045, dash="0.14 0.1", depth=-40)
    _lines(s, [((-3.2, 0.0, -1.0), (3.2, 0.0, -1.0))], P["slate"].base, 0.045, dash="0.08 0.08", depth=-41)
    _dot(s, point, 0.16, P["coral"].base, depth_bias=-50)
    return s.to_svg(title)


def b_anchor(title, pal):
    p = P[pal]
    n, cell = 8, 40
    size = n * cell
    lines = "".join(f'<path d="M{i * cell} 0V{size}M0 {i * cell}H{size}" stroke="#c5cdd8" stroke-width="1.5"/>' for i in range(1, n))
    c = 4.5 * cell
    colours = [P["coral"].base, P["blue"].base, P["green"].base]
    rects = []
    for k, scale in enumerate((70, 120, 170)):
        for ratio in (0.5, 1.0, 2.0):
            w, h = scale * math.sqrt(ratio), scale / math.sqrt(ratio)
            rects.append(f'<rect x="{c - w / 2:.1f}" y="{c - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" fill="none" '
                         f'stroke="{colours[k]}" stroke-width="3"/>')
    pad = 10
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {size + 2 * pad} {size + 2 * pad}" '
            f'width="{size + 2 * pad}" height="{size + 2 * pad}"><title>{title}</title>'
            f'<rect width="{size}" height="{size}" fill="#f4f6f9" stroke="#8a97a8" stroke-width="2"/>{lines}'
            f'<rect x="{4 * cell}" y="{4 * cell}" width="{cell}" height="{cell}" fill="{p.hi}"/>{"".join(rects)}'
            f'<circle cx="{c}" cy="{c}" r="5" fill="{p.ink}"/></svg>\n')


def b_skeleton(title):
    people = pose_points(1.0, (0, 0))[:1]
    person = people[0]
    xs, ys = [x for x, _ in person.values()], [y for _, y in person.values()]
    pad = 30
    x0, y0, x1, y1 = min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad
    parts = []
    for a, b, side in LIMBS:
        if a in person and b in person:
            (ax, ay), (bx, by) = person[a], person[b]
            r, g, bb = SIDE_COLOUR[side]
            parts.append(f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="rgb({r},{g},{bb})" stroke-width="9" '
                         f'stroke-linecap="round"/>')
    for x, y in person.values():
        parts.append(f'<circle cx="{x}" cy="{y}" r="8" fill="#ffffff" stroke="#28303c" stroke-width="3.5"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} {x1 - x0} {y1 - y0}" width="{x1 - x0}" '
            f'height="{y1 - y0}"><title>{title}</title>{"".join(parts)}</svg>\n')


# ------------------------------------------------------------------ catalogue
def build_specs():
    for key, (_, _, _, zh, _) in COMMONS.items():
        if key != "pose":
            add(f"photo-{key}", INPUT, f"输入图像：{zh}", f"input photo: {key}", ["输入图像", "照片", zh],
                (lambda k=key: square(k) if COMMONS[k][4] else wide(k)), key)
    for key, (_, _, _, zh) in SKIMAGE.items():
        add(f"photo-{key}", INPUT, f"输入图像：{zh}", f"input photo: {key}", ["输入图像", "照片", zh],
            (lambda k=key: square(k) if k != "coffee" else wide(k)), key)

    for key in ("cat", "dog", "bird"):
        zh = COMMONS[key][3]
        add(f"grid4-{key}", INPUT, f"图像分块 4×4（{zh}）", f"image split into 4x4 patches ({key})", ["图像分块", "patch", "ViT"],
            lambda k=key: grid_overlay(square(k), 4), key)
    for key in ("cat", "dog"):
        zh = COMMONS[key][3]
        add(f"patches-{key}", INPUT, f"分块展开（{zh}）", f"exploded patches ({key})", ["patch", "分块", "ViT", "Token"],
            lambda k=key: exploded(square(k, 512), 4, gap=10), key)
        add(f"mae-{key}", INPUT, f"随机掩码 75%（{zh}，MAE）", f"MAE masking 75% ({key})", ["MAE", "掩码", "自监督", "masked image"],
            lambda k=key: exploded(square(k, 512), 6, gap=6, masked=mae_cells(6, 0.75, 7)), key)
    add("mae-visible-cat", INPUT, "掩码后保留的可见块（猫）", "visible patches after masking (cat)", ["MAE", "可见块", "编码器输入"],
        lambda: exploded(square("cat", 512), 6, gap=6, masked=mae_cells(6, 0.75, 7), keep_only=True), "cat")
    add("patch-row-cat", INPUT, "分块展平为序列（猫）", "patches flattened to a sequence (cat)", ["patch", "展平", "Token 序列"],
        lambda: patch_row(square("cat", 576)), "cat")

    for t, a in ((1, 0.8), (2, 0.5), (3, 0.2), (4, 0.0)):
        add(f"noise-{t}-cat", INPUT, f"扩散加噪第 {t} 步（猫）", f"diffusion noising step {t} (cat)", ["扩散", "加噪", "diffusion"],
            lambda a=a: noisy(square("cat", 512), a), "cat")
    add("noise-strip-cat", INPUT, "逐步加噪序列（猫）", "forward diffusion strip (cat)", ["扩散", "加噪序列", "去噪"],
        lambda: on_white(strip([noisy(square("cat", 280), a) for a in (1.0, 0.75, 0.45, 0.15, 0.0)])), "cat")
    add("lowres-bird", INPUT, "低分辨率输入（翠鸟）", "low-resolution input (bird)", ["超分辨率", "低分辨率", "SR"],
        lambda: lowres(square("bird"), 28), "bird")
    add("blur-bird", INPUT, "模糊输入（翠鸟）", "blurred input (bird)", ["去模糊", "图像复原", "模糊"],
        lambda: square("bird").filter(ImageFilter.GaussianBlur(10)), "bird")
    add("edges-cat", INPUT, "Canny 边缘图（猫）", "Canny edge map (cat)", ["边缘", "Canny", "edge"], lambda: canny(square("cat")), "cat")
    add("edges-street", INPUT, "Canny 边缘图（街景）", "Canny edge map (street)", ["边缘", "Canny", "edge"],
        lambda: canny(wide("street")), "street")
    add("edges-camera", INPUT, "Canny 边缘图（摄影师）", "Canny edge map (cameraman)", ["边缘", "Canny", "经典图像"],
        lambda: canny(square("camera")), "camera")
    for idx, zh, en in ((0, "红", "red"), (1, "绿", "green"), (2, "蓝", "blue")):
        add(f"channel-{en}-coffee", INPUT, f"{zh}色通道（咖啡杯）", f"{en} channel (coffee)", ["通道", "RGB", zh],
            lambda i=idx: channel(wide("coffee"), i), "coffee")
    add("grey-coffee", INPUT, "灰度图（咖啡杯）", "greyscale (coffee)", ["灰度", "单通道"], lambda: ImageOps.grayscale(wide("coffee")).convert("RGB"), "coffee")
    add("fft-camera", INPUT, "傅里叶频谱（摄影师）", "Fourier spectrum (cameraman)", ["频域", "FFT", "频谱"],
        lambda: spectrum(square("camera")), "camera")
    add("superpixels-room", INPUT, "SLIC 超像素边界（室内）", "SLIC superpixel boundaries (room)", ["超像素", "SLIC", "分割"],
        lambda: superpixels(wide("room"), 220), "room")
    add("superpixels-dog", INPUT, "超像素均值图（狗）", "superpixel mean colours (dog)", ["超像素", "SLIC", "区域"],
        lambda: superpixel_mean(square("dog"), 160), "dog")

    def aug(kind):
        base = square("dog")
        if kind == "flip":
            return ImageOps.mirror(base)
        if kind == "crop":
            return base.crop((120, 60, 560, 500)).resize(base.size, Image.Resampling.LANCZOS)
        if kind == "jitter":
            hsv = cv2.cvtColor(np.asarray(base), cv2.COLOR_RGB2HSV).astype(np.int32)
            hsv[..., 0] = (hsv[..., 0] + 14) % 180
            out = Image.fromarray(cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB))
            return ImageEnhance.Color(ImageEnhance.Brightness(out).enhance(1.12)).enhance(1.5)
        if kind == "rotate":
            rot = base.rotate(18, resample=Image.Resampling.BICUBIC)
            m = 140
            return rot.crop((m, m, base.width - m, base.height - m)).resize(base.size, Image.Resampling.LANCZOS)
        if kind == "grey":
            return ImageOps.grayscale(base).convert("RGB")
        if kind == "blur":
            return base.filter(ImageFilter.GaussianBlur(7))
        out = base.copy()
        ImageDraw.Draw(out).rectangle((430, 120, 640, 330), fill=(128, 128, 128))
        return out
    for kind, zh in (("flip", "水平翻转"), ("crop", "随机裁剪"), ("jitter", "颜色抖动"), ("rotate", "旋转"), ("grey", "随机灰度"),
                     ("blur", "高斯模糊"), ("cutout", "Cutout 遮挡")):
        add(f"aug-{kind}-dog", INPUT, f"数据增强：{zh}（狗）", f"augmentation: {kind} (dog)", ["数据增强", "augmentation", zh, "对比学习"],
            lambda k=kind: aug(k), "dog")

    seg = {"dog": ((70, 70, 705, 705), (88, 196, 255)), "bird": ((140, 205, 512, 692), (255, 196, 64))}
    for key, (rect, colour) in seg.items():
        zh = COMMONS[key][3]
        add(f"mask-{key}", TASK, f"分割掩码（{zh}）", f"segmentation mask ({key})", ["分割掩码", "mask", "前景"],
            lambda k=key, r=rect: Image.fromarray(grabcut(square(k), r)), key)
        add(f"overlay-{key}", TASK, f"分割结果叠加（{zh}）", f"segmentation overlay ({key})", ["语义分割", "实例分割", "叠加"],
            lambda k=key, r=rect, c=colour: overlay_mask(square(k), grabcut(square(k), r), c), key)
        add(f"cutout-{key}", TASK, f"抠图：{zh}（透明背景）", f"cut-out ({key}, transparent)", ["抠图", "前景", "透明背景"],
            lambda k=key, r=rect: cutout(square(k), grabcut(square(k), r)), key)

    def det_box(key, rect, colour):
        m = grabcut(square(key), rect)
        ys, xs = np.nonzero(m)
        return boxes(square(key), [((xs.min(), ys.min(), xs.max(), ys.max()), colour)])
    add("box-dog", TASK, "检测框（狗）", "detection box (dog)", ["目标检测", "检测框", "bounding box"],
        lambda: det_box("dog", seg["dog"][0], (64, 192, 87)), "dog")
    add("box-car", TASK, "检测框（汽车）", "detection box (car)", ["目标检测", "检测框", "bounding box"],
        lambda: boxes(square("car"), [((40, 238, 724, 700), (51, 154, 240))]), "car")
    street_boxes = [((600, 650, 732, 1042), "p"), ((758, 678, 832, 888), "p"), ((84, 668, 216, 962), "p"),
                    ((190, 678, 252, 906), "p"), ((300, 732, 366, 918), "p"), ((1656, 646, 1752, 928), "p"),
                    ((1734, 768, 1778, 912), "p"), ((1058, 652, 1536, 1012), "c"), ((904, 732, 1128, 916), "c"),
                    ((814, 718, 956, 852), "c"), ((414, 776, 602, 968), "m")]
    cls_colour = {"p": (255, 107, 107), "c": (51, 154, 240), "m": (252, 196, 25)}

    def street_det():
        image = wide("street")
        k = image.width / photo("street").width
        return boxes(image, [((x0 * k, y0 * k, x1 * k, y1 * k), cls_colour[c]) for (x0, y0, x1, y1), c in street_boxes], width=3)
    add("boxes-street", TASK, "多目标检测框（街景）", "multi-object detection (street)", ["目标检测", "多类别", "行人", "车辆"],
        street_det, "street")

    def cam(key, rect):
        image = square(key)
        m = grabcut(image, rect).astype(np.float32)
        dist = cv2.distanceTransform((m > 0).astype(np.uint8), cv2.DIST_L2, 5)
        heat = cv2.GaussianBlur(dist, (0, 0), 40)
        return heat_overlay(image, heat, 0.48)
    add("cam-dog", TASK, "类激活热力图（狗）", "class activation map (dog)", ["CAM", "Grad-CAM", "热力图", "可解释性"],
        lambda: cam("dog", seg["dog"][0]), "dog")
    add("attention-cat", TASK, "注意力热力图（猫）", "attention heat map (cat)", ["注意力", "热力图", "显著性"],
        lambda: heat_overlay(square("cat"), gaussian_heat((SIDE, SIDE), [(266, 335), (478, 335), (372, 490)], [62, 62, 80]), 0.45),
        "cat")

    def pose(kind):
        image = square("pose")
        k = SIDE / 900
        people = pose_points(k, COMMONS["pose"][4][:2])
        if kind == "skeleton":
            return draw_skeleton(image, people).convert("RGB")
        if kind == "heat":
            pts = [p for person in people for p in person.values()]
            return heat_overlay(image, gaussian_heat((SIDE, SIDE), pts, [11] * len(pts)), 0.55)
        return draw_skeleton(image, people, background=Image.new("RGBA", image.size, (0, 0, 0, 0)))
    add("pose-skeleton", TASK, "人体关键点与骨架（运动人物）", "human pose keypoints (players)", ["姿态估计", "关键点", "骨架", "COCO"],
        lambda: pose("skeleton"), "pose")
    add("pose-heatmaps", TASK, "关键点热力图（运动人物）", "keypoint heat maps (players)", ["姿态估计", "关键点", "热力图"],
        lambda: pose("heat"), "pose")
    add("pose-only", TASK, "人体骨架（透明背景）", "human skeletons, transparent", ["姿态估计", "骨架", "关键点"],
        lambda: pose("only"), "pose")
    add("flow-wheel", TASK, "光流颜色编码色轮", "optical flow colour wheel", ["光流", "optical flow", "色轮"], flow_wheel)
    add("flow-field", TASK, "光流场颜色编码", "colour-coded flow field", ["光流", "运动", "optical flow"], flow_field)

    # photos on isometric planes
    for key in ("cat", "dog", "street", "road", "room", "aerial"):
        zh = COMMONS[key][3]
        add(f"iso-{key}", INPUT, f"斜置图像平面（{zh}）", f"image on an isometric plane ({key})", ["图像平面", "等轴测", "输入", "三维"],
            ("svg", lambda k=key: iso_photo(square(k, 640) if COMMONS[k][4] else wide(k, 800))), key)
    add("iso-retina", INPUT, "斜置图像平面（眼底）", "image on an isometric plane (retina)", ["医学图像", "图像平面", "等轴测"],
        ("svg", lambda: iso_photo(square("retina", 640))), "retina")
    add("iso-grid-cat", INPUT, "斜置分块图像（猫）", "patch grid on an isometric plane (cat)", ["图像分块", "ViT", "等轴测"],
        ("svg", lambda: iso_photo(square("cat", 640), grid=4)), "cat")

    def road_frames():
        image = photo("road")
        h = image.height
        w = round(h * 4 / 3)
        return [image.crop((x, 0, x + w, h)).resize((640, 480), Image.Resampling.LANCZOS) for x in (0, 50, 100, 150)]
    add("frames-road", INPUT, "视频帧堆叠（道路）", "stacked video frames (road)", ["视频", "帧序列", "时序", "自动驾驶"],
        ("svg", lambda: iso_frames(road_frames())), "road")
    add("frames-street", INPUT, "视频帧堆叠（街景）", "stacked video frames (street)", ["视频", "帧序列", "时序"],
        ("svg", lambda: iso_frames([wide("street", 800).crop((x, 0, x + 600, 465)) for x in (0, 60, 120)])), "street")
    add("pyramid-dog", INPUT, "图像金字塔（狗）", "image pyramid (dog)", ["多尺度", "图像金字塔", "下采样"],
        ("svg", lambda: iso_pyramid(square("dog", 640))), "dog")
    add("channels-cat", INPUT, "RGB 三通道分离（猫）", "RGB channels split (cat)", ["RGB", "通道", "输入张量"],
        ("svg", lambda: iso_channels(square("cat", 560))), "cat")
    add("frustum-photo", THREE_D, "相机视锥与成像平面（街景）", "camera frustum with an image (street)", ["相机", "视锥", "成像"],
        ("svg", lambda: lambda title: b_frustum(title, "blue", wide("street", 640).crop((60, 0, 588, 406)))), "street")

    # isometric 3-D vision schematics (no photo)
    for pal in ("blue", "purple"):
        add(f"frustum-{pal}", THREE_D, f"相机视锥（{P[pal].zh}）", f"camera frustum ({pal})", ["相机", "视锥", "frustum", "针孔相机"],
            ("svg", lambda p=pal: lambda title: b_frustum(title, p)))
    add("multiview", THREE_D, "多视角相机环绕物体", "multi-view camera rig", ["多视角", "相机", "NeRF", "三维重建"],
        ("svg", lambda: lambda title: b_multiview(title, "blue")))
    add("nerf-rays", THREE_D, "射线采样（NeRF 体渲染）", "ray sampling for volume rendering", ["NeRF", "体渲染", "射线", "采样点"],
        ("svg", lambda: lambda title: b_nerf(title, "blue")))
    for pal in ("blue", "teal", "orange"):
        add(f"voxels-{pal}", THREE_D, f"体素网格（{P[pal].zh}）", f"voxel grid ({pal})", ["体素", "voxel", "占据栅格", "三维"],
            ("svg", lambda p=pal: lambda title: b_voxels(title, p)))
    add("bbox3d", THREE_D, "点云中的三维检测框", "3D bounding box in a point cloud", ["三维检测", "点云", "3D box", "激光雷达"],
        ("svg", lambda: lambda title: b_bbox3d(title, "blue")))
    add("bev", THREE_D, "鸟瞰图（BEV）栅格与车辆", "bird's-eye-view grid with vehicles", ["BEV", "鸟瞰图", "自动驾驶", "占据栅格"],
        ("svg", lambda: lambda title: b_bev(title, "blue")))
    add("splats", THREE_D, "三维高斯泼溅", "3D Gaussian splats", ["3DGS", "高斯泼溅", "Gaussian splatting", "新视角合成"],
        ("svg", lambda: lambda title: b_splats(title, ["blue", "teal", "purple", "orange"])))
    add("triplane", THREE_D, "三平面特征（Tri-plane）", "tri-plane features", ["Tri-plane", "三平面", "三维表示"],
        ("svg", lambda: lambda title: b_triplane(title)))
    add("epipolar", THREE_D, "双目相机与三角测量", "stereo cameras and triangulation", ["双目", "极线几何", "三角测量", "深度"],
        ("svg", lambda: lambda title: b_epipolar(title, "blue")))
    add("anchors", TASK, "锚框（3 尺度 × 3 长宽比）", "anchor boxes, 3 scales x 3 ratios", ["锚框", "anchor", "目标检测"],
        ("svg", lambda: lambda title: b_anchor(title, "blue")))
    add("skeleton", TASK, "人体骨架模板（COCO 17 点）", "human skeleton template, COCO 17 keypoints", ["关键点", "骨架", "姿态"],
        ("svg", lambda: lambda title: b_skeleton(title)))


# ------------------------------------------------------------------ rendering
def save_image(image, stem, folder):
    if image.mode == "RGBA" and image.getextrema()[3][0] == 255:
        image = image.convert("RGB")
    if image.mode in ("RGBA", "L"):
        path = folder / f"{stem}.png"
        image.save(path, optimize=True)
        return "png", path
    path = folder / f"{stem}.jpg"
    image.convert("RGB").save(path, quality=90, optimize=True, progressive=True)
    return "jpg", path


def render(spec):
    eid, category, zh, en, tags, maker, key = spec
    files = {}
    if isinstance(maker, tuple):
        svg = maker[1]()(zh)
        files["svg"] = OUT / f"{eid}.svg"
        files["svg"].write_text(svg, encoding="utf-8", newline="\n")
        vb = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([\d.]+) ([\d.]+)"', svg)
        w, h = float(vb.group(3)), float(vb.group(4))
        scale = (PHOTO_PNG_SIDE if "<image" in svg else PNG_SIDE) / max(w, h)
        png = resvg_py.svg_to_bytes(svg_string=svg, width=round(w * scale), height=round(h * scale))
        image = Image.open(io.BytesIO(bytes(png))).convert("RGBA")
        files["png"] = OUT / f"{eid}.png"
        image.save(files["png"], optimize=True)
    else:
        image = maker()
        kind, path = save_image(image, eid, OUT)
        files[kind] = path
    thumb = image.convert("RGBA") if image.mode == "RGBA" else image.convert("RGB")
    thumb.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.Resampling.LANCZOS)
    files["thumb"] = OUT / "thumbs" / f"{eid}.webp"
    thumb.save(files["thumb"], quality=90, method=6)
    record = {
        "id": f"cv-{eid}", "kind": "atomic", "collection": "vision", "source": "vision", "category": category,
        "name": zh, "english": en, "tags": tags + ["计算机视觉"],
        "description": ("研图视觉图元：用 CC0 / 公有领域照片按常见视觉任务处理得到，处理结果同样以 CC0 发布。" if key else
                        "研图视觉图元：统一等轴测风格的三维视觉示意，SVG 可直接编辑，CC0 发布。"),
        "upstream": upstream(key) if key else "https://github.com/RuntimeWarning/research-figure-library",
        "upstream_label": "原始照片" if key else "生成脚本",
        "credit": credit(key) if key else "Figure Atlas (CC0 1.0); attribution not required.",
        "page": "", "svg_kind": "" if "svg" not in files else ("mixed" if "<image" in svg else "vector"),
        "has_alpha": image.mode == "RGBA", "width": image.width, "height": image.height,
        "files": {k: p.relative_to(DIST).as_posix() for k, p in files.items()},
        "hashes": {k: sha256(p) for k, p in files.items() if k != "thumb"},
        "bytes": {k: p.stat().st_size for k, p in files.items() if k != "thumb"},
    }
    return record


def main():
    build_specs()
    ids = [s[0] for s in SPECS]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate vision ids")
    (OUT / "thumbs").mkdir(parents=True, exist_ok=True)
    for key in COMMONS:
        photo(key)   # download sequentially before rendering
    records = []
    for i, spec in enumerate(SPECS):
        record = render(spec)
        record["order"] = 20000 + i
        records.append(record)
    keep = {Path(v).name for r in records for v in r["files"].values()}
    for path in list(OUT.glob("*.*")) + list((OUT / "thumbs").glob("*.*")):
        if path.name not in keep:
            path.unlink()
    source = {"short": "研图视觉", "title": "研图视觉图元（基于 CC0 / 公有领域照片与原创示意）", "authors": ["研图 Figure Atlas"],
              "venue": "CC0 1.0 · 可自由使用", "year": 2026, "arxiv": "",
              "url": "https://github.com/RuntimeWarning/research-figure-library", "pdf": "",
              "license": "CC0-1.0", "license_name": "CC0 1.0（公共领域）",
              "license_url": "https://creativecommons.org/publicdomain/zero/1.0/", "license_file": "",
              "attribution": "Figure Atlas (CC0 1.0); attribution not required.",
              "processing": "照片经裁剪、缩放后按对应视觉任务处理；示意图为原创绘制"}
    write_json(MANIFESTS / "vision.json", {"sources": {"vision": source}, "assets": records})
    print({"vision": len(records), "by_category": Counter(r["category"] for r in records),
           "bytes": sum(sum(r["bytes"].values()) for r in records)})


if __name__ == "__main__":
    main()
