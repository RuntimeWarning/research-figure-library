#!/usr/bin/env python3
"""Serve the figure library locally (Python standard library only)."""
from __future__ import annotations

import argparse
import functools
import gzip
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1] / "dist"
COMPRESS = {".json", ".js", ".css", ".csv", ".svg", ".html"}
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".svg": "image/svg+xml", ".webp": "image/webp", ".json": "application/json; charset=utf-8",
        ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".csv": "text/csv; charset=utf-8", ".html": "text/html; charset=utf-8",
    }
    cache: dict[Path, bytes] = {}

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        path = Path(self.translate_path(urlsplit(self.path).path))
        if path.is_dir():
            path = path / "index.html"
        if (path.suffix in COMPRESS and path.is_file() and "gzip" in self.headers.get("Accept-Encoding", "")
                and path.stat().st_size > 2048):
            data = self.cache.get(path)
            if data is None:
                data = gzip.compress(path.read_bytes(), 6)
                if path.name == "data.json":
                    self.cache[path] = data
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(str(path)))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def log_message(self, format, *args):  # quiet console
        pass


def main():
    parser = argparse.ArgumentParser(description="研图 · 本地检索服务")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not (ROOT / "index.html").is_file() or not (ROOT / "data.json").is_file():
        parser.error("dist/index.html 或 dist/data.json 不存在，请确认项目完整。")
    handler = functools.partial(Handler, directory=str(ROOT))
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    except OSError as error:
        parser.exit(1, f"无法启动本地服务：{error}\n如果服务已在运行，请直接打开 http://127.0.0.1:{args.port}/\n")
    print(f"\n研图 · 论文原图与科研图标素材库\n打开：http://127.0.0.1:{args.port}/\n按 Ctrl+C 停止服务。\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
