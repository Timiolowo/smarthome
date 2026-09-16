import io
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import wave
from typing import Optional
from src import audio_runtime


def normalize_voice_name(voice: Optional[str]) -> Optional[str]:
    """Normalizes voice name from browser descriptors like 'Samantha (Enhanced)' to 'Samantha' for macOS say."""
    if not voice or voice.lower() in ('default', 'none', ''):
        return None
    clean = re.sub(r'\s*\(.*?\)', '', voice).strip()
    return clean or None


class NativePlayback:
    def __init__(self, capture):
        self.capture = capture
        self.deadline = time.monotonic() + 120

    def poll(self):
        if self.capture.error or self.capture.playback_error:
            raise RuntimeError(self.capture.error or self.capture.playback_error)
        if time.monotonic() >= self.deadline:
            raise RuntimeError('Playback timed out')
        return 0 if self.capture.played.is_set() else None


class SoundDevicePlayback:
    """Polling adapter for interruptible Piper playback on Windows and Linux."""

    def poll(self):
        try:
            return None if sd.get_stream().active else 0
        except Exception:
            return 0


def play_ready_chime(capture=None):
    """A quiet, short ready cue, completed before accepting microphone input."""
    if sd is None or np is None:
        return
    samples = np.arange(1280) / 16000
    tone = (.06 * np.sin(2 * np.pi * 660 * samples) * np.sin(np.linspace(0, np.pi, 1280)) ** 2)
    try:
        if capture and capture.echo_cancelled:
            with tempfile.NamedTemporaryFile(suffix='.wav') as file:
                with wave.open(file.name, 'wb') as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(16000)
                    wav.writeframes((tone * 32767).astype('<i2').tobytes())
                capture.play(file.name)
                if not capture.played.wait(2):
                    capture.stop_playback()
        else:
            sd.play(tone.astype(np.float32), samplerate=16000)
            sd.wait()
        time.sleep(.12)  # Let the short acoustic tail settle before listening.
    except Exception as exc:
        print(f'[Audio] Ready cue unavailable: {exc}')

try:
    import numpy as np
    import sounddevice as sd
except ImportError:
    np = None
    sd = None

PIPER_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "tts",
    "en_US-lessac-medium.onnx",
)
PIPER_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "tts",
    "en_US-lessac-medium.onnx.json",
)


SIRI_SWIFT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "native",
    "siri_speak.swift",
)


class Speaker:
    def __init__(self):
        self._system = platform.system().lower()
        self._engine = None
        self.piper_voice = None
        self.current_process: Optional[subprocess.Popen] = None
        self.native_capture = None
        self.has_swift = bool(self._system == "darwin" and shutil.which("swift") and os.path.exists(SIRI_SWIFT_PATH))

        # 1. On non-macOS systems (Linux/PC), load Piper Neural TTS
        if self._system != "darwin" and os.path.exists(PIPER_MODEL_PATH) and os.path.exists(PIPER_CONFIG_PATH):
            try:
                from piper.voice import PiperVoice
                self.piper_voice = PiperVoice.load(PIPER_MODEL_PATH, config_path=PIPER_CONFIG_PATH)
                print("[Speaker] Piper Neural Voice loaded (natural offline voice for Linux/PC).")
            except Exception as e:
                print(f"[Speaker] Notice: Piper TTS not active ({e}), using system fallback.")

        # 2. Linux fallback engine if Piper is not active
        if self._system != "darwin" and self.piper_voice is None:
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
            except Exception as e:
                print(f"[Speaker] Notice: pyttsx3 skipped ({e}).")

    def stop(self) -> None:
        """Immediately silences any active speech process or audio playback."""
        if self.native_capture:
            try:
                self.native_capture.stop_playback()
            except (OSError, RuntimeError):
                pass
            self.native_capture = None
        if sd is not None:
            try:
                sd.stop()
            except Exception:
                pass
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass

        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=0.2)
            except Exception:
                try:
                    self.current_process.kill()
                except Exception:
                    pass
            self.current_process = None

    def speak(self, text: str, listener=None, interruptible: bool = False, voice: Optional[str] = None) -> bool:
        """
        Speaks text aloud smoothly.
        On macOS: Uses natural Apple Siri Voice (Voice 4 Enhanced) with fallback to 'say'.
        On other systems (Linux/PC): Uses downloaded Piper Neural Voice.
        """
        self.stop()
        print(f"\n📢 [Assistant Speaking]: \"{text}\"")

        norm_voice = normalize_voice_name(voice)

        # Render speech once, then play through the same engine as microphone AEC.
        if self._system == 'darwin' and listener and listener.capture and listener.capture.echo_cancelled:
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav') as file:
                    started = time.monotonic()
                    listener._state('SYNTHESIZING', 'Preparing my reply')
                    rendered = False

                    # 1a. Try Siri Enhanced voice via Swift first
                    if self.has_swift:
                        try:
                            siri_cmd = ['swift', SIRI_SWIFT_PATH, '-o', file.name]
                            if norm_voice:
                                siri_cmd += ['-v', norm_voice]
                            siri_cmd.append(text)
                            res = subprocess.run(siri_cmd, capture_output=True, timeout=30)
                            if res.returncode == 0 and os.path.exists(file.name) and os.path.getsize(file.name) > 1000:
                                rendered = True
                        except Exception as e:
                            print(f"[Speaker] Siri Swift TTS notice: {e}, using system fallback.")

                    # 1b. Only fallback to macOS 'say' command to render WAV if Swift is not available
                    if not rendered and not self.has_swift:
                        cmd = ['say', '-o', file.name, '--file-format=WAVE', '--data-format=LEI16@16000']
                        if norm_voice:
                            cmd += ['-v', norm_voice]
                        subprocess.run(cmd + [text], check=True, capture_output=True, timeout=60)
                        rendered = True

                    if not rendered:
                        raise RuntimeError('Failed to synthesize speech audio with native engine')

                    with wave.open(file.name, 'rb') as wav:
                        if not wav.getnframes():
                            raise RuntimeError('System voice produced no audio')
                    audio_runtime.timing('speech_preparation', time.monotonic() - started)
                    capture = listener.capture
                    self.native_capture = capture
                    capture.play(file.name)
                    deadline = time.monotonic() + 5
                    while not capture.playing.is_set() and not capture.played.is_set():
                        if time.monotonic() >= deadline:
                            raise RuntimeError('Audio playback did not start')
                        time.sleep(.01)
                    if capture.error or capture.playback_error:
                        raise RuntimeError(capture.error or capture.playback_error)
                    listener._state('SPEAKING', 'Speaking — you can interrupt')
                    interrupted = listener.monitor_for_interruption(NativePlayback(capture)) if interruptible else False
                    if not interruptible:
                        if not capture.played.wait(120):
                            raise RuntimeError('Audio playback timed out')
                    if interrupted:
                        capture.stop_playback()
                    self.native_capture = None
                    return interrupted
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                self.stop()
                print(f'[Speaker] Echo-cancelled playback failed ({exc}); using direct voice playback.')

        if listener:
            listener._state('SPEAKING', 'Speaking — press Enter to interrupt')

        # 1. macOS Siri Neural / Enhanced Voice (natural smooth voice via Swift)
        if self._system == "darwin" and self.has_swift:
            try:
                cmd = ["swift", SIRI_SWIFT_PATH]
                if norm_voice:
                    cmd += ["-v", norm_voice]
                cmd.append(text)
                self.current_process = subprocess.Popen(cmd)
                if not interruptible or listener is None:
                    self.current_process.wait()
                    return False
                else:
                    interrupted = listener.monitor_for_interruption(self.current_process, allow_voice=False)
                    if interrupted:
                        self.stop()
                        print("\n⚡ [INTERRUPTED]: Speech cut off by user.")
                        return True
                    return False
            except subprocess.SubprocessError as e:
                print(f"[Speaker] Siri Swift speech failed: {e}")
                return False

        # 2. macOS legacy 'say' (ONLY when Swift toolchain is unavailable)
        if self._system == "darwin" and not self.has_swift and shutil.which("say"):
            try:
                if norm_voice:
                    cmd = ["say", "-v", norm_voice, text]
                else:
                    cmd = ["say", text]
                self.current_process = subprocess.Popen(cmd)
                if not interruptible or listener is None:
                    self.current_process.wait()
                    return False

                interrupted = listener.monitor_for_interruption(self.current_process, allow_voice=False)
                if interrupted:
                    self.stop()
                    print("\n⚡ [INTERRUPTED]: Speech cut off by user.")
                    return True
                return False
            except subprocess.SubprocessError as e:
                print(f"[Speaker] macOS 'say' failed ({e})")
                return False

        # 3. Piper Neural TTS (For Linux/PC/other systems - high quality offline voice)
        if self.piper_voice is not None and sd is not None and np is not None:
            try:
                wav_io = io.BytesIO()
                with wave.open(wav_io, "wb") as wav_file:
                    self.piper_voice.synthesize(text, wav_file)
                wav_io.seek(0)
                with wave.open(wav_io, "rb") as wav_file:
                    sample_rate = wav_file.getframerate()
                    frames = wav_file.readframes(wav_file.getnframes())
                    audio_data = np.frombuffer(frames, dtype=np.int16)

                sd.play(audio_data, samplerate=sample_rate)
                if interruptible and listener is not None:
                    interrupted = listener.monitor_for_interruption(
                        SoundDevicePlayback(),
                        allow_voice=bool(listener.capture and listener.capture.echo_cancelled),
                    )
                    if interrupted:
                        self.stop()
                        print("\n⚡ [INTERRUPTED]: Speech cut off by user.")
                        return True
                else:
                    sd.wait()
                return False
            except Exception as e:
                print(f"[Speaker] Piper speech error ({e}), trying fallback...")

        # 4. Windows native System.Speech fallback (PowerShell)
        if self._system == "windows":
            try:
                escaped = text.replace("'", "''")
                ps_script = f"Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.Speak('{escaped}')"
                self.current_process = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script])
                if not interruptible or listener is None:
                    self.current_process.wait()
                    return False
                interrupted = listener.monitor_for_interruption(self.current_process, allow_voice=False)
                if interrupted:
                    self.stop()
                    print("\n⚡ [INTERRUPTED]: Speech cut off by user.")
                    return True
                return False
            except Exception:
                pass

        # 5. Linux / other fallback (espeak or pyttsx3)
        if shutil.which("espeak"):
            try:
                self.current_process = subprocess.Popen(["espeak", text])
                if not interruptible or listener is None:
                    self.current_process.wait()
                    return False
                interrupted = listener.monitor_for_interruption(self.current_process, allow_voice=False)
                if interrupted:
                    self.stop()
                    print("\n⚡ [INTERRUPTED]: Speech cut off by user.")
                    return True
                return False
            except Exception:
                pass

        if self._engine is not None:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
                return False
            except Exception:
                pass

        return False


# Global singleton instance
speaker = Speaker()


def speak(text: str, listener=None, interruptible: bool = False, voice: Optional[str] = None) -> bool:
    started = time.monotonic()
    try:
        return speaker.speak(text, listener=listener, interruptible=interruptible, voice=voice)
    finally:
        audio_runtime.timing('speech_playback_total', time.monotonic() - started)


def speak_stream(sentence_generator, listener=None, interruptible: bool = True,
                 voice: Optional[str] = None, cancel_event=None) -> tuple:
    """
    Speaks a stream of sentences sequentially.
    Immediately stops playback and sets cancel_event upon user interruption.
    Returns (interrupted: bool, spoken_text: str).
    """
    started = time.monotonic()
    spoken_sentences = []
    interrupted = False
    try:
        for sentence in sentence_generator:
            if cancel_event and cancel_event.is_set():
                interrupted = True
                break
            clean = sentence.strip()
            if not clean:
                continue
            interrupted = speaker.speak(clean, listener=listener, interruptible=interruptible, voice=voice)
            if interrupted:
                if cancel_event:
                    cancel_event.set()
                break
            spoken_sentences.append(clean)
    finally:
        if cancel_event and cancel_event.is_set():
            interrupted = True
        if interrupted and hasattr(sentence_generator, 'close'):
            sentence_generator.close()
        audio_runtime.timing('speech_playback_total', time.monotonic() - started)
    return interrupted, " ".join(spoken_sentences).strip()


def stop() -> None:
    speaker.stop()
