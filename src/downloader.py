import os
import sys
import time
import platform
import subprocess
import threading
import urllib.request
import urllib.error

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")


def get_system_hardware_specs():
    """Detects host RAM, CPU architecture, and provides intelligent model recommendations."""
    ram_gb = 8.0
    try:
        if sys.platform == "darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"]).strip()
            ram_gb = round(int(out) / (1024 ** 3), 1)
        elif sys.platform == "win32":
            try:
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                ram_gb = round(stat.ullTotalPhys / (1024 ** 3), 1)
            except Exception:
                pass
        elif hasattr(os, "sysconf") and "SC_PAGE_SIZE" in os.sysconf_names and "SC_PHYS_PAGES" in os.sysconf_names:
            ram_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            ram_gb = round(ram_bytes / (1024 ** 3), 1)
    except Exception:
        pass

    chip = platform.machine()
    is_apple_silicon = sys.platform == "darwin" and chip in ("arm64", "aarch64")

    if ram_gb >= 8:
        recommended_model = "llm_3b"
        reason = f"Your system has {ram_gb} GB RAM ({chip}). Llama 3.2 3B is recommended for top reasoning and tool-use."
    elif ram_gb >= 4:
        recommended_model = "llm_1b"
        reason = f"Your system has {ram_gb} GB RAM ({chip}). Llama 3.2 1B is recommended for ultra-fast, lightweight performance."
    else:
        recommended_model = "llm_1b"
        reason = f"Your system has {ram_gb} GB RAM. Low memory detected — 1B model or Cloud API is recommended."

    return {
        "ram_gb": ram_gb,
        "chip": chip,
        "platform": platform.system(),
        "is_apple_silicon": is_apple_silicon,
        "recommended_model": recommended_model,
        "reason": reason,
    }


MODEL_SPECS = {
    "llm_3b": {
        "name": "Llama 3.2 3B Instruct",
        "category": "Brain (LLM)",
        "ram_requirement": "8 GB+ RAM",
        "download_size": "~2.0 GB",
        "description": "High accuracy reasoning, counts, tool-use, multi-turn conversations.",
        "files": [
            {
                "url": "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
                "rel_path": "llm/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
                "min_size": 2_000_000_000,
                "label": "Llama-3.2-3B-Instruct-Q4_K_M.gguf (~2.0 GB)"
            }
        ]
    },
    "llm_1b": {
        "name": "Llama 3.2 1B Instruct",
        "category": "Brain (LLM)",
        "ram_requirement": "4 GB+ RAM",
        "download_size": "~750 MB",
        "description": "Ultra-fast inference with low memory footprint. Ideal for older laptops or Raspberry Pi.",
        "files": [
            {
                "url": "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
                "rel_path": "llm/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
                "min_size": 750_000_000,
                "label": "Llama-3.2-1B-Instruct-Q4_K_M.gguf (~750 MB)"
            }
        ]
    },
    "stt": {
        "name": "Faster-Whisper small.en (Acoustic Ears)",
        "category": "Speech Recognition (STT)",
        "files": [
            {
                "url": "https://huggingface.co/Systran/faster-whisper-small.en/resolve/main/model.bin",
                "rel_path": "stt/model.bin",
                "min_size": 450_000_000,
                "label": "Whisper small.en model.bin (~460 MB)"
            },
            {
                "url": "https://huggingface.co/Systran/faster-whisper-small.en/resolve/main/config.json",
                "rel_path": "stt/config.json",
                "min_size": 2_000,
                "label": "Whisper config.json"
            },
            {
                "url": "https://huggingface.co/Systran/faster-whisper-small.en/resolve/main/tokenizer.json",
                "rel_path": "stt/tokenizer.json",
                "min_size": 2_000_000,
                "label": "Whisper tokenizer.json"
            },
            {
                "url": "https://huggingface.co/Systran/faster-whisper-small.en/resolve/main/vocabulary.txt",
                "rel_path": "stt/vocabulary.txt",
                "min_size": 400_000,
                "label": "Whisper vocabulary.txt"
            }
        ]
    },
    "tts": {
        "name": "Piper Neural Voice (Natural Speech)",
        "category": "Voice Synthesis (TTS)",
        "files": [
            {
                "url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
                "rel_path": "tts/en_US-lessac-medium.onnx",
                "min_size": 60_000_000,
                "label": "Piper Voice Model (~63 MB)"
            },
            {
                "url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
                "rel_path": "tts/en_US-lessac-medium.onnx.json",
                "min_size": 4_000,
                "label": "Piper Voice Config"
            }
        ]
    }
}


class ModelDownloader:
    def __init__(self):
        self.lock = threading.Lock()
        self.active_task = None
        self.download_thread = None
        self.status = {
            "state": "idle", # "idle", "downloading", "completed", "error"
            "selected_models": [],
            "current_item": "",
            "current_file": "",
            "file_index": 0,
            "total_files": 0,
            "bytes_downloaded": 0,
            "total_bytes": 0,
            "percent": 0.0,
            "speed_mbps": 0.0,
            "eta_seconds": 0,
            "error_message": "",
            "completed_models": []
        }

    def get_models_status(self):
        """Check presence and validity of all models on disk."""
        result = {}
        for key, spec in MODEL_SPECS.items():
            all_exist = True
            total_sz = 0
            file_statuses = []
            for f in spec["files"]:
                full_path = os.path.join(MODELS_DIR, f["rel_path"])
                if os.path.exists(full_path):
                    sz = os.path.getsize(full_path)
                    valid = sz >= f["min_size"]
                    total_sz += sz
                    if not valid:
                        all_exist = False
                    file_statuses.append({"name": f["label"], "exists": True, "size": sz, "valid": valid})
                else:
                    all_exist = False
                    file_statuses.append({"name": f["label"], "exists": False, "size": 0, "valid": False})
            result[key] = {
                "name": spec["name"],
                "category": spec["category"],
                "ram_requirement": spec.get("ram_requirement", ""),
                "download_size": spec.get("download_size", ""),
                "description": spec.get("description", ""),
                "installed": all_exist,
                "total_size_bytes": total_sz,
                "files": file_statuses
            }
        return result

    def get_download_status(self):
        with self.lock:
            return dict(self.status)

    def start_download(self, model_keys):
        """Start downloading specified model keys in a background thread."""
        with self.lock:
            if self.status["state"] == "downloading":
                return False, "Download already in progress."

            valid_keys = [k for k in model_keys if k in MODEL_SPECS]
            if not valid_keys:
                return False, "No valid models specified for download."

            self.status["state"] = "downloading"
            self.status["selected_models"] = valid_keys
            self.status["error_message"] = ""
            self.status["percent"] = 0.0

            self.download_thread = threading.Thread(
                target=self._download_worker,
                args=(valid_keys,),
                daemon=True
            )
            self.download_thread.start()
            return True, "Download started."

    def _download_worker(self, model_keys):
        files_to_download = []
        for key in model_keys:
            spec = MODEL_SPECS[key]
            for f in spec["files"]:
                dest_path = os.path.join(MODELS_DIR, f["rel_path"])
                # Check if already complete
                if os.path.exists(dest_path) and os.path.getsize(dest_path) >= f["min_size"]:
                    continue
                files_to_download.append({
                    "model_key": key,
                    "model_name": spec["name"],
                    "url": f["url"],
                    "dest": dest_path,
                    "label": f["label"],
                    "min_size": f["min_size"]
                })

        with self.lock:
            self.status["total_files"] = len(files_to_download)
            self.status["file_index"] = 0
            if not files_to_download:
                self.status["state"] = "completed"
                self.status["percent"] = 100.0
                return

        for idx, item in enumerate(files_to_download):
            with self.lock:
                self.status["file_index"] = idx + 1
                self.status["current_item"] = item["model_name"]
                self.status["current_file"] = item["label"]

            dest = item["dest"]
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            temp_dest = dest + ".part"

            initial_bytes = 0
            if os.path.exists(temp_dest):
                initial_bytes = os.path.getsize(temp_dest)

            try:
                req = urllib.request.Request(
                    item["url"],
                    headers={"User-Agent": "SmartHome-Assistant-Downloader/1.0"}
                )
                if initial_bytes > 0:
                    req.add_header("Range", f"bytes={initial_bytes}-")

                opener = urllib.request.build_opener()
                with opener.open(req) as resp:
                    content_range = resp.headers.get("Content-Range")
                    content_length = resp.headers.get("Content-Length")

                    if content_range:
                        try:
                            total_file_bytes = int(content_range.split("/")[-1])
                        except Exception:
                            total_file_bytes = int(content_length) + initial_bytes if content_length else item["min_size"]
                    elif content_length:
                        total_file_bytes = int(content_length) + (initial_bytes if resp.status == 206 else 0)
                    else:
                        total_file_bytes = item["min_size"]

                    mode = "ab" if initial_bytes > 0 and resp.status == 206 else "wb"
                    if mode == "wb":
                        initial_bytes = 0

                    downloaded = initial_bytes
                    start_time = time.time()
                    last_update = start_time
                    chunk_size = 1024 * 128 # 128 KB

                    with open(temp_dest, mode) as out_f:
                        while True:
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            downloaded += len(chunk)

                            now = time.time()
                            if now - last_update >= 0.3: # update stats every 300ms
                                elapsed = max(0.001, now - start_time)
                                speed = (downloaded - initial_bytes) / elapsed # bytes per sec
                                speed_mbps = (speed * 8) / (1024 * 1024)
                                remaining_bytes = max(0, total_file_bytes - downloaded)
                                eta = remaining_bytes / max(1.0, speed) if speed > 0 else 0

                                pct = round(
                                    ((idx + (downloaded / max(1, total_file_bytes))) / len(files_to_download)) * 100,
                                    1
                                )

                                with self.lock:
                                    self.status["bytes_downloaded"] = downloaded
                                    self.status["total_bytes"] = total_file_bytes
                                    self.status["percent"] = min(99.9, pct)
                                    self.status["speed_mbps"] = round(speed_mbps, 2)
                                    self.status["eta_seconds"] = int(eta)
                                last_update = now

                # Download finished for this file, rename temp to actual
                if os.path.exists(dest):
                    os.remove(dest)
                os.rename(temp_dest, dest)

            except Exception as e:
                with self.lock:
                    self.status["state"] = "error"
                    self.status["error_message"] = f"Error downloading {item['label']}: {str(e)}"
                return

        with self.lock:
            self.status["state"] = "completed"
            self.status["percent"] = 100.0
            self.status["speed_mbps"] = 0.0
            self.status["eta_seconds"] = 0
            self.status["completed_models"] = model_keys


downloader = ModelDownloader()


def cli_download_models():
    """CLI entrypoint for interactive model downloads across Windows, macOS, and Linux."""
    specs = get_system_hardware_specs()
    print("=" * 60)
    print("      Local AI Models Downloader (Cross-Platform)")
    print("=" * 60)
    print(f"System: {specs['platform']} ({specs['chip']}) | RAM: {specs['ram_gb']} GB")
    print(f"Recommendation: {specs['reason']}\n")

    chosen_llm = specs["recommended_model"]
    models_to_fetch = [chosen_llm, "stt", "tts"]

    # Check if models already exist
    missing = []
    for mk in models_to_fetch:
        spec = MODEL_SPECS.get(mk)
        if not spec:
            continue
        all_ok = True
        for f in spec["files"]:
            dest = os.path.join(MODELS_DIR, f["rel_path"])
            min_sz = f.get("min_size", 1000)
            if not os.path.exists(dest) or os.path.getsize(dest) < min_sz:
                all_ok = False
                break
        if not all_ok:
            missing.append(mk)
        else:
            print(f"✓ {spec['name']} is already downloaded and verified.")

    if not missing:
        print("\nAll required offline AI models are ready!")
        return

    print(f"\nDownloading missing models: {', '.join(missing)}...")
    downloader.start_download(missing)

    last_pct = -1
    while True:
        status = downloader.get_status()
        state = status.get("state")
        pct = status.get("percent", 0.0)
        curr_file = status.get("current_file", "")
        speed = status.get("speed_mbps", 0.0)
        eta = status.get("eta_seconds", 0)

        if state == "downloading":
            if int(pct) != last_pct:
                sys.stdout.write(f"\r[{pct:5.1f}%] {curr_file[:35]:<35} | {speed:5.1f} Mbps | ETA: {eta:3d}s   ")
                sys.stdout.flush()
                last_pct = int(pct)
        elif state == "completed":
            print(f"\n\n✓ All downloads completed successfully!")
            break
        elif state == "error":
            print(f"\n\nError: {status.get('error_message')}")
            sys.exit(1)
        time.sleep(0.2)


if __name__ == "__main__":
    cli_download_models()
