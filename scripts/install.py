#!/usr/bin/env python3
"""Install in a personal prefix with staged releases and compensating rollback."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import socket

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bio_runtime import run_capture
from bio_tools import BIO_TOOLS, KNOWN_TOOLS, PROFILES, required_tools

FILES = ['bio_runtime.py','tests/test_runtime.py','tests/test_fetch_tools.py','bio_cli.py','VERSION','README.md','tools.lock.json','scripts/install.py',
         'scripts/fetch_tools.py','tests/test_cli.py','tests/test_installer.py','CHANGELOG.md','bio_tools.py']
FILES += sorted(path.relative_to(Path(__file__).resolve().parents[1]).as_posix()
                for path in (Path(__file__).resolve().parents[1] / 'docs').rglob('*.md'))
OWNED = ['peek','packz','unpackz','dust-du','bio-cli']
KNOWN = list(KNOWN_TOOLS)
WRAPPED = ['gdu','dust-du','dua','bat','rg','fd','eza','zstd','samtools','bcftools','bgzip']


def wrapper_bodies(runtime, release):
    bodies = {}
    for name in ['peek', 'packz', 'unpackz', 'bio-cli']:
        command = '' if name == 'bio-cli' else ' ' + name
        bodies[name] = '#!/bin/sh\nexec '+shlex.quote(runtime['python3'])+' '+shlex.quote(str(release/'bio_cli.py'))+command+' "$@"\n'
    for name in WRAPPED:
        if name not in runtime:
            continue
        extra = {'gdu':' --no-delete --no-spawn-shell -m 2','dua':' -t 2','dust-du':' -T 2'}.get(name,'')
        bodies[name] = '#!/bin/sh\nexec '+shlex.quote(runtime[name])+extra+' "$@"\n'
    return bodies


def atomic_text(path, text, mode=0o600):
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as out:
            out.write(text); out.flush(); os.fsync(out.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def switch(current, target):
    temporary = current.with_name('current.new-' + str(os.getpid()))
    try:
        temporary.symlink_to(target)
        os.replace(temporary, current)
    finally:
        if temporary.is_symlink(): temporary.unlink()


def install(a):
    source = Path(__file__).resolve().parents[1]
    prefix = a.prefix.expanduser().resolve()
    if prefix in [Path('/'), Path('/usr'), Path('/usr/local'), Path('/opt/homebrew')]:
        raise ValueError('Choose a personal installation prefix')
    base = prefix/'share/bio-cli'; base.mkdir(parents=True, exist_ok=True)
    with install_lock(base):
        return install_locked(a, source, prefix, base)


@contextlib.contextmanager
def install_lock(base):
    # Atomic mkdir works on shared filesystems that return ENOSYS for flock/lockf.
    # Never guess whether a foreign/stale owner is dead and remove its lock.
    lockdir = base/'install.lock.d'
    try:
        lockdir.mkdir(mode=0o700)
    except FileExistsError:
        raise ValueError('Installation lock already exists; inspect its owner and active installers before recovery: ' + str(lockdir))
    owner = lockdir/'owner.json'
    try:
        owner.write_text(json.dumps({'pid':os.getpid(), 'host':socket.gethostname()})+'\n')
        yield
    finally:
        if owner.exists(): owner.unlink()
        lockdir.rmdir()


def install_locked(a, source, prefix, base):
    profile = getattr(a, 'profile', 'full')
    required_names = required_tools(profile)
    selected_names = KNOWN_TOOLS if profile == 'full' else required_names + BIO_TOOLS
    owned_names = [name for name in OWNED if profile == 'full' or name != 'dust-du']
    current = base/'current'; userbin = prefix/'bin'
    if (current.exists() or current.is_symlink()) and not current.is_symlink():
        raise ValueError('Unmanaged current directory; refusing replacement')
    for name in owned_names:
        link = userbin/name
        if link.exists() or link.is_symlink():
            if not link.is_symlink() or os.readlink(link) != str(current/'bin'/name):
                raise ValueError('Unmanaged executable conflict: ' + name)
    shell = a.shell_file.expanduser().absolute() if a.shell_file else None
    old_shell = None; new_shell = None; shell_mode = 0o600
    if shell:
        if shell.is_symlink():
            raise ValueError('Shell configuration is a symlink; specify its real target')
        if not shell.parent.is_dir():
            raise ValueError('Shell configuration parent does not exist')
        old_shell = shell.read_text() if shell.exists() else None
        shell_mode = shell.stat().st_mode & 0o777 if shell.exists() else 0o600
        marker = '# bio-cli: managed PATH entry'
        line = 'export PATH=' + shlex.quote(str(current/'bin')) + ':"$PATH"'
        if marker in (old_shell or ''):
            if line not in old_shell: raise ValueError('Existing PATH marker differs; inspect manually')
        else:
            new_shell = (old_shell or '') + '\n' + marker + '\n' + line + '\n'
    overrides = {}
    for value in a.tool:
        name, sep, path = value.partition('=')
        if not sep or name not in KNOWN or not Path(path).is_absolute():
            raise ValueError('Use --tool KNOWN_NAME=/absolute/path')
        if name not in selected_names:
            raise ValueError('Companion tool overrides require --profile full: ' + name)
        overrides[name] = path
    version = (source/'VERSION').read_text().strip()
    h = hashlib.sha256()
    for file in FILES: h.update(file.encode()); h.update((source/file).read_bytes())
    if profile != 'full':
        h.update(('profile=' + profile).encode())
    release_id = version + '-' + h.hexdigest()[:12]
    releases = base/'releases'; releases.mkdir(exist_ok=True)
    release = releases/release_id
    state = prefix/'state/bio-cli'/('install-' + release_id)
    state.mkdir(parents=True, exist_ok=True)
    def managed(value):
        resolved = Path(value).resolve()
        return (resolved.parent == (current/'bin').resolve() or
                (resolved.parent.name == 'bin' and resolved.parent.parent.parent == releases))
    old_config = current/'runtime.json'
    previous_runtime = json.loads(old_config.read_text()) if old_config.is_file() else {}
    if old_config.is_file() and profile == 'core' and previous_runtime.get('_profile', 'full') != 'core':
        raise ValueError('Switching full to core requires a new personal --prefix; existing entries are preserved')
    def previous(name):
        value = previous_runtime.get(name)
        return value if value and not managed(value) and os.access(value, os.X_OK) else None
    def find(name):
        for entry in os.environ.get('PATH', '').split(os.pathsep):
            if not entry: continue
            candidate = Path(entry)/name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                if not managed(candidate): return str(candidate.absolute())
                if previous(name): return previous(name)
        return previous(name)
    runtime = {'_profile': profile}
    for name in selected_names:
        candidate = overrides.get(name)
        if not candidate and name not in ['gdu','dust-du']: candidate = find(name)
        if not candidate and a.tools_dir and (a.tools_dir/name).is_file():
            candidate = str((a.tools_dir/name).absolute())
        if not candidate: candidate = find(name)
        if not candidate:
            if name not in required_names:
                continue
            raise ValueError('Missing dependency before installation: ' + name)
        if managed(candidate): raise ValueError('Managed wrapper is not a dependency: ' + name)
        if not Path(candidate).is_file() or not os.access(candidate, os.X_OK):
            raise ValueError('Not executable: ' + candidate)
        runtime[name] = str(Path(candidate).absolute())
    if release.exists():
        # Incomplete legacy directories cannot be activated. Preserve them for inspection.
        required = FILES + ['runtime.json'] + ['bin/'+n for n in owned_names]
        if any(not (release/f).is_file() for f in required):
            raise ValueError('Incomplete existing release; retained for inspection: ' + str(release))
        if any((release/f).read_bytes() != (source/f).read_bytes() for f in FILES):
            raise ValueError('Existing release source differs; refusing mutation')
        installed = json.loads((release/'runtime.json').read_text())
        if installed.get('_profile', 'full') != profile:
            raise ValueError('Existing release uses a different installation profile')
        for name, value in overrides.items():
            same = name in installed and Path(value).resolve() == Path(installed[name]).resolve()
            if not same and a.tools_dir and name in installed:
                staged_copy = Path(value).parent == a.tools_dir.absolute() and Path(installed[name]) == release/'vendor'/name
                same = staged_copy and Path(value).read_bytes() == Path(installed[name]).read_bytes()
            if not same:
                raise ValueError('Existing release uses a different dependency: ' + name + '; choose a new personal --prefix')
        runtime = installed
        for name, body in wrapper_bodies(runtime, release).items():
            entry = release/'bin'/name
            if not entry.is_file() or entry.read_text() != body or not os.access(entry, os.X_OK):
                raise ValueError('Existing release wrapper differs: ' + name)
    versions = {}
    for name in selected_names:
        if name not in runtime and name not in required_names:
            continue
        if name not in runtime or managed(runtime[name]):
            raise ValueError('Invalid installed dependency: ' + name)
        try:
            result = run_capture([runtime[name], '--version'], timeout=15)
            if result.returncode: raise ValueError('Version probe failed: ' + name)
            versions[name] = {'path': runtime[name], 'version': result.stdout.decode('utf-8','replace').splitlines()[:3]}
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            if name in required_names or name in overrides:
                raise
            versions[name] = {'path': runtime[name], 'status': 'OPTIONAL_ERROR', 'error': str(exc)}
            print('Optional dependency probe failed: ' + name + '; ' + str(exc), file=sys.stderr)
    if not release.exists():
        staging = Path(tempfile.mkdtemp(prefix='.build-'+release_id+'-', dir=str(releases)))
        try:
            for file in FILES:
                dest = staging/file; dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source/file, dest)
            if a.tools_dir:
                for name in selected_names:
                    if name not in runtime:
                        continue
                    if Path(runtime[name]).parent == a.tools_dir.absolute():
                        dest = staging/'vendor'/name; dest.parent.mkdir(exist_ok=True)
                        shutil.copy2(runtime[name], dest)
                        runtime[name] = str(release/'vendor'/name)
            (staging/'runtime.json').write_text(json.dumps(runtime, indent=2)+'\n')
            binpath = staging/'bin'; binpath.mkdir()
            for name, body in wrapper_bodies(runtime, release).items():
                (binpath/name).write_text(body); (binpath/name).chmod(0o755)
            # Syntax and CLI entry are checked before a release can be activated.
            compile((staging/'bio_cli.py').read_text(), 'bio_cli.py', 'exec')
            interpreter = staging/'vendor/python3' if runtime['python3'] == str(release/'vendor/python3') else Path(runtime['python3'])
            subprocess.run([str(interpreter), str(staging/'bio_cli.py'), '--help'],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, check=True, timeout=15)
            staging.rename(release)
        except BaseException:
            print('Build failed; inactive staging retained at ' + str(staging), file=sys.stderr)
            raise
    for name in versions: versions[name]['path'] = runtime[name]
    # Do not rewrite an existing complete release, including its active wrappers.
    previous_target = os.readlink(current) if current.is_symlink() else None
    receipt = state/'installation.json'
    old_receipt = receipt.read_text() if receipt.exists() else None
    record = {'release_id':release_id, 'release':str(release), 'previous':previous_target,
              'profile':profile, 'tools':versions, 'shell_file':str(shell) if shell else None, 'status':'PREPARED'}
    userbin.mkdir(exist_ok=True)
    added = []; shell_changed = False; activated = False
    try:
        for name in owned_names:
            link = userbin/name
            if not (link.exists() or link.is_symlink()):
                link.symlink_to(current/'bin'/name); added.append(link)
        if new_shell is not None:
            if old_shell is not None:
                backup = state/(shell.name + '.backup')
                if not backup.exists(): atomic_text(backup, old_shell, shell_mode)
            atomic_text(shell, new_shell, shell_mode); shell_changed = True
        atomic_text(receipt, json.dumps(record, indent=2)+'\n')
        switch(current, release); activated = True
        record['status'] = 'ACTIVE'
        atomic_text(receipt, json.dumps(record, indent=2)+'\n')
    except BaseException as exc:
        rollback_errors = []
        def restore(action):
            try: action()
            except BaseException as err: rollback_errors.append(str(err))
        if activated:
            if previous_target is None: restore(lambda: current.unlink())
            else: restore(lambda: switch(current, previous_target))
        if shell_changed:
            if old_shell is None: restore(lambda: shell.unlink())
            else: restore(lambda: atomic_text(shell, old_shell, shell_mode))
        for link in added: restore(lambda link=link: link.unlink())
        if old_receipt is not None: restore(lambda: atomic_text(receipt, old_receipt))
        elif receipt.exists(): restore(lambda: receipt.unlink())
        failure = {'status':'ROLLBACK_FAILED' if rollback_errors else 'ROLLED_BACK',
                   'error':str(exc), 'rollback_errors':rollback_errors, 'release_id':release_id}
        fd, name = tempfile.mkstemp(prefix='failed-', suffix='.json', dir=str(state))
        with os.fdopen(fd,'w') as out: json.dump(failure,out,indent=2)
        print('Installation failed; state: '+failure['status']+'; receipt: '+name, file=sys.stderr)
        raise
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, default=Path.home()/'.local')
    parser.add_argument('--profile', choices=PROFILES, default='full',
                        help='full: 完整工具组合（默认）；core: 六项基础依赖，生信后端可选')
    parser.add_argument('--tools-dir', type=Path)
    parser.add_argument('--tool', action='append', default=[], help='NAME=/absolute/path')
    parser.add_argument('--shell-file', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(install(args), indent=2))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print('install: '+str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
