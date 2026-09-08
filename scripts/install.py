#!/usr/bin/env python3
"""Install in a user-selected prefix; preserve unrelated executables and shell settings."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--prefix',type=Path,default=Path.home()/'.local')
p.add_argument('--tools-dir',type=Path,help='directory containing verified upstream executables')
p.add_argument('--tool',action='append',default=[],help='explicit dependency mapping NAME=/absolute/path')
p.add_argument('--shell-file',type=Path,help='optional shell file; backed up before adding one PATH block')
a=p.parse_args()
# Validate potential conflicts before changing any active installation.
source=Path(__file__).resolve().parents[1]
prefix=a.prefix.expanduser().absolute()
if prefix in [Path('/'),Path('/usr'),Path('/usr/local'),Path('/opt/homebrew')]:
    p.error('Choose a personal installation prefix')
base_check=prefix/'share'/'bio-cli'
current_check=base_check/'current'
if (current_check.exists() or current_check.is_symlink()) and not current_check.is_symlink():
    raise SystemExit('Unmanaged current directory; refusing replacement')
for name in ['peek','packz','unpackz','dust-du']:
    link=prefix/'bin'/name
    if link.exists() or link.is_symlink():
        if not link.is_symlink() or os.readlink(link)!=str(current_check/'bin'/name):
            raise SystemExit('Unmanaged executable conflict: '+name)
if a.shell_file and a.shell_file.exists():
    text=a.shell_file.read_text()
    line='export PATH='+shlex.quote(str(current_check/'bin'))+':"$PATH"'
    if '# bio-cli: managed PATH entry' in text and line not in text:
        raise SystemExit('Existing PATH marker differs; inspect manually')
version=(source/'VERSION').read_text().strip()
files=['bio_cli.py','VERSION','README.md','tools.lock.json','scripts/install.py','scripts/fetch_tools.py','tests/test_cli.py','tests/test_installer.py']
h=hashlib.sha256()
for file in files:h.update(file.encode());h.update((source/file).read_bytes())
release_id=version+'-'+h.hexdigest()[:12]
base=prefix/'share'/'bio-cli'
release=base/'releases'/release_id
state=prefix/'state'/'bio-cli'/('install-'+release_id)
state.mkdir(parents=True,exist_ok=True)
overrides=dict(x.split('=',1) for x in a.tool)
known=['python3','tar','gzip','bzip2','xz','zstd','samtools','bcftools','bgzip','gdu','dust-du','dua','bat','rg','fd','eza']
runtime={}
# Inspect executable targets, not just PATH entries: prefix/bin also links here.
def managed_wrapper(value):
    resolved=Path(value).resolve()
    return (resolved.parent==(base/'current'/'bin').resolve() or
            (resolved.parent.name=='bin' and resolved.parent.parent.parent==(base/'releases').resolve()))

old_config=base/'current'/'runtime.json'
old_runtime=json.loads(old_config.read_text()) if old_config.is_file() else {}
def previous_dependency(name):
    value=old_runtime.get(name)
    return value if value and not managed_wrapper(value) and os.access(value,os.X_OK) else None

def find_dependency(name):
    for entry in os.environ.get('PATH','').split(os.pathsep):
        if not entry:continue
        candidate=Path(entry)/name
        if candidate.is_file() and os.access(candidate,os.X_OK):
            if not managed_wrapper(candidate):return str(candidate.absolute())
            previous=previous_dependency(name)
            if previous:return previous
    return previous_dependency(name)

for name in known:
    candidate=overrides.get(name)
    if not candidate and name not in ['gdu','dust-du']:
        candidate=find_dependency(name)
    if not candidate and a.tools_dir and (a.tools_dir/name).is_file():candidate=str((a.tools_dir/name).absolute())
    if not candidate:candidate=find_dependency(name)
    if not candidate:raise SystemExit('Missing dependency before installation: '+name)
    candidate=str(Path(candidate).absolute())
    if managed_wrapper(candidate):raise SystemExit('Managed wrapper is not a dependency: '+name)
    if not os.access(candidate,os.X_OK):raise SystemExit('Not executable: '+candidate)
    runtime[name]=candidate
# An existing release is immutable. Never report new overrides while running old ones.
if release.exists():
    installed=json.loads((release/'runtime.json').read_text())
    for name,value in overrides.items():
        if name not in installed or Path(value).resolve()!=Path(installed[name]).resolve():
            raise SystemExit('Existing release uses a different dependency: '+name+'; choose a new personal --prefix')
    runtime=installed
    if any(managed_wrapper(value) for value in runtime.values()):
        raise SystemExit('Existing release contains a managed dependency wrapper')
# Check executability before creating an active release.
versions={}
for name in known:
    flag='--version' if name!='gdu' else '--version'
    r=subprocess.run([runtime[name],flag],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)
    if r.returncode:raise SystemExit('Version probe failed: '+name)
    versions[name]={'path':runtime[name],'version':r.stdout.decode('utf-8','replace').splitlines()[:3]}
if not release.exists():
    release.mkdir(parents=True)
    for f in files:
        out=release/f;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/f,out)
    # Copy staging binaries into the versioned release. Reused system tools stay external.
    if a.tools_dir:
        for name in known:
            if Path(runtime[name]).parent==a.tools_dir.absolute():
                out=release/'vendor'/name;out.parent.mkdir(exist_ok=True);shutil.copy2(runtime[name],out);runtime[name]=str(out)
    (release/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
# Record the paths actually used, including binaries copied into this release.
for name in known:versions[name]['path']=runtime[name]
binpath=release/'bin';binpath.mkdir(exist_ok=True)
for name in ['peek','packz','unpackz']:
    # Use subcommand form so argv[0] need not rely on symlink resolution.
    body='#!/bin/sh\nexec '+shlex.quote(runtime['python3'])+' '+shlex.quote(str(release/'bio_cli.py'))+' '+name+' "$@"\n'
    (binpath/name).write_text(body);(binpath/name).chmod(0o755)
for name in ['gdu','dust-du','dua','bat','rg','fd','eza','zstd','samtools','bcftools','bgzip']:
    extra=''
    if name=='gdu':extra=' --no-delete --no-spawn-shell -m 2'
    if name=='dua':extra=' -t 2'
    if name=='dust-du':extra=' -T 2'
    (binpath/name).write_text('#!/bin/sh\nexec '+shlex.quote(runtime[name])+extra+' "$@"\n');(binpath/name).chmod(0o755)
# Only owned symlinks are replaced. Current switches atomically.
current=base/'current'
if current.exists() and not current.is_symlink():raise SystemExit('Unmanaged current directory; refusing replacement')
previous=os.readlink(current) if current.is_symlink() else None
temporary=base/('current.new-'+str(os.getpid()))
temporary.symlink_to(release);os.replace(temporary,current)
userbin=prefix/'bin';userbin.mkdir(exist_ok=True)
for name in ['peek','packz','unpackz','dust-du']:
    link=userbin/name;target=current/'bin'/name
    if link.exists() or link.is_symlink():
        if not link.is_symlink() or os.readlink(link)!=str(target):raise SystemExit('Unmanaged executable conflict: '+name)
    else:link.symlink_to(target)
if a.shell_file:
    shell=a.shell_file.expanduser().absolute()
    old=shell.read_text() if shell.exists() else ''
    marker='# bio-cli: managed PATH entry'
    line='export PATH='+shlex.quote(str(current/'bin'))+':"$PATH"'
    if marker not in old:
        if shell.exists():shutil.copy2(shell,state/(shell.name+'.backup'))
        with shell.open('a') as f:f.write('\n'+marker+'\n'+line+'\n')
    elif line not in old:raise SystemExit('Existing PATH marker differs; inspect manually')
record={'release_id':release_id,'release':str(release),'previous':previous,'tools':versions,'shell_file':str(a.shell_file) if a.shell_file else None}
(state/'installation.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
