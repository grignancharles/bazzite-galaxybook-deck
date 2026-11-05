"""
System Tray Mini-App for Pling Server Linux.
Supports PyQt6, PySide6, and GTK3 / AyatanaAppIndicator StatusNotifierItem.
Integrates natively into KDE Plasma and Bazzite taskbar.
"""

import os
import sys
import json
import time
import socket
import logging
import subprocess
import threading
from typing import Optional, Dict

logger = logging.getLogger("PlingTray")

class PlingClientIPC:
    """
    Communicates with the background PlingServer daemon via Unix Domain Socket.
    """
    def __init__(self, sock_path: str = "/tmp/pling-server.sock"):
        self.sock_path = sock_path

    def request(self, cmd_dict: dict, timeout: float = 1.0) -> Optional[dict]:
        if not os.path.exists(self.sock_path):
            return None
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(self.sock_path)
            s.sendall(json.dumps(cmd_dict).encode("utf-8"))
            raw = s.recv(4096).decode("utf-8")
            s.close()
            return json.loads(raw)
        except Exception:
            return None

    def get_status(self) -> Optional[dict]:
        return self.request({"command": "status"})

    def set_bitrate(self, mbps: int) -> bool:
        res = self.request({"command": "set_bitrate", "bitrate_mbps": mbps})
        return bool(res and res.get("status") == "ok")

    def toggle_audio(self, enabled: bool) -> bool:
        res = self.request({"command": "toggle_audio", "enabled": enabled})
        return bool(res and res.get("status") == "ok")

    def force_keyframe(self) -> bool:
        res = self.request({"command": "force_keyframe"})
        return bool(res and res.get("status") == "ok")

    def stop_stream(self) -> bool:
        res = self.request({"command": "stop_stream"})
        return bool(res and res.get("status") == "ok")

    def start_stream(self) -> bool:
        res = self.request({"command": "start_stream"})
        return bool(res and res.get("status") == "ok")


def run_qt_tray():
    """
    Runs the PyQt6 / PySide6 implementation of the System Tray widget.
    """
    try:
        from PyQt6 import QtWidgets, QtGui, QtCore
        from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
        from PyQt6.QtGui import QIcon, QAction
        Qt = QtCore.Qt
    except ImportError:
        try:
            from PySide6 import QtWidgets, QtGui, QtCore
            from PySide6.QtWidgets import QSystemTrayIcon, QMenu
            from PySide6.QtGui import QIcon, QAction
            Qt = QtCore.Qt
        except ImportError:
            return False

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    ipc = PlingClientIPC()
    assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    icon_active_path = os.path.join(assets_dir, "pling-icon-active.svg")
    icon_idle_path = os.path.join(assets_dir, "pling-icon-idle.svg")
    icon_wait_path = os.path.join(assets_dir, "pling-icon-waiting.svg")

    tray = QSystemTrayIcon()
    tray.setIcon(QIcon(icon_idle_path if os.path.exists(icon_idle_path) else ""))
    tray.setVisible(True)

    menu = QMenu()

    # Title header
    header_action = QAction("🎮 Pling Server (Tiger Lake)", menu)
    header_action.setEnabled(False)
    menu.addAction(header_action)

    status_action = QAction("⚪ Waiting for Quest...", menu)
    status_action.setEnabled(False)
    menu.addAction(status_action)

    menu.addSeparator()

    # Toggle Stream
    toggle_stream_action = QAction("⏹ Stop Streaming", menu)
    menu.addAction(toggle_stream_action)

    # Force IDR Keyframe
    keyframe_action = QAction("🔄 Refresh Screen (IDR Keyframe)", menu)
    menu.addAction(keyframe_action)

    menu.addSeparator()

    # Bitrate Submenu
    bitrate_menu = menu.addMenu("⚡ Bitrate Presets")
    bitrate_actions = {}
    for mbps in [15, 25, 35, 50, 70]:
        act = QAction(f"{mbps} Mbps", bitrate_menu)
        act.setCheckable(True)
        bitrate_actions[mbps] = act
        bitrate_menu.addAction(act)

    # Audio Toggle
    audio_action = QAction("🔊 Desktop Audio (PipeWire)", menu)
    audio_action.setCheckable(True)
    audio_action.setChecked(True)
    menu.addAction(audio_action)

    menu.addSeparator()

    # Quit
    quit_action = QAction("❌ Quit Pling", menu)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)

    # State tracking
    last_connected_count = 0

    def trigger_toggle_stream():
        status = ipc.get_status()
        if status and status.get("running"):
            if status.get("fps", 0) > 0:
                ipc.stop_stream()
            else:
                ipc.start_stream()

    toggle_stream_action.triggered.connect(trigger_toggle_stream)
    keyframe_action.triggered.connect(lambda: ipc.force_keyframe())

    def make_bitrate_handler(val):
        return lambda: ipc.set_bitrate(val)

    for mbps, act in bitrate_actions.items():
        act.triggered.connect(make_bitrate_handler(mbps))

    def toggle_audio_handler():
        ipc.toggle_audio(audio_action.isChecked())

    audio_action.triggered.connect(toggle_audio_handler)
    quit_action.triggered.connect(app.quit)

    # Periodic update timer
    timer = QtCore.QTimer()

    def update_state():
        nonlocal last_connected_count
        status = ipc.get_status()

        if not status:
            tray.setIcon(QIcon(icon_idle_path))
            tray.setToolTip("Pling Server: Offline")
            status_action.setText("⚪ Server Offline")
            toggle_stream_action.setText("▶ Start Server")
            return

        clients_count = status.get("clients_count", 0)
        avg_rtt = status.get("avg_rtt_ms", 0.0)
        fps = status.get("fps", 0.0)
        bitrate = status.get("bitrate_mbps", 30)
        audio_on = status.get("audio_enabled", True)

        # Notify on new connection
        if clients_count > last_connected_count:
            client_ip = status["clients"][0]["ip"] if status.get("clients") else "Quest"
            is_usb = status["clients"][0]["is_usb"] if status.get("clients") else False
            tray.showMessage(
                "Meta Quest Connected",
                f"Active Link: {'USB Cable (0ms)' if is_usb else 'Wi-Fi'} ({client_ip})\nHardware: Intel Iris Xe Gen12",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )
        elif clients_count < last_connected_count and last_connected_count > 0:
            tray.showMessage(
                "Meta Quest Disconnected",
                "Quest stream session ended.",
                QSystemTrayIcon.MessageIcon.Warning,
                2000
            )

        last_connected_count = clients_count

        # Update icons & tooltips
        if clients_count > 0:
            tray.setIcon(QIcon(icon_active_path))
            link_desc = "USB" if any(c["is_usb"] for c in status["clients"]) else "Wi-Fi"
            status_text = f"🟢 Streaming ({link_desc}) | {avg_rtt}ms RTT | {fps} FPS"
            tray.setToolTip(f"Pling Server: Connected ({link_desc})\nRTT: {avg_rtt}ms | {bitrate} Mbps | {fps} FPS")
        else:
            tray.setIcon(QIcon(icon_wait_path))
            status_text = f"🟡 Waiting for Quest... ({fps} FPS)"
            tray.setToolTip(f"Pling Server: Waiting for Quest on port 3000\n{bitrate} Mbps | {fps} FPS")

        status_action.setText(status_text)
        toggle_stream_action.setText("⏹ Stop Streaming" if fps > 0 else "▶ Resume Streaming")

        # Update checked preset
        for mbps, act in bitrate_actions.items():
            act.setChecked(mbps == bitrate)

        audio_action.setChecked(audio_on)

    timer.timeout.connect(update_state)
    timer.start(1000)
    update_state()

    logger.info("PyQt6 / PySide6 System Tray initialized.")
    return app.exec()


def run_gtk_tray():
    """
    Fallback implementation using GTK3 / AyatanaAppIndicator StatusNotifierItem.
    """
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        try:
            gi.require_version("AyatanaAppIndicator3", "0.1")
            from gi.repository import AyatanaAppIndicator3 as AppIndicator
        except (ValueError, ImportError):
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3 as AppIndicator
        from gi.repository import Gtk, GLib
    except Exception as e:
        logger.error(f"GTK AppIndicator not available: {e}")
        return False

    ipc = PlingClientIPC()
    assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    icon_active_path = os.path.join(assets_dir, "pling-icon-active.svg")
    icon_idle_path = os.path.join(assets_dir, "pling-icon-idle.svg")

    indicator = AppIndicator.Indicator.new(
        "pling-server-tray",
        icon_idle_path,
        AppIndicator.IndicatorCategory.APPLICATION_STATUS
    )
    indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)

    menu = Gtk.Menu()

    header_item = Gtk.MenuItem(label="🎮 Pling Server Linux")
    header_item.set_sensitive(False)
    menu.append(header_item)

    status_item = Gtk.MenuItem(label="⚪ Waiting for Quest...")
    status_item.set_sensitive(False)
    menu.append(status_item)

    sep = Gtk.SeparatorMenuItem()
    menu.append(sep)

    refresh_item = Gtk.MenuItem(label="🔄 Refresh Screen (IDR Keyframe)")
    refresh_item.connect("activate", lambda _: ipc.force_keyframe())
    menu.append(refresh_item)

    quit_item = Gtk.MenuItem(label="❌ Quit")
    quit_item.connect("activate", lambda _: Gtk.main_quit())
    menu.append(quit_item)

    menu.show_all()
    indicator.set_menu(menu)

    def update_gtk():
        status = ipc.get_status()
        if status and status.get("clients_count", 0) > 0:
            indicator.set_icon_full(icon_active_path, "Pling Active")
            rtt = status.get("avg_rtt_ms", 0.0)
            status_item.set_label(f"🟢 Streaming | {rtt}ms RTT")
        else:
            indicator.set_icon_full(icon_idle_path, "Pling Idle")
            status_item.set_label("🟡 Waiting for Quest...")
        return True

    GLib.timeout_add_seconds(1, update_gtk)
    logger.info("GTK3 AppIndicator System Tray initialized.")
    Gtk.main()
    return True


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    # Try PyQt / PySide first (KDE Plasma standard)
    if run_qt_tray():
        return
    # Fallback to GTK
    if run_gtk_tray():
        return
    logger.warning("No GUI toolkit available for System Tray. Running CLI status monitor instead.")
    ipc = PlingClientIPC()
    while True:
        status = ipc.get_status()
        print(f"\rStatus: {json.dumps(status)}", end="", flush=True)
        time.sleep(1.0)

if __name__ == "__main__":
    main()
