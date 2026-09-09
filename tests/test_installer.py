"""Installer regression tests use isolated synthetic command stubs only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class InstallerRegression(unittest.TestCase):
    def test_open_stdin_and_upgrade_are_safe(self):
        with tempfile.TemporaryDirectory(prefix='bio-cli-install-test-') as tmp:
            p=Path(tmp);source=p/'source';source.mkdir()
            for f in ['bio_runtime.py','tests/test_runtime.py','tests/test_fetch_tools.py','bio_cli.py','VERSION','README.md','tools.lock.json','scripts/install.py','scripts/fetch_tools.py','tests/test_cli.py','tests/test_installer.py']:
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
            files=['bio_runtime.py','tests/test_runtime.py','tests/test_fetch_tools.py','bio_cli.py','VERSION','README.md','tools.lock.json','scripts/install.py','scripts/fetch_tools.py','tests/test_cli.py','tests/test_installer.py']
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

if __name__=='__main__':unittest.main(verbosity=2)
