"""Synthetic-only behavioral acceptance tests; no research data required."""
import bz2
import argparse
import contextlib
import gzip
import importlib.util
import hashlib
import io
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'bio_cli.py'

class Acceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='bio-cli-test-')
        self.p = Path(self.temp.name)
        self.text = b'##synthetic fixture\nchrSynthetic\t1\tACGT\n'
    def tearDown(self): self.temp.cleanup()
    def runcli(self, *args, ok=True):
        p = subprocess.run([sys.executable, str(CLI)] + list(map(str,args)), capture_output=True)
        if ok: self.assertEqual(p.returncode, 0, p.stderr.decode())
        else: self.assertNotEqual(p.returncode, 0)
        return p
    def put(self,name,data=None):
        f=self.p/name; f.write_bytes(self.text if data is None else data); return f
    def test_help_and_command_routing(self):
        for name in ['peek','packz','unpackz']:
            text=self.runcli(name,'--help').stdout.decode()
            self.assertTrue(text.startswith('usage: '+name+' '))
            self.assertNotIn('{peek,packz,unpackz}',text)
            self.assertIn('示例',text)
            self.assertIn(b'bio-cli ',self.runcli(name,'--version').stdout)
        self.assertIn(b'peek',self.runcli('--help').stdout)
        self.runcli('unknown',ok=False)
        source=self.put('-synthetic.fa')
        self.assertEqual(self.runcli('peek','--',source).stdout,self.text)
    def test_text_formats_and_magic_compression(self):
        for name in ['synthetic.fa','synthetic.fastq','synthetic.gff3','synthetic.gtf','synthetic.bed','synthetic.vcf','synthetic.g.vcf','synthetic.fai','synthetic.dict','synthetic.tsv','synthetic.ann','synthetic.amb']:
            for suffix, encode in [('',lambda x:x),('.gz',gzip.compress),('.bz2',bz2.compress),('.xz',lzma.compress)]:
                f=self.put(name+suffix,encode(self.text))
                self.assertEqual(self.runcli('peek',f).stdout,self.text)
    def test_space_unicode_dash_and_limits(self):
        f=self.put('- 合成.fa',b'>synthetic\n'+b'A'*2000000+b'\n')
        r=self.runcli('peek','-n','1',f);self.assertEqual(r.stdout,b'>synthetic\n')
        r=self.runcli('peek','--max-bytes','128',f)
        self.assertEqual(len(r.stdout),128)
        self.assertIn(b'limit',r.stderr)
    def test_binary_index_metadata(self):
        for suffix in ['.0123','.bwt.2bit.64','.pac','.bai','.csi','.tbi','.h5ad','.rds']:
            r=self.runcli('peek',self.put('synthetic'+suffix,b'\x00\xff\x01'))
            self.assertIn(b'Metadata only',r.stdout); self.assertNotIn(b'\xff',r.stdout)
    def test_terminal_escape(self):
        r=self.runcli('peek',self.put('synthetic.txt',b'hello\x1b[2J\n'))
        self.assertNotIn(b'\x1b',r.stdout)
    def test_control_escape_preserves_unicode_and_whitespace(self):
        data='水稻\tACGT\n\r\x1b\x7f\u0085\u009f\u00a0'.encode()+b'\xff'
        expected='水稻\tACGT\n\\x0d\\x1b\\x7f\\x85\\x9f\u00a0\ufffd'.encode()
        self.assertEqual(self.runcli('peek',self.put('synthetic-controls.txt',data)).stdout,expected)
    def test_metadata_and_error_filename_escape(self):
        for suffix in ['.bai', '.h5ad']:
            r=self.runcli('peek',self.put('synthetic-\x1b[2J'+suffix,b'\x00'))
            self.assertNotIn(b'\x1b',r.stdout)
            self.assertIn(b'\\x1b',r.stdout)
        r=self.runcli('peek',self.p/'missing-\x1b[2J.txt',ok=False)
        self.assertNotIn(b'\x1b',r.stderr)
        self.assertIn(b'\\x1b',r.stderr)
    def test_tar_preview_stops_before_large_payload(self):
        spec=importlib.util.spec_from_file_location('preview_module',CLI)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        archive=self.p/'synthetic.tar'
        with tarfile.open(archive,'w') as tf:
            info=tarfile.TarInfo('large.fa');info.size=8*1024*1024
            tf.addfile(info,io.BytesIO(b'A'*info.size))
            tf.addfile(tarfile.TarInfo('second.txt'),io.BytesIO())
        count=[0]
        class Counted:
            def __init__(self,stream):self.stream=stream
            def read(self,n=-1):
                data=self.stream.read(n);count[0]+=len(data);return data
            def __getattr__(self,name):return getattr(self.stream,name)
        original=module.reader
        @contextlib.contextmanager
        def counted(*args,**kwargs):
            with original(*args,**kwargs) as r:
                r.stream=Counted(r.stream);yield r
        module.reader=counted
        output=io.StringIO();errors=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(errors):
            module.peek(argparse.Namespace(input=archive,lines=1,max_bytes=1024,no_pager=True))
        self.assertEqual(output.getvalue(),'8388608\tlarge.fa\n')
        self.assertLess(count[0],65536)
        self.assertIn('limit reached',errors.getvalue())
    def test_missing_bad_and_truncated(self):
        self.runcli('peek',self.p/'missing.gz',ok=False)
        bad=self.put('broken.gz',gzip.compress(self.text)[:-5])
        self.runcli('peek',bad,ok=False)
    def test_early_stop_not_error(self):
        f=self.put('large.gz',gzip.compress(b'x\n'*200000))
        self.assertEqual(self.runcli('peek','-n','10',f).stdout,b'x\n'*10)
    def test_zip_and_tar_listing(self):
        z=self.p/'synthetic.zip'
        with zipfile.ZipFile(z,'w') as a:a.writestr('synthetic/a.txt',self.text)
        self.assertIn(b'synthetic/a.txt',self.runcli('peek',z).stdout)
        for suffix,mode in [('.tar','w'),('.tar.gz','w:gz'),('.tar.bz2','w:bz2'),('.tar.xz','w:xz')]:
            f=self.p/('synthetic'+suffix)
            with tarfile.open(f,mode) as a:
                i=tarfile.TarInfo('synthetic/a.txt');i.size=len(self.text);a.addfile(i,io.BytesIO(self.text))
            self.assertIn(b'synthetic/a.txt',self.runcli('peek',f).stdout)
    def test_roundtrip_file_zstd_gzip_bgzip(self):
        for fmt in ['zstd','gzip','bgzip']:
            f=self.put('synthetic-'+fmt+'.txt')
            r=self.runcli('packz','--format',fmt,f)
            packed=Path(r.stdout.decode().strip())
            self.assertTrue(f.exists())
            self.assertEqual(self.runcli('peek',packed).stdout,self.text)
            out=self.p/('restored-'+fmt+'.txt')
            self.runcli('unpackz','-o',out,packed)
            self.assertEqual(hashlib.sha256(out.read_bytes()).digest(),hashlib.sha256(f.read_bytes()).digest())
            self.runcli('packz','--format',fmt,f,ok=False)
            self.runcli('unpackz','-o',out,packed,ok=False)
    def test_directory_roundtrip(self):
        d=self.p/'synthetic project';d.mkdir();(d/'empty').mkdir()
        (d/'text.txt').write_bytes(self.text);(d/'run.sh').write_text('#!/bin/sh\nexit 0\n');(d/'run.sh').chmod(0o755)
        (d/'link').symlink_to('text.txt');os.link(d/'text.txt',d/'hardlink')
        self.runcli('packz',d)
        archive=Path(str(d)+'.tar.zst')
        self.assertIn(b'text.txt',self.runcli('peek',archive).stdout)
        dest=self.p/'restore'
        self.runcli('unpackz',archive,'-C',dest)
        restored=dest/d.name
        self.assertEqual((restored/'text.txt').read_bytes(),self.text)
        self.assertTrue((restored/'link').is_symlink())
        self.assertEqual((restored/'text.txt').stat().st_ino,(restored/'hardlink').stat().st_ino)
        self.assertEqual((restored/'run.sh').stat().st_mode & 0o777,0o755)
        self.runcli('unpackz',archive,'-C',dest,ok=False)
        self.runcli('packz',d,'-o',d/'nested.tar.zst',ok=False)
    def test_archive_traversal_rejected(self):
        f=self.p/'evil.tar'
        with tarfile.open(f,'w') as a:
            i=tarfile.TarInfo('../outside.txt');i.size=1;a.addfile(i,io.BytesIO(b'x'))
        self.runcli('unpackz',f,'-C',self.p/'restore',ok=False)
        self.assertFalse((self.p/'outside.txt').exists())
    def test_escaping_symlink_rejected(self):
        f=self.p/'evil-link.tar'
        with tarfile.open(f,'w') as a:
            i=tarfile.TarInfo('link');i.type=tarfile.SYMTYPE;i.linkname='../outside';a.addfile(i)
        self.runcli('unpackz',f,'-C',self.p/'restore',ok=False)
        self.assertFalse((self.p/'outside').exists())
    def test_bad_compression_does_not_publish(self):
        bad=self.put('broken.gz',gzip.compress(self.text)[:-4]);out=self.p/'out.txt'
        self.runcli('unpackz',bad,'-o',out,ok=False)
        self.assertFalse(out.exists())
    def test_bam_bcf_cram(self):
        sam=self.put('synthetic.sam',b'@HD\tVN:1.6\tSO:coordinate\n@SQ\tSN:chrSynthetic\tLN:100\nreadSynthetic\t0\tchrSynthetic\t1\t60\t4M\t*\t0\t0\tACGT\tIIII\n')
        ref=self.put('synthetic.fa',b'>chrSynthetic\n'+b'ACGT'*25+b'\n')
        subprocess.run(['samtools','faidx',str(ref)],check=True)
        bam=self.p/'synthetic.bam';cram=self.p/'synthetic.cram'
        subprocess.run(['samtools','view','-b','-o',str(bam),str(sam)],check=True)
        subprocess.run(['samtools','view','-C','-T',str(ref),'-o',str(cram),str(bam)],check=True)
        self.assertIn(b'readSynthetic',self.runcli('peek',bam).stdout)
        self.assertNotIn(b'readSynthetic',self.runcli('peek','--header',bam).stdout)
        self.assertIn(b'@SQ',self.runcli('peek','--header',cram).stdout)
        self.runcli('peek',cram,ok=False)
        self.assertIn(b'readSynthetic',self.runcli('peek','--reference',ref,cram).stdout)
        vcf=self.put('synthetic.vcf',b'##fileformat=VCFv4.2\n##contig=<ID=chrSynthetic,length=100>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\nchrSynthetic\t1\t.\tA\tC\t.\tPASS\t.\n')
        bcf=self.p/'synthetic.bcf'
        subprocess.run(['bcftools','view','-Ob','-o',str(bcf),str(vcf)],check=True)
        self.assertIn(b'chrSynthetic\t1',self.runcli('peek',bcf).stdout)
        self.assertIn(b'#CHROM',self.runcli('peek','--header',bcf).stdout)
        self.assertFalse(Path(str(bam)+'.bai').exists())

if __name__=='__main__':unittest.main(verbosity=2)
