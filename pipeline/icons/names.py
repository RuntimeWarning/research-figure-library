"""Chinese display names for icons, built from the term list in ``zh_terms.tsv``."""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Style words are moved to a suffix so that the subject reads first.
SUFFIX = {"outline": "轮廓", "outlined": "轮廓", "variant": "变体", "alt": "备选", "filled": "填充"}
CJK = re.compile(r"[㐀-鿿]")


def tokens(name: str) -> list[str]:
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)  # "brainCircuit"; keeps "3D" together
    return [t for t in re.split(r"[^0-9A-Za-z]+", name.lower()) if t]


class Translator:
    def __init__(self, path: Path = HERE / "zh_terms.tsv"):
        self.terms: dict[str, dict[tuple[str, ...], str]] = {"": {}}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            pack = parts[2] if len(parts) > 2 else ""
            self.terms.setdefault(pack, {})[tuple(parts[0].split())] = parts[1]
        self.longest = max(len(k) for table in self.terms.values() for k in table)

    def lookup(self, phrase, pack):
        table = self.terms.get(pack, {})
        return table.get(phrase, self.terms[""].get(phrase))

    def translate(self, name: str, pack: str = "") -> str:
        """Return a Chinese name, or "" when no term of the name is known."""
        words = tokens(name)
        parts, suffix, known = [], [], 0
        i = 0
        while i < len(words):
            if words[i] in SUFFIX and i > 0:
                suffix.append(SUFFIX[words[i]])
                i += 1
                continue
            for size in range(min(self.longest, len(words) - i), 0, -1):
                zh = self.lookup(tuple(words[i:i + size]), pack)
                if zh is not None:
                    if zh != "-":
                        parts.append(zh)
                    known += size
                    i += size
                    break
            else:
                parts.append(words[i].upper() if len(words[i]) <= 3 and not words[i].isdigit() else words[i])
                i += 1
        if not known or not any(CJK.search(p) for p in parts):
            return ""
        text = ""
        for part in parts:
            if text and (not CJK.search(part[0]) or not CJK.search(text[-1])):
                text += " "
            text += part
        if suffix:
            text += "（" + "·".join(dict.fromkeys(suffix)) + "）"
        return text


def english_title(name: str) -> str:
    words = tokens(name)
    return " ".join(w if w.isdigit() else w.capitalize() for w in words)
