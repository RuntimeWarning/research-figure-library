"""More building blocks for model figures, in the same look as ``generate.py``.

Network modules (layer stacks, encoder / decoder wedges, U-Net, FPN, Transformer
layers, Inception and MoE blocks), attention and sampling patterns used by vision
models, detection and segmentation schematics, operators, activation curves and
small charts.  Every builder takes the element title plus keyword arguments and
returns an SVG string; ``register(add)`` lists them in the catalogue.
"""
from __future__ import annotations

import math

import style as st
from style import PALETTES as P, ORDER

NET, TENSOR, CONV, TOKEN, ATTN, FMAP = "网络结构与模块", "张量与通道", "卷积与采样", "Token 与嵌入", "注意力与 Transformer", "特征图"
TASK, OPS, GRAPH, SIGNAL, CHART, NEURON = "检测、分割与关键点", "运算符", "图与点云", "信号与噪声", "分布与图表", "神经元与全连接"
GREY = "#9aa6b8"
INK = "#3b4656"


# ------------------------------------------------------------------ helpers
def box(s, pal, x, y, z, w, h, d, front=None, top=None, left=None, front_svg="", bias=0.0):
    """Cuboid x..x+w, y..y+h, z..z+d with optional face colours."""
    def sides(p, n):
        if n[1] > 0.6:
            return top or p.top
        if n[0] < -0.6:
            return left or p.left
        return st.side_colour(p, n)
    st.extrude(s, st.rect(w, h), z, d, pal, front=front, origin=(x, y), front_svg=front_svg, depth_bias=bias, sides=sides)


def soft(pal):
    """Light face colours for plain blocks: (front, top, left)."""
    return st.mix(pal.cell, pal.hi, 0.55), st.mix(pal.cell, pal.hi, 0.2), pal.hi


def lines(s, segs, colour=GREY, width=0.05, dash=None, depth=-99.0, opacity=1.0):
    pts = [p for seg in segs for p in seg]
    s.add(depth, "<g>" + "".join(st.line3(a, b, colour, width, dash, opacity=opacity) for a, b in segs) + "</g>",
          [st.proj(p) for p in pts])


def dot3(s, p, r, fill, stroke="#ffffff", depth=None, sw=None):
    sx, sy = st.proj(p)
    s.add(st.dot(p, st.D) if depth is None else depth,
          f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="{r:.3f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw or r * 0.32:.3f}"/>',
          [(sx - r, sy - r), (sx + r, sy + r)])


def face_poly(points, z=0.0):
    return [st.proj((x, y, z)) for x, y in points]


def inset(x0, y0, x1, y1, z=0.0):
    return face_poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z)


def stage(s, pal, x, y, size, depth, bands=2, shade=None, bias=0.0):
    """A plain layer block: front face size x size, ``depth`` along z split into ``bands`` conv layers."""
    front, top, left = shade or soft(pal)
    step = depth / bands
    for i in range(bands):
        k = i % 2
        box(s, pal, x, y, i * step, size, size, step, front=front, top=st.mix(top, pal.hi, 0.35 * k),
            left=st.mix(left, pal.base, 0.45 * k), bias=bias)


# ------------------------------------------------------------------ network modules
def b_cnn(title, pals, sizes, depths, pool=None, fc=0, gap=0.5):
    """Plain layer blocks in a row: spatial size shrinks (or grows) while channel depth changes.

    ``pool`` adds a thin pooling plate after each block, ``fc`` adds fully connected bars at the end.
    """
    s = st.Scene()
    x = 0.0
    big = max(sizes)
    for i, (k, n, d) in enumerate(zip(pals, sizes, depths)):
        pal = P[k]
        y = (big - n) / 2
        stage(s, pal, x, y, n, d, bands=3 if d > 1.2 else 2)
        x += n + 0.07
        if pool and i < len(sizes) - 1:
            pp = P[pool]
            h = n * 0.82
            box(s, pp, x, y + (n - h) / 2, 0, 0.26, h, d * 0.92, front=pp.hi, top=st.mix(pp.cell, pp.hi, .4), left=pp.base)
            x += 0.26
        x += gap
    for j in range(fc):
        pal = P[pals[-1]] if j < fc - 1 else P["orange"]
        h = big * (0.78 - 0.2 * j)
        front, top, left = soft(pal)
        box(s, pal, x, (big - h) / 2, 0.3, 0.42, h, 0.42, front=front, top=top, left=left)
        x += 0.42 + gap
    return s.to_svg(title)


def b_unet(title, enc, dec, mid="purple", skip=GREY):
    """Encoder blocks down the left, decoder blocks up the right, dashed skip lines between levels."""
    s = st.Scene()
    sizes, depths = [2.4, 1.8, 1.3, 0.95], [0.5, 0.8, 1.1, 1.4]
    dx, dy = 1.1, 2.4
    width = 2 * len(sizes) * dx + 1.4
    skips = []
    for i, (n, d) in enumerate(zip(sizes, depths)):
        cy = -i * dy
        xe = i * dx
        xd = width - i * dx - n
        stage(s, P[enc], xe, cy - n / 2, n, d)
        stage(s, P[dec], xd, cy - n / 2, n, d)
        skips.append(((xe + n, cy, 0), (xd, cy, 0)))
    n, d = 0.8, 1.8
    cy = -len(sizes) * dy + 0.5
    stage(s, P[mid], width / 2 - n / 2, cy - n / 2, n, d, bands=3)
    lines(s, skips, skip, 0.06, dash="0.18 0.13")
    return s.to_svg(title)


def b_hourglass(title, pal_a, pal_b, latent="amber"):
    """Encoder blocks shrink to a latent vector, decoder blocks grow back."""
    s = st.Scene()
    sizes, depths = [3.0, 2.2, 1.5], [0.4, 0.7, 1.0]
    x = 0.0
    for n, d in zip(sizes, depths):
        stage(s, P[pal_a], x, -n / 2, n, d)
        x += n + 0.45
    lat = P[latent]
    for k in range(5):
        box(s, lat, x, -1.25 + k * 0.5, 0.3, 0.42, 0.42, 0.42, front=lat.ramp(0.15 + 0.15 * k), top=lat.cell, left=lat.hi)
    x += 0.42 + 0.45
    for n, d in zip(sizes[::-1], depths[::-1]):
        stage(s, P[pal_b], x, -n / 2, n, d)
        x += n + 0.45
    return s.to_svg(title)


def b_wedge(title, pal, kind="enc", bands=4, length=4.2, height=3.6, taper=0.95, depth=1.6):
    """Encoder (narrowing) or decoder (widening) drawn as a tapered prism with inset layer strips."""
    p = P[pal]
    s = st.Scene()
    _wedge(s, p, 0.0, 0.0, kind, bands, length, height, taper, depth)
    return s.to_svg(title)


def _wedge(s, p, x0, y0, kind, bands, length, height, taper, depth, z=0.0):
    a = taper
    if kind == "enc":
        outline = [(0, 0), (length, a), (length, height - a), (0, height)]
        half = lambda u: (a * u, height - a * u)  # noqa: E731
    else:
        outline = [(0, a), (length, 0), (length, height), (0, height - a)]
        half = lambda u: (a * (1 - u), height - a * (1 - u))  # noqa: E731
    m, g = 0.16, 0.12
    strip = (length - 2 * m - (bands - 1) * g) / bands
    frags = []
    for i in range(bands):
        u0 = (m + i * (strip + g)) / length
        u1 = (m + i * (strip + g) + strip) / length
        lo0, hi0 = half(u0)
        lo1, hi1 = half(u1)
        pts = [(x0 + u0 * length, y0 + lo0 + m), (x0 + u1 * length, y0 + lo1 + m), (x0 + u1 * length, y0 + hi1 - m),
               (x0 + u0 * length, y0 + hi0 - m)]
        frags.append(st.poly(face_poly(pts, z), p.hi if i % 2 == 0 else st.mix(p.cell, p.hi, 0.45)))
    st.extrude(s, outline, z, depth, p, origin=(x0, y0), front_svg="".join(frags))


def b_wedge_pair(title, pal_a, pal_b, kind="ae", latent="amber"):
    """Encoder and decoder wedges: an autoencoder (with a latent bar) or a bow-tie GAN-style pair."""
    s = st.Scene()
    if kind == "ae":
        _wedge(s, P[pal_a], 0, 0, "enc", 4, 3.6, 3.6, 1.1, 1.4)
        lat = P[latent]
        for k in range(4):
            box(s, lat, 4.15, 0.65 + k * 0.6, 0.35, 0.5, 0.5, 0.5, front=lat.ramp(0.15 + 0.17 * k), top=lat.cell, left=lat.hi)
        _wedge(s, P[pal_b], 5.2, 0, "dec", 4, 3.6, 3.6, 1.1, 1.4)
    elif kind == "siamese":
        _wedge(s, P[pal_a], 0, 2.7, "enc", 4, 3.4, 2.4, 0.7, 1.2)
        _wedge(s, P[pal_b], 0, -0.3, "enc", 4, 3.4, 2.4, 0.7, 1.2)
    else:   # teacher (big) and student (small)
        _wedge(s, P[pal_a], 0, 0, "enc", 5, 4.4, 4.0, 1.2, 1.6)
        _wedge(s, P[pal_b], 5.4, 0.8, "enc", 3, 2.8, 2.4, 0.7, 1.0)
    return s.to_svg(title)


def b_transformer(title, pals, layers=1, tokens=6):
    """Transformer layer as a tower of plates (norm, attention, norm, MLP); each plate shows a row of tokens."""
    s = st.Scene()
    w, h, d, gap = 4.6, 0.62, 1.7, 0.26
    y = 0.0
    plates = [pals[0], pals[1], pals[0], pals[2]] * layers
    for i, k in enumerate(plates):
        p = P[k]
        m, g = 0.14, 0.1
        cw = (w - 2 * m - (tokens - 1) * g) / tokens
        cells = "".join(st.poly(inset(m + c * (cw + g), y + m, m + c * (cw + g) + cw, y + h - m), p.cell if i % 2 == 0 else p.hi)
                        for c in range(tokens))
        thin = i % 2 == 0
        hh = h * (0.62 if thin else 1.0)
        if thin:
            cells = st.poly(inset(m, y + 0.1, w - m, y + hh - 0.1), p.cell)
        box(s, p, 0, y, 0, w, hh, d, front=p.base, front_svg=cells)
        y -= hh + gap + (0.45 if (i % 4 == 3) else 0)
    return s.to_svg(title)


def b_bottleneck(title, pal, inverted=False):
    """Three layers whose channel width (along the flow) goes wide-narrow-wide (or narrow-wide-narrow)."""
    s = st.Scene()
    widths = [0.45, 1.8, 0.45] if inverted else [1.6, 0.4, 1.6]
    x = 0.0
    for i, w in enumerate(widths):
        p = P[pal if i != 1 else ("amber" if pal != "amber" else "orange")]
        f, t, l = soft(p)
        box(s, p, x, 0, 0, w, 3.0, 2.2, front=f, top=t, left=l)
        x += w + 0.6
    return s.to_svg(title)


def b_inception(title, pals):
    """Four parallel branches between an input bar and a concatenation bar."""
    s = st.Scene()
    bar = P["slate"]
    f, t, l = soft(bar)
    box(s, bar, 0, 0, 0, 7.6, 0.45, 1.6, front=f, top=t, left=l)
    branches = [[pals[0]], [pals[0], pals[1]], [pals[0], pals[2]], [pals[3], pals[0]]]
    for b, branch in enumerate(branches):
        y = 0.85
        for k in branch:
            p = P[k]
            f, t, l = soft(p)
            box(s, p, 0.3 + b * 1.85, y, 0.3, 1.25, 0.8, 1.0, front=f, top=t, left=l)
            y += 1.15
    cat = P[pals[2]]
    box(s, cat, 0, 3.45, 0, 7.6, 0.45, 1.6, front=cat.hi, top=cat.cell, left=cat.base)
    return s.to_svg(title)


def b_moe(title, pal, active=(1, 3), experts=4):
    """A row of gate scores under a row of experts; the routed experts are coloured, the rest stay grey."""
    s = st.Scene()
    p = P[pal]
    g = P["slate"]
    w = 1.3
    xs = [i * (w + 0.55) for i in range(experts)]
    for i, x in enumerate(xs):
        q = p if i in active else g
        cells = {(r, c): (q.hi if (r + c) % 2 == 0 else q.cell) for r in range(3) for c in range(2)}
        st.cube(s, q, 2, 3, 2, x=x, y=2.6, z=0, cell=w / 2, colours=cells)
    gate = P["amber"]
    cw = 0.62
    gx = (xs[-1] + w) / 2 - experts * cw / 2
    st.slab(s, gate, experts, 1, x=gx, y=0, z=0.3, cell=cw, thick=0.4, margin=0.09, gap=0.07,
            colours={(0, i): (gate.ink if i in active else gate.cell) for i in range(experts)})
    segs_on = [((gx + (i + 0.5) * cw, cw, 0.5), (xs[i] + w / 2, 2.6, 0.2)) for i in active]
    segs_off = [((gx + (i + 0.5) * cw, cw, 0.5), (xs[i] + w / 2, 2.6, 0.2)) for i in range(experts) if i not in active]
    lines(s, segs_off, GREY, 0.045, dash="0.12 0.1", depth=60)
    lines(s, segs_on, p.base, 0.07, depth=60)
    return s.to_svg(title)


def b_dense(title, pal, n=4):
    """Dense connectivity: every block links to every later block with an arc over the top."""
    s = st.Scene()
    p = P[pal]
    size, step = 2.0, 2.45
    xs = [i * step for i in range(n)]
    for i, x in enumerate(xs):
        stage(s, P[pal] if i % 2 == 0 else P["teal" if pal != "teal" else "blue"], x, 0, size, 0.35, bands=1)
    arcs, bounds = [], []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = xs[i] + 0.5, xs[j] + 0.5
            hgt = size + 0.35 + 0.42 * (j - i)
            pts = [st.proj((a + (b - a) * t, size + (hgt - size) * math.sin(math.pi * t), 0.2)) for t in [k / 24 for k in range(25)]]
            bounds += pts
            arcs.append(f'<polyline points="{st.pts_attr(pts)}" fill="none" stroke="{p.ink if j - i == 1 else GREY}" '
                        f'stroke-width="0.055" stroke-linecap="round"/>')
    s.add(-99, "<g>" + "".join(arcs) + "</g>", bounds)
    return s.to_svg(title)


def b_fpn(title, pal_a, pal_b, levels=4):
    """Backbone pyramid on the left, output pyramid on the right, dashed lateral links."""
    s = st.Scene()
    sizes = [4, 3, 2, 1][:levels]
    y = 0.0
    lat = []
    for i, n in enumerate(sizes):
        a, b = P[pal_a], P[pal_b]
        cell = 0.62
        w = n * cell
        st.slab(s, a, n, n, x=-w / 2, y=y, z=0, cell=cell, thick=0.28, colours={(r, c): a.cell for r in range(n) for c in range(n)},
                margin=0.1, gap=0.07)
        st.slab(s, b, n, n, x=5.2 - w / 2, y=y, z=0, cell=cell, thick=0.28, colours={(r, c): b.hi for r in range(n) for c in range(n)},
                margin=0.1, gap=0.07)
        lat.append(((w / 2, y + w / 2, 0), (5.2 - w / 2, y + w / 2, 0)))
        y += w + 0.75
    lines(s, lat, GREY, 0.055, dash="0.16 0.12")
    return s.to_svg(title)


def b_codebook(title, pal, rows=8, cols=5, pick=3, seed=2):
    """A codebook (embedding table) with one selected entry highlighted."""
    p = P[pal]
    g = st.rng(seed)
    cells = {}
    for r in range(rows):
        for c in range(cols):
            v = g.random()
            cells[(r, c)] = p.ramp(0.25 + 0.7 * v) if r == pick else st.mix(P["slate"].cell, P["slate"].hi, 0.6 * v)
    s = st.Scene()
    st.slab(s, p if True else P["slate"], cols, rows, cell=0.62, colours=cells, gap=0.07, margin=0.12)
    return s.to_svg(title)


def b_queue(title, pal, n=7):
    """A memory queue: vectors side by side, the newest in full colour, older ones fading."""
    p = P[pal]
    s = st.Scene()
    g = st.rng(5)
    for i in range(n):
        t = i / (n - 1)
        cells = {(r, 0): st.mix(P["slate"].cell, p.ramp(0.15 + 0.8 * g.random()), 0.25 + 0.75 * t) for r in range(5)}
        st.slab(s, p if i == n - 1 else P["slate"], 1, 5, x=i * 0.95, cell=0.7, colours=cells, thick=0.5, margin=0.1, gap=0.07)
    return s.to_svg(title)


def b_pool_vector(title, pal, kind="gap"):
    """A C x H x W tensor next to its pooled 1 x 1 x C vector (GAP) or its flattened row (flatten)."""
    p = P[pal]
    s = st.Scene()
    g = st.rng(3)
    if kind == "gap":
        st.cube(s, p, 3, 3, 4, cell=0.8)
        left = {(0, k): p.ramp(0.15 + 0.8 * g.random()) for k in range(4)}
        st.cube(s, p, 1, 1, 4, x=3.9, y=0.8, cell=0.8, colours={(0, 0): left[(0, 0)]}, left_colours=left,
                top_colours={(k, 0): left[(0, k)] for k in range(4)})
    else:
        st.cube(s, p, 3, 3, 2, cell=0.8)
        row = {(0, c): p.ramp(0.15 + 0.8 * g.random()) for c in range(9)}
        st.slab(s, p, 9, 1, x=3.4, y=0.9, z=-1.2, cell=0.62, colours=row, thick=0.45, margin=0.1, gap=0.06)
    return s.to_svg(title)


def b_channel_attention(title, pal, kind="channel"):
    """Channel attention re-weights whole channels; spatial attention re-weights positions."""
    p = P[pal]
    s = st.Scene()
    g = st.rng(8)
    n, c = 4, 5
    if kind == "channel":
        w = [0.1 + 0.85 * g.random() for _ in range(c)]
        st.cube(s, p, n, n, c, cell=0.75, colours={(r, k): p.cell for r in range(n) for k in range(n)},
                top_colours={(k, col): p.ramp(w[k]) for k in range(c) for col in range(n)},
                left_colours={(r, k): p.ramp(w[k]) for r in range(n) for k in range(c)})
        st.cube(s, P["amber"], 1, 1, c, x=n * 0.75 + 1.0, y=n * 0.75 + 0.6, cell=0.75,
                top_colours={(k, 0): P["amber"].ramp(w[k]) for k in range(c)},
                left_colours={(0, k): P["amber"].ramp(w[k]) for k in range(c)}, colours={(0, 0): P["amber"].ramp(w[0])})
    else:
        heat = {(r, k): p.ramp(math.exp(-((r - 1.3) ** 2 + (k - 2.0) ** 2) / 2.2)) for r in range(n) for k in range(n)}
        st.cube(s, p, n, n, c, cell=0.75, colours=heat)
        st.slab(s, P["amber"], n, n, x=n * 0.75 + 1.1, y=0.4, z=-0.6, cell=0.6, thick=0.25,
                colours={k: P["amber"].ramp(math.exp(-((k[0] - 1.3) ** 2 + (k[1] - 2.0) ** 2) / 2.2)) for k in heat})
    return s.to_svg(title)


def b_plain(title, pal, w, h, d, style="soft"):
    """A plain cuboid without grid cells."""
    p = P[pal]
    s = st.Scene()
    if style == "soft":
        f, t, l = soft(p)
        box(s, p, 0, 0, 0, w, h, d, front=f, top=t, left=l)
    else:
        box(s, p, 0, 0, 0, w, h, d)
    return s.to_svg(title)


def b_glass(title, pal, w=3.2, h=3.2, d=2.4):
    """A translucent tensor: tinted faces with solid near edges and dashed hidden edges."""
    p = P[pal]
    s = st.Scene()
    corners = {(i, j, k): (i * w, j * h, k * d) for i in (0, 1) for j in (0, 1) for k in (0, 1)}
    faces = [[(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)], [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
             [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)],
             [(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)], [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]]
    fills = [p.cell, p.cell, p.cell, p.hi, p.hi, p.hi]
    body = []
    for f, c in zip(faces, fills):
        body.append(st.poly([st.proj(corners[v]) for v in f], c, ' fill-opacity="0.32"'))
    hidden = (1, 0, 1)
    for a in corners:
        for axis in range(3):
            if a[axis] == 0:
                b = list(a)
                b[axis] = 1
                b = tuple(b)
                dashed = hidden in (a, b)
                body.append(st.line3(corners[a], corners[b], p.base, 0.045 if dashed else 0.065, dash="0.12 0.1" if dashed else None))
    s.add(0, "<g>" + "".join(body) + "</g>", [st.proj(v) for v in corners.values()])
    return s.to_svg(title)


# ------------------------------------------------------------------ feature maps with scientific colour maps
CMAPS = {
    "viridis": ["#440154", "#482878", "#3e4a89", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"],
    "magma": ["#000004", "#1c1044", "#4f127b", "#812581", "#b5367a", "#e55964", "#fb8761", "#fec287", "#fcfdbf"],
    "plasma": ["#0d0887", "#46039f", "#7201a8", "#9c179e", "#bd3786", "#d8576b", "#ed7953", "#fb9f3a", "#fdca26", "#f0f921"],
    "turbo": ["#30123b", "#4662d7", "#36aaf9", "#1ae4b6", "#72fe5e", "#c8ef34", "#faba39", "#f66b19", "#ca2a04", "#7a0403"],
    "coolwarm": ["#3b4cc0", "#6788ee", "#9abbff", "#c9d7f0", "#edd1c2", "#f7a889", "#e26952", "#b40426"],
}
CMAP_ZH = {"viridis": "Viridis", "magma": "Magma", "plasma": "Plasma", "turbo": "Turbo", "coolwarm": "冷暖发散"}


def cmap(name, t):
    colours = CMAPS[name]
    t = max(0.0, min(0.9999, t))
    i = t * (len(colours) - 1)
    k = int(i)
    return st.mix(colours[k], colours[k + 1], i - k)


def smooth_field(rows, cols, seed, blobs=4):
    """Sum of random Gaussian bumps scaled to 0..1."""
    g = st.rng(seed)
    centres = [(g.random(), g.random(), 0.14 + g.random() * 0.16, 0.5 + g.random() * 0.6) for _ in range(blobs)]
    out = {}
    for r in range(rows):
        for c in range(cols):
            y, x = r / max(rows - 1, 1), c / max(cols - 1, 1)
            out[(r, c)] = sum(a * math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * s * s)) for cx, cy, s, a in centres)
    lo, hi = min(out.values()), max(out.values())
    return {k: (v - lo) / (hi - lo + 1e-9) for k, v in out.items()}


def b_cmap_map(title, name, n=8, channels=1, seed=0):
    s = st.Scene()
    for i in range(channels):
        f = smooth_field(n, n, seed + i * 7)
        st.slab(s, P["slate"], n, n, cell=0.55, z=i * 0.7, thick=0.3, colours={k: cmap(name, v) for k, v in f.items()},
                margin=0.12, gap=0.05)
    return s.to_svg(title)


def b_masked_map(title, pal, kind="masked", n=6, seed=3):
    """MAE-style masked positions (grey) or a sparse map (only active cells coloured)."""
    p = P[pal]
    g = st.rng(seed)
    cells = {}
    for r in range(n):
        for c in range(n):
            on = g.random() < (0.3 if kind == "masked" else 0.22)
            if kind == "masked":
                cells[(r, c)] = st.mix(p.cell, p.hi, g.random()) if on else "#c9d0da"
            else:
                cells[(r, c)] = (p.ink if g.random() < 0.4 else p.hi) if on else "#f1f4f8"
    s = st.Scene()
    st.slab(s, p, n, n, colours=cells)
    return s.to_svg(title)


def b_groups(title, pals, kind="split"):
    """Channel groups pulled apart (grouped convolution) or channels interleaved (channel shuffle)."""
    s = st.Scene()
    if kind == "split":
        for i, k in enumerate(pals):
            st.cube(s, P[k], 3, 3, 1, z=i * 1.45, cell=0.9)
        return s.to_svg(title)
    w, gap = 0.34, 0.12
    order = [(g, j) for g in range(3) for j in range(3)]
    shuffled = [(g, j) for j in range(3) for g in range(3)]
    for row, seq in ((1, order), (0, shuffled)):
        for i, (g, _) in enumerate(seq):
            p = P[pals[g]]
            f, t, l = soft(p)
            box(s, p, i * (w + gap), row * 3.0, 0, w, 2.1, 1.4, front=p.hi, top=t, left=p.base)
    return s.to_svg(title)


# ------------------------------------------------------------------ convolution and sampling
def centre(r, c, rows, cols, cell=1.0, margin=0.13, gap=0.09, x0=0.0, y0=0.0):
    """Centre of cell (r, c) of a slab drawn with ``st.slab`` at (x0, y0); row 0 is the top row."""
    cw = (cols * cell - 2 * margin - (cols - 1) * gap) / cols
    ch = (rows * cell - 2 * margin - (rows - 1) * gap) / rows
    return x0 + margin + c * (cw + gap) + cw / 2, y0 + rows * cell - margin - r * (ch + gap) - ch / 2


def b_deform_conv(title, pal, n=7, seed=4):
    """Regular 3 x 3 sampling positions (hollow) and learned offset positions (filled)."""
    p = P[pal]
    g = st.rng(seed)
    s = st.Scene()
    st.slab(s, P["slate"], n, n, colours={(r, c): "#eef1f6" for r in range(n) for c in range(n)})
    segs, dots = [], []
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            x, y = centre(3 + 2 * i, 3 + 2 * j, n, n)
            a = g.uniform(0, 2 * math.pi)
            d = 0 if (i, j) == (0, 0) else g.uniform(0.45, 0.85)
            ox, oy = d * math.cos(a), d * math.sin(a)
            segs.append(((x, y, 0), (x + ox, y + oy, 0)))
            dots.append(((x, y, 0), (x + ox, y + oy, 0)))
    lines(s, segs, p.base, 0.05, dash="0.1 0.08", depth=-90)
    for a, b in dots:
        dot3(s, a, 0.17, "#ffffff", stroke=GREY, depth=-91, sw=0.06)
        dot3(s, b, 0.24, p.base, depth=-92)
    return s.to_svg(title)


def b_transposed(title, pal_in, pal_out):
    """One input cell spreads over a 3 x 3 output window (transposed convolution)."""
    a, b = P[pal_in], P[pal_out]
    s = st.Scene()
    st.slab(s, a, 2, 2, colours={(0, 0): a.ink})
    ox, oy, oz = 3.6, -0.6, -3.4
    win = {(r, c): b.hi for r in range(3) for c in range(3)}
    win[(1, 1)] = b.ink
    st.slab(s, b, 5, 5, x=ox, y=oy, z=oz, colours=win)
    m, gp = 0.13, 0.09
    cw = (2 - 2 * m - gp) / 2
    src = [(m, 2 - m - cw), (m + cw, 2 - m - cw), (m + cw, 2 - m), (m, 2 - m)]
    cwo = (5 - 2 * m - 4 * gp) / 5
    x0, y1 = ox + m, oy + 5 - m
    x1, y0 = x0 + 3 * cwo + 2 * gp, y1 - 3 * cwo - 2 * gp
    dst = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    lines(s, [((px, py, 0), (qx, qy, oz)) for (px, py), (qx, qy) in zip(src, dst)], a.ink, 0.045, dash="0.16 0.12", opacity=0.75)
    return s.to_svg(title)


def b_pixel_shuffle(title):
    """Four 2 x 2 channels rearranged into one 4 x 4 map."""
    s = st.Scene()
    q = ["blue", "teal", "orange", "purple"]
    for i, k in enumerate(q):
        st.slab(s, P[k], 2, 2, z=i * 0.6, thick=0.28, colours={(r, c): P[k].hi for r in range(2) for c in range(2)})
    big = {(r, c): P[q[(r % 2) * 2 + c % 2]].hi for r in range(4) for c in range(4)}
    st.slab(s, P["slate"], 4, 4, x=3.6, y=-1.0, z=-2.2, colours=big)
    return s.to_svg(title)


def b_stride(title, pal, n=7):
    """A 3 x 3 window and the stride-2 positions it visits."""
    p = P[pal]
    cells = {(r, c): p.hi for r in range(3) for c in range(3)}
    s = st.Scene()
    st.slab(s, p, n, n, colours=cells)
    for r in range(1, n, 2):
        for c in range(1, n, 2):
            dot3(s, (*centre(r, c, n, n), 0), 0.13, p.ink if (r, c) == (1, 1) else P["slate"].hi, depth=-90, sw=0.04)
    return s.to_svg(title)


def b_padding(title, pal, n=6):
    p = P[pal]
    cells = {(r, c): ("#f4f6f9" if r in (0, n - 1) or c in (0, n - 1) else st.mix(p.cell, p.hi, 0.5 * ((r * 3 + c * 5) % 4) / 3))
             for r in range(n) for c in range(n)}
    s = st.Scene()
    st.slab(s, p, n, n, colours=cells)
    return s.to_svg(title)


KERNELS = {
    "sobel": [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]],
    "laplacian": [[0, 1, 0], [1, -4, 1], [0, 1, 0]],
    "gaussian": [[1, 4, 6, 4, 1], [4, 16, 24, 16, 4], [6, 24, 36, 24, 6], [4, 16, 24, 16, 4], [1, 4, 6, 4, 1]],
}


def b_classic_kernel(title, kind):
    k = KERNELS[kind]
    n = len(k)
    top = max(abs(v) for row in k for v in row)
    if kind == "gaussian":
        cells = {(r, c): P["purple"].ramp(k[r][c] / top) for r in range(n) for c in range(n)}
    else:
        cells = {(r, c): cmap("coolwarm", 0.5 + 0.5 * k[r][c] / top) for r in range(n) for c in range(n)}
    s = st.Scene()
    st.slab(s, P["slate"], n, n, colours=cells, thick=0.5)
    return s.to_svg(title)


def b_separable(title, pal, k=5):
    p = P[pal]
    g = st.rng(2)
    s = st.Scene()
    st.slab(s, p, 1, k, colours={(r, 0): p.ramp(0.2 + 0.7 * g.random()) for r in range(k)}, thick=0.5)
    st.slab(s, p, k, 1, x=1.9, y=(k - 1) / 2, colours={(0, c): p.ramp(0.2 + 0.7 * g.random()) for c in range(k)}, thick=0.5)
    return s.to_svg(title)


def b_patch_merge(title):
    """A 4 x 4 map split by position parity into four 2 x 2 maps stacked along channels (Swin patch merging)."""
    q = ["blue", "teal", "orange", "purple"]
    s = st.Scene()
    st.slab(s, P["slate"], 4, 4, colours={(r, c): P[q[(r % 2) * 2 + c % 2]].hi for r in range(4) for c in range(4)})
    for i, k in enumerate(q):
        st.slab(s, P[k], 2, 2, x=5.3, y=1.0, z=-1.0 + i * 0.62, thick=0.3, colours={(r, c): P[k].hi for r in range(2) for c in range(2)})
    return s.to_svg(title)


def b_bilinear(title, pal):
    """A sample point between four grid points, weighted by its distance to each."""
    p = P[pal]
    s = st.Scene()
    st.slab(s, P["slate"], 2, 2, cell=1.8, colours={(r, c): "#eef1f6" for r in range(2) for c in range(2)}, margin=0.1, gap=0.06)
    pts = [centre(r, c, 2, 2, 1.8, 0.1, 0.06) for r in range(2) for c in range(2)]
    q = (pts[0][0] + 0.62 * (pts[1][0] - pts[0][0]), pts[2][1] + 0.35 * (pts[0][1] - pts[2][1]))
    lines(s, [((q[0], q[1], 0), (x, y, 0)) for x, y in pts], p.base, 0.04, dash="0.1 0.08", depth=-90)
    for x, y in pts:
        dot3(s, (x, y, 0), 0.2, P["slate"].base, depth=-91)
    dot3(s, (q[0], q[1], 0), 0.24, P["coral"].base, depth=-92)
    return s.to_svg(title)


# ------------------------------------------------------------------ attention patterns
WINDOW_TINTS = ["#8ec2ff", "#a6ede3", "#ffd7a8", "#d0c3ff", "#b5ebc1", "#ffc4cb", "#ffe9a8", "#d7dfea", "#c7e3ff"]


def b_windows(title, shifted=False, pal=None, n=8, size=4):
    """Window partition (Swin): cells coloured by window, optionally shifted by half a window."""
    s = st.Scene()
    off = size // 2 if shifted else 0
    cells = {}
    for r in range(n):
        for c in range(n):
            wr, wc = (r + off) // size, (c + off) // size
            wid = wr * 3 + wc
            if pal:
                p = P[pal]
                cells[(r, c)] = p.hi if (wr + wc) % 2 == 0 else p.cell
            else:
                cells[(r, c)] = WINDOW_TINTS[wid % len(WINDOW_TINTS)]
    st.slab(s, P[pal] if pal else P["slate"], n, n, cell=0.6, colours=cells, margin=0.12, gap=0.06)
    return s.to_svg(title)


def b_deform_attn(title, pal, levels=1, seed=5):
    """A reference point and a few learned sampling points with their attention weights (dot size)."""
    p = P[pal]
    s = st.Scene()
    g = st.rng(seed)
    for lv in range(levels):
        n = [8, 6, 4][lv]
        cell = 0.6
        side = n * cell
        x0, y0, z = lv * 3.1, (4.8 - side) / 2, -lv * 2.4
        st.slab(s, P["slate"], n, n, x=x0, y=y0, z=z, cell=cell, thick=0.22, margin=0.1, gap=0.05,
                colours={(r, c): "#eef1f6" for r in range(n) for c in range(n)}, depth_bias=0)
        ref = (x0 + side * 0.48, y0 + side * 0.52, z)
        segs = []
        pts = []
        for k in range(4):
            a = g.uniform(0, 2 * math.pi)
            d = g.uniform(0.32, 0.36) * side
            q = (ref[0] + d * math.cos(a), ref[1] + d * math.sin(a), z)
            segs.append((ref, q))
            pts.append((q, 0.1 + 0.14 * g.random()))
        lines(s, segs, p.base, 0.04, dash="0.1 0.08", depth=st.dot(ref, st.D) - 0.5)
        for q, r in pts:
            dot3(s, q, r, p.hi, stroke=p.base, depth=st.dot(ref, st.D) - 0.6, sw=0.04)
        dot3(s, ref, 0.2, P["coral"].base, depth=st.dot(ref, st.D) - 0.7)
    return s.to_svg(title)


def b_query_pattern(title, pal, kind="axial", n=7, q=(2, 4)):
    """Which positions one query attends to: its row and column (axial), a local window, or everything (global)."""
    p = P[pal]
    cells = {}
    for r in range(n):
        for c in range(n):
            if kind == "axial":
                v = p.hi if (r == q[0] or c == q[1]) else p.cell
            elif kind == "local":
                d = max(abs(r - q[0]), abs(c - q[1]))
                v = p.hi if d == 1 else st.mix(p.cell, p.hi, 0.45) if d == 2 else p.cell
            else:
                v = p.ramp(0.85 * math.exp(-((r - q[0]) ** 2 + (c - q[1]) ** 2) / 9) + 0.15 * ((r * 7 + c * 3) % 5) / 4)
            cells[(r, c)] = v
    cells[q] = p.ink
    s = st.Scene()
    st.slab(s, p, n, n, colours=cells)
    return s.to_svg(title)


def b_heads(title, pals, n=6, seed=1):
    """Attention maps of several heads stacked one behind another."""
    s = st.Scene()
    g = st.rng(seed)
    for i, k in enumerate(pals):
        p = P[k]
        base = [[g.random() for _ in range(n)] for _ in range(n)]
        shift = i - 1
        val = lambda r, c: 0.75 * math.exp(-((r - c - shift) ** 2) / 1.5) + 0.25 * base[r][c]  # noqa: E731
        st.slab(s, p, n, n, cell=0.62, z=i * 0.85, thick=0.25, gap=0.06, margin=0.11,
                colours={(r, c): p.ramp(val(r, c)) for r in range(n) for c in range(n)})
    return s.to_svg(title)


def b_cross(title, pal_q, pal_k, rows=4, cols=7, kind="cross", seed=3, mat="purple"):
    """A query x key matrix with its query tokens on the left and key tokens on top; ``kind="clip"`` lights the diagonal."""
    a, b = P[pal_q], P[pal_k]
    g = st.rng(seed)
    cell = 0.7
    m = P[mat]
    if kind == "clip":
        cols = rows
        cells = {(r, c): (m.ink if r == c else st.mix("#f1f4f8", m.cell, 0.8 * g.random())) for r in range(rows) for c in range(cols)}
    else:
        cells = {(r, c): m.ramp(0.05 + 0.85 * g.random() ** 1.6) for r in range(rows) for c in range(cols)}
    s = st.Scene()
    st.slab(s, m, cols, rows, cell=cell, colours=cells, gap=0.07, margin=0.12)
    t = cell * 0.68
    for r in range(rows):
        x, y = centre(r, 0, rows, cols, cell, 0.12, 0.07)
        st.extrude(s, st.rect(t, t), 0, t, a, origin=(-1.0 - t / 2, y - t / 2), front=a.hi)
    for c in range(cols):
        x, y = centre(0, c, rows, cols, cell, 0.12, 0.07)
        st.extrude(s, st.rect(t, t), 0, t, b, origin=(x - t / 2, rows * cell + 0.45), front=b.hi)
    return s.to_svg(title)


def b_token_row(title, pals, kind="prune", n=8):
    """Tokens with some dropped (pruning), pairs merged into wider tokens (merging), or with an ellipsis in the middle."""
    s = st.Scene()
    size, gx = 0.72, 0.24
    x = 0.0
    if kind == "merge":
        widths = [1, 2, 1, 1, 3, 1]
        for i, w in enumerate(widths):
            p = P[pals[i % len(pals)]]
            ww = w * size + (w - 1) * gx
            st.extrude(s, st.rect(ww, size), 0, size, p, origin=(x, 0), front=p.hi if w > 1 else p.base)
            x += ww + gx
        return s.to_svg(title)
    if kind == "ellipsis":
        for i in range(n):
            if i in (3, 4):
                if i == 3:
                    for j in range(3):
                        dot3(s, (x + 0.12 + j * 0.36, size / 2, 0), 0.12, P["slate"].base, stroke="none")
                    x += 1.45
                continue
            p = P[pals[0]]
            st.extrude(s, st.rect(size, size), 0, size, p, origin=(x, 0), front=p.hi if i % 2 else p.base)
            x += size + gx
        return s.to_svg(title)
    dropped = {1, 4, 5}
    for i in range(n):
        p = P[pals[0]]
        if i in dropped:
            g = P["slate"]
            st.extrude(s, st.rect(size, size), 0, size, g, origin=(x, 0), front="#e3e8ef", sides="#cfd6e0")
        else:
            st.extrude(s, st.rect(size, size), 0, size, p, origin=(x, 0), front=p.hi if i % 2 else p.base)
        x += size + gx
    return s.to_svg(title)


def b_registers(title):
    s = st.Scene()
    size, gx = 0.72, 0.24
    seq = ["amber"] + ["blue"] * 6 + ["slate"] * 2
    for i, k in enumerate(seq):
        p = P[k]
        st.extrude(s, st.rect(size, size), 0, size, p, origin=(i * (size + gx) + (0.3 if i > 0 else 0) + (0.3 if i > 6 else 0), 0),
                   front=p.hi if (k == "blue" and i % 2) else p.base)
    return s.to_svg(title)


def b_posenc(title, kind="sin", rows=32, cols=24):
    """Sinusoidal position encoding (positions x dimensions) or a relative position bias table."""
    cells = {}
    for r in range(rows):
        for c in range(cols):
            if kind == "sin":
                freq = 1 / (50 ** ((c // 2) * 2 / cols))
                v = math.sin(r * freq) if c % 2 == 0 else math.cos(r * freq)
            else:
                d = abs(r - c * rows / cols)
                v = math.cos(d * 0.55) * math.exp(-d / 6)
            cells[(r, c)] = cmap("coolwarm", 0.5 + 0.5 * v)
    s = st.Scene()
    cell = 5.0 / max(rows, cols)
    st.slab(s, P["slate"], cols, rows, cell=cell, colours=cells, gap=0.0, margin=0.12, thick=0.32)
    return s.to_svg(title)


# ------------------------------------------------------------------ detection and segmentation
def panel(s, pal, w, h, frags, thick=0.42, fill="#ffffff"):
    inner = st.poly(inset(0.15, 0.15, w - 0.15, h - 0.15), fill)
    st.extrude(s, st.rect(w, h), 0, thick, pal, front_svg=inner + "".join(frags))


def rect_path(x0, y0, x1, y1, stroke, width=0.07, fill="none", opacity=None, dash=None):
    pts = inset(x0, y0, x1, y1)
    extra = f' fill-opacity="{opacity}"' if opacity is not None else ""
    extra += f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polygon points="{st.pts_attr(pts)}" fill="{fill}"{extra} stroke="{stroke}" stroke-width="{width}"/>'


def b_iou(title, pal_a="blue", pal_b="coral", over="amber"):
    s = st.Scene()
    a, b, o = P[pal_a], P[pal_b], P[over]
    A, B = (0.8, 0.9, 3.6, 3.2), (2.1, 1.7, 5.0, 3.8)
    I = (max(A[0], B[0]), max(A[1], B[1]), min(A[2], B[2]), min(A[3], B[3]))
    frags = [rect_path(*A, a.base, fill=a.cell, opacity=0.55, width=0.08), rect_path(*B, b.base, fill=b.cell, opacity=0.55, width=0.08),
             rect_path(*I, o.ink, fill=o.hi, opacity=0.9, width=0.05)]
    panel(s, P["slate"], 5.8, 4.6, frags)
    return s.to_svg(title)


def b_nms(title, pal="green"):
    s = st.Scene()
    p = P[pal]
    cands = [(1.0, 0.9, 3.9, 3.7), (1.3, 0.7, 4.2, 3.4), (0.8, 1.2, 3.6, 3.9), (1.5, 1.0, 4.4, 3.9)]
    frags = [rect_path(*c, GREY, width=0.05, dash="0.14 0.1") for c in cands]
    frags.append(rect_path(1.15, 0.95, 4.05, 3.75, p.base, fill=p.cell, opacity=0.35, width=0.1))
    panel(s, P["slate"], 5.4, 4.6, frags)
    return s.to_svg(title)


def b_box_regression(title):
    s = st.Scene()
    anchor, gt = (1.0, 1.0, 3.4, 3.2), (1.7, 1.4, 4.6, 3.9)
    ca = ((anchor[0] + anchor[2]) / 2, (anchor[1] + anchor[3]) / 2)
    cg = ((gt[0] + gt[2]) / 2, (gt[1] + gt[3]) / 2)
    frags = [rect_path(*anchor, GREY, width=0.06, dash="0.16 0.11"), rect_path(*gt, P["green"].base, fill=P["green"].cell, opacity=0.3, width=0.08)]
    a, b = st.proj((*ca, 0)), st.proj((*cg, 0))
    frags.append(f'<line x1="{a[0]:.3f}" y1="{a[1]:.3f}" x2="{b[0]:.3f}" y2="{b[1]:.3f}" stroke="{P["coral"].base}" stroke-width="0.06" '
                 f'stroke-dasharray="0.1 0.08"/>')
    for (x, y), col in ((ca, GREY), (cg, P["green"].base)):
        sx, sy = st.proj((x, y, 0))
        frags.append(f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="0.12" fill="{col}"/>')
    panel(s, P["slate"], 5.6, 4.8, frags)
    return s.to_svg(title)


def b_roi_align(title, pal="coral", n=6):
    s = st.Scene()
    p = P[pal]
    st.slab(s, P["slate"], n, n, colours={(r, c): "#eef1f6" for r in range(n) for c in range(n)})
    x0, y0, x1, y1 = 1.35, 1.55, 4.55, 4.35
    frags = [rect_path(x0, y0, x1, y1, p.base, width=0.08)]
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
    for a, b in (((xm, y0), (xm, y1)), ((x0, ym), (x1, ym))):
        pa, pb = st.proj((*a, 0)), st.proj((*b, 0))
        frags.append(f'<line x1="{pa[0]:.3f}" y1="{pa[1]:.3f}" x2="{pb[0]:.3f}" y2="{pb[1]:.3f}" stroke="{p.base}" '
                     f'stroke-width="0.05" stroke-dasharray="0.1 0.08"/>')
    for bx in (x0, xm):
        for by in (y0, ym):
            for u in (0.25, 0.75):
                for v in (0.25, 0.75):
                    sx, sy = st.proj((bx + u * (xm - x0), by + v * (ym - y0), 0))
                    frags.append(f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="0.09" fill="{p.ink}"/>')
    s.add(-90, "<g>" + "".join(frags) + "</g>", [st.proj((x0, y0, 0)), st.proj((x1, y1, 0))])
    return s.to_svg(title)


def b_centre_heat(title, pal, n=10):
    """Object centres as Gaussian peaks on a heat map (CenterNet style)."""
    p = P[pal]
    peaks = [(2.5, 2.2, 1.3), (6.5, 6.8, 1.7), (2.2, 7.4, 1.0)]
    cells = {}
    for r in range(n):
        for c in range(n):
            v = max(math.exp(-((r - pr) ** 2 + (c - pc) ** 2) / (2 * s * s)) for pr, pc, s in peaks)
            cells[(r, c)] = p.ramp(0.05 + 0.95 * v)
    for pr, pc, _ in peaks:
        cells[(round(pr), round(pc))] = p.ink
    s = st.Scene()
    st.slab(s, p, n, n, cell=0.55, colours=cells, margin=0.12, gap=0.05)
    return s.to_svg(title)


def blob_mask(n, cx, cy, rx, ry, wobble=0.18, seed=0):
    g = st.rng(seed)
    ph = [g.uniform(0, 6.28) for _ in range(3)]
    out = set()
    for r in range(n):
        for c in range(n):
            dx, dy = (c + 0.5) / n - cx, (r + 0.5) / n - cy
            a = math.atan2(dy, dx)
            rr = 1 + wobble * (math.sin(2 * a + ph[0]) + 0.6 * math.sin(3 * a + ph[1]))
            if (dx / rx) ** 2 + (dy / ry) ** 2 < rr * rr:
                out.add((r, c))
    return out


def b_mask_stack(title, pals, n=8):
    """Binary masks of several instances (one per slab), stacked like mask predictions."""
    s = st.Scene()
    shapes = [(0.35, 0.45, 0.24, 0.3), (0.65, 0.6, 0.26, 0.22), (0.5, 0.3, 0.32, 0.18), (0.3, 0.7, 0.18, 0.2)]
    for i, k in enumerate(pals):
        p = P[k]
        m = blob_mask(n, *shapes[i % 4], seed=i)
        st.slab(s, p, n, n, cell=0.55, z=i * 0.95, thick=0.25, margin=0.11, gap=0.05,
                colours={(r, c): (p.hi if (r, c) in m else "#f1f4f8") for r in range(n) for c in range(n)})
    return s.to_svg(title)


SEG = {"sky": "#8ec2ff", "building": "#b39ddb", "tree": "#58c674", "road": "#8e9db2", "car": "#f2717f", "person": "#ffb74d",
       "walk": "#ffe082"}


def b_label_grid(title, kind="semantic", n=14):
    """A pixel label map of a street scene: semantic classes, or each object instance in its own colour."""
    cells = {}
    inst = ["#f2717f", "#4fc3f7", "#ffb74d", "#ba68c8", "#81c784", "#ff8a65", "#9575cd"]
    for r in range(n):
        for c in range(n):
            y, x = r / n, c / n
            if y < 0.38 - 0.18 * (x > 0.62) + 0.05 * math.sin(x * 9):
                lab = "sky"
            elif (x < 0.22 and y < 0.62) or (x > 0.62 and y < 0.6):
                lab = "building"
            elif 0.25 < x < 0.42 and 0.3 < y < 0.62:
                lab = "tree"
            elif y > 0.86:
                lab = "walk"
            else:
                lab = "road"
            cells[(r, c)] = SEG[lab]
    objects = [(0.52, 0.6, 0.86, 0.8, "car"), (0.06, 0.64, 0.38, 0.86, "car"), (0.42, 0.44, 0.5, 0.8, "person"),
               (0.86, 0.48, 0.94, 0.84, "person")]     # x0, y0, x1, y1 with y measured from the top
    if kind == "instance":
        cells = {k: "#e3e8ef" for k in cells}
    for i, (x0, y0, x1, y1, lab) in enumerate(objects):
        for r in range(n):
            for c in range(n):
                x, y = (c + 0.5) / n, (r + 0.5) / n
                if x0 <= x <= x1 and y0 <= y <= y1:
                    cells[(r, c)] = SEG[lab] if kind == "semantic" else inst[i]
    s = st.Scene()
    st.slab(s, P["slate"], n, n, cell=0.4, colours=cells, gap=0.0, margin=0.12, thick=0.32)
    return s.to_svg(title)


# ------------------------------------------------------------------ tokens and vectors
def b_onehot(title, pal, n=8, hot=2, latent=False, seed=6):
    p = P[pal]
    g = st.rng(seed)
    if latent:
        cells = {(r, 0): cmap("coolwarm", 0.5 + 0.45 * max(-1, min(1, g.gauss(0, 0.55)))) for r in range(n)}
    else:
        cells = {(r, 0): (p.ink if r == hot else "#f1f4f8") for r in range(n)}
    s = st.Scene()
    st.slab(s, P["slate"] if latent else p, 1, n, cell=0.7, colours=cells, thick=0.55, margin=0.1, gap=0.07)
    return s.to_svg(title)


# ------------------------------------------------------------------ graphs
def ground(p):
    return (p[0], 0.0, -p[1])


def b_graph_kind(title, pal, alt, kind="knn", seed=11):
    g = st.rng(seed)
    p, q = P[pal], P[alt]
    s = st.Scene()
    if kind == "knn":
        pts = []
        while len(pts) < 13:
            cand = (g.uniform(0, 5.6), g.uniform(0, 4.2))
            if all((cand[0] - u) ** 2 + (cand[1] - v) ** 2 > 1.1 for u, v in pts):
                pts.append(cand)
        edges = set()
        for i, a in enumerate(pts):
            near = sorted(range(len(pts)), key=lambda j: (pts[j][0] - a[0]) ** 2 + (pts[j][1] - a[1]) ** 2)[1:4]
            edges |= {tuple(sorted((i, j))) for j in near}
        lines(s, [(ground(pts[a]), ground(pts[b])) for a, b in edges], P["slate"].hi, 0.05, depth=80)
        for i, pt in enumerate(pts):
            st.disc(s, q if i == 4 else p, *ground(pt), 0.26)
    elif kind == "bipartite":
        left = [(0.0, y) for y in (0, 1.2, 2.4, 3.6)]
        right = [(3.6, y) for y in (0.6, 1.8, 3.0)]
        edges = [(0, 0), (0, 1), (1, 0), (1, 2), (2, 1), (3, 2), (2, 2)]
        lines(s, [((*left[a], 0), (*right[b], 0)) for a, b in edges], P["slate"].hi, 0.055, depth=80)
        for pt in left:
            st.disc(s, p, pt[0], pt[1], 0, 0.36)
        for pt in right:
            st.disc(s, q, pt[0], pt[1], 0, 0.36)
    elif kind == "hyper":
        pts = [(0.4, 0.5), (1.6, 0.2), (1.2, 1.5), (2.8, 1.2), (3.4, 2.4), (2.2, 2.6), (4.2, 0.6), (0.6, 2.6)]
        groups = [([0, 1, 2], p), ([2, 3, 5], q), ([3, 4, 6], P["teal"])]
        for members, k in groups:
            cx = sum(pts[i][0] for i in members) / len(members)
            cy = sum(pts[i][1] for i in members) / len(members)
            rad = max(math.hypot(pts[i][0] - cx, pts[i][1] - cy) for i in members) + 0.45
            ring = [ground((cx + rad * math.cos(t) * 1.05, cy + rad * math.sin(t) * 0.8)) for t in [i * math.pi / 24 for i in range(48)]]
            face = [st.proj(v) for v in ring]
            s.add(90, st.poly(face, k.cell, f' fill-opacity="0.55" stroke="{k.base}" stroke-width="0.04"'), face)
        for i, pt in enumerate(pts):
            st.disc(s, P["slate"], *ground(pt), 0.2)
    else:   # node features: each node carries a small feature vector
        nodes = [(0, 0), (2.4, 0.4), (1.0, 2.0), (3.6, 2.2), (4.6, 0.0)]
        edges = [(0, 1), (0, 2), (1, 2), (1, 3), (3, 4), (1, 4)]
        lines(s, [((*nodes[a], 0), (*nodes[b], 0)) for a, b in edges], P["slate"].hi, 0.06, depth=80)
        for i, (x, y) in enumerate(nodes):
            st.disc(s, p if i != 1 else q, x, y, 0, 0.34)
            vec = {(r, 0): (p if i != 1 else q).ramp(0.2 + 0.18 * ((i * 3 + r * 2) % 5)) for r in range(3)}
            st.slab(s, p if i != 1 else q, 1, 3, x=x + 0.45, y=y - 0.2, z=0.0, cell=0.36, thick=0.25, margin=0.06, gap=0.04,
                    colours=vec, depth_bias=-1)
    return s.to_svg(title)


def b_mesh_graph(title, pal, n=7):
    """A triangulated grid mesh (mesh graph used by learned simulators)."""
    p = P[pal]
    s = st.Scene()
    pts = {}
    for i in range(n):
        for j in range(n):
            pts[(i, j)] = ground((j * 0.75 + (i % 2) * 0.375, i * 0.65))
    segs = []
    for (i, j), a in pts.items():
        for di, dj in ((0, 1), (1, 0), (1, -1 + (i % 2) * 1)):
            b = pts.get((i + di, j + dj))
            if b:
                segs.append((a, b))
    lines(s, segs, p.hi, 0.04, depth=80)
    for (i, j), a in pts.items():
        dot3(s, a, 0.1, p.base if (i + j) % 3 else P["orange"].base, stroke="#ffffff", depth=st.dot(a, st.D) - 5)
    return s.to_svg(title)


# ------------------------------------------------------------------ operators, activation curves and charts
def b_badge(title, pal, glyph, font=0.0):
    s = st.Scene()
    st.disc(s, P[pal], 0, 0, 0, 1.0, thick=0.35, glyph=glyph, font=font)
    return s.to_svg(title)


class Plot:
    """Maps data coordinates onto the inner area of a w x h panel lying in the front plane."""

    def __init__(self, w, h, xr, yr, m=0.5):
        self.w, self.h, self.xr, self.yr, self.m = w, h, xr, yr, m

    def pt(self, u, v):
        x = self.m + (u - self.xr[0]) / (self.xr[1] - self.xr[0]) * (self.w - 2 * self.m)
        y = self.m + (v - self.yr[0]) / (self.yr[1] - self.yr[0]) * (self.h - 2 * self.m)
        return st.proj((x, y, 0))

    def line(self, data, colour, width=0.09, dash=None, opacity=1.0):
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        extra += f' stroke-opacity="{opacity}"' if opacity < 1 else ""
        pts = st.pts_attr([self.pt(u, v) for u, v in data])
        return (f'<polyline points="{pts}" fill="none" stroke="{colour}" stroke-width="{width}" stroke-linecap="round" '
                f'stroke-linejoin="round"{extra}/>')

    def area(self, data, colour, opacity=0.4, base=0.0):
        pts = [self.pt(data[0][0], base)] + [self.pt(u, v) for u, v in data] + [self.pt(data[-1][0], base)]
        return st.poly(pts, colour, f' fill-opacity="{opacity}"')

    def axes(self, x0=None, y0=None, colour="#b4bfcd"):
        x0 = self.xr[0] if x0 is None else x0
        y0 = self.yr[0] if y0 is None else y0
        return (self.line([(self.xr[0], y0), (self.xr[1], y0)], colour, 0.04) +
                self.line([(x0, self.yr[0]), (x0, self.yr[1])], colour, 0.04))

    def dot(self, u, v, r, fill, stroke="#ffffff"):
        x, y = self.pt(u, v)
        return f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{r * 0.3:.3f}"/>'


ACTS = {
    "relu": ("ReLU", lambda x: max(0.0, x)),
    "leaky": ("Leaky ReLU", lambda x: x if x > 0 else 0.15 * x),
    "sigmoid": ("Sigmoid", lambda x: 1 / (1 + math.exp(-x))),
    "tanh": ("Tanh", math.tanh),
    "gelu": ("GELU", lambda x: 0.5 * x * (1 + math.erf(x / math.sqrt(2)))),
    "silu": ("SiLU / Swish", lambda x: x / (1 + math.exp(-x))),
    "softplus": ("Softplus", lambda x: math.log1p(math.exp(x))),
    "elu": ("ELU", lambda x: x if x > 0 else math.exp(x) - 1),
    "hardswish": ("Hard Swish", lambda x: x * min(max(x + 3, 0), 6) / 6),
    "step": ("阶跃函数", lambda x: 1.0 if x >= 0 else 0.0),
}


def b_activation(title, key, pal="blue", frame="slate"):
    f = ACTS[key][1]
    xs = [-3 + 6 * i / 120 for i in range(121)]
    ys = [f(x) for x in xs]
    lo, hi = min(min(ys), 0.0), max(ys)
    pad = (hi - lo) * 0.12
    plot = Plot(4.4, 3.4, (-3, 3), (lo - pad, hi + pad))
    if key == "step":
        curve = plot.line([(-3, 0), (0, 0)], P[pal].base, 0.11) + plot.line([(0, 1), (3, 1)], P[pal].base, 0.11)
        curve += plot.line([(0, 0), (0, 1)], P[pal].base, 0.05, dash="0.08 0.08")
    else:
        curve = plot.line(list(zip(xs, ys)), P[pal].base, 0.11)
    s = st.Scene()
    panel(s, P[frame], 4.4, 3.4, [plot.axes(0, 0), curve])
    return s.to_svg(title)


def softmax(logits):
    e = [math.exp(v) for v in logits]
    return [v / sum(e) for v in e]


def b_bars(title, pal, horizontal=False, n=7, seed=2):
    """Class probabilities as bars; the predicted class is in full colour."""
    p = P[pal]
    g = st.rng(seed)
    logits = [g.gauss(0, 0.8) for _ in range(n)]
    logits[2] += 2.4
    probs = softmax(logits)
    top = max(probs)
    s = st.Scene()
    for i, v in enumerate(probs):
        length = (0.25 if not horizontal else 0.55) + 3.2 * v / top
        front = p.base if v == top else st.mix(p.cell, p.hi, 0.35 + 0.65 * v / top)
        side = None if v == top else st.mix(p.cell, p.hi, 0.8)
        if horizontal:
            box(s, p, 0, -i * 0.78, 0, length, 0.5, 0.5, front=front, top=side, left=side)
        else:
            box(s, p, i * 0.72, 0, 0, 0.5, length, 0.5, front=front, top=side, left=side)
    return s.to_svg(title)


def b_hist(title, pal, bins=13, skew=0.0):
    p = P[pal]
    s = st.Scene()
    w = 0.42
    heights = []
    for i in range(bins):
        x = -3 + 6 * (i + 0.5) / bins
        v = math.exp(-x * x / 2) * (1 + skew * math.tanh(x))
        heights.append(v)
    top = max(heights)
    for i, v in enumerate(heights):
        h = 0.15 + 3.0 * v / top
        box(s, p, i * (w + 0.06), 0, 0, w, h, 0.42, front=st.mix(p.cell, p.hi, 0.3 + 0.7 * v / top), top=p.cell, left=p.hi)
    return s.to_svg(title)


def gauss(x, mu, sd):
    return math.exp(-((x - mu) / sd) ** 2 / 2) / sd


def b_dist(title, kind="gauss", pal="blue", alt="orange"):
    a, b = P[pal], P[alt]
    xs = [-4 + 8 * i / 160 for i in range(161)]
    frags = []
    if kind == "gauss":
        data = [(x, gauss(x, 0, 1)) for x in xs]
        plot = Plot(4.6, 3.2, (-4, 4), (0, 1.15))
        frags += [plot.area(data, a.cell, 0.75), plot.line(data, a.base, 0.1)]
    elif kind == "gmm":
        comps = [(-1.4, 0.7, 0.45), (1.3, 0.9, 0.55)]
        total = [(x, sum(wt * gauss(x, mu, sd) for mu, sd, wt in comps)) for x in xs]
        plot = Plot(4.6, 3.2, (-4, 4), (0, 0.75))
        frags.append(plot.area(total, a.cell, 0.6))
        for (mu, sd, wt), col in zip(comps, (b.base, P["teal"].base)):
            frags.append(plot.line([(x, wt * gauss(x, mu, sd)) for x in xs], col, 0.07, dash="0.14 0.1"))
        frags.append(plot.line(total, a.base, 0.1))
    else:   # two shifted distributions: source and target domains
        plot = Plot(4.6, 3.2, (-4, 4), (0, 1.15))
        for mu, sd, col in ((-1.0, 0.8, a), (1.2, 1.0, b)):
            data = [(x, gauss(x, mu, sd) * 0.8) for x in xs]
            frags += [plot.area(data, col.hi, 0.35), plot.line(data, col.base, 0.1)]
    s = st.Scene()
    panel(s, P["slate"], 4.6, 3.2, [plot.axes()] + frags)
    return s.to_svg(title)


def b_contour(title, kind="single"):
    plot = Plot(4.6, 4.0, (-3, 3), (-2.6, 2.6), m=0.3)
    comps = ([(0.0, 0.0, 2.5, 1.5, 28, "blue")] if kind == "single" else
             [(-1.45, 1.0, 1.3, 0.85, 20, "blue"), (1.45, 0.75, 1.1, 0.95, -35, "orange"), (0.05, -1.35, 1.6, 0.8, 5, "teal")])
    frags = []
    g = st.rng(4)
    for cx, cy, rx, ry, ang, k in comps:
        p = P[k]
        for level in (1.0, 0.72, 0.46, 0.22):
            pts = []
            for i in range(48):
                t = 2 * math.pi * i / 48
                u, v = rx * level * math.cos(t), ry * level * math.sin(t)
                c, sn = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                pts.append(plot.pt(cx + u * c - v * sn, cy + u * sn + v * c))
            frags.append(st.poly(pts, p.ramp(0.1 + 0.75 * (1 - level)), f' fill-opacity="0.85" stroke="{p.base}" stroke-width="0.03"'))
        for _ in range(6):
            frags.append(plot.dot(cx + g.gauss(0, rx * 0.45), cy + g.gauss(0, ry * 0.45), 0.07, p.ink, "none"))
    s = st.Scene()
    panel(s, P["slate"], 4.6, 4.0, frags)
    return s.to_svg(title)


SURFACES = {
    "bowl": lambda x, z: 0.55 * (x * x + 1.3 * z * z) + 0.06 * math.sin(4 * x) * math.cos(3 * z),
    "rugged": lambda x, z: (0.45 * (x * x + z * z) - 0.55 * math.exp(-((x - 0.45) ** 2 + (z + 0.3) ** 2) / 0.08)
                            - 0.35 * math.exp(-((x + 0.5) ** 2 + (z - 0.4) ** 2) / 0.06) + 0.08 * math.sin(6 * x + 2 * z)),
    "saddle": lambda x, z: 0.55 * (x * x - z * z),
}


def b_surface(title, kind="bowl", name="viridis", n=22):
    """A loss landscape: a height field drawn as shaded quads, coloured by height."""
    f = SURFACES[kind]
    size, scale = 4.4, 2.0
    grid = {}
    for i in range(n + 1):
        for j in range(n + 1):
            x, z = -1 + 2 * i / n, -1 + 2 * j / n
            grid[(i, j)] = f(x, z)
    lo, hi = min(grid.values()), max(grid.values())
    quads = []
    for i in range(n):
        for j in range(n):
            corners = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            pts3 = [((a / n - 0.5) * size, (grid[(a, b)] - lo) / (hi - lo) * scale, (b / n - 0.5) * size) for a, b in corners]
            v = sum((grid[c] - lo) / (hi - lo) for c in corners) / 4
            quads.append((st.depth_of(pts3), st.poly([st.proj(q) for q in pts3], cmap(name, v),
                                                      ' stroke="#ffffff" stroke-width="0.012" stroke-opacity="0.55"'), pts3))
    s = st.Scene()
    body = "".join(svg for _, svg, _ in sorted(quads, key=lambda q: -q[0]))
    s.add(0, f"<g>{body}</g>", [st.proj(q) for _, _, pts in quads for q in pts])
    return s.to_svg(title)


def b_curves(title, kind="loss", pal="blue", alt="orange", seed=3):
    a, b = P[pal], P[alt]
    g = st.rng(seed)
    xs = [i / 80 for i in range(81)]
    frags = []
    if kind == "loss":
        plot = Plot(4.6, 3.2, (0, 1), (0, 1.05))
        train = [(x, 0.08 + 0.85 * math.exp(-x * 5) + 0.012 * g.gauss(0, 1)) for x in xs]
        val = [(x, 0.2 + 0.75 * math.exp(-x * 4.2) + 0.1 * x * x + 0.012 * g.gauss(0, 1)) for x in xs]
        frags += [plot.line(val, b.base, 0.08), plot.line(train, a.base, 0.08)]
    elif kind == "acc":
        plot = Plot(4.6, 3.2, (0, 1), (0, 1.05))
        ours = [(x, 0.92 * (1 - math.exp(-x * 5.5)) + 0.01 * g.gauss(0, 1)) for x in xs]
        base = [(x, 0.76 * (1 - math.exp(-x * 4.0)) + 0.01 * g.gauss(0, 1)) for x in xs]
        frags += [plot.line(base, P["slate"].hi, 0.08, dash="0.14 0.1"), plot.line(ours, a.base, 0.09)]
    else:   # learning-rate schedule: linear warm-up then cosine decay
        plot = Plot(4.6, 3.2, (0, 1), (0, 1.08))
        lr = [(x, x / 0.1 if x < 0.1 else 0.5 * (1 + math.cos(math.pi * (x - 0.1) / 0.9))) for x in xs]
        frags += [plot.area(lr, a.cell, 0.6), plot.line(lr, a.base, 0.09)]
    s = st.Scene()
    panel(s, P["slate"], 4.6, 3.2, [plot.axes()] + frags)
    return s.to_svg(title)


def b_boundary(title, kind="curve", pal="blue", alt="orange", seed=6):
    a, b = P[pal], P[alt]
    g = st.rng(seed)
    plot = Plot(4.6, 3.8, (0, 1), (0, 1), m=0.3)
    edge = (lambda x: 0.5 + 0.22 * math.sin(x * 5.5 - 0.6)) if kind == "curve" else (lambda x: 0.12 + 0.8 * x)
    xs = [i / 60 for i in range(61)]
    frags = [st.poly([plot.pt(0, 1)] + [plot.pt(x, edge(x)) for x in xs] + [plot.pt(1, 1)], a.cell, ' fill-opacity="0.55"'),
             st.poly([plot.pt(0, 0)] + [plot.pt(x, edge(x)) for x in xs] + [plot.pt(1, 0)], b.cell, ' fill-opacity="0.55"')]
    if kind == "linear":
        for off in (-0.12, 0.12):
            frags.append(plot.line([(x, edge(x) + off) for x in (0, 1)], GREY, 0.045, dash="0.12 0.09"))
    frags.append(plot.line([(x, edge(x)) for x in xs], INK, 0.07))
    margin = 0.06 if kind == "curve" else 0.15
    placed = 0
    while placed < 34:
        x, y = g.uniform(0.04, 0.96), g.uniform(0.04, 0.96)
        if abs(y - edge(x)) < margin:
            continue
        frags.append(plot.dot(x, y, 0.1, a.base if y > edge(x) else b.base))
        placed += 1
    s = st.Scene()
    panel(s, P["slate"], 4.6, 3.8, frags)
    return s.to_svg(title)


def b_hypersphere(title, pals, seed=2):
    """Unit-sphere embeddings: points of each class gather around their own direction."""
    s = st.Scene()
    r = 2.0
    g = st.rng(seed)
    defs = ('<defs><radialGradient id="sphere" cx="0.36" cy="0.3" r="0.8"><stop offset="0" stop-color="#ffffff"/>'
            '<stop offset="0.6" stop-color="#e6ebf2"/><stop offset="1" stop-color="#b9c3d1"/></radialGradient></defs>')
    parts = [f'<circle cx="0" cy="0" r="{r}" fill="url(#sphere)"/>']
    for lat in (-50, -20, 10, 40):
        pts = []
        for t in range(0, 361, 8):
            q = (r * math.cos(math.radians(lat)) * math.cos(math.radians(t)), r * math.sin(math.radians(lat)),
                 r * math.cos(math.radians(lat)) * math.sin(math.radians(t)))
            if st.dot(q, st.D) < 0:
                pts.append(st.proj(q))
        if len(pts) > 1:
            parts.append(f'<polyline points="{st.pts_attr(pts)}" fill="none" stroke="#ffffff" stroke-width="0.04"/>')
    front = tuple(-c for c in st.D)
    offsets = [(-0.62, 0.48), (0.6, 0.5), (-0.5, -0.58), (0.62, -0.45)]   # along screen right / up
    dirs = [tuple(front[i] + a * st.R[i] + b * st.U[i] for i in range(3)) for a, b in offsets]
    for (dx, dy, dz), k in zip(dirs, pals):
        for _ in range(16):
            v = (dx + g.gauss(0, 0.17), dy + g.gauss(0, 0.17), dz + g.gauss(0, 0.17))
            n = math.sqrt(sum(c * c for c in v))
            q = tuple(r * c / n for c in v)
            if st.dot(q, st.D) < -0.2:
                sx, sy = st.proj(q)
                parts.append(f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="0.1" fill="{P[k].base}" stroke="#ffffff" stroke-width="0.03"/>')
    s.add(0, "<g>" + "".join(parts) + "</g>", [(-r, -r), (r, r)])
    return s.to_svg(title, defs=defs)


# ------------------------------------------------------------------ catalogue
def register(add):
    PZ = {k: P[k].zh for k in ORDER}
    cnn = [("blue", ["blue"] * 4, "蓝"), ("teal", ["teal"] * 4, "青"), ("purple", ["purple"] * 4, "紫"),
           ("grad", ["blue", "teal", "green", "amber"], "渐变")]
    for key, pals, zh in cnn:
        add(f"cnn-enc-{key}", NET, f"卷积编码器层块（{zh}）", f"convolutional encoder blocks ({key})",
            ["编码器", "卷积网络", "CNN", "下采样", "PlotNeuralNet", "backbone"], b_cnn, pals=pals, sizes=[3.4, 2.6, 1.9, 1.3],
            depths=[0.6, 1.0, 1.45, 1.9], pool="coral" if key != "grad" else None)
    for key, pals, zh in cnn[:3]:
        add(f"cnn-dec-{key}", NET, f"卷积解码器层块（{zh}）", f"convolutional decoder blocks ({key})",
            ["解码器", "上采样", "CNN", "PlotNeuralNet"], b_cnn, pals=pals, sizes=[1.3, 1.9, 2.6, 3.4], depths=[1.9, 1.45, 1.0, 0.6])
    for key, pals in (("blue", ["blue", "blue", "blue"]), ("purple", ["purple", "purple", "purple"])):
        add(f"cnn-cls-{key}", NET, f"卷积分类网络（{PZ[key]}，含全连接层）", f"CNN classifier with FC layers ({key})",
            ["分类网络", "CNN", "全连接", "AlexNet", "VGG"], b_cnn, pals=pals, sizes=[3.2, 2.3, 1.6], depths=[0.6, 1.1, 1.6],
            pool="coral", fc=3)
    for a, b, m, zh in (("blue", "teal", "purple", "蓝青"), ("purple", "orange", "amber", "紫橙"), ("green", "blue", "coral", "绿蓝")):
        add(f"unet-{a}-{b}", NET, f"U-Net 编码器—解码器（{zh}）", f"U-Net encoder-decoder ({a}/{b})",
            ["U-Net", "编码器-解码器", "跳跃连接", "分割", "skip connection"], b_unet, enc=a, dec=b, mid=m)
    for a, b, zh in (("blue", "teal", "蓝青"), ("purple", "coral", "紫红")):
        add(f"hourglass-{a}-{b}", NET, f"沙漏型编码—解码结构（{zh}）", f"hourglass encoder-decoder ({a}/{b})",
            ["自编码器", "沙漏", "瓶颈", "latent", "编码器-解码器"], b_hourglass, pal_a=a, pal_b=b)
    for k in ("blue", "teal", "purple", "orange", "green", "coral"):
        add(f"wedge-enc-{k}", NET, f"{PZ[k]}编码器（梯形）", f"{k} encoder wedge", ["编码器", "encoder", "梯形", "压缩"],
            b_wedge, pal=k, kind="enc")
        add(f"wedge-dec-{k}", NET, f"{PZ[k]}解码器（梯形）", f"{k} decoder wedge", ["解码器", "decoder", "梯形", "生成器"],
            b_wedge, pal=k, kind="dec")
    add("wedge-ae-blue", NET, "自编码器（编码器 + 隐向量 + 解码器）", "autoencoder: encoder, latent, decoder",
        ["自编码器", "VAE", "隐空间", "latent", "编码器-解码器"], b_wedge_pair, pal_a="blue", pal_b="teal")
    add("wedge-ae-purple", NET, "自编码器（紫橙）", "autoencoder (purple/orange)", ["自编码器", "VAE", "VQ-VAE", "隐空间"],
        b_wedge_pair, pal_a="purple", pal_b="orange", latent="green")
    add("wedge-siamese", NET, "孪生编码器（双分支）", "siamese encoders", ["孪生网络", "双分支", "对比学习", "权重共享"],
        b_wedge_pair, pal_a="blue", pal_b="orange", kind="siamese")
    add("wedge-teacher-student", NET, "教师—学生网络（大小编码器）", "teacher and student encoders",
        ["知识蒸馏", "教师网络", "学生网络", "distillation"], b_wedge_pair, pal_a="purple", pal_b="teal", kind="ts")
    for key, pals, zh in (("purple", ["amber", "purple", "orange"], "紫橙"), ("blue", ["slate", "blue", "teal"], "蓝青"),
                          ("coral", ["amber", "coral", "blue"], "红蓝")):
        add(f"transformer-{key}", NET, f"Transformer 层（{zh}）", f"Transformer layer ({key})",
            ["Transformer", "自注意力", "MLP", "LayerNorm", "编码器层"], b_transformer, pals=pals)
    add("transformer-x2-purple", NET, "两层 Transformer 堆叠", "two stacked Transformer layers", ["Transformer", "堆叠", "N×"],
        b_transformer, pals=["amber", "purple", "orange"], layers=2)
    for k in ("blue", "teal"):
        add(f"bottleneck-{k}", NET, f"瓶颈块（宽—窄—宽，{PZ[k]}）", f"bottleneck block ({k})", ["瓶颈", "bottleneck", "ResNet", "1×1 卷积"],
            b_bottleneck, pal=k)
        add(f"inverted-{k}", NET, f"倒残差块（窄—宽—窄，{PZ[k]}）", f"inverted residual block ({k})",
            ["倒残差", "inverted residual", "MobileNetV2", "扩张"], b_bottleneck, pal=k, inverted=True)
    add("inception-1", NET, "Inception 多分支模块", "Inception module", ["Inception", "多分支", "GoogLeNet", "多尺度"], b_inception,
        pals=["blue", "teal", "purple", "orange"])
    add("inception-2", NET, "多分支并行模块（暖色）", "multi-branch module, warm", ["多分支", "并行", "多尺度"], b_inception,
        pals=["coral", "amber", "orange", "purple"])
    add("moe-blue", NET, "混合专家（MoE）路由", "mixture of experts routing", ["MoE", "混合专家", "路由", "稀疏激活"], b_moe, pal="blue")
    add("moe-purple", NET, "混合专家（MoE，紫）", "mixture of experts (purple)", ["MoE", "专家", "门控"], b_moe, pal="purple",
        active=(0, 2))
    for k in ("blue", "purple"):
        add(f"dense-{k}", NET, f"密集连接块（{PZ[k]}）", f"dense block ({k})", ["DenseNet", "密集连接", "特征复用"], b_dense, pal=k)
    for a, b in (("blue", "orange"), ("purple", "teal")):
        add(f"fpn-{a}-{b}", NET, f"特征金字塔（FPN，{PZ[a]}{PZ[b]}）", f"feature pyramid network ({a}/{b})",
            ["FPN", "特征金字塔", "多尺度", "目标检测"], b_fpn, pal_a=a, pal_b=b)
    for k in ("blue", "purple", "teal"):
        add(f"codebook-{k}", TOKEN, f"码本（选中一条，{PZ[k]}）", f"codebook with a selected entry ({k})",
            ["码本", "codebook", "VQ-VAE", "量化", "离散表示"], b_codebook, pal=k, pick=ORDER.index(k) % 8)
    for k in ("blue", "orange"):
        add(f"queue-{k}", TOKEN, f"特征队列 / 记忆库（{PZ[k]}）", f"feature queue / memory bank ({k})",
            ["记忆库", "队列", "MoCo", "memory bank", "负样本"], b_queue, pal=k)
    for k in ("blue", "purple"):
        add(f"gap-{k}", TENSOR, f"全局平均池化（张量→向量，{PZ[k]}）", f"global average pooling ({k})", ["全局平均池化", "GAP", "池化", "向量"],
            b_pool_vector, pal=k)
        add(f"flatten-{k}", TENSOR, f"展平（张量→行向量，{PZ[k]}）", f"flatten ({k})", ["展平", "flatten", "向量", "reshape"],
            b_pool_vector, pal=k, kind="flatten")
    for k in ("blue", "teal"):
        add(f"chan-attn-{k}", ATTN, f"通道注意力（SE，{PZ[k]}）", f"channel attention ({k})", ["通道注意力", "SE", "SENet", "CBAM"],
            b_channel_attention, pal=k)
        add(f"spatial-attn-{k}", ATTN, f"空间注意力（{PZ[k]}）", f"spatial attention ({k})", ["空间注意力", "CBAM", "注意力图"],
            b_channel_attention, pal=k, kind="spatial")
    for k in ORDER:
        add(f"block-{k}", TENSOR, f"{PZ[k]}纯色张量块", f"{k} plain tensor block", ["张量", "模块", "立方体", "层"], b_plain,
            pal=k, w=2.4, h=2.4, d=1.6)
        add(f"layer-{k}", TENSOR, f"{PZ[k]}薄层块", f"{k} thin layer block", ["层", "卷积层", "特征图", "PlotNeuralNet"], b_plain,
            pal=k, w=3.0, h=3.0, d=0.45)
    for k in ("blue", "purple", "teal", "orange"):
        add(f"glass-{k}", TENSOR, f"{PZ[k]}半透明张量", f"{k} translucent tensor", ["张量", "半透明", "线框", "tensor"], b_glass, pal=k)

    for name in CMAPS:
        add(f"cmap-{name}", FMAP, f"{CMAP_ZH[name]} 配色特征图", f"feature map, {name} colour map", ["特征图", "热力图", name, "可视化"],
            b_cmap_map, name=name, seed=len(name))
        add(f"cmap-stack-{name}", FMAP, f"{CMAP_ZH[name]} 配色多通道特征图", f"stacked feature maps, {name}",
            ["多通道", "特征图", name, "通道"], b_cmap_map, name=name, n=6, channels=4, seed=3)
    for k in ("blue", "purple"):
        add(f"masked-map-{k}", FMAP, f"掩码特征图（{PZ[k]}）", f"masked feature map ({k})", ["掩码", "MAE", "masked", "自监督"],
            b_masked_map, pal=k)
        add(f"sparse-map-{k}", FMAP, f"稀疏特征图（{PZ[k]}）", f"sparse feature map ({k})", ["稀疏", "sparse", "稀疏卷积", "激活"],
            b_masked_map, pal=k, kind="sparse", seed=8)
    add("groups-1", TENSOR, "通道分组（三组）", "channel groups", ["分组卷积", "通道分组", "split", "grouped convolution"], b_groups,
        pals=["blue", "teal", "orange"])
    add("groups-2", TENSOR, "通道分组（紫红黄）", "channel groups, warm", ["分组卷积", "通道拆分", "split"], b_groups,
        pals=["purple", "coral", "amber"])
    add("shuffle", TENSOR, "通道重排（Channel Shuffle）", "channel shuffle", ["通道重排", "ShuffleNet", "channel shuffle"], b_groups,
        pals=["blue", "teal", "orange"], kind="shuffle")

    for k in ("blue", "purple"):
        add(f"deform-conv-{k}", CONV, f"可变形卷积采样点（{PZ[k]}）", f"deformable convolution sampling ({k})",
            ["可变形卷积", "deformable", "DCN", "偏移量", "采样点"], b_deform_conv, pal=k)
    add("transposed-conv", CONV, "转置卷积 2×2→5×5", "transposed convolution", ["转置卷积", "反卷积", "上采样", "deconvolution"],
        b_transposed, pal_in="purple", pal_out="teal")
    add("pixel-shuffle", CONV, "像素重排（Pixel Shuffle）", "pixel shuffle", ["像素重排", "PixelShuffle", "亚像素卷积", "超分辨率"],
        b_pixel_shuffle)
    for k in ("blue", "teal"):
        add(f"stride-{k}", CONV, f"步长为 2 的卷积窗口（{PZ[k]}）", f"stride-2 convolution windows ({k})", ["步长", "stride", "下采样", "卷积"],
            b_stride, pal=k)
        add(f"padding-{k}", CONV, f"零填充（{PZ[k]}）", f"zero padding ({k})", ["填充", "padding", "零填充", "卷积"], b_padding, pal=k)
    for kind, zh in (("sobel", "Sobel 算子"), ("laplacian", "拉普拉斯算子"), ("gaussian", "高斯核 5×5")):
        add(f"kernel-{kind}", CONV, f"{zh}", f"{kind} kernel", ["卷积核", "滤波器", kind, "边缘检测" if kind != "gaussian" else "平滑"],
            b_classic_kernel, kind=kind)
    for k in ("blue", "orange"):
        add(f"separable-{k}", CONV, f"可分离卷积核 1×5 + 5×1（{PZ[k]}）", f"separable 1x5 and 5x1 kernels ({k})",
            ["可分离卷积", "条形卷积", "大卷积核", "strip"], b_separable, pal=k)
    add("patch-merge", CONV, "Patch Merging（4×4→4 个 2×2）", "patch merging", ["Patch Merging", "Swin", "下采样", "空间到通道"],
        b_patch_merge)
    add("bilinear", CONV, "双线性插值采样", "bilinear interpolation", ["双线性插值", "采样", "grid sample", "插值"], b_bilinear, pal="coral")

    add("windows", ATTN, "窗口划分（Swin，彩色）", "window partition", ["Swin", "窗口注意力", "window attention", "划分"], b_windows)
    add("windows-shifted", ATTN, "移位窗口（Swin，彩色）", "shifted window partition", ["Swin", "移位窗口", "shifted window"], b_windows,
        shifted=True)
    for k in ("blue", "purple"):
        add(f"windows-{k}", ATTN, f"窗口划分（{PZ[k]}）", f"window partition ({k})", ["Swin", "窗口注意力", "局部注意力"], b_windows, pal=k)
        add(f"windows-shifted-{k}", ATTN, f"移位窗口（{PZ[k]}）", f"shifted windows ({k})", ["Swin", "移位窗口"], b_windows, pal=k,
            shifted=True)
    for k in ("blue", "purple"):
        add(f"deform-attn-{k}", ATTN, f"可变形注意力采样点（{PZ[k]}）", f"deformable attention sampling ({k})",
            ["可变形注意力", "Deformable DETR", "参考点", "采样点"], b_deform_attn, pal=k)
    add("deform-attn-ms", ATTN, "多尺度可变形注意力", "multi-scale deformable attention", ["可变形注意力", "多尺度", "Deformable DETR"],
        b_deform_attn, pal="blue", levels=3)
    for k in ("blue", "purple"):
        add(f"axial-{k}", ATTN, f"轴向注意力（行 + 列，{PZ[k]}）", f"axial attention ({k})", ["轴向注意力", "criss-cross", "行列注意力"],
            b_query_pattern, pal=k)
    add("local-attn", ATTN, "局部窗口注意力（邻域）", "local neighbourhood attention", ["邻域注意力", "局部注意力", "NAT"],
        b_query_pattern, pal="teal", kind="local")
    add("global-attn", ATTN, "全局注意力（单个查询）", "global attention for one query", ["全局注意力", "Non-local", "自注意力"],
        b_query_pattern, pal="orange", kind="global")
    add("heads-1", ATTN, "多头注意力图堆叠", "multi-head attention maps", ["多头注意力", "multi-head", "注意力图"], b_heads,
        pals=["blue", "teal", "purple", "orange"])
    add("heads-2", ATTN, "多头注意力图堆叠（蓝紫）", "multi-head attention maps, cool", ["多头注意力", "注意力头"], b_heads,
        pals=["blue", "purple", "blue", "purple"], seed=4)
    add("cross-attn-1", ATTN, "交叉注意力矩阵（查询 × 键）", "cross-attention matrix", ["交叉注意力", "cross attention", "查询", "键"],
        b_cross, pal_q="blue", pal_k="orange")
    add("cross-attn-2", ATTN, "交叉注意力矩阵（紫青）", "cross-attention matrix, purple/teal", ["交叉注意力", "图文", "多模态"],
        b_cross, pal_q="purple", pal_k="teal", seed=7, mat="blue")
    add("clip-matrix-1", ATTN, "图文对比相似度矩阵（CLIP）", "image-text contrastive matrix", ["CLIP", "对比学习", "图文匹配", "InfoNCE"],
        b_cross, pal_q="blue", pal_k="orange", rows=5, kind="clip")
    add("clip-matrix-2", ATTN, "对比相似度矩阵（青紫）", "contrastive similarity matrix, teal/purple", ["对比学习", "正样本对", "相似度"],
        b_cross, pal_q="teal", pal_k="purple", rows=5, kind="clip", mat="slate")
    add("token-prune", TOKEN, "Token 剪枝（灰色为丢弃）", "token pruning", ["Token 剪枝", "稀疏", "加速", "DynamicViT"], b_token_row,
        pals=["blue"])
    add("token-merge", TOKEN, "Token 合并（宽块为合并后）", "token merging", ["Token 合并", "ToMe", "加速"], b_token_row,
        pals=["blue", "teal", "purple"], kind="merge")
    for k in ("blue", "orange"):
        add(f"tokens-ellipsis-{k}", TOKEN, f"带省略号的长 Token 序列（{PZ[k]}）", f"long token sequence with ellipsis ({k})",
            ["Token", "长序列", "省略号", "sequence"], b_token_row, pals=[k], kind="ellipsis")
    add("registers", TOKEN, "分类 Token + 图像 Token + 寄存器 Token", "class, patch and register tokens", ["寄存器", "registers", "CLS", "ViT"],
        b_registers)
    add("posenc-sin", TOKEN, "正弦位置编码矩阵", "sinusoidal position encoding", ["位置编码", "positional encoding", "正弦", "Transformer"],
        b_posenc)
    add("posenc-rel", TOKEN, "相对位置偏置表", "relative position bias", ["相对位置", "位置偏置", "Swin", "RoPE"], b_posenc, kind="rel",
        rows=12, cols=12)
    for k in ("blue", "purple"):
        add(f"onehot-{k}", TOKEN, f"独热向量（{PZ[k]}）", f"one-hot vector ({k})", ["独热", "one-hot", "标签", "类别"], b_onehot, pal=k)
    add("latent-z", TOKEN, "隐向量 z（高斯采样）", "latent vector z", ["隐向量", "latent", "VAE", "高斯采样"], b_onehot, pal="purple",
        latent=True)

    add("iou", TASK, "交并比（IoU）", "intersection over union", ["IoU", "交并比", "目标检测", "重叠"], b_iou)
    add("iou-2", TASK, "交并比（青紫）", "intersection over union, teal/purple", ["IoU", "交并比"], b_iou, pal_a="teal", pal_b="purple",
        over="coral")
    add("nms", TASK, "非极大值抑制（NMS）", "non-maximum suppression", ["NMS", "非极大值抑制", "候选框", "目标检测"], b_nms)
    add("box-regression", TASK, "边框回归（锚框→真值框）", "bounding-box regression", ["边框回归", "锚框", "anchor", "偏移量"],
        b_box_regression)
    add("roi-align", TASK, "RoI Align 双线性采样", "RoI Align sampling", ["RoI Align", "Mask R-CNN", "区域特征", "双线性"], b_roi_align)
    for k in ("orange", "blue"):
        add(f"centre-heat-{k}", TASK, f"中心点热力图（{PZ[k]}）", f"object centre heat map ({k})", ["CenterNet", "中心点", "热力图", "关键点"],
            b_centre_heat, pal=k)
    add("mask-stack-1", TASK, "实例掩码堆叠", "stacked instance masks", ["实例分割", "掩码", "mask", "Mask2Former"], b_mask_stack,
        pals=["coral", "blue", "green", "amber"])
    add("mask-stack-2", TASK, "实例掩码堆叠（蓝）", "stacked instance masks, blue", ["实例分割", "掩码查询"], b_mask_stack,
        pals=["blue", "blue", "blue", "blue"])
    add("label-semantic", TASK, "语义分割标签图（街景）", "semantic label map", ["语义分割", "标签图", "像素分类", "Cityscapes"], b_label_grid)
    add("label-instance", TASK, "实例分割标签图（街景）", "instance label map", ["实例分割", "实例", "标签图"], b_label_grid, kind="instance")

    for kind, zh, en in (("knn", "K 近邻图", "k-nearest-neighbour graph"), ("bipartite", "二部图", "bipartite graph"),
                         ("hyper", "超图", "hypergraph"), ("features", "带节点特征的图", "graph with node features")):
        add(f"graph-{kind}", GRAPH, zh, en, ["图", "graph", "GNN", zh], b_graph_kind, pal="blue", alt="orange", kind=kind)
    add("mesh-graph", GRAPH, "三角网格图", "triangular mesh graph", ["网格", "mesh", "图神经网络", "GraphCast"], b_mesh_graph, pal="teal")

    glyphs = [("sub", "-", "减法", "subtract", 0.0), ("div", "div", "除法", "divide", 0.0), ("tanh", "tanh", "Tanh", "tanh", 0.0),
              ("gelu", "gelu", "GELU", "GELU", 0.0), ("sin", "sin", "正弦 / 周期", "sine", 0.0), ("max", "max", "最大值", "max", 0.62),
              ("transpose", "T", "转置", "transpose", 0.0)]
    for key, glyph, zh, en, font in glyphs:
        for k in ("slate", "blue"):
            add(f"op-{key}-{k}", OPS, f"{zh}运算符（{PZ[k]}）", f"{en} operator ({k})", ["运算符", "operator", zh, en], b_badge,
                pal=k, glyph=glyph, font=font)
    for key, glyph, zh in (("add", "+", "加法"), ("mul", "x", "乘法"), ("hadamard", "dot", "逐元素乘"), ("concat", "C", "拼接")):
        for k in ("teal", "orange", "purple", "coral"):
            add(f"op-{key}-{k}", OPS, f"{zh}运算符（{PZ[k]}）", f"{key} operator ({k})", ["运算符", "operator", zh, key], b_badge,
                pal=k, glyph=glyph)
    for key, (zh, _) in ACTS.items():
        add(f"act-{key}", OPS, f"{zh} 激活函数曲线", f"{zh} activation curve", ["激活函数", "activation", zh, "非线性"], b_activation,
            key=key)

    for k in ("blue", "purple"):
        add(f"probs-{k}", CHART, f"类别概率柱状图（{PZ[k]}）", f"class probability bars ({k})", ["概率", "Softmax", "分类输出", "柱状图"],
            b_bars, pal=k)
        add(f"probs-h-{k}", CHART, f"类别概率横向柱状图（{PZ[k]}）", f"horizontal class probability bars ({k})",
            ["概率", "Softmax", "置信度", "柱状图"], b_bars, pal=k, horizontal=True, seed=5)
    add("hist-blue", CHART, "直方图（正态分布）", "histogram, normal", ["直方图", "分布", "histogram", "统计"], b_hist, pal="blue")
    add("hist-orange", CHART, "直方图（偏态分布）", "histogram, skewed", ["直方图", "分布", "偏态"], b_hist, pal="orange", skew=0.6)
    add("dist-gauss", CHART, "高斯分布曲线", "Gaussian distribution", ["高斯分布", "正态分布", "概率密度", "Gaussian"], b_dist)
    add("dist-gmm", CHART, "高斯混合分布", "Gaussian mixture", ["高斯混合", "GMM", "多峰分布", "混合模型"], b_dist, kind="gmm")
    add("dist-shift", CHART, "源域与目标域分布偏移", "source and target domain shift", ["域偏移", "域适应", "分布差异", "domain shift"],
        b_dist, kind="shift")
    add("contour-single", CHART, "二维高斯等高线", "2D Gaussian contours", ["等高线", "二维高斯", "协方差", "概率密度"], b_contour)
    add("contour-mixture", CHART, "二维高斯混合等高线", "2D Gaussian mixture contours", ["高斯混合", "聚类", "等高线", "多峰"], b_contour,
        kind="mixture")
    add("surface-bowl", CHART, "损失曲面（凸）", "convex loss surface", ["损失曲面", "loss landscape", "优化", "凸"], b_surface)
    add("surface-rugged", CHART, "损失曲面（非凸多极小值）", "non-convex loss landscape", ["损失曲面", "局部极小值", "优化", "非凸"],
        b_surface, kind="rugged", name="plasma")
    add("surface-saddle", CHART, "鞍点曲面", "saddle surface", ["鞍点", "saddle", "优化", "曲面"], b_surface, kind="saddle", name="coolwarm")
    add("curve-loss", CHART, "训练与验证损失曲线", "training and validation loss", ["损失曲线", "训练", "验证", "过拟合"], b_curves)
    add("curve-acc", CHART, "精度提升曲线（对比基线）", "accuracy curve vs baseline", ["精度曲线", "收敛", "对比"], b_curves, kind="acc")
    add("curve-lr", CHART, "学习率调度（预热 + 余弦）", "learning-rate schedule, warm-up and cosine", ["学习率", "余弦退火", "warmup", "调度"],
        b_curves, kind="lr", pal="purple")
    add("boundary-curve", CHART, "非线性决策边界", "non-linear decision boundary", ["决策边界", "分类", "二分类", "decision boundary"],
        b_boundary)
    add("boundary-linear", CHART, "线性分类与间隔（SVM）", "linear classifier with margin", ["SVM", "间隔", "线性分类", "支持向量"],
        b_boundary, kind="linear", pal="teal", alt="coral", seed=9)
    add("hypersphere-1", CHART, "超球面上的嵌入聚类", "embeddings on a hypersphere", ["超球面", "对比学习", "归一化嵌入", "聚类"],
        b_hypersphere, pals=["blue", "orange", "teal", "purple"])
    add("hypersphere-2", CHART, "超球面嵌入（两类）", "embeddings on a hypersphere, two classes", ["超球面", "度量学习", "余弦相似度"],
        b_hypersphere, pals=["coral", "blue", "coral", "blue"], seed=5)
