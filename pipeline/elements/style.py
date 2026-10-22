"""Drawing kit for the 研图 element style: flat-shaded isometric solids.

Every element is built from extruded polygons seen by one fixed orthographic
camera from the upper left, so the left and top faces of each solid show its
thickness.  Faces are filled with flat colours from a palette; the front face of
a slab carries a grid of inset cells.  The output is plain, editable SVG.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

# --------------------------------------------------------------------- camera
_A, _B = 0.74, 0.47            # camera sits up-left: x and y components of the view direction
_D = (_A, -_B, 1.0)
_n = math.sqrt(sum(c * c for c in _D))
D = tuple(c / _n for c in _D)  # view direction, from the camera into the scene
_R = (D[2], 0.0, -D[0])        # screen right = up x D
_rn = math.hypot(_R[0], _R[2])
R = (_R[0] / _rn, 0.0, _R[2] / _rn)
U = (D[1] * R[2] - D[2] * R[1], D[2] * R[0] - D[0] * R[2], D[0] * R[1] - D[1] * R[0])  # screen up = D x R


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def proj(p):
    """3-D point (x right, y up, z into the screen) -> SVG coordinates (y down)."""
    return dot(p, R), -dot(p, U)


def facing(normal):
    """True when a face with this outward normal is turned towards the camera."""
    return dot(normal, D) < -1e-9


# --------------------------------------------------------------------- colour
def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _css(rgb):
    return "#" + "".join(f"{max(0, min(255, round(v * 255))):02x}" for v in rgb)


def mix(a, b, t):
    a, b = _hex(a), _hex(b)
    return _css(tuple(x + (y - x) * t for x, y in zip(a, b)))


@dataclass(frozen=True)
class Palette:
    key: str
    zh: str
    en: str
    base: str      # frame of slabs, grid lines
    left: str      # left side faces
    top: str       # top faces
    cell: str      # light cells
    hi: str        # highlighted cells
    ink: str       # strong accent

    def ramp(self, t):
        """Sequential colour: 0 -> light cell tint, 1 -> deep base."""
        t = max(0.0, min(1.0, t))
        if t < 0.5:
            return mix(self.cell, self.hi, t / 0.5)
        return mix(self.hi, self.left, (t - 0.5) / 0.5)


PALETTES = {
    "blue":   Palette("blue", "蓝色", "blue", "#1e6fe0", "#0f4fb3", "#1860cf", "#8ec2ff", "#3d8bef", "#0b3f94"),
    "teal":   Palette("teal", "青色", "teal", "#17a398", "#0d7a71", "#128d84", "#a6ede3", "#3fc2b3", "#0a5f58"),
    "orange": Palette("orange", "橙色", "orange", "#f28a1c", "#cf6a08", "#e27a12", "#ffd7a8", "#ff9a30", "#a85203"),
    "purple": Palette("purple", "紫色", "purple", "#7a5ce3", "#583dc2", "#6a4dd4", "#d0c3ff", "#9b82f6", "#43299c"),
    "green":  Palette("green", "绿色", "green", "#2ea84f", "#1d8039", "#279645", "#b5ebc1", "#58c674", "#146630"),
    "coral":  Palette("coral", "珊瑚红", "coral", "#e6485c", "#bd2d42", "#d23b50", "#ffc4cb", "#f2717f", "#97192d"),
    "slate":  Palette("slate", "石墨灰", "slate", "#5d6d84", "#435064", "#506075", "#d7dfea", "#8e9db2", "#323c4c"),
    "amber":  Palette("amber", "琥珀黄", "amber", "#eab10f", "#c08e04", "#d6a10a", "#ffe9a8", "#f5c93e", "#8f6a00"),
}
ORDER = ["blue", "teal", "orange", "purple", "green", "coral", "slate", "amber"]


def side_colour(pal: Palette, normal):
    """Flat shading by face orientation: top faces mid, left faces dark, front base."""
    nx, ny, nz = normal
    if ny > 0.6:
        return pal.top
    if nx < -0.6:
        return pal.left
    if ny > 0.2 or nx < -0.2:
        return mix(pal.top, pal.left, 0.5)
    return pal.left


# --------------------------------------------------------------------- scene
@dataclass
class Item:
    depth: float
    svg: str
    order: int = 0


@dataclass
class Scene:
    """Collects SVG fragments with a depth key; farther items are written first."""
    items: list = field(default_factory=list)
    points: list = field(default_factory=list)
    counter: int = 0

    def add(self, depth, svg, pts):
        self.counter += 1
        self.items.append(Item(depth, svg, self.counter))
        self.points.extend(pts)

    def to_svg(self, title, scale=40.0, pad=0.35, defs=""):
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        x0, x1, y0, y1 = min(xs) - pad, max(xs) + pad, min(ys) - pad, max(ys) + pad
        w, h = (x1 - x0) * scale, (y1 - y0) * scale
        body = "".join(i.svg for i in sorted(self.items, key=lambda i: (-i.depth, i.order)))
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.1f} {h:.1f}" width="{w:.0f}" height="{h:.0f}">'
                f"<title>{title}</title>{defs}"
                f'<g transform="matrix({scale} 0 0 {scale} {-x0 * scale:.2f} {-y0 * scale:.2f})" '
                f'stroke-linejoin="round">{body}</g></svg>\n')


def pts_attr(points):
    return " ".join(f"{x:.3f},{y:.3f}" for x, y in points)


def poly(points, fill, extra=""):
    return f'<polygon points="{pts_attr(points)}" fill="{fill}"{extra}/>'


def depth_of(points3):
    cx = sum(p[0] for p in points3) / len(points3)
    cy = sum(p[1] for p in points3) / len(points3)
    cz = sum(p[2] for p in points3) / len(points3)
    return dot((cx, cy, cz), D)


# --------------------------------------------------------------------- solids
def extrude(scene, outline, z0, thick, pal: Palette, front=None, origin=(0.0, 0.0), front_svg="", depth_bias=0.0,
            sides=None):
    """Extrude a 2-D polygon (x, y; counter-clockwise) from z0 to z0 + thick.

    The front face (at z0) is drawn in ``front`` (default: palette base) followed by
    ``front_svg`` — extra fragments already in screen space.  Visible side faces use
    flat shading from the palette.
    """
    ox, oy = origin
    pts = [(x + ox, y + oy) for x, y in outline]
    n = len(pts)
    svg = []
    shown = []
    for i in range(n):
        (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        length = math.hypot(ex, ey) or 1
        normal = (ey / length, -ex / length, 0.0)          # outward for counter-clockwise outlines
        if not facing(normal):
            continue
        quad = [(ax, ay, z0), (bx, by, z0), (bx, by, z0 + thick), (ax, ay, z0 + thick)]
        colour = (sides or side_colour)(pal, normal) if callable(sides or side_colour) else sides
        shown.append((dot(((ax + bx) / 2, (ay + by) / 2, z0 + thick / 2), D), poly([proj(p) for p in quad], colour)))
    for _, s in sorted(shown, key=lambda t: -t[0]):
        svg.append(s)
    face = [proj((x, y, z0)) for x, y in pts]
    svg.append(poly(face, front or pal.base))
    svg.append(front_svg)
    all3 = [(x, y, z) for x, y in pts for z in (z0, z0 + thick)]
    scene.add(depth_of(all3) + depth_bias, "<g>" + "".join(svg) + "</g>", [proj(p) for p in all3])


def rect(w, h):
    return [(0, 0), (w, 0), (w, h), (0, h)]


def cell_quads(x0, y0, w, h, cols, rows, z, margin=0.13, gap=0.09):
    """Screen quads for a grid of cells on the front plane z; row 0 is the top row."""
    cw = (w - 2 * margin - (cols - 1) * gap) / cols
    ch = (h - 2 * margin - (rows - 1) * gap) / rows
    out = {}
    for r in range(rows):
        for c in range(cols):
            cx = x0 + margin + c * (cw + gap)
            cy = y0 + h - margin - (r + 1) * ch - r * gap
            out[(r, c)] = [proj((cx, cy, z)), proj((cx + cw, cy, z)), proj((cx + cw, cy + ch, z)), proj((cx, cy + ch, z))]
    return out


def face_grid_top(x0, w, y, z0, d, cols, layers, margin=0.13, gap=0.09):
    """Cells on a top face (plane y) spanning x0..x0+w and z0..z0+d."""
    cw = (w - 2 * margin - (cols - 1) * gap) / cols
    cd = (d - 2 * margin - (layers - 1) * gap) / layers
    out = {}
    for k in range(layers):
        for c in range(cols):
            ax = x0 + margin + c * (cw + gap)
            az = z0 + margin + k * (cd + gap)
            out[(k, c)] = [proj((ax, y, az)), proj((ax + cw, y, az)), proj((ax + cw, y, az + cd)), proj((ax, y, az + cd))]
    return out


def face_grid_left(x, y0, h, z0, d, rows, layers, margin=0.13, gap=0.09):
    """Cells on a left face (plane x) spanning y0..y0+h and z0..z0+d; row 0 at the top."""
    ch = (h - 2 * margin - (rows - 1) * gap) / rows
    cd = (d - 2 * margin - (layers - 1) * gap) / layers
    out = {}
    for r in range(rows):
        for k in range(layers):
            ay = y0 + h - margin - (r + 1) * ch - r * gap
            az = z0 + margin + k * (cd + gap)
            out[(r, k)] = [proj((x, ay, az)), proj((x, ay + ch, az)), proj((x, ay + ch, az + cd)), proj((x, ay, az + cd))]
    return out


def slab(scene, pal: Palette, cols, rows, x=0.0, y=0.0, z=0.0, cell=1.0, thick=0.42, colours=None, margin=0.13,
         gap=0.09, depth_bias=0.0, plain=False):
    """A feature map: a thin box whose front face carries a cols x rows grid.

    ``colours`` maps (row, col) -> fill; missing cells use the light tint.  ``thick``, ``margin`` and
    ``gap`` are absolute lengths (one unit = one default cell).
    """
    w, h = cols * cell, rows * cell
    frags = []
    if not plain:
        for key, quad in cell_quads(x, y, w, h, cols, rows, z, margin, gap).items():
            frags.append(poly(quad, (colours or {}).get(key, pal.cell)))
    extrude(scene, rect(w, h), z, thick, pal, origin=(x, y), front_svg="".join(frags), depth_bias=depth_bias)


def cube(scene, pal: Palette, cols, rows, layers, x=0.0, y=0.0, z=0.0, cell=1.0, colours=None, top_colours=None,
         left_colours=None, margin=0.11, gap=0.08):
    """A tensor C x H x W drawn as a box with grids on its three visible faces."""
    w, h, d = cols * cell, rows * cell, layers * cell
    m, g = margin * cell, gap * cell
    front = "".join(poly(q, (colours or {}).get(k, pal.cell)) for k, q in cell_quads(x, y, w, h, cols, rows, z, m, g).items())
    top = "".join(poly(q, (top_colours or {}).get(k, mix(pal.cell, pal.hi, 0.35)))
                  for k, q in face_grid_top(x, w, y + h, z, d, cols, layers, m, g).items())
    left = "".join(poly(q, (left_colours or {}).get(k, mix(pal.cell, pal.hi, 0.6)))
                   for k, q in face_grid_left(x, y, h, z, d, rows, layers, m, g).items())
    svg = [
        poly([proj(p) for p in [(x, y + h, z), (x + w, y + h, z), (x + w, y + h, z + d), (x, y + h, z + d)]], pal.top), top,
        poly([proj(p) for p in [(x, y, z), (x, y + h, z), (x, y + h, z + d), (x, y, z + d)]], pal.left), left,
        poly([proj(p) for p in [(x, y, z), (x + w, y, z), (x + w, y + h, z), (x, y + h, z)]], pal.base), front,
    ]
    corners = [(x + a, y + b, z + c) for a in (0, w) for b in (0, h) for c in (0, d)]
    scene.add(depth_of(corners), "<g>" + "".join(svg) + "</g>", [proj(p) for p in corners])


def disc(scene, pal: Palette, cx, cy, z, r, thick=0.22, glyph="", glyph_colour="#ffffff", face=None, rim=None,
         font=0.0, depth_bias=0.0):
    """A coin facing the camera: node, operator badge."""
    off = proj((0, 0, thick))
    o0 = proj((0, 0, 0))
    dx, dy = off[0] - o0[0], off[1] - o0[1]
    sx, sy = proj((cx, cy, z))
    parts = [f'<circle cx="{sx + dx:.3f}" cy="{sy + dy:.3f}" r="{r:.3f}" fill="{rim or pal.left}"/>',
             f'<polygon points="{pts_attr(_tangent_band(sx, sy, dx, dy, r))}" fill="{rim or pal.left}"/>',
             f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="{r:.3f}" fill="{face or pal.base}"/>']
    if glyph:
        parts.append(glyph_svg(glyph, sx, sy, r, glyph_colour, font))
    pts = [(sx - r, sy - r), (sx + r + abs(dx), sy + r + abs(dy)), (sx + dx - r, sy + dy - r)]
    scene.add(dot((cx, cy, z + thick / 2), D) + depth_bias, "<g>" + "".join(parts) + "</g>", pts)


def _tangent_band(sx, sy, dx, dy, r):
    length = math.hypot(dx, dy) or 1
    nx, ny = -dy / length * r, dx / length * r
    return [(sx + nx, sy + ny), (sx + dx + nx, sy + dy + ny), (sx + dx - nx, sy + dy - ny), (sx - nx, sy - ny)]


CURVES = {   # glyph -> (f on [-3, 3], low, high) drawn as a small plot inside a badge
    "tanh": (math.tanh, -1.0, 1.0),
    "gelu": (lambda x: 0.5 * x * (1 + math.erf(x / math.sqrt(2))), -0.5, 3.0),
    "sin": (lambda x: math.sin(x * 1.05), -1.0, 1.0),
}


def glyph_svg(glyph, sx, sy, r, colour, font=0.0):
    s = r * 0.5
    w = r * 0.16
    line = f'stroke="{colour}" stroke-width="{w:.3f}" stroke-linecap="round" fill="none"'
    if glyph == "+":
        return f'<path d="M{sx - s:.3f} {sy:.3f}H{sx + s:.3f}M{sx:.3f} {sy - s:.3f}V{sy + s:.3f}" {line}/>'
    if glyph == "x":
        k = s * 0.75
        return f'<path d="M{sx - k:.3f} {sy - k:.3f}L{sx + k:.3f} {sy + k:.3f}M{sx + k:.3f} {sy - k:.3f}L{sx - k:.3f} {sy + k:.3f}" {line}/>'
    if glyph == "dot":
        return f'<circle cx="{sx:.3f}" cy="{sy:.3f}" r="{r * 0.17:.3f}" fill="{colour}"/>'
    if glyph == "sigmoid":
        return (f'<path d="M{sx - s:.3f} {sy + s * .55:.3f}C{sx - s * .1:.3f} {sy + s * .6:.3f} {sx - s * .2:.3f} {sy - s * .6:.3f} '
                f'{sx + s * .1:.3f} {sy - s * .55:.3f}S{sx + s * .6:.3f} {sy - s * .55:.3f} {sx + s:.3f} {sy - s * .55:.3f}" {line}/>')
    if glyph == "relu":
        return f'<path d="M{sx - s:.3f} {sy + s * .45:.3f}H{sx:.3f}L{sx + s:.3f} {sy - s * .6:.3f}" {line}/>'
    if glyph == "-":
        return f'<path d="M{sx - s:.3f} {sy:.3f}H{sx + s:.3f}" {line}/>'
    if glyph == "div":
        dots = "".join(f'<circle cx="{sx:.3f}" cy="{sy + k * s * 0.55:.3f}" r="{w * 0.75:.3f}" fill="{colour}"/>' for k in (-1, 1))
        return f'<path d="M{sx - s:.3f} {sy:.3f}H{sx + s:.3f}" {line}/>{dots}'
    if glyph in CURVES:
        f, lo, hi = CURVES[glyph]
        xs = [-1 + 2 * i / 24 for i in range(25)]
        ys = [f(x * 3) for x in xs]
        pts = " ".join(f"{sx + x * s:.3f},{sy - s * (2 * (y - lo) / (hi - lo) - 1) * 0.6:.3f}" for x, y in zip(xs, ys))
        return f'<polyline points="{pts}" {line} stroke-linejoin="round"/>'
    size = font or r * 1.05
    return (f'<text x="{sx:.3f}" y="{sy + size * 0.36:.3f}" font-size="{size:.3f}" text-anchor="middle" '
            f'font-family="Inter, Segoe UI, Arial, sans-serif" font-weight="700" fill="{colour}">{glyph}</text>')


def face_text(text, x, y, z, size, colour, weight=700, anchor="middle"):
    """Text lying in a front plane (z), centred at (x, y)."""
    ox, oy = proj((x, y, z))
    ux = proj((x + 1, y, z))
    vx = proj((x, y - 1, z))
    a, b = ux[0] - ox, ux[1] - oy
    c, d = vx[0] - ox, vx[1] - oy
    return (f'<text transform="matrix({a:.4f} {b:.4f} {c:.4f} {d:.4f} {ox:.3f} {oy:.3f})" x="0" y="{size * 0.36:.3f}" '
            f'font-size="{size:.3f}" text-anchor="{anchor}" font-family="Inter, Segoe UI, Arial, sans-serif" '
            f'font-weight="{weight}" fill="{colour}">{text}</text>')


def line3(p, q, colour, width=0.05, dash=None, cap="round", opacity=1.0):
    a, b = proj(p), proj(q)
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    op = f' stroke-opacity="{opacity}"' if opacity < 1 else ""
    return (f'<line x1="{a[0]:.3f}" y1="{a[1]:.3f}" x2="{b[0]:.3f}" y2="{b[1]:.3f}" stroke="{colour}" '
            f'stroke-width="{width}" stroke-linecap="{cap}"{extra}{op}/>')


def rng(seed):
    return random.Random(seed)
