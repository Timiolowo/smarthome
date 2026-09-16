"""
Android Device Bridge via ADB (Android Debug Bridge).
Enables the smart home assistant to inspect connected Android phones,
initiate phone calls, check battery/Wi-Fi, and dispatch device intents.
"""

import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional


class AndroidBridge:
    def __init__(self, adb_path: Optional[str] = None):
        self.adb_path = adb_path or shutil.which("adb") or "adb"

    def is_available(self) -> bool:
        """Returns True if the adb binary is installed and executable."""
        try:
            res = subprocess.run([self.adb_path, "version"], capture_output=True, text=True, timeout=2.0)
            return res.returncode == 0
        except Exception:
            return False

    def list_connected_devices(self) -> List[Dict[str, str]]:
        """Returns list of connected Android devices via 'adb devices'."""
        devices = []
        try:
            res = subprocess.run([self.adb_path, "devices", "-l"], capture_output=True, text=True, timeout=3.0)
            if res.returncode == 0:
                lines = res.stdout.strip().splitlines()
                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        serial = parts[0]
                        status = parts[1]
                        model_match = re.search(r"model:(\S+)", line)
                        model = model_match.group(1) if model_match else "Android Device"
                        devices.append({
                            "serial": serial,
                            "status": status,
                            "model": model.replace("_", " "),
                            "authorized": status == "device",
                        })
        except Exception:
            pass
        return devices

    def get_phone_status(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Queries battery level and connectivity of connected Android phone."""
        if not self.is_available():
            return {
                "available": False,
                "error": "ADB is not installed on this server.",
                "connected": False,
            }

        devices = self.list_connected_devices()
        if not devices:
            return {
                "available": True,
                "connected": False,
                "message": "No Android phone connected via USB or Wi-Fi ADB.",
            }

        target = devices[0]
        if serial:
            matching = [d for d in devices if d["serial"] == serial]
            if matching:
                target = matching[0]

        if not target.get("authorized"):
            return {
                "available": True,
                "connected": True,
                "authorized": False,
                "device": target,
                "message": f"{target['model']} is connected but unauthorized. Please accept the USB debugging prompt on your phone.",
            }

        cmd_prefix = [self.adb_path, "-s", target["serial"]] if target.get("serial") else [self.adb_path]

        # Get battery
        battery_pct = None
        is_charging = False
        try:
            res = subprocess.run(cmd_prefix + ["shell", "dumpsys", "battery"], capture_output=True, text=True, timeout=3.0)
            if res.returncode == 0:
                level_match = re.search(r"\blevel:\s*(\d+)", res.stdout)
                status_match = re.search(r"\bstatus:\s*(\d+)", res.stdout)  # 2 is charging
                if level_match:
                    battery_pct = int(level_match.group(1))
                if status_match:
                    is_charging = int(status_match.group(1)) == 2
        except Exception:
            pass

        return {
            "available": True,
            "connected": True,
            "authorized": True,
            "device": target,
            "battery_percent": battery_pct,
            "is_charging": is_charging,
            "summary": f"{target['model']} connected. Battery: {battery_pct}%{' (Charging)' if is_charging else ''}.",
        }

    def initiate_phone_call(self, phone_number: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Initiates an outbound phone call via Android intent ACTION_CALL or ACTION_DIAL."""
        clean_number = re.sub(r"[^\d+*#]", "", phone_number.strip())
        if not clean_number:
            return {"ok": False, "error": "Invalid phone number."}

        status = self.get_phone_status(serial=serial)
        if not status.get("connected") or not status.get("authorized"):
            return {
                "ok": False,
                "error": status.get("message") or "Android phone is not connected or authorized via ADB.",
            }

        target_serial = status["device"]["serial"]
        cmd = [
            self.adb_path,
            "-s",
            target_serial,
            "shell",
            "am",
            "start",
            "-a",
            "android.intent.action.CALL",
            "-d",
            f"tel:{clean_number}",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=4.0)
            if res.returncode == 0:
                return {
                    "ok": True,
                    "phone_number": clean_number,
                    "device": status["device"]["model"],
                    "message": f"Calling {clean_number} on your {status['device']['model']}.",
                }
            else:
                # Fallback to ACTION_DIAL if CALL permission is restricted
                dial_cmd = [
                    self.adb_path,
                    "-s",
                    target_serial,
                    "shell",
                    "am",
                    "start",
                    "-a",
                    "android.intent.action.DIAL",
                    "-d",
                    f"tel:{clean_number}",
                ]
                res_dial = subprocess.run(dial_cmd, capture_output=True, text=True, timeout=4.0)
                if res_dial.returncode == 0:
                    return {
                        "ok": True,
                        "phone_number": clean_number,
                        "device": status["device"]["model"],
                        "message": f"Dialing {clean_number} on your {status['device']['model']}.",
                    }
                return {"ok": False, "error": res.stderr.strip() or "Could not start call intent."}
        except Exception as e:
            return {"ok": False, "error": f"Failed to execute call intent: {e}"}


android_bridge = AndroidBridge()
