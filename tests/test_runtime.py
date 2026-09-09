"""Real isolated subprocesses: bounds, cancellation and lifecycle regressions."""
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bio_runtime import ManagedProcess, run_capture


class RuntimeTests(unittest.TestCase):
    def test_zombie_group_permission_race(self):
        process = ManagedProcess([sys.executable, '-c', 'pass'], capture_stdout=True)
        process.proc.wait(timeout=5)
        with patch('bio_runtime.os.killpg', side_effect=[PermissionError(), ProcessLookupError()]) as kill:
            process._signal(signal.SIGTERM)
            self.assertEqual(kill.call_count, 2)
        with patch('bio_runtime.os.killpg', side_effect=PermissionError()):
            with self.assertRaises(PermissionError):
                process._signal(signal.SIGTERM)
        process.finish()

    def test_output_bounds_and_exit_status(self):
        result = run_capture([sys.executable, '-c',
            'import sys;sys.stdout.write("x"*2000000);sys.stderr.write("y"*2000000);sys.exit(7)'],
            limit=2048)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, b'x'*2048+b'y'*2048)
        self.assertEqual(result.stderr, b'y'*2048)

    def test_deadline_reaps_backend(self):
        started = time.monotonic()
        process = ManagedProcess([sys.executable, '-c',
            'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)'],
            timeout=1, capture_stdout=True)
        with self.assertRaises(TimeoutError):
            process.finish()
        self.assertIsNotNone(process.proc.poll())
        self.assertFalse(process.errors.thread.is_alive())
        self.assertFalse(process.output.thread.is_alive())
        self.assertLess(time.monotonic()-started, 8)

    def test_interrupt_reaps_backend(self):
        process = ManagedProcess([sys.executable, '-c', 'import time;time.sleep(30)'], capture_stdout=True)
        original = process.proc.wait
        count = [0]
        def interrupted(*args, **kwargs):
            count[0] += 1
            if count[0] == 1:
                raise KeyboardInterrupt()
            return original(*args, **kwargs)
        with patch.object(process.proc, 'wait', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                process.finish()
        self.assertIsNotNone(process.proc.poll())
        self.assertFalse(process.errors.thread.is_alive())

    def test_descendant_holding_pipe_is_terminated(self):
        # Child inherits stdout/stderr. The parent exits immediately; capture must
        # still finish instead of waiting 30 seconds for the inherited pipe.
        code = 'import subprocess,sys;subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);print("ready")'
        started = time.monotonic()
        result = run_capture([sys.executable, '-c', code], timeout=3)
        self.assertEqual(result.returncode, 0)
        self.assertIn(b'ready', result.stdout)
        self.assertLess(time.monotonic()-started, 8)

    def test_reader_timeout_and_bounded_error(self):
        spec = importlib.util.spec_from_file_location('reader_cli', ROOT/'bio_cli.py')
        cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory(prefix='bio-runtime-test-') as tmp:
            source = Path(tmp)/'data'; source.write_bytes(b'x')
            r = cli.Reader(source, [sys.executable, '-c',
                'import sys,time;sys.stderr.write("e"*1000000);sys.stderr.flush();time.sleep(30)'], timeout=1)
            self.assertEqual(r.stream.read(1), b'')
            with self.assertRaises(TimeoutError): r.close()
            self.assertLessEqual(len(r.process.errors.data), 65536)
            self.assertTrue(r.process.errors.truncated)
