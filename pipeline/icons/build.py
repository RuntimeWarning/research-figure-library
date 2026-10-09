#!/usr/bin/env python3
"""Build every icon pack into ``dist/assets/icons/<pack>/`` and its manifest.

Run ``pipeline/icons/fetch.py`` first.  Sources are read from ``.cache/icons``;
the original IconPark, Tabler and Fluent Emoji selections are kept file-for-file
(their curated Chinese metadata lives in ``legacy_icons.json``).  Every new SVG is
sanitised: comments, metadata, editor attributes, scripts, event handlers and
external references are removed.  Single-colour packs are normalised to
``currentColor`` so that the web page can recolour them.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import sys
import tarfile
import urllib.parse
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from common import ASSETS, CACHE, DIST, MANIFESTS, read_json, sha256, slug, write_json  # noqa: E402
from names import Translator, english_title, tokens  # noqa: E402
import taxonomy as tx  # noqa: E402

HERE = Path(__file__).resolve().parent
SRC = CACHE / "icons"
OUT = ASSETS / "icons"
LICENSES = DIST / "licenses"
SVG_NS = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
EDITOR_NS = ("inkscape", "sodipodi", "adobe", "illustrator", "sketch", "figma", "serif", "bx", "krita",
             "purl.org/dc", "creativecommons", "rdf-syntax")
MAX_BIOICON_BYTES = 300_000
BLACK = {"#000", "#000000", "black", "#231f20", "#161616"}

PACKS = {
    "iconpark": {"name": "IconPark", "style": "多色", "version": "@icon-park/svg 1.4.2", "license": "Apache-2.0",
                 "license_file": "licenses/iconpark-LICENSE.txt", "homepage": "https://github.com/bytedance/IconPark",
                 "recolor": False},
    "tabler": {"name": "Tabler Icons", "style": "线性", "version": "@tabler/icons 3.49.0", "license": "MIT",
               "license_file": "licenses/tabler-LICENSE.txt", "homepage": "https://tabler.io/icons", "recolor": True},
    "phosphor": {"name": "Phosphor Icons", "style": "双色", "version": "@phosphor-icons/core 2.1.1", "license": "MIT",
                 "license_file": "licenses/phosphor-LICENSE.txt", "homepage": "https://phosphoricons.com",
                 "recolor": True},
    "fluent-emoji": {"name": "Fluent Emoji", "style": "彩色拟物", "version": "fluentui-emoji @1ffb34c",
                     "license": "MIT", "license_file": "licenses/fluent-emoji-LICENSE.txt",
                     "homepage": "https://github.com/microsoft/fluentui-emoji", "recolor": False},
    "fluent-system": {"name": "Fluent System Icons", "style": "线性 · 彩色", "version": "@fluentui/svg-icons 1.1.343",
                      "license": "MIT", "license_file": "licenses/fluent-system-LICENSE.txt",
                      "homepage": "https://github.com/microsoft/fluentui-system-icons", "recolor": True},
    "mdi": {"name": "Material Design Icons", "style": "实心", "version": "@mdi/svg 7.4.47", "license": "Apache-2.0",
            "license_file": "licenses/mdi-LICENSE.txt", "homepage": "https://pictogrammers.com/library/mdi/",
            "recolor": True},
    "carbon": {"name": "Carbon Icons", "style": "实心", "version": "@carbon/icons 11.90.0", "license": "Apache-2.0",
               "license_file": "licenses/carbon-LICENSE.txt", "homepage": "https://carbondesignsystem.com/elements/icons/library/",
               "recolor": True},
    "carbon-pictograms": {"name": "Carbon Pictograms", "style": "线描插画", "version": "@carbon/pictograms 12.86.0",
                          "license": "Apache-2.0", "license_file": "licenses/carbon-pictograms-LICENSE.txt",
                          "homepage": "https://carbondesignsystem.com/elements/pictograms/library/", "recolor": True},
    "healthicons": {"name": "Health Icons", "style": "医疗实心", "version": "healthicons 2.0.0", "license": "MIT",
                    "license_file": "licenses/healthicons-LICENSE.txt", "homepage": "https://healthicons.org",
                    "recolor": True},
    "bioicons": {"name": "Bioicons", "style": "生物科研插图", "version": "bioicons @d29e766",
                 "license": "CC0 / CC BY / MIT（逐项）", "license_file": "licenses/bioicons-LICENSES.txt",
                 "homepage": "https://bioicons.com", "recolor": False},
}
LEGACY_PACK = {"iconpark": "iconpark", "tabler": "tabler", "fluent": "fluent-emoji", "phosphor": "phosphor"}
translator = Translator()


# --------------------------------------------------------------------------- SVG
def _is_editor(name: str) -> bool:
    # Illustrator writes namespaces as entity references ("&ns_ai;") defined in a DOCTYPE.
    return name.startswith("&") or any(token in name for token in EDITOR_NS)


def clean_svg(data: bytes, mono: bool = False) -> str:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_comments=True, remove_pis=True,
                             huge_tree=True, recover=False)
    root = etree.fromstring(data, parser)
    if etree.QName(root).localname != "svg":
        raise ValueError("not an SVG document")
    for element in list(root.iter()):
        if not isinstance(element.tag, str):
            continue
        qname = etree.QName(element)
        if (qname.localname in ("script", "metadata", "foreignObject", "namedview")
                or (qname.namespace and qname.namespace not in (SVG_NS, XLINK) and _is_editor(qname.namespace))):
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)
            continue
        for key in list(element.attrib):
            attr = etree.QName(key)
            value = element.attrib[key]
            if (attr.localname.lower().startswith("on") or (attr.namespace and _is_editor(attr.namespace))
                    or attr.localname in ("data-name",)):
                del element.attrib[key]
            elif attr.localname == "href" and re.match(r"^\s*(https?:|file:|//|javascript:)", value, re.I):
                del element.attrib[key]
            elif mono and attr.localname in ("fill", "stroke") and value.strip().lower() in BLACK:
                element.set(key, "currentColor")
    if "viewBox" not in root.attrib:
        w = re.match(r"^\s*([\d.]+)", root.get("width", ""))
        h = re.match(r"^\s*([\d.]+)", root.get("height", ""))
        if w and h:
            root.set("viewBox", f"0 0 {w.group(1)} {h.group(1)}")
    # Physical or relative sizes ("43mm", "100%") make some renderers fail; the viewBox
    # keeps the aspect ratio and the page sets the display size.
    if "viewBox" in root.attrib:
        for key in ("width", "height"):
            if not re.fullmatch(r"\s*[\d.]+(px)?\s*", root.get(key, "0")):
                root.attrib.pop(key, None)
    for key in ("x", "y", "version", "enable-background"):
        root.attrib.pop(key, None)
    root.attrib.pop("{http://www.w3.org/XML/1998/namespace}space", None)
    for key in ("id", "style") if mono else ("id",):
        if key == "style" and "enable-background" not in root.get("style", ""):
            continue
        root.attrib.pop(key, None)
    if mono and root.get("fill") in (None, "black", "#000", "#000000"):
        root.set("fill", "currentColor")
    etree.cleanup_namespaces(root)
    text = etree.tostring(root, encoding="unicode")
    return re.sub(r">\s+<", "><", text).strip() + "\n"


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    if not path.is_file() or path.read_bytes() != data:
        path.write_bytes(data)


# ----------------------------------------------------------------------- helpers
def tar(name):
    return tarfile.open(SRC / name / "package.tgz")


def read_member(archive, member):
    return archive.extractfile(member).read()


def display_name(english: str, pack: str, zh: str = "") -> str:
    return zh or translator.translate(english, pack) or english_title(english)


def item(pack, ident, file, english, zh="", tags=(), category="界面与操作", **extra):
    tags = [t for t in dict.fromkeys(str(t).strip() for t in tags) if t and t.lower() != english.lower()]
    return {"id": ident, "pack": pack, "file": file, "en": english_title(english) if pack != "fluent-emoji" else english,
            "zh": display_name(english, pack, zh), "tags": tags[:10], "cat": category, **extra}


class Files:
    """Assign unique file names within a pack directory."""

    def __init__(self, pack):
        self.pack, self.used = pack, set()

    def name(self, base, alt=""):
        stem = slug(base)
        if stem in self.used and alt:
            stem = f"{stem}-{slug(alt)}"
        n, candidate = 2, stem
        while candidate in self.used:
            candidate, n = f"{stem}-{n}", n + 1
        self.used.add(candidate)
        return f"{candidate}.svg"


# ------------------------------------------------------------ original selections
def legacy_records():
    rows = read_json(HERE / "legacy_icons.json")
    return [r for r in rows]


def build_kept(pack_key, rows):
    """IconPark and Tabler: keep the exact SVG files, move them into the pack folder."""
    files, out = Files(pack_key), []
    for row in rows:
        name = files.name(row["en"])
        target = OUT / pack_key / name
        flat = OUT / f"{row['id']}.svg"
        target.parent.mkdir(parents=True, exist_ok=True)
        if flat.is_file() and not target.is_file():
            shutil.move(flat, target)
        if not target.is_file():
            raise FileNotFoundError(f"missing {pack_key} icon {row['id']}")
        category = tx.LEGACY.get(row["cat"], "界面与操作")
        zh = row["zh"]
        # Earlier automatic Tabler names read "分类 · english" or mixed scripts; translate them.
        if pack_key == "tabler" and (" · " in zh or re.search(r"[A-Za-z]{3,}", zh)):
            zh = translator.translate(row["en"], pack_key) or zh
        out.append(item(pack_key, row["id"], name, row["en"], zh, row["tags"], category,
                        featured=row["featured"]))
    return out


def build_phosphor(rows):
    archive = tar("phosphor")
    source = read_member(archive, "package/dist/index.mjs").decode("utf-8")
    # Parse the generated metadata (name, categories, tags) without executing JavaScript.
    # Icon categories reference the enum assigned to ``e``.
    enum = re.search(r"\be = /\* @__PURE__ \*/ \(\(i\) => \((.*?)\)\)\(e \|\| \{\}\)", source, re.S)
    category_values = dict(re.findall(r"i\.(\w+) = \"([^\"]+)\"", enum.group(1)))
    meta = {}
    for block in re.findall(r"\{\s*name: \"([^\"]+)\",(.*?)\n  \}", source.split("const n = [", 1)[1], re.S):
        name, body = block
        cats = re.search(r"categories: \[(.*?)\]", body, re.S)
        tags = re.search(r"tags: \[(.*?)\]", body, re.S)
        meta[name] = {
            "categories": [category_values.get(c.split(".")[-1].strip(), "") for c in cats.group(1).split(",")]
            if cats else [],
            "tags": re.findall(r"\"([^\"]+)\"", tags.group(1)) if tags else [],
        }
    curated = {r["en"]: r for r in rows}
    files, out = Files("phosphor"), []
    for member in sorted(archive.getnames()):
        m = re.match(r"package/assets/duotone/(.+)-duotone\.svg$", member)
        if not m:
            continue
        name = m.group(1)
        info = meta.get(name, {"categories": [], "tags": []})
        if "brands" in info["categories"] or name.endswith("-logo"):
            continue
        file = files.name(name)
        write(OUT / "phosphor" / file, clean_svg(read_member(archive, member)))
        tags = [t for t in info["tags"] if not t.startswith("*")]
        if name in curated:
            row = curated[name]
            out.append(item("phosphor", row["id"], file, name, row["zh"], row["tags"] + tags,
                            tx.LEGACY.get(row["cat"], "界面与操作"), featured=True))
            continue
        category = next((tx.PHOSPHOR[c] for c in info["categories"] if c in tx.PHOSPHOR), None)
        category = tx.by_keywords(tokens(name), category or "界面与操作") if category in (None, "生活与物品", "界面与操作") else category
        out.append(item("phosphor", f"phosphor-{name}", file, name, tags=tags, category=category))
    return out


def cldr_names():
    names = {}
    for package, member, key in (("cldr", "package/annotations/zh/annotations.json", "annotations"),
                                 ("cldr-derived", "package/annotationsDerived/zh/annotations.json",
                                  "annotationsDerived")):
        data = json.loads(read_member(tar(package), member))
        for glyph, value in data[key]["annotations"].items():
            names[glyph.replace("️", "")] = value
    return names


def build_fluent_emoji(rows):
    base = SRC / "fluent-emoji" / "assets"
    curated = {urllib.parse.unquote(r["src"]).split("/")[0]: r for r in rows}
    zh_names = cldr_names()
    files, out = Files("fluent-emoji"), []
    for folder in sorted(p for p in base.iterdir() if p.is_dir()):
        meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        if meta.get("group") == "Flags":
            continue
        svgs = sorted(folder.glob("Color/*.svg")) or sorted(folder.glob("Default/Color/*.svg"))
        if not svgs:
            continue
        english = meta.get("cldr") or folder.name
        annotation = zh_names.get((meta.get("glyph") or "").replace("️", ""), {})
        zh = (annotation.get("tts") or [""])[0]
        keywords = annotation.get("default", []) + meta.get("keywords", [])
        file = files.name(english)
        write(OUT / "fluent-emoji" / file, clean_svg(svgs[0].read_bytes()))
        row = curated.get(folder.name)
        if row:
            out.append(item("fluent-emoji", row["id"], file, row["en"], row["zh"], row["tags"] + keywords,
                            tx.LEGACY.get(row["cat"], "生活与物品"), featured=True, glyph=meta.get("glyph", "")))
            continue
        category = tx.EMOJI.get(meta.get("group"), "生活与物品")
        if category == "生活与物品":
            category = tx.by_keywords(tokens(english), "生活与物品")
        out.append(item("fluent-emoji", f"fe-{slug(english)}", file, english.capitalize(), zh, keywords, category,
                        glyph=meta.get("glyph", "")))
    return out


# --------------------------------------------------------------------- new packs
def build_mdi():
    archive = tar("mdi")
    meta = json.loads(read_member(archive, "package/meta.json"))
    files, out = Files("mdi"), []
    for icon in meta:
        tags = icon.get("tags", [])
        if icon.get("deprecated") or "Brand / Logo" in tags:
            continue
        name = icon["name"]
        file = files.name(name)
        write(OUT / "mdi" / file, clean_svg(read_member(archive, f"package/svg/{name}.svg"), mono=True))
        category = next((tx.MDI[t] for t in tags if t in tx.MDI), None) or tx.by_keywords(tokens(name))
        out.append(item("mdi", f"mdi-{name}", file, name, tags=icon.get("aliases", []) + tags, category=category))
    return out


def build_carbon():
    archive = tar("carbon-icons")
    meta = json.loads(read_member(archive, "package/metadata.json"))
    sub_of = {}
    for category in meta["categories"]:
        for sub in category.get("subcategories", []):
            for member in sub["members"]:
                sub_of[member] = (category["name"], sub["name"])
    files, out = Files("carbon"), []
    for icon in meta["icons"]:
        name = icon["name"]
        top, sub = sub_of.get(name, (icon.get("category", ""), icon.get("subcategory", "")))
        words = tokens(name)
        if top == "Brand" or "logo" in words or "ibm" in words or words[:1] == ["watson"]:
            continue
        asset = max(icon["assets"], key=lambda a: a["size"] if isinstance(a["size"], int) else 0)
        svg = (asset.get("optimized") or {}).get("data") or asset["source"]
        file = files.name(name.replace("--", "-"))
        write(OUT / "carbon" / file, clean_svg(svg.encode("utf-8"), mono=True))
        category = tx.CARBON.get(sub) or tx.by_keywords(words)
        if "watson-health" in icon.get("namespace", []):
            category = "生物与医学"
        english = icon.get("friendlyName") or name
        out.append(item("carbon", f"carbon-{slug(name)}", file, english, tags=icon.get("aliases", []),
                        category=category))
    return out


def build_carbon_pictograms():
    archive = tar("carbon-pictograms")
    meta = json.loads(read_member(archive, "package/metadata.json"))
    category_of = {}
    for category in meta["categories"]:
        for member in category["members"]:
            category_of.setdefault(member, category["name"])
    names = set(archive.getnames())
    files, out = Files("carbon-pictograms"), []
    for icon in meta["icons"]:
        name = icon["name"]
        group = category_of.get(name, "")
        words = tokens(name)
        if group in ("IBM", "Red Hat", "Third-party logos") or "ibm" in words or "logo" in words:
            continue
        member = f"package/svg/{name}.svg"
        if member not in names:
            continue
        file = files.name(name.replace("--", "-"))
        write(OUT / "carbon-pictograms" / file, clean_svg(read_member(archive, member), mono=True))
        category = tx.PICTOGRAMS.get(group) or tx.by_keywords(words, "生活与物品")
        english = icon.get("friendlyName") or name
        out.append(item("carbon-pictograms", f"cp-{slug(name)}", file, english, tags=icon.get("aliases", []),
                        category=category))
    return out


def build_fluent_system():
    archive = tar("fluentui-system")
    variants = {}
    for member in archive.getnames():
        m = re.match(r"package/icons/([a-z0-9_]+)_(\d+)_(regular|color)\.svg$", member)
        if m:
            variants.setdefault((m.group(1), m.group(3)), []).append((int(m.group(2)), member))
    files, out = Files("fluent-system"), []
    prefer = {"regular": (24, 20, 28, 32, 16, 48, 12), "color": (48, 32, 28, 24, 20, 16)}
    for (base, style), sizes in sorted(variants.items()):
        english = re.sub(r"_ltr$", "", base)
        if base.endswith("_rtl") or (english != base and (english, style) in variants):
            continue  # right-to-left mirrors and duplicated left-to-right names
        by_size = dict(sizes)
        size = next((s for s in prefer[style] if s in by_size), max(by_size))
        mono = style == "regular"
        file = files.name(english + ("" if mono else "-color"))
        write(OUT / "fluent-system" / file, clean_svg(read_member(archive, by_size[size]), mono=mono))
        category = tx.by_keywords(tokens(english))
        out.append(item("fluent-system", f"fs-{file[:-4]}", file, english,
                        tags=["彩色"] if not mono else [], category=category, recolor=mono))
    return out


def build_healthicons():
    archive = tar("healthicons")
    meta = json.loads(read_member(archive, "package/public/icons/meta-data.json"))
    names = set(archive.getnames())
    files, out = Files("healthicons"), []
    for icon in meta:
        member = f"package/public/icons/svg/filled/{icon['path']}.svg"
        if member not in names:
            continue
        file = files.name(icon["id"], icon["category"])
        write(OUT / "healthicons" / file, clean_svg(read_member(archive, member), mono=True))
        tags = [t for t in icon.get("tags", []) if not t.startswith("dhis2:")]
        category = tx.HEALTH.get(icon["category"], "生物与医学")
        out.append(item("healthicons", f"hi-{file[:-4]}", file, icon.get("title") or icon["id"],
                        tags=tags, category=category))
    return out


def build_bioicons():
    zip_path = next((SRC / "bioicons").glob("bioicons-*.zip"))
    archive = zipfile.ZipFile(zip_path)
    root = archive.namelist()[0].split("/")[0]
    index = json.loads(archive.read(f"{root}/static/icons/icons.json"))
    allowed = {"cc-0": "CC0-1.0", "cc-by-3.0": "CC-BY-3.0", "cc-by-4.0": "CC-BY-4.0", "mit": "MIT"}
    # Author folders use underscores and may differ in case from icons.json.
    members = {n.lower(): n for n in archive.namelist()}
    files, out, skipped = Files("bioicons"), [], Counter()
    for icon in index:
        license_id = allowed.get(icon["license"])
        if not license_id:
            skipped["license"] += 1
            continue
        author_dir = icon["author"].replace(" ", "_")
        member = members.get(f"{root}/static/icons/{icon['license']}/{icon['category']}/{author_dir}/"
                             f"{icon['name']}.svg".lower())
        if not member:
            skipped["missing"] += 1
            continue
        data = archive.read(member)
        if len(data) > MAX_BIOICON_BYTES or re.search(rb"<(?:\w+:)?image\b", data):
            skipped["size_or_bitmap"] += 1
            continue
        try:
            svg = clean_svg(data)
        except Exception:
            skipped["invalid"] += 1
            continue
        file = files.name(icon["name"], icon["author"])
        write(OUT / "bioicons" / file, svg)
        category = tx.BIOICONS.get(icon["category"], "生物与医学")
        english = icon["name"].replace("_", " ")
        topic = icon["category"].replace("_", " ").replace("-", " ")
        out.append(item("bioicons", f"bio-{file[:-4]}", file, english, tags=[topic],
                        category=category, author=icon["author"].replace("_", " "), license=license_id))
    print("bioicons skipped", dict(skipped), flush=True)
    return out


# ----------------------------------------------------------------------- licenses
def write_licenses():
    LICENSES.mkdir(parents=True, exist_ok=True)
    old = LICENSES / "fluent-LICENSE.txt"
    if old.is_file():
        old.replace(LICENSES / "fluent-emoji-LICENSE.txt")
    for pack, member in (("mdi", "package/LICENSE"), ("carbon-icons", "package/LICENSE"),
                         ("carbon-pictograms", "package/LICENSE"), ("healthicons", "package/LICENSE")):
        target = {"carbon-icons": "carbon"}.get(pack, pack)
        (LICENSES / f"{target}-LICENSE.txt").write_bytes(read_member(tar(pack), member))
    fluent_system = LICENSES / "fluent-system-LICENSE.txt"
    if not fluent_system.is_file():
        from common import fetch
        fetch("https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/LICENSE", fluent_system)
    zip_path = next((SRC / "bioicons").glob("bioicons-*.zip"))
    archive = zipfile.ZipFile(zip_path)
    root = archive.namelist()[0].split("/")[0]
    parts = ["Bioicons — https://bioicons.com — https://github.com/duerrsimon/bioicons",
             "Each icon keeps the license and author listed in dist/data.json and dist/sources.csv.", ""]
    for folder in ("cc-0", "cc-by-3.0", "cc-by-4.0", "mit"):
        parts += ["=" * 72, f"{folder.upper()} — license text shipped with Bioicons", "=" * 72,
                  archive.read(f"{root}/static/icons/{folder}/LICENSE").decode("utf-8", "replace").strip(), ""]
    authors = json.loads(archive.read(f"{root}/static/icons/authors.json"))
    parts += ["=" * 72, "Authors", "=" * 72] + [f"{k.replace('_', ' ')}: {v}" for k, v in sorted(authors.items())]
    (LICENSES / "bioicons-LICENSES.txt").write_text("\n".join(parts) + "\n", encoding="utf-8", newline="\n")
    return {k.replace("_", " "): v for k, v in authors.items()}


# --------------------------------------------------------------------------- main
def featured(record):
    pack, category = record["pack"], record["cat"]
    if "featured" in record:
        return record["featured"]
    if pack in ("bioicons", "healthicons", "carbon-pictograms"):
        return category in tx.CORE
    if pack == "fluent-system" and not record.get("recolor", True):
        return category in tx.CORE
    if pack in ("mdi", "carbon", "phosphor"):
        return category in {"智能与计算", "科学与实验", "图表与统计", "网络与云", "数据与存储"}
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="pack keys to rebuild")
    args = parser.parse_args()
    legacy = legacy_records()
    by_pack = {}
    for row in legacy:
        by_pack.setdefault(LEGACY_PACK[row["pack"]], []).append(row)
    authors = write_licenses()
    builders = {
        "iconpark": lambda: build_kept("iconpark", by_pack["iconpark"]),
        "tabler": lambda: build_kept("tabler", by_pack["tabler"]),
        "phosphor": lambda: build_phosphor(by_pack["phosphor"]),
        "fluent-emoji": lambda: build_fluent_emoji(by_pack["fluent-emoji"]),
        "mdi": build_mdi, "carbon": build_carbon, "carbon-pictograms": build_carbon_pictograms,
        "fluent-system": build_fluent_system, "healthicons": build_healthicons, "bioicons": build_bioicons,
    }
    for pack, build in builders.items():
        if args.only and pack not in args.only:
            continue
        records = build()
        if pack in ("phosphor", "fluent-emoji"):
            # These selections are rebuilt from source; drop the old flat copies.
            for row in by_pack[pack]:
                (OUT / f"{row['id']}.svg").unlink(missing_ok=True)
        ids = Counter(r["id"] for r in records)
        duplicates = [i for i, n in ids.items() if n > 1]
        if duplicates:
            raise ValueError(f"{pack}: duplicate ids {duplicates[:5]}")
        for record in records:
            record["featured"] = bool(featured(record))
            path = OUT / pack / record["file"]
            record["sha256"] = sha256(path)
            record["bytes"] = path.stat().st_size
            if pack == "bioicons":
                record["author_url"] = authors.get(record["author"], "")
        keep = {r["file"] for r in records}
        stale = [p for p in (OUT / pack).glob("*.svg") if p.name not in keep]
        for path in stale:
            path.unlink()
        info = dict(PACKS[pack], key=pack, path=f"assets/icons/{pack}/", count=len(records),
                    featured=sum(r["featured"] for r in records))
        write_json(MANIFESTS / f"icons-{pack}.json", {"pack": info, "assets": records})
        cats = Counter(r["cat"] for r in records)
        print(pack, len(records), "featured", info["featured"], "removed", len(stale), dict(cats.most_common(6)),
              flush=True)
    leftovers = [p.name for p in OUT.glob("*.svg")]
    if leftovers and not args.only:
        raise RuntimeError(f"{len(leftovers)} flat icon files were not assigned to a pack: {leftovers[:5]}")


if __name__ == "__main__":
    main()
