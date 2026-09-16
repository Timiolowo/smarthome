"""
Cross-Platform OS Adapter Layer for Smart Home Assistant.
Inspects Wi-Fi, battery/power metrics, CPU/memory usage, and OS details
across macOS, Windows, and Linux in a non-destructive, read-only manner.
"""

import os
import platform
import re
import subprocess
import time
from typing import Any, Dict, Optional


class BasePlatformAdapter:
    def get_wifi_status(self) -> Dict[str, Any]:
        raise NotImplementedError

    def get_battery_status(self) -> Dict[str, Any]:
        raise NotImplementedError

    def get_system_metrics(self) -> Dict[str, Any]:
        raise NotImplementedError

    def get_os_info(self) -> Dict[str, Any]:
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }

    def run_cmd(self, cmd: list, timeout: float = 3.0) -> Optional[str]:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None


class MacOSAdapter(BasePlatformAdapter):
    def get_wifi_status(self) -> Dict[str, Any]:
        # Try /System/Library/.../airport or networksetup
        airport_path = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
        if os.path.exists(airport_path):
            out = self.run_cmd([airport_path, "-I"])
            if out:
                ssid_match = re.search(r"\bSSID:\s*(.+)$", out, re.MULTILINE)
                rssi_match = re.search(r"\baggrRSSI:\s*(-?\d+)", out, re.MULTILINE)
                state_match = re.search(r"\bop mode:\s*(.+)$", out, re.MULTILINE)
                if ssid_match:
                    ssid = ssid_match.group(1).strip()
                    rssi = int(rssi_match.group(1)) if rssi_match else -50
                    return {
                        "connected": True,
                        "ssid": ssid,
                        "signal_rssi": rssi,
                        "signal_quality": "Strong" if rssi > -60 else ("Fair" if rssi > -75 else "Weak"),
                        "status": "connected",
                    }

        # Fallback to networksetup
        out = self.run_cmd(["networksetup", "-getairportnetwork", "en0"])
        if out and "Current Wi-Fi Network:" in out:
            ssid = out.split("Current Wi-Fi Network:", 1)[1].strip()
            return {
                "connected": True,
                "ssid": ssid,
                "signal_quality": "Good",
                "status": "connected",
            }
        return {"connected": False, "ssid": None, "signal_quality": "N/A", "status": "disconnected"}

    def get_battery_status(self) -> Dict[str, Any]:
        out = self.run_cmd(["pmset", "-g", "batt"])
        if out:
            pct_match = re.search(r"(\d+)%", out)
            charging_match = re.search(r"(charging|discharging|charged|AC Power|Battery Power)", out, re.I)
            source_match = re.search(r"Now drawing from '([^']+)'", out)

            percent = int(pct_match.group(1)) if pct_match else None
            source = source_match.group(1) if source_match else ("AC Power" if "AC Power" in out else "Battery")
            is_charging = "charging" in (charging_match.group(0).lower() if charging_match else "")
            return {
                "has_battery": percent is not None,
                "percent": percent,
                "power_source": source,
                "is_charging": is_charging,
                "status": f"{percent}% ({'Charging' if is_charging else 'Battery'})" if percent is not None else "Desktop / AC",
            }
        return {"has_battery": False, "percent": None, "power_source": "AC", "is_charging": False, "status": "AC Power"}

    def get_system_metrics(self) -> Dict[str, Any]:
        # CPU & Memory via sysctl / ps
        load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
        return {
            "load_average_1m": round(load_avg[0], 2),
            "load_average_5m": round(load_avg[1], 2),
            "os_name": "macOS",
            "uptime_seconds": self._get_uptime(),
        }

    def _get_uptime(self) -> float:
        try:
            out = self.run_cmd(["sysctl", "-n", "kern.boottime"])
            if out:
                # { sec = 1710582000, usec = ... }
                sec_match = re.search(r"sec\s*=\s*(\d+)", out)
                if sec_match:
                    boot_sec = int(sec_match.group(1))
                    return max(0.0, time.time() - boot_sec)
        except Exception:
            pass
        return 0.0


class WindowsAdapter(BasePlatformAdapter):
    def get_wifi_status(self) -> Dict[str, Any]:
        out = self.run_cmd(["netsh", "wlan", "show", "interfaces"])
        if out:
            ssid_match = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.MULTILINE)
            signal_match = re.search(r"^\s*Signal\s*:\s*(\d+)%", out, re.MULTILINE)
            if ssid_match:
                ssid = ssid_match.group(1).strip()
                signal = int(signal_match.group(1)) if signal_match else 80
                return {
                    "connected": True,
                    "ssid": ssid,
                    "signal_percent": signal,
                    "signal_quality": "Strong" if signal > 70 else ("Fair" if signal > 40 else "Weak"),
                    "status": "connected",
                }
        return {"connected": False, "ssid": None, "signal_quality": "N/A", "status": "disconnected"}

    def get_battery_status(self) -> Dict[str, Any]:
        out = self.run_cmd(["powershell", "-NoProfile", "-Command", "Get-WmiObject -Class Win32_Battery | Select-Object -Property EstimatedChargeRemaining, BatteryStatus"])
        if out:
            pct_match = re.search(r"(\d+)", out)
            if pct_match:
                pct = int(pct_match.group(1))
                return {
                    "has_battery": True,
                    "percent": pct,
                    "power_source": "Battery",
                    "is_charging": False,
                    "status": f"{pct}%",
                }
        return {"has_battery": False, "percent": None, "power_source": "AC Power", "is_charging": False, "status": "AC Power"}

    def get_system_metrics(self) -> Dict[str, Any]:
        return {
            "load_average_1m": 0.0,
            "load_average_5m": 0.0,
            "os_name": "Windows",
            "uptime_seconds": 0.0,
        }


class LinuxAdapter(BasePlatformAdapter):
    def get_wifi_status(self) -> Dict[str, Any]:
        out = self.run_cmd(["nmcli", "-t", "-f", "active,ssid,signal", "dev", "wifi"])
        if out:
            for line in out.splitlines():
                if line.startswith("yes:"):
                    parts = line.split(":")
                    ssid = parts[1] if len(parts) > 1 else "Wi-Fi"
                    sig = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 75
                    return {
                        "connected": True,
                        "ssid": ssid,
                        "signal_percent": sig,
                        "signal_quality": "Strong" if sig > 70 else "Fair",
                        "status": "connected",
                    }
        return {"connected": False, "ssid": None, "signal_quality": "N/A", "status": "disconnected"}

    def get_battery_status(self) -> Dict[str, Any]:
        # Read /sys/class/power_supply/BAT0 or upower
        bat_capacity = "/sys/class/power_supply/BAT0/capacity"
        bat_status = "/sys/class/power_supply/BAT0/status"
        if os.path.exists(bat_capacity):
            try:
                with open(bat_capacity, "r") as f:
                    pct = int(f.read().strip())
                status = "Discharging"
                if os.path.exists(bat_status):
                    with open(bat_status, "r") as f:
                        status = f.read().strip()
                return {
                    "has_battery": True,
                    "percent": pct,
                    "power_source": "Battery",
                    "is_charging": "charging" in status.lower(),
                    "status": f"{pct}% ({status})",
                }
            except Exception:
                pass
        return {"has_battery": False, "percent": None, "power_source": "AC Power", "is_charging": False, "status": "AC Power"}

    def get_system_metrics(self) -> Dict[str, Any]:
        load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
        uptime = 0.0
        if os.path.exists("/proc/uptime"):
            try:
                with open("/proc/uptime", "r") as f:
                    uptime = float(f.read().split()[0])
            except Exception:
                pass
        return {
            "load_average_1m": round(load_avg[0], 2),
            "load_average_5m": round(load_avg[1], 2),
            "os_name": "Linux",
            "uptime_seconds": round(uptime, 1),
        }


def get_platform_adapter() -> BasePlatformAdapter:
    sys_name = platform.system()
    if sys_name == "Darwin":
        return MacOSAdapter()
    elif sys_name == "Windows":
        return WindowsAdapter()
    else:
        return LinuxAdapter()


platform_adapter = get_platform_adapter()
