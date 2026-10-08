#!/usr/bin/env python3
"""Serve the local, complete asset library. Python standard library only."""
from __future__ import annotations
import argparse
import functools
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout,'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

class AssetHandler(SimpleHTTPRequestHandler):
    catalog_bytes = b''
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        '.svg': 'image/svg+xml',
        '.json': 'application/json; charset=utf-8',
        '.js': 'text/javascript; charset=utf-8',
        '.css': 'text/css; charset=utf-8',
        '.csv': 'text/csv; charset=utf-8',
    }
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()
    def do_GET(self):
        if urlsplit(self.path).path=='/data.json':
            self.send_response(200)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(self.catalog_bytes)))
            self.end_headers()
            self.wfile.write(self.catalog_bytes)
        else:
            super().do_GET()

def main():
    parser=argparse.ArgumentParser(description='论文素材统一检索 · 本地服务')
    parser.add_argument('--port', type=int, default=8766)
    args=parser.parse_args()
    directory=ROOT/'dist'
    if not (directory/'index.html').is_file() or not (directory/'data.json').is_file():
        parser.error('dist/index.html 或 dist/data.json 不存在，请检查项目是否完整。')
    catalog=json.loads((directory/'data.json').read_text(encoding='utf-8-sig'))
    source_only=0
    for item in catalog['assets']:
        item['available']=True
        if item['type'] in ('paper','atomic'):
            preview=item.get('preview','')
            if not preview or not (directory/preview).is_file():
                for key in ('preview','svg','png','pdf'):item[key]=''
                item['available']=False;item['source_only']=True;source_only+=1
    catalog['counts']['available']=len(catalog['assets'])-source_only
    catalog['counts']['source_only']=source_only
    for field in ('png','svg','pdf'):
        catalog['counts']['paper_'+field]=sum(bool(a.get(field)) for a in catalog['assets'] if a['type'] in ('paper','atomic'))
    AssetHandler.catalog_bytes=json.dumps(catalog,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    handler=functools.partial(AssetHandler,directory=str(directory))
    try:
        server=ThreadingHTTPServer(('127.0.0.1',args.port),handler)
    except OSError as e:
        parser.exit(1,f'无法启动本地服务：{e}\n若已有服务运行，直接打开 http://127.0.0.1:{args.port}/\n')
    print(f'\n论文素材统一检索\n打开网址：http://127.0.0.1:{args.port}/\n按 Ctrl+C 关闭服务。\n',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务已关闭。',flush=True)
    finally:
        server.server_close()

if __name__=='__main__':
    main()
