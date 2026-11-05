"""One shared, bounded, on-demand USB preview process for all local viewers."""
from collections import deque
from dataclasses import dataclass
import os
import re
import select
import subprocess
import threading
import time


@dataclass(frozen=True)
class Frame:
    sequence: int
    captured: float
    jpeg: bytes


class JPEGFrames:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, chunk):
        self.buffer.extend(chunk)
        result = []
        while True:
            start = self.buffer.find(b"\xff\xd8")
            if start < 0:
                self.buffer[:] = self.buffer[-1:]
                break
            if start:
                del self.buffer[:start]
            end = self.buffer.find(b"\xff\xd9", 2)
            if end < 0:
                if len(self.buffer) > 8_000_000:
                    self.buffer.clear()
                    raise RuntimeError("Camera returned an oversized frame.")
                break
            result.append(bytes(self.buffer[:end + 2]))
            del self.buffer[:end + 2]
        return result


class LiveCamera:
    def __init__(self, ffmpeg, *, probe=None, command_factory=None, retry_seconds=3, stall_seconds=8):
        self.ffmpeg = ffmpeg
        self.probe = probe or self._present
        self.command_factory = command_factory or self._command
        self.retry_seconds = retry_seconds
        self.stall_seconds = stall_seconds
        self.condition = threading.Condition(threading.RLock())
        self.frames = deque(maxlen=30)
        self.sequence = 0
        self.enabled = True
        self.viewers = 0
        self.process = None
        self.thread = None
        self.closed = False
        self.status = "idle"
        self.message = "Open the app to start the camera."

    def _present(self):
        result = subprocess.run([self.ffmpeg, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                                capture_output=True, timeout=5)
        return bool(re.search(rb"\[\d+\] Mentra Camera\r?$", result.stderr, re.M))

    def _command(self):
        # Name selection prevents a device-index change from selecting the Mac camera.
        return [self.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "avfoundation",
                "-framerate", "30", "-video_size", "1280x720", "-pixel_format", "uyvy422",
                "-i", "Mentra Camera:none", "-an", "-vf", "fps=10", "-c:v", "mjpeg", "-q:v", "2",
                "-f", "image2pipe", "pipe:1"]

    def _wanted(self):
        return self.enabled and self.viewers > 0 and not self.closed

    def attach(self):
        with self.condition:
            if self.closed:
                raise RuntimeError("The camera service is stopped.")
            self.viewers += 1
            if self.thread is None:
                self.thread = threading.Thread(target=self._worker, daemon=True)
                self.thread.start()
            self.condition.notify_all()

    def detach(self):
        with self.condition:
            self.viewers = max(0, self.viewers - 1)
            if not self.viewers:
                self.frames.clear()
            self.condition.notify_all()

    def set_enabled(self, enabled):
        with self.condition:
            self.enabled = enabled
            if not enabled:
                self.frames.clear()
                self.status, self.message = "paused", "Camera paused. Resume to see your glasses’ view."
            self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            age = time.monotonic() - self.frames[-1].captured if self.frames else None
            status = self.status
            message = self.message
            if status == "live" and (age is None or age > 2):
                status, message = "reconnecting", "Camera feed interrupted. Reconnecting automatically…"
            return dict(enabled=self.enabled, status=status, message=message,
                        sequence=self.sequence, frame_age=round(age, 2) if age is not None else None)

    def latest(self, after=0):
        with self.condition:
            if self.enabled and self.frames:
                frame = self.frames[-1]
                if frame.sequence > after and time.monotonic() - frame.captured < 2:
                    return frame
            return None

    def take_frames(self, count, check_cancel=lambda: None, timeout=15):
        with self.condition:
            if not self.enabled:
                raise RuntimeError("Camera is paused. Select Resume camera first.")
            after = self.sequence
        self.attach()
        result = []
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                check_cancel()
                with self.condition:
                    if not self.enabled:
                        raise RuntimeError("Camera was paused. Resume it and try again.")
                    frame = self.latest(after)
                    if frame and (not result or frame.captured - result[-1].captured >= .2):
                        result.append(frame)
                        after = frame.sequence
                        if len(result) == count:
                            return result
                    self.condition.wait(.1)
            raise RuntimeError(self.snapshot()["message"])
        finally:
            self.detach()

    def _state(self, status, message, clear=False):
        with self.condition:
            self.status, self.message = status, message
            if clear:
                self.frames.clear()
            self.condition.notify_all()

    def _worker(self):
        while True:
            with self.condition:
                while not self._wanted():
                    self.frames.clear()
                    self.status = "paused" if not self.enabled else "idle"
                    self.message = "Camera paused. Resume to see your glasses’ view." if not self.enabled else "Open the app to start the camera."
                    if self.closed:
                        return
                    self.condition.wait()
            process = None
            try:
                self._state("connecting", "Connecting to Mentra Camera…", clear=True)
                if not self.probe():
                    self._state("disconnected", "Mentra Camera is not connected. Waiting for its USB connection…", clear=True)
                else:
                    with self.condition:
                        if not self._wanted():
                            continue
                        process = subprocess.Popen(self.command_factory(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
                        self.process = process
                    parser = JPEGFrames()
                    last_frame = time.monotonic()
                    while True:
                        with self.condition:
                            if not self._wanted():
                                break
                        if time.monotonic() - last_frame > self.stall_seconds:
                            raise RuntimeError("The glasses camera stopped sending frames. Reconnecting…")
                        if not select.select([process.stdout], [], [], .2)[0]:
                            continue
                        chunk = os.read(process.stdout.fileno(), 65536)
                        if not chunk:
                            raise RuntimeError("Camera connection interrupted. Reconnecting…")
                        for jpeg in parser.feed(chunk):
                            with self.condition:
                                if not self._wanted():
                                    break
                                last_frame = time.monotonic()
                                self.sequence += 1
                                self.frames.append(Frame(self.sequence, last_frame, jpeg))
                                self.status, self.message = "live", "Live from Mentra Camera · 720p"
                                self.condition.notify_all()
            except Exception as error:
                self._state("reconnecting", str(error), clear=True)
            finally:
                if process is not None:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                    process.stdout.close()
                with self.condition:
                    self.process = None
            with self.condition:
                if self._wanted():
                    self.condition.wait(self.retry_seconds)

    def close(self):
        with self.condition:
            self.closed = True
            self.frames.clear()
            self.condition.notify_all()
        if self.thread:
            self.thread.join(timeout=8)
