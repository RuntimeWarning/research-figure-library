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
import tifffile
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
INPUT, TASK, THREE_D, MED, FEATURE = "图像输入与预处理", "检测、分割与关键点", "三维视觉", "医学影像", "特征图"
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
    "xray": ("Chest Xray PA 3-8-2010.png", "Stillwaterising", "CC0", "胸部 X 光片", (250, 190, 1610, 1550)),
    "ct": ("Computed tomography of human brain - large.png", "Department of Radiology, Uppsala University Hospital", "CC0",
           "脑部 CT", None),
    "mri": ("T1-weighted-MRI.png", "Mim.cis", "public domain", "脑部 MRI（T1）", (0, 38, 481, 519)),
}
MEDICAL = {"xray", "ct", "mri", "skin", "mitosis", "kidney"}
SKIMAGE = {
    # key: (loader, description, licence, 中文名)
    "astronaut": ("astronaut", "NASA photograph of Eileen Collins", "public domain", "宇航员"),
    "coffee": ("coffee", "photo by Rachel Michetti", "CC0", "咖啡杯"),
    "camera": ("camera", "photo by Lav Varshney", "CC0", "摄影师（灰度）"),
    "retina": ("retina", "fundus photograph by Mikael Häggström", "CC0", "眼底图像"),
    "skin": ("skin", "H&E stained section of skin by Kilbad", "public domain", "皮肤组织切片（H&E 染色）"),
    "mitosis": ("human_mitosis", "fluorescence image of human cell nuclei by David Root", "CC0", "荧光细胞核"),
    "kidney": ("kidney", "confocal fluorescence image of mouse kidney tissue by Genevieve Buckley", "CC0", "肾组织荧光图像"),
}
SKIMAGE_DOCS = "https://scikit-image.org/docs/stable/api/skimage.data.html"
# Sample images scikit-image downloads on demand (needs pooch); fetched here straight from its data repository.
SKIMAGE_DATA = "https://gitlab.com/scikit-image/data/-/raw/2cdc5ce89b334d28f06a58c9f0ca21aa6992a5ba/"
SKIMAGE_REMOTE = {"skin": "Normal_Epidermis_and_Dermis_with_Intradermal_Nevus_10x.JPG",
                  "human_mitosis": "AS_09125_050116030001_D03f00d0.tif", "kidney": "kidney-tissue-fluorescence.tif"}
CT_TILES = ([2, 275, 548, 822, 1096, 1369, 1642], [1, 274, 547, 820])   # slice grid in the 1920 px CT montage

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
    elif SKIMAGE[key][0] in SKIMAGE_REMOTE:
        loader = SKIMAGE[key][0]
        name = SKIMAGE_REMOTE[loader]
        data = fetch(SKIMAGE_DATA + quote(name), PHOTO_CACHE / f"sk-{loader}{Path(name).suffix.lower()}", timeout=300)
        image = remote_sample(loader, data)
    else:
        image = Image.fromarray(getattr(skdata, SKIMAGE[key][0])()).convert("RGB")
    _PHOTOS[key] = image
    return image


def remote_sample(loader, data):
    if loader == "skin":
        return Image.open(io.BytesIO(data)).convert("RGB")
    arr = tifffile.imread(io.BytesIO(data)).astype(np.float32)
    if loader == "human_mitosis":   # grey nuclei shown in the usual DAPI blue
        g = np.clip((arr - np.percentile(arr, 1)) / (np.percentile(arr, 99.7) - np.percentile(arr, 1)), 0, 1)
        return Image.fromarray((np.stack([g * 0.32, g * 0.66, g], -1) * 255).astype(np.uint8))
    rgb = np.moveaxis(arr[8], 0, -1)  # kidney: middle z-slice, three emission channels
    rgb = rgb / np.percentile(rgb, 99.6, axis=(0, 1))
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))


def ct_slice(index, side=None):
    """One axial slice from the CT montage (rows of seven), cropped to the head without the head-rest arcs."""
    name = COMMONS["ct"][0]
    data = fetch(f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(name)}?width=1920", PHOTO_CACHE / "ct.jpg")
    montage = Image.open(io.BytesIO(data)).convert("RGB")
    xs, ys = CT_TILES
    x, y = xs[index % 7], ys[index // 7]
    tile = montage.crop((x + 36, y + 6, x + 234, y + 258))
    return tile.resize((side, round(side * tile.height / tile.width)), Image.Resampling.LANCZOS) if side else tile


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


# ------------------------------------------------------------------ degradations (restoration inputs)
def as_float(image):
    return np.asarray(image.convert("RGB"), np.float32) / 255


def from_float(arr):
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))


def gaussian_noise(image, sigma=30, seed=1):
    arr = np.asarray(image, np.float32) + np.random.default_rng(seed).normal(0, sigma, (image.height, image.width, 3))
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def low_light(image, seed=2):
    dark = as_float(image) ** 2.0 * 0.28
    dark += np.random.default_rng(seed).normal(0, 0.012, dark.shape)
    return from_float(dark)


def hazy(image, beta=1.9, light=(0.86, 0.88, 0.9)):
    """Atmospheric scattering with depth growing towards the top of the frame."""
    arr = as_float(image)
    h = arr.shape[0]
    depth = 0.2 + 0.8 * (1 - np.linspace(0, 1, h)) ** 1.3
    t = np.exp(-beta * depth)[:, None, None]
    return from_float(arr * t + np.array(light) * (1 - t))


def rainy(image, seed=4):
    rng = np.random.default_rng(seed)
    h, w = image.height, image.width
    drops = np.zeros((h, w), np.float32)
    n = int(h * w * 0.004)
    drops[rng.integers(0, h, n), rng.integers(0, w, n)] = rng.uniform(0.6, 1.0, n)
    k = 31
    kernel = np.zeros((k, k), np.float32)
    cv2.line(kernel, (k // 2 + 5, 0), (k // 2 - 5, k - 1), 1.0, 1)
    streaks = cv2.filter2D(drops, -1, kernel / kernel.sum()) * 10
    streaks = cv2.GaussianBlur(streaks, (3, 3), 0).clip(0, 1)
    arr = as_float(hazy(image, 0.8)) * 0.9
    return from_float(arr + streaks[..., None] * 0.7 * (1 - arr))


def jpeg(image, quality=6):
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "JPEG", quality=quality)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def motion_blur(image, length=41):
    kernel = np.zeros((length, length), np.float32)
    kernel[length // 2, :] = 1 / length
    return Image.fromarray(cv2.filter2D(np.asarray(image), -1, kernel, borderType=cv2.BORDER_REFLECT))


def stroke_mask(size, seed=7, strokes=7):
    """Free-form brush strokes like the masks used to train inpainting models (0/255)."""
    rng = np.random.default_rng(seed)
    mask = np.zeros((size, size), np.uint8)
    for _ in range(strokes):
        x, y = rng.uniform(0.15, 0.85, 2) * size
        width = int(rng.uniform(0.022, 0.045) * size)
        angle = rng.uniform(0, 2 * np.pi)
        for _ in range(rng.integers(3, 6)):
            angle += rng.uniform(-1.2, 1.2)
            length = rng.uniform(0.08, 0.2) * size
            nx = float(np.clip(x + length * np.cos(angle), 0.05 * size, 0.95 * size))
            ny = float(np.clip(y + length * np.sin(angle), 0.05 * size, 0.95 * size))
            cv2.line(mask, (int(x), int(y)), (int(nx), int(ny)), 255, width, lineType=cv2.LINE_AA)
            cv2.circle(mask, (int(nx), int(ny)), width // 2, 255, -1, lineType=cv2.LINE_AA)
            x, y = nx, ny
    return mask


def with_holes(image, mask):
    arr = np.asarray(image).copy()
    arr[mask > 127] = 255
    return Image.fromarray(arr)


# ------------------------------------------------------------------ augmentations
def mixup(a, b, lam=0.5):
    return Image.blend(a, b, lam)


def cutmix(base, patch, box):
    out = base.copy()
    out.paste(patch.crop(box), box[:2])
    d = ImageDraw.Draw(out)
    d.rectangle(box, outline=(255, 255, 255), width=4)
    return out


def mosaic(images, side=SIDE, centre=(0.43, 0.56)):
    cx, cy = round(centre[0] * side), round(centre[1] * side)
    boxes = [(0, 0, cx, cy), (cx, 0, side, cy), (0, cy, cx, side), (cx, cy, side, side)]
    out = Image.new("RGB", (side, side))
    for image, (x0, y0, x1, y1) in zip(images, boxes):
        w, h = x1 - x0, y1 - y0
        s = max(w / image.width, h / image.height)
        im = image.resize((round(image.width * s) + 1, round(image.height * s) + 1), Image.Resampling.LANCZOS)
        ox, oy = (im.width - w) // 2, (im.height - h) // 2
        out.paste(im.crop((ox, oy, ox + w, oy + h)), (x0, y0))
    d = ImageDraw.Draw(out)
    d.line([(cx, 0), (cx, side)], fill=(255, 255, 255), width=4)
    d.line([(0, cy), (side, cy)], fill=(255, 255, 255), width=4)
    return out


def perspective(image, k=0.16):
    w, h = image.size
    src = np.float32([(0, 0), (w, 0), (w, h), (0, h)])
    dst = np.float32([(w * k, h * 0.06), (w * (1 - k * 0.4), 0), (w, h * (1 - k * 0.5)), (0, h)])
    m = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(np.asarray(image.convert("RGBA")), m, (w, h), borderValue=(0, 0, 0, 0))
    return Image.fromarray(warped, "RGBA")


def random_erasing(image, seed=5):
    rng = np.random.default_rng(seed)
    arr = np.asarray(image).copy()
    for x0, y0, x1, y1 in ((420, 110, 600, 270), (130, 520, 300, 640)):
        arr[y0:y1, x0:x1] = rng.integers(0, 256, (y1 - y0, x1 - x0, 3))
    return Image.fromarray(arr)


def gridmask(image, cell=128, ratio=0.45, offset=(30, 40)):
    arr = np.asarray(image).copy()
    hole = int(cell * ratio)
    for y in range(offset[1], image.height, cell):
        for x in range(offset[0], image.width, cell):
            arr[y:y + hole, x:x + hole] = 0
    return Image.fromarray(arr)


def sobel_magnitude(image):
    grey = cv2.GaussianBlur(np.asarray(image.convert("L"), np.float32), (0, 0), 1.6)
    mag = np.hypot(cv2.Sobel(grey, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(grey, cv2.CV_32F, 0, 1, ksize=3))
    mag = np.clip(mag / np.percentile(mag, 99.3), 0, 1) ** 0.8
    return Image.fromarray(cv2.applyColorMap((mag * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)[..., ::-1])


# ------------------------------------------------------------------ CNN-like feature maps from a photo
def responses(image, size=64):
    """Rectified responses of a small filter bank (oriented Gabor, centre-surround, colour-opponent), pooled to
    ``size`` x ``size``: they look like the feature maps of an early CNN layer."""
    rgb = as_float(image)
    grey = rgb.mean(-1)
    maps = []
    for scale in (4.0, 8.0):
        for k in range(4):
            kern = cv2.getGaborKernel((31, 31), scale, k * np.pi / 4, scale * 2.2, 0.6, 0)
            kern -= kern.mean()
            maps.append(np.maximum(cv2.filter2D(grey, -1, kern), 0))
    for s1, s2 in ((2, 6), (5, 14)):
        dog = cv2.GaussianBlur(grey, (0, 0), s1) - cv2.GaussianBlur(grey, (0, 0), s2)
        maps += [np.maximum(dog, 0), np.maximum(-dog, 0)]
    rg = rgb[..., 0] - rgb[..., 1]
    by = rgb[..., 2] - (rgb[..., 0] + rgb[..., 1]) / 2
    maps += [np.maximum(rg, 0), np.maximum(-rg, 0), np.maximum(by, 0), np.maximum(-by, 0)]
    out = []
    for m in maps:
        m = cv2.resize(cv2.GaussianBlur(m, (0, 0), 2), (size, size), interpolation=cv2.INTER_AREA)
        out.append(np.clip(m / (np.percentile(m, 99.5) + 1e-6), 0, 1))
    return out


def colourise(m, cmap=cv2.COLORMAP_VIRIDIS, side=None):
    if isinstance(cmap, str):   # palette name: light cell tint -> deep ink
        pal = P[cmap]
        m = m ** 0.65
        stops = [st._hex(c) for c in (pal.cell, pal.hi, pal.base, pal.ink)]
        t = m * (len(stops) - 1)
        i = np.clip(t.astype(int), 0, len(stops) - 2)
        f = (t - i)[..., None]
        a, b = np.array(stops)[i], np.array(stops)[i + 1]
        rgb = ((a + (b - a) * f) * 255).astype(np.uint8)
    elif cmap is None:
        rgb = np.repeat((m * 255).astype(np.uint8)[..., None], 3, -1)
    else:
        rgb = cv2.applyColorMap((m * 255).astype(np.uint8), cmap)[..., ::-1]
    image = Image.fromarray(np.ascontiguousarray(rgb))
    return image.resize((side, side), Image.Resampling.BICUBIC) if side else image


def channel_grid(image, cmap, n=4, tile=176, gap=10, order=(0, 9, 2, 13, 5, 8, 15, 3, 10, 1, 14, 6, 12, 4, 11, 7)):
    maps = responses(image, 48)
    out = Image.new("RGBA", (n * tile + (n - 1) * gap, n * tile + (n - 1) * gap), (0, 0, 0, 0))
    for i in range(n * n):
        out.paste(colourise(maps[order[i] % len(maps)], cmap, tile).convert("RGBA"), ((i % n) * (tile + gap), (i // n) * (tile + gap)))
    return out


# ------------------------------------------------------------------ annotations drawn at 3x and scaled down (anti-aliased)
def annotate(image, draw, scale=3):
    base = image.convert("RGBA")
    layer = Image.new("RGBA", (base.width * scale, base.height * scale), (0, 0, 0, 0))
    draw(ImageDraw.Draw(layer), scale)
    return Image.alpha_composite(base, layer.resize(base.size, Image.Resampling.LANCZOS)).convert("RGB")


def point_marker(d, k, x, y, colour, r=15):
    d.ellipse(((x - r - 4) * k, (y - r - 4) * k, (x + r + 4) * k, (y + r + 4) * k), fill=(255, 255, 255, 255))
    d.ellipse(((x - r) * k, (y - r) * k, (x + r) * k, (y + r) * k), fill=colour + (255,))


def dashed_box(d, k, box, colour, width=5, dash=22, gap=14):
    x0, y0, x1, y1 = (v * k for v in box)
    for (ax, ay), (bx, by) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        length = math.hypot(bx - ax, by - ay)
        t = 0.0
        while t < length:
            u = min(t + dash * k, length)
            d.line([(ax + (bx - ax) * t / length, ay + (by - ay) * t / length), (ax + (bx - ax) * u / length, ay + (by - ay) * u / length)],
                   fill=colour + (255,), width=width * k)
            t += (dash + gap) * k


def smooth_path(points, n=24):
    """Catmull-Rom curve through ``points``."""
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = (np.array(p, float) for p in pts[i - 1:i + 3])
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)))
    out.append(tuple(points[-1]))
    return out


# ------------------------------------------------------------------ medical images
def nuclei():
    """Instance labels of the nuclei in a crop of the mitosis image (Otsu threshold + distance-transform watershed)."""
    from skimage.feature import peak_local_max
    image = photo("mitosis").crop((176, 256, 432, 512)).resize((SIDE, SIDE), Image.Resampling.BICUBIC)
    grey = cv2.GaussianBlur(np.asarray(image)[..., 2], (0, 0), 2)
    _, fg = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    dist = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
    peaks = peak_local_max(dist, min_distance=9, labels=fg > 0, exclude_border=False)
    markers = np.zeros(dist.shape, np.int32)
    for i, (r, c) in enumerate(peaks, 1):
        markers[r, c] = i
    labels = segmentation.watershed(-dist, markers, mask=fg > 0)
    return image, labels


def label_colours(n, seed=3):
    rng = np.random.default_rng(seed)
    hues = rng.permutation(np.linspace(0, 179, max(n, 1), endpoint=False))
    hsv = np.stack([hues, rng.uniform(120, 200, n), rng.uniform(210, 255, n)], -1).astype(np.uint8)[None]
    return np.vstack([[0, 0, 0], cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)[0]])


def nuclei_view(kind):
    image, labels = nuclei()
    colours = label_colours(labels.max())
    if kind == "labels":
        return Image.fromarray(colours[labels].astype(np.uint8))
    out = np.asarray(image).copy()
    if kind == "contours":
        for lab in range(1, labels.max() + 1):
            m = (labels == lab).astype(np.uint8)
            cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            cv2.drawContours(out, cs, -1, tuple(int(v) for v in colours[lab]), 3, lineType=cv2.LINE_AA)
        return Image.fromarray(out)
    items = []
    for lab in range(1, labels.max() + 1):
        ys, xs = np.nonzero(labels == lab)
        if len(xs) > 60:
            items.append((xs.min() - 4, ys.min() - 4, xs.max() + 4, ys.max() + 4))

    def draw(d, k):
        for box in items:
            d.rectangle(tuple(v * k for v in box), outline=(255, 196, 64, 255), width=3 * k)
    return annotate(Image.fromarray(out), draw)


def brain_tissue(kind):
    """Three intensity classes inside the brain of the T1 MRI (k-means), a rough CSF / grey / white matter split."""
    image = square("mri")
    grey = np.asarray(image.convert("L"), np.float32)
    bright = cv2.morphologyEx((grey > 55).astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    _, lab = cv2.connectedComponents(bright)
    brain = (lab == lab[grey.shape[0] // 2, grey.shape[1] // 2]).astype(np.uint8)
    brain = cv2.morphologyEx(brain, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    cs, _ = cv2.findContours(brain, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    brain = cv2.drawContours(np.zeros_like(brain), cs, -1, 1, -1)
    values = grey[brain > 0].reshape(-1, 1)
    _, idx, centres = cv2.kmeans(values, 3, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5), 4,
                                 cv2.KMEANS_PP_CENTERS)
    rank = np.argsort(np.argsort(centres[:, 0]))
    classes = np.zeros(grey.shape, np.uint8)
    classes[brain > 0] = rank[idx[:, 0]] + 1
    palette = np.array([[0, 0, 0], [77, 150, 255], [255, 167, 38], [255, 238, 170]], np.uint8)   # CSF, grey, white
    if kind == "labels":
        return Image.fromarray(palette[classes])
    arr = np.asarray(image).astype(np.float32)
    sel = classes > 0
    arr[sel] = arr[sel] * 0.45 + palette[classes][sel] * 0.55
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))


def fluorescence(image, colours=((90, 140, 255), (80, 230, 120), (255, 90, 90))):
    """Each channel of a multi-channel fluorescence image on black, in its own colour and brightened."""
    arr = as_float(image)
    out = []
    for i, colour in enumerate(colours):
        v = np.clip(arr[..., i] / (np.percentile(arr[..., i], 99.5) + 1e-6), 0, 1) ** 0.75
        out.append(from_float(v[..., None] * np.array(colour) / 255))
    return out


def wsi_tiles(n_cols=8):
    """Whole-slide tiling: tissue tiles outlined, background tiles dimmed."""
    image = wide("skin", 1024)
    hsv = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2HSV)
    tissue = hsv[..., 1] > 40
    tile = image.width // n_cols
    rows = image.height // tile
    image = image.crop((0, 0, n_cols * tile, rows * tile))
    arr = np.asarray(image).astype(np.float32)
    keep = []
    for r in range(rows):
        for c in range(n_cols):
            sl = (slice(r * tile, (r + 1) * tile), slice(c * tile, (c + 1) * tile))
            if tissue[sl].mean() > 0.5:
                keep.append((c * tile, r * tile))
            else:
                arr[sl] = arr[sl] * 0.35 + 255 * 0.65
    out = Image.fromarray(arr.astype(np.uint8))

    def draw(d, k):
        for c in range(1, n_cols):
            d.line([(c * tile * k, 0), (c * tile * k, out.height * k)], fill=(255, 255, 255, 255), width=2 * k)
        for r in range(1, rows):
            d.line([(0, r * tile * k), (out.width * k, r * tile * k)], fill=(255, 255, 255, 255), width=2 * k)
        for x, y in keep:
            d.rectangle(((x + 3) * k, (y + 3) * k, (x + tile - 3) * k, (y + tile - 3) * k), outline=(40, 120, 230, 255), width=4 * k)
    return annotate(out, draw)


# ------------------------------------------------------------------ photos on isometric planes (SVG)
def data_uri(image, side=560):
    alpha = image.mode == "RGBA" and image.getextrema()[3][0] < 255
    image = image.convert("RGBA" if alpha else "RGB")
    image.thumbnail((side, side), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    if alpha:
        image.save(buf, "PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
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


def iso_stack(images, width=4.0, step=(0.45, 0.45, 1.0)):
    """Images on parallel slabs, each one shifted up, right and back."""
    def make(title):
        s = st.Scene()
        for i, image in enumerate(images):
            photo_slab(s, image, width, x=i * step[0], y=i * step[1], z=i * step[2])
        return s.to_svg(title)
    return make


def iso_tokens(image, n=3, size=1.05, gap=0.32):
    """The n x n patches of an image as a row of tiles: the patch-embedding input of a ViT."""
    def make(title):
        s = st.Scene()
        for i, part in enumerate(p for row in tiles(image, n) for p in row):
            photo_slab(s, part, size, x=i * (size + gap), thick=0.22)
        return s.to_svg(title)
    return make


def iso_exploded(image, n=4, gap=0.22, masked=None):
    """Patches pulled apart on a plane; ``masked`` patches become blank grey tiles (MAE)."""
    def make(title):
        s = st.Scene()
        parts = tiles(image, n)
        w = (4.4 - (n - 1) * gap) / n
        for r in range(n):
            for c in range(n):
                x, y = c * (w + gap), (n - 1 - r) * (w + gap)
                if masked and (r, c) in masked:
                    st.extrude(s, st.rect(w, w), 0, 0.16, PAPER, origin=(x, y), front="#d5dbe4")
                else:
                    photo_slab(s, parts[r][c], w, x=x, y=y, thick=0.16)
        return s.to_svg(title)
    return make


def iso_backbone(image, cmap, seed=0):
    """An input photo followed by three stages of real-looking feature maps that shrink and multiply."""
    maps = responses(image, 48)
    order = np.random.default_rng(seed).permutation(len(maps))

    def make(title):
        s = st.Scene()
        photo_slab(s, image, 3.6, x=0, y=0, z=0)
        x, k = 4.3, 0
        for width, count, res in ((3.0, 3, 48), (2.2, 4, 24), (1.5, 5, 12)):
            y = (3.6 - width) / 2
            for j in range(count):
                m = cv2.resize(maps[order[k % len(maps)]], (res, res), interpolation=cv2.INTER_AREA)
                k += 1
                tile = colourise(m / (m.max() + 1e-6), cmap, 256 if res > 12 else 192)
                photo_slab(s, tile, width, x=x + j * 0.2, y=y + j * 0.12, z=j * 0.42, thick=0.1)
            x += width + 0.6 + count * 0.2
        return s.to_svg(title)
    return make


def iso_feature_stack(image, cmap, count=4, picks=(0, 9, 13, 2)):
    maps = responses(image, 56)
    return iso_stack([colourise(maps[i], cmap, 336) for i in picks[:count]], 3.4, (0.42, 0.42, 0.95))


def iso_tubelet(frames, box=(0.38, 0.3, 0.62, 0.62), colour="#e6485c", step=0.9):
    """Video frames with the same space-time patch outlined on each, joined into a tube."""
    def make(title):
        s = st.Scene()
        w = 4.0
        h = w * frames[0].height / frames[0].width
        u0, v0, u1, v1 = box
        corners = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        for i, frame in enumerate(frames):
            z = i * step
            photo_slab(s, frame, w, z=z)
            quad = [st.proj((u * w, (1 - v) * h, z)) for u, v in corners]
            s.add(st.dot((w / 2, h / 2, z), st.D) - 0.05, st.poly(quad, colour, f' fill-opacity="0.18" stroke="{colour}" stroke-width="0.06"'),
                  quad)
        segs = [((u * w, (1 - v) * h, 0), (u * w, (1 - v) * h, (len(frames) - 1) * step)) for u, v in corners]
        _lines(s, segs, colour, 0.04, dash="0.1 0.08", depth=-60, opacity=0.9)
        return s.to_svg(title)
    return make


def mpi_layers(image, bands=4):
    """Split a street photo into depth bands (top of the frame = far) as RGBA layers of a multi-plane image."""
    arr = np.asarray(image.convert("RGBA")).copy()
    h = arr.shape[0]
    edges = np.linspace(0, h, bands + 1).astype(int)
    out = []
    for i in range(bands):
        layer = np.zeros_like(arr)
        layer[edges[i]:edges[i + 1]] = arr[edges[i]:edges[i + 1]]
        out.append(Image.fromarray(layer, "RGBA"))
    return out


def iso_mpi(image, bands=4):
    layers = mpi_layers(image, bands)

    def make(title):
        s = st.Scene()
        w = 4.0
        h = w * image.height / image.width
        for i, layer in enumerate(layers):
            z = (bands - 1 - i) * 1.1    # far band at the back
            face = [st.proj(p) for p in [(0, 0, z), (w, 0, z), (w, h, z), (0, h, z)]]
            s.add(st.dot((w / 2, h / 2, z), st.D) + 0.01, st.poly(face, "#eef3fb", ' fill-opacity="0.55" stroke="#8e9db2" stroke-width="0.03"'),
                  face)
            s.add(st.dot((w / 2, h / 2, z), st.D), photo_face(layer, w, h, 0, 0, z, stroke="none"), face)
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


# ------------------------------------------------------------------ more 3-D schematics
AXIS = {"x": "#e6485c", "y": "#2ea84f", "z": "#1e6fe0"}


def _axes(s, origin, length, width=0.09, depth=-80):
    o = origin
    for key, d in (("x", (1, 0, 0)), ("y", (0, 1, 0)), ("z", (0, 0, -1))):
        end = tuple(o[i] + d[i] * length for i in range(3))
        _lines(s, [(o, end)], AXIS[key], width, depth=depth)
        _dot(s, end, width * 1.9, AXIS[key], depth_bias=depth - 1 - st.dot(end, st.D))
    _dot(s, o, width * 1.6, "#3b4656", depth_bias=depth - 2 - st.dot(o, st.D))


def b_axes(title, frame=False):
    s = st.Scene()
    if frame:
        p = P["slate"]
        st.cube(s, P["blue"], 2, 2, 2, x=-0.2, y=-0.2, z=-0.2, cell=1.0)
        _axes(s, (-0.2, 1.8, -0.2), 1.6, 0.07)
        _lines(s, _box_edges((0.8, 0.8, 0.8), (2.0, 2.0, 2.0)), p.hi, 0.03, dash="0.1 0.08", depth=60)
    _axes(s, (0, 0, 0) if not frame else (-2.6, -0.4, 1.8), 2.4 if not frame else 1.2)
    return s.to_svg(title)


def icosphere(level=2):
    t = (1 + 5 ** 0.5) / 2
    verts = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
             (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    verts = [tuple(c / math.sqrt(sum(v * v for v in p)) for c in p) for p in verts]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
             (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(level):
        cache, new = {}, []

        def mid(a, b):
            key = tuple(sorted((a, b)))
            if key not in cache:
                m = [(verts[a][i] + verts[b][i]) / 2 for i in range(3)]
                n = math.sqrt(sum(v * v for v in m))
                verts.append(tuple(v / n for v in m))
                cache[key] = len(verts) - 1
            return cache[key]
        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            new += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = new
    return verts, faces


LIGHT = (-0.45, 0.75, -0.5)


def shade_mesh(s, verts, faces, pal, wire=False, edge="#ffffff"):
    ln = math.sqrt(sum(c * c for c in LIGHT))
    light = tuple(c / ln for c in LIGHT)
    polys = []
    for f in faces:
        pts = [verts[i] for i in f]
        u = [pts[1][i] - pts[0][i] for i in range(3)]
        v = [pts[2][i] - pts[0][i] for i in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        nl = math.sqrt(sum(c * c for c in n)) or 1
        n = tuple(c / nl for c in n)
        cen = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
        if st.dot(n, cen) < 0:     # keep normals pointing outwards for closed meshes around the origin
            n = tuple(-c for c in n)
        front = st.facing(n)
        face = [st.proj(p) for p in pts]
        if wire:
            colour = pal.base if front else pal.hi
            op = "1" if front else "0.35"
            polys.append((st.depth_of(pts), f'<polygon points="{st.pts_attr(face)}" fill="none" stroke="{colour}" stroke-width="0.025" '
                                            f'stroke-opacity="{op}" stroke-linejoin="round"/>', face))
        elif front:
            b = max(0.0, st.dot(n, light))
            colour = st.mix(pal.left, pal.cell, 0.15 + 0.85 * b)
            polys.append((st.depth_of(pts), st.poly(face, colour, f' stroke="{edge}" stroke-width="0.012" stroke-opacity="0.6"'), face))
    body = "".join(svg for _, svg, _ in sorted(polys, key=lambda q: -q[0]))
    s.add(0, f"<g>{body}</g>", [p for _, _, f in polys for p in f])


TORUS_TILT = -0.8


def b_mesh(title, pal, shape="sphere", wire=False):
    s = st.Scene()
    if shape == "sphere":
        verts, faces = icosphere(2)
        shade_mesh(s, [tuple(c * 2.0 for c in v) for v in verts], faces, P[pal], wire)
        return s.to_svg(title)
    R, r, nu, nv = 2.0, 0.75, 28, 14
    verts = [((R + r * math.cos(b)) * math.cos(a), r * math.sin(b), (R + r * math.cos(b)) * math.sin(a))
             for a in [2 * math.pi * i / nu for i in range(nu)] for b in [2 * math.pi * j / nv for j in range(nv)]]
    faces = [(i * nv + j, ((i + 1) % nu) * nv + j, ((i + 1) % nu) * nv + (j + 1) % nv, i * nv + (j + 1) % nv)
             for i in range(nu) for j in range(nv)]
    t = TORUS_TILT
    verts = [(x, y * math.cos(t) - z * math.sin(t), y * math.sin(t) + z * math.cos(t)) for x, y, z in verts]
    shade_torus(s, verts, faces, P[pal], wire)
    return s.to_svg(title)


def shade_torus(s, verts, faces, pal, wire):
    """Torus faces, with the outward normal taken from the nearest point on the core circle."""
    ln = math.sqrt(sum(c * c for c in LIGHT))
    light = tuple(c / ln for c in LIGHT)
    polys = []
    tilt = TORUS_TILT
    for f in faces:
        pts = [verts[i] for i in f]
        cen = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
        # undo the tilt to find the core point
        x, y, z = cen
        y0, z0 = y * math.cos(-tilt) - z * math.sin(-tilt), y * math.sin(-tilt) + z * math.cos(-tilt)
        a = math.atan2(z0, x)
        core = (2.0 * math.cos(a), 0.0, 2.0 * math.sin(a))
        core = (core[0], core[1] * math.cos(tilt) - core[2] * math.sin(tilt), core[1] * math.sin(tilt) + core[2] * math.cos(tilt))
        n = tuple(cen[i] - core[i] for i in range(3))
        nl = math.sqrt(sum(c * c for c in n)) or 1
        n = tuple(c / nl for c in n)
        front = st.facing(n)
        face = [st.proj(p) for p in pts]
        if wire:
            polys.append((st.depth_of(pts), f'<polygon points="{st.pts_attr(face)}" fill="none" stroke="{pal.base if front else pal.hi}" '
                                            f'stroke-width="0.025" stroke-opacity="{1 if front else 0.3}"/>', face))
        elif front:
            b = max(0.0, st.dot(n, light))
            polys.append((st.depth_of(pts), st.poly(face, st.mix(pal.left, pal.cell, 0.15 + 0.85 * b),
                                                    ' stroke="#ffffff" stroke-width="0.012" stroke-opacity="0.6"'), face))
    body = "".join(svg for _, svg, _ in sorted(polys, key=lambda q: -q[0]))
    s.add(0, f"<g>{body}</g>", [p for _, _, f in polys for p in f])


def look_frustum(s, pal, apex, target, dist=0.9, hw=0.42, hh=0.32, depth_bias=0.0):
    f = [target[k] - apex[k] for k in range(3)]
    n = math.sqrt(sum(c * c for c in f))
    f = [c / n for c in f]
    right = (f[2], 0.0, -f[0])
    rn = math.hypot(right[0], right[2]) or 1
    right = (right[0] / rn, 0.0, right[2] / rn)
    up = (f[1] * right[2] - f[2] * right[1], f[2] * right[0] - f[0] * right[2], f[0] * right[1] - f[1] * right[0])
    c = [apex[k] + f[k] * dist for k in range(3)]
    quad = [tuple(c[k] + sx * hw * right[k] + sy * hh * up[k] for k in range(3)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    _lines(s, [(apex, q) for q in quad], pal.ink, 0.03, depth=st.depth_of(quad) + depth_bias)
    face = [st.proj(q) for q in quad]
    s.add(st.depth_of(quad) + depth_bias - 0.01, st.poly(face, pal.cell, f' stroke="{pal.ink}" stroke-width="0.035" fill-opacity="0.9"'), face)


def b_trajectory(title, pal):
    p = P[pal]
    s = st.Scene()
    st.cube(s, P["orange"], 2, 2, 2, x=-0.8, y=-0.8, z=-0.8, cell=0.8)
    path = [(4.0 * math.cos(a), 0.9 + 0.35 * math.sin(2 * a), 3.0 * math.sin(a)) for a in np.linspace(math.pi * 0.95, math.pi * 2.25, 60)]
    _lines(s, list(zip(path, path[1:])), P["slate"].hi, 0.045, dash="0.12 0.1", depth=40)
    for k in range(0, 60, 10):
        look_frustum(s, p, path[k], (0, 0, 0))
        _dot(s, path[k], 0.09, p.base)
    return s.to_svg(title)


def b_cost_volume(title, cmap_name="viridis", n=6, d=6, seed=3):
    s = st.Scene()
    rng = np.random.default_rng(seed)
    best = rng.integers(1, d - 1, (n, n))
    for k in range(d):
        cells = {}
        for r in range(n):
            for c in range(n):
                v = math.exp(-((k - best[r, c]) ** 2) / 1.5)
                cells[(r, c)] = CMAPS_HEX(cmap_name, 0.1 + 0.85 * v)
        st.slab(s, P["slate"], n, n, cell=0.62, z=k * 0.62, thick=0.2, colours=cells, margin=0.1, gap=0.05)
    return s.to_svg(title)


def CMAPS_HEX(name, t):  # noqa: N802  (matplotlib-style colour maps via OpenCV)
    table = {"viridis": cv2.COLORMAP_VIRIDIS, "magma": cv2.COLORMAP_MAGMA, "plasma": cv2.COLORMAP_PLASMA, "turbo": cv2.COLORMAP_TURBO,
             "inferno": cv2.COLORMAP_INFERNO}
    rgb = cv2.applyColorMap(np.array([[int(max(0, min(1, t)) * 255)]], np.uint8), table[name])[0, 0][::-1]
    return "#" + "".join(f"{int(v):02x}" for v in rgb)


def b_hashgrid(title):
    s = st.Scene()
    size = 4.8
    levels = [(4, P["orange"], 0.07), (8, P["teal"], 0.04), (16, P["purple"], 0.022)]
    st.extrude(s, st.rect(size, size), 0, 0.3, P["slate"], front="#f6f8fb")
    segs_all = []
    q = (2.95, 1.75)
    for n, pal, width in levels[::-1]:
        step = size / n
        segs = [((i * step, 0, 0), (i * step, size, 0)) for i in range(1, n)] + [((0, i * step, 0), (size, i * step, 0)) for i in range(1, n)]
        _lines(s, segs, pal.hi if n == 16 else pal.base, width, depth=-10 - n * 0.01, opacity=0.9)
        cx, cy = math.floor(q[0] / step) * step, math.floor(q[1] / step) * step
        segs_all.append(((cx, cy), step, pal))
    for (cx, cy), step, pal in segs_all:
        for dx in (0, step):
            for dy in (0, step):
                _dot(s, (cx + dx, cy + dy, 0), 0.11 if step < 0.5 else 0.14, pal.base, depth_bias=-60)
    _dot(s, (*q, 0), 0.15, P["coral"].base, depth_bias=-70)
    return s.to_svg(title)


def b_octree(title, pal):
    """An adaptive octree over a solid (a ground slab and a ball): full cells stay whole, partial cells split,
    leaves coloured by depth."""
    s = st.Scene()
    size = 4.0

    def inside(x, y, z):
        return y <= 1.0 or (x - 2.0) ** 2 + (y - 2.0) ** 2 + (z - 2.0) ** 2 <= 1.8 ** 2

    leaves = []

    def split(x, y, z, c, level):
        corners = [inside(x + i * c, y + j * c, z + k * c) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
        centre = inside(x + c / 2, y + c / 2, z + c / 2)
        if all(corners) and centre:
            leaves.append((x, y, z, c, level))
        elif level < 3 and (any(corners) or centre):
            h = c / 2
            for i in (0, 1):
                for j in (0, 1):
                    for k in (0, 1):
                        split(x + i * h, y + j * h, z + k * h, h, level + 1)
        elif centre:
            leaves.append((x, y, z, c, level))
    split(0, 0, 0, size, 0)
    tones = {1: P["purple"], 2: P[pal], 3: P["amber"]}
    for x, y, z, c, level in leaves:
        q = tones.get(level, P[pal])
        odd = (round(x / c) + round(y / c) + round(z / c)) % 2 * 0.22    # checker neighbouring cells of a level
        st.extrude(s, st.rect(c, c), z, c, q, origin=(x, y), front=st.mix(q.cell, q.hi, 0.45 + odd),
                   sides=lambda _p, n, q=q, o=odd: st.mix(q.cell, q.hi, o) if n[1] > 0.6 else st.mix(q.hi, q.base, o))
    _lines(s, _box_edges((size / 2, size / 2, size / 2), (size, size, size)), P["slate"].hi, 0.03, dash="0.1 0.08", depth=-90)
    return s.to_svg(title)


def b_lidar(title, seed=2):
    s = st.Scene()
    rng = np.random.default_rng(seed)
    objects = [((3.0, 1.2), (1.8, 0.8)), ((-2.6, 2.4), (1.0, 2.0)), ((1.2, -3.4), (2.0, 0.9)), ((-3.6, -1.8), (0.9, 1.8))]
    pts = []
    for ring in range(1, 9):
        rad = 0.9 + ring * 0.62
        for a in np.linspace(0, 2 * np.pi, int(40 + ring * 9), endpoint=False):
            x, z = rad * math.cos(a), rad * math.sin(a)
            hidden = any(abs(x - ox) < w / 2 + 0.6 and abs(z - oz) < d / 2 + 0.6 and rad > math.hypot(ox, oz)
                         and abs(math.atan2(z, x) - math.atan2(oz, ox)) < 0.32 for (ox, oz), (w, d) in objects)
            if not hidden:
                pts.append((x, 0.0, z, rad))
    for (ox, oz), (w, d) in objects:
        for _ in range(140):
            side = rng.integers(4)
            u = rng.uniform(-0.5, 0.5)
            h = rng.uniform(0, 0.9)
            if side == 0:
                x, z = ox - w / 2, oz + u * d
            elif side == 1:
                x, z = ox + u * w, oz - d / 2
            elif side == 2:
                x, z = ox + w / 2, oz + u * d
            else:
                x, z = ox + u * w, oz + d / 2
            pts.append((x, h, z, math.hypot(ox, oz)))
    body = []
    for x, y, z, rad in sorted(pts, key=lambda q: -st.dot(q[:3], st.D)):
        sx, sy = st.proj((x, y, z))
        body.append(f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="0.05" fill="{CMAPS_HEX("turbo", 0.12 + 0.8 * min(rad, 6.2) / 6.2)}"/>')
    s.add(10, "<g>" + "".join(body) + "</g>", [st.proj(q[:3]) for q in pts])
    st.cube(s, P["slate"], 1, 1, 2, x=-0.35, y=0, z=-0.7, cell=0.7)
    return s.to_svg(title)


OCC = {"road": "#b4bfcd", "walk": "#f4a6b3", "building": "#9b82f6", "car": "#f2717f", "tree": "#58c674", "trunk": "#a0785a",
       "pole": "#f5c93e"}


def b_occupancy(title):
    """Semantic occupancy: a street scene built from labelled voxels."""
    s = st.Scene()
    cells = {}
    n = 12
    for i in range(n):
        for k in range(n):
            cells[(i, 0, k)] = "walk" if i in (0, 1, n - 2, n - 1) else "road"
    for k in range(0, n, 1):
        for h in range(1, 4 if k % 5 else 3):
            cells[(0, h, k)] = "building"
            if k < 7:
                cells[(n - 1, h, k)] = "building"
    for (i, k) in ((4, 2), (4, 3), (7, 6), (7, 7), (4, 8), (4, 9)):
        cells[(i, 1, k)] = "car"
    for (i, k) in ((4, 2), (4, 8)):
        cells[(i, 2, k + 1)] = "car"
    for (i, k) in ((n - 2, 9),):
        cells[(i, 1, k)] = "trunk"
        cells[(i, 2, k)] = "trunk"
        for di in (-1, 0):
            for dk in (-1, 0, 1):
                cells[(i + di, 3, k + dk)] = "tree"
        cells[(i, 4, k)] = "tree"
    cells[(1, 1, 10)] = cells[(1, 2, 10)] = cells[(1, 3, 10)] = "pole"
    for (i, h, k), lab in cells.items():
        colour = OCC[lab]
        st.extrude(s, st.rect(1, 1), k * 1.0, 1.0, P["slate"], origin=(i, h), front=colour,
                   sides=lambda pal, nrm, c=colour: st.mix(c, "#ffffff", 0.25) if nrm[1] > 0.6 else st.mix(c, "#2b3442", 0.22))
    return s.to_svg(title)


def sdf_image(size=420):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size * 2 - 1
    circle = np.hypot(xx + 0.25, yy + 0.1) - 0.42
    q = np.abs(np.stack([xx - 0.3, yy - 0.25])) - np.array([0.28, 0.32])[:, None, None]
    box_d = np.hypot(np.maximum(q[0], 0), np.maximum(q[1], 0)) + np.minimum(np.maximum(q[0], q[1]), 0)
    d = np.minimum(circle, box_d)
    v = np.clip(0.5 + d * 0.9, 0, 1)
    stops = np.array([st._hex(c) for c in ("#3b4cc0", "#6788ee", "#c9d7f0", "#ffffff", "#edd1c2", "#e26952", "#b40426")])
    t = v * (len(stops) - 1)
    i = np.clip(t.astype(int), 0, len(stops) - 2)
    rgb = stops[i] + (stops[i + 1] - stops[i]) * (t - i)[..., None]
    rgb *= (0.86 + 0.14 * np.cos(d * 70))[..., None] ** 1.0
    rgb[np.abs(d) < 0.008] = (0.15, 0.17, 0.2)
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))


def b_sdf(title):
    s = st.Scene()
    photo_slab(s, sdf_image(), 4.0)
    return s.to_svg(title)


def b_ellipsoid(title, pal):
    """A 3-D Gaussian: its silhouette is the projection of the covariance, drawn with its principal axes."""
    p = P[pal]
    s = st.Scene()
    a, b = 0.6, 0.35
    rot_y = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    rot_z = np.array([[math.cos(b), -math.sin(b), 0], [math.sin(b), math.cos(b), 0], [0, 0, 1]])
    axes3 = rot_y @ rot_z @ np.diag([2.4, 1.1, 0.8])
    cov = axes3 @ axes3.T
    m = np.array([st.R, [-u for u in st.U]])
    vals, vecs = np.linalg.eigh(m @ cov @ m.T)
    rx, ry = math.sqrt(vals[1]), math.sqrt(vals[0])
    ang = math.degrees(math.atan2(vecs[1, 1], vecs[0, 1]))
    defs = (f'<defs><radialGradient id="ell" cx="0.4" cy="0.35" r="0.75"><stop offset="0" stop-color="{p.cell}"/>'
            f'<stop offset="0.65" stop-color="{p.hi}"/><stop offset="1" stop-color="{p.left}"/></radialGradient></defs>')
    s.add(5, f'<ellipse cx="0" cy="0" rx="{rx:.3f}" ry="{ry:.3f}" transform="rotate({ang:.2f})" fill="url(#ell)" fill-opacity="0.88"/>',
          [(-rx, -rx), (rx, rx)])
    for k, key in enumerate(("x", "y", "z")):
        v = axes3[:, k]
        _lines(s, [(tuple(-v), tuple(v))], AXIS[key], 0.05, depth=-50)
    _dot(s, (0, 0, 0), 0.12, "#3b4656", depth_bias=-60)
    return s.to_svg(title, defs=defs)


def sample_box(rng, centre, size, n):
    (cx, cy, cz), (w, h, d) = centre, size
    areas = [w * h, w * h, w * d, w * d, h * d, h * d]
    pts = []
    for _ in range(n):
        f = rng.choice(6, p=np.array(areas) / sum(areas))
        u, v = rng.uniform(-0.5, 0.5, 2)
        if f < 2:
            pts.append((cx + u * w, cy + v * h, cz + (f - 0.5) * d))
        elif f < 4:
            pts.append((cx + u * w, cy + (f - 2.5) * h, cz + v * d))
        else:
            pts.append((cx + (f - 4.5) * w, cy + u * h, cz + v * d))
    return pts


def sample_cylinder(rng, centre, radius, length, axis, n):
    pts = []
    for _ in range(n):
        a, t = rng.uniform(0, 2 * math.pi), rng.uniform(-0.5, 0.5) * length
        c = [radius * math.cos(a), radius * math.sin(a)]
        if axis == "x":
            pts.append((centre[0] + t, centre[1] + c[0], centre[2] + c[1]))
        else:   # along z
            pts.append((centre[0] + c[0], centre[1] + c[1], centre[2] + t))
    return pts


PART = ["#1e6fe0", "#f28a1c", "#2ea84f", "#e6485c", "#7a5ce3", "#17a398"]


def shape_points(kind, seed=0):
    rng = np.random.default_rng(seed)
    parts = []
    if kind == "car":
        parts.append(sample_box(rng, (0, 0.55, 0), (4.2, 0.75, 1.8), 700))
        parts.append(sample_box(rng, (-0.2, 1.22, 0), (2.2, 0.6, 1.6), 380))
        wheels = []
        for x in (-1.35, 1.35):
            for z in (-0.92, 0.92):
                wheels += sample_cylinder(rng, (x, 0.32, z), 0.32, 0.25, "z", 70)
        parts.append(wheels)
    elif kind == "chair":
        parts.append(sample_box(rng, (0, 1.2, 0), (1.8, 0.16, 1.8), 520))
        parts.append(sample_box(rng, (0, 2.3, 0.85), (1.8, 2.0, 0.14), 560))
        legs = []
        for x in (-0.78, 0.78):
            for z in (-0.78, 0.78):
                legs += sample_box(rng, (x, 0.56, z), (0.13, 1.12, 0.13), 70)
        parts.append(legs)
    else:   # airplane
        body = sample_cylinder(rng, (0, 0.9, 0), 0.34, 5.0, "x", 640)
        body = [(x, 0.9 + (y - 0.9) * (1 - max(0, (x - 1.5)) / 1.5 * 0.6), z) for x, y, z in body]
        parts.append(body)
        parts.append(sample_box(rng, (0.1, 0.8, 0), (1.1, 0.07, 5.0), 600))
        tail = sample_box(rng, (-2.25, 1.55, 0), (0.6, 1.0, 0.06), 120) + sample_box(rng, (-2.25, 1.05, 0), (0.55, 0.05, 1.8), 140)
        parts.append(tail)
        engines = sample_cylinder(rng, (0.35, 0.55, -1.3), 0.17, 0.8, "x", 80) + sample_cylinder(rng, (0.35, 0.55, 1.3), 0.17, 0.8, "x", 80)
        parts.append(engines)
    return parts


def b_shape_points(title, kind, pal=None, yaw=None):
    s = st.Scene()
    parts = shape_points(kind)
    yaw = {"airplane": -1.05, "chair": -0.5, "car": -0.35}[kind] if yaw is None else yaw
    c, sn = math.cos(yaw), math.sin(yaw)
    pts = []
    for i, part in enumerate(parts):
        for x, y, z in part:
            pts.append(((x * c - z * sn, y, x * sn + z * c), i))
    ys = [q[1] for q, _ in pts]
    lo, hi = min(ys), max(ys)
    body = []
    for q, i in sorted(pts, key=lambda t: -st.dot(t[0], st.D)):
        sx, sy = st.proj(q)
        colour = P[pal].ramp(0.25 + 0.7 * (q[1] - lo) / (hi - lo)) if pal else PART[i]
        body.append(f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="0.045" fill="{colour}"/>')
    s.add(0, "<g>" + "".join(body) + "</g>", [st.proj(q) for q, _ in pts])
    return s.to_svg(title)


def b_semantic_points(title, seed=6):
    rng = np.random.default_rng(seed)
    labelled = []
    labelled += [((x, 0, z), OCC["road"]) for x, z in rng.uniform([-4, -3], [4, 3], (900, 2))]
    labelled += [((x, 0, z), OCC["walk"]) for x, z in rng.uniform([-4, 2.2], [4, 3], (160, 2))]
    labelled += [(q, OCC["building"]) for q in sample_box(rng, (0, 1.5, 3.4), (8, 3, 0.6), 700)]
    for cx, cz in ((-1.8, -0.8), (1.6, 0.6)):
        labelled += [(q, OCC["car"]) for q in sample_box(rng, (cx, 0.55, cz), (2.0, 0.9, 1.0), 240)]
    for tx in (-3.2, 2.9):
        labelled += [(q, OCC["trunk"]) for q in sample_cylinder(rng, (tx, 0.7, 2.0), 0.1, 1.4, "z", 30)]
        for _ in range(220):
            v = rng.normal(0, 1, 3)
            v = v / np.linalg.norm(v) * 0.75
            labelled.append(((tx + v[0], 2.0 + v[1], 2.0 + v[2]), OCC["tree"]))
    s = st.Scene()
    body = []
    for q, colour in sorted(labelled, key=lambda t: -st.dot(t[0], st.D)):
        sx, sy = st.proj(q)
        body.append(f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="0.05" fill="{colour}"/>')
    s.add(0, "<g>" + "".join(body) + "</g>", [st.proj(q) for q, _ in labelled])
    return s.to_svg(title)


def blob_points(rng, n=700):
    pts = []
    for _ in range(n):
        u, v = rng.uniform(0, 2 * math.pi), math.acos(rng.uniform(-1, 1))
        r = 1.0 + 0.2 * math.sin(3 * u) * math.sin(2 * v)
        pts.append((2.2 * r * math.sin(v) * math.cos(u), 1.3 * r * math.cos(v), 1.5 * r * math.sin(v) * math.sin(u)))
    return pts


def b_point_groups(title, kind="fps", seed=3):
    """Farthest point sampling with ball-query neighbourhoods, or one point and its k nearest neighbours."""
    rng = np.random.default_rng(seed)
    pts = np.array(blob_points(rng))
    s = st.Scene()
    body = []
    front = pts[[st.dot(q, st.D) < 0.4 for q in pts]] if kind == "knn" else pts
    for q in sorted(pts.tolist(), key=lambda q: -st.dot(q, st.D)):
        sx, sy = st.proj(q)
        body.append(f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="0.04" fill="#9aa6b8"/>')
    s.add(10, "<g>" + "".join(body) + "</g>", [st.proj(q) for q in pts])
    if kind == "fps":
        chosen = [int(np.argmin(pts @ np.array(st.D)))]
        dist = np.linalg.norm(pts - pts[chosen[0]], axis=1)
        while len(chosen) < 9:
            nxt = int(np.argmax(dist))
            chosen.append(nxt)
            dist = np.minimum(dist, np.linalg.norm(pts - pts[nxt], axis=1))
        for i, c in enumerate(chosen):
            q = pts[c].tolist()
            sx, sy = st.proj(q)
            colour = P[ORDER_COLOURS[i % len(ORDER_COLOURS)]]
            s.add(st.dot(q, st.D) - 20, f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="0.55" fill="{colour.hi}" fill-opacity="0.28" '
                  f'stroke="{colour.base}" stroke-width="0.03"/>', [(sx - 0.55, sy - 0.55), (sx + 0.55, sy + 0.55)])
            _dot(s, q, 0.11, colour.base, depth_bias=-40)
    else:
        q0 = front[int(np.argmin(np.linalg.norm(front - front.mean(0), axis=1)))]
        near = np.argsort(np.linalg.norm(pts - q0, axis=1))[1:17]
        sx, sy = st.proj(q0.tolist())
        rad = max(math.dist((sx, sy), st.proj(pts[i].tolist())) for i in near) + 0.15
        s.add(-20, f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="{rad:.3f}" fill="{P["coral"].cell}" fill-opacity="0.45" '
              f'stroke="{P["coral"].base}" stroke-width="0.03"/>', [(sx - rad, sy - rad), (sx + rad, sy + rad)])
        _lines(s, [(q0.tolist(), pts[i].tolist()) for i in near], P["blue"].base, 0.035, depth=-30)
        for i in near:
            _dot(s, pts[i].tolist(), 0.08, P["blue"].base, depth_bias=-31)
        _dot(s, q0.tolist(), 0.14, P["coral"].base, depth_bias=-40)
    return s.to_svg(title)


ORDER_COLOURS = ["blue", "orange", "teal", "purple", "coral", "green", "amber", "blue", "orange"]


# ------------------------------------------------------------------ catalogue
def build_specs():
    for key, (_, _, _, zh, _) in COMMONS.items():
        if key != "pose" and key not in MEDICAL:
            add(f"photo-{key}", INPUT, f"输入图像：{zh}", f"input photo: {key}", ["输入图像", "照片", zh],
                (lambda k=key: square(k) if COMMONS[k][4] else wide(k)), key)
    for key, (_, _, _, zh) in SKIMAGE.items():
        if key not in MEDICAL:
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

    # degraded inputs for restoration
    restore = ["图像复原", "退化", "低层视觉"]
    add("degrade-noise-bird", INPUT, "噪声图像 σ=30（翠鸟）", "noisy image, sigma 30 (bird)", restore + ["去噪", "高斯噪声"],
        lambda: gaussian_noise(square("bird")), "bird")
    add("degrade-lowlight-room", INPUT, "低光照图像（室内）", "low-light image (room)", restore + ["低光增强", "暗光"],
        lambda: low_light(wide("room")), "room")
    add("degrade-haze-street", INPUT, "雾天图像（街景）", "hazy image (street)", restore + ["去雾", "大气散射"],
        lambda: hazy(wide("street")), "street")
    add("degrade-rain-road", INPUT, "雨天图像（道路）", "rainy image (road)", restore + ["去雨", "雨纹"], lambda: rainy(wide("road")), "road")
    add("degrade-jpeg-cat", INPUT, "JPEG 压缩伪影（猫）", "JPEG artefacts (cat)", restore + ["压缩伪影", "JPEG"],
        lambda: jpeg(square("cat", 384)).resize((SIDE, SIDE), Image.Resampling.NEAREST), "cat")
    add("degrade-motion-car", INPUT, "运动模糊（汽车）", "motion blur (car)", restore + ["去模糊", "运动模糊"],
        lambda: motion_blur(square("car")), "car")
    add("inpaint-holes-dog", INPUT, "待修复的缺损图像（狗）", "image with holes to inpaint (dog)", restore + ["图像修复", "inpainting"],
        lambda: with_holes(square("dog"), stroke_mask(SIDE)), "dog")
    add("inpaint-mask", INPUT, "自由形状修复掩码", "free-form inpainting mask", ["图像修复", "掩码", "inpainting", "mask"],
        lambda: Image.fromarray(stroke_mask(SIDE)), None)

    # more augmentations
    aug_tags = ["数据增强", "augmentation"]
    add("aug-mixup", INPUT, "数据增强：MixUp（猫 + 狗）", "augmentation: MixUp (cat + dog)", aug_tags + ["MixUp", "混合"],
        lambda: mixup(square("cat"), square("dog")), "cat")
    add("aug-cutmix", INPUT, "数据增强：CutMix（狗 + 猫）", "augmentation: CutMix (dog + cat)", aug_tags + ["CutMix", "裁剪混合"],
        lambda: cutmix(square("dog"), square("cat"), (420, 330, 720, 630)), "dog")
    add("aug-mosaic", INPUT, "数据增强：Mosaic 四图拼接", "augmentation: Mosaic", aug_tags + ["Mosaic", "YOLO", "拼接"],
        lambda: mosaic([square("dog"), square("car"), square("bird"), wide("street")]), "dog")
    add("aug-solarize-dog", INPUT, "数据增强：曝光反转（狗）", "augmentation: solarize (dog)", aug_tags + ["Solarize", "RandAugment"],
        lambda: ImageOps.solarize(square("dog"), 128), "dog")
    add("aug-posterize-dog", INPUT, "数据增强：色阶分离（狗）", "augmentation: posterize (dog)", aug_tags + ["Posterize", "RandAugment"],
        lambda: ImageOps.posterize(square("dog"), 2), "dog")
    add("aug-perspective-dog", INPUT, "数据增强：透视变换（狗）", "augmentation: perspective (dog)", aug_tags + ["透视变换", "几何变换"],
        lambda: perspective(square("dog")), "dog")
    add("aug-erasing-dog", INPUT, "数据增强：随机擦除（狗）", "augmentation: random erasing (dog)", aug_tags + ["Random Erasing", "遮挡"],
        lambda: random_erasing(square("dog")), "dog")
    add("aug-gridmask-dog", INPUT, "数据增强：GridMask 网格遮挡（狗）", "augmentation: GridMask (dog)", aug_tags + ["GridMask", "遮挡"],
        lambda: gridmask(square("dog")), "dog")
    add("sobel-cat", INPUT, "梯度幅值图（Sobel，猫）", "gradient magnitude, Sobel (cat)", ["梯度", "Sobel", "边缘", "高频"],
        lambda: sobel_magnitude(square("cat")), "cat")

    # CNN-like feature maps from photos
    feat = ["特征图", "特征可视化", "CNN", "激活"]
    add("featgrid-cat-viridis", FEATURE, "特征图通道可视化 4×4（猫，Viridis）", "16 feature channels (cat, viridis)", feat + ["通道"],
        lambda: channel_grid(square("cat"), cv2.COLORMAP_VIRIDIS), "cat")
    add("featgrid-cat-grey", FEATURE, "特征图通道可视化 4×4（猫，灰度）", "16 feature channels (cat, grey)", feat + ["通道", "灰度"],
        lambda: channel_grid(square("cat"), None), "cat")
    add("featgrid-dog-magma", FEATURE, "特征图通道可视化 4×4（狗，Magma）", "16 feature channels (dog, magma)", feat + ["通道"],
        lambda: channel_grid(square("dog"), cv2.COLORMAP_MAGMA), "dog")
    for key, cmap, zh, en in (("cat", cv2.COLORMAP_VIRIDIS, "Viridis", "viridis"), ("cat", "blue", "蓝色", "blue"),
                              ("dog", cv2.COLORMAP_MAGMA, "Magma", "magma"), ("street", cv2.COLORMAP_TURBO, "Turbo", "turbo")):
        add(f"featstack-{key}-{en}", FEATURE, f"真实感特征图堆叠（{COMMONS[key][3]}，{zh}）", f"stacked feature maps ({key}, {en})",
            feat + ["多通道", "等轴测"], ("svg", lambda k=key, c=cmap: iso_feature_stack(square(k, 640), c)), key)
    add("backbone-cat", FEATURE, "输入图像与逐级特征图（猫）", "input image and backbone feature maps (cat)", feat + ["骨干网络", "下采样"],
        ("svg", lambda: iso_backbone(square("cat", 512), cv2.COLORMAP_VIRIDIS)), "cat")
    add("backbone-street", FEATURE, "输入图像与逐级特征图（街景）", "input image and backbone feature maps (street)",
        feat + ["骨干网络", "多尺度"], ("svg", lambda: iso_backbone(square("street", 512), "blue", seed=2)), "street")

    # patches and tokens on isometric planes
    add("iso-tokens-cat", INPUT, "图像块 Token 序列（猫，等轴测）", "patch tokens in a row (cat)", ["Patch Embedding", "Token", "ViT", "等轴测"],
        ("svg", lambda: iso_tokens(square("cat", 576))), "cat")
    add("iso-tokens-dog", INPUT, "图像块 Token 序列（狗，等轴测）", "patch tokens in a row (dog)", ["Patch Embedding", "Token", "ViT"],
        ("svg", lambda: iso_tokens(square("dog", 576))), "dog")
    add("iso-exploded-cat", INPUT, "斜置分块展开（猫）", "exploded patches on an isometric plane (cat)", ["图像分块", "patch", "ViT", "等轴测"],
        ("svg", lambda: iso_exploded(square("cat", 640))), "cat")
    add("iso-mae-cat", INPUT, "斜置随机掩码（猫，MAE）", "MAE masking on an isometric plane (cat)", ["MAE", "掩码", "自监督", "等轴测"],
        ("svg", lambda: iso_exploded(square("cat", 640), masked=mae_cells(4, 0.6, 3))), "cat")
    add("iso-mae-dog", INPUT, "斜置随机掩码（狗，MAE）", "MAE masking on an isometric plane (dog)", ["MAE", "掩码", "自监督"],
        ("svg", lambda: iso_exploded(square("dog", 640), masked=mae_cells(4, 0.6, 11))), "dog")

    def road_clip(n=4, step=50):
        image = photo("road")
        w = round(image.height * 4 / 3)
        return [image.crop((x, 0, x + w, image.height)).resize((640, 480), Image.Resampling.LANCZOS) for x in range(0, n * step, step)]
    add("tubelet-road", INPUT, "视频时空块（Tubelet，道路）", "video tubelet (road)", ["视频", "Tubelet", "ViViT", "时空"],
        ("svg", lambda: iso_tubelet(road_clip())), "road")
    add("mpi-street", THREE_D, "多平面图像（MPI，街景）", "multi-plane image (street)", ["MPI", "多平面图像", "新视角合成", "分层"],
        ("svg", lambda: iso_mpi(wide("street", 800).crop((60, 0, 740, 510)))), "street")

    # prompts and annotations
    def sam_points(image):
        def draw(d, k):
            for x, y in ((390, 230), (310, 440)):
                point_marker(d, k, x, y, (46, 168, 79))
            for x, y in ((690, 560), (110, 110)):
                point_marker(d, k, x, y, (230, 72, 92))
        return annotate(image, draw)
    add("prompt-points-dog", TASK, "点提示（SAM，正负点，狗）", "point prompts (dog)", ["SAM", "点提示", "交互式分割", "prompt"],
        lambda: sam_points(square("dog")), "dog")
    add("prompt-box-car", TASK, "框提示（SAM，汽车）", "box prompt (car)", ["SAM", "框提示", "交互式分割", "prompt"],
        lambda: annotate(square("car"), lambda d, k: dashed_box(d, k, (34, 232, 730, 706), (30, 111, 224))), "car")
    add("prompt-mask-dog", TASK, "点提示与分割结果（狗）", "point prompt and predicted mask (dog)", ["SAM", "分割结果", "提示"],
        lambda: sam_points(overlay_mask(square("dog"), grabcut(square("dog"), seg["dog"][0]), (88, 196, 255))), "dog")

    def polygon(key, rect, colour):
        image = square(key)
        m = grabcut(image, rect)
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        poly_pts = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 9, True).reshape(-1, 2)

        def draw(d, k):
            pts = [(x * k, y * k) for x, y in poly_pts]
            d.polygon(pts, fill=colour + (70,))
            d.line(pts + pts[:1], fill=colour + (255,), width=4 * k, joint="curve")
            for x, y in pts:
                d.ellipse((x - 7 * k, y - 7 * k, x + 7 * k, y + 7 * k), fill=(255, 255, 255, 255), outline=colour + (255,), width=3 * k)
        return annotate(image, draw)
    add("polygon-dog", TASK, "多边形标注（狗）", "polygon annotation (dog)", ["多边形标注", "标注", "实例分割", "LabelMe"],
        lambda: polygon("dog", seg["dog"][0], (122, 92, 227)), "dog")
    add("polygon-bird", TASK, "多边形标注（翠鸟）", "polygon annotation (bird)", ["多边形标注", "标注"],
        lambda: polygon("bird", seg["bird"][0], (230, 72, 92)), "bird")

    def scribbles():
        fg = [smooth_path([(300, 170), (390, 250), (330, 330), (300, 450), (420, 470), (560, 380)]),
              smooth_path([(140, 650), (250, 600), (380, 565)])]
        bg = [smooth_path([(470, 650), (600, 600), (735, 655)]), smooth_path([(40, 330), (95, 220), (175, 70)])]

        def draw(d, k):
            for line in fg:
                d.line([(x * k, y * k) for x, y in line], fill=(46, 168, 79, 255), width=14 * k, joint="curve")
            for line in bg:
                d.line([(x * k, y * k) for x, y in line], fill=(230, 72, 92, 255), width=14 * k, joint="curve")
        return annotate(square("dog"), draw)
    add("scribble-dog", TASK, "涂鸦标注（前景 / 背景，狗）", "scribble annotation (dog)", ["涂鸦标注", "弱监督", "scribble"], scribbles, "dog")

    def yolo_grid(n=7):
        image = square("dog")
        m = grabcut(image, seg["dog"][0])
        ys, xs = np.nonzero(m)
        box = (xs.min(), ys.min(), xs.max(), ys.max())
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        cell = SIDE / n
        c, r = int(cx // cell), int(cy // cell)

        def draw(d, k):
            d.rectangle((c * cell * k, r * cell * k, (c + 1) * cell * k, (r + 1) * cell * k), fill=(242, 138, 28, 150))
            for i in range(1, n):
                d.line([(i * cell * k, 0), (i * cell * k, SIDE * k)], fill=(255, 255, 255, 230), width=3 * k)
                d.line([(0, i * cell * k), (SIDE * k, i * cell * k)], fill=(255, 255, 255, 230), width=3 * k)
            d.rectangle(tuple(v * k for v in box), outline=(242, 138, 28, 255), width=5 * k)
            d.ellipse(((cx - 9) * k, (cy - 9) * k, (cx + 9) * k, (cy + 9) * k), fill=(255, 255, 255, 255), outline=(242, 138, 28, 255),
                      width=4 * k)
        return annotate(image, draw)
    add("yolo-grid-dog", TASK, "YOLO 网格划分与负责单元（狗）", "YOLO grid and responsible cell (dog)", ["YOLO", "网格", "目标检测", "单阶段"],
        yolo_grid, "dog")

    # medical images
    med = ["医学影像", "医学图像"]
    add("photo-xray", MED, "输入图像：胸部 X 光片", "chest X-ray", med + ["X 光", "胸片", "放射"], lambda: square("xray"), "xray")
    add("photo-ct", MED, "输入图像：脑部 CT 切片", "brain CT slice", med + ["CT", "断层", "脑部"], lambda: ct_slice(16, 600), "ct")
    add("photo-mri", MED, "输入图像：脑部 MRI（T1）", "brain MRI, T1", med + ["MRI", "磁共振", "脑部"], lambda: square("mri", 481), "mri")
    add("photo-skin", MED, "输入图像：皮肤组织切片（H&E）", "H&E skin section", med + ["病理", "H&E", "组织切片"], lambda: wide("skin"), "skin")
    add("photo-mitosis", MED, "输入图像：荧光细胞核", "fluorescent cell nuclei", med + ["细胞", "荧光", "显微镜"],
        lambda: photo("mitosis").crop((128, 128, 512, 512)).resize((SIDE, SIDE), Image.Resampling.BICUBIC), "mitosis")
    add("photo-kidney", MED, "输入图像：肾组织共聚焦荧光图", "confocal fluorescence of kidney tissue", med + ["荧光", "共聚焦", "组织"],
        lambda: photo("kidney").copy(), "kidney")
    add("ct-volume", MED, "CT 切片堆叠（体数据）", "stack of CT slices (volume)", med + ["CT", "体数据", "三维", "切片"],
        ("svg", lambda: iso_stack([ct_slice(i, 360) for i in (19, 18, 17, 16, 15, 14)], 3.4, (0.22, 0.16, 0.62))), "ct")
    add("iso-mri", MED, "斜置图像平面（MRI）", "MRI on an isometric plane", med + ["MRI", "图像平面", "等轴测"],
        ("svg", lambda: iso_photo(square("mri", 481))), "mri")
    add("iso-xray", MED, "斜置图像平面（胸片）", "chest X-ray on an isometric plane", med + ["X 光", "图像平面", "等轴测"],
        ("svg", lambda: iso_photo(square("xray", 640))), "xray")
    add("iso-ct", MED, "斜置图像平面（CT）", "CT slice on an isometric plane", med + ["CT", "图像平面", "等轴测"],
        ("svg", lambda: iso_photo(ct_slice(16, 480))), "ct")
    add("kidney-channels", MED, "多通道荧光图像分离", "fluorescence channels split", med + ["多通道", "荧光", "通道"],
        ("svg", lambda: iso_stack(fluorescence(square("kidney", 480)), 3.6, (0.42, 0.42, 1.0))), "kidney")
    add("nuclei-labels", MED, "细胞核实例分割标签", "nucleus instance labels", med + ["实例分割", "细胞分割", "watershed"],
        lambda: nuclei_view("labels"), "mitosis")
    add("nuclei-contours", MED, "细胞核分割轮廓叠加", "nucleus contours overlaid", med + ["实例分割", "细胞分割", "轮廓"],
        lambda: nuclei_view("contours"), "mitosis")
    add("nuclei-boxes", MED, "细胞检测框", "cell detection boxes", med + ["细胞检测", "目标检测", "显微镜"],
        lambda: nuclei_view("boxes"), "mitosis")
    add("mri-tissue", MED, "脑组织三类分割（MRI）", "brain tissue classes (MRI)", med + ["脑组织分割", "灰质", "白质", "脑脊液"],
        lambda: brain_tissue("labels"), "mri")
    add("mri-tissue-overlay", MED, "脑组织分割叠加（MRI）", "brain tissue classes overlaid (MRI)", med + ["脑组织分割", "叠加"],
        lambda: brain_tissue("overlay"), "mri")
    add("wsi-tiles", MED, "病理切片分块与组织筛选", "whole-slide tiling with tissue tiles", med + ["病理", "WSI", "分块", "多示例学习"],
        wsi_tiles, "skin")

    # 3-D schematics
    add("axes", THREE_D, "三维坐标轴", "3D coordinate axes", ["坐标轴", "坐标系", "XYZ", "三维"], ("svg", lambda: lambda title: b_axes(title)))
    add("axes-frame", THREE_D, "物体与局部坐标系", "object with its local frame", ["坐标系", "位姿", "6D 位姿", "旋转"],
        ("svg", lambda: lambda title: b_axes(title, frame=True)))
    for pal in ("blue", "teal", "orange"):
        add(f"mesh-sphere-{pal}", THREE_D, f"三角网格球体（{P[pal].zh}）", f"triangle mesh sphere ({pal})", ["网格", "mesh", "三维重建", "表面"],
            ("svg", lambda p=pal: lambda title: b_mesh(title, p)))
    add("mesh-sphere-wire", THREE_D, "网格线框球体", "wireframe mesh sphere", ["网格", "线框", "wireframe", "mesh"],
        ("svg", lambda: lambda title: b_mesh(title, "purple", wire=True)))
    add("mesh-torus", THREE_D, "圆环网格", "torus mesh", ["网格", "mesh", "圆环", "表面"], ("svg", lambda: lambda title: b_mesh(title, "purple", "torus")))
    add("mesh-torus-wire", THREE_D, "圆环线框", "wireframe torus", ["网格", "线框", "圆环"],
        ("svg", lambda: lambda title: b_mesh(title, "teal", "torus", wire=True)))
    add("trajectory", THREE_D, "相机轨迹（环绕拍摄）", "camera trajectory around an object", ["相机轨迹", "SLAM", "位姿", "多视角"],
        ("svg", lambda: lambda title: b_trajectory(title, "blue")))
    add("cost-volume", THREE_D, "代价体（视差 × 高 × 宽）", "cost volume", ["代价体", "立体匹配", "cost volume", "视差"],
        ("svg", lambda: lambda title: b_cost_volume(title)))
    add("cost-volume-magma", THREE_D, "代价体（Magma）", "cost volume, magma", ["代价体", "多视图立体", "MVS", "深度"],
        ("svg", lambda: lambda title: b_cost_volume(title, "magma", seed=8)))
    add("hashgrid", THREE_D, "多分辨率哈希网格", "multi-resolution hash grid", ["哈希编码", "Instant-NGP", "多分辨率", "网格"],
        ("svg", lambda: lambda title: b_hashgrid(title)))
    add("octree", THREE_D, "八叉树划分", "octree subdivision", ["八叉树", "octree", "稀疏体素", "层级"],
        ("svg", lambda: lambda title: b_octree(title, "blue")))
    add("lidar-scan", THREE_D, "激光雷达扫描（按距离着色）", "LiDAR scan coloured by range", ["激光雷达", "LiDAR", "点云", "自动驾驶"],
        ("svg", lambda: lambda title: b_lidar(title)))
    add("occupancy", THREE_D, "语义占据栅格（街景体素）", "semantic occupancy voxels", ["语义占据", "体素", "Occupancy", "自动驾驶"],
        ("svg", lambda: lambda title: b_occupancy(title)))
    add("sdf-slice", THREE_D, "符号距离场切片（SDF）", "signed distance field slice", ["SDF", "符号距离场", "隐式表示", "等值线"],
        ("svg", lambda: lambda title: b_sdf(title)))
    add("gaussian-ellipsoid", THREE_D, "单个三维高斯椭球", "single 3D Gaussian ellipsoid", ["3DGS", "高斯", "协方差", "椭球"],
        ("svg", lambda: lambda title: b_ellipsoid(title, "purple")))
    for kind, zh in (("car", "汽车"), ("chair", "椅子"), ("airplane", "飞机")):
        add(f"points-{kind}", THREE_D, f"{zh}点云（按部件着色）", f"{kind} point cloud, part colours", ["点云", "部件分割", "ShapeNet", zh],
            ("svg", lambda k=kind: lambda title: b_shape_points(title, k)))
    add("points-airplane-blue", THREE_D, "飞机点云（按高度着色）", "airplane point cloud, height colours", ["点云", "ModelNet", "飞机"],
        ("svg", lambda: lambda title: b_shape_points(title, "airplane", "blue")))
    add("points-street", THREE_D, "街景语义点云", "semantic street point cloud", ["点云", "语义分割", "街景", "激光雷达"],
        ("svg", lambda: lambda title: b_semantic_points(title)))
    add("points-fps", THREE_D, "最远点采样与球查询", "farthest point sampling and ball query", ["FPS", "最远点采样", "PointNet++", "球查询"],
        ("svg", lambda: lambda title: b_point_groups(title)))
    add("points-knn", THREE_D, "点云局部 K 近邻", "k nearest neighbours in a point cloud", ["KNN", "邻域", "DGCNN", "点云"],
        ("svg", lambda: lambda title: b_point_groups(title, "knn")))


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
                        "研图视觉图元：统一等轴测风格的三维视觉示意，SVG 可直接编辑，CC0 发布。" if isinstance(maker, tuple) else
                        "研图视觉图元：由脚本直接生成的示意图像，CC0 发布。"),
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
