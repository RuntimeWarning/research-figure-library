#!/usr/bin/env python3
"""Flag transparent-background elements whose content touches the image border.

Content running into the edge usually means the drawing was clipped by a too
tight viewBox.  Elements that fill their canvas on purpose (patch grids) are
listed in ``FULL_BLEED``.  Exits with status 1 when anything is flagged.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ASSETS  # noqa: E402

FULL_BLEED = {"mae-cat", "mae-dog", "mae-visible-cat", "patch-row-cat", "patches-cat", "patches-dog"}


def touches(path: Path) -> dict:
    image = Image.open(path)
    if image.mode != "RGBA":
        return {}
    alpha = np.asarray(image.getchannel("A"))
    if alpha.min() == 255:
        return {}
    h, w = alpha.shape
    edges = {"top": alpha[0], "bottom": alpha[-1], "left": alpha[:, 0], "right": alpha[:, -1]}
    limit = {"top": max(3, w // 100), "bottom": max(3, w // 100), "left": max(3, h // 100), "right": max(3, h // 100)}
    return {k: int((v > 40).sum()) for k, v in edges.items() if (v > 40).sum() > limit[k]}


def main():
    flagged = []
    for pattern in ("elements/*.png", "vision/*.png", "collected/*/*.png"):
        for path in sorted(ASSETS.glob(pattern)):
            if path.stem in FULL_BLEED:
                continue
            hit = touches(path)
            if hit:
                flagged.append((path.relative_to(ASSETS).as_posix(), hit))
    for name, hit in flagged:
        print(f"clipped? {name} {hit}")
    print(f"{len(flagged)} element(s) touch the border")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
