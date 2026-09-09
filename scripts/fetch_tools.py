#!/usr/bin/env python3
"""Fetch pinned upstream binaries without overwriting existing cache or tools."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def check_target(path):
    if path.is_symlink():
        raise ValueError('Refusing symbolic link target: ' + str(path))
    if path.exists() and not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('Target is not a regular file: ' + str(path))


def publish(partial, target, expected):
    """Race-safe no-clobber publication; identical concurrent result may be reused."""
    check_target(target)
    try:
        os.link(partial, target)
    except FileExistsError:
        check_target(target)
        if digest(target) != expected:
            raise ValueError('Refusing to replace existing file: ' + str(target))
    partial.unlink()


def copy_hashed(source, dest):
    h = hashlib.sha256()
    for chunk in iter(lambda: source.read(1024 * 1024), b''):
        dest.write(chunk); h.update(chunk)
    dest.flush(); os.fsync(dest.fileno())
    return h.hexdigest()


def fetch(item, destination, opener=urllib.request.urlopen):
    destination = Path(destination)
    # Lock files are trusted source, but names still cannot select outside paths.
    for key in ('asset', 'command', 'member'):
        value = item[key]
        if not value or Path(value).name != value or value in ('.', '..') or '\\' in value:
            raise ValueError('Expected a basename for ' + key)
    destination.mkdir(parents=True, exist_ok=True)
    bindir = destination/'bin'
    if bindir.is_symlink():
        raise ValueError('Refusing symbolic link bin directory')
    bindir.mkdir(exist_ok=True)
    archive = destination/item['asset']; binary = bindir/item['command']
    check_target(archive); check_target(binary)
    if not archive.exists():
        fd, name = tempfile.mkstemp(prefix=archive.name+'.download-', dir=str(destination))
        partial = Path(name)
        try:
            with os.fdopen(fd, 'wb') as out, opener(item['url'], timeout=45) as inp:
                actual = copy_hashed(inp, out)
            if actual != item['sha256']:
                raise ValueError('Digest mismatch: ' + item['asset'])
            publish(partial, archive, actual)
        except BaseException:
            print('Incomplete download retained: ' + str(partial), file=sys.stderr)
            raise
    if digest(archive) != item['sha256']:
        raise ValueError('Cached digest mismatch: ' + item['asset'])
    with tarfile.open(archive) as members:
        found = [m for m in members if m.isfile() and Path(m.name).name == item['member']]
        if len(found) != 1:
            raise ValueError('Expected exactly one executable member')
        fd, name = tempfile.mkstemp(prefix=binary.name+'.partial-', dir=str(bindir))
        partial = Path(name)
        try:
            with os.fdopen(fd, 'wb') as out, members.extractfile(found[0]) as inp:
                actual = copy_hashed(inp, out)
            partial.chmod(0o755)
            publish(partial, binary, actual)
        except BaseException:
            print('Incomplete executable retained: ' + str(partial), file=sys.stderr)
            raise
    if not os.access(binary, os.X_OK):
        raise ValueError('Existing executable lacks execute permission: ' + str(binary))
    return {'command':item['command'], 'sha256':actual, 'release':item['release']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--platform', required=True, choices=['darwin-arm64','linux-x86_64'])
    p.add_argument('--destination', required=True, type=Path)
    a = p.parse_args()
    lock = json.loads((Path(__file__).resolve().parents[1]/'tools.lock.json').read_text())[a.platform]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(lambda item: fetch(item, a.destination), lock):
            print(json.dumps(result))


if __name__ == '__main__':
    main()
