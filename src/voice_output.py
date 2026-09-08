import io
import os
import platform
import shutil
import subprocess
import time
import wave
from typing import Optional

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


class Speaker:
    def __init__(self):
        self._system = platform.system().lower()
        self._engine = None
        self.piper_voice = None
        self.current_process: Optional[subprocess.Popen] = None

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
        if sd is not None:
            try:
                sd.stop()
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
        On macOS: Uses native high-quality built-in voice.
        On other systems (Linux/PC): Uses downloaded Piper Neural Voice.
        """
        self.stop()
        print(f"\n📢 [Assistant Speaking]: \"{text}\"")

        # 1. macOS native 'say' (Clean, fast, built-in Mac voice)
        if self._system == "darwin" and shutil.which("say"):
            try:
                if voice and voice.lower() not in ("default", "none"):
                    cmd = ["say", "-v", voice, text]
                else:
                    cmd = ["say", text]
                self.current_process = subprocess.Popen(cmd)
                if not interruptible or listener is None:
                    self.current_process.wait()
                    return False

                interrupted = listener.monitor_for_interruption(self.current_process)
                if interrupted:
                    self.stop()
                    print("\n⚡ [INTERRUPTED]: Speech cut off by user.")
                    return True
                return False
            except subprocess.SubprocessError as e:
                print(f"[Speaker] macOS 'say' failed ({e}), falling back...")

        # 2. Piper Neural TTS (For Linux/PC/other systems - high quality offline voice)
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
                sd.wait()
                return False
            except Exception as e:
                print(f"[Speaker] Piper speech error ({e}), trying fallback...")

        # 3. Linux / other fallback (espeak or pyttsx3)
        if shutil.which("espeak"):
            try:
                self.current_process = subprocess.Popen(["espeak", text])
                if not interruptible or listener is None:
                    self.current_process.wait()
                    return False
                interrupted = listener.monitor_for_interruption(self.current_process)
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
    return speaker.speak(text, listener=listener, interruptible=interruptible, voice=voice)


def stop() -> None:
    speaker.stop()
