"""Installer regression tests use isolated synthetic command stubs only."""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('source_installer',ROOT/'scripts/install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class InstallerRegression(unittest.TestCase):
    def test_open_stdin_and_upgrade_are_safe(self):
        with tempfile.TemporaryDirectory(prefix='bio-cli-install-test-') as tmp:
            p=Path(tmp);source=p/'source';source.mkdir()
            for f in installer.FILES:
                dest=source/f;dest.parent.mkdir(exist_ok=True,parents=True);shutil.copy2(ROOT/f,dest)
            fake=p/'upstream';fake.mkdir()
            names=['tar','gzip','bzip2','xz','zstd','samtools','bcftools','bgzip','gdu','dust-du','dua','bat','rg','fd','eza']
            for n in names:
                script=fake/n
                # stdin stays OPEN in the parent; probes must explicitly detach it.
                script.write_text('#!/bin/sh\n/bin/cat >/dev/null\nprintf "synthetic tool 1.0\\n"\n');script.chmod(0o755)
            prefix=p/'prefix';shell=p/'shellrc'
            env=os.environ.copy();env['PATH']=str(fake)+os.pathsep+'/usr/bin:/bin'
            command=[sys.executable,str(source/'scripts/install.py'),'--prefix',str(prefix),'--tools-dir',str(fake),'--tool','python3='+sys.executable,'--shell-file',str(shell)]
            def run():
                proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.communicate();self.fail('Version probe waited on inherited stdin')
                out,err=proc.communicate();self.assertEqual(proc.returncode,0,err.decode());return json.loads(out)
            first=run()
            help_output=subprocess.check_output([str(prefix/'bin/peek'),'--help'],env=env,timeout=5).decode()
            self.assertTrue(help_output.startswith('usage: peek '))
            self.assertIn('peek annotation.gff3.gz',help_output)
            self.assertNotIn('{peek,packz,unpackz}',help_output)
            first_runtime=json.loads((Path(first['release'])/'runtime.json').read_text())
            self.assertEqual(first['tools']['zstd']['path'],first_runtime['zstd'])
            env['PATH']=str(prefix/'share/bio-cli/current/bin')+os.pathsep+str(prefix/'bin')+os.pathsep+env['PATH']
            # Upgrade without staging: prefix/bin/dust-du must resolve to its real dependency.
            pos=command.index('--tools-dir');del command[pos:pos+2]
            (source/'VERSION').write_text('0.0.99\n')
            second=run();self.assertNotEqual(first['release_id'],second['release_id'])
            # The displayed version must follow the installed VERSION, including upgrades.
            for name in ['bio-cli','peek','packz','unpackz']:
                output=subprocess.check_output([str(prefix/'bin'/name),'--version'],env=env,timeout=5)
                self.assertEqual(output,b'bio-cli 0.0.99\n')
            # Split documentation must survive personal-prefix installation.
            for file in ['README.md','CHANGELOG.md'] + [f for f in installer.FILES if f.startswith('docs/')]:
                self.assertEqual((Path(second['release'])/file).read_bytes(),(source/file).read_bytes())
            runtime=json.loads((Path(second['release'])/'runtime.json').read_text())
            self.assertFalse(any('current/bin' in value for value in runtime.values()))
            self.assertNotEqual(runtime['dust-du'],str(prefix/'bin/dust-du'))
            for name in ['zstd','dust-du']:
                r=subprocess.run([str(prefix/'share/bio-cli/current/bin'/name),'--version'],input=b'',capture_output=True,timeout=3)
                self.assertEqual(r.returncode,0)
            self.assertEqual(shell.read_text().count('# bio-cli: managed PATH entry'),1)
            entry=prefix/'share/bio-cli/current/bin/peek'
            before=entry.stat().st_mtime_ns
            run();self.assertEqual(shell.read_text().count('# bio-cli: managed PATH entry'),1)
            self.assertEqual(entry.stat().st_mtime_ns,before)
            overview=subprocess.check_output([str(prefix/'bin/bio-cli'),'tools'],env=env,timeout=5)
            self.assertIn(b'rg',overview)
            # Conflicting configuration must fail before changing an installed release.
            replacement=p/'replacement-zstd'
            replacement.write_text('#!/bin/sh\nprintf "replacement tool\\n"\n');replacement.chmod(0o755)
            current=prefix/'share/bio-cli/current'
            original_target=os.readlink(current)
            original_config=(current/'runtime.json').read_bytes()
            rejected=subprocess.run(command+['--tool','zstd='+str(replacement)],env=env,input=b'',capture_output=True,timeout=10)
            self.assertNotEqual(rejected.returncode,0)
            self.assertIn(b'Existing release uses a different dependency',rejected.stderr)
            self.assertEqual(os.readlink(current),original_target)
            self.assertEqual((current/'runtime.json').read_bytes(),original_config)
            receipt=json.loads((prefix/'state/bio-cli'/('install-'+second['release_id'])/'installation.json').read_text())
            self.assertEqual(receipt['tools']['zstd']['path'],runtime['zstd'])
            rejected=subprocess.run(command+['--tool','dust-du='+str(prefix/'bin/dust-du')],env=env,input=b'',capture_output=True,timeout=10)
            self.assertNotEqual(rejected.returncode,0)
            self.assertIn(b'Managed wrapper is not a dependency',rejected.stderr)
            self.assertEqual(os.readlink(current),original_target)

            # Reuse must detect altered installed wrappers instead of reporting success.
            altered=current/'bin/peek'
            original_body=altered.read_bytes()
            altered.write_text('#!/bin/sh\nexit 0\n')
            rejected=subprocess.run(command,env=env,input=b'',capture_output=True,timeout=10)
            self.assertNotEqual(rejected.returncode,0)
            self.assertIn(b'Existing release wrapper differs',rejected.stderr)
            self.assertEqual(os.readlink(current),original_target)
            altered.write_bytes(original_body)

class InstallerTransactions(unittest.TestCase):
    def test_portable_lock_is_exclusive_and_released(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('lock_installer',ROOT/'scripts/install.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix='bio-cli-lock-test-') as tmp:
            base=Path(tmp)
            with module.install_lock(base):
                owner=json.loads((base/'install.lock.d/owner.json').read_text())
                self.assertEqual(owner['pid'],os.getpid())
                with self.assertRaises(ValueError):
                    with module.install_lock(base):pass
                self.assertTrue((base/'install.lock.d/owner.json').is_file())
            self.assertFalse((base/'install.lock.d').exists())
            with self.assertRaises(RuntimeError):
                with module.install_lock(base):raise RuntimeError('synthetic failure')
            self.assertFalse((base/'install.lock.d').exists())
            (base/'install.lock.d').mkdir()
            with self.assertRaises(ValueError):
                with module.install_lock(base):pass
            self.assertTrue((base/'install.lock.d').is_dir())

    def test_build_failure_retry_and_activation_rollback(self):
        import argparse
        import importlib.util
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='bio-cli-transaction-') as tmp:
            p=Path(tmp);source=p/'source';source.mkdir()
            files=installer.FILES
            for file in files:
                dest=source/file;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/file,dest)
            fake=p/'fake';fake.mkdir()
            names=['tar','gzip','bzip2','xz','zstd','samtools','bcftools','bgzip','gdu','dust-du','dua','bat','rg','fd','eza']
            for name in names:
                f=fake/name;f.write_text('#!/bin/sh\nprintf "synthetic version 1.0\\n"\n');f.chmod(0o755)
            spec=importlib.util.spec_from_file_location('synthetic_installer',source/'scripts/install.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            prefix=p/'prefix';shell=p/'shellrc'
            shell.write_text('# original\n')
            a=argparse.Namespace(prefix=prefix,tools_dir=fake,tool=['python3='+sys.executable]+[n+'='+str(fake/n) for n in names],shell_file=shell)
            first=module.install(a)
            current=prefix/'share/bio-cli/current';old_target=os.readlink(current)
            old_shell=shell.read_bytes()
            (source/'VERSION').write_text('0.0.98\n')
            original_copy=module.shutil.copy2
            def fail_copy(src,dst,*args,**kwargs):
                if Path(src).name=='VERSION':raise OSError('synthetic copy failure')
                return original_copy(src,dst,*args,**kwargs)
            with patch.object(module.shutil,'copy2',side_effect=fail_copy):
                with self.assertRaises(OSError):module.install(a)
            self.assertEqual(os.readlink(current),old_target)
            second=module.install(a)
            self.assertNotEqual(second['release'],first['release'])
            old_target=os.readlink(current)
            (source/'VERSION').write_text('0.0.97\n')
            original_atomic=module.atomic_text;failed=[False]
            def fail_receipt(path,text,*args,**kwargs):
                if path.name=='installation.json' and '"status": "ACTIVE"' in text and not failed[0]:
                    failed[0]=True;raise OSError('synthetic receipt failure')
                return original_atomic(path,text,*args,**kwargs)
            with patch.object(module,'atomic_text',side_effect=fail_receipt):
                with self.assertRaises(OSError):module.install(a)
            self.assertEqual(os.readlink(current),old_target)
            self.assertEqual(shell.read_bytes(),old_shell)
            failures=list((prefix/'state/bio-cli').glob('*/failed-*.json'))
            self.assertEqual(json.loads(failures[0].read_text())['status'],'ROLLED_BACK')
            self.assertEqual(module.install(a)['status'],'ACTIVE')
            # A bad Shell target fails before activation in a new prefix.
            a.prefix=p/'new-prefix';a.shell_file=p/'missing-parent/shellrc'
            with self.assertRaises(ValueError):module.install(a)
            self.assertFalse((a.prefix/'share/bio-cli/current').exists())

class CoreProfileAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='bio-cli-core-')
        self.root = Path(self.temp.name)
        self.source = self.root/'source'
        for file in installer.FILES:
            target = self.source/file
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/file, target)
        self.fake = self.root/'upstream'
        self.fake.mkdir()
        self.names = ['tar', 'gzip', 'bzip2', 'xz', 'zstd']
        for name in self.names:
            self.add_tool(name)
        self.prefix = self.root/'prefix'
        self.shell = self.root/'shellrc'
        self.shell.write_text('# synthetic original\n')
        # Only selected synthetic commands are discoverable; no host samtools,
        # companion binaries, or accidental system dependencies can satisfy this.
        self.env = dict(os.environ, PATH=str(self.fake))

    def tearDown(self):
        self.temp.cleanup()

    def add_tool(self, name, exit_code=0):
        target = self.fake/name
        target.write_text('#!/bin/sh\nprintf "synthetic '+name+' version 1.0\\n"\nexit '+str(exit_code)+'\n')
        target.chmod(0o755)
        return target

    def install(self, profile=None, ok=True, extra=()):
        command = [sys.executable, str(self.source/'scripts/install.py'),
                   '--prefix', str(self.prefix), '--shell-file', str(self.shell),
                   '--tool', 'python3='+sys.executable]
        if profile is not None:
            command += ['--profile', profile]
        result = subprocess.run(command+list(extra), env=self.env, capture_output=True, timeout=15)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b'Traceback', result.stderr)
        return result

    def command(self, *args, ok=True):
        result = subprocess.run([str(self.prefix/'bin/bio-cli')]+list(map(str,args)),
                                env=self.env, capture_output=True, timeout=15)
        if ok: self.assertEqual(result.returncode, 0, result.stderr.decode())
        else: self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b'Traceback', result.stderr)
        return result

    def test_core_without_optional_tools_and_profile_diagnostics(self):
        record = self.install('core')
        self.assertEqual(record['profile'], 'core')
        self.assertEqual(set(record['tools']), set(['python3']+self.names))
        release = Path(record['release'])
        runtime = json.loads((release/'runtime.json').read_text())
        self.assertEqual(runtime['_profile'], 'core')
        self.assertEqual(set(p.name for p in (release/'bin').iterdir()),
                         {'bio-cli', 'peek', 'packz', 'unpackz', 'zstd'})
        self.assertFalse((self.prefix/'bin/dust-du').is_symlink())
        source = self.root/'synthetic.txt'
        source.write_text('synthetic rice\n')
        self.assertEqual(self.command('peek', source).stdout, b'synthetic rice\n')
        bam = self.root/'synthetic.bam';bam.write_bytes(b'synthetic')
        self.assertIn(b'Missing dependency: samtools', self.command('peek', bam, ok=False).stderr)
        report = json.loads(self.command('doctor', '--json').stdout)
        self.assertEqual(report['profile'], 'core')
        self.assertEqual(sum(row['required'] for row in report['checks']), 6)
        self.assertTrue(all(row['status']=='OK' for row in report['checks'] if row['required']))
        self.assertTrue(all(row['status']=='OPTIONAL_MISSING' for row in report['checks'] if not row['required']))
        # Checking full requirements explicitly still reports failure.
        self.command('doctor', '--profile', 'full', '--json', ok=False)
        entry = release/'bin/peek';before = entry.stat().st_mtime_ns
        self.assertEqual(self.install('core')['release_id'], record['release_id'])
        self.assertEqual(entry.stat().st_mtime_ns, before)
        # Missing optional backends can be added to PATH without reinstallation.
        self.add_tool('samtools')
        report = json.loads(self.command('doctor', '--json').stdout)
        self.assertEqual(next(row for row in report['checks'] if row['tool']=='samtools')['status'], 'OK')
        # A failed optional backend is reported, but required tools still pass.
        self.add_tool('samtools', 7)
        report = json.loads(self.command('doctor', '--json').stdout)
        self.assertEqual(next(row for row in report['checks'] if row['tool']=='samtools')['status'], 'OPTIONAL_ERROR')
        self.add_tool('zstd', 7)
        report = json.loads(self.command('doctor', '--json', ok=False).stdout)
        self.assertEqual(next(row for row in report['checks'] if row['tool']=='zstd')['status'], 'ERROR')

    def test_full_default_and_core_to_full_upgrade(self):
        shell = self.shell.read_bytes()
        rejected = self.install(ok=False)
        self.assertIn(b'Missing dependency before installation: samtools', rejected.stderr)
        self.assertFalse((self.prefix/'share/bio-cli/current').exists())
        self.assertEqual(self.shell.read_bytes(), shell)
        core = self.install('core')
        for name in ['samtools','bcftools','bgzip','gdu','dust-du','dua','bat','rg','fd','eza']:
            self.add_tool(name)
        full = self.install()
        self.assertEqual(full['profile'], 'full')
        self.assertNotEqual(core['release_id'], full['release_id'])
        self.assertEqual(full['previous'], core['release'])
        self.assertEqual(len(full['tools']), 16)
        self.assertTrue((self.prefix/'bin/dust-du').is_symlink())
        self.assertEqual(self.shell.read_text().count('# bio-cli: managed PATH entry'), 1)
        report = json.loads(self.command('doctor','--json').stdout)
        self.assertEqual(report['profile'], 'full')
        self.assertTrue(all(row['required'] and row['status']=='OK' for row in report['checks']))
        old_target = os.readlink(self.prefix/'share/bio-cli/current')
        self.assertIn(b'new personal --prefix', self.install('core',ok=False).stderr)
        self.assertEqual(os.readlink(self.prefix/'share/bio-cli/current'), old_target)
        self.assertEqual(self.install()['release_id'], full['release_id'])
        # Releases from before profiles had no metadata key and remain full.
        config = Path(full['release'])/'runtime.json'
        legacy = json.loads(config.read_text());legacy.pop('_profile')
        config.write_text(json.dumps(legacy))
        self.assertEqual(json.loads(self.command('doctor','--json').stdout)['profile'], 'full')
        self.assertEqual(self.install()['release_id'], full['release_id'])

    def test_native_core_compression_and_directory_restore(self):
        tools = {name: shutil.which(name) for name in installer.KNOWN[:6]}
        tools['python3'] = sys.executable
        self.assertTrue(all(tools.values()), 'Native core dependencies are required for acceptance')
        self.install('core', extra=[part for name,path in tools.items() for part in ['--tool',name+'='+path]])
        source = self.root/'synthetic.tsv';source.write_bytes(b'chrSynthetic\t1\tACGT\n')
        self.command('packz', source)
        self.command('unpackz', str(source)+'.zst', '-o', self.root/'restored.tsv')
        self.assertEqual((self.root/'restored.tsv').read_bytes(), source.read_bytes())
        self.command('packz', '--format', 'gzip', source)
        self.assertEqual(self.command('peek', str(source)+'.gz').stdout, source.read_bytes())
        directory = self.root/'project';directory.mkdir()
        (directory/'data.tsv').write_bytes(source.read_bytes())
        self.command('packz', directory)
        self.command('unpackz', str(directory)+'.tar.zst', '-C', self.root/'restored')
        self.assertEqual((self.root/'restored/project/data.tsv').read_bytes(), source.read_bytes())
        self.assertTrue(source.exists())
        self.assertTrue((directory/'data.tsv').exists())
        self.assertFalse((self.root/'restored.bio-cli-incomplete').exists())

    def test_optional_probe_and_override_validation(self):
        self.add_tool('samtools', 7)
        record = self.install('core')
        self.assertEqual(record['tools']['samtools']['status'], 'OPTIONAL_ERROR')
        self.assertEqual(self.command('doctor','--json').returncode, 0)
        current = self.prefix/'share/bio-cli/current';old_target = os.readlink(current)
        self.assertIn(b'Not executable', self.install('core',ok=False,
                      extra=['--tool','samtools='+str(self.root/'missing')]).stderr)
        self.assertEqual(os.readlink(current), old_target)
        self.assertIn(b'require --profile full', self.install('core',ok=False,
                      extra=['--tool','rg='+str(self.add_tool('rg'))]).stderr)
        # Explicit bad overrides must never be silently treated as optional.
        self.assertIn(b'Version probe failed', self.install('core',ok=False,
                      extra=['--tool','samtools='+str(self.fake/'samtools')]).stderr)
        self.assertEqual(os.readlink(current), old_target)

    def test_core_upgrade_activation_failure_restores_entries(self):
        import argparse
        from unittest.mock import patch
        core = self.install('core')
        for name in ['samtools','bcftools','bgzip','gdu','dust-du','dua','bat','rg','fd','eza']:
            self.add_tool(name)
        spec = importlib.util.spec_from_file_location('profile_rollback_installer', self.source/'scripts/install.py')
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        args = argparse.Namespace(prefix=self.prefix, shell_file=self.shell, profile='full',
                                  tools_dir=None, tool=['python3='+sys.executable]+[name+'='+str(self.fake/name) for name in installer.KNOWN if name!='python3'])
        original = module.atomic_text
        def fail_receipt(path, text, *args, **kwargs):
            if path.name=='installation.json' and '"status": "ACTIVE"' in text:
                raise OSError('synthetic core-to-full activation failure')
            return original(path,text,*args,**kwargs)
        with patch.object(module,'atomic_text',side_effect=fail_receipt):
            with self.assertRaises(OSError):module.install(args)
        self.assertEqual(os.readlink(self.prefix/'share/bio-cli/current'), core['release'])
        self.assertFalse((self.prefix/'bin/dust-du').is_symlink())
        self.assertTrue((self.prefix/'bin/peek').is_file())
        self.assertEqual(json.loads(self.command('doctor','--json').stdout)['profile'], 'core')

if __name__=='__main__':unittest.main(verbosity=2)
