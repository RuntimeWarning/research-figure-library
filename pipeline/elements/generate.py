#!/usr/bin/env python3
"""Generate the 研图 element library: generic building blocks for model figures.

All elements share one look (see ``style.py``): flat-shaded isometric solids,
inset grid cells and an eight-colour palette.  Each element is written as an
editable SVG plus a transparent PNG and a WebP thumbnail under
``dist/assets/elements/``; metadata goes to ``pipeline/manifests/elements.json``.

The elements are original work of this project and are released under CC0 1.0.
"""
from __future__ import annotations

import io
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import resvg_py
from PIL import Image

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from common import ASSETS, MANIFESTS, sha256, write_json  # noqa: E402
import style as st  # noqa: E402
from style import PALETTES as P, ORDER  # noqa: E402

OUT = ASSETS / "elements"
PNG_SIDE = 1024
THUMB_SIDE = 420
# Shared by every element source (originals here, collected ones in ``pipeline/collected``).
CATEGORIES = ["特征图", "张量与通道", "卷积与采样", "Token 与嵌入", "注意力与 Transformer", "神经元与全连接",
              "网络结构与模块", "图像输入与预处理", "检测、分割与关键点", "三维视觉", "运算符", "图与点云", "时空与气象", "信号与噪声",
              "数据与文档", "计算与设备", "人物与智能体", "科学与医学", "天气与地理", "城市与交通", "动物与植物",
              "标记与符号", "通用物件"]
SPECS = []          # (id, builder, kwargs, meta)


def add(eid, category, zh, en, tags, fn, desc="", **kw):
    assert category in CATEGORIES, category
    SPECS.append((eid, fn, kw, {"id": eid, "category": category, "name": zh, "english": en, "tags": tags,
                                "description": desc}))


# ------------------------------------------------------------------ helpers
def pattern(kind, rows, cols, seed=0):
    """Cells to highlight: returns {(r, c): level} with level 1 (hi) or 2 (ink)."""
    r = st.rng(seed)
    if kind == "none":
        return {}
    if kind == "center":
        return {(rows // 2, cols // 2): 1}
    if kind == "diag":
        return {(i, i): 1 for i in range(min(rows, cols))}
    if kind == "scatter":
        n = max(2, rows * cols // 8)
        cells = r.sample([(i, j) for i in range(rows) for j in range(cols)], n)
        return {c: 1 for c in cells}
    if kind == "window":
        return {(i, j): 1 for i in range(1, 4) for j in range(1, 4) if i < rows and j < cols}
    if kind == "cross":
        return {**{(rows // 2, j): 1 for j in range(cols)}, **{(i, cols // 2): 1 for i in range(rows)}}
    if kind == "corner":
        return {(i, j): 1 for i in range(rows // 2) for j in range(cols // 2)}
    raise ValueError(kind)


def colour_cells(pal, cells):
    return {k: (pal.hi if v == 1 else pal.ink) for k, v in cells.items()}


def heat(pal, rows, cols, fn):
    return {(r, c): pal.ramp(fn(r / max(rows - 1, 1), c / max(cols - 1, 1))) for r in range(rows) for c in range(cols)}


def blob(r, c, cx=0.45, cy=0.5, s=0.28):
    return math.exp(-((r - cy) ** 2 + (c - cx) ** 2) / (2 * s * s))


PRECIP = ["#e8eef3", "#bfe6b8", "#7fd17a", "#34b44a", "#f2d22e", "#f59a1f", "#e8452c", "#b82fbf"]
TEMP = ["#2b6cb0", "#5b9bd5", "#9cc7ea", "#e8eef3", "#f6b48f", "#e9764f", "#c0392b"]


def ramp_list(colours, t):
    t = max(0.0, min(0.9999, t))
    i = t * (len(colours) - 1)
    k = int(i)
    return st.mix(colours[k], colours[k + 1], i - k)


def field(rows, cols, seed, blobs=4, shift=(0.0, 0.0)):
    g = st.rng(seed)
    centres = [(g.random(), g.random(), 0.12 + g.random() * 0.18, 0.5 + g.random() * 0.6) for _ in range(blobs)]
    out = {}
    for r in range(rows):
        for c in range(cols):
            y, x = r / (rows - 1), c / (cols - 1)
            v = sum(a * math.exp(-((x - cx - shift[0]) ** 2 + (y - cy - shift[1]) ** 2) / (2 * s * s)) for cx, cy, s, a in centres)
            v += (g.random() - 0.5) * 0.12
            out[(r, c)] = v
    return out


# ------------------------------------------------------------------ builders (each returns an SVG string)
def b_feature_map(title, pal, rows, cols, kind="none", seed=0, thick=0.42):
    s = st.Scene()
    st.slab(s, P[pal], cols, rows, colours=colour_cells(P[pal], pattern(kind, rows, cols, seed)), thick=thick)
    return s.to_svg(title)


def b_heat_map(title, pal, rows=6, cols=6, mode="blob"):
    p = P[pal]
    fns = {"blob": lambda r, c: blob(r, c), "diag": lambda r, c: math.exp(-((r - c) ** 2) / 0.06),
           "grad": lambda r, c: (r + c) / 2, "ring": lambda r, c: abs(math.hypot(r - .5, c - .5) - .32) < .14}
    s = st.Scene()
    st.slab(s, p, cols, rows, colours=heat(p, rows, cols, lambda r, c: float(fns[mode](r, c))))
    return s.to_svg(title)


def b_sequence(title, pals, sizes, direction="down"):
    """Feature maps placed one behind the other, like the stages of a network."""
    s = st.Scene()
    x = 0.0
    z = 0.0
    for i, (pal, n) in enumerate(zip(pals, sizes)):
        p = P[pal]
        big = max(sizes)
        y = (big - n) * 0.5 * 0.35
        cells = colour_cells(p, pattern("scatter" if n >= 5 else "center", n, n, seed=i + 3))
        st.slab(s, p, n, n, x=x, y=y, z=z, colours=cells)
        x += n * 0.5 + 0.2
        z -= n * 0.62 + 0.5
    return s.to_svg(title)


def b_cube(title, pal, cols, rows, layers, accent=None):
    p = P[pal]
    s = st.Scene()
    front = colour_cells(p, pattern(accent, rows, cols, 5)) if accent else None
    st.cube(s, p, cols, rows, layers, colours=front)
    return s.to_svg(title)


def b_stack(title, pals, n, cols=4, rows=4, gap=0.75):
    s = st.Scene()
    for i in range(n):
        pal = P[pals[i % len(pals)]]
        st.slab(s, pal, cols, rows, z=i * gap, thick=0.3)
    return s.to_svg(title)


def b_concat(title, pal_a, pal_b):
    s = st.Scene()
    st.cube(s, P[pal_a], 3, 3, 2, z=0)
    st.cube(s, P[pal_b], 3, 3, 2, z=2.0)
    return s.to_svg(title)


def b_conv(title, pal_in, pal_out, k=3):
    """Input map with a k x k window projected onto one cell of the output map."""
    a, b = P[pal_in], P[pal_out]
    s = st.Scene()
    n_in, n_out = 6, 4
    win = {(i, j): 1 for i in range(1, 1 + k) for j in range(1, 1 + k)}
    st.slab(s, a, n_in, n_in, colours=colour_cells(a, win))
    ox, oy, oz = 5.4, 1.0, -4.2
    st.slab(s, b, n_out, n_out, x=ox, y=oy, z=oz, colours={(1, 1): b.hi})
    # window corners on the input face, target cell corners on the output face
    m, g = 0.13, 0.09
    cw = (n_in - 2 * m - (n_in - 1) * g) / n_in
    x0, x1 = m + 1 * (cw + g), m + (k + 1) * (cw + g) - g
    y1, y0 = n_in - m - 1 * (cw + g), n_in - m - (k + 1) * (cw + g) + g
    cwo = (n_out - 2 * m - (n_out - 1) * g) / n_out
    tx0, tx1 = ox + m + (cwo + g), ox + m + 2 * (cwo + g) - g
    ty1, ty0 = oy + n_out - m - (cwo + g), oy + n_out - m - 2 * (cwo + g) + g
    lines = "".join(st.line3((px, py, 0), (qx, qy, oz), a.ink, 0.045, dash="0.16 0.12", opacity=0.75)
                    for (px, py), (qx, qy) in [((x0, y0), (tx0, ty0)), ((x1, y0), (tx1, ty0)),
                                               ((x1, y1), (tx1, ty1)), ((x0, y1), (tx0, ty1))])
    s.add(-99, f"<g>{lines}</g>", [st.proj((x0, y0, 0)), st.proj((tx1, ty1, oz))])
    return s.to_svg(title)


def b_kernel(title, pal, k, seed=0):
    p = P[pal]
    g = st.rng(seed)
    s = st.Scene()
    if k == 1:   # a 1 x 1 convolution acts along channels: draw it as a channel column
        st.cube(s, p, 1, 1, 4, colours={(0, 0): p.hi})
        return s.to_svg(title)
    cells = {(r, c): st.mix(p.cell, p.hi, 0.15 + 0.85 * g.random()) for r in range(k) for c in range(k)}
    cells[(k // 2, k // 2)] = p.base
    st.slab(s, p, k, k, colours=cells, thick=0.5)
    return s.to_svg(title)


def b_pooling(title, mode="max"):
    s = st.Scene()
    quads = ["blue", "teal", "orange", "purple"]
    cells = {}
    for r in range(4):
        for c in range(4):
            q = P[quads[(r // 2) * 2 + c // 2]]
            strong = (r % 2, c % 2) == ((r // 2 + c // 2) % 2, (r // 2) % 2)
            cells[(r, c)] = q.hi if (mode == "max" and strong) else q.cell
    pal = P["slate"]
    st.slab(s, pal, 4, 4, colours=cells)
    out = {(r, c): (P[quads[r * 2 + c]].hi if mode == "max" else st.mix(P[quads[r * 2 + c]].cell, P[quads[r * 2 + c]].hi, .5))
           for r in range(2) for c in range(2)}
    st.slab(s, pal, 2, 2, x=4.3, y=1.0, z=-3.2, colours=out)
    return s.to_svg(title)


def b_dilated(title, pal, rate=2):
    p = P[pal]
    n = 7
    centre = n // 2
    cells = {(centre + i * rate, centre + j * rate): p.hi for i in (-1, 0, 1) for j in (-1, 0, 1)}
    cells[(centre, centre)] = p.ink
    s = st.Scene()
    st.slab(s, p, n, n, colours=cells)
    return s.to_svg(title)


def b_receptive(title, pal):
    p = P[pal]
    s = st.Scene()
    sizes = [7, 5, 3]
    hi = [{(i, j): p.hi for i in range(1, 6) for j in range(1, 6)}, {(i, j): p.hi for i in range(1, 4) for j in range(1, 4)},
          {(1, 1): p.ink}]
    x = 0
    z = 0
    for n, cells in zip(sizes, hi):
        st.slab(s, p, n, n, x=x, y=(7 - n) * 0.5, z=z, colours=cells, thick=0.3)
        x += 0.6
        z -= 2.6
    return s.to_svg(title)


def b_patches(title, flatten=False):
    s = st.Scene()
    n = 4
    cols = [P[k] for k in ORDER[:8]]
    g = st.rng(7)
    cells = {(r, c): cols[(r * n + c) % 8].hi for r in range(n) for c in range(n)}
    st.slab(s, P["slate"], n, n, colours=cells, gap=0.16)
    if flatten:
        for i in range(8):
            pal = cols[i % 8]
            st.extrude(s, st.rect(0.62, 0.62), -3.0, 0.62, pal, origin=(5.0 + i * 0.85, 0.4), front=pal.hi)
    return s.to_svg(title)


def b_upsample(title):
    s = st.Scene()
    q = ["blue", "teal", "orange", "purple"]
    st.slab(s, P["slate"], 2, 2, colours={(r, c): P[q[r * 2 + c]].hi for r in range(2) for c in range(2)})
    big = {(r, c): (P[q[(r // 2) * 2 + c // 2]].hi if (r + c) % 2 == 0 else P[q[(r // 2) * 2 + c // 2]].cell)
           for r in range(4) for c in range(4)}
    st.slab(s, P["slate"], 4, 4, x=2.9, y=-1.0, z=-3.0, colours=big)
    return s.to_svg(title)


def b_depthwise(title):
    s = st.Scene()
    for i, k in enumerate(["blue", "teal", "orange"]):
        st.slab(s, P[k], 3, 3, z=i * 0.9, thick=0.3, colours={(1, 1): P[k].hi})
    st.slab(s, P["purple"], 1, 1, x=4.0, y=1.0, z=-2.0, thick=1.8, colours={(0, 0): P["purple"].hi})
    return s.to_svg(title)


def b_tokens(title, pals, n=6, size=0.72, gapx=0.22, first=None):
    s = st.Scene()
    for i in range(n):
        pal = P[first] if (first and i == 0) else P[pals[i % len(pals)]]
        st.extrude(s, st.rect(size, size), 0, size, pal, origin=(i * (size + gapx), 0), front=pal.hi if i % 2 else pal.base)
    return s.to_svg(title)


def b_vector(title, pal, n=6, vertical=True, seed=1):
    p = P[pal]
    g = st.rng(seed)
    if vertical:
        cells = {(r, 0): p.ramp(0.1 + 0.85 * g.random()) for r in range(n)}
        cols, rows = 1, n
    else:
        cells = {(0, c): p.ramp(0.1 + 0.85 * g.random()) for c in range(n)}
        cols, rows = n, 1
    s = st.Scene()
    st.slab(s, p, cols, rows, colours=cells, thick=0.6)
    return s.to_svg(title)


def b_embedding(title, pal, rows=6, cols=4, seed=3):
    p = P[pal]
    g = st.rng(seed)
    s = st.Scene()
    st.slab(s, p, cols, rows, colours={(r, c): p.ramp(0.08 + 0.8 * g.random()) for r in range(rows) for c in range(cols)})
    return s.to_svg(title)


def b_qkv(title):
    s = st.Scene()
    for i, (k, label) in enumerate([("coral", "Q"), ("teal", "K"), ("purple", "V")]):
        p = P[k]
        g = st.rng(i + 11)
        x = i * 1.9
        st.slab(s, p, 1, 5, x=x, colours={(r, 0): p.ramp(0.1 + 0.8 * g.random()) for r in range(5)}, thick=0.6)
        s.add(-50, st.face_text(label, x + 0.5, 6.0, 0, 0.9, p.base), [st.proj((x, 6.6, 0)), st.proj((x + 1, 5.6, 0))])
    return s.to_svg(title)


MASKS = {
    "causal": lambda i, j, n: j <= i,
    "window": lambda i, j, n: abs(i - j) <= 1,
    "dilated": lambda i, j, n: abs(i - j) <= 4 and (i - j) % 2 == 0,
    "block": lambda i, j, n: i // 2 == j // 2,
    "global": lambda i, j, n: abs(i - j) <= 1 or i == 0 or j == 0,
    "strided": lambda i, j, n: j <= i and (i - j < 2 or (i - j) % 3 == 0),
    "full": lambda i, j, n: True,
}
MASK_ZH = {"causal": "因果注意力掩码", "window": "滑动窗口注意力掩码", "dilated": "空洞窗口注意力掩码", "block": "分块局部注意力掩码",
           "global": "全局加局部注意力掩码", "strided": "跨步稀疏注意力掩码", "full": "全注意力矩阵"}
MASK_EN = {"causal": "causal attention mask", "window": "sliding-window attention mask", "dilated": "dilated window mask",
           "block": "block-local attention mask", "global": "global + local attention mask",
           "strided": "strided sparse attention mask", "full": "full attention matrix"}


def b_mask(title, pal, kind, n=8):
    p = P[pal]
    cells = {(i, j): (p.hi if MASKS[kind](i, j, n) else p.cell) for i in range(n) for j in range(n)}
    for i in range(n):
        if MASKS[kind](i, i, n):
            cells[(i, i)] = p.ink
    s = st.Scene()
    st.slab(s, p, n, n, cell=0.62, colours=cells, gap=0.07, margin=0.12)
    return s.to_svg(title)


def b_attention(title, pal, n=8, seed=0, mode="diag"):
    p = P[pal]
    g = st.rng(seed)
    if mode == "diag":
        val = lambda i, j: math.exp(-((i - j) ** 2) / 3.0) * 0.85 + g.random() * 0.15  # noqa: E731
    else:
        base = [[g.random() for _ in range(n)] for _ in range(n)]
        val = lambda i, j: (base[i][j] + base[j][i]) / 2  # noqa: E731
    s = st.Scene()
    st.slab(s, p, n, n, cell=0.62, colours={(i, j): p.ramp(val(i, j)) for i in range(n) for j in range(n)}, gap=0.07, margin=0.12)
    return s.to_svg(title)


def b_token_attention(title, pal_a, pal_b):
    s = st.Scene()
    g = st.rng(5)
    n = 5
    a, b = P[pal_a], P[pal_b]
    lines = []
    for i in range(n):
        for j in range(n):
            w = g.random() ** 2
            lines.append(st.line3((i * 1.0 + 0.36, 2.25, 0.36), (j * 1.0 + 0.36, 0.72, 0.36), a.ink, 0.03 + 0.07 * w,
                                  opacity=0.25 + 0.7 * w))
    s.add(50, "<g>" + "".join(lines) + "</g>", [st.proj((0, 2.2, 0)), st.proj((5, 0.7, 0))])
    for i in range(n):
        st.extrude(s, st.rect(0.72, 0.72), 0, 0.72, a, origin=(i * 1.0, 2.25), front=a.hi)
        st.extrude(s, st.rect(0.72, 0.72), 0, 0.72, b, origin=(i * 1.0, 0), front=b.hi)
    return s.to_svg(title)


def b_mlp(title, layers, pals):
    s = st.Scene()
    xs = [i * 2.1 for i in range(len(layers))]
    pos = []
    for x, n in zip(xs, layers):
        pos.append([(x, (max(layers) - 1) * 0.5 * 0.95 - k * 0.95 + (max(layers) - n) * 0.0) for k in range(n)])
    centred = []
    for col, n in zip(pos, layers):
        off = (max(layers) - n) * 0.95 / 2
        centred.append([(x, y - off + (max(layers) - 1) * 0.0) for x, y in col])
    lines = []
    for a, b in zip(centred, centred[1:]):
        for (x1, y1) in a:
            for (x2, y2) in b:
                lines.append(st.line3((x1, y1, 0), (x2, y2, 0), "#9aa6b8", 0.035, opacity=0.8))
    s.add(80, "<g>" + "".join(lines) + "</g>", [st.proj((0, 0, 0))])
    for col, pal in zip(centred, pals):
        for x, y in col:
            st.disc(s, P[pal], x, y, 0, 0.36)
    return s.to_svg(title, scale=40)


def b_neuron(title, pal):
    s = st.Scene()
    lines = "".join(st.line3((0, y, 0), (2.4, 1.5, 0), "#9aa6b8", 0.04) for y in (0, 1, 2, 3))
    lines += st.line3((2.4, 1.5, 0), (4.0, 1.5, 0), "#9aa6b8", 0.05)
    s.add(80, f"<g>{lines}</g>", [st.proj((0, 0, 0)), st.proj((4, 3, 0))])
    for y in (0, 1, 2, 3):
        st.disc(s, P["slate"], 0, y, 0, 0.28)
    st.disc(s, P[pal], 2.4, 1.5, 0, 0.62, glyph="sigmoid")
    st.disc(s, P[pal], 4.0, 1.5, 0, 0.3, face=P[pal].hi)
    return s.to_svg(title)


def b_residual(title, pal):
    p = P[pal]
    s = st.Scene()
    st.extrude(s, st.rect(3.0, 0.9), 0, 0.9, p, origin=(0, 0))
    st.extrude(s, st.rect(3.0, 0.9), 0, 0.9, p, origin=(0, 1.6))
    path = [(1.5, 2.5), (1.5, 3.2), (4.0, 3.2), (4.0, -0.9), (2.0, -0.9)]
    links = [((1.5, 0.9), (1.5, 1.6)), ((1.5, 0.0), (1.5, -0.5))]
    segs = list(zip(path, path[1:])) + links
    lines = "".join(st.line3((a[0], a[1], 0.45), (b[0], b[1], 0.45), P["slate"].base, 0.08) for a, b in segs)
    s.add(90, f"<g>{lines}</g>", [st.proj((x, y, 0.45)) for seg in segs for x, y in seg])
    st.disc(s, P["slate"], 1.5, -0.9, 0.45, 0.42, glyph="+", depth_bias=-5)
    return s.to_svg(title)


def b_operator(title, pal, glyph):
    s = st.Scene()
    st.disc(s, P[pal], 0, 0, 0, 1.0, thick=0.35, glyph=glyph)
    return s.to_svg(title)


def b_graph(title, pal_nodes, pal_alt, seed=0, centre=False):
    g = st.rng(seed)
    if centre:
        nodes = [(0.0, 0.0)] + [(1.9 * math.cos(a), 1.9 * math.sin(a)) for a in [i * 2 * math.pi / 6 + 0.3 for i in range(6)]]
        edges = [(0, i) for i in range(1, 7)]
    else:
        nodes = [(0, 0), (1.8, 0.6), (3.4, -0.2), (0.6, 1.9), (2.4, 2.3), (3.9, 1.5), (1.4, -1.5), (3.0, -1.7)]
        edges = [(0, 1), (1, 2), (0, 3), (3, 4), (1, 4), (4, 5), (2, 5), (0, 6), (6, 7), (2, 7), (1, 6)]
    s = st.Scene()
    # nodes on the ground plane (x, 0, z) so the graph lies flat in the view
    to3 = lambda p: (p[0], 0.0, -p[1] * 1.0)  # noqa: E731
    lines = "".join(st.line3(to3(nodes[a]), to3(nodes[b]), P["slate"].hi, 0.07) for a, b in edges)
    s.add(80, f"<g>{lines}</g>", [st.proj(to3(n)) for n in nodes])
    for i, n in enumerate(nodes):
        pal = P[pal_alt] if (centre and i == 0) or (not centre and i in (1, 4)) else P[pal_nodes]
        x, y, z = to3(n)
        st.disc(s, pal, x, y, z, 0.36 if not (centre and i == 0) else 0.5)
    return s.to_svg(title)


def b_point_cloud(title, pal, seed=0, shape="blob"):
    g = st.rng(seed)
    p = P[pal]
    pts = []
    for _ in range(420):
        u, v = g.random() * 2 * math.pi, math.acos(2 * g.random() - 1)
        if shape == "blob":
            r = 1.0 + 0.18 * math.sin(3 * u) * math.sin(2 * v)
            x, y, z = 2.0 * r * math.sin(v) * math.cos(u), 1.2 * r * math.cos(v), 1.4 * r * math.sin(v) * math.sin(u)
        else:  # torus
            a, b = 1.8, 0.6
            x, y, z = (a + b * math.cos(v * 2)) * math.cos(u), b * math.sin(v * 2), (a + b * math.cos(v * 2)) * math.sin(u)
        pts.append((x, y, z))
    s = st.Scene()
    ys = [q[1] for q in pts]
    lo, hi = min(ys), max(ys)
    body = []
    for q in sorted(pts, key=lambda q: -st.dot(q, st.D)):
        sx, sy = st.proj(q)
        body.append(f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="0.075" fill="{p.ramp((q[1] - lo) / (hi - lo))}"/>')
    s.add(0, "<g>" + "".join(body) + "</g>", [st.proj(q) for q in pts])
    return s.to_svg(title)


def b_globe(title, pal, weather=False):
    p = P[pal]
    s = st.Scene()
    r = 2.0
    defs = (f'<defs><radialGradient id="g" cx="0.38" cy="0.32" r="0.75"><stop offset="0" stop-color="{p.cell}"/>'
            f'<stop offset="0.55" stop-color="{p.hi}"/><stop offset="1" stop-color="{p.left}"/></radialGradient></defs>')
    parts = [f'<circle cx="0" cy="0" r="{r}" fill="url(#g)"/>']
    if weather:
        g = st.rng(4)
        for _ in range(7):
            lat, lon = g.uniform(-0.8, 0.8), g.uniform(-1.2, 1.2)
            q = (r * math.cos(lat) * math.sin(lon), r * math.sin(lat), -r * math.cos(lat) * math.cos(lon))
            sx, sy = st.proj(q)
            parts.append(f'<ellipse cx="{sx:.3f}" cy="{sy:.3f}" rx="{g.uniform(.25, .5):.2f}" ry="{g.uniform(.15, .3):.2f}" '
                         f'fill="#ffffff" fill-opacity="0.55"/>')
    tilt = 0.35

    def point(lat, lon):
        x, y, z = r * math.cos(lat) * math.sin(lon), r * math.sin(lat), -r * math.cos(lat) * math.cos(lon)
        return (x, y * math.cos(tilt) - z * math.sin(tilt), y * math.sin(tilt) + z * math.cos(tilt))

    grid = []
    for lat_deg in range(-60, 61, 30):
        grid.append([point(math.radians(lat_deg), math.radians(t)) for t in range(0, 361, 6)])
    for lon_deg in range(0, 180, 30):
        grid.append([point(math.radians(t), math.radians(lon_deg)) for t in range(-90, 271, 6)])
    for line in grid:
        seg = []
        for q in line:
            if st.dot(q, st.D) < 0.02:      # front hemisphere
                seg.append(st.proj(q))
            elif seg:
                if len(seg) > 1:
                    parts.append(f'<polyline points="{st.pts_attr(seg)}" fill="none" stroke="#ffffff" stroke-opacity="0.55" stroke-width="0.04"/>')
                seg = []
        if len(seg) > 1:
            parts.append(f'<polyline points="{st.pts_attr(seg)}" fill="none" stroke="#ffffff" stroke-opacity="0.55" stroke-width="0.04"/>')
    s.add(0, "<g>" + "".join(parts) + "</g>", [(-r, -r), (r, r)])
    return s.to_svg(title, defs=defs)


def b_radar(title, seed=0, n=16):
    f = field(n, n, seed)
    cells = {k: ramp_list(PRECIP, v * 0.85) for k, v in f.items()}
    s = st.Scene()
    st.slab(s, P["slate"], n, n, cell=0.4, colours=cells, margin=0.14, gap=0.0, thick=0.38)
    return s.to_svg(title)


def b_radar_sequence(title, seed=0, frames=4, n=12):
    s = st.Scene()
    for t in range(frames):
        f = field(n, n, seed, shift=(0.07 * t, -0.03 * t))
        cells = {k: ramp_list(PRECIP, v * 0.85) for k, v in f.items()}
        st.slab(s, P["slate"], n, n, cell=0.4, x=t * 1.2, z=-t * 1.9, colours=cells, margin=0.12, gap=0.0, thick=0.3)
    return s.to_svg(title)


def b_temperature(title, seed=0, n=16, cols=24):
    g = st.rng(seed)
    cells = {}
    for r in range(n):
        for c in range(cols):
            lat = 1 - abs((r / (n - 1)) * 2 - 1)
            v = 0.15 + 0.7 * lat + 0.12 * math.sin(c / cols * 6.28 * 2 + r * 0.4) + (g.random() - .5) * 0.08
            cells[(r, c)] = ramp_list(TEMP, v)
    s = st.Scene()
    st.slab(s, P["slate"], cols, n, cell=0.3, colours=cells, margin=0.14, gap=0.0, thick=0.36)
    return s.to_svg(title)


def b_st_cube(title, seed=0):
    s = st.Scene()
    n = 4
    for t, k in enumerate(["blue", "teal", "green", "amber", "orange"]):
        p = P[k]
        f = field(n, n, seed + t)
        st.slab(s, p, n, n, z=t * 0.62, thick=0.38, colours={kk: p.ramp(v * 0.8) for kk, v in f.items()})
    return s.to_svg(title)


def b_series(title, pal, lines=1, seed=0):
    p = P[pal]
    s = st.Scene()
    w, h = 6.0, 3.2
    frags = []
    colours = [p.ink, P["coral"].base, P["teal"].base]
    g = st.rng(seed)
    for k in range(lines):
        ph = g.random() * 6
        pts = []
        for i in range(61):
            x = 0.35 + i / 60 * (w - 0.7)
            y = h / 2 + (0.9 if lines == 1 else 0.45) * math.sin(i / 60 * 12 + ph) * (0.6 + 0.4 * math.sin(i / 60 * 3 + k))
            y += (k - (lines - 1) / 2) * 0.9
            pts.append(st.proj((x, y, 0)))
        frags.append(f'<polyline points="{st.pts_attr(pts)}" fill="none" stroke="{colours[k]}" stroke-width="0.075" '
                     f'stroke-linecap="round" stroke-linejoin="round"/>')
    inner = [(0.15, 0.15), (w - 0.15, 0.15), (w - 0.15, h - 0.15), (0.15, h - 0.15)]
    panel = st.poly([st.proj((x, y, 0)) for x, y in inner], "#ffffff")
    st.extrude(s, st.rect(w, h), 0, 0.42, p, front_svg=panel + "".join(frags))
    return s.to_svg(title)


def b_noise(title, pal=None, seed=0, n=8):
    g = st.rng(seed)
    if pal:
        p = P[pal]
        cells = {(r, c): p.ramp(g.random()) for r in range(n) for c in range(n)}
        frame = p
    else:
        cells = {(r, c): st.mix(P[ORDER[g.randrange(8)]].hi, "#ffffff", g.random() * 0.5) for r in range(n) for c in range(n)}
        frame = P["slate"]
    s = st.Scene()
    st.slab(s, frame, n, n, cell=0.6, colours=cells, gap=0.06)
    return s.to_svg(title)


def b_diffusion(title, seed=0, steps=4, n=6):
    s = st.Scene()
    g = st.rng(seed)
    clean = field(n, n, seed + 9)
    for t in range(steps):
        a = t / (steps - 1)
        cells = {}
        for k, v in clean.items():
            base = P["blue"].ramp(v * 0.9)
            noise = st.mix(P[ORDER[g.randrange(8)]].hi, "#ffffff", g.random() * 0.4)
            cells[k] = st.mix(base, noise, a)
        st.slab(s, P["slate"], n, n, cell=0.6, x=t * 1.35, z=-t * 2.3, colours=cells, gap=0.06, thick=0.3)
    return s.to_svg(title)


def b_spectrum(title, pal, seed=0, bars=10):
    p = P[pal]
    g = st.rng(seed)
    s = st.Scene()
    for i in range(bars):
        h = 0.4 + 2.6 * math.exp(-i / 3.0) * (0.75 + 0.25 * g.random())
        st.extrude(s, st.rect(0.5, h), 0, 0.5, p, origin=(i * 0.68, 0), front=p.ramp(0.3 + 0.6 * (1 - i / bars)))
    return s.to_svg(title)


def b_wavelet(title, pal):
    p = P[pal]
    cells = {}
    for r in range(4):
        for c in range(4):
            q = (r // 2) * 2 + c // 2
            cells[(r, c)] = [p.ink, p.hi, p.hi, st.mix(p.cell, p.hi, 0.35)][q]
    s = st.Scene()
    st.slab(s, p, 4, 4, colours=cells)
    return s.to_svg(title)


# ------------------------------------------------------------------ pictures on a slab
SCENES = {
    "day": {"sky": "#bfe3ff", "sun": "#ffd25a", "far": "#8fb8e8", "near": "#5aa86b", "ground": "#8fd18a"},
    "sunset": {"sky": "#ffc9a3", "sun": "#ff8a3d", "far": "#b78ad6", "near": "#6d4fa8", "ground": "#e7a77f"},
    "night": {"sky": "#2c3e73", "sun": "#f4f1d0", "far": "#475f9e", "near": "#24335f", "ground": "#3b4d80"},
}
LABELS = {"sky": "#7cc4ff", "sun": "#ffd84d", "far": "#a78bfa", "near": "#34c38f", "ground": "#f59e6b"}
DEPTH = {"sky": "#f2f4f7", "sun": "#d9dee5", "far": "#a6b0bd", "near": "#5f6b7a", "ground": "#2f3845"}


def _picture(colours, w, h, z=0.0, box=False):
    """Flat landscape (sky, sun, two mountain ranges, ground) mapped onto the front plane."""
    m = 0.14
    def face(points):
        return [st.proj((m + px * (w - 2 * m), m + py * (h - 2 * m), z)) for px, py in points]
    parts = [st.poly(face([(0, 0), (1, 0), (1, 1), (0, 1)]), colours["sky"])]
    sun = [(0.74 + 0.11 * math.cos(a) * 0.75, 0.76 + 0.11 * math.sin(a)) for a in [i * math.pi / 16 for i in range(32)]]
    parts.append(st.poly(face(sun), colours["sun"]))
    parts.append(st.poly(face([(0, 0.25), (0.22, 0.55), (0.36, 0.42), (0.55, 0.68), (0.8, 0.35), (1, 0.48), (1, 0.25)]), colours["far"]))
    parts.append(st.poly(face([(0, 0.18), (0.18, 0.4), (0.4, 0.22), (0.6, 0.45), (0.85, 0.2), (1, 0.3), (1, 0.18)]), colours["near"]))
    parts.append(st.poly(face([(0, 0), (1, 0), (1, 0.2), (0, 0.2)]), colours["ground"]))
    if box:
        for (x0, y0, x1, y1), col in (((0.5, 0.18, 0.66, 0.5), "#e6485c"), ((0.62, 0.62, 0.88, 0.92), "#1e6fe0")):
            pts = face([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
            parts.append(f'<polygon points="{st.pts_attr(pts)}" fill="none" stroke="{col}" stroke-width="0.08"/>')
            tag = face([(x0, y1), (x0 + 0.12, y1), (x0 + 0.12, y1 + 0.06), (x0, y1 + 0.06)])
            parts.append(st.poly(tag, col))
    return "".join(parts)


def b_image(title, scene="day", mode="photo", patches=False, w=5.0, h=4.0):
    colours = {"seg": LABELS, "depth": DEPTH}.get(mode, SCENES[scene])
    s = st.Scene()
    front = _picture(colours, w, h, box=(mode == "detect"))
    if patches:
        lines = []
        for i in range(1, 4):
            lines.append(st.line3((w * i / 4, 0.14, 0), (w * i / 4, h - 0.14, 0), "#ffffff", 0.07))
            lines.append(st.line3((0.14, h * i / 4, 0), (w - 0.14, h * i / 4, 0), "#ffffff", 0.07))
        front += "".join(lines)
    st.extrude(s, st.rect(w, h), 0, 0.42, P["slate"], front_svg=front)
    return s.to_svg(title)


def b_embedding_space(title, clusters, seed=0):
    g = st.rng(seed)
    w, h = 5.0, 4.0
    s = st.Scene()
    dots = []
    centres = [(1.4, 2.7), (3.6, 2.9), (2.5, 1.2), (3.9, 1.0)][:len(clusters)]
    for (cx, cy), k in zip(centres, clusters):
        for _ in range(16):
            x, y = cx + g.gauss(0, 0.32), cy + g.gauss(0, 0.28)
            x, y = min(max(x, 0.4), w - 0.4), min(max(y, 0.4), h - 0.4)
            sx, sy = st.proj((x, y, 0))
            dots.append(f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="0.12" fill="{P[k].base}"/>')
    inner = st.poly([st.proj((x, y, 0)) for x, y in [(0.14, 0.14), (w - 0.14, 0.14), (w - 0.14, h - 0.14), (0.14, h - 0.14)]], "#ffffff")
    st.extrude(s, st.rect(w, h), 0, 0.42, P["slate"], front_svg=inner + "".join(dots))
    return s.to_svg(title)


# ------------------------------------------------------------------ catalogue
def build_specs():
    PZ = {k: P[k].zh for k in ORDER}
    for k in ORDER:
        add(f"fmap-6-{k}", "特征图", f"{PZ[k]}特征图 6×6", f"{k} feature map 6x6", ["特征图", "feature map", "网格", "卷积"],
            b_feature_map, pal=k, rows=6, cols=6)
        add(f"fmap-6-hi-{k}", "特征图", f"{PZ[k]}特征图 6×6（高亮）", f"{k} feature map 6x6, highlighted cells",
            ["特征图", "feature map", "激活", "高亮"], b_feature_map, pal=k, rows=6, cols=6, kind="scatter", seed=ORDER.index(k))
        add(f"fmap-4-{k}", "特征图", f"{PZ[k]}特征图 4×4", f"{k} feature map 4x4", ["特征图", "feature map", "下采样"],
            b_feature_map, pal=k, rows=4, cols=4, kind="center")
        add(f"fmap-3-{k}", "特征图", f"{PZ[k]}特征图 3×3", f"{k} feature map 3x3", ["特征图", "feature map", "小尺寸"],
            b_feature_map, pal=k, rows=3, cols=3, kind="center")
        add(f"heat-{k}", "特征图", f"{PZ[k]}热力特征图", f"{k} heat feature map", ["热力图", "heat map", "激活图", "特征图"],
            b_heat_map, pal=k)
    for mode, zh, en in (("diag", "对角响应图", "diagonal response map"), ("grad", "渐变响应图", "gradient response map"),
                         ("ring", "环形响应图", "ring response map")):
        for k in ("blue", "purple", "orange"):
            add(f"resp-{mode}-{k}", "特征图", f"{PZ[k]}{zh}", f"{k} {en}", ["响应图", "特征图", "activation"],
                b_heat_map, pal=k, mode=mode)
    seqs = [("down-1", ["blue", "teal", "orange"], [6, 4, 3], "下采样特征图序列（蓝青橙）"),
            ("down-2", ["purple", "blue", "teal"], [6, 4, 3], "下采样特征图序列（紫蓝青）"),
            ("down-3", ["green", "teal", "blue"], [6, 4, 3], "下采样特征图序列（绿青蓝）"),
            ("down-4", ["coral", "orange", "amber"], [6, 4, 3], "下采样特征图序列（红橙黄）"),
            ("down-5", ["slate", "blue", "coral"], [6, 4, 3], "下采样特征图序列（灰蓝红）"),
            ("down4-1", ["blue", "teal", "green", "amber"], [7, 5, 4, 3], "四级下采样特征图序列"),
            ("up-1", ["orange", "teal", "blue"], [3, 4, 6], "上采样特征图序列（橙青蓝）"),
            ("up-2", ["teal", "blue", "purple"], [3, 4, 6], "上采样特征图序列（青蓝紫）"),
            ("up-3", ["amber", "orange", "coral"], [3, 4, 6], "上采样特征图序列（黄橙红）"),
            ("same-1", ["blue", "blue", "blue"], [4, 4, 4], "等尺寸特征图序列（蓝）"),
            ("same-2", ["teal", "teal", "teal"], [4, 4, 4], "等尺寸特征图序列（青）"),
            ("same-3", ["blue", "teal", "orange", "purple"], [4, 4, 4, 4], "多阶段特征图序列（彩色）")]
    for key, pals, sizes, zh in seqs:
        add(f"seq-{key}", "特征图", zh, "feature map sequence " + key, ["特征图序列", "下采样" if "down" in key else "上采样" if "up" in key else "多阶段",
                                                                 "encoder", "pyramid", "多尺度"], b_sequence, pals=pals, sizes=sizes)

    for k in ORDER:
        add(f"tensor-cube-{k}", "张量与通道", f"{PZ[k]}三维张量 3×3×3", f"{k} 3D tensor 3x3x3", ["张量", "tensor", "立方体", "C×H×W"],
            b_cube, pal=k, cols=3, rows=3, layers=3)
        add(f"tensor-wide-{k}", "张量与通道", f"{PZ[k]}扁平张量 5×4×2", f"{k} flat tensor", ["张量", "tensor", "特征张量"],
            b_cube, pal=k, cols=5, rows=4, layers=2, accent="scatter")
        add(f"stack-{k}", "张量与通道", f"{PZ[k]}多通道堆叠", f"{k} stacked channels", ["通道", "channels", "堆叠", "特征图"],
            b_stack, pals=[k], n=5)
    for k in ("blue", "purple", "teal", "orange"):
        add(f"tensor-deep-{k}", "张量与通道", f"{PZ[k]}高通道张量 2×4×6", f"{k} channel-heavy tensor", ["张量", "通道", "channels"],
            b_cube, pal=k, cols=2, rows=4, layers=6)
    add("stack-rainbow", "张量与通道", "彩色多通道堆叠", "multi-colour stacked channels", ["通道", "channels", "彩色", "堆叠"],
        b_stack, pals=ORDER[:6], n=6)
    add("stack-rgb", "张量与通道", "RGB 三通道", "RGB channels", ["RGB", "图像通道", "输入图像"], b_stack,
        pals=["coral", "green", "blue"], n=3, gap=0.9)
    for a, b in (("blue", "orange"), ("teal", "purple"), ("green", "coral"), ("blue", "teal")):
        add(f"concat-{a}-{b}", "张量与通道", f"{PZ[a]}{PZ[b]}通道拼接", f"channel concatenation {a} + {b}",
            ["拼接", "concat", "通道", "特征融合"], b_concat, pal_a=a, pal_b=b)

    for a, b in (("blue", "teal"), ("purple", "orange"), ("green", "amber"), ("slate", "coral")):
        add(f"conv-{a}-{b}", "卷积与采样", f"卷积运算示意（{PZ[a]}→{PZ[b]}）", f"convolution {a} to {b}",
            ["卷积", "convolution", "卷积核", "感受野"], b_conv, pal_in=a, pal_out=b)
    for k in ORDER:
        add(f"kernel-3-{k}", "卷积与采样", f"{PZ[k]}卷积核 3×3", f"{k} 3x3 kernel", ["卷积核", "kernel", "filter", "权重"],
            b_kernel, pal=k, k=3, seed=ORDER.index(k))
    for k in ("blue", "teal", "orange", "purple"):
        add(f"kernel-5-{k}", "卷积与采样", f"{PZ[k]}卷积核 5×5", f"{k} 5x5 kernel", ["卷积核", "kernel", "大卷积核"],
            b_kernel, pal=k, k=5, seed=7)
        add(f"kernel-1-{k}", "卷积与采样", f"{PZ[k]}1×1 卷积", f"{k} 1x1 convolution", ["1×1 卷积", "pointwise", "逐点卷积"],
            b_kernel, pal=k, k=1)
    add("pool-max", "卷积与采样", "最大池化 4×4→2×2", "max pooling", ["池化", "pooling", "max pooling", "下采样"], b_pooling, mode="max")
    add("pool-avg", "卷积与采样", "平均池化 4×4→2×2", "average pooling", ["池化", "pooling", "average pooling"], b_pooling, mode="avg")
    for k in ("blue", "teal"):
        add(f"dilated-{k}", "卷积与采样", f"{PZ[k]}空洞卷积采样网格", f"{k} dilated convolution grid",
            ["空洞卷积", "dilated", "atrous", "感受野"], b_dilated, pal=k)
    for k in ("blue", "purple"):
        add(f"receptive-{k}", "卷积与采样", f"{PZ[k]}感受野逐层收缩", f"{k} receptive field", ["感受野", "receptive field", "卷积"],
            b_receptive, pal=k)
    add("patches", "卷积与采样", "图像分块（彩色 Patch）", "image patches", ["patch", "图像分块", "ViT", "分块"], b_patches)
    add("patches-flatten", "卷积与采样", "图像分块展平为 Token", "patches flattened to tokens",
        ["patch embedding", "ViT", "Token", "展平"], b_patches, flatten=True)
    add("upsample", "卷积与采样", "上采样 2×2→4×4", "upsampling", ["上采样", "upsample", "像素重排"], b_upsample)
    add("depthwise", "卷积与采样", "深度可分离卷积", "depthwise separable convolution", ["深度可分离", "depthwise", "MobileNet"],
        b_depthwise)

    for k in ORDER:
        add(f"tokens-{k}", "Token 与嵌入", f"{PZ[k]} Token 序列", f"{k} token sequence", ["Token", "序列", "sequence", "嵌入"],
            b_tokens, pals=[k])
        add(f"vector-{k}", "Token 与嵌入", f"{PZ[k]}特征向量（竖）", f"{k} feature vector", ["向量", "vector", "嵌入", "embedding"],
            b_vector, pal=k, seed=ORDER.index(k))
    for k, first in (("blue", "orange"), ("teal", "coral"), ("purple", "amber"), ("slate", "blue")):
        add(f"tokens-cls-{k}", "Token 与嵌入", f"带分类 Token 的序列（{PZ[k]}）", f"token sequence with class token ({k})",
            ["CLS", "class token", "Token", "ViT"], b_tokens, pals=[k], first=first)
    add("tokens-multimodal", "Token 与嵌入", "多模态 Token 序列", "multimodal tokens", ["多模态", "multimodal", "Token", "图文"],
        b_tokens, pals=["blue", "blue", "blue", "orange", "orange", "orange"])
    add("tokens-rainbow", "Token 与嵌入", "彩色 Token 序列", "colourful tokens", ["Token", "序列", "彩色"], b_tokens, pals=ORDER, n=8)
    for k in ("blue", "teal", "orange", "purple"):
        add(f"vector-h-{k}", "Token 与嵌入", f"{PZ[k]}特征向量（横）", f"{k} feature vector (row)", ["向量", "vector", "行向量"],
            b_vector, pal=k, vertical=False, n=8, seed=3)
        add(f"embedding-{k}", "Token 与嵌入", f"{PZ[k]}嵌入矩阵", f"{k} embedding matrix", ["嵌入", "embedding", "矩阵"],
            b_embedding, pal=k)
    add("qkv", "Token 与嵌入", "Q / K / V 向量", "query key value", ["QKV", "注意力", "query", "key", "value"], b_qkv)

    for kind in MASKS:
        for k in ("blue", "purple"):
            add(f"mask-{kind}-{k}", "注意力与 Transformer", f"{PZ[k]}{MASK_ZH[kind]}", f"{k} {MASK_EN[kind]}",
                ["注意力", "掩码", "mask", "attention", "稀疏注意力" if kind not in ("full", "causal") else "Transformer"],
                b_mask, pal=k, kind=kind)
    for k in ("blue", "purple", "orange", "teal", "coral", "green"):
        add(f"attn-{k}", "注意力与 Transformer", f"{PZ[k]}注意力热图", f"{k} attention map", ["注意力", "attention map", "热图", "矩阵"],
            b_attention, pal=k, seed=ORDER.index(k))
    for k in ("blue", "teal"):
        add(f"sim-{k}", "注意力与 Transformer", f"{PZ[k]}相似度矩阵", f"{k} similarity matrix", ["相似度", "similarity", "相关矩阵"],
            b_attention, pal=k, seed=9, mode="sym")
    for a, b in (("blue", "orange"), ("purple", "teal")):
        add(f"tokattn-{a}-{b}", "注意力与 Transformer", f"Token 间注意力连接（{PZ[a]}{PZ[b]}）", f"token-to-token attention {a} {b}",
            ["注意力", "attention", "Token", "交叉注意力"], b_token_attention, pal_a=a, pal_b=b)

    add("mlp-1", "神经元与全连接", "全连接网络 3-5-4-2", "MLP 3-5-4-2", ["MLP", "全连接", "神经网络", "neurons"], b_mlp,
        layers=[3, 5, 4, 2], pals=["teal", "blue", "blue", "orange"])
    add("mlp-2", "神经元与全连接", "全连接网络 4-6-6-3", "MLP 4-6-6-3", ["MLP", "全连接", "神经网络"], b_mlp,
        layers=[4, 6, 6, 3], pals=["slate", "purple", "purple", "coral"])
    add("mlp-3", "神经元与全连接", "单隐层网络 3-4-1", "MLP 3-4-1", ["MLP", "感知机", "神经网络"], b_mlp, layers=[3, 4, 1],
        pals=["green", "green", "amber"])
    add("neuron", "神经元与全连接", "单个神经元", "single neuron", ["神经元", "neuron", "激活函数"], b_neuron, pal="blue")
    for k in ("blue", "teal"):
        add(f"residual-{k}", "网络结构与模块", f"{PZ[k]}残差连接单元", f"{k} residual unit", ["残差", "residual", "跳跃连接", "ResNet"],
            b_residual, pal=k)

    ops = [("add", "+", "加法"), ("mul", "x", "乘法"), ("hadamard", "dot", "逐元素乘"), ("sigmoid", "sigmoid", "Sigmoid"),
           ("relu", "relu", "ReLU"), ("concat", "C", "拼接"), ("sum", "Σ", "求和"), ("softmax", "S", "Softmax")]
    for key, glyph, zh in ops:
        for k in ("slate", "blue"):
            add(f"op-{key}-{k}", "运算符", f"{zh}运算符（{PZ[k]}）", f"{key} operator ({k})", ["运算符", "operator", zh, key],
                b_operator, pal=k, glyph=glyph)

    for i, (a, b) in enumerate((("blue", "orange"), ("teal", "coral"), ("purple", "amber"))):
        add(f"graph-{i + 1}", "图与点云", f"图结构（{PZ[a]}）", f"graph ({a})", ["图", "graph", "GNN", "节点"], b_graph,
            pal_nodes=a, pal_alt=b, seed=i)
    for i, (a, b) in enumerate((("blue", "orange"), ("teal", "purple"))):
        add(f"graph-star-{i + 1}", "图与点云", f"邻居聚合示意（{PZ[a]}）", f"neighbour aggregation ({a})",
            ["图神经网络", "消息传递", "GNN", "邻居"], b_graph, pal_nodes=a, pal_alt=b, centre=True)
    for i, (k, shape) in enumerate((("blue", "blob"), ("purple", "blob"), ("teal", "torus"), ("orange", "torus"))):
        add(f"pointcloud-{i + 1}", "三维视觉", f"{PZ[k]}点云", f"{k} point cloud", ["点云", "point cloud", "三维"], b_point_cloud,
            pal=k, seed=i, shape=shape)


    for sc, zh in (("day", "白天"), ("sunset", "黄昏"), ("night", "夜晚")):
        add(f"image-{sc}", "图像输入与预处理", f"输入图像（{zh}风景）", f"input image ({sc})", ["输入图像", "image", "图片", "输入"],
            b_image, scene=sc)
    add("image-patches", "图像输入与预处理", "输入图像分块网格", "image split into patches", ["图像分块", "patch", "ViT", "输入图像"],
        b_image, scene="day", patches=True)
    add("image-seg", "检测、分割与关键点", "语义分割掩码", "semantic segmentation mask", ["语义分割", "segmentation", "掩码", "标签图"],
        b_image, mode="seg")
    add("image-depth", "三维视觉", "深度图", "depth map", ["深度图", "depth", "深度估计"], b_image, mode="depth")
    add("image-detect", "检测、分割与关键点", "目标检测框", "detection boxes", ["目标检测", "检测框", "bounding box", "detection"],
        b_image, mode="detect")
    add("embed-space-3", "图与点云", "嵌入空间聚类（三类）", "embedding space, three clusters", ["嵌入空间", "聚类", "对比学习", "特征分布"],
        b_embedding_space, clusters=["blue", "orange", "teal"], seed=1)
    add("embed-space-4", "图与点云", "嵌入空间聚类（四类）", "embedding space, four clusters", ["嵌入空间", "聚类", "t-SNE", "特征分布"],
        b_embedding_space, clusters=["purple", "coral", "green", "amber"], seed=2)
    for k in ("blue", "teal", "slate"):
        add(f"globe-{k}", "时空与气象", f"{PZ[k]}地球经纬网格", f"{k} globe", ["地球", "globe", "经纬网格", "全球"], b_globe, pal=k)
    add("globe-weather", "时空与气象", "地球与云团", "globe with clouds", ["地球", "云", "天气", "气象"], b_globe, pal="blue", weather=True)
    for i in range(3):
        add(f"radar-{i + 1}", "时空与气象", f"雷达回波图 {i + 1}", f"radar echo map {i + 1}", ["雷达回波", "降水", "radar", "临近预报"],
            b_radar, seed=i + 1)
    for i in range(2):
        add(f"radar-seq-{i + 1}", "时空与气象", f"雷达回波时间序列 {i + 1}", f"radar echo sequence {i + 1}",
            ["雷达回波", "时间序列", "降水预报", "视频预测"], b_radar_sequence, seed=i + 5)
    for i in range(2):
        add(f"temperature-{i + 1}", "时空与气象", f"全球温度场 {i + 1}", f"temperature field {i + 1}", ["温度场", "气象场", "ERA5", "全球"],
            b_temperature, seed=i)
    add("st-cube", "时空与气象", "时空张量（多时刻堆叠）", "spatiotemporal tensor", ["时空", "T×H×W", "视频", "时间步"], b_st_cube)

    for k in ("blue", "teal", "purple", "orange"):
        add(f"series-{k}", "信号与噪声", f"{PZ[k]}时间序列面板", f"{k} time series panel", ["时间序列", "time series", "信号"],
            b_series, pal=k, seed=ORDER.index(k))
    for k in ("slate", "blue"):
        add(f"series-multi-{k}", "信号与噪声", f"多变量时间序列（{PZ[k]}）", f"multivariate time series ({k})",
            ["多变量", "时间序列", "multivariate"], b_series, pal=k, lines=3, seed=4)
    add("noise-colour", "信号与噪声", "彩色高斯噪声", "colour Gaussian noise", ["噪声", "noise", "扩散模型", "高斯"], b_noise, seed=1)
    for k in ("slate", "blue", "purple"):
        add(f"noise-{k}", "信号与噪声", f"{PZ[k]}随机噪声", f"{k} random noise", ["噪声", "noise", "随机"], b_noise, pal=k, seed=2)
    for i in range(2):
        add(f"diffusion-{i + 1}", "信号与噪声", f"逐步加噪序列 {i + 1}", f"forward diffusion steps {i + 1}",
            ["扩散", "diffusion", "加噪", "去噪"], b_diffusion, seed=i + 3)
    for k in ("blue", "orange"):
        add(f"spectrum-{k}", "信号与噪声", f"{PZ[k]}频谱柱状图", f"{k} spectrum bars", ["频谱", "spectrum", "频域", "傅里叶"],
            b_spectrum, pal=k, seed=ORDER.index(k))
    for k in ("teal", "purple"):
        add(f"wavelet-{k}", "信号与噪声", f"{PZ[k]}小波四子带", f"{k} wavelet sub-bands", ["小波", "wavelet", "LL", "频域"],
            b_wavelet, pal=k)


def render(task):
    eid, fn, kw, meta = task
    svg = fn(meta["name"], **kw)
    (OUT / f"{eid}.svg").write_text(svg, encoding="utf-8")
    import re
    vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    w, h = float(vb.group(1)), float(vb.group(2))
    scale = PNG_SIDE / max(w, h)
    png = resvg_py.svg_to_bytes(svg_string=svg, width=round(w * scale), height=round(h * scale))
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    image.save(OUT / f"{eid}.png", optimize=True)
    thumb = image.copy()
    thumb.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.Resampling.LANCZOS)
    thumb.save(OUT / "thumbs" / f"{eid}.webp", quality=92, method=6)
    files = {"png": f"{eid}.png", "svg": f"{eid}.svg"}
    return {**meta, "kind": "atomic", "original": True, "source": "figure-atlas", "svg_kind": "vector", "has_alpha": True,
            "width": image.width, "height": image.height,
            "files": {**{k: f"assets/elements/{v}" for k, v in files.items()}, "thumb": f"assets/elements/thumbs/{eid}.webp"},
            "hashes": {k: sha256(OUT / v) for k, v in files.items()},
            "bytes": {k: (OUT / v).stat().st_size for k, v in files.items()}}


def main():
    build_specs()
    ids = [s[0] for s in SPECS]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate element ids")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "thumbs").mkdir(exist_ok=True)
    with ProcessPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(render, SPECS))
    keep = {Path(v).name for r in records for v in r["files"].values()}
    for path in list(OUT.glob("*.*")) + list((OUT / "thumbs").glob("*.*")):
        if path.name not in keep:
            path.unlink()
    for i, r in enumerate(records):
        r["id"] = "el-" + r["id"]
        r["order"] = i
        r["description"] = r["description"] or (f"研图原创图元，统一的等轴测风格。SVG 中每个面和单元格都是独立图形，"
                                                f"可直接改色、增删格子或调整大小。")
    source = {"short": "研图原创", "title": "研图 Figure Atlas 原创图元", "authors": ["研图 Figure Atlas"],
              "venue": "CC0 1.0 · 可自由使用", "year": 2026, "arxiv": "",
              "url": "https://github.com/RuntimeWarning/research-figure-library", "pdf": "",
              "license": "CC0-1.0", "license_name": "CC0 1.0（公共领域）",
              "license_url": "https://creativecommons.org/publicdomain/zero/1.0/", "original": True}
    write_json(MANIFESTS / "elements.json", {"categories": CATEGORIES, "sources": {"figure-atlas": source},
                                             "assets": records})
    from collections import Counter
    print({"elements": len(records), "by_category": Counter(r["category"] for r in records),
           "bytes": sum(sum(r["bytes"].values()) for r in records)})


if __name__ == "__main__":
    main()
