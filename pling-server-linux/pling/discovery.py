"""
Network Discovery & USB ADB Tethering for Pling Server Linux.
Sends UDP broadcasts on port 7001 and automatically bridges USB via adb reverse.
"""

import time
import socket
import shutil
import logging
import subprocess
import threading
from typing import Optional
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
        self._adb_bin = shutil.which("adb")

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

            logger.info("Discovery service started (UDP broadcast & ADB auto-reverse).")

    def stop(self) -> None:
        with self._lock:
            self._running = False

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
        Broadcasts LINUX_SERVER:<ip>:<port> to port 7001 so Quest auto-connects.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        targets = ["255.255.255.255"]

        while self._running:
            try:
                local_ip = self.get_local_ip()
                message = f"LINUX_SERVER:{local_ip}:{self.config.tcp_port}".encode("utf-8")

                # Derive subnet broadcast (e.g. 192.168.1.255)
                parts = local_ip.split(".")
                if len(parts) == 4 and parts[0] != "127":
                    subnet_broadcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                    current_targets = list(set(targets + [subnet_broadcast]))
                else:
                    current_targets = targets

                for target in current_targets:
                    try:
                        sock.sendto(message, (target, self.config.udp_port))
                    except Exception:
                        pass

            except Exception as e:
                logger.debug(f"UDP broadcast tick error: {e}")

            time.sleep(self.config.broadcast_interval)

        sock.close()

    def _adb_monitor_loop(self) -> None:
        """
        Monitors connected Quest devices and ensures 'adb reverse tcp:3000 tcp:3000' is active.
        """
        if not self._adb_bin:
            logger.info("ADB binary not found in PATH. USB auto-reverse disabled.")
            return

        last_connected = False

        while self._running:
            try:
                result = subprocess.run(
                    [self._adb_bin, "devices"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=2.0
                )
                lines = result.stdout.strip().splitlines()
                devices = [line.split()[0] for line in lines[1:] if "\tdevice" in line]

                if devices:
                    if not last_connected:
                        logger.info(f"Quest detected via USB: {devices[0]}. Setting up zero-latency reverse bridge...")
                        for serial in devices:
                            subprocess.run([self._adb_bin, "-s", serial, "reverse", f"tcp:{self.config.tcp_port}", f"tcp:{self.config.tcp_port}"], timeout=2.0)
                            if self.config.god_mode_optimizations:
                                self._apply_quest_god_mode(serial)
                        last_connected = True
                else:
                    last_connected = False

            except Exception as e:
                logger.debug(f"ADB check loop: {e}")

            time.sleep(3.0)

    def _apply_quest_god_mode(self, serial: str) -> None:
        """
        Applies performance and sharpening flags on Meta Quest via ADB.
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
        logger.info(f"💎 God Mode parameters applied to Quest ({serial}).")
