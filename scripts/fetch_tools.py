#!/usr/bin/env python3
"""Fetch pinned upstream binaries into an explicitly chosen staging directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--platform',required=True,choices=['darwin-arm64','linux-x86_64'])
p.add_argument('--destination',required=True,type=Path)
a=p.parse_args()
lock=json.loads((Path(__file__).resolve().parents[1]/'tools.lock.json').read_text())[a.platform]
a.destination.mkdir(parents=True,exist_ok=True)

def fetch(item):
    archive=a.destination/item['asset']
    def digest(path):
        h=hashlib.sha256()
        with path.open('rb') as f:
            for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
        return h.hexdigest()
    if not archive.exists():
        partial=Path(str(archive)+'.download')
        with urllib.request.urlopen(item['url'],timeout=45) as src, partial.open('wb') as out:
            shutil.copyfileobj(src,out)
        if digest(partial)!=item['sha256']:raise RuntimeError('Digest mismatch: '+item['asset'])
        partial.rename(archive)
    if digest(archive)!=item['sha256']:raise RuntimeError('Cached digest mismatch: '+item['asset'])
    binary=a.destination/'bin'/item['command'];binary.parent.mkdir(exist_ok=True)
    with tarfile.open(archive) as t:
        members=[m for m in t if m.isfile() and Path(m.name).name==item['member']]
        if len(members)!=1:raise RuntimeError('Expected exactly one executable member')
        content=t.extractfile(members[0]).read()
    if binary.exists() and binary.read_bytes()!=content:raise RuntimeError('Refusing to replace existing binary')
    binary.write_bytes(content);binary.chmod(0o755)
    return {'command':item['command'],'sha256':hashlib.sha256(content).hexdigest(),'release':item['release']}

for r in ThreadPoolExecutor(max_workers=3).map(fetch,lock):print(json.dumps(r))
