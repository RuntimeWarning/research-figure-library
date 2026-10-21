#!/usr/bin/env python3
"""Collect stand-alone figure elements from openly licensed libraries (see ``picks.py``).

Sources are downloaded at pinned commits into ``.cache/web/`` and processed into
``dist/assets/collected/<source>/``: an SVG where the source is vector, a PNG and a
WebP thumbnail.  Metadata goes to ``pipeline/manifests/collected.json``.

* Isoflow isopacks (MIT): isometric SVG objects, unchanged.
* Fluent Emoji 3D (MIT): 256 px renders; Chinese names come from the Fluent Emoji
  icon manifest, so run ``pipeline/icons/build.py`` first.
* 3dicons (CC0): 400 px renders in the colour and clay styles.
* NN-SVG (MIT): schematics rendered by ``nnsvg.mjs`` (run it first; needs
  puppeteer-core and Chrome) into ``.cache/web/nn-svg-out``.
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import resvg_py
from PIL import Image

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from common import ASSETS, CACHE, DIST, MANIFESTS, fetch, read_json, sha256, slug, write_json  # noqa: E402
from picks import FLUENT, FLUENT_TAGS, FLUENT_ZH, PICKS, PREFIX, SOURCES, THREEDICON_STYLES, THREEDICONS  # noqa: E402

WEB = CACHE / "web"
OUT = ASSETS / "collected"
PNG_SIDE = 1600
THUMB_SIDE = 560
ORDER = ["isoflow", "fluent-3d", "3dicons", "nn-svg"]


def categories():
    text = (Path(__file__).resolve().parents[1] / "elements" / "generate.py").read_text(encoding="utf-8")
    block = re.search(r"^CATEGORIES = \[(.*?)\]", text, re.S | re.M).group(1)
    return re.findall(r'"([^"]+)"', block)


# ------------------------------------------------------------------ sources
def raw(repo, commit, path):
    return f"https://raw.githubusercontent.com/{repo}/{commit}/{quote(path)}"


def unpack(repo, commit):
    root = WEB / f"{repo.split('/')[1]}-{commit}"
    if not root.is_dir():
        data = fetch(f"https://codeload.github.com/{repo}/zip/{commit}", WEB / f"{repo.split('/')[1]}-{commit}.zip")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            archive.extractall(WEB)
    return root


def fluent_jobs():
    """Fluent Emoji 3D picks: (path in repo, id, zh, en, category, tags)."""
    commit = SOURCES["fluent-3d"]["commit"]
    tree = json.loads(fetch(f"https://api.github.com/repos/microsoft/fluentui-emoji/git/trees/{commit}?recursive=1",
                            WEB / "fluent" / f"tree-{commit[:8]}.json"))
    renders = {}
    for entry in tree["tree"]:
        path = entry["path"]
        if path.endswith(".png") and "/3D/" in path and ("/Default/3D/" in path or path.count("/") == 3):
            renders.setdefault(path.split("/")[1].lower(), path)
    manifest = read_json(MANIFESTS / "icons-fluent-emoji.json")
    if not manifest:
        raise SystemExit("Run pipeline/icons/build.py first: Fluent Emoji names come from its manifest")
    names = {a["en"].lower(): a for a in manifest["assets"]}
    jobs = []
    for category, entries in FLUENT.items():
        for name in entries:
            icon = names.get(name, {})
            zh = FLUENT_ZH.get(name) or icon.get("zh")
            if name not in renders or not zh:
                raise ValueError(f"Fluent Emoji pick without a 3D render or Chinese name: {name}")
            tags = FLUENT_TAGS.get(name, []) + [t for t in icon.get("tags", []) if t != zh][:6]
            jobs.append((renders[name], slug(name), zh, name, category, tags))
    return jobs


def threedicon_jobs():
    commit = SOURCES["3dicons"]["commit"]
    jobs = []
    for name, zh, en, category, tags in THREEDICONS:
        meta = fetch(raw("realvjy/3dicons", commit, f"content/3dicons-meta/{name}.md"),
                     WEB / "3dicons" / "meta" / f"{name}.md").decode("utf-8")
        urls = dict(re.findall(r"^(\w+):\s*(https://\S+)", meta, re.M))
        for style, style_zh in THREEDICON_STYLES.items():
            jobs.append(((urls[style], style), f"{name}-{style}", f"{zh}（{style_zh}）", f"{en} ({style})", category,
                         tags + ["三维", "3D", style_zh]))
    return jobs


def prepare():
    licences = DIST / "licenses"
    roots = {"isoflow": unpack("markmanx/isopacks", SOURCES["isoflow"]["commit"])}
    (licences / "isoflow-LICENSE.txt").write_bytes((roots["isoflow"] / "collections/isoflow/LICENSE").read_bytes())
    (licences / "3dicons-LICENSE.txt").write_bytes(
        fetch(raw("realvjy/3dicons", SOURCES["3dicons"]["commit"], "LICENSE"), WEB / "3dicons" / "LICENSE"))
    roots["nn-svg"] = unpack("alexlenail/NN-SVG", SOURCES["nn-svg"]["commit"])
    (licences / "nn-svg-LICENSE.txt").write_bytes((roots["nn-svg"] / "LICENSE").read_bytes())
    if not (WEB / "nn-svg-out").is_dir():
        raise SystemExit(f"Run first: node pipeline/collected/nnsvg.mjs {roots['nn-svg']} {WEB / 'nn-svg-out'}")
    jobs = {key: rows for key, rows in PICKS.items()}
    jobs["fluent-3d"] = fluent_jobs()
    jobs["3dicons"] = threedicon_jobs()
    return roots, jobs


# ------------------------------------------------------------------ processing
def px_size(svg: str) -> str:
    """Use unitless (px) width/height on the root element; resvg rejects some units."""
    match = re.search(r"<svg\b[^>]*>", svg)
    fixed = re.sub(r'\b(width|height)="([\d.]+)(?:pt|px|mm)?"', r'\1="\2"', match.group(0))
    return svg[:match.start()] + fixed + svg[match.end():]


def render_svg(svg: str) -> Image.Image:
    vb = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', svg)
    w, h = float(vb.group(1)), float(vb.group(2))
    scale = PNG_SIDE / max(w, h)
    png = resvg_py.svg_to_bytes(svg_string=svg, width=round(w * scale), height=round(h * scale))
    return Image.open(io.BytesIO(bytes(png))).convert("RGBA")


def trim_alpha(image: Image.Image, margin: int = 6) -> Image.Image:
    box = image.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if not box:
        return image
    x0, y0, x1, y1 = box
    return image.crop((max(0, x0 - margin), max(0, y0 - margin), min(image.width, x1 + margin),
                       min(image.height, y1 + margin)))


def upstream(key, ref):
    s = SOURCES[key]
    if key == "isoflow":
        return f"{s['repo']}/blob/{s['commit']}/collections/isoflow/icons/{ref}"
    if key == "fluent-3d":
        return f"{s['repo']}/blob/{s['commit']}/{quote(ref)}"
    if key == "3dicons":
        return ref[0]
    return s["url"]


def process(key, ref, roots):
    if key == "isoflow":
        svg = px_size((roots["isoflow"] / "collections/isoflow/icons" / ref).read_text(encoding="utf-8"))
        return svg, render_svg(svg)
    if key == "nn-svg":
        svg = px_size((WEB / "nn-svg-out" / ref).read_text(encoding="utf-8"))
        return svg, render_svg(svg)
    if key == "fluent-3d":
        data = fetch(raw("microsoft/fluentui-emoji", SOURCES[key]["commit"], ref), WEB / "fluent" / Path(ref).name)
    else:
        url, style = ref
        data = fetch(url, WEB / "3dicons" / "png" / style / Path(url).name)
    return None, trim_alpha(Image.open(io.BytesIO(data)).convert("RGBA"))


def main():
    allowed = set(categories())
    roots, jobs = prepare()
    OUT.mkdir(parents=True, exist_ok=True)
    records, keep = [], set()
    for key in ORDER:
        source = SOURCES[key]
        folder = OUT / key
        (folder / "thumbs").mkdir(parents=True, exist_ok=True)
        for ref, pid, zh, en, category, tags in jobs[key]:
            if category not in allowed:
                raise ValueError(f"{pid}: unknown category {category}")
            svg, image = process(key, ref, roots)
            files = {"png": folder / f"{pid}.png", "thumb": folder / "thumbs" / f"{pid}.webp"}
            if svg is not None:
                files["svg"] = folder / f"{pid}.svg"
                files["svg"].write_text(svg, encoding="utf-8", newline="\n")
            image.save(files["png"], optimize=True)
            thumb = image.copy()
            thumb.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.Resampling.LANCZOS)
            thumb.save(files["thumb"], quality=90, method=6)
            keep.update(p.resolve() for p in files.values())
            records.append({
                "id": f"{PREFIX[key]}-{pid}", "kind": "atomic", "collection": key, "source": key, "category": category,
                "name": zh, "english": en, "tags": list(dict.fromkeys(tags + [source["short"]])),
                "description": f"收集自 {source['title']}，{source['license_name']} 许可。{source['processing']}。",
                "upstream": upstream(key, ref), "page": "",
                "svg_kind": "" if svg is None else ("mixed" if "<image" in svg else "vector"),
                "has_alpha": True, "width": image.width, "height": image.height,
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
