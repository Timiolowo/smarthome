"""Persistent 16 kHz capture, with native echo-cancelled playback on macOS."""
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import subprocess
import tempfile
import threading
import time
import uuid

import numpy as np


class AudioCapture:
    frame_size = 512

    def __init__(self, device=None, echo_cancellation=True):
        self.frames = queue.Queue(maxsize=125)  # Four seconds, bounded if processing is slow.
        self.pending = np.empty(0, dtype=np.float32)
        self.echo_cancelled = False
        self.process = None
        self.reader = None
        self.stream = None
        self.error = None
        self.dropped_frames = 0
        self.played = threading.Event()
        self.playing = threading.Event()
        self.playback_id = None
        self.playback_error = None
        self.name = 'System default microphone'
        if platform.system() == 'Darwin' and echo_cancellation and device is None:
            try:
                self._start_native()
                return
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                self.close()
                self.error = None
                print(f'[Audio] Native echo cancellation unavailable: {exc}. Voice interruption disabled.')
        import sounddevice as sd
        info = sd.query_devices(device, 'input')
        self.name = info['name']
        self.stream = sd.InputStream(device=device, samplerate=16000, channels=1,
                                     dtype='float32', blocksize=self.frame_size,
                                     callback=self._callback)
        self.stream.start()

    def _callback(self, data, frames, timestamp, status):
        if status.input_overflow:
            self.dropped_frames += 1
        self._enqueue(data[:, 0].copy())

    def _enqueue(self, frame):
        try:
            self.frames.put_nowait(frame)
        except queue.Full:
            try:
                self.frames.get_nowait()
            except queue.Empty:
                pass
            self.dropped_frames += 1
            self.frames.put_nowait(frame)

    def _start_native(self):
        source = Path(__file__).resolve().parent.parent / 'native' / 'VoiceAudio.swift'
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
        cache = Path(tempfile.gettempdir()) / f'smarthome-audio-{os.getuid()}'
        cache.mkdir(mode=0o700, exist_ok=True)
        binary = cache / f'voice-audio-{digest}'
        if not binary.exists():
            print('[Audio] Building macOS voice processing helper (first run only)...')
            build = subprocess.run(['xcrun', 'swiftc', '-O', '-module-cache-path', str(cache / 'modules'),
                                    str(source), '-o', str(binary)], capture_output=True, text=True, timeout=120)
            if build.returncode:
                raise RuntimeError(build.stderr[-1500:])
        self.ready = threading.Event()
        self.process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.reader = threading.Thread(target=self._events, daemon=True)
        self.reader.start()
        if not self.ready.wait(8) or not self.echo_cancelled:
            raise RuntimeError(self.error or 'No echo-cancelled audio route available')

    def _events(self):
        process = self.process
        try:
            for line in process.stdout:
                event = json.loads(line)
                kind = event.get('event')
                if kind == 'ready':
                    self.echo_cancelled = event.get('echo_cancelled', False)
                    self.name = event.get('device', self.name)
                    self.ready.set()
                elif kind == 'audio':
                    self._enqueue(np.frombuffer(base64.b64decode(event['pcm']), dtype='<f4').copy())
                elif kind == 'error':
                    self.error = event.get('message', 'Audio device failed')
                    self.ready.set()
                elif event.get('id') == self.playback_id:
                    if kind == 'playing':
                        self.playing.set()
                    elif kind in ('played', 'play_error'):
                        self.playback_error = event.get('message')
                        self.played.set()
        except (ValueError, OSError) as exc:
            self.error = str(exc)
        finally:
            self.error = self.error or 'Audio capture stopped; check your microphone connection'
            self.ready.set()
            self.played.set()

    def read(self, timeout=2):
        deadline = time.monotonic() + timeout
        while len(self.pending) < self.frame_size:
            if self.error:
                raise RuntimeError(self.error)
            try:
                frame = self.frames.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                raise RuntimeError('No microphone audio received') from None
            self.pending = np.concatenate((self.pending, frame))
        frame, self.pending = self.pending[:self.frame_size], self.pending[self.frame_size:]
        return frame

    def flush(self):
        self.pending = np.empty(0, dtype=np.float32)
        while True:
            try:
                self.frames.get_nowait()
            except queue.Empty:
                break

    def _command(self, **command):
        if self.process is None or self.process.poll() is not None:
            raise RuntimeError('Native audio helper is not running')
        self.process.stdin.write(json.dumps(command) + '\n')
        self.process.stdin.flush()

    def play(self, path):
        self.playback_id = uuid.uuid4().hex
        self.playback_error = None
        self.playing.clear()
        self.played.clear()
        self._command(command='play', path=str(path), id=self.playback_id)

    def stop_playback(self):
        if self.process and self.process.poll() is None:
            self._command(command='stop')

    def close(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.process:
            process, self.process = self.process, None
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if self.reader:
                self.reader.join(timeout=2)
            process.stdin.close()
            process.stdout.close()
