"""Owned subprocess groups with bounded diagnostics and optional deadlines.

Standard library only, for the supported macOS/Linux environments. A deadline
can terminate a subprocess group; it cannot interrupt a blocked filesystem read
in the parent process. No global signal handlers or environment changes.
"""
import os
import signal
import subprocess
import threading


class BoundedCapture:
    def __init__(self, stream, limit=65536):
        self.stream = stream
        self.limit = limit
        self.data = bytearray()
        self.truncated = False
        self.thread = threading.Thread(target=self._drain, daemon=True)
        self.thread.start()

    def _drain(self):
        try:
            while True:
                chunk = self.stream.read(65536)
                if not chunk:
                    break
                remaining = self.limit - len(self.data)
                self.data.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    self.truncated = True
        finally:
            self.stream.close()

    def finish(self):
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError('Subprocess output pipe did not close after group termination')
        return bytes(self.data)


class ManagedProcess:
    def __init__(self, command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                 env=None, timeout=None, capture_stdout=False, limit=65536):
        self.command = command
        self.proc = subprocess.Popen(command, stdin=stdin, stdout=stdout,
                                     stderr=subprocess.PIPE, env=env,
                                     start_new_session=True)
        self.errors = BoundedCapture(self.proc.stderr, limit)
        self.output = BoundedCapture(self.proc.stdout, limit) if capture_stdout else None
        self.stdout = self.proc.stdout
        self.timed_out = False
        self.timeout = timeout
        self.done = threading.Event()
        self.watcher = None
        self.finished = False
        if timeout is not None:
            self.watcher = threading.Thread(target=self._deadline, daemon=True)
            self.watcher.start()

    def _signal(self, sig):
        try:
            os.killpg(self.proc.pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            # macOS can report EPERM for a group whose last process is becoming
            # a zombie (not yet observable by poll). Reap it, then retry the
            # group so surviving descendants are still signalled. Never hide
            # permission failures for a live process or a surviving group.
            try:
                self.proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                raise PermissionError('Cannot signal the live subprocess group')
            try:
                os.killpg(self.proc.pid, sig)
            except ProcessLookupError:
                pass

    def _deadline(self):
        if not self.done.wait(self.timeout):
            self.timed_out = True
            self._signal(signal.SIGKILL)

    def finish(self, cancel=False, wait_timeout=None):
        if self.finished:
            return self.proc.returncode
        try:
            if cancel:
                self._signal(signal.SIGTERM)
            try:
                code = self.proc.wait(timeout=5 if cancel else wait_timeout)
            except subprocess.TimeoutExpired:
                self._signal(signal.SIGKILL)
                code = self.proc.wait(timeout=5)
                if not cancel:
                    self.timed_out = True
            # A backend must not leave children holding inherited pipes open.
            self._signal(signal.SIGKILL)
            self.errors.finish()
            if self.output:
                self.output.finish()
            if self.timed_out:
                raise TimeoutError('Subprocess exceeded its deadline')
            return code
        except BaseException:
            self._signal(signal.SIGKILL)
            self.proc.wait(timeout=5)
            self.errors.finish()
            if self.output:
                self.output.finish()
            raise
        finally:
            if self.stdout is not None and self.output is None:
                self.stdout.close()
            self.done.set()
            if self.watcher:
                self.watcher.join(timeout=1)
            self.finished = True


def run_capture(command, timeout=15, limit=8192, env=None):
    process = ManagedProcess(command, timeout=timeout, capture_stdout=True,
                             limit=limit, env=env)
    try:
        code = process.finish()
    except BaseException:
        process.finish(cancel=True)
        raise
    return subprocess.CompletedProcess(command, code,
        bytes(process.output.data) + bytes(process.errors.data),
        bytes(process.errors.data))
