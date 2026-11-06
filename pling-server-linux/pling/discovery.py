"""
Network Discovery & USB ADB Tethering for Pling Server Linux.
Sends UDP discovery broadcasts on port 7001 and automatically bridges USB via adb reverse.
Matches Mac ContentView auto-ADB and God Mode performance optimizations.
"""

import time
import socket
import shutil
import logging
import subprocess
import threading
from typing import Optional, List
from pling.config import PlingConfig

logger = logging.getLogger("PlingDiscovery")

class DiscoveryService:
    """
    Handles automatic server discovery over Wi-Fi (UDP 7001) and USB tethering via ADB.
    """
    def __init__(self, config: PlingConfig):
        self.config = config
        self._running = False
        self._udp_thread: Optional[threading.Thread] = None
        self._adb_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._adb_bin = self._find_adb()
        self._active_quest_serials: List[str] = []

    def _find_adb(self) -> Optional[str]:
        candidates = [
            shutil.which("adb"),
            "/usr/bin/adb",
            "/usr/local/bin/adb",
            os.path.expanduser("~/Android/Sdk/platform-tools/adb"),
        ]
        return next((p for p in candidates if p and os.path.exists(p)), None)

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True

            self._udp_thread = threading.Thread(target=self._udp_broadcast_loop, name="PlingUDPBroadcast", daemon=True)
            self._udp_thread.start()

            if self.config.auto_adb:
                self._adb_thread = threading.Thread(target=self._adb_monitor_loop, name="PlingADBMonitor", daemon=True)
                self._adb_thread.start()

            logger.info("Discovery service active (UDP 7001 discovery & ADB USB auto-bridge).")

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False

        # Restore Quest defaults on active devices
        if self._adb_bin and self._active_quest_serials:
            for serial in self._active_quest_serials:
                self._restore_quest_defaults(serial)
            self._active_quest_serials.clear()

    def get_local_ip(self) -> str:
        """
        Retrieves primary LAN IP address.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _udp_broadcast_loop(self) -> None:
        """
        Broadcasts MAC_SERVER:<ip>:<port> to port 7001 matching Mac ContentView startUDPBroadcast().
        Also targets subnet broadcast and iPhone hotspot subnet (.1 through .14).
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass

        base_targets = ["255.255.255.255"]

        while self._running:
            try:
                local_ip = self.get_local_ip()
                # Format matches Mac ContentView line 2141
                msg = f"MAC_SERVER:{local_ip}:{self.config.tcp_port}".encode("utf-8")

                targets = list(base_targets)
                parts = local_ip.split(".")
                if len(parts) == 4 and parts[0] != "127":
                    subnet_broadcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                    targets.append(subnet_broadcast)
                    # Send directly to hotspot range .1..14 (iPhone hotspot typically assigns Quest .4 and PC .5)
                    for i in range(1, 15):
                        targets.append(f"{parts[0]}.{parts[1]}.{parts[2]}.{i}")

                for target in set(targets):
                    try:
                        sock.sendto(msg, (target, self.config.udp_port))
                    except Exception:
                        pass

            except Exception as e:
                logger.debug(f"UDP discovery tick error: {e}")

            time.sleep(self.config.broadcast_interval)

        sock.close()

    def _adb_monitor_loop(self) -> None:
        """
        Monitors connected Quest devices via USB and sets up reverse port forward.
        Applies God Mode GPU/CPU priority levels.
        """
        if not self._adb_bin:
            logger.info("ADB executable not found. USB reverse bridge disabled.")
            return

        last_serials: List[str] = []

        while self._running:
            try:
                res = subprocess.run([self._adb_bin, "devices"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=2.0)
                lines = res.stdout.strip().splitlines()

                # Filter USB hardware serials (ignore Wi-Fi IP serials containing '.' or ':')
                current_serials = []
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == "device":
                        s = parts[0]
                        if "." not in s and ":" not in s:
                            current_serials.append(s)

                # Newly connected devices
                for serial in current_serials:
                    if serial not in last_serials:
                        logger.info(f"Meta Quest connected via USB cable: {serial}")
                        # Reverse port forward: 3000 -> 3000
                        subprocess.run([self._adb_bin, "-s", serial, "reverse", f"tcp:{self.config.tcp_port}", f"tcp:{self.config.tcp_port}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2.0)
                        if self.config.god_mode_optimizations:
                            self._apply_quest_god_mode(serial)
                        if serial not in self._active_quest_serials:
                            self._active_quest_serials.append(serial)

                # Disconnected devices
                for serial in last_serials:
                    if serial not in current_serials:
                        logger.info(f"Meta Quest USB disconnected: {serial}. Restoring defaults...")
                        self._restore_quest_defaults(serial)
                        if serial in self._active_quest_serials:
                            self._active_quest_serials.remove(serial)

                last_serials = current_serials

            except Exception as e:
                logger.debug(f"ADB monitor loop tick error: {e}")

            time.sleep(3.0)

    def _apply_quest_god_mode(self, serial: str) -> None:
        """
        Applies high-performance settings to Quest via ADB shell.
        Matching Mac optimizeQuestPerformance(): CPU/GPU level 5, sharpening 1, no foveation.
        """
        commands = [
            ["shell", "setprop", "debug.oculus.cpu_level", "5"],
            ["shell", "setprop", "debug.oculus.gpu_level", "5"],
            ["shell", "setprop", "debug.oculus.foveation.level", "0"],
            ["shell", "setprop", "debug.oculus.layer.sharpening", "1"],
            ["shell", "am", "broadcast", "-a", "com.oculus.vrpowermanager.prox_sensor_off"]
        ]
        for cmd in commands:
            try:
                subprocess.run([self._adb_bin, "-s", serial] + cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.0)
            except Exception:
                pass
        logger.info(f"💎 God Mode parameters applied to Quest ({serial}): Max CPU/GPU clock, sharpening enabled.")

    def _restore_quest_defaults(self, serial: str) -> None:
        """
        Restores Quest properties to defaults when streaming ends.
        Matching Mac restoreQuestDefaults().
        """
        commands = [
            ["shell", "setprop", "debug.oculus.cpu_level", "0"],
            ["shell", "setprop", "debug.oculus.gpu_level", "0"],
            ["shell", "setprop", "debug.oculus.foveation.level", "0"],
            ["shell", "setprop", "debug.oculus.layer.sharpening", "0"],
            ["shell", "am", "broadcast", "-a", "com.oculus.vrpowermanager.prox_sensor_on"],
            ["reverse", "--remove", f"tcp:{self.config.tcp_port}"]
        ]
        for cmd in commands:
            try:
                subprocess.run([self._adb_bin, "-s", serial] + cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1.0)
            except Exception:
                pass
        logger.info(f"♻️ Quest defaults restored for device {serial}.")
