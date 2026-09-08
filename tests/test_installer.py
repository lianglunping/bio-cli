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
            for f in ['bio_cli.py','VERSION','README.md','tools.lock.json','scripts/install.py','scripts/fetch_tools.py','tests/test_cli.py','tests/test_installer.py']:
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
            run();self.assertEqual(shell.read_text().count('# bio-cli: managed PATH entry'),1)
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

if __name__=='__main__':unittest.main(verbosity=2)
