#!/usr/bin/env python3
"""Download the pinned upstream icon sources into ``.cache/icons/``.

npm tarballs and Git commits are pinned so that every build reproduces the same
files.  Fluent Emoji is fetched file by file (metadata plus the Color SVG of each
emoji) because the full repository also contains large 3D PNG renders.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import CACHE, fetch  # noqa: E402

ROOT = CACHE / "icons"
NPM = {
    "mdi": "https://registry.npmjs.org/@mdi/svg/-/svg-7.4.47.tgz",
    "carbon-icons": "https://registry.npmjs.org/@carbon/icons/-/icons-11.90.0.tgz",
    "carbon-pictograms": "https://registry.npmjs.org/@carbon/pictograms/-/pictograms-12.86.0.tgz",
    "fluentui-system": "https://registry.npmjs.org/@fluentui/svg-icons/-/svg-icons-1.1.343.tgz",
    "healthicons": "https://registry.npmjs.org/healthicons/-/healthicons-2.0.0.tgz",
    "phosphor": "https://registry.npmjs.org/@phosphor-icons/core/-/core-2.1.1.tgz",
    "cldr": "https://registry.npmjs.org/cldr-annotations-full/-/cldr-annotations-full-48.2.0.tgz",
    "cldr-derived": "https://registry.npmjs.org/cldr-annotations-derived-full/-/cldr-annotations-derived-full-48.2.0.tgz",
}
BIOICONS_COMMIT = "d29e766ea7580b8063c4f47b29e872db40a4d979"
FLUENT_EMOJI_COMMIT = "1ffb34c752ecf5d402f04cfb4b392c77f57c54bc"
SKIN_TONES = ("Light", "Medium-Light", "Medium", "Medium-Dark", "Dark")


def fluent_emoji():
    base = ROOT / "fluent-emoji"
    tree = json.loads(fetch(
        f"https://api.github.com/repos/microsoft/fluentui-emoji/git/trees/{FLUENT_EMOJI_COMMIT}?recursive=1",
        base / "tree.json"))
    paths = [item["path"] for item in tree["tree"] if item["type"] == "blob"]
    wanted = [p for p in paths if p.endswith("/metadata.json")]
    for p in paths:
        parts = p.split("/")
        if not p.endswith(".svg") or "Color" not in parts:
            continue
        if any(tone in parts for tone in SKIN_TONES):
            continue  # one default-tone design per emoji
        wanted.append(p)

    def get(path):
        url = (f"https://raw.githubusercontent.com/microsoft/fluentui-emoji/{FLUENT_EMOJI_COMMIT}/"
               + urllib.parse.quote(path))
        fetch(url, base / path)
        return path
    with ThreadPoolExecutor(max_workers=8) as pool:
        done = list(pool.map(get, wanted))
    print("fluent-emoji files", len(done), flush=True)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for name, url in NPM.items():
        data = fetch(url, ROOT / name / "package.tgz")
        print(name, len(data), flush=True)
    data = fetch(f"https://codeload.github.com/duerrsimon/bioicons/zip/{BIOICONS_COMMIT}",
                 ROOT / "bioicons" / f"bioicons-{BIOICONS_COMMIT}.zip", timeout=900)
    print("bioicons", len(data), flush=True)
    fluent_emoji()


if __name__ == "__main__":
    main()
