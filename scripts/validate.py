#!/usr/bin/env python3
"""Validate local or public catalogs without third-party dependencies."""
from collections import Counter
import argparse
import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

def validate(directory):
    directory=directory.resolve()
    data=json.loads((directory/'data.json').read_text(encoding='utf-8-sig'))
    assets=data['assets'];counts=Counter(a['type'] for a in assets)
    assert len(assets)==data['counts']['total']
    assert len({a['id'] for a in assets})==len(assets),'Duplicate IDs'
    kinds=('icon','paper','atomic','architecture')
    assert set(counts)<=set(kinds),dict(counts)
    for kind in kinds:assert counts[kind]==data['counts'].get(kind,0)
    classic=sum(bool(a.get('architecture') or a['type']=='architecture') for a in assets)
    assert classic==data['counts'].get('classic_architecture',classic)
    featured=sum(bool(a['featured']) for a in assets)
    assert featured==data['counts']['featured']
    files=set();source_only=0;license_files=set()
    for a in assets:
        assert a['name'] and isinstance(a['tags'],list),a['id']
        assert a['source_url'].startswith('https://'),a['id']
        paths=[a.get(k,'') for k in ('preview','svg','png','pdf')]
        if not any(paths):
            assert a['type'] in ('paper','atomic') and a.get('source_only'),a['id']
            source_only+=1
        for value in filter(None,paths):
            assert value.isascii() and '\\' not in value and not value.startswith('/'),value
            p=(directory/value).resolve()
            assert p.is_relative_to(directory) and p.is_file(),value
            assert p.stat().st_size<100*1024*1024,value
            files.add(p)
        if a['type']=='icon':assert a['license'] in ('MIT','Apache-2.0'),a['id']
        if a['type'] in ('paper','atomic'):assert a['license']!='MIT',a['id']
        if a['type']=='architecture':
            assert a['license']=='MIT' and a.get('pack')=='original-architectures',a['id']
            assert a.get('architecture') and a.get('svg_kind')=='vector',a['id']
            assert a['svg'].startswith('assets/architectures/'),a['id']
        license_url=a.get('license_url','')
        if license_url and not urlsplit(license_url).scheme:
            assert license_url.startswith('licenses/') and '..' not in Path(license_url).parts,a['id']
            license_path=(directory/license_url).resolve()
            assert license_path.is_relative_to(directory) and license_path.is_file(),a['id']
            license_files.add(license_path)
        for kind,expected in a.get('hashes',{}).items():
            if a.get(kind):
                assert hashlib.sha256((directory/a[kind]).read_bytes()).hexdigest()==expected,a['id']
    for p in files:
        if p.suffix=='.svg':
            root=ET.parse(p).getroot();assert root.tag.endswith('svg'),p.name
            for el in root.iter():
                assert not el.tag.endswith('script'),p.name
                for key,value in el.attrib.items():
                    assert not key.lower().startswith('on'),p.name
                    if key.endswith('href'):
                        assert not value.startswith(('http:','https:','file:','//')),p.name
    assert license_files,'Missing icon licenses'
    with (directory/'sources.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f));assert len(rows)==len(assets)
    if source_only:
        assert source_only==counts['paper']+counts['atomic']
        assert not (directory/'assets/papers').exists(),'Public build contains paper files'
        assert data['counts']['available']==counts['icon']+counts['architecture']
    if 'available' in data['counts']:assert data['counts']['available']==len(assets)-source_only
    for field in ('png','svg','pdf'):
        key='paper_'+field
        if key in data['counts']:
            assert data['counts'][key]==sum(bool(a.get(field)) for a in assets if a['type'] in ('paper','atomic')),key
    summary={'status':'passed','total':len(assets),'featured':featured,'types':dict(counts),'classic_architecture':classic,'source_only':source_only,'referenced_files':len(files),'licenses':len(license_files)}
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',nargs='?',default=str(Path(__file__).resolve().parents[1]/'dist'))
    args=parser.parse_args();validate(Path(args.directory))
