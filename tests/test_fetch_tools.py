"""Offline source archives and injected I/O faults; never download in tests."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fetch_tools', ROOT/'scripts/fetch_tools.py')
fetcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(fetcher)


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='bio-fetch-test-')
        self.root = Path(self.temp.name)
        self.payload = b'#!/bin/sh\nprintf "synthetic version\\n"\n'
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            entry = tarfile.TarInfo('package/tool'); entry.size = len(self.payload)
            archive.addfile(entry, io.BytesIO(self.payload))
        self.archive = stream.getvalue()
        self.item = dict(asset='asset.tar.gz', command='tool', member='tool',
                         sha256=hashlib.sha256(self.archive).hexdigest(), release='synthetic', url='https://example.invalid/asset')
    def tearDown(self):
        self.temp.cleanup()
    def opener(self, *args, **kwargs):
        return io.BytesIO(self.archive)
    def fetch(self):
        return fetcher.fetch(self.item, self.root, self.opener)

    def test_roundtrip_reuse_is_immutable(self):
        first = self.fetch()
        binary = self.root/'bin/tool'; before = binary.stat()
        self.assertEqual(binary.read_bytes(), self.payload)
        self.assertEqual(self.fetch(), first)
        after = binary.stat()
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
        self.assertEqual(list((self.root/'bin').glob('*.partial-*')), [])

    def test_dangling_symlink_refused_without_touching_target(self):
        (self.root/'bin').mkdir(); outside = self.root/'unrelated'
        (self.root/'bin/tool').symlink_to(outside)
        with self.assertRaises(ValueError): self.fetch()
        self.assertFalse(outside.exists())
        (self.root/'bin/tool').unlink()
        (self.root/'asset.tar.gz').symlink_to(outside)
        with self.assertRaises(ValueError): self.fetch()
        self.assertFalse(outside.exists())

    def test_different_existing_binary_is_unchanged(self):
        (self.root/'bin').mkdir(); binary = self.root/'bin/tool'; binary.write_bytes(b'original')
        with self.assertRaises(ValueError): self.fetch()
        self.assertEqual(binary.read_bytes(), b'original')

    def test_partial_download_failure_then_retry(self):
        class Broken(io.BytesIO):
            def read(self, n=-1):
                if self.tell(): raise OSError('synthetic transport failure')
                return super().read(10)
        with self.assertRaises(OSError):
            fetcher.fetch(self.item, self.root, lambda *a, **k: Broken(self.archive))
        self.assertFalse((self.root/'asset.tar.gz').exists())
        self.assertEqual(len(list(self.root.glob('*.download-*'))), 1)
        self.fetch()
        self.assertEqual((self.root/'bin/tool').read_bytes(), self.payload)

    def test_binary_write_failure_does_not_publish(self):
        (self.root/'asset.tar.gz').write_bytes(self.archive)
        def fail(source, dest):
            dest.write(b'partial'); raise OSError('synthetic write failure')
        with patch.object(fetcher, 'copy_hashed', side_effect=fail):
            with self.assertRaises(OSError): self.fetch()
        self.assertFalse((self.root/'bin/tool').exists())
        self.fetch()
        self.assertEqual((self.root/'bin/tool').read_bytes(), self.payload)

    def test_digest_mismatch_never_publishes(self):
        self.item['sha256'] = '0'*64
        with self.assertRaises(ValueError): self.fetch()
        self.assertFalse((self.root/'asset.tar.gz').exists())
        self.assertFalse((self.root/'bin/tool').exists())

    def test_two_fetches_publish_only_identical_results(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.fetch(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual((self.root/'bin/tool').read_bytes(), self.payload)
        self.assertEqual(list((self.root/'bin').glob('*.partial-*')), [])
