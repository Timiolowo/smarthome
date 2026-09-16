"""
Hardware Device Inventory for Smart Home Assistant.
Maintains grounded truth on what smart-home appliances are connected vs unconnected
to prevent the AI from hallucinating physical actions.
"""

import json
import os
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEVICES_FILE = os.path.join(DATA_DIR, "devices.json")


class DeviceInventory:
    DEFAULT_DEVICES = {
        "lights": {
            "name": "Smart Lights",
            "category": "lighting",
            "connected": False,
            "status": "unconnected",
            "description": "Smart LED bulbs / switches (Philips Hue, Zigbee, etc.)",
        },
        "ac": {
            "name": "Air Conditioner / Climate",
            "category": "climate",
            "connected": False,
            "status": "unconnected",
            "description": "Smart thermostat or AC infrared controller",
        },
        "tv": {
            "name": "Smart TV / Media Player",
            "category": "entertainment",
            "connected": False,
            "status": "unconnected",
            "description": "Apple TV, Android TV, HDMI-CEC or Smart TV switch",
        },
        "fans": {
            "name": "Smart Fan",
            "category": "climate",
            "connected": False,
            "status": "unconnected",
            "description": "Smart plug / ceiling fan controller",
        },
        "plugs": {
            "name": "Smart Plugs",
            "category": "power",
            "connected": False,
            "status": "unconnected",
            "description": "Smart power sockets",
        },
    }

    def __init__(self, devices_file: str = DEVICES_FILE):
        self.devices_file = devices_file
        self.devices = self._load_devices()

    def _load_devices(self) -> Dict[str, Any]:
        if not os.path.exists(self.devices_file):
            self._save_devices(self.DEFAULT_DEVICES)
            return dict(self.DEFAULT_DEVICES)
        try:
            with open(self.devices_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return dict(self.DEFAULT_DEVICES)

    def _save_devices(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.devices_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[DeviceInventory] Failed to save devices: {e}")

    def is_connected(self, device_key: str) -> bool:
        """Returns True only if physical hardware for device_key is verified connected."""
        key = device_key.lower().strip()
        dev = self.devices.get(key)
        if dev:
            return dev.get("connected") is True
        for k, v in self.devices.items():
            if k in key or key in k:
                return v.get("connected") is True
        return False

    def get_grounded_refusal(self, device_name: str, action: str = "control") -> str:
        """Returns an honest, grounded refusal explaining the physical hardware is not connected."""
        clean_dev = device_name.strip()
        return (
            f"I cannot {action} the {clean_dev} because we don't have smart {clean_dev} hardware connected to the system yet. "
            "I will only confirm device actions once physical smart switches or hubs are integrated."
        )

    def list_devices(self) -> List[Dict[str, Any]]:
        return [{"id": k, **v} for k, v in self.devices.items()]

    def set_device_connected(self, device_key: str, connected: bool, name: Optional[str] = None) -> None:
        if device_key not in self.devices:
            self.devices[device_key] = {
                "name": name or device_key.capitalize(),
                "category": "custom",
                "connected": connected,
                "status": "online" if connected else "unconnected",
            }
        else:
            self.devices[device_key]["connected"] = connected
            self.devices[device_key]["status"] = "online" if connected else "unconnected"
            if name:
                self.devices[device_key]["name"] = name
        self._save_devices(self.devices)


device_inventory = DeviceInventory()
