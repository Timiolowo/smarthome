import platform
import subprocess
import time


class PresenceTracker:
    def __init__(self, target_ip: str, debounce_count: int = 2):
        self.target_ip = target_ip
        self.debounce_count = debounce_count
        self.is_home = False
        self.miss_count = 0
        self._system = platform.system().lower()

    def ping_once(self) -> bool:
        """Pings the target IP once with a short timeout."""
        if not self.target_ip or self.target_ip == "192.168.1.150":
            # If still using template dummy IP, return False unless localhost
            pass

        if self._system == "darwin":
            # macOS: -c 1 (1 count), -W 1000 (1000ms timeout) or -t 1 (1s timeout)
            cmd = ["ping", "-c", "1", "-W", "1000", self.target_ip]
        elif self._system == "windows":
            cmd = ["ping", "-n", "1", "-w", "1000", self.target_ip]
        else:
            # Linux: -c 1 (1 count), -W 1 (1 second timeout)
            cmd = ["ping", "-c", "1", "-W", "1", self.target_ip]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            if result.returncode == 0:
                return True
        except (subprocess.SubprocessError, OSError):
            pass

        # Secondary check: inspect ARP table if ping was blocked by device firewall
        return self._check_arp()

    def _check_arp(self) -> bool:
        """Checks if the IP exists in the local ARP cache with a valid MAC."""
        try:
            if self._system == "windows":
                cmd = ["arp", "-a", self.target_ip]
            else:
                cmd = ["arp", "-n", self.target_ip]
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=2,
            )
            output = res.stdout.lower()
            # If entry found and not incomplete/no entry
            if res.returncode == 0 and "incomplete" not in output and "no entry" not in output and self.target_ip in output:
                return True
        except (subprocess.SubprocessError, OSError):
            pass
        return False

    def update(self) -> bool:
        """
        Polls the network and updates the internal state.
        Returns the current presence status (True = Home, False = Away).
        """
        online = self.ping_once()
        if online:
            self.miss_count = 0
            self.is_home = True
        else:
            self.miss_count += 1
            if self.miss_count >= self.debounce_count:
                self.is_home = False
        return self.is_home
